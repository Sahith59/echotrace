# ECHOTRACE: current implementation and delivery plan

Updated 2026-09-26. This is the authoritative checklist. **Phase 3A is complete for the first public-data experiment. Phase 3B is running. Phase 2 core implementation is complete, but full verification and live Grok review are still open.**

Previous decisions and dated milestones are preserved in [the historical plan](plan-history-2026-09-25.md). They do not override this checklist. Operational continuity is in [memory.md](memory.md), stable rules in [claude.md](claude.md).

## Product and challenge fit

ECHOTRACE helps an analyst investigate a suspicious recorded voice message: upload audio, inspect the learned synthesis assessment and measured evidence, listen to scored passages, compare noise/compression, and export a reproducible report. It focuses on NSA HackGT13 Challenge 1, HEARSAY.

Required challenge outputs: supported audio-file input, automatic orchestration of multiple forensic methods, a synthesis score on a 0–100 scale, and CSV predictions for the sponsor's held-out data. Manipulation subtype is optional in the detailed brief. See [challenge text](challenges/hearsay-audio-authentication/CHALLENGE.md).

The numerical score comes from the speech detector. Signal measurements describe the recording. Grok explains supplied measurements and cannot change the score. Current scores are uncalibrated; low scores do not prove authenticity. Speaker identity and factual truth are separate questions with separately planned evidence workflows.

## Current phase overview

| Phase | Status | What closes it |
| --- | --- | --- |
| 0 — Requirements | Internal requirements documented; sponsor details missing | Official data, metric, CSV template, rules and deadline confirmed |
| 1 — Baseline | Working pipeline and public diagnostic evaluation | Sponsor-specific baseline evaluation and schema validation remain open |
| 2 — Workbench | Core implemented; acceptance checks in progress | Remaining browser/accessibility checks and live AI interpretation review |
| 3A — Prepare | Complete for the bounded public-data run | 14,000 selected files audited; split separation and GPU execution verified |
| 3B — Adapt | Running: Slurm 4503646 | A saved checkpoint and completed training/evaluation artifacts |
| 3C — Evaluate | Waiting for the active job | Independent comparison, error review and serving checks before replacement |
| 4 — Demonstrate | Comparison feature built; rehearsal pending | A complete honest demo with measured successes and failures |
| 5 — Submit | Pending sponsor materials and final evaluation | Frozen model, validated official CSV, runnable prototype and required artifacts |
| Extensions — Speaker and claims | Planned, not implemented | Separate reference/source evidence and validation; cannot delay core submission |

## Phase 0 — Requirements

- [x] Scope NSA #1 only; preserve the sponsor's supplied brief.
- [x] Record input/output contracts and local-first architecture.
- [x] Confirm five-hour aggregate GPU budget, one GPU/one node, account and personal cluster storage.
- [ ] Obtain official sponsor training/test data and label definitions.
- [ ] Confirm scoring metric, CSV columns/scale/order, permitted feedback and evaluation rules.
- [ ] Confirm event-wide requirements, deadline, submission destination and external-data terms.

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
- [ ] Establish candidate performance on the current independent public split (active Phase 3 experiment).
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
- [ ] Complete visual/accessibility checks at desktop, narrow phone and landscape sizes. Current DOM measurements show no page overflow at 375/768 px; this is not a full accessibility or visual-regression pass.
- [ ] Verify live Grok output, citations, persistence and unchanged score after the user saves `XAI_API_KEY` in root `.env`. Key is absent at last status check.
- [ ] After Phase 3C, present the accepted model's validation summary linked to its actual version/configuration.

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

## Phase 3B — Bounded adaptation (running)

- [x] Submit success-dependent main job **4503646**; it started **2026-09-26 01:00:42 America/New_York**.
- [x] Confirm actual model fitting: `training/best.pt` exists, first observed at 05:11 UTC.
- [ ] Complete the training run and save final metrics/configuration/checkpoint hash.
- [ ] Complete four whole-file evaluations: baseline/candidate on selection/acceptance.
- [ ] Produce the acceptance report, complete score ledgers and attack/codec slices.

