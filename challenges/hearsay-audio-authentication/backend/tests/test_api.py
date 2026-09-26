import csv
import io
import time

from fastapi.testclient import TestClient

from echotrace.api import Store, create_app


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
