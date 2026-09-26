# Grok-assisted interpretation

The user selected Grok/xAI. The repository root `.env` was created with an empty `XAI_API_KEY` and configurable `ECHOTRACE_LLM_MODEL=grok-4.7`. It is ignored by Git and has owner-only permissions. Do not put the key in frontend/VITE variables or commit it. The backend reads this file at request time; after saving a key, use **Check configuration** in the UI. Configured does not mean the key/model has been authenticated; authentication is checked by an actual generation request.

On a completed recording, **Generate interpretation** sends only allowlisted model scores, calibration status, scored window values and measured audio-quality/spectral numbers to the fixed xAI HTTPS endpoint. It sends no audio, original filename, content hash, transcript, reference label or user-supplied prose. Only the backend handles the key. Calls are on demand, serialized and capped at1600 output tokens/45seconds; a successful report is cached with evidence hash, prompt version, provider/model and generation time. Repeated clicks reuse it. These are token/request bounds, not a monetary spending limit.

The model writes a summary, findings citing evidence IDs, and suggested next steps. Pydantic checks the structured schema and references; unknown IDs/extra score fields/malformed outputs are rejected. This verifies structure and reference existence, not the semantic truth of generated prose. The UI keeps it labeled AI interpretation, shows measurement references, and warns that it can err. It never changes detector scores. Deterministic quality caveats remain separately labeled Measurement limitations. JSON exports include a generated interpretation when present.

No fixed prose is substituted and passed off as LLM output if configuration or generation fails. Missing credentials, authorization failures, limits and invalid output have explicit states. No tools, transcript analysis, web search, identity verification or fact checking are invoked by this feature.

## Verification

Backend transport tests use injected/fake HTTP responses: no paid requests or real provider text is implied by those tests. They cover sanitization, schema, evidence IDs, absent keys, null score, cache persistence and unchanged detector output, error redaction, and report export. Frontend tests cover generation, caching, failures, busy states, stale-job responses, configuration refresh and structured interval values. Live browser checked missing-key state and configuration refresh. An actual Grok generation remains pending the user's key.

Official API references reviewed:
- https://docs.x.ai/developers/model-capabilities/text/structured-outputs
- https://docs.x.ai/developers/models/grok-4.7
- https://docs.x.ai/developers/rest-api-reference/inference/chat-completions
