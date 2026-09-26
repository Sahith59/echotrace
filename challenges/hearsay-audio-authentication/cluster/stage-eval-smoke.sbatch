#!/usr/bin/env bash
#SBATCH --job-name=echotrace-eval-smoke
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
set -Eeuo pipefail
: "${ECHOTRACE_ROOT:?}"
export PATH="$ECHOTRACE_ROOT/envs/runtime/bin:/usr/bin:/bin"
python="$ECHOTRACE_ROOT/envs/detector/bin/python"
backend="$ECHOTRACE_ROOT/source/9903fac"
sample=$(find "$ECHOTRACE_ROOT/data/asvspoof5-aa/audio" -type f -name '*.flac' -print -quit)
[[ -n "$sample" ]]
command -v ffprobe
command -v ffmpeg
PYTHONPATH="$backend" "$python" - "$sample" <<'PY'
import sys
from pathlib import Path
from echotrace.audio import decode_audio, measure_audio
samples, info = decode_audio(Path(sys.argv[1]))
_, _, quiet = measure_audio(samples)
assert len(samples) > 0 and info["analysis_sample_rate"] == 16000 and not quiet
print({"decoder_smoke":"passed","codec":info["codec"],"duration_s":info["duration_s"]})
PY
