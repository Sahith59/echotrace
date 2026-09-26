# Implemented build: one guided audio investigation

Status: approved and implemented through phases 3C, 4A, 4B and 4C on 2026-09-26. Phase 5 official sponsor submission remains pending. Existing work and historical results remain intact.

## Purpose

Help an analyst review a suspicious voice message, decide which evidence needs attention, and hand off a reproducible case. Primary user: audio-review/security analyst. Ordinary users can upload a recording, but the core design is an investigation workflow rather than a consumer truth detector.

Example: a recorded urgent instruction appears to come from a trusted colleague. The analyst asks whether there are signs of synthesis, whether the result is reliable for this recording, and what should be checked next. Identity and factual accuracy remain separate questions.

## Completed ordered build

1. **Phase 3C: primary detector migration — complete.** Pinned NII now provides shared API/CLI whole-file inference with an explicit <=30-second scope. Historical AASIST reports remain attributable; mixed-model stress comparisons and ambiguous exports are guarded. Parity, runtime and fail-closed quiet/corrupt/long/missing-model behavior are tested. No silent truncation. The public benchmark pass is not sponsor validation or a calibrated probability. The paired common-eligible AASIST result remains pending because the cluster jump host is unreachable.
2. **Phase 4A: guided case overview — complete.** The light workspace guides recording review, reliability checks and case evidence. Technical details use progressive disclosure. Analyst disposition and notes persist separately from model findings, with draft and version handling. A low score is never labeled verified authentic.
3. **Phase 4B: review queue and reliability checks — complete.** Queue search, score/date sort, status/review/date filters and unscored-case handling are implemented. Compression/noise comparisons retain model provenance, and mixed-model comparisons fail closed. Queue prioritization remains deterministic and explainable, not a validated risk model.
4. **Phase 4C: evidence-linked brief and handoff — complete.** Groq summarizes allowlisted current-detector evidence, with clickable measured references and versioned analyst findings. Exports include content hash, model version, transformations, AI provenance and analyst disposition. Hashes show byte identity, not legal chain-of-custody certification.
5. **Phase 5: evaluation and demonstration.** Publish counts, recall, false positives, threshold and limitations. Use genuine, synthetic and inconclusive cases, disclose inspected examples, and demonstrate batch CSV export. Freeze official output only after the sponsor supplies its contract. Verify browser, restart, report and failure journeys. Deployment remains separate.

## Detector strategy

Start from the strongest measured pretrained candidate; do not train from scratch merely to claim training. NII currently achieved 937/1000 synthetic detections and 24/1000 genuine false alarms at threshold0.5 on the frozen public benchmark (one quiet row retained in model-only results). Authors have evaluated this dataset before, so this is replication. Keep an independent, representative evaluation for any future fitting or calibration. Additional training/ensembling is conditional on new evidence of a useful improvement, not automatic. Preserve remaining aggregate five-hour GPU budget.

## Existing capabilities to reuse

Real audio decoding, NII primary inference, preserved legacy AASIST reports/comparisons, playback, history, noise/MP3 derivatives, six-column analyst CSV, local transcripts/corrections, consented voice-reference similarity, analyst source reviews, Groq interpretation, case JSON/HTML and benchmark evidence. Speaker similarity does not prove identity; transcription/source review does not detect lies. Hosted source retrieval is unavailable.

## Architecture

React workspace -> FastAPI case/job API -> local file validation and FFmpeg decoding -> pinned NII primary detector plus audio-quality measurements -> SQLite case/results and local originals -> evidence-linked review UI and exports. Optional local WavLM handles reference similarity, faster-whisper handles transcription; a separate Groq request receives allowlisted measured evidence, not recording bytes. Current Groq explanations cover primary evidence only.

## Differentiation and demonstration

Claim a reproducible investigation workflow, not a new detector architecture or a market-first invention. Demonstrate an analyst finding a suspicious case, seeing why a score needs caution, testing a transformation, inspecting optional corroborating evidence, and exporting a concise review. Measure analyst task completion time and comprehension before claiming productivity gains.

## Groq activation verification

Live browser generation succeeded on 2026-09-26. The initial unstructured edge `403` was fixed by setting an explicit user-agent; the working key did not need replacement. The structured response passed application validation, persisted, and left the detector score unchanged. No additional billable verification call is required.

## Verification and remaining gates

The completed local suite reports 288 backend tests, 51 frontend tests and a successful production build. The wheel was inspected and includes `primary_detector`, `analyst_review`, `nii_parity` and `validation_summary`; it excludes environment files, uploaded audio and model weights. Built-in public-sample multipart upload passed in the browser. A native unfamiliar-file chooser check remains manual.

Phase 5 still requires the sponsor's official data, metric, CSV contract, deadline and authorized submission destination. Source publication of the current commits is also pending. Do not claim NII superiority over AASIST until job `4504670` can be retrieved and evaluated on the common eligible denominator.
