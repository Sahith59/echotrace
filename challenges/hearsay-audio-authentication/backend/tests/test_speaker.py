import hashlib
import json
import stat
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from echotrace.api import Store, create_app
from echotrace.speaker import (
    MAX_REFERENCE_BYTES,
    SpeakerComparisonError,
    SpeakerComparisonService,
    audio_quality,
)
from echotrace.speaker_router import create_speaker_router


class FakeEmbedder:
    def status(self):
        return {
            "available": True,
            "ready": True,
            "model": {
                "id": "test/speaker-model",
                "revision": "abc123",
                "weights_sha256": "f" * 64,
            },
            "reason": None,
        }

    def embed(self, samples):
        mean = float(np.mean(samples))
        return np.asarray([mean, float(np.std(samples)) + 0.01], dtype=np.float32)


def fake_decode(path: Path):
    raw = path.read_bytes()
    if raw == b"invalid":
        raise ValueError("No readable audio stream was found")
    if raw == b"short":
        samples = np.ones(16_000, dtype=np.float32) * 0.1
    elif raw == b"quiet":
        samples = np.ones(48_000, dtype=np.float32) * 0.00001
    else:
        samples = np.linspace(0.05, 0.4, 48_000, dtype=np.float32)
    return samples, {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "duration_s": len(samples) / 16_000,
        "analysis_sample_rate": 16_000,
    }


def app_for(tmp_path):
    store = Store(tmp_path)
    source = tmp_path / "source.wav"
    source.write_bytes(b"source")
    store.create("complete", "source.wav", source)
    original = {"synthetic_score": 0.37, "input": {"filename": "source.wav"}}
    store.update("complete", status="completed", stage="completed", result=original)
    store.create("pending", "pending.wav", source)
    service = SpeakerComparisonService(store, embedder=FakeEmbedder(), decoder=fake_decode)
    app = FastAPI()
    app.include_router(create_speaker_router(store, service))
    return app, store


def test_comparison_requires_consent_and_completed_recording(tmp_path):
    app, _ = app_for(tmp_path)
    with TestClient(app) as client:
        denied = client.post(
            "/api/analyses/complete/speaker-comparison",
            data={"consent": "false"},
            files={"file": ("reference.wav", b"reference")},
        )
        assert denied.status_code == 422
        assert "consent" in denied.json()["detail"].lower()
        assert client.post(
            "/api/analyses/pending/speaker-comparison",
            data={"consent": "true"},
            files={"file": ("reference.wav", b"reference")},
        ).status_code == 409
        assert client.post(
            "/api/analyses/missing/speaker-comparison",
            data={"consent": "true"},
            files={"file": ("reference.wav", b"reference")},
        ).status_code == 404


@pytest.mark.parametrize("payload, phrase", [
    (b"invalid", "readable audio"),
    (b"short", "2 seconds"),
    (b"quiet", "quiet"),
])
def test_invalid_short_and_quiet_references_are_rejected(tmp_path, payload, phrase):
    app, _ = app_for(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/analyses/complete/speaker-comparison",
            data={"consent": "true"},
            files={"file": ("reference.wav", payload)},
        )
    assert response.status_code == 422
    assert phrase in response.json()["detail"].lower()


def test_oversized_reference_is_rejected_and_temp_file_removed(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path)
    monkeypatch.setattr("echotrace.speaker_router.MAX_REFERENCE_BYTES", 5)
    with TestClient(app) as client:
        response = client.post(
            "/api/analyses/complete/speaker-comparison",
            data={"consent": "true"},
            files={"file": ("reference.wav", b"123456")},
        )
    assert response.status_code == 413
    assert not list((tmp_path / ".speaker-temp").glob("*"))


