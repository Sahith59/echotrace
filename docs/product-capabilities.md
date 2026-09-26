# What ECHOTRACE does

ECHOTRACE is a local workbench for someone investigating a suspicious recorded message. Its primary user is an audio analyst; a non-specialist can also upload and listen to a recording, but the model's number is not a guarantee of authenticity.

## The actual user journey

1. **Add a recording.** Choose your own permitted file or one of the optional 24 labeled diagnostic examples. WAV, MP3, M4A, FLAC, Ogg/Opus and other FFmpeg-decodable inputs are supported, with 50 MiB/120-second limits. Uploading does not train the model.
2. **Inspect synthesized-speech evidence.** The learned AASIST-L model evaluates complete overlapping coverage of the audio. The file score averages its window scores. FFmpeg/signal processing separately measure amplitude, clipping, quiet frames and spectral energy. Those measurements are not fake model explanations and do not determine the neural score.
3. **Listen to passages.** Playback and waveform/interval seeking help you inspect the actual recording. Highlighted windows are review regions, not proven splice boundaries.
4. **Compare changed conditions.** Produce a separately saved MP3 or noisy copy and rerun inference. See whether the score changes. The original remains intact; score stability does not establish correctness.
5. **Compare a trusted voice.** With explicit permission, upload a reference sample. A pinned Microsoft WavLM model computes two speaker embeddings and their cosine similarity. It cannot identify an unknown person or distinguish identity from a convincing clone/replay. Reference audio is temporary; comparison metadata is separately removable.
6. **Read and correct the words.** Faster-whisper runs locally, returns timestamped text, and retains immutable analyst corrections. A failed retry does not erase a successful transcript. Speech recognition may be wrong and should be reviewed.
7. **Review a claim against sources.** Select one factual statement. Record your own assessment and source URLs, clearly labeled analyst-written. Hosted Groq search is currently unavailable: the new provider’s source-provenance contract has not been validated. The app does not fabricate web citations. Correcting a transcript marks earlier linked claims stale. This is not lie detection.
8. **Explain the measurements.** Separate optional Groq interpretation summarizes supplied measurement evidence. It receives no recording, filename or transcript and cannot change the synthesis score. No API key means no generated AI explanation.
9. **Export a case.** The printable report and JSON include synthesis, speaker evidence, transcript versions and claim reviews separately. The app never combines these into an authenticity probability. Batch view exports completed scored analyses as an analyst CSV.
10. **Check the detector's measured limits.** The validation panel shows actual public-data experiments and explicit promotion decisions, including failed goals. A recording-condition selector exposes measured codec-specific false positives and class counts; it does not guess the codec of an uploaded file.

## What is implemented versus validated

| Capability | Implementation | Evidence / practical limit |
| --- | --- | --- |
| Upload, queue, retry, history | Implemented | Automated format/error/size tests and real local inference; browser file-chooser automation requires the extension file permission |
| Detector and signal measurements | Implemented | Real pinned baseline; independent experiments recorded; validated stronger promotion remains a separate gate |
| Playback, seeking, derivatives | Implemented | Exercised in the browser and integration tests |
| Speaker reference | Implemented | Real pinned-model smoke and live API comparison; no calibrated identity decision or population-level verification accuracy |
| Local transcript/corrections | Implemented | Real CPU model and browser transcript/correction journey; no claimed speech-recognition accuracy benchmark |
| Analyst claim review | Implemented | Browser save, stale-version warning, persistence and case export verified |
| Groq interpretation | Implemented and transport-tested | Live generation awaits a Groq key; hosted claim search remains unavailable; analyst source review works |
| Case JSON / printable HTML | Implemented | Escaping, boundaries, browser report contents and download event verified |
| Batch / official CSV adapter | Implemented | Exact-ID/finite-score/schema checks; official held-out data and schema not supplied |
| Model training and evaluation | Implemented and executed | GPU run ledgers and independent public-corpus metrics; public metrics are not sponsor accuracy |

## Training versus using the application

The web app runs **inference**: it uses saved model weights to analyze one recording. It does not learn from uploads. Offline cluster training is separate: labeled training files update weights, selection files choose settings, and a locked independent set checks the frozen result. A candidate is not installed just because a job completed or a checkpoint exists.

## What the product does not establish

It cannot prove who spoke, whether a person intended to deceive, recording origin, or general factual truth. Voice similarity requires a reference and remains vulnerable to cloning and replay. Claim review depends on sources, their dates and correct transcription. Noise or a failed/unsupported input must not be treated as proof of authenticity. Manipulation subtype is currently undetermined.

## Phase terms

- **Phase 0:** define the challenge and official input/output rules.
- **Phase 1:** create the real detector and evaluation/export foundation.
- **Phase 2:** make the investigation workbench and verify normal/failure journeys.
- **Phase 3A:** prepare independent labeled data.
- **Phase 3B:** train or run a bounded candidate experiment.
- **Phase 3C:** review independent results and promote only if justified.
- **Phase 4:** rehearse a truthful demo with successes, errors and known misses.
- **Phase 5:** package the runnable source and, once supplied, produce the exact official sponsor submission.
- **Extensions:** speaker comparison, transcription/source review and unified reporting, now implemented alongside the core workbench.

The authoritative live checklist is [plan.md](../plan.md). Deployment is outside this source-release iteration.

## Honest differentiation

The detector architecture is not our invention. Commercial tools already provide deepfake detection, voice authentication, and investigation interfaces: see [Resemble Detect](https://docs.resemble.ai/detect), [Pindrop Pulse](https://www.pindrop.com/pulse-for-meetings), and the [NII AntiDeepfake research models](https://github.com/nii-yamagishilab/AntiDeepfake). We have not established that any ECHOTRACE feature is unique in the market.

Our project-level contribution is a reproducible investigation workflow: original and stressed recordings stay linked, detector versions and measured failures remain visible, transcript corrections preserve history and invalidate dependent claim reviews, and exports keep synthesis, voice similarity and factual evidence separate. The analyst can inspect how and where a model fails instead of trusting one impressive percentage. The new codec-condition view makes that failure analysis directly inspectable.

That is useful engineering and a defensible hackathon demonstration. A stronger learned detector still needs independently measured performance; extra panels do not substitute for it. The NII candidate is being checked against its authors’ implementation and a frozen external benchmark before any serving decision. ASVspoof5 is part of NII training, so it cannot validate that candidate independently. Public benchmark results cannot guarantee sponsor ranking.
