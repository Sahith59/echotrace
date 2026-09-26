# ECHOTRACE

A local audio-forensics workbench for **NSA HEARSAY, Challenge 1**. Review uploaded recordings, inspect actual learned-detector and signal measurements, compare compressed/noisy derivatives, and export reproducible batch predictions.

## Current status

The first working prototype is implemented. It runs the official AASIST-L checkpoint on CPU and provides a React interface, durable local jobs, playback, interval scores, quality/spectral/temporal observations, JSON reports, analyst CSV export, and a shared command-line pipeline.

**This is not a validated authentication system.** Scores are uncalibrated. In a local smoke test the baseline gave a known macOS-generated synthetic speech clip a low synthesis score. That observed failure is recorded in [model feasibility](../../docs/model-feasibility.md), not hidden as a successful accuracy demonstration. Sponsor dataset evaluation, a validated detector promotion, calibration, and official CSV verification remain outstanding. Completed public-data experiments do not substitute for sponsor testing.

The [problem validation](../../docs/problem-validation.md) links primary FBI/FTC evidence; the [product review](../../docs/product-validation.md) explains why recorded-audio triage fits this challenge. Evidence of voice-cloning harm does not prove our detector works.

Current development is **release integration and independent model evaluation**. The [training runner](docs/training-runner.md), [three-way data preparation](../../docs/data-preparation.md), [whole-file checkpoint evaluation and acceptance](../../docs/checkpoint-evaluation.md), and [one-GPU cluster package](../../docs/cluster-handoff.md) are implemented and locally tested. A real A100 run completed 6,000 training steps and independent evaluation. Its recall improved from 22.5% to 44.5% at about 4% false positives, but failed the predeclared 80% recall target and was not promoted. The final native adaptation completed 1,250 steps and reached 87.4% recall but 24.4% false positives on a separate balanced 2,000-file holdout. It also failed promotion. The app retains AASIST-L and displays all three measured experiments. Total GPU allocation was 1h44m53; no job remains active. The [Groq interpretation integration](../../docs/ai-interpretation.md) is available after configuring a backend API key; it summarizes recorded evidence without altering the detector score.

## Run locally

