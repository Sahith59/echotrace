# ECHOTRACE implementation plan

Status: usable prototype, detector reliability inadequate. Next priority is detector audit and bounded five-hour adaptation planning; sponsor evaluation/submission remain open. Updated: 2026-09-25.

**Latest priority:** [Detector improvement plan](docs/detector-improvement-plan.md) supersedes historical training deferral below. Keep24 clips for demo; prepare separate fitting and locked validation data. No training job has started.

## Objective and scope

Build ECHOTRACE for **NSA Challenge 1: HEARSAY — The Audio Authentication Challenge**. Provide autonomous multi-technique audio analysis, a synthesis-likelihood score on a 0–100 scale, and a reproducible CSV of predictions for the sponsor's held-out test set. Present the results in a polished audio-forensics workbench.

Pitch: “Inspect a suspicious recording, see which passages warrant review, and understand how stable the assessment is.”

The product supports investigation; a model score does not prove authenticity, establish identity, or authenticate the recording's origin. No prize, accuracy, latency, or generalization claims are guaranteed.

### Source and requirement boundaries

- Authoritative challenge text available locally: [CHALLENGE.md](challenges/hearsay-audio-authentication/CHALLENGE.md).
- The user supplied the complete sponsor-challenges excerpt on 2026-09-25. It matches the local NSA #1 brief. The full Notion event packet could not be retrieved; event-wide rules remain unverified.
- NSA #2 packet analysis and NSA #3 Codebreaker are out of scope.
- Other sponsors' judging criteria, required videos, technologies, public repositories, and submission tags do not become NSA requirements.
- The brief initially mentions manipulation type in the mission, but later explicitly calls identification optional. Plan it as a stretch feature; clarify with the sponsor.

| Confirmed requirement | Planned implementation | Acceptance evidence |
| --- | --- | --- |
| Audio-file input including WAV, MP3, M4A | FFmpeg decoding with validation and declared supported formats | Successful real fixtures in all three containers |
| Automatic multiple forensic techniques | Learned anti-spoofing inference plus spectral and temporal/quality analysis | One job runs each technique and records its actual output |
| Synthesis likelihood, 0–100% | Validated score mapping; calibration where supported by data | Score bounds, polarity checks, calibration status and validation report |
| Provided labeled training and held-out test sets | Manifest-based training/validation and frozen test inference | Split manifest and reproducible run record |
| CSV predictions on test set | Schema adapter, validation, and batch CLI | Every expected ID exactly once, official columns and scale |
| Optional manipulation type | Classifier only for supported labels with measured performance | Per-class validation, or explicit undetermined result |

## Decisions to resolve at build kickoff

Do not invent answers. Missing dataset/schema blocks final evaluation/submission, but need not block decoding, interface work, or checkpoint smoke tests after implementation is authorized.

| Unknown | How to resolve | Planning assumption / consequence |
| --- | --- | --- |
| Dataset location, license, size, classes and metadata | Sponsor release / mentor | No sponsor data or results currently available |
| Scoring metric and judging weights | Sponsor instructions | Report diagnostics; optimize only once metric is known |
| CSV schema, score direction, scale, ID ordering | Official template / sample | Internal schema is not the submission contract |
| Test access and permitted evaluation feedback | Sponsor rules | No test-label tuning; freeze model before final inference |
| External datasets / pretrained models / cloud-upload restrictions | Event rules and sponsor | Brief allows cloud and model tools; do not infer unrestricted data redistribution |
| Submission deadline, channel, artifact requirements | Event packet / sponsor | Do not claim that a video or public repo is mandatory |
| Team size, remaining time, GPU and spending budget | User | Plan for one worker and pretrained inference; no paid provisioning without a budget |

## Product and design

### Primary flow

1. Open the workbench; drop an audio file or choose a clearly labeled example.
2. See honest job stages: decoding, quality analysis, detector inference, aggregation, completion. Progress reflects work performed, not simulated percentages.
3. Inspect the likelihood score, calibration label, quality limitations, and model version.
4. Play the recording and seek by waveform or a suspicious interval. Provide an accessible text list of intervals as well.
5. Expand evidence: detector scores, spectrum view, clipping/silence/duration measurements, and measured discontinuities. Distinguish observations from conclusions.
6. Optionally create a compressed/noisy derivative and compare assessments.
7. Export an analysis JSON/report, or enter batch mode to validate and export sponsor predictions.

