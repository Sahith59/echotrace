# Legacy detector comparison

The comparison feature is retained for analyses originally scored by the legacy pinned AASIST-L primary. On those historical analyses it can run the pinned NII detector, keep both model identities visible, and preserve disagreement without averaging or changing either score.

## Analyst journey

Open a completed legacy AASIST-L original recording and choose **Run second detector**. The saved AASIST-L primary and NII research scores appear separately, with model identities and a clear historical research label. Inspect **Comparison provenance** and **Detector validation** before interpreting a disagreement. The primary detector's Groq explanation remains separate and explicitly covers primary measurements only.

New analyses already use the pinned NII `wav2vec-small-anti-deepfake` checkpoint as primary, so the API rejects NII-on-NII comparison as meaningless. It does not yet run AASIST-L as a new secondary detector. A paired common-eligibility AASIST comparison remains pending. Neither historical output is a calibrated probability of authenticity.

A case JSON or printable case report includes a historical comparison when one was generated. The analyst CSV keeps the analysis's recorded primary score and model version; it does not silently substitute a comparison score. Official sponsor export still requires the sponsor's actual schema.

## Historical NII comparison setup

Install backend dependencies using the normal project setup. Then explicitly fetch the optional checkpoint from its pinned author release:

```sh
uv run python -c 'from echotrace.nii_candidate import setup_candidate_weights; setup_candidate_weights()'
```

Run this from `challenges/hearsay-audio-authentication/backend`. The approximately 380 MB checkpoint is cached locally and SHA-256 checked. It is not bundled in Git, never downloaded by a scoring request, and carries the author's CC BY-NC-SA 4.0 license. See [candidate protocol](nii-candidate.md) for exact revisions, hashes and reference parity.

A pinned reference-parity report ships with the application; missing or mismatched proof prevents the historical comparison from running. Reference parity verifies implementation consistency, not detector accuracy. Public-data performance is a separate benchmark.

## Integrity and failure behavior

The API verifies the original's content hash and stores comparison output in a separate SQLite table. Cached results must match original content, primary result/model and candidate checkpoint. Concurrent comparison requests are serialized; unsupported input, missing weights, failed parity or changed source returns an explicit error. No fake fallback score is produced. Source recordings and the primary analysis remain unchanged.

Frontend checks cover on-demand execution, saved comparison loading, unavailable model, input rejection/retry, server recovery and switching recordings during an in-flight request. Backend checks cover cache integrity, immutable primary scores, bounds, quiet files, invalid model outputs and report inclusion. These checks establish application behavior; detection performance is recorded separately in the frozen external benchmark.

## Demonstration limits

On two already inspected public examples, the NII candidate scored the known synthetic clip at 0.9999683 and the known genuine clip at 0.0192228. These are diagnostic observations, not an accuracy estimate and not independent evaluation data. Do not quote them as a population success rate or sponsor performance.

## Frozen public benchmark

CPU job `4504662` completed all 2,000 recordings at a predeclared threshold of `0.5`: recall 93.7%, false-positive rate 2.4%, AUROC 0.9925, zero scoring failures. This balanced model-only benchmark retains one quiet file that the application rejects. A common app-eligible comparison must use 1,999 rows. The authors previously evaluated this public dataset, so this is benchmark replication, not a new blind test or sponsor validation. See [sanitized benchmark evidence](../challenges/hearsay-audio-authentication/reports/nii-inwild-2k/benchmark.json). NII is now the scoped prototype primary; see [model serving decision](model-serving-decision.md).