Prerequisites: Python 3.11 or 3.12, [uv](https://docs.astral.sh/uv/), FFmpeg/ffprobe on PATH, and Node/npm. Commands below start in this challenge directory. The app binds to loopback; do not expose it publicly without authentication and deployment hardening.

Terminal 1:

```sh
cd backend
uv sync --frozen --python 3.11
uv run echotrace setup-model
uv run uvicorn echotrace.api:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd frontend
npm ci
npm run dev -- --port 5173
```

Open **http://127.0.0.1:5173**. Upload a WAV, MP3 or M4A, or select multiple recordings. Current limits: 50 MiB and 120 seconds per file, one inference job at a time. Uploaded audio stays on the local server. Dependencies and model weights require network access at setup; typography has local fallback fonts.

`setup-model` downloads the pinned official 426 KB AASIST-L checkpoint and verifies its SHA-256. No model download occurs during inference. Missing weights yield measured signal observations with no synthetic score. Vendor code/license/provenance are in `backend/echotrace/vendor/`; upstream attribution remains intact.

Jobs and source audio persist in `artifacts/workspace/`. Model weights are cached in `backend/artifacts/`. These paths are ignored by Git. `ECHOTRACE_WORKSPACE` can set a different local job directory. Interrupted jobs are marked failed on restart and can be retried. Core local analysis needs no cloud credentials. Optional Groq interpretation requires your own Groq key and may incur provider charges. Hosted claim search is unavailable until its source-provenance contract is validated.

## What the UI does

- Intake and history: actual uploads, queued/running/completed/failed states, retry, original filenames.
- Investigation: 0–100 uncalibrated model score, player and seekable waveform, scored windows, measured evidence, limitations, provenance and downloadable JSON.
- Comparison: MP3 at 64 kbps or seeded noise at 20 dB SNR, with new real inference, original preservation and score deltas. Stability is not correctness.
- Batch: select completed scored files and download an **analyst** CSV. It is explicitly not the sponsor's confirmed schema.
- Speaker reference: consent-gated, local Microsoft WavLM embeddings and uncalibrated cosine similarity. Temporary reference audio is deleted after processing; comparison metadata can be removed.
- Transcript: local faster-whisper speech recognition, timestamp seeking, immutable corrections and explicit errors.
- Claims: source-backed analyst reviews, with hosted Groq search explicitly unavailable pending validated source provenance. Previous claims are marked stale when the transcript changes.
- Case report: downloadable JSON and printable HTML keep the four evidence types separate, with provenance and no combined authenticity probability.
- Detector validation: actual independent before/after metrics, including failed promotion gates.

Spectral and temporal measurements do not determine the learned model's score. Window aggregation is an unvalidated mean of full-coverage windows, including an overlapping final window when needed. The model does not identify speaker, intent, specific generator or manipulation subtype. Quiet audio yields no assessment. Speech presence is not independently verified, so non-speech scores must not be interpreted as valid speech-authenticity evidence.

## CLI and sponsor preparation

Run these in `backend/`:

```sh
uv run echotrace score /absolute/path/recording.wav --output result.json
uv run echotrace batch manifest.csv --root /absolute/path/audio --output scores.csv
uv run echotrace audit train.csv --root /absolute/path/audio --split --output audit.json
uv run echotrace evaluate validation.csv scores.csv --root /absolute/path/audio --output metrics.json
```

Manifest CSV uses `file_id,path` with relative audio paths. Labeled manifests also use `label` (0 genuine, 1 synthetic) and optionally `group_id`, `speaker_id`, and `source_id` covering related recording families. Exact-file hashes and transitive links within any of these metadata columns are kept together by the split helper. Each column has its own namespace. Seeded membership is independent of manifest row ordering. A group field must be prepared from relevant metadata; the tool cannot discover every hidden relationship automatically. Near-duplicate acoustic grouping and independent calibration are not implemented yet.

Batch runs write every ID, including explicit failures, and a `.run.json` sidecar. Failures cause a nonzero exit status; they must be resolved before submission. The same size/duration limits currently apply to CLI and UI, with no silent truncation. Confirm sponsor test limits before final inference.

Schema conversion and coverage validation:

```sh
uv run echotrace export scores.csv --expected expected-ids.csv \
  --schema ../configs/submission.example.json --output example-export.csv \
  --allow-example-schema
```

The example is deliberately marked unofficial. For actual submission, adapt a reviewed config to the sponsor's headers/scale and set `official_schema_confirmed` only after checking the official template. Omit `--allow-example-schema` for the final export. The current adapter supports an ID column and a synthesis-score column (0–1 or 0–100, synthetic-high); extend it only if the real sponsor format requires additional fields or another convention. It checks expected IDs/order, duplicates, coverage and finite scores. It does not upload or submit anything.

## Verify

```sh
cd backend
uv run echotrace setup-model
uv run pytest -q
```

```sh
cd frontend
npm run build
```

Tests cover real decoding/model execution, silence and limits, score polarity math, API/CLI parity, job restart/failure behavior, leakage guards, metrics and CSV schema/coverage. The speech parity test uses macOS `say` and is skipped on other platforms. Generated tones and local TTS fixtures validate software wiring, not benchmark accuracy.

## Remaining competition-critical work

Obtain the sponsor dataset, metric, schema, deadline and event rules. Evaluate this baseline on a grouped validation set, compare stronger candidates, fit calibration if supported, document false positives/negatives, and generate the official held-out CSV. See [plan.md](../../plan.md) for phase gates and [memory.md](../../memory.md) for session state.

## Larger public benchmark and comparison candidate

ASVspoof 5 Track 1 is the selected large public train/development source. The official protocol archive was downloaded and checked against the published MD5. Prepared metadata includes 182,357 train, 140,950 development Track 1, and 680,774 evaluation Track 1 records. Only selected audio archives have been downloaded and verified on the cluster; the full corpus is not staged. The dated run ledger records exact archive checksums, decoded subsets and completed experiments. Preserve these official partitions; do not run a random split across their union. Read `docs/large-dataset-review.md` at repository root for source and licensing details.

After obtaining the official protocols and audio in the documented folder layout, convert each protocol independently from the backend directory:

```sh
uv run python -m echotrace.asvspoof5 ASVspoof5.train.tsv --partition train --output train.csv
uv run python -m echotrace.asvspoof5 ASVspoof5.dev.track_1.tsv --partition dev --output dev.csv
uv run python -m echotrace.asvspoof5 ASVspoof5.eval.track_1.tsv --partition eval --output eval.csv
```

Outputs must not already exist. Conversion validates protocol labels/IDs, preserves speaker/source/attack/codec metadata, and records the protocol hash. It does not imply audio availability, train a model, or compute performance. The audio root must contain `flac_T/`, `flac_D/`, or `flac_E_eval/`. Only training and development audio is needed initially. Exact official archive sizes, URLs and checksums are in `configs/asvspoof5-downloads.json`. The initial eight audio archives total 57,561,937,920 bytes; budget additional extraction space. Cluster allocation and personal data storage have been verified; see the dated run ledger.

An isolated full-AASIST candidate can be compared without changing the web detector:

```sh
uv run python -m echotrace.candidate --setup
uv run python -m echotrace.candidate artifacts/public-pilot/manifest.csv --root artifacts/public-pilot --output artifacts/new-candidate-run
```

This comparison runner is deliberately limited to 256 files and CPU while checking feasibility; it is not a full-corpus cluster runner. Setup explicitly downloads checksum-pinned official weights. Inference never downloads implicitly. Scores remain uncalibrated. Keep a fresh output directory for each run. No promotion decision should be based on the small existing pilot.

### What should I upload in the website?

- **To check the detector:** choose a dataset recording whose genuine/synthetic label is known, then compare the result with that label. The label is for your evaluation; the app does not use filenames or labels to predict.
- **To check the workflow:** upload your own short recording, use playback/seek and export. A custom recording without known provenance cannot establish detector correctness.
- **To train:** do neither through the web upload. Training is a separate offline process using designated labeled training data. Uploading audio does not teach or change the model.

Current app limit: 50 MiB and 120 seconds. A low synthesis score does not prove identity or truth. Public pilot audio is under `backend/artifacts/public-pilot/original/en/` (genuine) and `backend/artifacts/public-pilot/fake/en/` (synthetic); these directories are ignored by Git. Do not publish clips without their required terms/attribution.

## Try the fixed 24-recording demo

On the intake page, expand **Try a known recording**, select a labeled MLAAD-tiny example, optionally preview it, then choose **Analyze this sample**. The app sends its audio through the normal upload and AASIST-L pipeline. It does not use the label for scoring or train the model. The catalog checks local audio against pinned provenance; unavailable or changed files are not served.

The local sample consists of 12 genuine and 12 synthetic recordings. It is a small selected diagnostic set, not an independent accuracy benchmark. Custom uploads remain supported. These 24 clips are for interface diagnostics; training and independent evaluation use a separate ASVspoof 5 subset.

## Groq review and experimental training

Set `GROQ_API_KEY` in the repository root `.env`; `ECHOTRACE_LLM_MODEL` defaults to `openai/gpt-oss-120b`. The backend reads configuration when requested. Use **Check configuration** then **Generate interpretation** on a completed recording. Only measured findings go to Groq; no audio/filenames/transcripts are sent. Reports are cached and included in JSON export. See [Groq integration](../../docs/ai-interpretation.md).

The [experimental training runner](docs/training-runner.md) accepts frozen train/selection manifests and a bounded configuration. It does not start automatically or replace the web detector. The 24 demo clips are excluded; independent acceptance evaluation is required before promotion.

## Prepare optional local models

From `backend/`, run the explicit setup commands in [speaker comparison](../../docs/speaker-comparison.md) and [transcription](../../docs/claim-review.md). Both runtime routes fail clearly if model files are missing; they never substitute a fake result. Model downloads and caches are excluded from Git.

```sh
uv run python -m echotrace.speaker
uv run python -m echotrace.transcription --model base --cache-dir ../artifacts/workspace/models/faster-whisper
```

Create root `.env` from `.env.example` if it does not exist, then edit `GROQ_API_KEY` locally. Never put it in a `VITE_` variable, a screenshot, or Git. Without a key, local detection, speaker comparison, transcription, analyst review and exports remain usable; live Groq is unavailable.

## Verification

```sh
# In backend/
uv run pytest -q
# In frontend/
npm test
npm run build
```

See [release verification](../../docs/release-verification.md), [the phase checklist](../../plan.md), and [the demonstration guide](../../docs/demo-guide.md). This iteration ends with a private source repository. Deployment, multi-user authentication and official sponsor submission require the subsequent deployment/submission configuration.