### Views

- **Intake:** drag/drop plus keyboard file picker, supported formats and limits, sample provenance, clear errors.
- **Investigation:** large waveform and player; score summary; timeline; compact evidence panel; expand technical details on demand.
- **Batch:** per-file status, processed/failed counts, score table, retry and export preflight. Failure rows remain visible.
- **Comparison:** original and transformed clip, labeled transformation parameters, score change, playback and limitations.

Visual direction: restrained charcoal/navy surface, crisp typography, cyan playback accent, amber uncertainty, and a distinct high-score color. Use readable contrast, ample spacing, meaningful motion, and reduced-motion support. Do not imitate official NSA branding or imply endorsement. Avoid decorative radar animations that obscure actual analysis.

Terminology: “synthetic-likelihood estimate,” “uncalibrated model score,” “suspicious interval,” “limited evidence,” and “manipulation type undetermined.” Low synthesis score is not proof of authenticity. Detector agreement is not a confidence interval. Window scores are not exact edit boundaries.

## Architecture and contracts

### Proposed stack

- Frontend: React + TypeScript + Vite; waveform/audio player and an accessible results table.
- Backend: Python + FastAPI; PyTorch model adapters; FFmpeg decoding; NumPy/SciPy audio measurements. Pin compatible versions after checkpoint smoke testing.
- Local SQLite job store and filesystem artifact directory; one inference worker initially. Avoid introducing Redis, distributed queues, accounts, or a separate database service for the prototype.
- A Python batch CLI imports the same analysis package as the API. CSV scoring must not be a separate implementation.
- Local-first demo. Optional remote GPU inference only after budget, data permissions, and deployment needs are resolved. Never expose an unauthenticated upload service publicly.

```text
Upload or dataset manifest
  -> validate / hash original / create job
  -> decode and preserve source metadata
  -> quality + spectral/temporal analysis
  -> model-specific preprocessing -> learned detector(s)
  -> window/file aggregation -> optional validated fusion
  -> calibration / limitations / structured result
  -> API and UI, analysis export, or sponsor CSV adapter
```

Keep original audio; create explicit derived files. Each detector receives its documented sample rate, channel handling, crop/padding policy, and amplitude convention. Avoid destructive denoising or silence trimming by default; these can change forensic cues. Treat file headers and filenames as metadata, not predictive features.

### Proposed repository layout

```text
claude.md                         # durable project instructions
memory.md                         # current state and decision history
plan.md                           # ordered work and acceptance gates
docs/reviews.md                   # independent planning reviews and resolutions
challenges/hearsay-audio-authentication/
  CHALLENGE.md                    # preserve original brief
  SOLUTION.md                     # project entry point
  backend/                       # API + shared Python analysis package
  frontend/                      # React app
  configs/                       # versioned model/preprocessing settings
  scripts/                       # dataset audit, evaluation, batch commands
  tests/                         # meaningful unit and integration checks
  reports/                       # small measured summaries, no private audio
  data/                          # ignored local data
  artifacts/                     # ignored checkpoints, audio, runs
```

### Internal contracts, to finalize before implementation

- Dataset item: `file_id`, `relative_path`, optional `label`, `speaker_id`, `source_id`, `generator_id`, `group_id`, `split`, `sha256`. Resolve paths inside the dataset root.
- Analysis result: `analysis_id`, source hash, input duration/codec/sample rate, pipeline/model versions, configuration hash, status, score or null, score kind/calibration status, per-detector outputs, quality observations, intervals, limitations, timing and errors.
- Internal `synthetic_score` uses 0–1; UI uses 0–100. CSV adapter follows the official scale. Store `score_kind` as calibrated estimate or uncalibrated score. Never call a raw softmax a calibrated probability.
- Interval: start/end seconds, originating model/window size, score kind, score, and label “window-level assessment.” Keep original time coordinates after resampling.
- Manipulation result: supported class or `undetermined`; include source model and validation basis. Do not infer TTS versus voice conversion from a binary model.
- Analysis states: `queued`, `running`, `completed`, `failed`; explicit stage, warnings and timestamps. A completed analysis can have limitations. Worker failures must not leave jobs permanently running.
- API proposal: `POST /api/analyses`, `GET /api/analyses/{id}`, `GET /api/analyses/{id}/audio`, `POST /api/analyses/{id}/stress-tests`, `POST /api/batches`, `GET /api/batches/{id}`, `GET /api/batches/{id}/export`, `GET /api/health`. Polling is sufficient initially.
- Expected invalid/unsupported/no-speech inputs return an explicit status and null score when analysis is not meaningful. Never replace failure with 0%, 50%, or a cached example. Final submission cannot silently omit these IDs; resolve failures or follow a sponsor-approved policy.
- Limits: configure bytes, duration, decoded samples, batch size and worker concurrency; show them in the UI. Decode with timeout using argument arrays, temporary paths and cleanup. Do not accept arbitrary URLs or shell strings.

