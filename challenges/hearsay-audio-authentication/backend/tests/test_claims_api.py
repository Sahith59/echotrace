from fastapi import FastAPI
from fastapi.testclient import TestClient

from echotrace.api import Store
from echotrace.claims_router import create_claims_router, load_claim_artifacts


class FakeTranscriber:
    def status(self):
        return {
            "available": True,
            "provider": "faster-whisper",
            "model": "test-model",
            "device": "cpu",
            "compute_type": "int8",
            "cache_state": "ready",
            "download_allowed": False,
            "max_duration_s": 120,
        }

    def transcribe(self, path):
        return {
            "text": "The bridge opened in 2020.",
            "segments": [{"id": 0, "start_s": 0.0, "end_s": 2.0, "text": "The bridge opened in 2020."}],
            "language": "en",
            "language_probability": 0.99,
            "duration_s": 2.0,
        }


class UnavailableReviewer:
    def status(self):
        return {
            "available": False,
            "provider": "xai",
            "model": "grok-test",
            "reason": "Grok is not configured.",
            "connection_verified": False,
        }

    def review(self, claim, **kwargs):
        raise AssertionError("provider must not run without consent")


def app_for(tmp_path):
    store = Store(tmp_path)
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"audio")
    store.create("job", "recording.wav", audio)
    store.update("job", status="completed", stage="completed", result={"synthetic_score": 0.99})
    app = FastAPI()
    app.include_router(create_claims_router(store, transcriber=FakeTranscriber(), reviewer=UnavailableReviewer()))
    app.state.store = store
    return app


def test_transcript_generation_correction_and_stale_claim_association(tmp_path):
    with TestClient(app_for(tmp_path)) as client:
        generated = client.post("/api/analyses/job/transcript")
        assert generated.status_code == 201
        assert generated.json()["version"] == 1
        assert generated.json()["source"] == "automatic"

        claim = client.post("/api/analyses/job/claims", json={
            "text": "The bridge opened in 2020.",
            "transcript_version": 1,
            "span": {"start_s": 0.0, "end_s": 2.0},
            "external_search_consent": False,
        })
        assert claim.status_code == 201
        assert claim.json()["verdict"] == "uncheckable"
        assert claim.json()["method"] == "manual_pending"
        assert claim.json()["stale_transcript"] is False

        corrected = client.put("/api/analyses/job/transcript", json={
            "base_version": 1,
            "segments": [{"start_s": 0.0, "end_s": 2.0, "text": "The bridge opened in 2021."}],
        })
        assert corrected.status_code == 200
        assert corrected.json()["version"] == 2
        assert corrected.json()["source"] == "analyst_corrected"
        assert corrected.json()["text"] == "The bridge opened in 2021."

        saved = client.get("/api/analyses/job/claims").json()["claims"]
        assert saved[0]["transcript_version"] == 1
        assert saved[0]["stale_transcript"] is True
        transcript = client.get("/api/analyses/job/transcript").json()
        assert transcript["version"] == 2
        assert [item["version"] for item in transcript["versions"]] == [1, 2]
        artifacts = load_claim_artifacts(client.app.state.store, "job")
        assert artifacts["transcript"]["version"] == 2
        assert artifacts["claims"][0]["stale_transcript"] is True


def test_providerless_analyst_review_is_persisted_with_distinct_provenance(tmp_path):
    with TestClient(app_for(tmp_path)) as client:
        response = client.post("/api/analyses/job/claims", json={
            "text": "The bridge opened in 2020.",
            "external_search_consent": False,
            "analyst_review": {
                "verdict": "supported",
                "rationale": "The city report states the opening year.",
                "evidence": [{
                    "url": "https://city.example/reports/bridge",
                    "title": "Bridge completion report",
                    "publisher": "City Works Department",
                    "published_at": "2020-11-02",
                    "quote": "The bridge opened to traffic in 2020.",
                    "stance": "supports",
                }],
            },
        })

        assert response.status_code == 201
        body = response.json()
        assert body["verdict"] == "supported"
        assert body["method"] == "analyst"
        assert body["provider"] is None
        assert body["evidence"][0]["provenance"] == "analyst_supplied"
        assert client.get("/api/analyses/job/claims").json()["claims"][0]["id"] == body["id"]


def test_claim_validation_and_explicit_provider_unavailability(tmp_path):
    with TestClient(app_for(tmp_path)) as client:
        unavailable = client.post("/api/analyses/job/claims", json={
            "text": "The bridge opened in 2020.",
            "external_search_consent": True,
        })
        assert unavailable.status_code == 503
        saved = client.get("/api/analyses/job/claims").json()["claims"]
        assert saved[0]["status"] == "error"
        assert saved[0]["error"] == "Grok is not configured."

        assert client.post("/api/analyses/job/claims", json={
            "text": "Claim",
            "external_search_consent": True,
            "analyst_review": {
                "verdict": "supported",
                "rationale": "Cannot choose two paths.",
                "evidence": [{"url": "https://example.com", "stance": "supports"}],
            },
        }).status_code == 422
        assert client.put("/api/analyses/job/transcript", json={
            "base_version": 999,
            "text": "stale correction",
        }).status_code == 409


def test_status_and_missing_or_incomplete_jobs_fail_closed(tmp_path):
    app = app_for(tmp_path)
    with TestClient(app) as client:
        status = client.get("/api/claims/status").json()
        assert status["provider"]["available"] is False
        assert status["transcription"]["provider"] == "faster-whisper"
        assert status["limits"]["max_claim_chars"] == 2000
        assert client.get("/api/analyses/missing/transcript").status_code == 404
        assert client.post("/api/analyses/missing/claims", json={
            "text": "A claim", "external_search_consent": False
        }).status_code == 404
