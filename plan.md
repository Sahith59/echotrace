# ECHOTRACE: current implementation and delivery plan

Updated 2026-09-26. **The approved light workspace and guided investigation are implemented. New API/CLI analyses use pinned NII whole-file scoring (<=30seconds); legacy AASIST results remain immutable. A real browser NII analysis and real Groq interpretation succeeded. Guided steps, queue/date filters, analyst reviews and provenance-safe comparisons/exports are implemented. Phase5 local verification is complete within the documented checks; official sponsor data/schema/submission and deployment remain external gates. NII serving is an explicit prototype decision using absolute benchmark gates and parity, not a claim that the old training-candidate comparative contract passed.**

Previous decisions and dated milestones are preserved in [the historical plan](plan-history-2026-09-25.md). They do not override this checklist. Operational continuity is in [memory.md](memory.md), stable rules in [claude.md](claude.md).

## Product and challenge fit

ECHOTRACE helps an analyst investigate a suspicious recorded voice message: upload audio, inspect the learned synthesis assessment and measured evidence, listen to scored passages, compare noise/compression, and export a reproducible report. It focuses on NSA HackGT13 Challenge 1, HEARSAY.

Required challenge outputs: supported audio-file input, automatic orchestration of multiple forensic methods, a synthesis score on a 0–100 scale, and CSV predictions for the sponsor's held-out data. Manipulation subtype is optional in the detailed brief. See [challenge text](challenges/hearsay-audio-authentication/CHALLENGE.md).

The numerical score comes from the speech detector. Signal measurements describe the recording. Groq explains supplied measurements and cannot change the score. Current scores are uncalibrated; low scores do not prove authenticity. Speaker similarity and source-backed claim reviews are implemented as separate evidence workflows; neither proves identity or truth.

## Current phase overview

| Phase | Status | What closes it |
| --- | --- | --- |
| 0 — Requirements | Internal requirements documented; sponsor details missing | Official data, metric, CSV template, full rules and NSA cutoff confirmed |
| 1 — Baseline | Working pipeline and public diagnostic evaluation | Sponsor-specific baseline evaluation and schema validation remain open |
| 2 — Workbench | Implemented; built-in public-sample multipart upload and live Groq generation passed in the browser | Manual native unfamiliar-file chooser check remains |
| 3A — Prepare | Complete for the bounded public-data run | 14,000 selected files audited; split separation and GPU execution verified |
| 3B — Adapt | Completed: adaptation and frozen-candidate experiments | Final job 4504574 finished; artifacts retained |
| 3C — Evaluate | Earlier adaptations failed; NII passed parity and frozen absolute gates and is the scoped prototype primary | Retrieve paired baseline job 4504670; public benchmark replication is not sponsor validation or a superiority claim |
| 4 — Demonstrate | Light guided workspace, queue/review flow, real Groq generation and saved fallback complete | Venue/display rehearsal remains external |
| 5 — Submit | Pending sponsor materials and final evaluation | Frozen model, validated official CSV, runnable prototype and required artifacts |
| Extensions — Speaker and claims | Implemented and tested, including live Groq interpretation | Similarity is not identity proof; generated interpretation can be wrong |

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
- [x] Groq backend and UI integration: on-demand evidence-only requests, validated citations, cache, provenance, explicit failure states and unchanged detector score.

### Acceptance checks

- [x] Desktop known-recording analysis, playback/interval seeking and MP3 comparison exercised in the browser.
- [x] Narrow-screen recording playback and keyboard seeking verified; selected JSON report downloaded and inspected.
- [x] Two-result analyst CSV downloaded through the browser; exact IDs and saved scores verified in the file.
- [x] Failed and scoreless QA recordings are disabled in the live batch selection UI.
- [x] Real detector/FFmpeg integration verifies completed JSON/CSV persist byte-identically across application lifespan restart; interrupted work becomes failed and retries successfully.
- [x] Repair the reproduced mobile keyboard focus escape and verify focus entry, Tab containment and Escape restoration in Chrome. Automated tests also cover desktop resize and cleanup.
- [ ] Complete the native unfamiliar-file chooser journey manually. Built-in public-sample normal multipart upload passed in the browser; automated local-file selection remains blocked by the Chrome extension's file-URL permission.
- [x] Inspect desktop, 375×812 phone and 812×375 landscape layouts; verify no page overflow and visible input focus. Mobile focus containment/reduced-motion implementation are tested. This is not a formal screen-reader/WCAG certification or pixel-regression suite.
- [x] Verify live Groq interpretation output, evidence references, persistence and unchanged score. The initial edge `403` was fixed with the required user-agent; authenticated browser generation succeeded with the working key.
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

## Phase 3C — Historical candidate evaluation and current serving decision

