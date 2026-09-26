"""The offline full-AASIST comparison stays separate from the web detector."""

import csv
import json
import math
import wave

import numpy as np
import pytest

from echotrace import candidate


def _wav(path, seconds):
    rate = 16_000
    samples = (10000 * np.sin(np.arange(round(seconds * rate)) * 2 * math.pi * 230 / rate)).astype("<i2")
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(samples.tobytes())


def _manifest(tmp_path):
    _wav(tmp_path / "a.wav", 0.5)
    _wav(tmp_path / "b.wav", 8.7)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("file_id,path,label\na,a.wav,0\nb,b.wav,1\n")
    return manifest


def test_candidate_scores_all_windows_and_writes_reviewable_metrics(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    calls = []

    def fake_window(samples):
        assert len(samples) == 64_600
        calls.append(1)
        score = [0.2, 0.6, 0.8, 1.0][len(calls) - 1]
        return {"score": score, "logits": [float(len(calls)), -float(len(calls))]}

    monkeypatch.setattr(candidate, "score_window", fake_window)
    monkeypatch.setattr(candidate, "verify_weights", lambda: "a" * 64)
    output = tmp_path / "candidate-run"
    assert candidate.main([str(manifest), "--root", str(tmp_path), "--output", str(output)]) == 0
    rows = list(csv.DictReader((output / "predictions.csv").open()))
    assert rows[0]["synthetic_score"] == "0.2"
    assert float(rows[1]["synthetic_score"]) == pytest.approx(0.8)
    details = json.loads((output / "details.json").read_text())
    assert [len(item["intervals"]) for item in details["files"]] == [1, 3]
    assert details["files"][1]["intervals"][-1]["end_s"] == pytest.approx(8.7)
    assert details["files"][1]["intervals"][0]["raw_logits"] == [2.0, -2.0]
    assert all(item["sha256"] for item in details["files"])
    assert details["model"]["name"] == "AASIST"
    assert details["model"]["weights_sha256"] == "a" * 64
    metrics = json.loads((output / "metrics.json").read_text())
    assert metrics["sample_count"] == 2
    assert metrics["roc_auc"] == 1.0


def test_candidate_requires_fresh_output_and_never_overwrites_source(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(candidate, "score_window", lambda _: pytest.fail("scoring started"))
    for output in (tmp_path, tmp_path / "a.wav", tmp_path / "existing"):
        if output.name == "existing":
            output.mkdir()
        assert candidate.main([str(manifest), "--root", str(tmp_path), "--output", str(output)]) == 2
    assert manifest.read_text().startswith("file_id,path,label")


def test_candidate_missing_checkpoint_does_not_download(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(candidate, "WEIGHTS_PATH", tmp_path / "missing.pth")
    monkeypatch.setattr(candidate.urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    output = tmp_path / "run"
    assert candidate.main([str(manifest), "--root", str(tmp_path), "--output", str(output)]) == 2
    assert not output.exists()


def test_candidate_rejects_bad_checkpoint_before_loading(tmp_path, monkeypatch):
    checkpoint = tmp_path / "AASIST.pth"
    checkpoint.write_bytes(b"tampered")
    monkeypatch.setattr(candidate, "WEIGHTS_PATH", checkpoint)
    with pytest.raises(RuntimeError, match="hash|checksum"):
        candidate.verify_weights()