## Detection and evaluation strategy

1. Audit the supplied training set: class balance, durations, codecs, sample rates, duplicates, correlated recordings and group metadata. Record source provenance.
2. Establish one working pretrained anti-spoofing baseline. AASIST is a candidate, not a promised winner. Check checkpoint license, provenance, score polarity, preprocessing and runtime.
   If checkpoint compatibility or domain performance is poor, compare frozen speech embeddings with a small trained head and a lightweight LFCC/log-spectral feature classifier. These routes require supplied training labels; deterministic heuristics alone do not satisfy the planned learned-detector gate. Benchmark a naive class-prior baseline as an evaluation sanity check.
3. Add spectral/temporal and quality measurements. They supply complementary analysis; they affect the synthesis score only if validated.
4. Create speaker/source/recording-group-aware validation where metadata permits. Keep duplicates, derivatives and crops of one recording in the same split. Apply augmentation after splitting. Document limitations if groups are unavailable.
5. Evaluate a second detector such as a wav2vec 2.0 anti-spoofing checkpoint, or frozen speech embeddings with a small supervised head. Downloaded speech encoders alone are not trained deepfake detectors.
6. Compare a simple validated fusion against the best single model. Fit fusion on out-of-fold predictions or a designated training split. Keep evaluation examples separate from fusion/calibration fitting. Drop branches that add latency without measured value.
7. Calibrate using a disjoint calibration portion or a documented cross-validation design when sample count permits. If data are insufficient, expose an uncalibrated score honestly and record that limitation.
8. Measure the official metric plus appropriate diagnostics: AUC, precision/recall/F1, confusion matrix, false-positive rate, calibration/reliability and runtime. Use score-based metrics without threshold tuning; fit any classification threshold only on development data. Report sample counts and label balance.
9. Assess robustness on controlled derivatives of validation examples. Compression/noise variants stay grouped with their originals; they are correlated observations. Stable scores do not prove correctness. Do not tune on the held-out sponsor test set.
10. Freeze the chosen pipeline, configuration, calibration and export adapter; run final inference and verify coverage. Preserve the run manifest and checksums.

Preserve raw detector outputs alongside mapped scores to support polarity audits and evaluation. If generator metadata and sample counts permit, add a held-out-generator diagnostic; do not assume it replaces the sponsor's evaluation distribution. Near-duplicate acoustic checks complement exact hashes when practical. Begin with simple calibration such as Platt/temperature scaling; avoid flexible calibrators on tiny samples. Do not add per-example uncertainty intervals without a validated statistical procedure.

