# ECHOTRACE: what the prototype does

ECHOTRACE is a recorded-audio investigation workbench for an analyst reviewing a suspicious voice recording. The user uploads a file, listens to the passages flagged by the model, inspects the measured evidence, compares altered copies, and exports a record of the investigation. The NSA HEARSAY task is the core: analyze audio and produce reproducible synthesis scores and test-set predictions.

## Available features

| Feature | What a user can do | Current boundary |
| --- | --- | --- |
| Audio intake | Upload WAV, MP3, M4A and other FFmpeg-supported recordings, singly or in a batch | 50 MiB / 120 seconds per file; unsupported input fails explicitly |
| Real learned inference | Run the pinned AASIST-L detector on the uploaded audio | Current model misses known synthetic recordings; scores are uncalibrated |
| Playable evidence timeline | Play the original audio, seek with the waveform or a scored interval, and compare passages | Windows are model assessments, not verified splice boundaries |
| Signal measurements | Inspect clipping, quietness, duration and spectral/temporal measurements | These are measured observations, not independent proof of synthesis |
| Known-recording examples | Preview and analyze 24 local reference clips with known labels | Reference labels stay separate from predictions; not an independent benchmark |
| Compression/noise comparison | Generate an MP3 or seeded noisy derivative, listen to both and compare scores | The rerun is real; stable scores do not prove accuracy |
| Saved investigations | Reopen prior analyses, inspect job status and retry failed processing | Local SQLite and file storage; no multi-user access system |
| Evidence export | Download analysis JSON with hashes, configuration, evidence and results | Analyst report; does not certify authenticity |
| Batch CSV export | Select scored recordings and export IDs/scores | Official sponsor columns/scale/order are not yet provided |
| AI interpretation | Request a Grok brief linked to recorded measurements and save it with the result | Integration tested; key absent at last status check, so live output not yet reviewed |
| Independent model evaluation | Compare baseline and candidate on separate selection/acceptance data | Command-line reports, not a web dashboard; real cluster training is running; independent results pending |
| Error breakdowns | Compare missed synthetic and falsely flagged genuine recordings by attack and codec | Descriptive acceptance report; small or single-class slices have limited meaning |

The speech detector makes the numerical assessment. Grok explains the supplied measurements; it cannot change the score or verify a speaker's identity or the truth of a statement.

## Demonstration sequence

1. Choose a known recording or upload an unfamiliar permitted recording. Show actual processing and the result's model/provenance.
2. Compare the reference label with the prediction where a label is available. Explain any miss directly.
3. Play a high-scoring interval and inspect the evidence. Do not call it an exact edit location.
4. Make a compressed or noisy copy. Listen to both and show how the measured assessment changes.
5. When Grok is configured and reviewed, generate the evidence brief and check its references.
6. Export the investigation. Present the separate baseline/candidate acceptance report once real evaluation is complete.

The distinctive combination is inspectable audio evidence, an actual robustness comparison and a reproducible report tied to a measured detector. The next useful improvement is a demonstrably better detector, not more decorative controls.

## Ordered remaining work

- **Phase 3A — complete for the public run:** official train/dev `aa` archives staged and 14,000 selected files audited, with separate training/selection/acceptance manifests. Actual subset coverage and limitations are recorded in the run ledger.
- **Phase 3B — running:** adapt AASIST-L within the one-node/one-GPU five-hour allocation; job 4503646 has started and saved a checkpoint. No training from scratch or multi-node sweep.
- **Phase 3C:** compare frozen models at selection-chosen thresholds; review aggregate and attack/codec errors, confidence intervals and serving performance. Only then consider a web-model replacement with rollback.
- **Phase 2 follow-through:** show the accepted model's measured validation summary and verify live Grok wording. Keep unsupported cases and low-score limitations visible.
- **Phases 4/5:** finish responsive/restart/export QA, rehearse, freeze the pipeline and adapt CSV to official sponsor requirements.

Speaker-reference comparison and external-source factual-claim review remain later extensions. They need their own inputs, models/evidence and validation. Neither is currently implemented or part of the synthesis score. Manipulation subtype remains undetermined until appropriate labeled evaluation supports it.
