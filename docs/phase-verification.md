# ECHOTRACE phase verification

Updated 2026-09-26. Current execution: **Phase 3B is running**. Phase 3A passed for the bounded public-data experiment. Phase 2 core features are implemented, with remaining acceptance checks listed below. The complete done/open/planned checklist is [plan.md](../plan.md).

## Verified by implementation and actual checks

| Area | Evidence | Boundary |
| --- | --- | --- |
| Real audio processing | WAV/MP3/M4A decoding, pinned learned model, measured evidence and API/CLI parity tests | The original detector still misses known synthetic voices |
| Saved investigation | Real detector/FFmpeg lifespan restart preserves JSON/CSV; interrupted work recovers and retries | Isolated application restart, not a forced restart of the user's running server |
| Playback and seeking | Browser playback/pause, interval navigation and keyboard waveform seek | Window assessment is not exact splice localization |
| Analyst exports | Browser JSON and two-row CSV downloads inspected against actual saved scores/IDs | Official sponsor CSV contract remains unknown |
| Failure behavior | Invalid audio fails; silence has null score; both live checkboxes disabled | Explicit QA fixtures, not detection-quality samples |
| Mobile navigation | Reproduced focus defect fixed; focused tests and live Chrome containment/restore/resize checks pass | Full accessibility certification is not claimed |
| Cluster preparation | Verified archives; all 14,000 selected files audited; separated train/selection/acceptance | Bounded public subset, not sponsor data or full ASVspoof5 |
| Actual training | Slurm 4503646 running since 01:00:42 Eastern; a checkpoint exists | Final independent results and promotion still pending |

Reports: [browser acceptance](phase2-browser-verification.md), [restart/export](phase2-restart-verification.md), [mobile repair](tdd/phase2-mobile-navigation.md), [cluster run](cluster-run-2026-09-25.md).

## Phase 2: remaining acceptance checks

- [ ] Complete an unfamiliar-file upload through the browser and follow it to playback/report. Browser automation's file selection is blocked by Chrome extension file-URL permission; ordinary backend format/inference checks pass. Enabling the extension's Allow access to file URLs permits an automated retry; a manual upload is also valid verification.
- [ ] Finish full desktop/phone/landscape visual and accessibility review, including contrast, reduced motion and screen-reader behavior. Narrow-screen DOM geometry and focused keyboard interactions passed, but there is no visual-regression baseline.
- [ ] Configure `XAI_API_KEY` locally in root `.env`, then verify live Grok citations, score immutability, persistence and JSON export. Do not put the key in chat or frontend settings.
- [ ] After Phase 3C accepts a candidate, show validation evidence linked to its exact serving model/configuration.
- [ ] Verify browser playback for expanded formats such as OPUS; required WAV/MP3/M4A remain the core supported-format priority.

## What the user can check in the app now

Open <http://127.0.0.1:5173>.

1. **Try a known recording:** choose genuine and synthetic examples, preview and analyze them. Compare labels with actual model scores; a disagreement is a detector error.
2. **Inspect:** play the result, click an interval or use the waveform's arrow keys, then inspect evidence, limitations and Technical provenance.
3. **Compare:** run MP3 compression or Add noise. Play both versions and inspect the real score change. Stable scores do not prove authenticity.
4. **Export:** select two completed scored records in Batch & export, download CSV and confirm only the requested IDs appear. Download a result's JSON for the full evidence/model record.
5. **Check failures:** the explicitly named QA-silent and QA-invalid records demonstrate null-score and failure states; neither can be selected for scored CSV export.
6. **After key setup:** generate a Grok interpretation. Confirm references match measured findings and the numerical detector score is unchanged; reopen the saved brief.

Uploading a dataset clip or your own permitted recording performs inference only. It does not train the model, establish identity or verify the truth of speech.

## Phase 3: next evidence gates

- [x] Verify environment, one-A100 compatibility, archive checksums and all selected speech files.
- [x] Start the existing one-node/one-GPU adaptation job and observe a saved checkpoint.
- [ ] Complete training plus baseline/candidate scoring on selection and locked acceptance.
- [ ] Review recall, false alarms, AUROC/AP, counts, intervals and attack errors at frozen thresholds.
- [ ] Review serving parity/latency and decide whether evidence supports replacing the web model.

Do not submit duplicate jobs or exceed the five-hour aggregate GPU budget. Check live status through the existing SSH/account settings and [run ledger](cluster-run-2026-09-25.md). The original web model remains active until a candidate passes review.

## Phases 4–5 and extensions

- [ ] Rehearse a complete demo with genuine/synthetic examples and an honest detector failure.
- [ ] Present independent before/after results when available; preserve a saved real-run fallback.
- [ ] Obtain official data, metric, CSV schema, deadline and submission destination.
- [ ] Freeze the selected model, score all held-out files, validate IDs/scale/polarity/order and resolve failures.
- [ ] Deliver the runnable prototype, required CSV, evaluation report and required event artifacts.

Speaker-reference comparison and source-backed factual-claim review remain planned extensions with separate inputs and validation. They are not currently implemented or included in the synthesis score.
