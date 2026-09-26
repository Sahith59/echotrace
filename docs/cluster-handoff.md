# TReNDs Phase 3B cluster handoff

This is a local submission package, not a record of a cluster run. The job template is [train-and-evaluate.sbatch](../challenges/hearsay-audio-authentication/cluster/train-and-evaluate.sbatch). It requests one node, one task, four CPUs, one A100 GPU, 32 GB host memory, and five hours. The user supplied SSH alias `trends`, campus username `sthummala2`, and Slurm account `trends517s113`. The former fall account `fall24csc4760` must not be used. A read-only SSH attempt from this workspace timed out before authentication, so network access and account status remain unverified; campus VPN may be required. The operator must still verify the matching GPU partition and type, actual GPU memory, personal storage path, site policy, and available allocation before submitting. The supplied Summer 2026 guide is documentation, not live authorization or inventory. No submission, download, or GPU run has been performed by this package.

Before scheduling GPU time, stage the environment, pinned pretrained weights, audio, and frozen manifests under the user's permitted data location. Audit the train, selection, and locked acceptance splits for linked speakers/sources, duplicates and class balance; exclude the 24 demonstration files. Keep each scoring manifest at 10,000 records or fewer, the evaluator's current cap, and at least 100 recordings of each class in both selection and acceptance. Smaller local smoke experiments use a separate command, not this full five-hour job. Complete a permitted smoke test and throughput/memory estimate. The [training runner](../challenges/hearsay-audio-authentication/docs/training-runner.md) uses a fresh output directory and expects absolute paths in its JSON config. Set `device` to `cuda`, `max_wall_seconds` to at most 10800, and `validation_manifest` to the same frozen selection manifest submitted below. The config's `output_dir` and the evaluation directory must be different, fresh paths with existing parent directories. Before training, the job uses the shared loader to verify and hash the actual staged files in all three manifests; it checks both classes, pinned demonstration exclusions, and pairwise content, file ID, group, speaker, and source separation. This preflight takes time within the allocation, so stage and audit the files beforehand. Locked acceptance is used only by the evaluator and acceptance report. Verify the evaluator and reporter CLIs before submission:

```sh
"$ECHOTRACE_PYTHON" -m echotrace.checkpoint_eval --help
"$ECHOTRACE_PYTHON" -m echotrace.acceptance --help
```

Set these paths in the submission shell. They must be absolute, and the Python executable must belong to the staged backend environment. Do not source or copy `.env` into the job or results.

```sh
export ECHOTRACE_PYTHON=/absolute/path/to/environment/bin/python
export ECHOTRACE_BACKEND=/absolute/path/to/hearsay-audio-authentication/backend
export ECHOTRACE_CONFIG=/absolute/path/to/frozen-training-config.json
export ECHOTRACE_SELECTION_MANIFEST=/absolute/path/to/frozen-selection.csv
export ECHOTRACE_ACCEPTANCE_MANIFEST=/absolute/path/to/frozen-acceptance.csv
export ECHOTRACE_EVAL_DIR=/absolute/path/to/new-evaluation-directory
```

Create a unique log directory **before** `sbatch`; the template does not create one for Slurm. Confirm the account is still active and replace the partition placeholder with a verified authorized GPU partition. Run this command only after the data audit, environment test, and allocation check. The explicit `--gres` can be changed to another permitted GPU type with at least 16 GB after measured batch and memory checks.

```sh
log_dir=/absolute/path/to/new-run-logs
mkdir -m 700 "$log_dir"
sbatch \
  --account=trends517s113 \
  --partition=ACTUAL_AUTHORIZED_GPU_PARTITION \
  --gres=gpu:A100:1 \
  --output="$log_dir/slurm-%j.out" \
  --error="$log_dir/slurm-%j.err" \
  --export=ALL \
  /absolute/path/to/hearsay-audio-authentication/cluster/train-and-evaluate.sbatch
```

Save the returned job ID. Use `squeue -j JOB_ID` and `sacct -j JOB_ID` to inspect only this run. The job refuses direct shell invocation without a Slurm job ID and fails before training if required paths, verified audio, split separation, class counts, fresh output directories, CUDA configuration, or evaluator/reporter files are missing. The runner caps training at three hours; the job then scores baseline and selected checkpoint on selection and locked acceptance manifests, each with a 1200-second cap, and writes `acceptance-report.json`. Three hours plus four scoring caps totals 4 hours 20 minutes, leaving 40 minutes for setup, hashing, reporting and shutdown within the five-hour Slurm limit. These are ceilings; slow preparation or evaluation may exhaust the allocation. Keep data acquisition outside it.

The training output must contain `metrics.json` naming `best.pt` and a nonempty checkpoint before scoring starts. The job records the checkpoint hash in `candidate.sha256`, passes it to candidate evaluation, and stops on any failed step. The evaluator should create fresh output directories `selection-baseline`, `selection-candidate`, `acceptance-baseline`, and `acceptance-candidate` under `ECHOTRACE_EVAL_DIR`; the acceptance reporter writes `acceptance-report.json`. Review the report, raw scores, failures, provenance, wall time, and slice counts before any manual promotion. A failed gate leaves the candidate experimental. Do not treat a selection result as locked acceptance evidence or claim sponsor performance from public data.

Before submission, confirm that `checkpoint_eval.py` implements `MANIFEST --dataset-root ROOT --output FRESH --device cuda [--checkpoint PATH --checkpoint-sha256 SHA] --role selection|acceptance --max-wall-seconds N` and that `acceptance.py` accepts the four result directories and `--output FILE` as invoked in the template. Run `bash -n` on the template and the local guard tests. The guide's `#SGATCH` example is a typo; this template uses `#SBATCH`.
