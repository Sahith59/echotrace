# TReNDs experiment ledger

Started 2026-09-25 America/New_York (cluster timestamps are UTC on 2026-09-26). **Current status: all three bounded experiments completed and failed promotion. No experiment job remains active.** The first-run setup below is historical. Recheck live status before any action.

## Completed results and current final run

| Run / job | Actual GPU allocation | Result |
| --- | --- | --- |
| Smoke 4503631 | 13 seconds | Numerical compatibility only |
| AASIST adaptation 4503646 | 55m49 | 6,000 training steps; acceptance recall 44.47%, FPR 3.98%, AUROC 0.8448; not promoted |
| Native frozen 4503743 | 7 seconds | Wrong dataset-root preflight; failed before inference |
| Native frozen 4503749 | 7m48 | 457 fresh-speaker acceptance files; recall 49.10%, FPR 5.17%, AUROC 0.8470; not promoted |
| Native adaptation setup 4504573 | 4 seconds | Missing output parent; failed before model loading or inference |
| Native adaptation 4504574 | 40m52 | ASVspoof5 eval-aa acceptance recall 87.40%, FPR 24.40%, AUROC 0.9061; not promoted |

Aggregate GPU allocation elapsed is **1h44m53s**, including both short preflight failures. Full aggregate reports are checked in under `challenges/hearsay-audio-authentication/reports/cluster-run-01/`, `reports/native-frozen-01/` and `reports/native-adapt-01/`. These contain the independently selected thresholds, confusion counts, confidence intervals and promotion decisions. They are public-data experiments, not sponsor results.

The remaining unused development speakers supplied only 33 genuine and zero synthetic examples, so that proposed next holdout was rejected. CPU job **4503784** downloaded and checksum-verified the archive but failed its decoder audit because ffprobe was absent from PATH. Its initial cleanup discarded temporary files; no GPU allocation was consumed. CPU decoder smoke **4504562** then passed on a real FLAC. Recovery job **4504563** completed in 20m27s after four bounded HTTP ranges, fixed full-archive checksum verification, and 2,000 successful decode/quality checks. Content audit **4504572** completed in 6s: all 2,000 acceptance original-file hashes were unique and had zero overlap with 14,458 hashes from the frozen train, selection and prior-evaluation ledgers. The official partition and content checks are separate evidence; different speaker-ID namespaces alone are not proof of independence.

The final native adaptation is predeclared: pinned wav2vec2 checkpoint `c66306024a7ede0be291e9c4558b37634782dc4e`, frozen convolutional encoder, transformer/head training, seed 20260926, effective batch 16, AdamW learning rate 1e-5, at most 2,000 steps / three epochs / 2h30 fit. Checkpoint and threshold selection use only the original selection split. Final acceptance is evaluated after freezing them.

Final job **4504574** used one A100 for 40m52s within its hard 3h30 allocation. Epoch 1 was selected using only the original selection split (recall 95.91%, FPR 4.70%, AUROC 0.9937); epoch 2 regressed and triggered the predeclared patience stop. On untouched acceptance3, the selected checkpoint reached recall 87.40% but FPR 24.40%, so it failed the unchanged 80%/5% gates and was not promoted. The candidate checkpoint SHA-256 is `ec5b7388348b0f37dae0a7f74de6cfe61f9a9d815a035574ac6579458ca695ad`; the aggregate report SHA-256 is `52d3cbe4047d800dda4ecf6c1eb80fd37ac5e261c38690e94f9c83d4f2e92966`.

Independence is established only against our frozen 10,000-file train, 2,000-file selection and prior evaluation ledgers. The Gary Stafford model card describes 1,866 author-collected YouTube/TTS clips, while its Gustking base card does not provide a complete upstream training inventory. This run therefore does not claim acceptance3 is independent of every upstream pretraining source. The web continues serving the original AASIST-L.

Post-hoc slice review found that compressed bona fide audio drove the failure: candidate FPR was 21.9%–59.0% on C01–C04 and C06–C10, while uncompressed audio, C05 and C11 were at or below 2.63%. No threshold was retuned from this observation. After excluding every acceptance3 and prior-ledger speaker and source, eval-aa retains 2,950 files (1,672 genuine / 1,278 fake), 2,202 sources and 97 speakers, but only 10 synthetic speakers. This can support a frozen file/source-disjoint follow-up holdout, with limited synthetic-speaker diversity and no sponsor-distribution claim. No further GPU experiment was submitted.

