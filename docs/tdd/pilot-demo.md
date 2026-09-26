# Fixed 24-recording guided demo evidence

Date: 2026-09-25. Scope: pinned example access and real-inference UI, no training.

## Test mapping and checkpoints

- Catalog schema, allowed IDs, integrity, missing/tampered files and escaped/symlink paths: backend/tests/test_pilot.py. Initial RED checkpoint4ef9c4d preceded implementation. Additional cases were added during review.
- Example loading, reference labels, sample bytes passed to upload callback, busy/error/unavailable/retry states: frontend/src/components/PilotExamples.test.tsx. **Deviation:** UI implementation preceded its tests; do not describe this part as RED-first TDD.
- Integration glue mounts the router in create_app and the picker in App. These files had pre-existing untracked content, so their first checkpoint includes that baseline content.

## Verification

- Backend: `uv run pytest -q` →61 passed, one upstream Starlette TestClient deprecation warning.
- Frontend: `npm run test:coverage` →7 passed; PilotExamples alone93.84% statements,82.6% branches,95.45% functions,100% lines. This is not whole-app coverage.
- `npm run build` →TypeScript and Vite production build passed.
- Live Chrome via computer use: all24 catalog options, genuine and synthetic sample submissions completed using AASIST-L; interval seek moved to3seconds, playback changed to Pause, MP3 comparison completed. Genuine example rounded0%; synthetic example rounded9%, a real false negative at0.5. MP3 derivative rounded8%. No label overrides.
- Batch table persisted samples; selected two originals and invoked CSV download. Download artifact contents were not independently checked this turn.
- Browser review exposed ALL FILES counting only originals while statuses included derivatives. Corrected displayed total to all jobs; no new behavior test for this small display correction.

## Limits and next step

24 inspected files remain a demo/diagnostic set. No fitting, calibration, GPU job or general performance claim. Mobile/restart recovery and downloaded export artifact verification remain next, along with sponsor data/schema gates.
