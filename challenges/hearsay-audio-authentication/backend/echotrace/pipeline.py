"""Shared analysis pipeline for API and batch clients."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import numpy as np

from .audio import SAMPLE_RATE, decode_audio, measure_audio, waveform_buckets
from .model import WINDOW_SAMPLES
from .primary_detector import PrimaryDetectorError, model_status, score_primary


def _windows(samples: np.ndarray):
    """Legacy AASIST full-coverage windows for offline reproducibility only."""
    if len(samples) <= WINDOW_SAMPLES:
        window = np.resize(samples, WINDOW_SAMPLES).astype(np.float32, copy=False)
        yield 0, len(samples), window
        return
    starts = list(range(0, len(samples) - WINDOW_SAMPLES + 1, WINDOW_SAMPLES))
    last = len(samples) - WINDOW_SAMPLES
    if starts[-1] != last:
        starts.append(last)
    for start in starts:
        yield start, start + WINDOW_SAMPLES, samples[start:start + WINDOW_SAMPLES]


def analyze_file(path: Path, progress: Callable[[str], None] | None = None) -> dict:
    start_time = time.monotonic()
    def stage(value: str) -> None:
        if progress is not None:
            progress(value)

    stage("decoding")
    samples, input_info = decode_audio(Path(path))
    stage("quality")
    evidence, quality_limitations, too_quiet = measure_audio(samples)
    status = model_status()
    limitations = [
        "The score is uncalibrated on the sponsor dataset and does not authenticate origin or identity.",
        "Speech presence is not independently verified; the detector was trained for speech anti-spoofing.",
    ]
    limitations.extend(quality_limitations)
    if too_quiet:
        raise PrimaryDetectorError("Audio is too quiet for the primary detector.")
    if len(samples) < 400:
        raise PrimaryDetectorError("Primary detector requires at least 400 samples.")
    if len(samples) > 30 * SAMPLE_RATE:
        raise PrimaryDetectorError("Audio exceeds the primary detector's 30-second whole-file limit; no truncation was performed.")
    if not status["available"]:
        raise PrimaryDetectorError(status["reason"] or "Pinned NII primary detector is unavailable.")
    stage("detector")
    output = score_primary(samples)
    score = float(output["score"])
    intervals = [{
        "start_s": 0.0,
        "end_s": input_info["duration_s"],
        "score": score,
        "raw_logits": [float(value) for value in output["raw_logits"]],
        "score_kind": "uncalibrated",
        "scope": "whole_file",
    }]
    stage("aggregation")
    limitations.append("The primary detector scores the complete recording once; it does not localize edits or verified boundaries.")
    limitations.append("Public In-the-Wild results replicate a benchmark previously evaluated by the checkpoint authors and are not sponsor validation.")
    result = {
        "schema_version": "1.1",
        "pipeline_version": "0.2.0",
        "input": input_info,
        "synthetic_score": score,
        "score_kind": "uncalibrated" if score is not None else "unavailable",
        "model": {key: status[key] for key in (
            "name", "version", "upstream_revision", "source_revision", "weights_sha256",
            "config_sha256", "device", "role", "parity_sha256")},
        "aggregation": {
            "method": "whole_file_layer_norm_mean_pool",
            "sample_rate": SAMPLE_RATE,
            "min_samples": 400,
            "max_duration_s": 30,
            "padding": "none",
            "truncation": "rejected",
            "validated_on_sponsor_data": False,
        },
        "manipulation_type": "undetermined",
        "waveform": waveform_buckets(samples),
        "intervals": intervals,
        "evidence": evidence,
        "limitations": limitations,
        "runtime_s": round(time.monotonic() - start_time, 3),
    }
    stage("completed")
    return result
