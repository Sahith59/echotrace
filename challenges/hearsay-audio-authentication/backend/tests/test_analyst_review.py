import csv
import hashlib
import io

from fastapi.testclient import TestClient

from echotrace.api import create_app


MODEL = {"name": "NII wav2vec-small-anti-deepfake", "version": "v1", "weights_sha256": "a" * 64}


def completed(app, tmp_path, job_id="case", *, model=MODEL, score=.3, content=b"audio"):
    path = tmp_path / f"{job_id}.wav"
    path.write_bytes(content)
    app.state.store.create(job_id, f"{job_id}.wav", path)
    app.state.store.update(job_id, status="completed", stage="completed", result={
        "synthetic_score": score,
        "score_kind": "uncalibrated",
        "input": {"sha256": hashlib.sha256(content).hexdigest()},
        "model": model,
    })


def test_review_lifecycle_is_separate_versioned_and_exported(tmp_path):
    app = create_app(root=tmp_path / "workspace")
    completed(app, tmp_path)
    with TestClient(app) as client:
        initial = client.get("/api/analyses/case/analyst-review")
        assert initial.json() == {"status": "needs_review", "notes": "", "version": 0, "updated_at": None}

        saved = client.put("/api/analyses/case/analyst-review", json={
            "status": "corroboration_requested",
            "notes": "=Seek an independent source",
            "expected_version": 0,
        })
        assert saved.status_code == 200
        assert saved.json()["version"] == 1
        assert saved.json()["status"] == "corroboration_requested"

        stale = client.put("/api/analyses/case/analyst-review", json={
            "status": "review_complete", "notes": "Done", "expected_version": 0,
        })
        assert stale.status_code == 409
        assert stale.json()["detail"]["current_version"] == 1

        detail = client.get("/api/analyses/case").json()
        assert detail["result"]["synthetic_score"] == .3
        assert "analyst_review" not in detail["result"]
        assert detail["analyst_review"]["notes"] == "=Seek an independent source"
        history = client.get("/api/analyses").json()
        assert history[0]["analyst_review"]["version"] == 1

        case = client.get("/api/analyses/case/case-report").json()
        assert case["analyst_review"]["status"] == "corroboration_requested"
        page = client.get("/api/analyses/case/case-report.html").text
        assert "corroboration requested" in page
        assert "Seek an independent source" in page

        exported = client.post("/api/exports", json={"ids": ["case"]})
        row = next(csv.DictReader(io.StringIO(exported.text)))
        assert row["analyst_review_status"] == "corroboration_requested"
        assert row["analyst_review_notes"] == "'=Seek an independent source"
        assert row["analyst_review_version"] == "1"


def test_review_rejects_incomplete_job_invalid_status_and_oversized_notes(tmp_path):
    app = create_app(root=tmp_path)
    path = tmp_path / "pending.wav"
    path.write_bytes(b"audio")
    app.state.store.create("pending", "pending.wav", path)
    with TestClient(app) as client:
        assert client.get("/api/analyses/missing/analyst-review").status_code == 404
        assert client.get("/api/analyses/pending/analyst-review").status_code == 409
        assert client.put("/api/analyses/pending/analyst-review", json={
            "status": "approved", "notes": "", "expected_version": 0,
        }).status_code == 422
        completed(app, tmp_path, "complete")
        assert client.put("/api/analyses/complete/analyst-review", json={
            "status": "review_complete", "notes": "x" * 8001, "expected_version": 0,
        }).status_code == 422


def test_csv_rejects_mixed_or_unidentified_models(tmp_path):
    app = create_app(root=tmp_path / "workspace")
    completed(app, tmp_path, "one")
    completed(app, tmp_path, "two", model={"name": "AASIST-L", "weights_sha256": "b" * 64})
    with TestClient(app) as client:
        result = client.post("/api/exports", json={"ids": ["one", "two"]})
        assert result.status_code == 409
        assert "same identified model" in result.json()["detail"]
