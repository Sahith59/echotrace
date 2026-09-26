import csv
import hashlib
import io
import time

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from echotrace.api import Store, create_app


def test_health_advertises_primary_whole_file_duration_limit(tmp_path):
    with TestClient(create_app(tmp_path, analyzer=fake_analyzer)) as client:
        assert client.get("/api/health").json()["limits"]["max_duration_s"] == 30


def fake_analyzer(path, progress=None):
    """Explicit test double; never registered in the running application."""
    if path.read_bytes() == b"corrupt":
        raise ValueError("Unsupported recording")
    if progress:
        progress("quality analysis")
    return {"input": {"filename": path.name}, "synthetic_score": 0.25,
            "score_kind": "uncalibrated", "limitations": ["test double"]}


def wait(client, job_id):
    for _ in range(100):
        job = client.get(f"/api/analyses/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Job did not finish")


def test_upload_analysis_report_export_and_failure_isolation(tmp_path):
    with TestClient(create_app(tmp_path, fake_analyzer)) as client:
        first = client.post("/api/analyses", files={"file": ("../name.wav", b"test audio")})
        assert first.status_code == 202
        job = wait(client, first.json()["id"])
        assert job["filename"] == "name.wav"
        assert job["status"] == "completed"
        assert "path" not in job
        assert client.get(f"/api/analyses/{job['id']}/audio").content == b"test audio"
        assert client.get(f"/api/analyses/{job['id']}/report").json()["synthetic_score"] == 0.25
        bad = client.post("/api/analyses", files={"file": ("broken.wav", b"corrupt")}).json()
        assert wait(client, bad["id"])["status"] == "failed"
        assert client.post("/api/exports", json={"ids": [job["id"], bad["id"]]}).status_code == 409
        out = client.post("/api/exports", json={"ids": [job["id"]]})
        assert out.status_code == 200
        assert out.headers["x-export-kind"] == "analyst-not-sponsor-schema"
        assert list(csv.DictReader(io.StringIO(out.text)))[0]["synthetic_score"] == "0.25"
        assert client.post("/api/exports", json={"ids": [job["id"], job["id"]]}).status_code == 422
        assert client.get("/api/analyses/missing").status_code == 404


def test_empty_upload_null_score_and_invalid_transform(tmp_path):
    def limited(path, progress=None):
        return {"input": {"filename": path.name}, "synthetic_score": None}
    with TestClient(create_app(tmp_path, limited)) as client:
        assert client.post("/api/analyses", files={"file": ("empty.wav", b"")}).status_code == 422
        job = client.post("/api/analyses", files={"file": ("silence.wav", b"silence")}).json()
        wait(client, job["id"])
        assert client.post("/api/exports", json={"ids": [job["id"]]}).status_code == 409
        assert client.post(f"/api/analyses/{job['id']}/stress-tests", json={"kind": "shell"}).status_code == 422


def test_interrupted_jobs_are_recovered_and_completed_jobs_persist(tmp_path):
    store = Store(tmp_path)
    source = tmp_path / "recording.wav"
    source.write_bytes(b"test audio")
    store.create("interrupted", "recording.wav", source)
    store.update("interrupted", status="running")
    store.create("finished", "recording.wav", source)
    store.update("finished", status="completed", result={"synthetic_score": 0.1})
    with TestClient(create_app(tmp_path, fake_analyzer)) as client:
        assert client.get("/api/analyses/interrupted").json()["status"] == "failed"
        assert client.get("/api/analyses/finished").json()["status"] == "completed"
        assert client.post("/api/analyses/interrupted/retry").status_code == 202
        assert wait(client, "interrupted")["status"] == "completed"


def test_upload_limit_cleans_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr("echotrace.api.MAX_BYTES", 5)
    with TestClient(create_app(tmp_path, fake_analyzer)) as client:
        assert client.post("/api/analyses", files={"file": ("large.wav", b"123456")}).status_code == 413
        assert client.get("/api/analyses").json() == []
        assert not [p for p in tmp_path.iterdir() if p.is_dir()]


def test_stress_rejects_legacy_model_before_creating_a_job(tmp_path, monkeypatch):
    app = create_app(tmp_path / "workspace", fake_analyzer)
    source = tmp_path / "source.wav"
    source.write_bytes(b"source")
    app.state.store.create("legacy", "source.wav", source)
    app.state.store.update("legacy", status="completed", stage="completed", result={
        "synthetic_score": .2,
        "input": {"sha256": hashlib.sha256(b"source").hexdigest()},
        "model": {"name": "AASIST-L", "weights_sha256": "a" * 64},
    })
    monkeypatch.setattr("echotrace.pipeline.model_status", lambda: {
        "name": "NII wav2vec-small-anti-deepfake", "weights_sha256": "b" * 64,
    })
    with TestClient(app) as client:
        response = client.post("/api/analyses/legacy/stress-tests", json={"kind": "mp3"})
        assert response.status_code == 409
        assert "Reanalyze" in response.json()["detail"]
        assert [job["id"] for job in client.get("/api/analyses").json()] == ["legacy"]


def test_reanalysis_creates_new_job_and_preserves_original(tmp_path):
    def analyzer(path, progress=None):
        content = path.read_bytes()
        return {
            "input": {"filename": path.name, "sha256": hashlib.sha256(content).hexdigest()},
            "synthetic_score": .7,
            "model": {"name": "NII wav2vec-small-anti-deepfake", "weights_sha256": "b" * 64},
        }

    app = create_app(tmp_path / "workspace", analyzer)
    source = tmp_path / "source.wav"
    source.write_bytes(b"unchanged source")
    app.state.store.create("original", "source.wav", source)
    original_result = {
        "input": {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "synthetic_score": .2,
        "model": {"name": "AASIST-L", "weights_sha256": "a" * 64},
    }
    app.state.store.update("original", status="completed", stage="completed", result=original_result)
    with TestClient(app) as client:
        response = client.post("/api/analyses/original/reanalyze")
        assert response.status_code == 202
        new_id = response.json()["id"]
        updated = wait(client, new_id)
        assert updated["status"] == "completed"
        assert updated["reanalysis_of"] == "original"
        assert updated["result"]["reanalysis_of"] == "original"
        assert updated["result"]["synthetic_score"] == .7
        assert client.get("/api/analyses/original").json()["result"] == original_result
        assert client.post(f"/api/analyses/{new_id}/reanalyze").status_code == 422


def test_stress_result_fails_if_model_changes_after_queueing(tmp_path, monkeypatch):
    legacy = {"name": "AASIST-L", "weights_sha256": "a" * 64}
    current = {"name": "NII wav2vec-small-anti-deepfake", "weights_sha256": "b" * 64}

    def changed_analyzer(path, progress=None):
        return {
            "input": {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
            "synthetic_score": .6,
            "model": current,
        }

    app = create_app(tmp_path / "workspace", changed_analyzer)
    source = tmp_path / "source.wav"
    sf.write(source, np.full(16_000, .1, dtype=np.float32), 16_000)
    app.state.store.create("legacy", "source.wav", source)
    app.state.store.update("legacy", status="completed", stage="completed", result={
        "synthetic_score": .2,
        "input": {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "model": legacy,
    })
    monkeypatch.setattr("echotrace.pipeline.model_status", lambda: legacy)
    with TestClient(app) as client:
        response = client.post("/api/analyses/legacy/stress-tests", json={"kind": "noise"})
        assert response.status_code == 202
        derived = wait(client, response.json()["id"])
        assert derived["status"] == "failed"
        assert "primary model changed" in derived["error"]
        assert derived["result"] is None
