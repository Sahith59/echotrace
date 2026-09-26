# Phase 1 evaluation readiness — TDD evidence

Source: [plan.md](../../plan.md), Phase 1 grouped validation and reproducible batch/export. Journeys: an analyst needs related recordings kept out of opposite evaluation partitions, repeatable membership after manifest reordering, and batch/report output that cannot overwrite its own input.

Validation intent was normalized to project-local pytest and pytest-cov commands after inspecting pyproject.toml (uv + pytest). No plan-embedded installers or destructive commands were executed. Sequential-thinking tool discovery returned no callable tool; ordered steps are recorded in the plan.

| Guarantee | Test target | RED | GREEN |
|---|---|---|---|
| Loader retains trimmed speaker/source metadata; transitive links stay together | tests/test_split_metadata.py | 2 failed, 1 passed before fix | 3 passed |
| Seeded membership remains stable under reordered manifests | same, order test over 20 seeds | 1 failed, 2 passed after strengthening regression | Passed with canonical component ordering |
| CLI output/sidecar cannot alias inputs through direct paths, symlinks or hardlinks; valid distinct outputs work | tests/test_cli_output_safety.py | 14 failed initially; extended to 15 failed, 1 passed before production fix | 16 passed |

Actual commands (backend directory):

- `uv run pytest -q tests/test_split_metadata.py`
- `uv run pytest -q tests/test_split_metadata.py tests/test_evaluation.py` — 8 passed after each grouping fix.
- `uv run pytest -q tests/test_cli_output_safety.py` — 16 passed after guard implementation.
- `uv run --with pytest-cov pytest -q --cov=echotrace --cov-report=term-missing` — **37 passed, 1 upstream Starlette/httpx deprecation warning, 7.13s; 88% statement coverage**. evaluation.py 86%, cli.py 88%. Overall number includes vendored AASIST; first-party is 729 statements, 112 missed, approximately 84.6%. No branch-coverage claim.

Checkpoints on active master: e17dee0 (metadata RED), 005a61a (metadata GREEN), 5137668 (order RED), 9d00321 (order GREEN), 997ce79 and 01cdc78 (output safety RED), 614287d (output safety GREEN). This repository began with untracked implementation; the GREEN commits consequently first track the existing production modules together with fixes, not only new lines. Other user work remains untracked and untouched by these commits.

Known gaps: output alias guards cover CLI entry points, not direct library use of export_submission. Concurrent filesystem changes after preflight and atomic output replacement remain future hardening. Malformed schema type validation and richer batch provenance need follow-up. Metadata links cannot discover absent speaker/source relationships. No browser changes in this iteration; no new browser E2E claim. These tests establish software guarantees, not detector accuracy.

## Large corpus preparation and candidate comparison continuation

New test-first guarantees: ASVspoof5 protocol conversion preserves train/dev/eval boundaries, labels and metadata; rejects malformed IDs/labels/duplicates and existing output without overwriting. Candidate runs are isolated from web inference, verify exact official weights/configuration, retain raw logits and file hashes, use fresh output directories and reject one-class evaluation before writing.

Initial RED: importing `echotrace.asvspoof5.convert_protocol` and `echotrace.candidate` failed because these new implementation modules did not yet exist (intended missing implementation, not dependency failure). Checkpoint e107142 precedes production implementation. Importer GREEN:9tests; checkpoint8be9731. Candidate initial GREEN:4tests plus real24file inference. Further tests exposed one-class partial output (7passed/1failed); preflight fixed it, final8passed. For this follow-up the agent edited production after observed RED but before the root made test checkpoint5a22bea; this timing deviation is recorded rather than claiming perfect checkpoint order. Candidate GREEN checkpoint3d2a275.

Root full suite: `uv run --with pytest-cov pytest -q --cov=echotrace --cov-report=term-missing` —54passed, one upstream warning,88%statement coverage,7.15s; importer82%, candidate85%. Statement coverage is not branch coverage. Offline real candidate run is additional integration evidence, not a test-suite accuracy claim. Candidate scores every decoded clip and does not apply the web quiet-audio gate; compare speech samples and disclose this distinction. No UI code changed in this continuation.
