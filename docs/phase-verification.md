# ECHOTRACE phase verification

Status: 2026-09-25. Current work is Phase 3A: training/evaluation software is verified, but real-data and cluster staging remain open. The local prototype is usable; sponsor training/test data, official metric, and submission template are absent. Check a box only after **you** observe the behavior or review the named evidence. A working page is not evidence of detector accuracy. Start the app using the [challenge README](../challenges/hearsay-audio-authentication/README.md), then open <http://127.0.0.1:5173>. The local app accepts up to 50 MiB and 120 seconds per file.

## Phase 0 — Requirements and feasibility

- [ ] Confirm the official dataset, metric, CSV template, deadline, event rules, and permitted compute/data use with the sponsor. These are still missing here.
- [x] The challenge requirements and internal contracts are documented in [plan.md](../plan.md) and [build-contract.md](build-contract.md). This means planning is recorded, not that official requirements are complete.
- [ ] Record the actual time and compute available before committing to training or cluster use.

## Phase 1 — Baseline and submission path

- [ ] In the web intake, upload one known, permitted WAV, MP3, and M4A recording. Open each result and confirm it shows actual processing, a model/version, measured evidence, and either an **uncalibrated** score or a clear reason no score is available. The repo has passed local format and model integration checks; repeat this on your own files.
- [ ] Try a quiet or invalid file and confirm a null assessment or a visible failure, rather than an invented score. Use only files you may process.
- [ ] While sponsor data are absent, run a small, labeled public-data pilot using [the public-data plan](public-data-plan.md): freeze the sample and unchanged baseline first, record failures and public-corpus metrics, and keep its claims separate from HEARSAY performance.
- [ ] After sponsor data arrives, audit labels and related recordings, make a grouped validation split, and evaluate the current baseline **before training or tuning**. Save metrics, sample counts, false-positive/false-negative examples, score direction, and runtime. This is the next core gate: a known synthetic local TTS clip received a low score, so the current baseline has no established challenge accuracy.
- [ ] Run the shared batch scorer on sponsor data, resolve failed IDs, and adapt the CSV export to the **official** template. The web “Export selected CSV” currently produces an analyst CSV; it is not a verified sponsor submission.

## Phase 2 — Product vertical slice

- [ ] Upload an unfamiliar supported recording in the web app; watch queued/running/completed status, then play it and seek from a scored interval. Inspect evidence, limitations, and technical provenance. These features are implemented; this is the user click-through check.
- [ ] Download its JSON report; return to Recent recordings or Batch & export and reopen the persisted result. Restart the local app and check that completed history remains and interrupted work is marked failed/retryable.
- [ ] Select multiple completed, scored rows in Batch & export and download the analyst CSV. Check that pending, failed, or scoreless rows cannot be selected. Browser and build checks exist, but full interactive/mobile QA remains open.

## Phase 3 — Measured performance

- [x] Phase 3A software: three-way data preparation, whole-file checkpoint scoring, failure/coverage checks, frozen-threshold comparison and bounded Slurm package have passed local verification. These checks do not measure speech-detection quality.
- [ ] Phase 3A data/cluster: working `ssh trends`, permitted personal data storage, verified allocation/partition, installed independent audio, frozen manifests and measured GPU throughput. User supplied account `trends517s113`; never use the old course account.
- [ ] Phase 3B: complete one five-hour, one-node, one-GPU adaptation/evaluation job and retain the actual job ID, checkpoint, scores and report.
- [ ] Phase 3C: review acceptance counts, recall, false positives, confidence intervals, slices and serving performance. An eligible report requires review; no automatic web-model replacement.
- [ ] On the grouped sponsor validation set, compare the baseline with any second detector or adaptation. Record the official metric and relevant error/runtime breakdowns; keep a change only when its measured benefit warrants it.
- [ ] If the data support it, fit calibration on separate development data and evaluate it on untouched validation data. Until then, the web label must remain “Uncalibrated model score.” No calibration, ensemble comparison, or sponsor-data performance report is complete.

## Phase 4 — Distinctive demonstration

