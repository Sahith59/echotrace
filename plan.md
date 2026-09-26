# ECHOTRACE: current implementation and delivery plan

Updated 2026-09-26. This is the authoritative checklist. **The workbench and requested evidence extensions are implemented. Two independent public-data detector experiments completed and failed promotion goals. A final native adaptation experiment is preparing a new locked public-evaluation holdout. Release packaging and verification are underway; live Grok and official sponsor submission still require external inputs.**

Previous decisions and dated milestones are preserved in [the historical plan](plan-history-2026-09-25.md). They do not override this checklist. Operational continuity is in [memory.md](memory.md), stable rules in [claude.md](claude.md).

## Product and challenge fit

ECHOTRACE helps an analyst investigate a suspicious recorded voice message: upload audio, inspect the learned synthesis assessment and measured evidence, listen to scored passages, compare noise/compression, and export a reproducible report. It focuses on NSA HackGT13 Challenge 1, HEARSAY.

Required challenge outputs: supported audio-file input, automatic orchestration of multiple forensic methods, a synthesis score on a 0–100 scale, and CSV predictions for the sponsor's held-out data. Manipulation subtype is optional in the detailed brief. See [challenge text](challenges/hearsay-audio-authentication/CHALLENGE.md).

The numerical score comes from the speech detector. Signal measurements describe the recording. Grok explains supplied measurements and cannot change the score. Current scores are uncalibrated; low scores do not prove authenticity. Speaker similarity and source-backed claim reviews are implemented as separate evidence workflows; neither proves identity or truth.

## Current phase overview

| Phase | Status | What closes it |
| --- | --- | --- |
| 0 — Requirements | Internal requirements documented; sponsor details missing | Official data, metric, CSV template, full rules and NSA cutoff confirmed |
| 1 — Baseline | Working pipeline and public diagnostic evaluation | Sponsor-specific baseline evaluation and schema validation remain open |
| 2 — Workbench | Implemented; local checks complete with stated exceptions | Manual unfamiliar-file upload and live Grok verification remain |
| 3A — Prepare | Complete for the bounded public-data run | 14,000 selected files audited; split separation and GPU execution verified |
| 3B — Adapt | Completed: adaptation and frozen-candidate experiments | Final job 4504574 finished; artifacts retained |
| 3C — Evaluate | Three experiments evaluated; quality gate failed | Representative codec data and a fresh independent benchmark before another promotion attempt |
| 4 — Demonstrate | Local rehearsal and saved fallback complete | Venue/display rehearsal and live Grok remain external checks |
| 5 — Submit | Pending sponsor materials and final evaluation | Frozen model, validated official CSV, runnable prototype and required artifacts |
| Extensions — Speaker and claims | Implemented and tested | Live Grok remains unverified without a key; similarity is not identity proof |

## Phase 0 — Requirements

- [x] Scope NSA #1 only; preserve the sponsor's supplied brief.
- [x] Record input/output contracts and local-first architecture.
- [x] Confirm five-hour aggregate GPU budget, one GPU/one node, account and personal cluster storage.
- [ ] Obtain official sponsor training/test data and label definitions.
- [ ] Confirm scoring metric, CSV columns/scale/order, permitted feedback and evaluation rules.
- [x] Read the organizer packet in Chrome: main schedule ends hacking September 27 at 8 AM; one track plus eligible sponsor challenges; teams up to four. See [organizer requirements](docs/organizer-requirements.md).
- [x] Read public Devpost requirements: code/AI attribution, Devpost then Expo registration, one project and expo attendance; record timing inconsistencies. Prepare [submission copy](docs/submission-draft.md).
- [ ] Confirm remaining full event rules, sponsor-specific cutoff/destination and external-data/prior-work terms. The linked live site requires event login.

Sponsor-specific unknowns do not block independent engineering, but public-data performance does not establish sponsor performance.

## Phase 1 — Real baseline and evaluation infrastructure

