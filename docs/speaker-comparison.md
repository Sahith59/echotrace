# Local speaker-reference comparison

ECHOTRACE can compare a completed recording with a trusted voice reference on
the local machine. The feature returns an **uncalibrated cosine similarity**
between pretrained speaker embeddings. It does not identify a person, prove
identity, or authenticate a recording.

## API

`GET /api/speaker/status` reports dependency and weight readiness, the pinned
model provenance, and input limits. Missing dependencies or uncached weights
are explicit; there is no heuristic or fabricated fallback.

`POST /api/analyses/{job_id}/speaker-comparison` accepts multipart form fields:

- `file`: the trusted reference audio, at most 20 MiB and 120 seconds;
- `consent`: must be `true`, confirming permission to process the reference;
- `reference_label`: optional printable label of 1–80 characters.

Both recordings must decode to at least two seconds of finite, audible audio.
The response contains the cosine value, quality measurements, SHA-256 hashes,
model provenance, and limitations. It deliberately returns
`identity_verdict: null` and `calibration: "uncalibrated"`.

`GET /api/analyses/{job_id}/speaker-comparison` retrieves the persisted report.
`DELETE` on the same URL removes its metadata. The uploaded reference file is
deleted immediately after the comparison, including on validation or model
failure; only its label, SHA-256 hash, quality observations, and result remain.
No absolute filesystem paths or original reference filename are returned.

Speaker reports use their own `speaker_comparisons` SQLite table. They never
modify the synthesis detector's `synthetic_score` or imply that speaker
similarity is evidence of synthetic speech.

## Model and bounded inference

The implementation uses Microsoft's `microsoft/wavlm-base-plus-sv` through the
Transformers `WavLMForXVector` API. It pins repository revision
`1bfd64eca136543feb28c5ffaf05381c6af33121` and downloads only:

- `config.json`
- `preprocessor_config.json`
- `model.safetensors`

The 404,479,908-byte SafeTensors file must match SHA-256
`94c3defe08248d81c7b2bd0a058ea9985269cefed13076434669c47fade41182`.
Loading is local-only after download, forces `use_safetensors=True`, and disables
remote code. The repository's pickle checkpoint is never downloaded or loaded.

CPU inference is serialized. Recordings longer than ten seconds use four evenly
spaced ten-second windows at most (40 seconds of model input), and their
unit-normalized x-vectors are averaged. This keeps inference bounded while
sampling the entire recording span. The API rejects a concurrent comparison
with HTTP 409 rather than growing an unbounded model queue.

Primary references:

- [Microsoft WavLM speaker-verification model card](https://huggingface.co/microsoft/wavlm-base-plus-sv)
- [Pinned SafeTensors artifact and SHA-256](https://huggingface.co/microsoft/wavlm-base-plus-sv/blob/1bfd64eca136543feb28c5ffaf05381c6af33121/model.safetensors)
- [Transformers WavLM documentation](https://huggingface.co/docs/transformers/model_doc/wavlm)
- [Transformers model loading documentation](https://huggingface.co/docs/transformers/main_classes/model#transformers.PreTrainedModel.from_pretrained)

## Interpretation limits

Cosine similarity has no deployment-specific calibration here. Microphone,
codec, room, noise, health, emotion, language, replay, editing, and recording
length can alter it. Modern voice cloning can sound or embed similarly to the
reference. A high score is not proof of identity, and a low score is not proof
of different speakers. The result does not establish consent, origin, factual
truth, or whether either recording is synthetic.

## TDD evidence

The RED checkpoint is commit `4d88838`: `uv run pytest -q
tests/test_speaker.py` failed during collection because `echotrace.speaker` did
not exist. After implementation, the speaker test slice passes. It covers
consent, missing and incomplete jobs, invalid media, short and quiet audio,
oversized upload cleanup, local reference deletion, separate persistence,
synthetic-score preservation, status/error contracts, pinned downloads,
SafeTensors-only loading, and bounded long-audio windows.

The pretrained-model smoke check downloaded the pinned artifact, verified its
size and SHA-256, loaded it on CPU, and produced a finite 512-dimensional
embedding. Its self-cosine was `1.0000001` before clamping (ordinary floating
point rounding). This is a numerical plumbing check, not an accuracy,
calibration, or identity test.
