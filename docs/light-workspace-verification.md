# Light workspace and guided investigation verification

Date: 2026-09-26. Scope: local prototype and source release, not deployment or official sponsor submission.

## Design and useful interactions

The approved light direction replaces the dark monochrome overrides with warm paper, translucent white surfaces, ink text, blue/teal actions and distinct warning/error treatments. IBM Plex Sans is bundled locally; editorial headings use a serif stack and technical values use IBM Plex Mono. The background is a generated interpretation of the user's woven reference, softened with blur and a light overlay. Asset: `frontend/public/textures/woven-field.png`. It is decorative and does not encode evidence.

The supplied glass-calendar component was adapted into a recording-date filter with month navigation, clear selection, keyboard dismissal and small-screen positioning. The existing Motion, TypeScript, Tailwind and `components/ui` setup is reused. No nonfunctional event/settings controls were copied. Contextual help opens with keyboard or pointer and closes with Escape. Transitions honor reduced-motion preferences.

Each case now has three steps: **Review recording**, **Check reliability**, and **Case evidence**. Notes persist independently of the model score; draft preservation and version checks prevent silent overwrites. The queue supports search, review/analysis status, date filters and sorting while retaining failed/unscored records.

## Verified live in Chrome

- Legacy synthetic recording reanalyzed through the new primary NII pipeline: new case `14e3396e7c554e1bb4c64036ac6310b7`, score `0.9999682903289795`, 8.72-second input, displayed processing time 1.2 seconds. Original case remains unchanged.
- Known genuine public sample submitted through the built-in sample upload, which uses the normal multipart analysis endpoint: new case prefix `d55cea14`, displayed synthesis score 2%, 7.53-second input, processing time 1.1 seconds. These two examples are inspected diagnostics, not an accuracy benchmark.
- Real Groq generation succeeded using the configured key. A completed MP3 comparison invalidated the old brief; regeneration included the measured MP3 score and score difference. Clicking its evidence reference opened and highlighted the actual measurement row.
- Saved analyst status `corroboration_requested` and an analyst-written demonstration note at version 1; verified the persisted review in case JSON.
- Mobile viewport 375×812: no document horizontal overflow; date popover within viewport; queue filtering and selection worked. Escape dismissed the calendar. Contextual-help stacking was corrected and visually rechecked.
- Same-model CSV downloaded through the browser: two rows, six columns (`file_id`, `filename`, `synthetic_score`, `analyst_review_status`, `analyst_review_notes`, `analyst_review_version`), including the saved review status. Download checked at `~/Downloads/echotrace-analyst-export (2).csv`.

Native unfamiliar-file chooser automation remains limited by browser file permissions. Built-in real-file upload and backend format/error tests passed; this does not claim a manually selected arbitrary file was tested through the native chooser. No browser security permissions were weakened.

## Regression and packaging checks

- Frontend: 51 tests across eight files passed; production TypeScript/Vite build passed.
- Backend: 290 tests passed after the final interpretation-scope refinement. The v3 evidence contract explicitly distinguishes the whole-file display span from independent windows and same-detector transformations from independent corroboration.
- Built wheel inspected: includes `primary_detector.py`, `analyst_review.py`, `nii_parity.json` and `validation_summary.json`; contains no `.env`, audio examples or model-weight files.
- Meaningful RED/GREEN contracts cover contextual help/calendar, analyst conflict/draft behavior, primary detector failures/parity, evidence links/refresh, mixed-model guards and report freshness. Queue/navigation integration checks were added after those UI features were implemented; they are regression tests, not claimed test-first development.

## Phase completion and remaining boundaries

Phases 3C (scoped primary serving), 4A (guided review), 4B (queue/reliability) and 4C (evidence brief/handoff) are implemented. Phase 5 local demonstration and regression checks are covered; official submission still requires the sponsor's files, schema, metric and destination. Deployment remains a separate user-directed step.

The pinned NII model is a pretrained detector, not a newly invented architecture. The 2,000-file In-the-Wild result is public benchmark replication: 937/1,000 synthetic detections and 24/1,000 genuine false alarms at threshold 0.5. One quiet recording is included in model-only metrics but rejected by the application. See [serving decision](model-serving-decision.md) for parity, provenance and open validation requirements. Scores are uncalibrated and current primary inputs are limited to 30 seconds without silent truncation.

Paired AASIST baseline job 4504670 results still need retrieval; cluster jump-host attempts timed out. No duplicate job or extra GPU training was launched. No relative superiority or sponsor-performance claim is made.

Speaker similarity does not prove identity; transcript/source review does not prove truth. Hosted claim-source retrieval remains unavailable until source provenance can be validated. AI prose still needs analyst review. Full screen-reader and formal accessibility certification are not claimed.

The final backend was restarted with no queued/running jobs. Existing reports and analyst notes survived. The prior brief was visibly marked outdated in the printable report after the evidence contract changed.

Final v3 Groq regeneration succeeded in the browser after restart. It described the entire-file score as uncalibrated, stated that acoustic reference ranges were absent, and identified MP3 results as same-detector robustness observations. Case JSON reported `interpretation_status=current`, prompt v3, original score unchanged, one matched stress comparison and analyst revision 1. Source release `60a870c` was pushed to the private repository; CI: [run 36251442812](https://github.com/Sahith59/echotrace/actions/runs/36251442812).