- [ ] On a completed result, choose **MP3 compression** or **Add noise**. Confirm the derivative gets a separate real analysis, playable audio, and a score change in points. The feature is implemented; a stable score does not prove robustness or authenticity.
- [ ] Prepare licensed or consented genuine and synthetic demo clips with provenance. These are not yet in the project. Speaker comparison and factual-claim review are future extensions with separate evidence gates; neither is part of the current score.

## Phase 5 — Freeze and handoff

- [ ] Once the sponsor format is known, freeze the model/configuration and official CSV adapter. Run held-out test inference without tuning on test labels, then verify every expected ID once, required columns/order/scale, finite values, and resolved failures.
- [ ] Rehearse the complete web flow, app restart, batch export, and a clearly labeled saved real run. Check the actual submission channel and deadline before delivery. The README contains setup and CLI instructions, but the official CSV and final submission are not ready.

## Cluster information to collect, if cluster evaluation is useful

Record the following operational facts with the team or cluster administrator; do not paste passwords, tokens, private keys, or sponsor audio into this document. No cluster, GPU allocation, scheduler, or access method has been confirmed, so this is an information checklist rather than a command recipe.

- [ ] Approved access route and account/allocation owner; whether sponsor audio and model weights may be placed there.
- [ ] Cluster operating system, CPU/GPU models and counts, GPU memory, RAM, and per-job time limits.
- [ ] Scheduler name and site documentation, available queues/partitions, fair-use limits, and whether interactive jobs are allowed.
- [ ] Python/container environment options, FFmpeg availability, outbound download policy, and supported storage/scratch locations with quotas and retention rules.
- [ ] Data-transfer method, permitted data location, encryption/cleanup requirements, and whether results may leave the cluster.
- [ ] Remaining allocation/budget, queue wait expectations, and a contact for access or job failures.

Use the existing CPU baseline to establish sponsor-data metrics first. Cluster resources matter only if those measurements show that a larger comparison or training run is warranted.

## Latest handoff — 24-recording guided demo

The examples now exist locally (12 genuine, 12 synthetic); this supersedes the earlier Phase 4 note saying demo clips are absent.

1. Open Investigations → **Try a known recording**. Choose one genuine and one synthetic sample; preview each and press **Analyze this sample**. No manual dataset upload is needed.
2. Check that each creates a completed result with an uncalibrated score. A known label and model score may disagree; that is a detector error, not a reason to change the label.
3. Play a result, click an interval to seek, and run **MP3 compression**. Confirm a separate derived result appears.
4. In **Batch & export**, select the two original sample results and export CSV. Check it contains exactly those IDs and scores in 0–1 units.
5. Optional: upload your own permitted recording to test unfamiliar input. Uploading runs inference; it does not train the model, prove identity, or verify factual truth.

Agent verified desktop selection, real inference, playback/seek and compression. Mobile/responsive and restart/recovery checks remain next. Training and large downloads are paused; no cluster needed for this demo.

## Grok interpretation and training preparation handoff

1. Add your xAI key to the root.env `XAI_API_KEY`; do not put it in frontend settings.
2. Open a completed recording → AI interpretation → Check configuration → Generate interpretation. This sends measured findings only to xAI. Verify each cited measurement against the displayed value, and that the synthesis score stays unchanged.
3. Reopen the result and download JSON: the same generated brief should persist with model, prompt version, evidence hash and generation time.
4. If a key/model/request fails, expect a clear error rather than fabricated generated notes.
5. Review the saved24file error report. Trainingrunner availability is not evidence of improved accuracy; the five-hour experiment has not run.

## Latest handoff — Phase 3A software

The work in this milestone is behind the interface. Existing recording scores and the web model have not changed; there is no new accuracy claim to verify in the browser yet. The next web-visible detector milestone comes after Phase 3C accepts a trained candidate.

For current app verification, choose a known recording, analyze it, play a scored interval, and export JSON. Once your xAI key is configured, generate an AI interpretation and confirm its cited findings match the measured evidence while the original score stays unchanged. An upload performs inference only, whether it comes from the dataset or is your own permitted recording.

The current user-dependent action is restoring cluster access and obtaining permitted personal data storage. The last SSH attempt timed out before login. A 100 GB home quota is not permission to stage the large corpus there. After connectivity is available, verify account/partition/storage before following [cluster handoff](cluster-handoff.md). Review [checkpoint evaluation](checkpoint-evaluation.md) for the exact acceptance behavior.
