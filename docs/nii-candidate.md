# NII wav2vec primary adapter

Status: selected as the prototype's primary detector after reference parity and the predeclared frozen-benchmark absolute gates passed. This scoped serving choice does not establish sponsor accuracy, calibration, or scientific superiority over every alternative.

## Pinned inputs and evaluation boundary

- Model: `nii-yamagishilab/wav2vec-small-anti-deepfake`
- Hugging Face revision: `9a13264b5dcc827a8d5a4f8e01fccefa392f886b`
- Safetensors SHA-256: `828ee456122f86d5d631cb7895a10e5c62c78a4fcb8a8b1c42cb5838a9abcfe0`
- Official source revision: `0dea622bde8f064c8ee5a557f2598643123fc6b6`
- Checkpoint license: CC BY-NC-SA 4.0. Code license: BSD-3-Clause.

The official training inventory includes ASVspoof5. ASVspoof5 results therefore cannot be treated as independent evaluation of this checkpoint. The adapter emits an uncalibrated class-0 fake softmax and makes no authenticity, identity or factual-truth claim.

## Predeclared reference parity gate

Before any reference results are inspected, the acceptance limits are fixed at maximum absolute logit difference `1e-3` and maximum absolute fake-probability difference `1e-4`. Both implementations must use CPU FP32 on the same five fixed inputs: two public genuine clips, two public synthetic clips and one generated tone. Any excess requires investigation; the tolerances must not be relaxed.

The official reference must run in an isolated x86 Linux Python 3.9 CPU environment with the pinned NII source and its pinned fairseq dependency. Old fairseq and numerical packages must never be installed in the live ECHOTRACE environment.

## RED checkpoint

`uv run pytest -q tests/test_nii_candidate.py` failed during collection because `echotrace.nii_candidate` did not exist. This is the expected pre-implementation failure for the committed candidate contract.

## GREEN checkpoint

The candidate adapter strictly mapped all 211 inference tensors into the pinned Transformers wav2vec model, loaded the two classifier tensors separately and scored class 0 as fake. The seven unused tensors are Fairseq pretraining quantizer/projection state. Scoring uses the complete mono 16 kHz waveform, official whole-waveform layer normalization and mean frame pooling. Inputs below the 400-sample convolutional receptive field or above 30 seconds fail explicitly and are never padded or truncated.

The ignored local checkpoint lives at `backend/artifacts/nii-model/model.safetensors`. `setup_candidate_weights()` is the only network-enabled setup path; `candidate_status()` and `score_samples()` use only the checksum-verified local file. CPU inference is fixed to four Torch threads on first candidate load.

Official reference scoring ran on x86 Linux, CPU FP32, Python 3.9, Torch 2.6.0+cpu, NumPy 1.21.2, NII source `0dea622bde8f064c8ee5a557f2598643123fc6b6` and fairseq `862efab86f649c04ea31545ce28d13c59560113d`. The same fixed bundle had SHA-256 `f4e7250aa2053d7639334d47f6be7b9699afb4a1f88c034fd44f8530a043e12a`.

Parity passed without changing the predeclared limits:

- Five of five fixed inputs compared.
- Maximum absolute logit difference: `3.790855407714844e-05` (limit `1e-3`).
- Maximum absolute fake-probability difference: `6.183981895446777e-07` (limit `1e-4`).

Local focused verification: `uv run pytest -q tests/test_nii_candidate.py` → 8 passed. The first full backend run reached 253 passing tests and six unrelated claim-provider failures during concurrent provider work; a later root integration run reported the full backend green. This paragraph records the historical candidate milestone. The adapter is now selected by `pipeline.py` through `primary_detector.py`.

## Frozen external benchmark replication

After parity passed, the adapter scored the locked 2,000-row In-the-Wild manifest at the predeclared threshold `0.5`. Job `4504662` completed on CPU in 8 minutes 46 seconds with 2,000/2,000 model inputs scored: AUROC `0.9925`, recall `0.937`, and false-positive rate `0.024`. These meet the predeclared recall (`>=0.80`), FPR (`<=0.05`) and complete model-coverage gates. No threshold was selected on this benchmark.

All 2,000 source files were rehashed against the manifest after the run; every hash matched. The runner now performs this check before scoring each file in future runs and retains a mismatch as an explicit failure row. The frozen set contains one quiet file. It remains in these model-only metrics, while a live-app comparison must exclude it from both models' denominators because the shared app quality gate rejects it.

This is benchmark replication, not sponsor validation, and it was not used for fitting. Upstream pretraining overlap is unknown. The result supported a prototype serving decision; paired common-eligibility AASIST results, unseen-corpus generalization and calibration remain open. Evidence is recorded in `challenges/hearsay-audio-authentication/reports/nii-inwild-2k/benchmark.json`, and the decision boundary is documented in [model serving decision](model-serving-decision.md).
