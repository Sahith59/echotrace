# NII wav2vec candidate adapter

Status: candidate-only implementation. It is not imported by the serving pipeline and does not establish better detection performance.

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

Pending implementation, official-reference comparison and verification.
