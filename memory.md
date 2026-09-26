# ECHOTRACE persistent memory

Last updated: 2026-09-25. State: first working local prototype implemented; sponsor-data evaluation and official submission still pending.

## User intent and authorization

- Build a compelling, polished submission for **NSA Challenge 1: HEARSAY**, named ECHOTRACE.
- Concept accepted: forensic workbench with audio upload, likelihood score, suspicious-interval inspection, multiple analysis methods, optional robustness comparison and CSV export.
- Latest request: validate public urgency and NSA #1 fit, then build the application with multiple GPT-6 Sol agents at medium reasoning. Three such agents reviewed urgency, model feasibility and product fit, then implemented independent components. Main-session model switching was not available; no claim that it was changed.
- Planning and bounded validation completed; implementation authorized on 2026-09-25. No budget, paid infrastructure, external publication or submission destination authorized.

## Verified context

- Repository: `/Users/sahithreddythummala/HackGT13-sponsor-projects/nsa`.
- Initial content was only challenge documentation. Now a React frontend, Python backend, tests, lockfiles and local ignored artifacts exist under HEARSAY. No sponsor dataset has been provided.
- Git had no commits and existing files were untracked. Do not delete or overwrite user-owned work as cleanup.
- No applicable AGENTS.md found in the inspected workspace/ancestor locations.
- User attachment: `/Users/sahithreddythummala/.codex/attachments/5ee49d2d-4dcf-445d-bc53-ef95560a578a/Pasted text.txt`. Full sponsor excerpt read; local NSA #1 brief matches.
- Notion event packet previously failed retrieval. Sponsor excerpt does not establish all event-wide rules.
- Confirmed: WAV/MP3/M4A-style input, autonomous multiple forensic techniques, 0–100% synthesis-likelihood score, labeled training and held-out test data to be supplied, CSV predictions required. Manipulation type explicitly optional in detailed wording.
- Cloud services, open-source LLMs, speech models and signal-processing toolkits allowed by the challenge excerpt. Other sponsors' requirements do not apply automatically.

## Decisions

| Decision | Reason |
| --- | --- |
| Scope only NSA #1 | User's explicit selection |
| Baseline and CSV before elaborate demo | Prediction evaluation is a confirmed deliverable |
| Shared CLI/API scoring | Avoid evaluation/demo divergence |
| Pretrained detector plus DSP first | Feasible multi-technique pipeline without training from scratch |
| Ensemble only if validated | Extra models can worsen accuracy or latency |
| Show calibration and limitations honestly | Raw model confidence is not calibrated likelihood |
| Timeline means window assessment | Precise splice localization requires separate evidence |
| Local-first single-worker prototype | Compute, team, time and budget are unknown |
| Stress testing is optional comparison | Distinctive demo without claiming universal robustness |

## Open questions

Dataset link, official metric, class definitions, CSV schema/scale/order, evaluation rules, deadline/destination, permitted external data, team size, available time, GPU and budget. Asked user asynchronously during planning; no answer recorded yet. Do not silently convert these to facts.

## Current implementation and validation

- App README: `challenges/hearsay-audio-authentication/README.md` has startup, tests, CLI, limits and remaining work.
- `docs/problem-validation.md`: primary FBI/FTC public evidence; broad fraud totals explicitly not voice-cloning totals.
- `docs/product-validation.md`: analyst uploaded-recording triage is a stronger scope fit than consumer scam verdicts or live-call integration. This is a design judgment, not user research or proof of being the best possible submission.
- `docs/model-feasibility.md`: pinned official AASIST-L revision/hash, license, preprocessing, real CPU inference and observed limitations.
- `docs/build-contract.md`: integration API/result contract. Original plan and prior planning reviews preserved.
- Backend: FastAPI, SQLite durable jobs, one inference worker, upload, status, history, playback, JSON report, retry, MP3/noise derivatives and analyst CSV export.
- Pipeline: FFmpeg decode, 16 kHz mono analysis, actual AASIST-L CPU inference, full-coverage windows, six measured quality/spectral/temporal observations. DSP does not determine synthesis score. Results retain hashes/config/version and unrounded scores/logits.
- Frontend: React/TypeScript/Vite, dark analyst workbench, single/multi upload, history, actual status, waveform seeking, scored intervals, evidence/limitations, comparisons and analyst CSV selection.
- CLI: `setup-model`, `score`, `batch`, `audit`, `evaluate`, `export`. Shared scoring with API; grouped content/metadata split, evaluation metrics and strict configurable CSV preflight. Example schema is not official. No calibration/training adapter implemented yet.
- Current limits: 50 MiB and 120 s per file for both API and CLI; one worker, 100-job pending limit. No silent truncation. Long sponsor clips require a reviewed extension.
- Fixes from review: small balanced group-split edge case, out-of-range batch score rejection, retry lock recheck, and SQL pending-count query avoiding per-job historical scans.

