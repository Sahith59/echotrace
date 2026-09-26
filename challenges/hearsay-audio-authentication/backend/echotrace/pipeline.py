"""Shared analysis pipeline for API and batch clients."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import numpy as np

from .audio import SAMPLE_RATE, decode_audio, measure_audio, waveform_buckets
from .model import WINDOW_SAMPLES, model_status, score_window


def _windows(samples: np.ndarray):
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
    intervals = []
    score = None
    if too_quiet:
        pass
    elif not status["available"]:
        limitations.append(status["reason"])
    else:
        stage("detector")
        scores = []
        for window_start, window_end, window in _windows(samples):
            output = score_window(window)
            interval_score = output["score"]
            scores.append(interval_score)
            intervals.append({
                "start_s": round(window_start / SAMPLE_RATE, 5),
                "end_s": round(window_end / SAMPLE_RATE, 5),
                "score": interval_score,
                "raw_logits": output["logits"],
                "score_kind": "uncalibrated",
            })
        stage("aggregation")
        score = float(np.mean(scores))
        if len(scores) > 1:
            limitations.append("File score is the mean of full-coverage window scores; this aggregation has not been validated on sponsor data.")
        limitations.append("Window scores are assessments of their intervals, not verified edit boundaries.")
    result = {
        "schema_version": "1.0",
        "pipeline_version": "0.1.0",
        "input": input_info,
        "synthetic_score": score,
        "score_kind": "uncalibrated" if score is not None else "unavailable",
        "model": {key: status[key] for key in (
            "name", "version", "upstream_revision", "weights_sha256", "config_sha256", "device")},
        "aggregation": {
            "method": "mean_window_spoof_softmax",
            "window_samples": WINDOW_SAMPLES,
            "hop_samples": WINDOW_SAMPLES,
            "tail_policy": "end_anchored_overlap",
            "short_input_policy": "repeat_pad",
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
