# First prototype integration contract

2026-09-25. Implementation authorized after public-need and fit review. Target user: an analyst reviewing a suspicious voicemail or recorded message. Detection supports triage, not identity verification or an automated fraud verdict.

## Backend package boundary

Working directory: `challenges/hearsay-audio-authentication/backend`.

Shared module `echotrace.pipeline` exposes:

```python
analyze_file(path: Path, progress: Callable[[str], None] | None = None) -> dict
model_status() -> dict
```

Return JSON-safe values only:

```json
{
  "schema_version": "1.0",
  "input": {"filename": "example.wav", "sha256": "...", "duration_s": 8.5, "sample_rate": 16000, "channels": 1, "codec": "pcm_s16le"},
  "synthetic_score": 0.7,
  "score_kind": "uncalibrated",
  "model": {"name": "actual model", "version": "actual revision"},
  "manipulation_type": "undetermined",
  "waveform": [0.1, 0.2],
  "intervals": [{"start_s": 0, "end_s": 4, "score": 0.7}],
  "evidence": [{"id": "rms", "label": "RMS level", "value": -21.5, "unit": "dBFS", "detail": "Measured signal level", "kind": "quality"}],
  "limitations": ["Not calibrated on the sponsor dataset."],
  "runtime_s": 2.1
}
```

Example above specifies shape, not real output. `synthetic_score` may be null when no defensible detector assessment exists. Waveform is normalized absolute amplitude buckets from actual audio (up to 256); all interval scores 0–1. Raise a descriptive exception for undecodable files. Model unavailable may return actual DSP results and null score with an explicit limitation. Silent/non-speech inputs must not be called authentic. No fake demo scores.

## HTTP

`POST /api/analyses` multipart `file` -> job; `GET /api/analyses` -> array of jobs; `GET /api/analyses/{id}` -> job; `GET /api/analyses/{id}/audio` -> original file; `GET /api/analyses/{id}/report` -> JSON result. Job:

```json
{"id":"uuid", "filename":"example.wav", "status":"queued", "stage":"queued", "created_at":"ISO8601", "result":null, "error":null}
```

Status: queued/running/completed/failed. Completed jobs include the analysis result above. Poll every 1–2 seconds while pending. History is persisted in SQLite. Single serialized inference worker.

`GET /api/health` -> `{"status":"ok","model":{...}}`.

`POST /api/analyses/{id}/stress-tests` JSON `{"kind":"mp3"}` or `{"kind":"noise"}` -> new real derived job with `parent_id` and `transform` metadata. Input preserved. No uploaded audio leaves local server.

`POST /api/exports` JSON `{"ids":["uuid", ...]}` -> CSV `file_id,filename,synthetic_score` (0–1). Explicitly **analyst export, not official sponsor schema**. Reject pending, failed, missing-score, duplicate or unknown IDs. Official configurable CLI schema is independent adapter over same outputs.

## Limits and startup

Initially local-only server `127.0.0.1:8000`; Vite `127.0.0.1:5173` proxies `/api`. Upload max 50 MiB, duration max 120 seconds displayed in UI; batch CLI may expose a documented alternative full-coverage limit. Keep one scoring job at a time. Do not silently truncate inputs.

Frontend owns `frontend/`; pipeline developer owns `backend/echotrace/pipeline.py`, supporting model/audio modules and pipeline tests. Root owns API, CLI, persistence, package metadata and integration. Dataset tooling agent owns `backend/echotrace/evaluation.py` and its tests. Avoid modifying another owner's files without coordination.
