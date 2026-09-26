# First bounded TReNDs experiment

Started 2026-09-25 America/New_York (cluster timestamps are UTC on 2026-09-26). Last status check: 2026-09-26 03:55 UTC. This is a run ledger, not a completed training or accuracy report. Recheck live status before any action.

## Location and scope

- Access: `ssh trends`; login host `arctrdlogin001`; user `sthummala2`; account `trends517s113`.
- Owned storage: `/data/users3/sthummala2/echotrace`. The user's unrelated `brset-codex` directory is untouched. Home contains no staged dataset/environment from this work.
- CPU work uses `qTRD`, 2 CPUs / 8 GB per job. Main GPU work uses `qTRDGPUM`, 1 node / 1 A100 / 4 CPUs / 32 GB host RAM. No arrays or exclusive nodes.
- Download: only `flac_T_aa.tar` and `flac_D_aa.tar`, 14,169,763,840 bytes total. Preserve official train/dev membership; no evaluation audio. Limited common/shared path checks found no existing ASVspoof5 copy; no search through other users' research files was performed.
- Planned frozen experiment: up to 10,000 training rows, 4,000 dev rows split by linked groups into selection/acceptance. Require 100 per class in both evaluation sets and complete audio audit. Actual counts are not known until staging/preflight finish.

## Jobs and last observed progress

| Job | Purpose | Evidence / state |
| --- | --- | --- |
| 4503617 | Python 3.11, FFmpeg and uv environment | Completed, 65 seconds |
| 4503629 | Locked dependencies and Linux tests | Dependencies installed; test failure from missing saved-report fixtures |
| 4503637 | Retry after restoring fixtures | Completed, 169 passed / 1 macOS-only test skipped |
| 4503631 | Actual A100 compatibility/numerical check | Completed, 13 seconds; no fitted speech model saved |
| 4503630 | Verified archive download and extraction | Running; 5,878,317,056 bytes of first archive present at last check; checksums/availability incomplete |
| 4503644 | New snapshot and preflight-code verification | Completed in 6 seconds; every packaged file hash verified, 41 tests passed |
| 4503645 | Freeze splits and audit every selected recording | Queued after successful 4503630 and 4503644 |
| 4503646 | Training, four evaluation runs, acceptance report | Queued after successful 4503645; 4h55 outer limit; `Requeue=0` verified |

The smoke reserved at most 5 minutes, and the main job at most 4h55: combined requested GPU wall limits are 5 hours. Training itself is capped at 3 hours, with four 20-minute whole-file scoring caps and 35 minutes of main-job overhead. CPU staging/audit time and queue time are additional. Failed dependencies automatically cancel audit/training jobs. Automatic requeue was disabled on main job 4503646 with `scontrol update JobId=4503646 Requeue=0`. Do not resubmit a duplicate or extend the budget automatically.

The A100 check measured an NVIDIA A100-SXM4-40GB, driver 580.159.04, PyTorch 2.14.0+cu130, one visible GPU, 3,194,475,520 peak allocated bytes and 0.1052 seconds per batch of 8 forward/backward passes on generated signals. This does not measure decoder throughput or speech quality. The data audit decodes sequentially with a 3,600-second cap; failure or timeout blocks training.

## Artifacts and reproducibility

Final training source snapshot: `source/fe1fcfc/`, with `file-manifest.json` hashing every packaged file. Transfer archive SHA-256: `95917e7253e1d4bb95c18560c8c5800c5194b5136da7d1627d0180098e35e633`. The already-running downloader uses the earlier `source/00a1d04/` snapshot and a fresh non-symlink target; subsequent local symlink hardening does not change its pinned URLs, hashes or extraction behavior.

Nothing from root `.env`, frontend private settings or SSH keys was included. The packages contain code, locked dependencies, pinned pretrained weights, official train/dev metadata and public diagnostic report fixtures. The CPU-only environment remains in `envs/runtime`; the detector environment is in `envs/detector`. Installed package versions are saved in `runs/environment-freeze.txt`.

All paths below are relative to the project storage root:

- `data/asvspoof5-aa/provenance.json`: archive hashes and actual subset counts after successful staging.
- `runs/aasist-aa-01/manifests/`: frozen train/selection/acceptance CSVs.
- `runs/aasist-aa-01/preflight.json`: complete per-file CPU audit and split coverage.
- `runs/aasist-aa-01/training-config.json`: generated only if the audit passes.
- `runs/aasist-aa-01/training/`: configuration, metrics and selected checkpoint if training succeeds.
- `runs/aasist-aa-01/evaluation/`: four score ledgers and `acceptance-report.json` if evaluation succeeds.
- `logs/`: per-job output/error logs; `tools/`: exact submitted scripts; `runs/gpu-smoke.json`: numerical smoke evidence.

## Read progress

```sh
ssh trends 'squeue -j 4503630,4503644,4503645,4503646'
ssh trends 'sacct -j 4503630,4503644,4503645,4503646 --format=JobID,State,Elapsed,ExitCode'
```

After completion, inspect every failure, class/attack/codec count, baseline/candidate metric and interval. Passing provisional point-estimate gates is only eligibility for review; no script changes the web model. Review serving parity and runtime, and preserve rollback, before any replacement. The current app remains the original uncalibrated AASIST-L detector until then. Public acceptance is separate from sponsor-specific evaluation and official CSV validation.