def test_persists_uncalibrated_similarity_without_reference_or_score_mutation(tmp_path):
    app, store = app_for(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/analyses/complete/speaker-comparison",
            data={"consent": "true", "reference_label": " Interview sample "},
            files={"file": ("private-name.wav", b"reference")},
        )
        assert response.status_code == 200
        report = response.json()
        assert report["status"] == "completed"
        assert report["similarity"]["calibration"] == "uncalibrated"
        assert report["similarity"]["identity_verdict"] is None
        assert -1 <= report["similarity"]["cosine"] <= 1
        assert report["reference"]["label"] == "Interview sample"
        assert report["reference"]["retained"] is False
        assert report["reference"]["sha256"] == hashlib.sha256(b"reference").hexdigest()
        assert "private-name" not in json.dumps(report)
        assert any("cloning" in item.lower() for item in report["limitations"])
        assert client.get("/api/analyses/complete/speaker-comparison").json() == report
        assert not list((tmp_path / ".speaker-temp").glob("*"))

        # Speaker metadata lives separately and cannot alter synthesis scoring.
        assert store.get("complete")["result"]["synthetic_score"] == 0.37
        with store.connect() as db:
            saved = db.execute(
                "SELECT report FROM speaker_comparisons WHERE job_id=?", ("complete",)
            ).fetchone()
        assert json.loads(saved[0]) == report

        deleted = client.delete("/api/analyses/complete/speaker-comparison")
        assert deleted.status_code == 204
        assert client.get("/api/analyses/complete/speaker-comparison").status_code == 404


def test_status_contract_and_missing_model_error(tmp_path):
    app, store = app_for(tmp_path)
    with TestClient(app) as client:
        status = client.get("/api/speaker/status").json()
    assert status["available"] is True
    assert status["model"]["id"] == "test/speaker-model"
    assert status["limits"] == {
        "max_reference_bytes": MAX_REFERENCE_BYTES,
        "max_audio_duration_s": 120.0,
        "min_audio_duration_s": 2.0,
        "embedding_audio_cap_s": 40.0,
    }

    class Missing(FakeEmbedder):
        def status(self):
            return {"available": False, "ready": False, "model": None,
                    "reason": "Speaker model dependencies are unavailable."}

        def embed(self, samples):
            raise SpeakerComparisonError("Speaker model dependencies are unavailable.")

    missing_app = FastAPI()
    missing_app.include_router(create_speaker_router(
        store, SpeakerComparisonService(store, embedder=Missing(), decoder=fake_decode)
    ))
    with TestClient(missing_app) as client:
        response = client.post(
            "/api/analyses/complete/speaker-comparison",
            data={"consent": "true"},
            files={"file": ("reference.wav", b"reference")},
        )
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_audio_quality_gate_boundaries():
    with pytest.raises(SpeakerComparisonError, match="2 seconds"):
        audio_quality(np.ones(31_999, dtype=np.float32))
    with pytest.raises(SpeakerComparisonError, match="quiet"):
        audio_quality(np.zeros(32_000, dtype=np.float32))
    result = audio_quality(np.ones(32_000, dtype=np.float32) * 0.05)
    assert result["duration_s"] == 2.0
    assert result["rms_dbfs"] == pytest.approx(-26.02, abs=0.01)


def test_main_app_registers_speaker_routes(tmp_path):
    with TestClient(create_app(tmp_path, lambda path, progress=None: {})) as client:
        response = client.get("/api/speaker/status")
    assert response.status_code == 200
    assert response.json()["model"]["id"] == "microsoft/wavlm-base-plus-sv"


def test_sensitive_reference_temp_file_is_owner_only(tmp_path):
    app, store = app_for(tmp_path)
    observed_modes = []

    class InspectingService:
        def compare(self, job, reference_path, reference_label):
            observed_modes.append(stat.S_IMODE(reference_path.stat().st_mode))
            return {"status": "completed"}

    secure_app = FastAPI()
    secure_app.include_router(create_speaker_router(store, InspectingService()))
    with TestClient(secure_app) as client:
        response = client.post(
            "/api/analyses/complete/speaker-comparison",
            data={"consent": "true"},
            files={"file": ("private.wav", b"sensitive voice")},
        )
    assert response.status_code == 200
    assert observed_modes == [0o600]
