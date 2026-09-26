# What ECHOTRACE does

ECHOTRACE is a local workbench for someone investigating a suspicious recorded message. Its primary user is an audio analyst; a non-specialist can also upload and listen to a recording, but the model's number is not a guarantee of authenticity.

## The actual user journey

1. **Add a recording.** Choose your own permitted file or one of the optional 24 labeled diagnostic examples. WAV, MP3, M4A, FLAC, Ogg/Opus and other FFmpeg-decodable inputs are supported, with 50 MiB/120-second limits. Uploading does not train the model.
2. **Inspect synthesized-speech evidence.** The pinned NII wav2vec model scores the complete decoded waveform once, up to 30 seconds. Longer inputs fail explicitly rather than being truncated. FFmpeg/signal processing separately measure amplitude, clipping, quiet frames and spectral energy. Those measurements do not determine or explain the neural score.
3. **Review detector provenance.** New analyses use NII only. Saved legacy AASIST-L analyses can retain their historical NII research comparison, with both model identities and uncalibrated scores kept separate. The app prevents meaningless NII-on-NII comparison. A new paired AASIST comparison for NII-primary analyses remains pending. See [comparison workflow](detector-comparison.md).
4. **Listen to passages.** Playback and waveform/interval seeking help you inspect the actual recording. Highlighted windows are review regions, not proven splice boundaries.
5. **Compare changed conditions.** Produce a separately saved MP3 or noisy copy and rerun inference. See whether the score changes. The original remains intact; score stability does not establish correctness.
6. **Compare a trusted voice.** With explicit permission, upload a reference sample. A pinned Microsoft WavLM model computes two speaker embeddings and their cosine similarity. It cannot identify an unknown person or distinguish identity from a convincing clone/replay. Reference audio is temporary; comparison metadata is separately removable.
7. **Read and correct the words.** Faster-whisper runs locally, returns timestamped text, and retains immutable analyst corrections. A failed retry does not erase a successful transcript. Speech recognition may be wrong and should be reviewed.
8. **Review a claim against sources.** Select one factual statement. Record your own assessment and source URLs, clearly labeled analyst-written. The app does not fabricate web citations. Correcting a transcript marks earlier linked claims stale. This is not lie detection.
9. **Explain the measurements.** Separate optional Groq interpretation summarizes supplied measurement evidence. It receives no recording, filename or transcript and cannot change the synthesis score. A live browser generation succeeded with authenticated Groq transport; missing credentials still produce an explicit unavailable state.
10. **Export a case.** The printable report and JSON include synthesis, speaker evidence, transcript versions and claim reviews separately. The app never combines these into an authenticity probability. Batch view exports completed scored analyses as an analyst CSV.
11. **Follow the guided review.** A light three-step path moves from recording evidence to transcript/claims to report review. The queue supports filters for date, analyst status and version state; drafts and completed reviews stay distinct. The six-column analyst CSV preserves the selected analysis/model identity and linked stress-test context.
12. **Check the detector's measured limits.** The validation panel shows the NII serving benchmark separately from historical candidate experiments and failed goals. A recording-condition selector exposes measured codec-specific false positives and class counts; it does not guess the codec of an uploaded file.

## What is implemented versus validated

| Capability | Implementation | Evidence / practical limit |
| --- | --- | --- |
| Upload, queue, retry, history | Implemented | Automated format/error/size tests and real local inference; browser file-chooser automation requires the extension file permission |
| Detector and signal measurements | Implemented | Pinned NII primary, official-reference parity and frozen public benchmark replication; not sponsor validation |
| Legacy detector comparison | Preserved for historical analyses | Saved AASIST-L-primary/NII-research comparisons remain attributable; new NII-primary analyses do not run NII against itself, and a new paired AASIST path remains pending |
| Playback, seeking, derivatives | Implemented | Exercised in the browser and integration tests |
| Speaker reference | Implemented | Real pinned-model smoke and live API comparison; no calibrated identity decision or population-level verification accuracy |
| Local transcript/corrections | Implemented | Real CPU model and browser transcript/correction journey; no claimed speech-recognition accuracy benchmark |
| Analyst claim review | Implemented | Browser save, stale-version warning, persistence and case export verified |
| Groq interpretation | Implemented and live browser-verified | Authenticated generation `14e3396e7c554e1bb4c64036ac6310b7` succeeded; the initial unstructured `403` was resolved by setting the required user agent; no further paid calls were made |
| Case JSON / printable HTML | Implemented | Escaping, boundaries, browser report contents and download event verified |
| Guided queue / analyst CSV | Implemented and browser-verified | Three-step workflow, date/status/version filters, drafts, review state, matched model/stress context and six-column export; official sponsor schema remains unknown |
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

That is useful engineering and a defensible hackathon demonstration. The NII primary detector has reference parity and measured results on a frozen 2,000-file public benchmark: 93.7% recall, 2.4% false positives, AUROC 0.9925 at threshold 0.5. This replicates a dataset already evaluated by its authors; it is not a new blind test. NII was selected for prototype serving on those scoped absolute gates, without claiming that the older training-specific promotion contract passed. ASVspoof5 is part of NII training, so it cannot validate this checkpoint independently. Public benchmark results cannot guarantee sponsor ranking.

The current light-workspace browser evidence is recorded in [light workspace verification](light-workspace-verification.md). Older phase and experiment entries remain historical milestones rather than descriptions of the current serving model.
