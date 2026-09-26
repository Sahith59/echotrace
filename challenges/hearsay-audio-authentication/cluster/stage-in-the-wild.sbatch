#!/usr/bin/env bash
#SBATCH --job-name=echotrace-itw-stage
#SBATCH --partition=qTRD
#SBATCH --account=trends517s113
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=03:00:00
#SBATCH --no-requeue
set -Eeuo pipefail

: "${ECHOTRACE_ROOT:?Set ECHOTRACE_ROOT to the owned cluster project root}"
: "${ECHOTRACE_ITW_TOOL_DIR:?Set ECHOTRACE_ITW_TOOL_DIR to the pinned tool snapshot}"

export PATH="$ECHOTRACE_ROOT/envs/runtime/bin:/usr/bin:/bin"
python="$ECHOTRACE_ROOT/envs/runtime/bin/python"
stage="$ECHOTRACE_ITW_TOOL_DIR/stage_in_the_wild.py"
test -x "$python"
test -f "$stage"
test -x "$ECHOTRACE_ROOT/envs/runtime/bin/ffmpeg"
test -x "$ECHOTRACE_ROOT/envs/runtime/bin/ffprobe"
command -v curl >/dev/null

downloads="$ECHOTRACE_ROOT/downloads/in-the-wild-eee168f"
archive="$downloads/release_in_the_wild.zip"
target="$ECHOTRACE_ROOT/data/in-the-wild-external-2k"
url='https://huggingface.co/datasets/mueller91/In-The-Wild/resolve/eee168f92c367f8c82ff2cf42b6f61e362fd6211/release_in_the_wild.zip'
expected_bytes=8161489023
expected_sha='46665f30a6758b45642c659c7e0e80da2ba3d121b064716824a56a010ddf9e1a'

mkdir -p "$downloads"
test ! -e "$target"
test ! -L "$target"

if [[ ! -f "$archive" ]]; then
  chunk=2040372256
  pids=()
  for index in 0 1 2 3; do
    start=$((index * chunk))
    end=$((start + chunk - 1))
    if (( end >= expected_bytes )); then end=$((expected_bytes - 1)); fi
    part="$downloads/release_in_the_wild.zip.part-$index"
    expected_part=$((end - start + 1))
    if [[ -f "$part" && $(stat -c %s "$part") -ne $expected_part ]]; then
      echo "Refusing unexpected cached range size: $part" >&2
      exit 2
    fi
    if [[ ! -f "$part" ]]; then
      curl --fail --location --retry 3 --retry-all-errors --connect-timeout 30 \
        --range "$start-$end" --max-filesize "$expected_part" --output "$part" "$url" &
      pids+=("$!")
    fi
  done
  for pid in "${pids[@]}"; do wait "$pid"; done

  "$python" - "$downloads" "$archive.part" "$expected_bytes" "$expected_sha" <<'PY'
import hashlib
import sys
from pathlib import Path

folder, output = map(Path, sys.argv[1:3])
expected_size, expected_hash = int(sys.argv[3]), sys.argv[4]
digest = hashlib.sha256()
size = 0
with output.open("xb") as target:
    for index in range(4):
        part = folder / f"release_in_the_wild.zip.part-{index}"
        with part.open("rb") as source:
            while block := source.read(1024 * 1024):
                target.write(block)
                digest.update(block)
                size += len(block)
if size != expected_size or digest.hexdigest() != expected_hash:
    raise SystemExit(f"assembled archive mismatch: bytes={size} sha256={digest.hexdigest()}")
PY
  mv -- "$archive.part" "$archive"
fi

"$python" "$stage" --archive "$archive" --output-dir "$target" --sample-per-class 1000