### Actual checks on 2026-09-25

- `uv run pytest -q` in backend: **18 passed**, 6.31 s. One upstream Starlette/httpx deprecation warning; no failing tests.
- `npm run build` in frontend: **passed** TypeScript and production build. Agent reported npm install audit found zero vulnerabilities.
- Real inference: WAV/MP3/M4A decode and AASIST-L checkpoint forward pass; explicit spoof index0 polarity math; silent input has null score.
- macOS `say` synthetic speech fixture: API/CLI score and interval parity passed. This is software integration evidence, not classification accuracy.
- Live API original + MP3 64 kbps + noise 20 dB SNR(seed42): all completed; analyst CSV exported all three IDs. Fixture named `KNOWN-SYNTHETIC-macos-say.wav` in local history.
- Browser: Chrome rendered the empty application with connected local backend and working intake controls visible. Full interactive/mobile visual QA is not complete; user was also using Chrome, so subsequent checks used API and build validation.

### Critical model limitation

A known macOS-generated TTS clip received a low synthetic score: about 0.0299 WAV, 0.0292 MP3 and 0.0355 M4A in independent CLI smoke runs. The live stress-test variants scored about 0.0226 (MP3 64k) and 0.0460 (noise). Different MP3 settings produce different derivatives. Do not demonstrate these as correct detections or claim a measured accuracy from them. This is concrete evidence that the baseline needs dataset-relevant evaluation and likely adaptation/replacement. UI says uncalibrated; low scores do not authenticate anyone. No standalone speech-presence model exists, so non-speech inputs also require caution.

### Running local processes

- Backend: `uv run uvicorn echotrace.api:app --host 127.0.0.1 --port 8000` (session 56341 at handoff; process IDs may change).
- Frontend: `npm run dev -- --port 5173` / agent Vite server at http://127.0.0.1:5173 (session 42255 at handoff).
- Model weights: ignored `backend/artifacts/AASIST-L.pth`; explicit `echotrace setup-model` restores them.
- Job/audio storage: ignored `artifacts/workspace/`. Generated synthetic fixtures are ignored under backend/artifacts.

## Next action

Obtain sponsor training/test data, metric and sample submission plus time/compute constraints. Audit grouping/labels, benchmark the existing baseline and stronger candidates, then calibrate on independent development data if feasible. Preserve the working app/CLI while improving model quality. Confirm and extend the submission adapter against actual sponsor schema. Complete interactive/mobile QA and a judge-ready demo using transparently sourced recordings. Do not assume competition readiness from passing integration tests.

## Update protocol

### UI refinement — 2026-09-25

- Applied the user's frontend-design, framer-motion and ui-ux-pro-max skills and two pasted component references. A GPT-6 Sol medium agent implemented and refined the scoped signal-morph component; root integrated the app-wide glass system.
- Added Motion, Tailwind v4/Vite, shadcn-compatible configuration, aliases, cn utility and local Outfit/IBM Plex fonts. Added reusable glass surfaces/buttons and native-scroll/manual signal morphing. Decorative specimens are explicitly illustrative; no fabricated analysis output.
- Revised intake, navigation, header, investigation/evidence/batch surfaces with an ice blue/navy palette. Preserved API behavior and scientific caveats. Added reduced motion, focus/skip navigation, live processing status and Escape/mobile visibility handling.
- `npm run build` passed after integration. Chrome accessibility tree confirms the loaded new intake, three arrangement buttons, file picker, existing history and engine online. Screenshot capture failed with ScreenCaptureKit -3811 and a subsequent click was blocked by concurrent user Chrome changes. Full visual/mobile and click-through QA remains pending.
- Restarted frontend at http://127.0.0.1:5173 (session 94043). Backend health on port8000 reports the local CPU model available. Previous frontend session had ended.
- Design decisions and test boundaries: `docs/design-system.md`. Phase 2 UI refinement is implemented; sponsor-dependent evaluation, calibration and official CSV gates remain incomplete. Baseline's known synthetic failure remains unresolved.


Append concise dated outcomes after each significant work session. Include changed files, actual commands/checks/results, decisions, blockers and next action. Keep unverified assumptions labeled and phase checkboxes aligned with real evidence. Never store secrets here.

