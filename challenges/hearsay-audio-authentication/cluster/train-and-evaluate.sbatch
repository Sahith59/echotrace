#!/usr/bin/env bash
#SBATCH --job-name=echotrace-phase3b
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:A100:1
#SBATCH --mem=32G
#SBATCH --time=05:00:00

set -Eeuo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  printf 'Run this job only through an authorized Slurm allocation\n' >&2
  exit 2
fi

# Supply --account, --partition, --output and --error to sbatch explicitly.
# Supply all ECHOTRACE_* paths through the submission environment. Never source .env.
for name in ECHOTRACE_PYTHON ECHOTRACE_BACKEND ECHOTRACE_CONFIG \
            ECHOTRACE_SELECTION_MANIFEST ECHOTRACE_ACCEPTANCE_MANIFEST \
            ECHOTRACE_EVAL_DIR; do
  if [[ -z "${!name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$name" >&2
    exit 2
  fi
  if [[ "${!name}" != /* ]]; then
    printf '%s must be an absolute path\n' "$name" >&2
    exit 2
  fi
done
if [[ ! -x "$ECHOTRACE_PYTHON" ]]; then
  printf 'ECHOTRACE_PYTHON must be an executable file\n' >&2
  exit 2
fi

"$ECHOTRACE_PYTHON" - "$ECHOTRACE_PYTHON" "$ECHOTRACE_BACKEND" \
  "$ECHOTRACE_CONFIG" "$ECHOTRACE_SELECTION_MANIFEST" \
  "$ECHOTRACE_ACCEPTANCE_MANIFEST" "$ECHOTRACE_EVAL_DIR" <<'PY'
import json
import sys
from pathlib import Path

python, backend, config_path, selection, acceptance, eval_dir = map(Path, sys.argv[1:])
for name, path in (("python", python), ("backend", backend),
                   ("config", config_path), ("selection manifest", selection),
                   ("acceptance manifest", acceptance), ("evaluation directory", eval_dir)):
    if not path.is_absolute():
        raise SystemExit(f"{name} must be an absolute path: {path}")
if not python.is_file() or not backend.is_dir() or not config_path.is_file():
    raise SystemExit("Python, backend and training config must exist")
if not selection.is_file() or not acceptance.is_file() or selection.samefile(acceptance):
    raise SystemExit("Selection and acceptance must be distinct existing manifests")
if eval_dir.exists() or eval_dir.is_symlink() or not eval_dir.parent.is_dir():
    raise SystemExit("Evaluation directory must be fresh and its parent must exist")
if not (backend / "echotrace" / "checkpoint_eval.py").is_file():
    raise SystemExit("Checkpoint evaluator is unavailable; no GPU training started")
if not (backend / "echotrace" / "acceptance.py").is_file():
    raise SystemExit("Acceptance reporter is unavailable; no GPU training started")
config = json.loads(config_path.read_text(encoding="utf-8"))
for key in ("dataset_root", "train_manifest", "validation_manifest", "output_dir"):
    path = Path(config[key])
    if not path.is_absolute():
        raise SystemExit(f"Training config {key} must be an absolute path")
    if key == "output_dir":
        if path.resolve() == eval_dir.resolve():
            raise SystemExit("Training and evaluation output directories must be different")
        if path.exists() or path.is_symlink() or not path.parent.is_dir():
            raise SystemExit("Training output must be fresh and its parent must exist")
    elif not (path.is_dir() if key == "dataset_root" else path.is_file()):
        raise SystemExit(f"Training config {key} does not exist")
if config["device"] != "cuda" or not 1 <= config["max_wall_seconds"] <= 10_800:
    raise SystemExit("Training requires CUDA and a wall limit of at most 10800 seconds")
if Path(config["validation_manifest"]).samefile(acceptance):
    raise SystemExit("Locked acceptance manifest cannot be training validation")
if Path(config["train_manifest"]).samefile(acceptance):
    raise SystemExit("Locked acceptance manifest cannot be the training manifest")
if Path(config["validation_manifest"]).resolve() != selection.resolve():
    raise SystemExit("Training validation must match the frozen selection manifest")

# Verify the actual staged bytes and all split links before spending GPU time.
sys.path.insert(0, str(backend))
from echotrace.evaluation import load_manifest
from echotrace.training import validate_splits

try:
    root = Path(config["dataset_root"])
    records = {
        "train": load_manifest(Path(config["train_manifest"]), root),
        "selection": load_manifest(selection, root),
        "acceptance": load_manifest(acceptance, root),
    }
    for name in ("selection", "acceptance"):
        if len(records[name]) > 10_000:
            raise ValueError(f"{name} manifest exceeds the 10000-file evaluator cap")
        for label in (0, 1):
            if sum(record["label"] == label for record in records[name]) < 100:
                raise ValueError(f"{name} requires at least 100 files per class")
    for left, right in (("train", "selection"), ("train", "acceptance"),
                        ("selection", "acceptance")):
        try:
            validate_splits(records[left], records[right])
        except ValueError as exc:
            raise ValueError(f"{left}/{right} overlap or invalid split: {exc}") from exc
except (OSError, ValueError, RuntimeError) as exc:
    raise SystemExit(f"Preflight data validation failed: {exc}") from exc
print("Preflight passed; training is capped at three hours", flush=True)
PY

cd "$ECHOTRACE_BACKEND"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
dataset_root=$("$ECHOTRACE_PYTHON" - "$ECHOTRACE_CONFIG" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["dataset_root"])
PY
)

"$ECHOTRACE_PYTHON" -m echotrace.training "$ECHOTRACE_CONFIG"

checkpoint=$("$ECHOTRACE_PYTHON" - "$ECHOTRACE_CONFIG" <<'PY'
import json
import sys
from pathlib import Path

output = Path(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["output_dir"])
metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
checkpoint = output / "best.pt"
if metrics.get("checkpoint") != "best.pt" or not checkpoint.is_file() or checkpoint.stat().st_size == 0:
    raise SystemExit("Training produced no usable selected checkpoint")
print(checkpoint)
PY
)

mkdir "$ECHOTRACE_EVAL_DIR"
candidate_sha=$("$ECHOTRACE_PYTHON" - "$checkpoint" <<'PY'
import hashlib
import sys
from pathlib import Path

digest = hashlib.sha256()
with Path(sys.argv[1]).open("rb") as source:
    for block in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(block)
print(digest.hexdigest())
PY
)
printf '%s  %s\n' "$candidate_sha" "$checkpoint" > "$ECHOTRACE_EVAL_DIR/candidate.sha256"

# Each scoring call has a 20-minute internal cap. All four calls remain in this allocation.
"$ECHOTRACE_PYTHON" -m echotrace.checkpoint_eval \
  "$ECHOTRACE_SELECTION_MANIFEST" --dataset-root "$dataset_root" \
  --output "$ECHOTRACE_EVAL_DIR/selection-baseline" --device cuda \
  --role selection --max-wall-seconds 1200
"$ECHOTRACE_PYTHON" -m echotrace.checkpoint_eval \
  "$ECHOTRACE_SELECTION_MANIFEST" --dataset-root "$dataset_root" \
  --output "$ECHOTRACE_EVAL_DIR/selection-candidate" --device cuda \
  --checkpoint "$checkpoint" --checkpoint-sha256 "$candidate_sha" \
  --role selection --max-wall-seconds 1200
"$ECHOTRACE_PYTHON" -m echotrace.checkpoint_eval \
  "$ECHOTRACE_ACCEPTANCE_MANIFEST" --dataset-root "$dataset_root" \
  --output "$ECHOTRACE_EVAL_DIR/acceptance-baseline" --device cuda \
  --role acceptance --max-wall-seconds 1200
"$ECHOTRACE_PYTHON" -m echotrace.checkpoint_eval \
  "$ECHOTRACE_ACCEPTANCE_MANIFEST" --dataset-root "$dataset_root" \
  --output "$ECHOTRACE_EVAL_DIR/acceptance-candidate" --device cuda \
  --checkpoint "$checkpoint" --checkpoint-sha256 "$candidate_sha" \
  --role acceptance --max-wall-seconds 1200

"$ECHOTRACE_PYTHON" -m echotrace.acceptance \
  --baseline-selection "$ECHOTRACE_EVAL_DIR/selection-baseline" \
  --candidate-selection "$ECHOTRACE_EVAL_DIR/selection-candidate" \
  --baseline-acceptance "$ECHOTRACE_EVAL_DIR/acceptance-baseline" \
  --candidate-acceptance "$ECHOTRACE_EVAL_DIR/acceptance-candidate" \
  --output "$ECHOTRACE_EVAL_DIR/acceptance-report.json"

printf 'Training, scoring, and acceptance report completed. Review before any promotion.\n'