## Historical first-run setup (05:25 UTC checkpoint)

## Location and scope

- Access: `ssh trends`; login host `arctrdlogin001`; user `sthummala2`; account `trends517s113`.
- Owned storage: `/data/users3/sthummala2/echotrace`. The user's unrelated `brset-codex` directory is untouched. Home contains no staged dataset/environment from this work.
- CPU work uses `qTRD`, 2 CPUs / 8 GB per job. Main GPU work uses `qTRDGPUM`, 1 node / 1 A100 / 4 CPUs / 32 GB host RAM. No arrays or exclusive nodes.
- Download: only `flac_T_aa.tar` and `flac_D_aa.tar`, 14,169,763,840 bytes total. Preserve official train/dev membership; no evaluation audio. Limited common/shared path checks found no existing ASVspoof5 copy; no search through other users' research files was performed.
- Frozen experiment: 10,000 training rows, 2,000 selection rows and 2,000 locked acceptance rows, separated by linked groups. All 14,000 files were decoded and audited with zero failures or quiet files. Train genuine/synthetic counts: 3,801/6,199; selection: 1,021/979; acceptance: 979/1,021. Training attacks A01–A08; dev A09–A16. Codec metadata is `-` for every selected row; do not claim codec-diversity evidence.

## Jobs and last observed progress

| Job | Purpose | Evidence / state |
| --- | --- | --- |
| 4503617 | Python 3.11, FFmpeg and uv environment | Completed, 65 seconds |
| 4503629 | Locked dependencies and Linux tests | Dependencies installed; test failure from missing saved-report fixtures |
| 4503637 | Retry after restoring fixtures | Completed, 169 passed / 1 macOS-only test skipped |
| 4503631 | Actual A100 compatibility/numerical check | Completed, 13 seconds; no fitted speech model saved |
| 4503630 | Verified archive download and extraction | Completed at 04:31:29 UTC after 1h00m59s; checksums passed, 36,500 train / 47,400 dev files staged |
| 4503644 | New snapshot and preflight-code verification | Completed in 6 seconds; every packaged file hash verified, 41 tests passed |
| 4503645 | Freeze splits and audit every selected recording | Completed at 05:00:41 UTC after 29m12s; ready=true, all 14,000 selected files audited |
| 4503646 | Training, four evaluation runs, acceptance report | RUNNING since 05:00:42 UTC / 01:00:42 Eastern; 24m07s at last check, 4h55 limit, Requeue=0 |

The smoke reserved at most 5 minutes, and the main job at most 4h55: combined requested GPU wall limits are 5 hours. Training itself is capped at 3 hours, with four 20-minute whole-file scoring caps and 35 minutes of main-job overhead. CPU staging/audit time and queue time are additional. Failed dependencies automatically cancel audit/training jobs. Automatic requeue was disabled on main job 4503646 with `scontrol update JobId=4503646 Requeue=0`. Do not resubmit a duplicate or extend the budget automatically.

The A100 check measured an NVIDIA A100-SXM4-40GB, driver 580.159.04, PyTorch 2.14.0+cu130, one visible GPU, 3,194,475,520 peak allocated bytes and 0.1052 seconds per batch of 8 forward/backward passes on generated signals. This does not measure decoder throughput or speech quality. The sequential data audit completed in 1,744.667 seconds of measured preflight work, within its 3,600-second cap.

Actual fitting is confirmed by `runs/aasist-aa-01/training/best.pt` (3,361,353 bytes, first observed timestamp 05:11 UTC). Final training metrics and independent evaluation have not yet been produced at this check. A saved checkpoint is not evidence of improved accuracy.

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

A stale SSH multiplex connection failed on the follow-up check. A fresh connection with ControlPath=none and an explicit fresh proxy through the configured `elpis` alias succeeded. This did not interrupt the already-running Slurm job. No credential/configuration changes were made.