### Graphite revision after user feedback — 2026-09-25

- Removed the decorative Circle/Align/Scatter hero from the application and removed the Engine online header badge. Replaced intake with upload, concrete review capabilities and a real clickable recent-recordings list.
- Changed all active original/refinement CSS colors to neutral greys and revised glass highlights/shadows. Added locally hosted Public Sans for headings and interface text, retaining mono only for technical data. All existing investigation, comparison and batch views share the revised theme.
- UI UX skill design-system and UX searches completed; user-directed monochrome palette overrides generated blue/light recommendations. Sequential-thinking SKILL.md read, but referenced tool was not available; phased fallback recorded in plan.md.
- TypeScript/Vite production build passed. Desktop Chrome screenshots now work: inspected intake and actual result page; clicked recent recording and confirmed real score/evidence navigation. Full small-phone, landscape, reduced-motion and export-interaction QA remain pending.
- Added planned speaker comparison and source-backed claim review phases with separate evidence gates. Neither is implemented or a guaranteed identity/truth verdict. Core sponsor-data evaluation remains next priority; known baseline failure remains unresolved.

### Phase 1 continuation — public-data pilot and TDD

User has no sponsor data. Authorized public dataset search and cluster use with space left for others; actual scheduler, GPU inventory/allocation and access remain unknown. No cluster jobs submitted; plan single-GPU pilot before scaling under university policy.

Implemented metadata-preserving, transitively grouped speaker/source validation split and manifest-order-independent seeded membership. Added CLI input/output/sidecar alias guards (direct/symlink/hardlink). TDD checkpoints on master recorded in docs/tdd/phase1-evaluation-readiness.md. Existing repo began untracked, so initial GREEN commits include prior module content; no unrelated challenge files committed. Full backend:37passed, one upstream warning,88% statement coverage including vendor (~84.6% first-party). No browser changes this iteration.

Researched primary-source public datasets and downloaded only24 files (~5.27MB) from pinned MLAAD-tiny revision9143e5ea709575ebab6bec52840a1043aada7bb1.12genuine/12synthetic English, four selected generators. All scored with unchanged CPU AASIST-L. At fixed0.5:TN9 FP3 FN6 TP6, ROC AUC0.7431. Diagnostic only: small selection, no independent speaker/source split or overlap exclusion. No training/calibration. Reports+public provenance in challenges/hearsay-audio-authentication/reports/public-pilot; audio ignored under backend/artifacts/public-pilot. Licenses saved locally; no audio published.

Next: compare stronger detector on a documented independent public development split before training; obtain cluster facts; preserve sponsor-specific gates. Pending hardening: library export collision handling, malformed schema type checks, atomic output, richer batch provenance. Web verification checklist:docs/phase-verification.md. Phase1 NOT closed; public pilot is measured baseline evidence only.

### Large-dataset preparation and second candidate

User requested larger internet dataset and clarification about upload. Explained dataset clip for known-label detector evaluation vs custom clip for workflow; neither upload trains model. Research in docs/large-dataset-review.md recommends official ASVspoof5 train/dev (~57.56GB archives); full release142.3GB. User asked async for local/external/cluster storage path and cluster docs; no reply yet. No large audio download or node allocation.

Downloaded/checksummed only20.67MB official ASVspoof5 protocol archive plus README/license. New echotrace/asvspoof5.py converts all official partitions, with nine tests. Actual prepared counts:train182357 (genuine18797/spoof163560), dev140950(31334/109616), eval680774(138688/542086). Manifests ignored under backend/artifacts/asvspoof5; summaries in reports/asvspoof5-preparation. Exact download inventory in configs/asvspoof5-downloads.json. Metadata counts are not audio availability/performance.

New isolated echotrace/candidate.py full AASIST from same pinned official upstream; weights/config hashes pinned. CLI explicit setup, fresh output, maximum256files, CPU. Web remains AASIST-L. Candidate real24file diagnostic:TN12 FP0 FN8 TP4; AUC0.756944 vs baseline0.743056; recall worsened4/12vs6/12 so no promotion. No training/calibration. Reports/candidate-pilot retains metrics/predictions/provenance. Comparison intended for labeled speech, no web quiet-audio gate. Original run details predate later explanatory scope field; metrics/code inference unchanged.

Root suite54passed,88%statement coverage (vendor included), importer82%, candidate85%; agent later focused8candidate tests85%. TDD evidence and checkpoint timing deviation recorded in docs/tdd/phase1-evaluation-readiness.md. Next acquire installed audio at approved storage destination, audit corpus and set representative development evaluation; choose further architecture/adaptation from measured failures rather than promote based on tiny pilot.

