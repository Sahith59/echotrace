# Whole-file checkpoint evaluation and acceptance

These commands implement Phase 3A's evaluation machinery. They have passed local software and actual-model CPU smoke checks. They are not evidence of improved speech detection, sponsor performance, or completed cluster training. The web app still uses the original AASIST-L weights.

## Inputs and split roles

Use [data preparation](data-preparation.md) to freeze independent `train.csv`, `selection.csv` and `acceptance.csv` before fitting. The inspected 24 demo recordings stay outside these sets. Training labels use `0=genuine, 1=synthetic`; AASIST inference uses class0 as the synthetic score. Selection data choose the training checkpoint and operating threshold. Acceptance is scored only after those choices are fixed; do not iterate on its labels. A further experiment informed by acceptance errors needs fresh independent acceptance evidence.

The [training runner](../challenges/hearsay-audio-authentication/docs/training-runner.md) saves `best.pt` with the pinned pretrained hash, architecture hash, upstream revision and hashed train/selection record provenance. It selects by first-crop validation loss. The evaluator instead uses the same shared full-file windows as the web app: mono16kHz decode, 64,600-sample windows, repeat padding for short audio, end-anchored overlapping tail, mean class0 softmax, and the shared quiet-audio check. Thus training selection loss and acceptance score measure different aggregation policies, explicitly.

## Scoring commands

Run from `challenges/hearsay-audio-authentication/backend` using the prepared environment and pinned baseline weights. Every output directory must be new. Example baseline selection run:

```sh
uv run python -m echotrace.checkpoint_eval /absolute/path/selection.csv \
  --dataset-root /absolute/path/audio \
  --output /absolute/path/selection-baseline \
  --device cpu --role selection --max-wall-seconds 1200
```

For the trained candidate, compute SHA-256 of the actual `best.pt` and supply that digest (not the pretrained model digest):

```sh
uv run python -m echotrace.checkpoint_eval /absolute/path/selection.csv \
  --dataset-root /absolute/path/audio \
  --output /absolute/path/selection-candidate \
  --device cpu --role selection --max-wall-seconds 1200 \
  --checkpoint /absolute/path/training-output/best.pt \
  --checkpoint-sha256 ACTUAL_64_CHARACTER_LOWERCASE_SHA256
```

Repeat with `acceptance.csv`, `--role acceptance`, and new `acceptance-baseline` / `acceptance-candidate` directories. Use `--device cuda` only within permitted GPU resources. `--max-seconds` is an alias of `--max-wall-seconds`; the scorer caps files at10,000 and its timer at5,400 seconds. Timers start after manifest/content verification and are cooperative, not a hard process kill. The Slurm package uses1,200 seconds per run within its five-hour outer limit.

The candidate loader verifies the checkpoint digest before `torch.load(weights_only=True)`, checks pinned model provenance, and loads the state strictly. Both training provenance splits require both classes and no cross-split links. Candidate selection may reuse the training validation set; it cannot overlap training. Candidate acceptance cannot overlap either fitted split by content hash, file ID, group, speaker or source. Hash grouping cannot discover unknown near-duplicates or relationships absent from metadata.

Each run writes `scores.csv` and `run.json`. Every requested ID appears, including failed or quiet inputs with a blank score; the run records actual failures, timing, record metadata and score-file digest. A successfully written ledger can still be incomplete. Inspect `complete` and failure rows; acceptance reporting refuses incomplete coverage. No score is fabricated for an error.

## Compare the four frozen runs

```sh
uv run python -m echotrace.acceptance \
  --baseline-selection /absolute/path/selection-baseline \
  --candidate-selection /absolute/path/selection-candidate \
  --baseline-acceptance /absolute/path/acceptance-baseline \
  --candidate-acceptance /absolute/path/acceptance-candidate \
  --output /absolute/path/new-acceptance-report.json
```

The reporter checks complete matching file coverage, CSV hashes, labels, model identity and preprocessing, and split separation. It independently chooses baseline and candidate thresholds on selection scores, maximizing recall at at most5% selection false-positive rate; ties prefer fewer false positives then a higher threshold. Acceptance labels do not affect those thresholds. Scores remain uncalibrated; an operating threshold is not probability calibration.

Provisional internal gates require at least100 recordings per class in both selection and acceptance, candidate acceptance recall≥80%, false-positive rate≤5%, recall gain≥10 percentage points over baseline, and no AUROC regression. Reports include confusion matrices, AUROC, average precision and Wilson95% intervals for recall/FPR. These are point-estimate gates, not confidence-bound guarantees or sponsor criteria. Sparse/failed data cannot qualify. `eligible_for_review` is a review signal; `promoted` is always false.

Before any web-model replacement, review per-attack/codec errors and counts, serving latency/memory, train/serve score parity and distribution differences. The current reporter retains slice metadata but does not calculate slice reports or EER. Public-corpus acceptance cannot establish sponsor accuracy. Keep the baseline and an explicit rollback path. Official test data, metric and CSV schema remain separate requirements.
