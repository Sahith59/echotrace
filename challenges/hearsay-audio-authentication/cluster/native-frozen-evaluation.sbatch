#!/usr/bin/env bash
#SBATCH --job-name=echotrace-native
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:A100:1
#SBATCH --mem=32G
#SBATCH --time=01:30:00
set -Eeuo pipefail

: "${ECHOTRACE_ROOT:?}"
: "${ECHOTRACE_BACKEND:?}"
: "${ECHOTRACE_ACCEPTANCE2:?}"
: "${ECHOTRACE_OUTPUT:?}"
python="$ECHOTRACE_ROOT/envs/detector/bin/python"
dataset="$ECHOTRACE_ROOT/data/asvspoof5-aa/audio"
selection="$ECHOTRACE_ROOT/runs/aasist-aa-01/manifests/selection.csv"
old_acceptance="$ECHOTRACE_ROOT/runs/aasist-aa-01/manifests/acceptance.csv"
baseline_selection="$ECHOTRACE_ROOT/runs/aasist-aa-01/evaluation/selection-baseline"
model_cache="$ECHOTRACE_ROOT/models/garystafford-c663060"

[[ -x "$python" && -d "$ECHOTRACE_BACKEND" && -f "$selection" \
   && -f "$old_acceptance" && -f "$ECHOTRACE_ACCEPTANCE2" \
   && -f "$baseline_selection/run.json" && ! -e "$ECHOTRACE_OUTPUT" ]]

"$python" - "$selection" "$old_acceptance" "$ECHOTRACE_ACCEPTANCE2" <<'PY'
import csv, sys
from collections import Counter
from pathlib import Path
selection, old, fresh = map(Path, sys.argv[1:])
def rows(path): return list(csv.DictReader(path.open(encoding="utf-8", newline="")))
s, o, f = rows(selection), rows(old), rows(fresh)
used = {r["speaker_id"] for r in s + o}
fresh_speakers = {r["speaker_id"] for r in f}
if used & fresh_speakers or len(f) < 200 or min(Counter(r["label"] for r in f).values()) < 100:
    raise SystemExit("Fresh acceptance speaker/count preflight failed")
if {r["file_id"] for r in s + o} & {r["file_id"] for r in f}:
    raise SystemExit("Fresh acceptance file overlap")
print({"fresh_rows": len(f), "fresh_speakers": len(fresh_speakers),
       "labels": Counter(r["label"] for r in f)})
PY

mkdir "$ECHOTRACE_OUTPUT"
started=$(date +%s)
cd "$ECHOTRACE_BACKEND"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$ECHOTRACE_OUTPUT/gpu.csv"

"$python" -m echotrace.checkpoint_eval "$ECHOTRACE_ACCEPTANCE2" \
  --dataset-root "$dataset" --output "$ECHOTRACE_OUTPUT/acceptance2-baseline" \
  --device cuda --role acceptance --max-wall-seconds 1200

"$python" -m echotrace.native_detector_eval "$selection" \
  --dataset-root "$dataset" --output "$ECHOTRACE_OUTPUT/selection-native" \
  --cache "$model_cache" --compatibility-run "$baseline_selection/run.json" \
  --device cuda --role selection --max-seconds 2400

"$python" -m echotrace.native_detector_eval "$ECHOTRACE_ACCEPTANCE2" \
  --dataset-root "$dataset" --output "$ECHOTRACE_OUTPUT/acceptance2-native" \
  --cache "$model_cache" \
  --compatibility-run "$ECHOTRACE_OUTPUT/acceptance2-baseline/run.json" \
  --device cuda --role acceptance --max-seconds 1200

"$python" -m echotrace.acceptance \
  --baseline-selection "$baseline_selection" \
  --candidate-selection "$ECHOTRACE_OUTPUT/selection-native" \
  --baseline-acceptance "$ECHOTRACE_OUTPUT/acceptance2-baseline" \
  --candidate-acceptance "$ECHOTRACE_OUTPUT/acceptance2-native" \
  --output "$ECHOTRACE_OUTPUT/acceptance-report.json"

finished=$(date +%s)
"$python" - "$ECHOTRACE_OUTPUT" "$started" "$finished" <<'PY'
import hashlib, json, sys
from pathlib import Path
root, started, finished = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
source = Path(__import__('echotrace.native_detector_eval', fromlist=['x']).__file__)
job = Path(__file__) if '__file__' in globals() else None
report = {"wall_seconds": finished-started,
          "evaluator_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
          "gpu": (root/'gpu.csv').read_text().strip()}
(root/'runtime.json').write_text(json.dumps(report, indent=2)+'\n')
PY