### Latest scope: fixed 24-file demo (supersedes large-data next step)

User reversed large-data choice. ASVspoof5 audio acquisition and cluster work are paused. Two GPT-6 Sol medium agents implemented local example API and frontend selector. Added pinned catalog and hash-verified audio routes, no arbitrary paths; Try a known recording sends actual bytes to existing upload/inference. No training, calibration, threshold tuning or model replacement.

Verified 61 backend tests, 7 UI tests (sample component 93.84% statements / 82.6% branches), production build. Live Chrome: genuine wives_and_daughters_17_f000049 rounded 0%, synthetic jane_eyre_21_f000371 rounded 9% (a miss), playback/seek works; MP3 derivative completed at rounded 8%. Selected those two original results and exercised CSV export; downloaded artifact contents not independently verified this turn. Corrected ALL FILES total to include derived analyses, consistent with table/status counters.

Backend RED checkpoint4ef9c4d preceded implementation; frontend tests came after implementation, a documented TDD deviation. No general accuracy claim. Next finish mobile/restart/export-artifact QA and demo rehearsal; sponsor evaluation remains open.

### Detector usefulness review and training reopened

User challenged low scores and permitted five-hour cluster training. Audited model/pipeline/audio/UI and saved scores with two GPT-6 Sol medium reviewers. Confirmed real class0 spoof softmax, mean4.04s windows, UI percentage rounding; deterministic interpretation text and quality rules, no LLM. All24 are not below10%: only2/12synthetic are; scores3.91–99.75%. Baseline catches6/12synthetic and flags3/12genuine at0.5. Root cause for individual failures not proven; domain transfer and aggregation need audit. Official upstream class map verified.

Created docs/detector-improvement-plan.md and updated plan/claude priorities. Training deferral superseded by bounded one-GPU five-hour adaptation proposal;24clips remain demo. No trainer exists yet; ASVspoof5 audio absent. Next implement reference/parity and per-file error audit, then runner/data preparation. Proposed acceptance80%recall at<=5%FPR plus10pp improvement on locked data, not predicted performance or sponsor criteria. Asked cluster documentation/GPU/scheduler/storage via async; waiting. No model code or weights changed, no GPU job/download launched.

User supplied TReNDs Summer2026 PDF; read all65pages by text extraction. Slurm confirmed, GPU queues and A100 typed GRES documented; propose1A100/1node/4CPU/32GB hostRAM/5h. Personal /data/users# path and authorized Slurmaccount/partition remain unknown. No login-node compute or dataset duplication; guide contains #SGATCH typo and inconsistent shortflags, so use corrected explicit directives. Cluster details appended to detector-improvement-plan.md. No remote connection or allocation attempted.

### Implemented detector preparation and Grok interpretation

User explicitly requested LLM-assisted notes and selected Grok, asking for.env. Created root.env (emptykey, owneronly, ignored), .env.example; xAI structured ChatCompletions adapter defaultgrok-4.7 perofficialdocs, allowlisted numerical evidence only, noaudio/names/transcripts. On-demand API/cache in existingSQLite result, originalscore unchanged, provenance hash/prompt/model/time; unknownrefs/schemafailclosed; no fakegeneratedfallback. UI new AIinterpretation, Checkconfiguration, loading/error/caching and windowrefs; fixed notes renamedMeasurementlimitations. Key stillnotconfigured at livebrowser check, realLLM generation pending. No billablecall attempted.

Three GPT6Sol medium agents added parity/erroraudit, experimentaltrainingrunner, interpretationUI. Backend102pass; frontend15pass/buildpass. Selectedmodulecoverage95%interpretation92%diagnostics80%trainingrounded; componentcoverage92.62%statements. ActualAASIST CPUoptimization smoke ongeneratedsignals passed, notaccuracy. Auditall24 confusionunchanged. Trainingrunner bounded3h optimizationinside5hplan, strictmanifest/demo exclusions, explicitlabelmapping, finitegrad/loss, freshoutput bestvalidationcheckpoint. Noresume/earlystopping/fullfileacceptance runner yet. NoGPUtraining/datasetdownload/promotedweights.

Next: useraddskey, liveGrok verification; separatedata+clusterallocation/paths, lockedselection/acceptance manifests, fullfilecandidatecheckpointscorer, Slurmpackage then5h training. Latest priority detectionquality overUIdecoration. docs/ai-interpretation.md and docs/tdd/detector-and-ai-review.md preserve tests/limitations.
