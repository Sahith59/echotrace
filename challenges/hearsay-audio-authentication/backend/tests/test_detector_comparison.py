import hashlib
import threading
import json

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from echotrace.api import create_app
from echotrace import detector_comparison


WEIGHTS_SHA = "b" * 64


def status(available=True):
    return {
        "name": "NII wav2vec-small-anti-deepfake",
        "version": "9a13264b5dcc",
        "upstream_revision": "9a13264b5dcc827a8d5a4f8e01fccefa392f886b",
        "source_revision": "0dea622bde8f064c8ee5a557f2598643123fc6b6",
        "weights_sha256": WEIGHTS_SHA,
        "available": available,
        "device": "cpu",
        "max_duration_s": 30,
        "parity_approved": available,
        "reason": None if available else "Release parity evidence is unavailable.",
    }


def completed(app, tmp_path, *, seconds=1.0, amplitude=.1, job_id="job"):
    path = tmp_path / f"{job_id}.wav"
    samples = (amplitude * np.sin(2 * np.pi * 220 * np.arange(round(16000 * seconds)) / 16000)).astype("float32")
    sf.write(path, samples, 16000, subtype="FLOAT")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    app.state.store.create(job_id, f"{job_id}.wav", path)
    app.state.store.update(job_id, status="completed", stage="completed", result={
        "synthetic_score": .2,
        "score_kind": "uncalibrated",
        "input": {"sha256": digest, "duration_s": seconds},
        "model": {"name": "AASIST-L", "version": "primary-v1", "weights_sha256": "a" * 64},
    })
    return path


def scorer(samples):
    assert samples.ndim == 1
    return {"score": .7, "raw_logits": [1.5, -.2], "score_kind": "uncalibrated",
            "aggregation": "whole_file_layer_norm_mean_pool"}


def test_status_and_not_generated_contract(tmp_path):
    app = create_app(root=tmp_path / "workspace", detector_comparison_scorer=scorer,
                     detector_comparison_status=lambda: status())
    completed(app, tmp_path)
    with TestClient(app) as client:
        model = client.get("/api/detector-comparison/status")
        assert model.status_code == 200
        assert model.json()["experimental"] is True
        assert model.json()["promotion_status"] == "research_only_not_promoted"
        assert model.json()["available"] is True
        assert client.get("/api/analyses/job/detector-comparison").json() == {"status": "not_generated"}


def test_generates_separate_cached_report_without_changing_primary_score(tmp_path):
    calls = []
    def counted(samples):
        calls.append(len(samples))
        return scorer(samples)
    app = create_app(root=tmp_path / "workspace", detector_comparison_scorer=counted,
                     detector_comparison_status=lambda: status())
    completed(app, tmp_path)
    with TestClient(app) as client:
        before = client.get("/api/analyses/job").json()["result"]
        response = client.post("/api/analyses/job/detector-comparison")
        assert response.status_code == 200
        report = response.json()
        assert report["status"] == "generated"
        assert report["experimental"] is True
        assert report["primary_score_unchanged"] is True
        assert report["primary_score"] == .2
        assert report["candidate_score"] == .7
        assert report["score_difference"] == .5
        assert report["raw_logits"] == [1.5, -.2]
        assert report["model"]["weights_sha256"] == WEIGHTS_SHA
        assert report["primary_model"]["name"] == "AASIST-L"
        assert report["preprocessing"]["max_duration_s"] == 30
        assert "confidence" in report["limitation"].lower()
        assert client.post("/api/analyses/job/detector-comparison").json() == report
        assert calls == [16000]
        assert client.get("/api/analyses/job").json()["result"] == before
        case = client.get("/api/analyses/job/case-report").json()
        assert case["detector_comparison"] == report
        printable = client.get("/api/analyses/job/case-report.html").text
        assert "Experimental detector comparison" in printable


def test_rejects_unavailable_model_and_changed_original(tmp_path):
    unavailable = create_app(root=tmp_path / "one", detector_comparison_scorer=scorer,
                             detector_comparison_status=lambda: status(False))
    completed(unavailable, tmp_path, job_id="missing")
    with TestClient(unavailable) as client:
        assert client.post("/api/analyses/missing/detector-comparison").status_code == 503

    app = create_app(root=tmp_path / "two", detector_comparison_scorer=scorer,
                     detector_comparison_status=lambda: status())
    path = completed(app, tmp_path, job_id="changed")
    path.write_bytes(path.read_bytes() + b"changed")
    with TestClient(app) as client:
        result = client.post("/api/analyses/changed/detector-comparison")
        assert result.status_code == 409
        assert "changed" in result.json()["detail"].lower()


def test_rejects_quiet_short_and_over_30_second_audio(tmp_path):
    app = create_app(root=tmp_path / "workspace", detector_comparison_scorer=scorer,
                     detector_comparison_status=lambda: status())
    completed(app, tmp_path, seconds=.01, job_id="short")
    completed(app, tmp_path, seconds=1, amplitude=0, job_id="quiet")
    completed(app, tmp_path, seconds=30.01, job_id="long")
    with TestClient(app) as client:
        for job in ("short", "quiet", "long"):
            response = client.post(f"/api/analyses/{job}/detector-comparison")
            assert response.status_code == 422, (job, response.text)


def test_concurrent_generation_returns_409(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    def slow(samples):
        entered.set()
        assert release.wait(3)
        return scorer(samples)
    app = create_app(root=tmp_path / "workspace", detector_comparison_scorer=slow,
                     detector_comparison_status=lambda: status())
    completed(app, tmp_path)
    outcomes = []
    def request():
        with TestClient(app) as client:
            outcomes.append(client.post("/api/analyses/job/detector-comparison").status_code)
    thread = threading.Thread(target=request)
    thread.start()
    assert entered.wait(2)
    with TestClient(app) as client:
        assert client.post("/api/analyses/job/detector-comparison").status_code == 409
    release.set()
    thread.join(3)
    assert outcomes == [200]


def test_parity_marker_is_hash_and_schema_gated(tmp_path, monkeypatch):
    marker = tmp_path / "parity.json"
    payload = {"passed": True, "case_count": 5, "max_abs_logit_difference": .0005,
               "logit_tolerance": .001, "max_abs_probability_difference": .00005,
               "probability_tolerance": .0001}
    marker.write_text(json.dumps(payload))
    monkeypatch.setattr(detector_comparison, "PARITY_SHA256", hashlib.sha256(marker.read_bytes()).hexdigest())
    assert detector_comparison._parity_status(marker)["approved"] is True
    payload["case_count"] = 4
    marker.write_text(json.dumps(payload))
    assert detector_comparison._parity_status(marker)["approved"] is False