- [x] FFmpeg decoding and validation for WAV, MP3 and M4A; explicit corrupt/quiet/oversized/long-input handling.
- [x] Pinned pretrained AASIST-L inference using shared API/CLI code.
- [x] Full-coverage scored windows, waveform and measured quality/spectral observations.
- [x] Preserve source hash, model/configuration, raw score, score kind, errors and runtime.
- [x] Verify class polarity, padding, API/CLI parity and first-crop versus whole-file behavior.
- [x] Keep 24 public reference clips with labels/provenance separate from predictions and independent evaluation.
- [x] Document baseline diagnostic failures; compare full AASIST without promoting it.
- [x] Implement grouped manifest preparation, independent checkpoint evaluation and strict configurable CSV export.
- [x] Establish candidate performance on independent public splits and record failed promotion gates.
- [ ] Repeat evaluation on sponsor data and validate the official CSV contract when available.

Known diagnostic: the original detector caught 6/12 synthetic recordings and falsely flagged 3/12 genuine recordings at threshold 0.5 on the selected 24 clips. This small inspected set is a diagnostic, not a general accuracy estimate. The app still serves the original model.

## Phase 2 — Complete investigation workbench

**Implementation complete does not mean all acceptance checks are complete.** Each item below records that distinction.

### Implemented and covered by automated checks

- [x] Single/multiple uploads, byte/duration limits and actionable errors.
- [x] Durable SQLite jobs, actual processing stages, saved results, failure isolation and retry.
- [x] Intake, investigation, recording history and batch views connected to real inference.
- [x] Audio playback, waveform seeking and selectable scored intervals.
- [x] Measured forensic observations, calibration label, limitations and technical provenance.
- [x] Known-recording selector with reference labels kept distinct from model scores.
- [x] Real MP3/noise derivatives, playback, separate analyses and score differences.
- [x] JSON report and selected analyst CSV export; reject failed/scoreless/duplicate selections server-side.
- [x] Graphite glass interface, local Public Sans typography, visible focus/skip link and reduced-motion implementation.
- [x] Grok backend and UI integration: on-demand evidence-only requests, validated citations, cache, provenance, explicit failure states and unchanged detector score.

### Acceptance checks

- [x] Desktop known-recording analysis, playback/interval seeking and MP3 comparison exercised in the browser.
- [x] Narrow-screen recording playback and keyboard seeking verified; selected JSON report downloaded and inspected.
- [x] Two-result analyst CSV downloaded through the browser; exact IDs and saved scores verified in the file.
- [x] Failed and scoreless QA recordings are disabled in the live batch selection UI.
- [x] Real detector/FFmpeg integration verifies completed JSON/CSV persist byte-identically across application lifespan restart; interrupted work becomes failed and retries successfully.
- [x] Repair the reproduced mobile keyboard focus escape and verify focus entry, Tab containment and Escape restoration in Chrome. Automated tests also cover desktop resize and cleanup.
- [ ] Complete unfamiliar-file browser upload journey. Automated browser file selection is blocked by the Chrome extension's file-URL permission; backend format tests pass.
- [x] Inspect desktop, 375×812 phone and 812×375 landscape layouts; verify no page overflow and visible input focus. Mobile focus containment/reduced-motion implementation are tested. This is not a formal screen-reader/WCAG certification or pixel-regression suite.
- [ ] Verify live Grok output, citations, persistence and unchanged score after the user saves `XAI_API_KEY` in root `.env`. Key is absent at last status check.
- [x] Present measured validation summaries with checkpoint hashes and explicit failed/not-promoted status; never label an experimental model as serving.

Evidence: [restart verification](docs/phase2-restart-verification.md), [phase verification](docs/phase-verification.md), [feature inventory](docs/product-capabilities.md). Analyst CSV is implemented; official sponsor-format export remains a Phase 5 gate.

## Phase 3A — Prepare independent speech data (complete for this run)

