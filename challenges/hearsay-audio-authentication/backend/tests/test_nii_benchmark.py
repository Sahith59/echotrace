from __future__ import annotations

import csv
import hashlib

import numpy as np
import pytest

from echotrace import nii_benchmark


def test_fixed_threshold_metrics_and_failed_rows_are_preserved(tmp_path, monkeypatch):
    root = tmp_path / "dataset"
    (root / "audio").mkdir(parents=True)
    rows = []
    scores = iter(([0.9] * 800) + ([0.1] * 200) + ([0.9] * 50) + ([0.1] * 949))
    for index in range(2_000):
        label = 1 if index < 1_000 else 0
        path = root / "audio" / f"{index}.wav"
        path.write_bytes(b"audio")
        rows.append({"file_id": str(index), "path": f"audio/{index}.wav", "label": str(label),
                     "duration_s": "1.0", "sha256": hashlib.sha256(b"audio").hexdigest()})
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0])
        writer.writeheader(); writer.writerows(rows)
    monkeypatch.setattr(nii_benchmark, "MANIFEST_SHA256", hashlib.sha256(manifest.read_bytes()).hexdigest())
    monkeypatch.setattr(nii_benchmark, "_load_samples", lambda path: np.ones(16_000, dtype=np.float32))
    calls = 0
    def scorer(_samples):
        nonlocal calls
        calls += 1
        if calls == 2_000:
            raise ValueError("explicit failure")
        return {"score": next(scores)}

    report = nii_benchmark.evaluate(manifest, root, tmp_path / "out", scorer)
    assert report["protocol"]["threshold"] == 0.5
    assert report["metrics"]["recall"] == 0.8
    assert report["metrics"]["fpr"] == pytest.approx(50 / 999)
    assert report["coverage"]["failed"] == 1
    assert report["coverage"]["errors"] == {"explicit failure": 1}
    assert report["gate"] == {"recall_passed": True, "fpr_passed": False, "coverage_passed": False, "eligible_for_review": False}
    with (tmp_path / "out" / "scores.csv").open(newline="") as source:
        output = list(csv.DictReader(source))
    assert len(output) == 2_000
    assert output[-1]["error"] == "explicit failure"


def test_changed_audio_is_retained_as_an_integrity_failure(tmp_path, monkeypatch):
    root = tmp_path / "dataset"
    (root / "audio").mkdir(parents=True)
    audio = root / "audio" / "sample.wav"
    audio.write_bytes(b"changed")
    rows = [{"file_id": str(index), "path": "audio/sample.wav", "label": str(index % 2),
             "duration_s": "1.0", "sha256": hashlib.sha256(b"expected").hexdigest()}
            for index in range(2_000)]
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0])
        writer.writeheader(); writer.writerows(rows)
    monkeypatch.setattr(nii_benchmark, "MANIFEST_SHA256", hashlib.sha256(manifest.read_bytes()).hexdigest())
    monkeypatch.setattr(nii_benchmark, "candidate_status", lambda: {})

    report = nii_benchmark.evaluate(manifest, root, tmp_path / "out", lambda _: {"score": 0.5})

    assert report["coverage"]["eligible"] == 0
    assert report["coverage"]["errors"] == {"audio_sha256_mismatch": 2_000}
    assert report["gate"]["eligible_for_review"] is False
