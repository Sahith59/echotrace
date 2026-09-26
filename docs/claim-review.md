# ECHOTRACE transcript and claim review

ECHOTRACE can create a timestamped transcript locally and keep analyst corrections as immutable versions. Factual claim review is a separate workflow. Neither a transcript nor an audio synthesis score establishes speaker identity, provenance, or whether spoken words are true.

## Local model setup

The server uses `faster-whisper` with the multilingual `base` model, CPU execution, and `int8` compute by default. Runtime requests never silently download a model. An operator explicitly prepares one bounded model in the same cache directory used by the server:

```bash
cd challenges/hearsay-audio-authentication/backend
uv run python -m echotrace.transcription --model base --cache-dir ../artifacts/workspace/models/faster-whisper
```

Automatic setup is limited to the Whisper `tiny`, `base`, and `small` families, including their English variants. Set `ECHOTRACE_WHISPER_MODEL` only when the prepared cache matches that model. `ECHOTRACE_WHISPER_CPU_THREADS` accepts 1–16 and defaults to 4. The status endpoint reports the model name and whether the cache appears ready without exposing an absolute local path.

`POST /api/analyses/{job_id}/transcript` runs local transcription synchronously. A single process-wide lock prevents concurrent model work. Input recordings are already limited to 120 seconds by the analysis pipeline; transcript output is additionally capped at 1,000 segments and 100,000 characters, and segment iteration stops as soon as the count limit is crossed. Model load and inference failures are saved as immutable error versions, returned as HTTP 503, and may be retried with another POST. After a failed retry, GET and case-report exports keep the latest successful transcript at the top level and expose the failed version separately as `latest_attempt: {status, version, error}`. There is no placeholder transcript.

`PUT /api/analyses/{job_id}/transcript` creates a new `analyst_corrected` version from `base_version`. It never overwrites the earlier version. A stale base version returns HTTP 409. Claims retain their original transcript version and dynamically report `stale_transcript: true` after a newer corrected transcript is saved.

Each recording is capped at 50 persisted transcript attempts or corrections and 200 claim records. The API returns HTTP 429 before additional local model work, provider calls, or persistence. This also bounds the complete history returned by the GET routes.

## Claim review paths

`POST /api/analyses/{job_id}/claims` accepts up to 2,000 characters plus an optional transcript version and timestamp span. It has three explicit paths:

- With no external-search consent and no analyst review, the claim is saved as `uncheckable` with method `manual_pending`.
- With `analyst_review`, the analyst supplies a verdict, rationale, and source annotations. These records use method `analyst`, provider `null`, and evidence provenance `analyst_supplied`. ECHOTRACE validates the URL form but does not fetch analyst URLs.
- With `external_search_consent: true`, only the claim text is sent to xAI. Audio, synthesis scores, the full transcript, and local paths are excluded. The fixed destination is `https://api.x.ai/v1/responses`; the request enables the provider's `web_search` tool and a strict JSON schema. The API key is read at use time from the existing environment configuration and is never returned or logged.

External review uses `supported`, `contradicted`, `insufficient_evidence`, or `uncheckable`. A supported or contradicted result must include source evidence with a matching stance. Every evidence URL must also occur in the provider's actual citation or annotation metadata. The response must additionally report at least one `usage.server_side_tool_usage_details.web_search_calls`, the counter documented for the xAI Responses API. Missing or zero search use forces `uncheckable` with no evidence. A URL citation alone does not prove an exact quotation, so quote text is retained only when it is present in provider-supplied excerpt metadata. Provider errors and invalid citations are stored as error claim records and returned as HTTP 503 for an explicit retry.

Source URLs must be HTTP(S), omit credentials, and use a public hostname. The backend never follows these URLs, preventing claim text or evidence from turning into arbitrary server-side requests. Claim and source text are treated as untrusted data in the provider prompt.

## API shapes

`GET /api/claims/status` reports provider availability, local transcription readiness, limits, and the external disclosure boundary. `GET /api/analyses/{job_id}/transcript` returns the latest transcript state plus every version. `GET /api/analyses/{job_id}/claims` returns every persisted claim review, newest first.

An analyst review request looks like:

```json
{
  "text": "The bridge opened in 2020.",
  "transcript_version": 1,
  "span": {"start_s": 14.2, "end_s": 16.8},
  "external_search_consent": false,
  "analyst_review": {
    "verdict": "supported",
    "rationale": "The city's completion report states the opening year.",
    "evidence": [{
      "url": "https://city.example/reports/bridge",
      "title": "Bridge completion report",
      "publisher": "City Works Department",
      "published_at": "2020-11-02",
      "quote": "The bridge opened to traffic in 2020.",
      "stance": "supports"
    }]
  }
}
```

## Validation evidence

The RED checkpoint was commit `56c2914`: the new tests failed during collection because the three implementation modules did not exist. The GREEN target is:

```bash
uv run pytest -q tests/test_transcription.py tests/test_claims.py tests/test_claims_api.py
```

The tests cover the real faster-whisper call contract through a model test double, timestamp and duration validation, cache/download policy, transcript versioning, stale claim associations, analyst provenance, provider unavailability, injection-shaped claim data, supported/contradicted abstention without evidence, hallucinated citations, quote suppression, and rejection of local or credential-bearing evidence URLs. No live xAI test ran because no key is configured; transport fixtures validate the exact provider request and response boundary without presenting fixture output as a live review.

GREEN evidence: the focused run passed 16 tests. The full backend run passed 212 tests. A focused `pytest-cov` run measured 80% combined statement coverage across `claims.py`, `claims_router.py`, and `transcription.py`. A real local smoke run loaded the prepared `base` model on CPU with `int8`, decoded generated speech, and returned two ordered timestamped segments; this verifies the installed runtime and cache without making the generated phrase a permanent test fixture.

Primary references used for the integration are the [xAI Web Search guide](https://docs.x.ai/developers/tools/web-search), [xAI citation contract](https://docs.x.ai/developers/tools/citations), [xAI structured output guide](https://docs.x.ai/developers/model-capabilities/text/structured-outputs), and the [faster-whisper project documentation](https://github.com/SYSTRAN/faster-whisper).