One A100-SXM4-40GB, one node, 4 CPUs, 32 GB host RAM. Main Slurm limit 4h55, plus the earlier smoke's five-minute reservation, totals five GPU-hours maximum. Training itself is capped at three hours / 6,000 steps / 10 epochs; each evaluation at 20 minutes. Automatic requeue is disabled. Do not duplicate or extend the run. CPU preparation and queue time are separate from GPU time.

See [run ledger](docs/cluster-run-2026-09-25.md) for exact paths, job IDs and live-status commands. A running job or checkpoint file is not proof of improved accuracy.

## Phase 3C — Evaluate before replacing the web model

- [ ] Verify complete outputs, expected IDs, finite values, recorded failures and checkpoint/config consistency.
- [ ] Select thresholds using selection data only; keep acceptance labels out of training/tuning.
- [ ] Review synthetic recall, genuine false-positive rate, AUROC, average precision, counts and confidence intervals.
- [ ] Review attack slices, individual misses and regressions; disclose codec-coverage limitations.
- [ ] Evaluate provisional goals: at least 80% recall, at most 5% false-positive rate, at least 10 percentage-point recall gain, no AUROC regression. These are internal goals, not predicted results or sponsor criteria.
- [ ] Verify checkpoint loading and API/CLI serving parity; measure local inference latency/memory.
- [ ] Keep a rollback checkpoint and replace the web model only if evidence supports it.
- [ ] If the candidate fails, report the failure and decide the next architecture/data experiment without automatically exceeding the compute budget.

Calibration, fusion/ensembles, alternate speech encoders and EER reporting are conditional follow-ups, not completed features or mandatory additions. Only retain changes with measured benefit. Never inflate scores to make a demo look successful.

## Phase 4 — Compelling demonstration

- [x] Provide real noise/compression comparisons and playable derived audio.
- [x] Preserve example provenance/licenses and distinguish reference labels from predictions.
- [x] Export investigation evidence and model provenance.
- [ ] Rehearse genuine, synthetic, failed-detection, noisy and compressed cases.
- [ ] Present independent before/after detector results once available.
- [ ] Prepare a clearly labeled saved real run as a network fallback.
- [ ] Validate all demo controls and readable layout on the presentation display.

Demo sequence: suspicious recording → actual assessment → listen to a scored passage → compare a compressed/noisy copy → evidence-linked explanation when configured → export report → measured detector comparison. Do not claim precise edit localization, identity proof or factual truth from a synthesis score.

## Phase 5 — Freeze and submit

- [ ] Obtain official schema, held-out inputs, scoring metric, deadline and destination.
- [ ] Freeze detector/configuration and any independently validated calibration.
- [ ] Run held-out inference without label-driven tuning.
- [ ] Validate all IDs exactly once, columns/order/scale/polarity and finite values; resolve failures.
- [ ] Finish restart, responsive, export and live-provider acceptance checks.
- [x] Document reproducible setup/inference/export commands and known limitations.
- [ ] Package runnable prototype, final CSV, evaluation report and only the required event artifacts.
- [ ] Rehearse and submit through the authorized destination once supplied.

## Requested later extensions (not implemented)

- [ ] **Speaker-reference comparison:** accept a consented trusted reference, compare speaker embeddings, quality-gate inputs, test genuine/impostor/cloned/replayed pairs and report similarity or inconclusive status. It cannot identify an unknown person or prove identity from voice alone. Define reference retention/deletion before release.
- [ ] **Source-backed claim review:** obtain a correctable timestamped transcript, select factual claims, retrieve independent dated sources with citations and show supported/contradicted/insufficient evidence. Validate citation support; private facts, intent and subjective claims remain unresolved. This is not lie detection.
- [ ] **Integrated case report:** show synthesis, speaker comparison and claim review separately, each with its own evidence and status. Do not combine them into an overall authenticity probability.

## Immediate work order

1. Let the existing cluster job continue; inspect its actual outputs without submitting duplicates.
2. Finish Phase 2's independently actionable verification and reproduced defects while it runs.
3. Review live Grok only after the key is configured locally.
4. Review completed training/evaluation, then consider a tested model promotion.
5. Complete demo and sponsor submission gates. No prize or detector-performance result is guaranteed.
