# Cluster staging and complete audio audit: verification record

Date: 2026-09-25. Applied ECC TDD and MLE workflows. Three GPT-6 Sol medium agents handled bounded staging, CPU preflight and error-slice reporting; root integrated and verified them. This record concerns software correctness and cluster execution, not a measured improvement in speech detection.

## RED/GREEN checkpoints

| Area | RED | GREEN | Evidence |
| --- | --- | --- | --- |
| Attack/codec acceptance slices | `396be3d` | `fdf5dbe` | 18 acceptance tests; 94% statement coverage |
| Pinned archive staging | `43da3de` | `00a1d04` | 8 offline fixture tests |
| Dangling staging destination | `df5252b` | `1ab1187` | 10 tests; 81% statement coverage |
| Complete CPU experiment audit | `38bc97e` | `fe1fcfc` | 13 focused tests; 89% statement coverage |

The dangling-output checkpoint also added a same-size checksum-corruption regression that already passed; the symlink test provided RED. A later config-write-failure preflight regression and implementation arrived together before the parent could capture a separate RED commit. That timing deviation does not change the passing result, but this was not a strict RED commit for every individual regression.

## Meaningful behaviors checked

- Staging: pinned bytes and hashes; same-size corruption; path traversal, links, duplicate members, non-audio members and output collisions; bounded extraction; preserved official metadata; provenance. No real network download in unit tests.
- Preflight: all selected audio decoded and counted; linked split/class gates; quiet/corrupt files fail readiness; wall cap interrupts slow work; duration/window ledger; fresh outputs; no training config on failed audit or failed config publication. No silent filtering or label-driven resplitting.
- Acceptance slices: baseline/candidate alignment; per-attack/codec counts and confusion; missing metadata bucket; undefined single-class rankings/rates remain null; locked threshold use. Existing aggregate eligibility gates remain intact.

Final root `uv run pytest -q` in the backend: **183 passed**, 10.47 seconds, one upstream Starlette deprecation warning. Selected acceptance/preflight statement coverage was 92%. Staging's separate suite: **10 passed**. Earlier 12 Slurm guard tests and shell syntax verification remain applicable; the shared job template was not changed this turn.

## Actual cluster evidence

- Job 4503617 installed the CPU runtime under permitted personal data storage.
- Job 4503629 installed locked dependencies, then revealed missing saved-report fixtures in the source transfer. Restored those exact files; job 4503637 passed **169 tests / 1 macOS-only skip**. No unresolved dependency-install failure is being concealed.
- Final source snapshot `fe1fcfc` includes all required fixtures and file checksums. Job 4503644 verified every packaged file and passed **41 focused tests** on Linux.
- Job 4503631 performed finite forward/backward work on one actual A100-SXM4-40GB. It completed in 13 seconds; no fitted speech checkpoint was saved. Generated signals are numerical smoke inputs, not a classification benchmark.
- Main training/evaluation job 4503646 is queued behind full audio audit 4503645, which depends on verified staging 4503630 and code verification 4503644. Failed dependencies cancel subsequent jobs; the main job has no automatic requeue. See the [run ledger](../cluster-run-2026-09-25.md) for exact paths, limits and live-status commands.

## Remaining evidence

Archive checksums, actual corpus coverage and full audio audit are not complete at this handoff. Adaptation has not started. There are no independent candidate results yet, no new web-model weights, and no live Grok generation. Browser UI was unchanged and was not newly tested this turn; live API health and missing-provider status were checked. Next decisions must use the real run artifacts, not passing unit tests as a proxy for detector accuracy.
