# Research detector comparison

The workbench can run a second learned speech detector on the same original recording. Its purpose is to make disagreement visible and give the analyst a reproducible second assessment. It does not average scores, change the original result, or promote an experimental model into the primary pipeline.

## Analyst journey

Open a completed original recording and choose **Run second detector**. The two model scores appear separately, with model identities and a clear experimental label. Inspect **Comparison provenance** and **Detector validation** before interpreting a disagreement. The primary detector's Groq explanation remains separate and explicitly covers primary measurements only.

The second model is the pinned NII `wav2vec-small-anti-deepfake` checkpoint. It uses the entire decoded waveform, official layer normalization and mean pooling. It supports at most 30 seconds, rejects quiet or very short recordings, and runs locally. Neither output is a calibrated probability of authenticity. The original AASIST-L workflow still supports its existing two-minute limit.

A case JSON or printable case report includes the separate comparison when generated. The main analyst CSV continues to contain the original primary score; it does not silently substitute the research model. Official sponsor export still requires the sponsor's actual schema and final model decision.

## Reproducible setup

Install backend dependencies using the normal project setup. Then explicitly fetch the optional checkpoint from its pinned author release:

```sh
uv run python -c 'from echotrace.nii_candidate import setup_candidate_weights; setup_candidate_weights()'
```

Run this from `challenges/hearsay-audio-authentication/backend`. The approximately 380 MB checkpoint is cached locally and SHA-256 checked. It is not bundled in Git, never downloaded by a scoring request, and carries the author's CC BY-NC-SA 4.0 license. See [candidate protocol](nii-candidate.md) for exact revisions, hashes and reference parity.

A pinned reference-parity report ships with the application; missing or mismatched proof prevents the comparison from running. Reference parity verifies implementation consistency, not detector accuracy. Public-data performance is a separate benchmark.

## Integrity and failure behavior

The API verifies the original's content hash and stores comparison output in a separate SQLite table. Cached results must match original content, primary result/model and candidate checkpoint. Concurrent comparison requests are serialized; unsupported input, missing weights, failed parity or changed source returns an explicit error. No fake fallback score is produced. Source recordings and the primary analysis remain unchanged.

Frontend checks cover on-demand execution, saved comparison loading, unavailable model, input rejection/retry, server recovery and switching recordings during an in-flight request. Backend checks cover cache integrity, immutable primary scores, bounds, quiet files, invalid model outputs and report inclusion. These checks establish application behavior; detection performance is recorded separately in the frozen external benchmark.

## Demonstration limits

On two already inspected public examples, the NII candidate scored the known synthetic clip at 0.9999683 and the known genuine clip at 0.0192228. These are diagnostic observations, not an accuracy estimate and not independent evaluation data. Do not quote them as a population success rate or sponsor performance.

## Frozen public benchmark

CPU job4504662 completed all2,000 recordings at a predeclared threshold of0.5: recall93.7%, false-positive rate2.4%, AUROC0.9925, zero scoring failures. This balanced model-only benchmark retains one quiet file that the application rejects. The common app-eligible comparison must use1,999 rows. The authors previously evaluated this public dataset, so this is benchmark replication, not a new blind test or sponsor validation. See [sanitized benchmark evidence](../challenges/hearsay-audio-authentication/reports/nii-inwild-2k/benchmark.json). The primary serving model has not changed.
