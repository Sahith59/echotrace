# Primary detector serving decision

## Decision

ECHOTRACE uses the pinned NII `wav2vec-small-anti-deepfake` checkpoint as its primary detector for the prototype. This is a scoped product serving choice, not scientific model promotion, sponsor validation, or evidence that the training-specific contract in `acceptance.py` passed.

The choice is based on two completed checks:

- The Transformers adapter matched the isolated official Fairseq reference on five fixed CPU FP32 inputs. Maximum absolute logit difference was `3.790855407714844e-05` against the predeclared `1e-3` limit; maximum fake-probability difference was `6.183981895446777e-07` against the predeclared `1e-4` limit.
- On the frozen 2,000-row In-the-Wild replication at the predeclared `0.5` threshold, the model scored all 2,000 inputs with recall `0.937`, false-positive rate `0.024`, and AUROC `0.9925`. This passed the predeclared absolute recall (`>=0.80`), false-positive-rate (`<=0.05`), and model-coverage gates. All input hashes matched the frozen manifest.

One quiet file is included in the model-only replication metrics but is rejected by the application quality gate. A paired serving comparison must therefore use the 1,999-row common app-eligible subset for both models. That AASIST comparison is pending and no baseline improvement is claimed here.

## Boundaries and open evidence

The In-the-Wild result is a benchmark replication, not sponsor data, and was not used to fit or select the threshold. The benchmark was previously evaluated by the checkpoint authors, and overlap with upstream pretraining is unknown. The [NII training inventory](https://huggingface.co/nii-yamagishilab/wav2vec-small-anti-deepfake) includes **ASVspoof5 and MLAAD**, so neither the ASVspoof5 adaptation holdout nor the 24 MLAAD demo clips independently validate this checkpoint.

A later, different-corpus [ArA-DF-2026 stress check](ara-df-2026-stress-check.md) found **61.2% synthetic recall and 7.0% genuine false positives** for NII on a fixed 198 eligible / 200 selected Arabic Track-2 development-test sample at the unchanged 0.5 threshold (AUROC 0.9018). Historical AASIST-L scored those same 198 eligible IDs with 78.6% recall and 93.0% false positives (AUROC 0.3485). This is evidence of a domain-shift limitation and fails the desired 80% recall / <=5% false-positive goals. It does not undo the earlier parity result, but it sharply narrows the claim supported by the earlier In-the-Wild replication. Serving has not been retuned on this inspected sample.

The following remain open:

- retrieval of the separate paired NII/AASIST metrics on the same 1,999 In-the-Wild app-eligible files; the ArA-DF-2026 paired sample above is complete;
- a broader, representative and untouched source-diverse corpus with a separately frozen selection/test protocol; the ArA-DF-2026 sample is narrow and has now been inspected;
- codec, speaker, generator, language, channel, and duration slices;
- calibration of the displayed likelihood and an operating threshold tied to the product's error costs;
- representative CPU latency, memory, concurrency, and failure testing in the deployment environment.

Outputs remain uncalibrated synthetic-speech detector scores. They do not establish speaker identity, authenticity, edit location, intent, or factual truth.

## Rollback

There is no runtime, configuration, or environment-variable detector switch. Commit `fe8b8a5` statically selects `primary_detector.py` from `pipeline.py`; the pinned legacy AASIST adapter remains in `backend/echotrace/model.py` for offline reproducibility.

Rollback requires reverting the NII primary change to pre-promotion commit `d4c7a57` (or reverting `fe8b8a5` together with its RED contract commit `3c0b54f`), redeploying, and restarting the API process. Preserve completed reports because each report records its model identity and weights hash. Before completing rollback, run the backend test suite and one real AASIST inference with the pinned weights SHA-256 `814331d088032bb4c3fa61cc014789eadeed464209dd094ab3a2dd6ffbdce27a`.