- [x] Verify all three completed experiments, finite predictions, failures, checkpoint provenance and selection-only thresholds.
- [x] Review recall, false-positive rate, AUROC, counts, confidence intervals and available attack/codec slices.
- [x] Evaluate the predeclared promotion goals: at least 80% recall, at most 5% false positives, at least 10 percentage-point recall gain, no AUROC regression. **The final candidate failed the false-positive goal.**
- [x] Historical decision: retain the original serving model after the three training candidates failed and preserve those candidates as experimental evidence. No checkpoint was promoted automatically.
- [ ] Meet the detector quality goals on a new representative independent benchmark. This is an unresolved product-quality requirement, not a completed feature.
- [x] Separately evaluate pinned NII: official-reference parity and frozen absolute benchmark gates passed; activate it as the explicitly reviewed prototype primary with local CPU/runtime, provenance, failure and rollback checks.

Final native candidate: **87.4% recall, 24.4% false-positive rate, AUROC 0.90609** on 1,000 genuine and 1,000 synthetic recordings. Baseline on those same files: 53.7% recall, 24.0% false positives, AUROC 0.70538. Thresholds were fixed using the original selection set. These are different records from earlier experiments and must not be pooled as directly comparable tests.

Post-hoc diagnosis finds much higher false positives on several compressed genuine-audio codecs. Do not retune on this inspected acceptance set. A future experiment needs representative compressed genuine training/selection data, an independently frozen test with sufficient speaker diversity, and remaining-budget review. Our audits establish independence from this project's records, not every upstream pretraining corpus. Calibration, ensembles and further encoders remain conditional research, not completed features.

## Phase 4 — Compelling demonstration

- [x] Provide real noise/compression comparisons and playable derived audio.
- [x] Preserve example provenance/licenses and distinguish reference labels from predictions.
- [x] Export investigation evidence and model provenance.
- [x] Exercise genuine, synthetic/missed-detection, corrupt, quiet, noisy and compressed cases through browser/API checks; preserve their actual results.
- [x] Present independent before/after detector results in the live validation panel, including failed promotion decisions; the final run is included in the release summary.
- [x] Save real genuine and missed-synthetic case JSON/HTML with SHA-256 manifest under ignored `artifacts/release-demo/`; explicitly label them prior runs.
- [x] Verify the local light desktop and responsive layouts, guided steps, queue filters, report/export/seek/claim controls, live Groq generation and honest unavailable states. The native unfamiliar-file chooser and actual venue/display rehearsal remain manual checks.

Demo sequence: suspicious recording → actual assessment → listen to a scored passage → compare a compressed/noisy copy → evidence-linked explanation when configured → export report → measured detector comparison. Do not claim precise edit localization, identity proof or factual truth from a synthesis score.

## Phase 5 — Freeze and submit

