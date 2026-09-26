# Phase 3A evaluation and cluster package evidence

2026-09-25. User authorized continued development and GPT-6 Sol medium agents. Three agents handled checkpoint evaluation, experiment data preparation and the cluster package; root integrated the acceptance reporter, audited cross-module contracts and ran final checks. ECC TDD was applied. Sequential-thinking skill instructions were consulted; the named MCP tool is unavailable, so the written phase sequence records the workflow.

## RED checkpoints on the active branch

| Commit | Behavior and observed failure |
| --- | --- |
| `f53672b` | Checkpoint scoring and training provenance tests failed before the evaluator/provenance implementation |
| `3ff888a` | Independent experiment preparation tests failed before the module existed |
| `99a9469` | Frozen thresholds, coverage and acceptance gates specified before implementation |
| `d11245e` | Integration reproduced the reporter expecting `completed` while the scorer emits `scored` |
| `74c2a51` | Eight evaluator hardening failures: CLI alias, demo exclusions and malformed training provenance; reporter malformed-ID failure |
| `581c11d` | Three Slurm preflight failures: missing acceptance audio, insufficient class counts and training/acceptance content overlap reached training |

The Slurm script's initial draft preceded its original guard tests; that is a TDD deviation. The subsequent preflight defects followed RED then implementation. Additional regression cases were added after GREEN without further production changes. Several GREEN integrations were batched into the final implementation checkpoint rather than committed immediately after each individual agent result. Do not describe the entire turn as strict sequential TDD.

## Final verification

From `challenges/hearsay-audio-authentication/backend`:

```sh
uv run --with pytest-cov pytest -q \
  --cov=echotrace.checkpoint_eval --cov=echotrace.prepare_experiment \
  --cov=echotrace.acceptance --cov=echotrace.training \
  --cov-report=term-missing
```

Root result: **167 passed**, one existing Starlette/httpx deprecation warning, 9.18s. Selected-module statement coverage: acceptance93%, evaluator83%, preparation81%, training81%; combined84%. This is not whole-project or branch coverage.

From the challenge directory: `python3 -m unittest -q cluster.test_job` → **12 passed**, 8.671s; `bash -n cluster/train-and-evaluate.sbatch` → passed. Shared data validators run for real; fake model commands verify shell ordering without allocating a GPU. The tiny preflight file fixtures test path/content hashing, not audio decoding. The script verifies all three manifests, both classes, pairwise links and at least100/class in both evaluation sets before invoking training.

## Actual-model local integration

Root generated six sine-wave WAV fixtures with separate IDs/groups/content: two training, two selection, two acceptance. The real preparation command froze manifests; the actual pinned AASIST-L model completed one CPU optimization step and wrote a provenance-bearing checkpoint. The whole-file evaluator scored both baseline and that checkpoint on both evaluation splits with complete ledgers. The acceptance reporter, also invoked through its CLI, returned `eligible_for_review=false`, `promoted=false`, as required for this tiny fixture.

Ignored local artifacts: `backend/artifacts/phase3a-wiring-i9qhoca7/`, including configuration, preparation, checkpoint, four score ledgers and acceptance reports. These generated signals check numerical execution and wiring only; they are not real/synthetic speech evidence or a meaningful detector-training experiment. No weights were promoted and no app score was changed. Existing `.env` and all generated model/data artifacts remain ignored.

## External limits

The SSH attempt to `trends` timed out before authentication; no remote command, dataset transfer or cluster submission occurred. User supplied the current account and reports no personal data path. The Grok status check still reported unavailable; no live generation or billable API call was performed. No frontend code changed in this milestone, so prior browser/frontend checks were not represented as newly rerun.

Next gate: restore cluster access, establish permitted storage/partition, install and audit real independent speech audio, freeze suitable counts from measured throughput, then submit one bounded job. The current software cannot establish an improved detector, speaker identity or message truth.
