#!/usr/bin/env bash
#SBATCH --job-name=echotrace-audit3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -Eeuo pipefail
: "${ECHOTRACE_ROOT:?}"
: "${ECHOTRACE_BACKEND:?}"
python="$ECHOTRACE_ROOT/envs/detector/bin/python"
data="$ECHOTRACE_ROOT/data/asvspoof5-eval-aa"
cd "$ECHOTRACE_BACKEND"
"$python" -m echotrace.independence_audit "$data/acceptance3.csv" \
  --dataset-root "$data/audio" \
  --prior-run "$ECHOTRACE_ROOT/runs/aasist-aa-01/evaluation/selection-candidate/run.json" \
  --prior-run "$ECHOTRACE_ROOT/runs/aasist-aa-01/evaluation/acceptance-candidate/run.json" \
  --prior-run "$ECHOTRACE_ROOT/runs/native-frozen-01/evaluation-v2/acceptance2-native/run.json" \
  --output "$data/independence-audit.json"
