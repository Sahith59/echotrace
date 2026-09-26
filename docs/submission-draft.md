# ECHOTRACE — submission copy draft

This is reviewable copy, not a submitted entry. Final model results, the official CSV, a recorded demo, judge-accessible code and eligibility/timing checks must be attached before submission. See [organizer requirements](organizer-requirements.md).

## One-line description

Investigate a suspicious voice recording with synthesis assessment, reference-voice comparison, transcript review and separately sourced claim evidence.

## Inspiration

A convincing voice can be synthesized, a genuine voice can be replayed, and a real recording can contain an unsupported statement. These are different questions. We wanted a workbench that makes the distinctions visible and preserves what the analyst actually examined.

## What it does

ECHOTRACE analyzes uploaded audio with a real speech detector and independent signal measurements. An analyst can listen to scored passages, test a compressed or noisy derivative, compare a permitted trusted voice reference, transcribe locally and correct the text, review a selected claim against sources, and export the complete investigation. Errors and inconclusive results remain visible.

Optional Grok interpretation explains measured findings. Optional consented Grok web search reviews a selected claim. Neither changes the detector score. Speaker similarity is not an identity verdict, and claim review is not lie detection.

## How it was built

React, TypeScript and Vite provide the interface. FastAPI and SQLite preserve local analysis jobs and results. FFmpeg decodes media; PyTorch runs pretrained speech models. The project implements validation, window aggregation, queue/retry behavior, playback and comparisons, explicit evidence boundaries, transcript-version linking, source review and reproducible exports. Offline cluster scripts preserve separate training, selection and acceptance data and record measured promotion decisions.

This is not a newly pretrained foundation model. AASIST-L supplies the original synthesis detector, Microsoft WavLM supplies speaker embeddings, and faster-whisper supplies transcription. Public ASVspoof 5 data supports the bounded detector experiments; the 24 MLAAD-tiny clips are diagnostic examples, not an independent benchmark. Exact model revisions, licenses and source credits are in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

Development used AI coding assistance for planning, implementation, tests and review. Pretrained components, generated assistance and the project's integration/adaptation work should be disclosed separately in the final entry.

## Challenges and evidence

The initial detector missed synthetic recordings. We preserved those failures, built independent evaluation, ran bounded GPU experiments and kept failed candidates out of the live pipeline. The final release's validation panel and checked-in reports are the source of measured results; passing software tests alone does not establish detection accuracy. A CPU preparation failure also led to fail-fast decoder checks and recoverable download staging.

## Demonstration

Show one genuine example and one synthetic example, including a missed detection. Listen to a scored passage, compare an altered copy, generate and correct a local transcript, link a passage to a claim review, and export a report. Present a real reference comparison with its limitations. Show live Grok output only if configured and verified; otherwise say it is unavailable. Follow the [demo guide](demo-guide.md).

## Remaining competition inputs

The sponsor's data and prediction schema must drive the final CSV. Do not submit the example schema as official, claim an unmeasured accuracy, conceal unsuccessful experiments, or represent saved output as live computation. The current iteration ends with a private source repository; deployment and official submission are subsequent authorized steps.