- [x] Verify VPN/SSH, account `trends517s113`, `qTRD` CPU and `qTRDGPUM` GPU access.
- [x] Use owned `/data/users3/sthummala2/echotrace`; preserve unrelated research and avoid large home-directory storage.
- [x] Install pinned environment, FFmpeg and model weights through CPU Slurm jobs.
- [x] Stage official train/dev `aa` archives only: 14,169,763,840 archive bytes, verified checksums; 36,500 train and 47,400 dev recordings available.
- [x] Freeze 10,000 training / 2,000 selection / 2,000 locked acceptance recordings, excluding the inspected demo set.
- [x] Verify content/ID/group/speaker/source separation and class coverage.
- [x] Decode and audit all 14,000 selected files: zero failures and zero quiet files.
- [x] Verify source snapshot hashes and Linux tests; perform finite forward/backward computation on one actual A100.

| Split | Genuine | Synthetic | Role |
| --- | --- | --- | --- |
| Training | 3,801 | 6,199 | Update model weights |
| Selection | 1,021 | 979 | Select checkpoint and decision threshold |
| Locked acceptance | 979 | 1,021 | Independently assess the frozen candidate |

Training includes attacks A01–A08; selection/acceptance include A09–A16. Codec metadata is `-` throughout this subset, so it does not provide a meaningful cross-codec benchmark. The subset is not the full ASVspoof5 corpus.

## Phase 3B — Bounded adaptation

- [x] Submit success-dependent main job **4503646**; it started **2026-09-26 01:00:42 America/New_York**.
- [x] Confirm actual model fitting: `training/best.pt` exists, first observed at 05:11 UTC.
- [x] Complete run 01: Slurm 4503646, 6,000 steps, saved checkpoint/configuration and hashes, 55m49 GPU allocation elapsed.
- [x] Complete run 01 four whole-file evaluations: baseline/candidate on selection/acceptance, zero file failures.
- [x] Preserve run 01 acceptance report, full score ledgers and attack/codec slices.
- [x] Evaluate a pinned frozen wav2vec2 candidate in run 02 on 457 new-speaker acceptance clips; no promotion.
- [x] Complete final native adaptation/evaluation in job **4504574**: 1,250 optimizer steps, early stop after epoch 2, retain epoch 1 checkpoint. The frozen 2,000-file evaluation holdout passed decoder and original-file hash independence checks before fitting.
- [x] Preserve setup failures: CPU job 4503784 lacked ffprobe; recovery 4504563 passed; GPU 4504573 exited after four seconds on a missing parent; replacement 4504574 completed in 40m52.

One A100-SXM4-40GB, one node, 4 CPUs, 32 GB host RAM. Aggregate actual GPU allocation use is **1h44m53**, including smoke/setup failures. No further GPU run is planned in this iteration. CPU preparation and queue time are separate. No automatic requeue or duplicate allocation.

See [run ledger](docs/cluster-run-2026-09-25.md) for exact paths, job IDs and live-status commands. A running job or checkpoint file is not proof of improved accuracy.

## Phase 3C — Evaluate before replacing the web model

- [x] Verify all three completed experiments, finite predictions, failures, checkpoint provenance and selection-only thresholds.
- [x] Review recall, false-positive rate, AUROC, counts, confidence intervals and available attack/codec slices.
- [x] Evaluate the predeclared promotion goals: at least 80% recall, at most 5% false positives, at least 10 percentage-point recall gain, no AUROC regression. **The final candidate failed the false-positive goal.**
- [x] Retain the original serving model and preserve failed candidates as experimental evidence. No checkpoint is promoted automatically.
- [ ] Meet the detector quality goals on a new representative independent benchmark. This is an unresolved product-quality requirement, not a completed feature.
- [ ] If a future candidate passes, verify local CPU/evaluator parity, latency/memory, model-version comparison guards and rollback before activating it.

Final native candidate: **87.4% recall, 24.4% false-positive rate, AUROC 0.90609** on 1,000 genuine and 1,000 synthetic recordings. Baseline on those same files: 53.7% recall, 24.0% false positives, AUROC 0.70538. Thresholds were fixed using the original selection set. These are different records from earlier experiments and must not be pooled as directly comparable tests.