- [ ] Obtain official schema, held-out inputs, scoring metric, deadline and destination.
- [ ] Freeze detector/configuration and any independently validated calibration.
- [ ] Run held-out inference without label-driven tuning.
- [ ] Validate all IDs exactly once, columns/order/scale/polarity and finite values; resolve failures.
- [x] Finish restart, responsive, export and live-provider acceptance checks for the local prototype.
- [x] Document reproducible setup/inference/export commands and known limitations.
- [x] Verify the release wheel contains `primary_detector`, `analyst_review`, `nii_parity` and `validation_summary`, and excludes environment files, uploaded audio and model weights.
- [x] Historical release: publish verified runnable source, tests, documentation and evaluation reports to [Sahith59/echotrace](https://github.com/Sahith59/echotrace), private. Application commit `eb14365` passed [GitHub CI](https://github.com/Sahith59/echotrace/actions/runs/36230750860): 249 backend passed / one macOS-only test skipped; 32 frontend passed and production build passed. Local macOS suite passed all 250 backend tests. The final NII/light-workspace source update was pushed as `a4db6e4`; backend and frontend passed [clean-install CI36251617928](https://github.com/Sahith59/echotrace/actions/runs/36251617928).
- [ ] Produce the official CSV and any remaining required event artifacts after the sponsor contract is supplied.
- [ ] Rehearse and submit through the authorized destination once supplied.

## Requested evidence extensions

- [x] **Speaker-reference comparison:** consented local reference, pinned WavLM embeddings, quality gates, cosine similarity, temporary reference deletion and separately removable metadata. Real model/self-match and automated failure checks pass. No calibrated genuine/impostor/clone/replay population benchmark or identity claim is made.
- [x] **Transcript and claim workflow:** local timestamped transcription, immutable corrections, passage-to-claim time links, analyst-supplied evidence and analyst-supplied public source URLs. Hosted Groq search is currently unavailable pending validated retrieval provenance; historical provider reviews remain visible. This is not lie detection.
- [x] **Integrated case report:** JSON and printable HTML show synthesis, speaker reference, transcript versions and claim reviews separately; escaped untrusted text and no overall authenticity probability.

## Handoff and next work

The earlier source release is published. The user reopened detector improvement and Groq integration; the current source update passed fresh local checks and is published. Deployment still awaits user direction.

Remaining gates:

1. Manually exercise the native unfamiliar-file browser chooser; built-in public-sample multipart upload and live Groq interpretation already passed.
2. Obtain official NSA held-out files, CSV schema, metric, cutoff and submission instructions; use the strict export pipeline and resolve every failed row.
3. Address compressed-genuine false positives using representative training/selection data and a fresh benchmark before claiming a strong detector or promoting a candidate. Do not retune the inspected acceptance sets.
4. Plan deployment authentication, storage/retention and hosting in the next user-directed iteration. No deployment or official competition entry was performed here.

## Reopened detector and provider iteration

- [x] Confirm provider is Groq; create ignored owner-only key placeholder and adapt evidence interpretation.
- [x] Add condition-specific benchmark inspection from actual run03 report; browser C07 slice checked.
- [x] Finish source-search provider migration and regression tests. Hosted search must remain unavailable until actual retrieved URL provenance can be validated; analyst review remains supported.
- [x] Freeze and audit In-The-Wild external manifest (successful CPU4504655): 2,000 rows balanced1,000/class, all<=30s, onequiet retained; zeroexact-byte overlaps against16,458project hashes. Source IDs absent, upstream pretraining independence not established.
- [x] Finish clean cluster parity record for pinned NII adapter (CPU4504660, completed). Corrected five-input CPUcomparison passes declared1e-3logit/1e-4probability limits; earlier setup failures preserved.
- [x] Run frozen external benchmark at predeclared threshold0.5: CPU4504662 completed, all2,000 model-scored, recall93.7%, FPR2.4%, AUROC0.9925. One quiet genuine row is retained in these model-only results; app-eligible comparison must use the common1,999 rows. No threshold tuning on this benchmark; no ASVspoof5 independence claim for NII.
- [x] Make the reviewed prototype serving decision after measured absolute gates, reference parity, runtime and provenance checks; do not describe it as scientific superiority or passage of the older training-specific acceptance contract.
- [x] Publish the current source update; no deployment. Local verification is complete: 290 backend tests, 51 frontend tests and production build passed.

- [x] Integrate and browser-test an on-demand, research-only NII second-detector comparison. Keep primary score unchanged, preserve both model identities, and never average uncalibrated scores. Frontend seven journeys pass; real genuine/synthetic comparisons, quiet rejection, saved reports, and 375px layout verified in Chrome.

### Completed primary migration and open paired evaluation

- [ ] Finish same-file AASIST baseline comparison and common app-eligible denominator audit. NII result is public benchmark replication; the authors have previously evaluated this dataset.
- [x] Route the shared primary API/CLI pipeline through pinned NII with its verified whole-file <=30-second preprocessing; reject rather than silently truncate longer inputs.
- [x] Preserve existing AASIST reports and their model IDs; prevent mixed-model robustness comparisons and ambiguous CSV exports.
- [x] Verify primary inference parity, runtime, missing-model/quiet/long-file failures and rollback; update model status consistently.
- [x] Keep historical experiments and separate speaker/claim evidence. Groq explanations refer to the actual primary model's evidence.

Groq activation is complete. The ignored root `.env` remains backend-only; never paste the key into chat. Live authenticated generation passed after the client supplied the required user-agent. Do not repeat a billable call solely for verification.

## Approved continuation: UI and phases3C–5

- [x] Replace dark monochrome styling with light textured glass, readable text hierarchy, semantic button/status colors and reduced-motion transitions.
- [x] Adapt supplied calendar into real queue date filtering; add keyboard-usable contextual info buttons.
- [x] Phase3C prototype primary migration: pinned NII shared API/CLI, parity/runtime checks,30second limit, fail-closed input/model handling, preserved historical AASIST reports. See serving-decision document for measured and unmeasured boundaries.
- [x] Phase4A: Review recording / Check reliability / Case evidence navigation; durable analyst status and notes with optimistic concurrency and local draft retention.
- [x] Phase4B: queue search/status/review/date filters, score/date sort, actual compression/noise comparison, full-provenance mixed-model guards and original reanalysis.
- [x] Phase4C: real Groq generation; allowlisted current comparison measurements invalidate stale briefs; clickable evidence references; versioned analyst findings in case report and CSV.
- [ ] Phase5 official submission: still needs sponsor inputs/schema/metric and authorized destination. No official submission or deployment is claimed.
- [ ] Retrieve completed same-file baseline CPU4504670 when cluster login returns. Latest attempts timed out at the jump-host banner; no duplicate jobs launched.

User verification: open a known sample, run NII (or use legacy reanalysis), inspect help, switch investigation steps, save notes, filter the queue, run one transformation and export a same-model case/CSV. The key previously appeared rejected; bounded diagnosis showed an unstructured edge403 fixed by an explicit User-Agent. Real Groq generation subsequently succeeded—do not ask the user to replace the working key.
