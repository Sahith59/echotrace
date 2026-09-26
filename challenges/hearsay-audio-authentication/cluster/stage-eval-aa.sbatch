#!/usr/bin/env bash
#SBATCH --job-name=echotrace-eval-stage
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=03:00:00
set -Eeuo pipefail
: "${ECHOTRACE_ROOT:?}"
: "${ECHOTRACE_EVAL_MANIFEST:?}"
export PATH="$ECHOTRACE_ROOT/envs/runtime/bin:/usr/bin:/bin"
target="$ECHOTRACE_ROOT/data/asvspoof5-eval-aa"
[[ ! -e "$target" && -f "$ECHOTRACE_EVAL_MANIFEST" ]]
temp="$ECHOTRACE_ROOT/data/.eval-aa-$SLURM_JOB_ID"
mkdir "$temp"
trap 'failed="$ECHOTRACE_ROOT/data/.eval-aa-failed-$SLURM_JOB_ID"; mv -- "$temp" "$failed"; echo "Preserved failed staging at $failed" >&2' ERR
url='https://zenodo.org/api/records/14498691/files/flac_E_aa.tar/content'
archive_dir="$ECHOTRACE_ROOT/downloads/asvspoof5-eval-aa"
archive="$archive_dir/flac_E_aa.tar"
mkdir -p "$archive_dir"
python="$ECHOTRACE_ROOT/envs/detector/bin/python"
backend="$ECHOTRACE_ROOT/source/9903fac/backend"
smoke=$(find "$ECHOTRACE_ROOT/data/asvspoof5-aa/audio" -type f -name '*.flac' -print -quit)
[[ -n "$smoke" ]]
PYTHONPATH="$backend" "$python" - "$smoke" <<'PY'
import sys
from pathlib import Path
from echotrace.audio import decode_audio
samples,info=decode_audio(Path(sys.argv[1]))
assert len(samples)>0 and info['analysis_sample_rate']==16000
print(f"decoder smoke passed: {info['codec']} {info['duration_s']}s")
PY
if [[ ! -f "$archive" ]]; then
  chunk=2112445440
  pids=()
  for i in 0 1 2 3; do
    start=$((i*chunk)); end=$((start+chunk-1)); part="$archive_dir/flac_E_aa.tar.part-$i"
    curl --fail --location --retry 3 --connect-timeout 30 --max-filesize "$chunk" \
      --range "$start-$end" --output "$part" "$url" &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do wait "$pid"; done
  for i in 0 1 2 3; do [[ $(stat -c %s "$archive_dir/flac_E_aa.tar.part-$i") = "$chunk" ]]; done
  cat "$archive_dir"/flac_E_aa.tar.part-{0,1,2,3} > "$archive.part"
  [[ $(stat -c %s "$archive.part") = 8449781760 ]]
  [[ $(md5sum "$archive.part" | cut -d' ' -f1) = a8c800766f3d4ef87971e2b4f29663e2 ]]
  mv "$archive.part" "$archive"
  rm "$archive_dir"/flac_E_aa.tar.part-{0,1,2,3}
fi
[[ $(stat -c %s "$archive") = 8449781760 ]]
[[ $(md5sum "$archive" | cut -d' ' -f1) = a8c800766f3d4ef87971e2b4f29663e2 ]]
sha256sum "$archive" > "$temp/archive.sha256"
tar -tf "$archive" > "$temp/members.txt"
awk 'BEGIN{ok=1} $0!="flac_E_eval/" && $0 !~ /^flac_E_eval\/E_[0-9]+\.flac$/ {ok=0} END{exit !ok}' "$temp/members.txt"
[[ $(sort "$temp/members.txt" | uniq -d | wc -l) = 0 ]]
mkdir "$temp/audio"
tar --no-same-owner --no-same-permissions -xf "$archive" -C "$temp/audio"

PYTHONPATH="$backend" "$python" - "$ECHOTRACE_EVAL_MANIFEST" "$temp" <<'PY'
import csv, hashlib, json, sys
from collections import Counter
from pathlib import Path
from echotrace.audio import decode_audio, measure_audio
manifest, temp = map(Path, sys.argv[1:])
audio = temp/'audio'
with manifest.open(encoding='utf-8', newline='') as h:
    reader=csv.DictReader(h); fields=reader.fieldnames; rows=list(reader)
available=[r for r in rows if (audio/r['path']).is_file()]
if len(available) != 68188 or Counter(r['label'] for r in available) != {'0':14171,'1':54017}:
    raise SystemExit('Eval-aa membership/count mismatch')
def rank(row): return hashlib.sha256(('acceptance3-20260926:'+row['file_id']).encode()).digest()
selected=[]
for label in ('0','1'):
    selected += sorted((r for r in available if r['label']==label), key=rank)[:1000]
selected.sort(key=lambda r:r['file_id'])
fail=[]
for i,row in enumerate(selected,1):
    try:
        samples,info=decode_audio(audio/row['path']); _,_,quiet=measure_audio(samples)
        if quiet: raise ValueError('quiet')
    except Exception as exc: fail.append({'file_id':row['file_id'],'reason':str(exc)})
    if i%250==0: print(f'audited {i}/2000',flush=True)
if fail: raise SystemExit(f'Acceptance3 audio audit failed: {fail[:5]}')
out=temp/'acceptance3.csv'
with out.open('w',encoding='utf-8',newline='') as h:
    w=csv.DictWriter(h,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(selected)
report={'dataset':'ASVspoof5 Track1 eval aa','rows':2000,'labels':Counter(r['label'] for r in selected),
        'speakers':len({r['speaker_id'] for r in selected}),
        'sources':len({r['source_id'] for r in selected}),
        'manifest_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
        'selection_rule':'lowest sha256(acceptance3-20260926:file_id), 1000/class',
        'audio_audit':{'decoded':2000,'failures':0,'quiet':0},
        'archive':{'name':'flac_E_aa.tar','bytes':8449781760,'md5':'a8c800766f3d4ef87971e2b4f29663e2',
                   'sha256':(temp/'archive.sha256').read_text().split()[0]}}
(temp/'provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
PY
mv "$temp" "$target"
