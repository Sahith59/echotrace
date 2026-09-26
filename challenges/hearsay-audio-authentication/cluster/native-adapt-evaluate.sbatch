#!/usr/bin/env bash
#SBATCH --job-name=echotrace-adapt
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:A100:1
#SBATCH --mem=32G
#SBATCH --time=03:30:00
set -Eeuo pipefail
: "${ECHOTRACE_ROOT:?}"; : "${ECHOTRACE_BACKEND:?}"; : "${ECHOTRACE_OUTPUT:?}"
root="$ECHOTRACE_ROOT"; python="$root/envs/detector/bin/python"
train="$root/runs/aasist-aa-01/manifests/train.csv"
selection="$root/runs/aasist-aa-01/manifests/selection.csv"
acceptance="$root/data/asvspoof5-eval-aa/acceptance3.csv"
train_audio="$root/data/asvspoof5-aa/audio"
accept_audio="$root/data/asvspoof5-eval-aa/audio"
base_selection="$root/runs/aasist-aa-01/evaluation/selection-baseline"
cache="$root/models/garystafford-c663060"
[[ -x "$python" && -f "$acceptance" && -f "$root/data/asvspoof5-eval-aa/provenance.json" \
   && -f "$base_selection/run.json" && ! -e "$ECHOTRACE_OUTPUT" ]]

"$python" - "$train" "$selection" "$acceptance" <<'PY'
import csv,sys
from collections import Counter
def rows(p):
 with open(p,encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
t,s,a=map(rows,sys.argv[1:])
if (len(t),len(s),len(a))!=(10000,2000,2000) or Counter(r['label'] for r in a)!={'0':1000,'1':1000}:
 raise SystemExit('Frozen split counts changed')
for field in ('file_id','speaker_id','source_id'):
 if ({r[field] for r in t+s}&{r[field] for r in a}):raise SystemExit(f'Acceptance overlap: {field}')
print('Independent acceptance3 preflight passed')
PY

mkdir "$ECHOTRACE_OUTPUT"
started=$(date +%s)
cd "$ECHOTRACE_BACKEND"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$ECHOTRACE_OUTPUT/gpu.csv"
"$python" -m echotrace.native_adapt --train "$train" --selection "$selection" \
  --dataset-root "$train_audio" --output "$ECHOTRACE_OUTPUT/adapt" --cache "$cache"

"$python" -m echotrace.checkpoint_eval "$acceptance" --dataset-root "$accept_audio" \
  --output "$ECHOTRACE_OUTPUT/acceptance3-baseline" --device cuda --role acceptance --max-wall-seconds 1800
"$python" -m echotrace.native_detector_eval "$selection" --dataset-root "$train_audio" \
  --output "$ECHOTRACE_OUTPUT/selection-adapted" --cache "$cache" \
  --adapted-model "$ECHOTRACE_OUTPUT/adapt/best" --compatibility-run "$base_selection/run.json" \
  --device cuda --role selection --max-seconds 1800
"$python" -m echotrace.native_detector_eval "$acceptance" --dataset-root "$accept_audio" \
  --output "$ECHOTRACE_OUTPUT/acceptance3-adapted" --cache "$cache" \
  --adapted-model "$ECHOTRACE_OUTPUT/adapt/best" \
  --compatibility-run "$ECHOTRACE_OUTPUT/acceptance3-baseline/run.json" \
  --device cuda --role acceptance --max-seconds 1800
"$python" -m echotrace.acceptance --baseline-selection "$base_selection" \
  --candidate-selection "$ECHOTRACE_OUTPUT/selection-adapted" \
  --baseline-acceptance "$ECHOTRACE_OUTPUT/acceptance3-baseline" \
  --candidate-acceptance "$ECHOTRACE_OUTPUT/acceptance3-adapted" \
  --output "$ECHOTRACE_OUTPUT/acceptance-report.json"
finished=$(date +%s)
"$python" - "$ECHOTRACE_OUTPUT" "$started" "$finished" <<'PY'
import hashlib,json,sys
from pathlib import Path
root,start,end=Path(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3])
source=Path(__import__('echotrace.native_adapt',fromlist=['x']).__file__)
(root/'runtime.json').write_text(json.dumps({'wall_seconds':end-start,'adapt_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'gpu':(root/'gpu.csv').read_text().strip()},indent=2)+'\n')
PY
