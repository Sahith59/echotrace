# Release verification — 2026-09-26

This report distinguishes real execution, automated test doubles and unverified external dependencies. It is updated as final release checks finish.

## Real local execution

- Original pinned AASIST-L scoring and FFmpeg decoding run in the application. Earlier integration checks verify identical saved JSON/CSV across restart and explicit interrupted-job recovery.
- Microsoft WavLM speaker model loaded from verified SafeTensors; real embeddings are finite. Comparing the exact same public diagnostic clip produced cosine 1.000000, correctly labeled uncalibrated with no identity verdict. This is a runtime diagnostic, not a speaker-verification benchmark.
- Faster-whisper `base`, CPU/int8, transcribed an actual 7.53-second public diagnostic recording. The browser showed timestamped text. A punctuation correction created version 2; a linked analyst claim became stale.
- The printable case report showed the actual synthesis score, speaker reference, both transcript versions, an explicitly uncheckable analyst review and the stale warning. The JSON download event was observed through Chrome; backend export contents are independently integration-tested.
- Production build on loopback port 4173 was used for stable browser checks. Desktop, 375×812 phone and 812×375 landscape views were inspected. Phone and landscape document widths matched their viewport widths. Temporary viewport override was reset.
- Previous browser checks covered playback, keyboard/waveform seeking, real MP3/noise derivatives, selected analyst CSV download, failed/scoreless selection rejection and mobile focus containment.

## Automated evidence

Backend suites cover media validation, uploads, queue/retry/persistence, real restart, model class polarity and reference parity, train/evaluation split separation, finite predictions, no-overwrite outputs, strict submission schemas, consent, speaker cleanup, transcript versions, claim citation failure, stale reviews, missing providers and escaped reports.

Security checks include host allowlisting, cross-site mutation rejection, parameterized SQLite operations, local-only model loading, SafeTensors hashes, no arbitrary URL fetching, no provider redirects, private reference-file permissions, explicit model setup, bounded record counts, and spreadsheet-safe analyst filenames. Tests involving hostile-shaped input run in isolated temporary test workspaces, not against user data.

At the last completed feature verification: **29 frontend tests passed**; production build passed. The explicitly instrumented PilotExamples/AIInterpretation/CaseReview components measured **95.04% statement, 80.71% branch, 96.15% function and 98.64% line coverage**. These percentages do not describe the entire application. Backend counts change with the final release tests and are recorded in the closing checklist.

`npm audit --omit=dev --audit-level=high` reported zero production dependency vulnerabilities. A heuristic scan of 264 historical Git blobs found no credential patterns or >10MB blobs; this is not a guarantee against every possible secret. `.env`, audio, databases, caches and weights are ignored and are not release artifacts.

## TDD evidence

New speaker and claim/transcription features retain agent RED/GREEN commits documented in their feature guides. Root integration checkpoints include case report `6717253` → `4fe726d`, source stance `35b9600` → `fb44beb`, local boundary `a974890` → `0419d25`, speaker readiness `7a9683c` → `9c9fbfc`, retry display `8f2391b` → `6881913`, and Opus delivery `3c41c7d` → `08c5a29`.

Two workflow corrections are retained transparently: the first CaseReview test invocation used the wrong working directory, then an excluded test glob; actual missing-module RED was captured in `0eb8d34` before implementation. The first model-validation implementation commit was prematurely named GREEN while an overly exact text assertion still failed; the corrected substring assertion and actual full passing run are recorded in `cefdd78`. These are not represented as successful first attempts.

## External and operational limits

- Chrome's automated file chooser lacks the extension's file-URL permission. Normal UI pilot uploads and API format/real model tests provide coverage, but the unfamiliar local-file chooser journey is not claimed complete. No browser security settings were changed.
- `XAI_API_KEY` is absent at the last checked provider status. Real Grok generation/search, provider billing and live citation quality remain unverified. Transport tests are test doubles, not live AI evidence.
- The sponsor's official dataset/schema/metric/deadline/destination are unavailable. No official CSV or competition submission is claimed.
- This is a loopback, single-user prototype. Multi-user authentication, deployment infrastructure, operational retention policy and independent forensic validation are not provided by this source release.
- Local model input/concurrency is bounded, but native CPU inference has no safe hard wall-clock cancellation. Audio decode and network requests have explicit timeouts.
- Passing software tests establishes workflow behavior, not deepfake detection accuracy. See the measured model reports and promotion decisions.
