#!/usr/bin/env bash
#SBATCH --job-name=echotrace-native-prep
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -Eeuo pipefail
: "${ECHOTRACE_ROOT:?}"
: "${ECHOTRACE_BACKEND:?}"
python="$ECHOTRACE_ROOT/envs/detector/bin/python"
uv="$ECHOTRACE_ROOT/envs/runtime/bin/uv"
manifest="$ECHOTRACE_ROOT/runs/native-frozen-01/acceptance2.csv"
mkdir -p "$(dirname "$manifest")" "$ECHOTRACE_ROOT/models"

"$uv" pip install --python "$python" 'transformers>=4.48,<5' \
  'huggingface-hub>=0.28,<1' 'safetensors>=0.5,<1'

"$python" - "$ECHOTRACE_ROOT" "$manifest" <<'PY'
import csv, sys
from collections import Counter
from pathlib import Path
root, output = Path(sys.argv[1]), Path(sys.argv[2])
manifests = root/'runs/aasist-aa-01/manifests'
def rows(path):
    with path.open(encoding='utf-8', newline='') as handle: return list(csv.DictReader(handle))
selection, old = rows(manifests/'selection.csv'), rows(manifests/'acceptance.csv')
used = {r['speaker_id'] for r in selection + old}
remaining = [r for r in rows(root/'data/asvspoof5-aa/dev.csv') if r['speaker_id'] not in used]
counts = Counter(r['label'] for r in remaining)
if set(counts) != {'0','1'} or min(counts.values()) < 100 or len(remaining) > 10000:
    raise SystemExit(f'Fresh acceptance counts invalid: {counts}')
if output.exists(): raise SystemExit('Fresh acceptance output already exists')
with output.open('w', encoding='utf-8', newline='') as handle:
    writer=csv.DictWriter(handle, fieldnames=remaining[0].keys(), lineterminator='\n')
    writer.writeheader(); writer.writerows(remaining)
print({'rows':len(remaining),'speakers':len({r['speaker_id'] for r in remaining}),'labels':counts})
PY

cd "$ECHOTRACE_BACKEND"
"$python" -m echotrace.native_detector_eval --setup \
  --cache "$ECHOTRACE_ROOT/models/garystafford-c663060"
sha256sum "$manifest" \
  "$ECHOTRACE_ROOT/models/garystafford-c663060/model.safetensors" \
  "$ECHOTRACE_BACKEND/echotrace/native_detector_eval.py" \
  > "$ECHOTRACE_ROOT/runs/native-frozen-01/preflight.sha256"
