# Experimental AASIST-L training runner

Stage audio, the official pretrained AASIST-L checkpoint, and frozen train and selection manifests before requesting GPU time. The example [configuration](../configs/training-pilot.json) uses placeholders; replace every path and confirm the measured batch size and throughput on the allocated GPU. Run from the backend environment:

```sh
python -m echotrace.training ../configs/training-pilot.json
```

The train and validation CSVs use the shared manifest format: `file_id,path,label` and optional `group_id,speaker_id,source_id`. Paths are relative to `dataset_root`. Labels are `0=genuine, 1=synthetic`; the runner converts them explicitly to AASIST targets `1=bonafide, 0=spoof`. Both splits need both classes. Any matching content hash, file ID, group, speaker, or source across splits aborts the run. The 24 public demonstration recordings are barred by their pinned content hashes from `reports/public-pilot/provenance.json`. Freeze a separate locked acceptance set outside this runner.

The runner uses the shared FFmpeg mono 16 kHz decoder and the first shared 64,600-sample window per file. Short audio repeats to fill that window. Long audio is cropped at the start. Validation loss and accuracy therefore describe **fixed first crops**, not the web app's mean score over the whole file. A checkpoint is selected by the lowest validation cross-entropy. The selection set is used only for that selection; it is not an independent acceptance result. No threshold is selected, no checkpoint is promoted, and no cluster job or download is triggered.

`max_wall_seconds` is capped at 10,800 seconds so at least two hours remain in a five-hour allocation for setup and locked evaluation. `max_steps`, `max_epochs`, batch size, worker count, learning rate, seed, and CPU/CUDA device are explicit and bounded. A fresh output directory receives `config.json`, `metrics.json`, and `best.pt` when validation completes. The checkpoint contains model and optimizer state, step/epoch, pretrained weight hash, data hash, and configuration. An expired limit can leave metrics without a checkpoint; check `checkpoint` before using an artifact. Keep each run's output directory unique. The wall timer is cooperative: an individual decoder call or model step can finish after the deadline before the next check. Resume and validation patience early stopping are not exposed by this pilot runner; a subsequent experiment needs a fresh output directory and fresh wall budget.

The checkpoint also retains model-configuration SHA-256, upstream revision and content/ID/group/speaker/source provenance for both fitted splits. The [whole-file evaluator](../../../docs/checkpoint-evaluation.md) checks this provenance and checkpoint identity before scoring. Use the [three-way preparation command](../../../docs/data-preparation.md) and [bounded cluster package](../../../docs/cluster-handoff.md) for the complete experiment.

The checkpoint is experimental. Evaluate the baseline and selected checkpoint on the same locked files with the intended whole-file serving policy before considering any manual promotion. This runner does not establish sponsor accuracy or calibration.
