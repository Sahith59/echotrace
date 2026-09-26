# Phase 2 browser acceptance record

Date: 2026-09-26. Tested the running local prototype at `http://127.0.0.1:5173` through Chrome/CUA. Applied the ECC browser-QA workflow. No provider key or private recording was used.

## Verified

- Intake rendered at a 375 × 812 viewport. Mobile navigation opened and reached Batch & export.
- Batch and recording views had document widths matching the 375 px viewport; the table scrolls within its own container. Batch also had no page overflow at 768 px. At 1440 px the desktop view also had no page overflow and resizing out of an open drawer cleared modal/inert state. These geometry checks do not replace complete visual review.
- Selected two existing completed recordings through mobile batch controls and downloaded the actual CSV. `/Users/sahithreddythummala/Downloads/echotrace-analyst-export (1).csv` contained exactly IDs `0f1bc5d6a66e46b981a896713f4c3fd4` and `a10f0d5f5f4c4683aec36cad8a72062e`, with scores `0.09214715551` and `0.02991159679`. Compared both with saved API results within the CSV's 10-significant-digit precision.
- Opened the saved Jane Eyre synthetic analysis, started and paused playback, and used the waveform's ArrowRight key to seek to 5 seconds. The low score is a known detector miss, not an authenticity claim.
- Downloaded its JSON report through the browser. The parsed downloaded JSON exactly matches the complete saved API report, including AASIST-L model metadata, full stored score, input hash, intervals, evidence, limitations and aggregation policy.
- Created explicitly named `QA-silent-recording.wav` and `QA-invalid-recording.wav` fixtures through the local API, then refreshed Batch & export in Chrome. Silence completed with a null score; invalid audio failed with a readable error. Both selection checkboxes were disabled. These are API-created fixtures, not successful browser upload claims.
- Found a real mobile drawer defect: focus could Tab to background Add recording while the drawer was open. Repaired it with behavioral tests. Live Chrome confirmed focus entry, forward/reverse containment, Escape restoration and removal of modal/inert state. See [TDD evidence](tdd/phase2-mobile-navigation.md).
- Separate real detector/FFmpeg lifespan restart verification preserved JSON/CSV exactly and recovered/retried interrupted work. See [restart evidence](phase2-restart-verification.md). The user's running backend was not stopped.

## Remaining checks and boundaries

- Custom-file browser upload was attempted with a permitted local M4A fixture. The hidden-input chooser timed out; the visible Add files control opened a chooser, but file selection was rejected by the Chrome extension with `Not allowed`. This is a browser automation permission blocker; do not mark the unfamiliar-file browser journey complete. Enable the extension's Allow access to file URLs, or perform that final browser upload manually. Backend WAV/MP3/M4A integration checks already pass.
- Some resized screenshots were scaled unexpectedly by the capture surface. No committed visual baseline exists, so visual regression is **inconclusive**. Full landscape, reduced-motion, contrast and screen-reader checks remain open. DOM geometry and focused keyboard checks are the verified subset.
- Captured warning entries came from a separate installed browser extension, not the app. No claim of a complete network or Web Vitals audit is made.
- Grok remains unconfigured; no live generated brief was tested. AI interpretation integration tests are separate from provider validation.
- Expanded formats such as OPUS still need browser playback verification. Required WAV/MP3/M4A remain the priority.

This closes specific Phase 2 acceptance tasks, not all Phase 2 gates or any detector-quality gate. Temporary browser viewport overrides are reset before handoff.