Post-hoc diagnosis finds much higher false positives on several compressed genuine-audio codecs. Do not retune on this inspected acceptance set. A future experiment needs representative compressed genuine training/selection data, an independently frozen test with sufficient speaker diversity, and remaining-budget review. Our audits establish independence from this project's records, not every upstream pretraining corpus. Calibration, ensembles and further encoders remain conditional research, not completed features.

## Phase 4 — Compelling demonstration

- [x] Provide real noise/compression comparisons and playable derived audio.
- [x] Preserve example provenance/licenses and distinguish reference labels from predictions.
- [x] Export investigation evidence and model provenance.
- [x] Exercise genuine, synthetic/missed-detection, corrupt, quiet, noisy and compressed cases through browser/API checks; preserve their actual results.
- [x] Present independent before/after detector results in the live validation panel, including failed promotion decisions; the final run is included in the release summary.
- [x] Save real genuine and missed-synthetic case JSON/HTML with SHA-256 manifest under ignored `artifacts/release-demo/`; explicitly label them prior runs.
- [x] Verify the local desktop and responsive layouts, report/export/seek/claim controls and honest unavailable states. Unfamiliar-file browser chooser and live Grok remain the Phase 2 external checks; actual venue/display rehearsal is still needed.

Demo sequence: suspicious recording → actual assessment → listen to a scored passage → compare a compressed/noisy copy → evidence-linked explanation when configured → export report → measured detector comparison. Do not claim precise edit localization, identity proof or factual truth from a synthesis score.

## Phase 5 — Freeze and submit

- [ ] Obtain official schema, held-out inputs, scoring metric, deadline and destination.
- [ ] Freeze detector/configuration and any independently validated calibration.
- [ ] Run held-out inference without label-driven tuning.
- [ ] Validate all IDs exactly once, columns/order/scale/polarity and finite values; resolve failures.
- [ ] Finish restart, responsive, export and live-provider acceptance checks.
- [x] Document reproducible setup/inference/export commands and known limitations.
- [x] Publish verified runnable source, tests, documentation and evaluation reports to [Sahith59/echotrace](https://github.com/Sahith59/echotrace), private. Application commit `eb14365` passed [GitHub CI](https://github.com/Sahith59/echotrace/actions/runs/36230750860): 249 backend passed / one macOS-only test skipped; 32 frontend passed and production build passed. Local macOS suite passed all250 backend tests.
- [ ] Produce the official CSV and any remaining required event artifacts after the sponsor contract is supplied.
- [ ] Rehearse and submit through the authorized destination once supplied.

## Requested evidence extensions

- [x] **Speaker-reference comparison:** consented local reference, pinned WavLM embeddings, quality gates, cosine similarity, temporary reference deletion and separately removable metadata. Real model/self-match and automated failure checks pass. No calibrated genuine/impostor/clone/replay population benchmark or identity claim is made.
- [x] **Transcript and claim workflow:** local timestamped transcription, immutable corrections, passage-to-claim time links, analyst-supplied evidence and optional consented Grok web search. Sources must occur in provider citations; failed/unsupported responses remain unresolved. Live provider validation requires the missing key. This is not lie detection.
- [x] **Integrated case report:** JSON and printable HTML show synthesis, speaker reference, transcript versions and claim reviews separately; escaped untrusted text and no overall authenticity probability.

## Handoff and next work

The authorized private source repository is published and the application CI passed. This iteration stops at source handoff; deployment awaits the user's next direction. A final documentation-only commit records publication without changing the tested application.

Remaining gates:

1. Save the xAI key locally and verify real interpretation/search output; manually exercise the unfamiliar-file browser chooser.
2. Obtain official NSA held-out files, CSV schema, metric, cutoff and submission instructions; use the strict export pipeline and resolve every failed row.
3. Address compressed-genuine false positives using representative training/selection data and a fresh benchmark before claiming a strong detector or promoting a candidate. Do not retune the inspected acceptance sets.
4. Plan deployment authentication, storage/retention and hosting in the next user-directed iteration. No deployment or official competition entry was performed here.
