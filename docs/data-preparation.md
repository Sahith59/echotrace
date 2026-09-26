# ASVspoof5 three-way experiment preparation

The metadata importer has produced official ASVspoof5 Track 1 train and dev manifests, but the audio is not installed in this workspace. Run this command only after obtaining the corresponding audio through an authorized source. It does not download data or train a model.

The current cluster experiment uses the [bounded staging utility](../challenges/hearsay-audio-authentication/cluster/stage_data.py) to download exactly the pinned train/dev `aa` archives, verify size/MD5, extract regular FLAC members safely and filter the official protocols to those members. This is a subset of ASVspoof5, not a full-corpus benchmark. Files absent from Track1 metadata, such as development enrollment recordings, are counted separately. Source, checksums and label counts are retained in `provenance.json`. Staging does not modify the official full manifests or use evaluation audio.

For the active run, `python -m echotrace.experiment_preflight --staged-root /ABS/staged --output-dir /ABS/fresh --train-limit 10000 --dev-limit 4000 --max-wall-seconds 3600` wraps preparation and a full CPU audio audit. It freezes the three manifests, checks class counts/group separation, then decodes and measures every selected recording. It records durations, window counts, failures/quiet audio and speaker/attack/codec coverage. Any failed, quiet or unaudited recording prevents readiness; no file is silently dropped. It writes `training-config.json` only on success and exits nonzero otherwise, so the dependent GPU job cannot start. Audit is sequential and has a one-hour cap; slow input can make an otherwise valid dataset fail readiness. See [live run record](cluster-run-2026-09-25.md).

From `challenges/hearsay-audio-authentication/backend`:

```sh
uv run python -m echotrace.prepare_experiment \
  --train-manifest /path/to/train.csv \
  --dev-manifest /path/to/dev.csv \
  --dataset-root /path/to/asvspoof5-audio \
  --output-dir /path/to/new-experiment-manifests \
  --seed 42 --train-limit 30000 --dev-limit 10000
```

The output directory must be new. The command writes `train.csv`, `selection.csv`, `acceptance.csv`, and `preparation.json` after all checks pass. The two source CSVs must have explicit `partition` values (`train` and `dev`), binary labels (`0` genuine, `1` synthetic), relative audio paths, and nonempty speaker, source, or group metadata for each row. The official importer also supplies `attack_id` and `codec`; all input columns survive in the output. Train rows come only from the official train partition. The selected dev rows are divided into a selection set for model or threshold choices and a locked acceptance set for the final check. Never use acceptance labels to choose a model, threshold, or preprocessing rule.

`--train-limit` and `--dev-limit` are positive integer caps of 30,000 and 10,000 respectively. Stable seeded hashes choose bounded rows in each class, independently of input row order. The dev split uses the existing transitive `grouped_split` logic: shared speaker, source, explicit group, or identical audio content stays together. The command rejects a split if independent groups or either class are insufficient, or if the three outputs share IDs, speakers, sources, groups, or audio hashes. It also excludes the pinned 24 MLAAD-tiny diagnostic recordings by catalog ID and actual audio hash. Those recordings remain demonstration and regression material only.

The command calls `load_manifest` on the **selected rows**, which checks path containment and hashes each selected audio file. Missing files, malformed metadata, and overlapping sets fail before the output directory is published. `preparation.json` contains the seed, source manifest SHA-256 values, source row counts, requested limits, per-split class counts, counts of unique audio hashes, and small sorted hash slices. Its `audio_verification_scope` is `selected_subset_only`: the command does not audit or verify unselected audio in the full source manifests. Retain the source manifests and report with any later training result so the selected experiment can be reproduced.
