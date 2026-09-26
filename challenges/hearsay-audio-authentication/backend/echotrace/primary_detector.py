"""Registry entry for the promoted, pinned NII whole-file primary detector."""
from __future__ import annotations

import hashlib
import json

import numpy as np

from .detector_comparison import PARITY_PROVENANCE, PARITY_SHA256, _parity_status
from .nii_candidate import (
    HF_REPOSITORY,
    HF_REVISION,
    MAX_SAMPLES,
    MAX_DURATION_S,
    MIN_SAMPLES,
    SAMPLE_RATE,
    SOURCE_REVISION,
    WEIGHTS_SHA256,
    candidate_status,
    score_samples,
    setup_candidate_weights,
)


PRIMARY_CONFIG = {
    "schema_version": 1,
    "detector": "nii-yamagishilab-wav2vec-small-anti-deepfake",
    "repository": HF_REPOSITORY,
    "model_revision": HF_REVISION,
    "source_revision": SOURCE_REVISION,
    "weights_sha256": WEIGHTS_SHA256,
    "fake_class_index": 0,
    "sample_rate": SAMPLE_RATE,
    "min_samples": MIN_SAMPLES,
    "max_samples": MAX_SAMPLES,
    "max_duration_s": MAX_DURATION_S,
    "preprocessing": "mono_16khz_float32_whole_file_layer_norm",
    "aggregation": "whole_file_layer_norm_mean_pool",
    "padding": "none",
    "truncation": "rejected",
    "score_kind": "uncalibrated",
}
CONFIG_SHA256 = hashlib.sha256(
    json.dumps(PRIMARY_CONFIG, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


class PrimaryDetectorError(ValueError):
    """The promoted detector cannot produce a defensible result for this input."""


def model_status() -> dict:
    base = candidate_status()
    parity = _parity_status()
    available = bool(base.get("available") and parity["approved"])
    return {
        **base,
        "available": available,
        "reason": None if available else (base.get("reason") or parity["reason"]),
        "role": "primary",
        "config_sha256": CONFIG_SHA256,
        "parity_approved": parity["approved"],
        "parity_sha256": PARITY_SHA256,
        "parity_provenance": PARITY_PROVENANCE,
        "min_samples": MIN_SAMPLES,
        "score_kind": "uncalibrated",
        "preprocessing": PRIMARY_CONFIG["preprocessing"],
        "aggregation": PRIMARY_CONFIG["aggregation"],
        "promotion_status": "primary_public_benchmark_replication",
        "evaluation_boundary": (
            "Promoted from a frozen public In-the-Wild replication, not sponsor validation or calibration. "
            "The checkpoint authors previously evaluated this dataset."
        ),
    }


def setup_primary_weights():
    path = setup_candidate_weights()
    status = model_status()
    if not status["available"]:
        raise PrimaryDetectorError(status["reason"] or "Pinned NII primary detector is unavailable.")
    return path


def score_primary(samples: np.ndarray) -> dict:
    samples = np.asarray(samples)
    if samples.ndim != 1 or not np.all(np.isfinite(samples)):
        raise PrimaryDetectorError("Primary detector input must be finite, one-dimensional audio.")
    if samples.size < MIN_SAMPLES:
        raise PrimaryDetectorError("Primary detector requires at least 400 samples.")
    if samples.size > MAX_SAMPLES:
        raise PrimaryDetectorError("Primary detector supports at most 30 seconds and does not truncate audio.")
    status = model_status()
    if not status["available"]:
        raise PrimaryDetectorError(status["reason"] or "Pinned NII primary detector is unavailable.")
    try:
        return score_samples(samples)
    except (RuntimeError, ValueError) as exc:
        raise PrimaryDetectorError(f"Primary detector could not score the recording: {exc}") from None