External baseline references (previously reviewed): [AASIST](https://github.com/clovaai/aasist), [SSL anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing), [generalization study](https://arxiv.org/abs/2203.16263). Published benchmark results are not performance estimates for this challenge. Recheck dependencies and checkpoint availability at build time.

## Ordered phases

Phases are sequential at their gates. Independent frontend work may proceed against a documented fixture while detection work proceeds, but fixture mode must be visibly labeled and must never supply evaluated predictions. Suggested percentages below are effort allocations, not elapsed-time promises.

### Phase 0 — Lock requirements and feasibility (8%)

- [ ] Obtain remaining event rules, deadline, scoring metric, dataset and submission template.
- [ ] Confirm compute/budget/team and record in memory.
- [ ] Audit dataset and checkpoint availability; establish preprocessing and score polarity.
- [x] Finalize internal contracts, supported inputs and operational limits.
- [ ] Create a realistic work schedule from actual remaining time.

Gate: documented assumptions, viable model route and scope. If sponsor data are delayed, explicitly mark evaluation gates blocked and proceed only with independent work.

### Phase 1 — Working baseline and submission path (22%)

- [x] Create isolated environment and pinned dependencies; decode WAV/MP3/M4A fixtures.
- [x] Implement shared model adapter and file-level scoring with explicit failures.
- [x] Add complementary spectral/temporal/quality analysis and deterministic orchestration.
- [ ] Build dataset manifest and reproducible grouped validation split.
- [ ] Run baseline evaluation and record actual metrics and runtime.
- [ ] Implement batch CLI and configurable CSV adapter; validate against official template when available.

Gate: real audio -> actual detector and forensic outputs -> reproducible batch results. A schema-compliant CSV must exist as soon as the template and test inputs are available. No synthetic demo values used as model output.

### Phase 2 — Complete product vertical slice (22%)

- [x] Implement durable jobs, result persistence, status API, playback and upload validation.
- [x] Build intake, investigation and batch views; connect to actual analysis.
- [x] Add waveform seeking, quality observations, errors, keyboard support and reduced motion.
- [x] Produce window-level scores with explicit resolution; verify timestamp alignment.
- [x] Show score kind, limitations and run/model provenance.
- [x] Integrate export preflight and per-file failures.

Gate: an unfamiliar supported file completes the full UI flow; batch export and CLI use the same scoring implementation. UI remains usable during inference. Genuine inference is clearly separated from illustrative fixtures.

### Phase 3 — Improve measured performance (23%)

- [ ] Analyze baseline errors; test a second detector or lightweight adaptation if compute permits.
- [ ] Compare candidate fusion and file/window aggregation methods on development data.
- [ ] Fit calibration without evaluation leakage; select thresholds only if required.
- [ ] Run ablation report: strongest single detector, additional measurements, candidate ensemble.
- [ ] Measure degradation and runtime across representative duration/quality groups.
- [ ] Retain only justified changes; version the selected model configuration.

Gate: selected system has a documented comparison with baseline and known limitations. Improvement is an experimental goal, not a requirement to fabricate or keep an inferior ensemble.

### Phase 4 — Distinctive demonstration (10%)

- [x] Implement compression/noise stress test as a separate derived analysis; record transform parameters and seed.
- [x] Show original/transformed playback, side-by-side scores, and change in percentage points.
- [ ] Prepare licensed/consented genuine and synthetic demo clips with provenance.
- [ ] Optional: experiment with partial synthesis and manipulation classes only with suitable labels and validation.
- [x] Add concise report export if time permits.

Gate: transformations and reruns are real; no robustness or localization claim exceeds validation. If time is tight, cut this phase before cutting evaluation and CSV reliability.

### Phase 5 — Freeze, rehearse and hand off (15%)

- [ ] Freeze configuration, models, calibrator and official CSV adapter.
- [ ] Run full held-out test inference without label-driven tuning.
- [ ] Validate IDs, counts, scale, polarity, columns, ordering, finite values and duplicates.
- [ ] Resolve failed test inputs; record sponsor-approved exceptions, if any.
- [ ] Run focused automated checks and manual end-to-end demo; test an app restart.
- [x] Document exact setup/inference/export commands, hardware, runtime and artifact hashes.
- [ ] Verify actual event submission requirements; prepare only required artifacts plus useful demo support.
- [ ] Rehearse a short demo and prepare a clearly labeled recording or saved real run as a network fallback.
- [ ] Deliver final CSV, validation report, runnable prototype and limitations. External submission only through an authorized destination/action.

Gate: reproducible results and valid submission artifacts; user can run the prototype and explain the evaluation. No deployment or prize success assumed.

## Focused verification

- Known-label fixtures verify class-index/score polarity; zero/one conversion is consistent in API, UI and export.
- Integration fixtures cover the three required containers, short/silent audio, corrupt files, Unicode/spaces in names, timeout and long-input limits.
- Split checks detect duplicate/group overlap; scoring does not consume labels or filename hints.
- Batch CSV check enforces exact expected identifiers and official schema, preserves errors, and rejects NaN/infinity/out-of-range scores.
- API/CLI parity check confirms the same file/config yields equivalent results within declared numeric tolerance.
- UI checks cover upload -> progress -> result -> seek -> batch -> export, plus failure/retry and keyboard access.
- Restart recovery marks interrupted work clearly and supports retry. Saved results remain associated with their actual model/configuration.
- Performance measurements include cold start, warm inference, representative long clip, and full batch. Set runtime targets only after hardware/data are known.

## Demo storyboard (proposed, not a sponsor requirement)

1. Briefly play two known-provenance recordings and invite an authenticity guess.
2. Analyze one live and show the result, timeline and measured evidence.
3. Explain a limitation or disagreement honestly.
4. Run one compression stress test; display what actually changed.
5. Show the batch run, official-format CSV preflight, and measured baseline comparison.

Use precomputed real results only if clearly labeled. If optional features underperform, demonstrate the stronger validated core.

## Scope protection and fallback

Must ship: real learned detection, multiple automatic analysis techniques, supported audio decoding, honest score semantics, usable investigation/batch UI, reproducibility and required CSV.

Cut first: LLM narration, exact generator attribution, live-call integration, accounts, transcription, custom model training from scratch, cloud deployment, fine-grained splice localization and elaborate motion.

No GPU: measure pretrained CPU inference, cap interactive input duration visibly, use offline batches, or evaluate a lightweight head. Preserve a real baseline; do not silently substitute fake output.

Keep the offline batch CLI usable if the web service fails. Cache permitted model artifacts and record checksums before the demo. If quantization or another runtime is introduced, measure prediction parity and primary-metric impact before adopting it. Test-file duration must never be silently truncated to the interactive UI limit; use a documented full-coverage chunking policy or resolve official limits.

Checkpoint failure: try one documented alternative within a bounded feasibility window. If no learned detector works, stop calling the product a completed authentication system and record the blocker.

Small or mismatched data: prefer simpler models and honest uncalibrated scores over overfit fusion. Keep unknown manipulation types unknown.

## Completion and next action

### UI refinement checkpoint — 2026-09-25

- [x] Integrate supplied morphing-card concept as an explicitly illustrative signal study.
- [x] Apply reusable liquid-glass surfaces, dark palette and locally hosted typography across the workspace.
- [x] Add reduced-motion handling, focus styling, skip link and mobile navigation Escape behavior.
- [x] Pass TypeScript/production build and confirm live intake controls through Chrome accessibility inspection.
- [ ] Complete screenshot-based desktop/mobile review and full interactive journey; macOS capture failure and concurrent Chrome activity prevented this review.

This is a refinement of Phase 2. It does not complete Phase 3 evaluation or Phase 5 submission gates. See `docs/design-system.md` for implementation and QA boundaries.

Planning and independent validation are complete. The user authorized implementation on 2026-09-25. A first local prototype has been built through the independent portions of Phases 0–2 and 4; missing sponsor data prevents evaluation, calibration and the final submission gates. The initial pretrained baseline produced a low score on a known synthetic TTS smoke fixture, so no accuracy claim is warranted. Paid infrastructure, publication and external submission remain unauthorized.

## Revised sequence after design feedback — 2026-09-25

The circle/align/scatter display was decorative and has been removed from the application. Current design direction supersedes the earlier blue signal-study direction: graphite/black glass, Public Sans, plain functional labels and actual recording history.

1. **Interface refinement:** remove decorative signal controls and Engine online badge; apply neutral glass and typography to every existing view; inspect intake, real results and batch. Build verification is required. Small-phone/landscape and reduced-motion interaction checks remain explicit QA tasks.
2. **Core detector evaluation (next engineering priority):** obtain sponsor data, metric and schema; audit grouped splits; compare pretrained candidates against the current known-failing baseline; retain measured improvements; fit and evaluate calibration separately. Produce a reproducible validation report before making performance claims.
3. **Submission readiness:** freeze selected model and configuration, validate official CSV IDs/scale/order, resolve failed files and run the full batch. Rehearse a real recording demo with documented provenance.
4. **Speaker comparison extension:** accept a claimed identity and a consented, trusted reference recording with provenance. Quality-gate both clips, compare speaker embeddings, and evaluate genuine/impostor pairs with speaker-disjoint evaluation, including cloned and replayed examples. Report similarity or inconclusive status, never identity established solely by voice. Gate launch on measured false-accept/false-reject tradeoffs and a clear reference-audio retention/deletion policy. It is a separate output from synthesis detection and cannot identify an unknown person without reference evidence.
5. **Claim review extension:** create a timestamped transcript for user correction; let the analyst select checkable factual claims; retrieve independent sources with publication dates, supporting excerpts and links; report supported/contradicted/insufficient evidence for each claim. Preserve reviewer notes and provenance. Subjective statements, intent and unverifiable/private facts stay unresolved. Validate citation entailment, source relevance and hallucination rate before enabling automated summaries. This is evidence-backed claim review, not lie detection or a universal truth score.
6. **Integrated case report:** present synthesis assessment, speaker comparison and claim review as separate evidence tracks, each with its status and limitations. Never combine them into a misleading overall authenticity probability.

Steps 4–6 are requested product scope, currently planned and not implemented. They must not delay sponsor-required detection/evaluation and CSV delivery. The expanded product addresses the user's request without promising that acoustic analysis proves identity or truth. No prize is guaranteed.

The sequential-thinking skill was read; its specified tool is unavailable in this session. This explicit ordered sequence and its acceptance gates provide the recorded planning fallback.

## Active Phase 1 continuation — public-data pilot

The user has no sponsor dataset yet and authorized finding public development data. A public-data benchmark can move Phase 1 evaluation forward, but cannot close the sponsor-specific evaluation or submission gates. Choose a documented source with genuine/synthetic labels, usable licensing, and reproducible downloads; preserve its original train/test boundaries and disclose overlap with pretrained model training.

- [x] Preserve optional speaker/source metadata and keep transitive linked recordings in one validation partition.
- [x] Make seeded validation membership independent of manifest row order.
- [ ] Complete output-path safety checks before cluster batch runs.
- [ ] Select public development data, obtain a bounded pilot, audit it and report baseline results.
- [ ] Confirm cluster scheduler, GPU memory/types, allocation policy, storage and wall-time constraints.
- [ ] Run a single-GPU pilot before requesting additional approved capacity; free nodes alone do not authorize allocation.

At each phase handoff, report completed acceptance criteria, outstanding gates, actual test results, and the user's web verification steps from `docs/phase-verification.md`. No phase is closed by appearance or passing software tests alone.

### Public pilot completed (Phase 1 evidence, not phase closure)

- [x] Download bounded pinned MLAAD-tiny sample (24 files, ~5.27MB) with public URLs, hashes and source terms recorded.
- [x] Run unchanged baseline and fixed-threshold evaluation:24/24processed;TN9 FP3 FN6 TP6; ROC AUC0.7431. Small selected diagnostic only; no model fitting or calibration.
- [x] CLI input/output alias guards tested, including batch sidecar collisions.
- [ ] Compare another detector on independently defined public development data before selecting training work.

See `challenges/hearsay-audio-authentication/reports/public-pilot/README.md` and `docs/tdd/phase1-evaluation-readiness.md`. Sponsor evaluation/schema and university cluster facts remain unresolved. Public pilot does not close Phase1 or begin Phase3 training.

### Large public data and candidate comparison — continuation

- [x] Research primary sources for ASVspoof5, full MLAAD, In-the-Wild and Deepfake-Eval2024; choose ASVspoof5 Track1 train/dev as the main large public benchmark, with external corpora reserved for separate evaluation.
- [x] Verify official protocol archive checksum; convert182357train/140950dev/680774eval metadata records without repartitioning. Audio remains unavailable locally.
- [x] Implement/test strict protocol importer; retain source/speaker/attack/codec metadata and reject overwrite/malformed input.
- [x] Implement isolated pinned full-AASIST candidate and run unchanged24file public pilot. Mixed result:TN12 FP0 FN8 TP4 at0.5, AUC0.7569; do not promote to web default.
- [x] Record official archive URLs/checksums and57,561,937,920-byte train/dev download inventory.
- [ ] Obtain chosen storage destination and cluster resource facts; install train/dev audio, verify hashes and audit actual files.
- [ ] Establish representative fixed development benchmark and compare stronger architectures/adaptation before training decisions. The candidate experiment is bounded to256files/CPU and is not the full-corpus runner.

Current phase status:Phase1 evaluation infrastructure advanced; public large-data evaluation and sponsor gates remain open. Phase3 training has not started. No cluster nodes allocated.

## Current scope decision — fixed 24-recording demo

The user reversed the large-dataset choice. Pause ASVspoof5 audio acquisition and cluster training. Keep completed importer/research artifacts for later; do not delete them. Use the existing24 MLAAD-tiny recordings as the fixed diagnostic/demo set.

Ordered work:
1. Phase1 demo-data access: expose only the pinned local catalog, known reference labels and hash-verified audio; no arbitrary file paths or downloads.
2. Phase2 guided sample workflow: choose/preview a known recording directly in the web app and send its bytes through the existing real upload/inference pipeline. Clearly separate reference label from prediction. Handle missing/tampered local examples honestly.
3. Verify sample selection -> actual analysis -> playback/seek -> comparison/export using automated checks and live computer-use testing. Hand off a short user checklist.
4. Keep Phase3 training deferred: these24 already inspected recordings cannot serve as independent proof after fitting. Preserve baseline and candidate scores; no fitting, threshold tuning or accuracy claims on the same set. Larger-data infrastructure is paused by user choice.
5. Continue remaining product QA/reporting around this demo scope. Sponsor submission requirements and trustworthy detector evaluation remain separate open gates; a24sample demo does not close them.

### Guided sample milestone delivered

- [x] Phase 1 demo access: pinned catalog with hash, size and path checks; all 24 local examples available.
- [x] Phase 2 guided workflow: choose/preview/analyze known recordings through real inference. Missing samples and request failures have explicit states.
- [x] Desktop browser: genuine and synthetic analysis, playback, interval seek, MP3 derivative and selected export action exercised.
- [x] Automated verification: 61 backend tests, 7 frontend interaction tests, production build.
- [ ] Next: finish responsive/mobile and restart/recovery QA, then rehearse the fixed 24-sample demo and reporting.

This completes the guided-example milestone, not the entire evaluation phase. Training and cluster use remain deferred. Sponsor-specific evaluation/submission gates stay open. See docs/tdd/pilot-demo.md.

## Priority correction — detector usefulness first

User explicitly reopened training with a five-hour cluster budget. Follow docs/detector-improvement-plan.md: Phase1 scoring parity/error audit → Phase3A independent data and training runner → Phase3B one-GPU timed adaptation → Phase3C measured acceptance → Phase2 evidence presentation → Phases4/5 demo and delivery. Mobile polish is no longer the immediate critical path. Gates and resource prerequisites are documented; no accuracy or completed-training claims.

## Detector and AI review implementation milestone

- [x] Parity checks for decoding, class polarity, padding and explicit first-crop versus whole-file aggregation difference.
- [x] All24file error report and non-destructive diagnostics CLI.
- [x] Experimental bounded AASIST-L training runner; label-map conversion, leakage/demo exclusion, weighted optimization, finite-loss/gradient checks and saved checkpoint/provenance. CPU optimizer smoke verified.
- [x] User-selected Grok interpretation: root `.env`, on-demand backend/API, evidence-linked findings, cached JSON export and UI unavailable/retry states. Deterministic notes relabeled Measurement limitations.
- [x] Backend102tests, frontend15tests, productionbuild; livebrowser missing-key/configrefresh.
- [ ] Add userkey and run realGrok output review. Tests used explicit doubles, not generated text.
- [ ] Next detectionphase: obtain separate dataset at cluster storage, lock train/selection/acceptance manifests; implement whole-file candidate-checkpoint scorer and bounded Slurm submission using confirmed allocation.
- [ ] Run five-hour experiment and promote only on independent acceptance evidence. Current detector remains unchanged.

Product feature priorities: reliable synthetic-speech triage; playable scored intervals; noise/compression comparisons; AI-written evidence brief; full error/validation report; exportable findings with model provenance. Speaker-reference comparison and external-source claim review remain later, separately validated extensions. No extra decorative features take priority over detection quality.
