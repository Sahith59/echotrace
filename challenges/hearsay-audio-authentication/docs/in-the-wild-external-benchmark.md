# Locked In-the-Wild external benchmark

This benchmark tests the unchanged detector on realistic English audio collected from online videos. It is an external evaluation set only. It must not be used for training, checkpoint selection, threshold fitting, calibration, or repeated error-driven tuning. No detector predictions are read while the 2,000-file sample is selected.

## Pinned source and rights

- Author repository: `mueller91/In-The-Wild`
- Hugging Face API revision checked on 2026-09-26: `eee168f92c367f8c82ff2cf42b6f61e362fd6211`
- Archive: `release_in_the_wild.zip`, 8,161,489,023 bytes
- SHA-256: `46665f30a6758b45642c659c7e0e80da2ba3d121b064716824a56a010ddf9e1a`
- The current author Hugging Face card is tagged CC BY-SA 4.0. The older author project page says Apache-2.0. Until the maintainer resolves that discrepancy, use the more conservative CC BY-SA attribution posture and do not redistribute audio or derivatives.

The author card describes 31,781 clips, 58 public figures, 37.9 hours total, 20.7 hours genuine and 17.2 hours fake. The pinned archive actually contains 31,779 metadata rows: 19,963 bona-fide and 11,816 spoof across 54 metadata speaker IDs. The discrepancy is preserved rather than silently reconciled.

## Fixed protocol

The staging code validates the exact archive byte count and SHA-256 before opening it. It rejects encrypted entries, links, traversal paths, unexpected file types, duplicate names, excessive members, oversized members, and excessive expanded size. It permits only WAV audio, `meta.csv`, and the author's `attribution.txt`; that attribution is preserved in the staged output. It reads `meta.csv`, requires `file`, `speaker`, and `label`, then selects the lowest `sha256("external-itw-20260926:" + file)` ranks: 1,000 genuine and 1,000 fake. All original metadata columns are preserved verbatim as JSON in each manifest row.

Only those 2,000 recordings are extracted. FFprobe and FFmpeg must resolve from the pinned runtime environment. Every selected file is decoded, checked for a positive duration and quiet output, and content-hashed. Quiet, decode-failed, long, and duplicate rows remain in the fixed manifest with explicit status fields; the staging process never improves the benchmark by dropping difficult files. Provenance reports duration coverage at the detector's 30-second whole-file runtime boundary for each label. Missing source identifiers remain blank and are counted; they are never inferred from filenames. Speaker IDs come only from author metadata.

The successful target is `data/in-the-wild-external-2k/`, containing `audio/`, `manifest.csv`, `attribution.txt`, and `provenance.json`. The verified archive remains under `downloads/in-the-wild-eee168f/`. Range parts and a failed assembled archive remain for diagnosis after failure. The job never requeues automatically.

## Independence boundary

These recordings are external to ECHOTRACE's project training, selection, and prior acceptance ledgers. The upstream data inventories for every pretrained component are incomplete, so this does not establish independence from all upstream pretraining. Report the benchmark separately from ASVspoof5 and from any sponsor evaluation. A result on this balanced 2,000-file sample cannot be presented as expected HEARSAY performance.

## Reproducible CPU staging

The job requests one `qTRD` node, two CPUs, 8 GB RAM, three hours, and no GPU. Before submission, create a fresh log directory and copy the staging module and job file into an immutable tool snapshot. Set:

```sh
export ECHOTRACE_ROOT=/data/users3/sthummala2/echotrace
export ECHOTRACE_ITW_TOOL_DIR=/data/users3/sthummala2/echotrace/tools/external-itw-20260926
sbatch \
  --output="$ECHOTRACE_ROOT/logs/in-the-wild-stage-%j.out" \
  --error="$ECHOTRACE_ROOT/logs/in-the-wild-stage-%j.err" \
  --export=ALL \
  "$ECHOTRACE_ITW_TOOL_DIR/stage-in-the-wild.sbatch"
```

After staging succeeds, freeze and hash `manifest.csv` before any model scoring. Scoring needs a separate explicitly authorized job; this staging job consumes CPU only and does not submit or run inference.

## Actual staging evidence, 2026-09-26

Final CPU job `4504655` completed in 4m37s on one `qTRD` node with two CPUs and 8 GB RAM. Requeue was disabled. No GPU was requested or used. The locked manifest is `/data/users3/sthummala2/echotrace/data/in-the-wild-external-2k/manifest.csv`, SHA-256 `dbfa528249c855261d64b864956a6b346b0faf40897622bae6e5a28ba1f9309a`.

The manifest has exactly 2,000 rows: 1,000 genuine (`label=0`) and 1,000 spoof (`label=1`). All 2,000 decoded as `pcm_f32le`. One quiet recording, `21680.wav`, remains in the manifest with `audit_status=quiet`; there were zero decode failures and zero duplicate selected file hashes. The sample has 53 speaker IDs and no source IDs because the author's three-column metadata provides only `file`, `speaker`, and `label`.

Every selected recording is at most 30 seconds according to the complete decoder audit: genuine 1,000 at or below 30 seconds, zero above; spoof 1,000 at or below 30 seconds, zero above. Neither label has unavailable duration. This is full selected-set coverage, not a filter applied at scoring time.

`project-independence-audit.json` beside the manifest records zero exact original-file hash overlap against 16,458 hashes from the project's frozen training, selection, and three prior acceptance ledgers. Exact speaker/source strings also had zero overlap, but those identifiers use different dataset namespaces and cannot establish person-level or upstream independence. No scores or predictions were generated.

Two preserved failed attempts document why the protocol changed. Job `4504647` stopped after 2m06s when the real archive exposed the previously unknown author `attribution.txt`; the revised allowlist preserves it. Job `4504651` decoded all 2,000 files and stopped after 4m42s on the quiet recording; the final protocol retains quiet and failed rows instead of silently improving the benchmark by dropping them. The checksum-verified archive cache survived both attempts. Neither job used a GPU or requeued.
