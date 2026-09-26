# ECHOTRACE demonstration

## Explain the problem in one sentence

“A convincing voice message can be synthetic, a genuine voice can be replayed, and a real recording can contain false statements. ECHOTRACE keeps these questions separate and preserves the evidence behind each assessment.”

## Five-minute walkthrough

1. **Add a recording.** On the intake page use a local WAV/MP3/M4A, or expand the known-recording selector. The 24 optional public examples run through the same upload and real detector as custom files. Labels are reference information and never model input.
2. **Read the assessment.** Explain that the number is an uncalibrated synthesis score. Show a genuine and a synthetic clip; include a documented missed detection. A low score cannot prove a recording is genuine.
3. **Listen and compare.** Play the original, seek a scored interval, and create an MP3 or noisy derivative. Show the separate analysis and score difference. Stable results do not establish correctness.
4. **Compare a reference.** Upload a permitted trusted voice recording, explicitly consent, and run the local WavLM comparison. Explain the cosine scale, quality limits and deleted reference audio. A same-recording diagnostic should score near one, but does not validate identity recognition.
5. **Inspect the words.** Create a local transcript, play a timestamped passage and save a correction. Explain that automatic transcription can be wrong; previous versions are retained.
6. **Review a claim.** Enter one factual statement. If Grok is configured, consent to sending that claim only and inspect its cited sources. Otherwise record a clearly labeled analyst review. Private facts and subjective statements should remain uncheckable. Change a transcript and show the stale-review warning.
7. **Export the case.** Open the printable report or download case JSON. Synthesis, speaker, transcript and claims are separate, with hashes/model provenance and no overall authenticity probability. Batch view exports selected scored rows as an analyst CSV.
8. **Show actual validation.** Expand the detector validation panel. Explain the completed GPU experiments, their held-out results, and why a candidate that fails our goals is not promoted. Never present the inspected 24 examples as independent accuracy evidence.

## Failure demonstrations

Use only QA copies: empty or corrupt audio should fail clearly; silence should have no synthesis score; unsupported/overlong files should return useful errors; an unavailable Grok provider should be disabled rather than produce a canned AI report. Failed and scoreless rows cannot be exported as valid numerical predictions. Original recordings remain intact when derivatives are created.

## Offline fallback

The original detector, prepared voice model and prepared transcription model run locally. Retain a saved real analysis and its exported report before the demo. Clearly label saved evidence as a prior run; do not animate it as new computation. Grok web search requires connectivity and a configured key. Source repository setup does not include copyrighted recordings or model weights.

## Competition handoff

Official sponsor data, metric, CSV template, event deadline and submission destination are still required for final submission. The strict CLI adapter rejects missing/duplicate IDs, failed or nonfinite predictions, and unconfirmed example schemas. Deployment is a subsequent task.
