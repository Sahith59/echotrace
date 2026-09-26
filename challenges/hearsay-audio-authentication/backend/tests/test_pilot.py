"""Public pilot catalog serves only the fixed, locally verified diagnostic clips."""

import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from echotrace.api import create_app
from echotrace.pilot import create_pilot_router


REVISION = "9143e5ea709575ebab6bec52840a1043aada7bb1"
GENUINE_ID = "2d374fc61bd89e32"
SYNTHETIC_ID = "b9bcdda92ac7de4e"


def client_for(root, provenance):
    app = FastAPI()
    app.include_router(create_pilot_router(root=root, provenance_path=provenance))
    return TestClient(app)


@pytest.fixture
def sample(tmp_path):
    root = tmp_path / "audio"
    root.mkdir()
    genuine = root / "original/en/genuine.wav"
    genuine.parent.mkdir(parents=True)
    genuine.write_bytes(b"genuine audio")
    synthetic = root / "fake/en/Engine/synthetic.wav"
    synthetic.parent.mkdir(parents=True)
    synthetic.write_bytes(b"synthetic audio")
    entries = [
        {"file_id": GENUINE_ID, "path": "original/en/genuine.wav", "label": 0,
         "sha256": hashlib.sha256(genuine.read_bytes()).hexdigest(), "bytes": genuine.stat().st_size},
        {"file_id": SYNTHETIC_ID, "path": "fake/en/Engine/synthetic.wav", "label": 1,
         "sha256": hashlib.sha256(synthetic.read_bytes()).hexdigest(), "bytes": synthetic.stat().st_size},
    ]
    provenance = tmp_path / "provenance.json"
    provenance.write_text(json.dumps({"dataset": "mueller91/MLAAD-tiny", "revision": REVISION,
                                      "files": entries}))
    return root, provenance, genuine, synthetic


def test_catalog_lists_fixed_entries_without_paths_and_serves_verified_audio(sample):
    root, provenance, genuine, synthetic = sample
    client = client_for(root, provenance)
    response = client.get("/api/examples")
    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "MLAAD-tiny"
    assert "diagnostic" in body["note"].lower()
    assert body["examples"] == [
        {"id": GENUINE_ID, "filename": "genuine.wav", "label": "genuine", "available": True},
        {"id": SYNTHETIC_ID, "filename": "synthetic.wav", "label": "synthetic", "available": True},
    ]
    assert client.get(f"/api/examples/{GENUINE_ID}/audio").content == genuine.read_bytes()
    assert client.get(f"/api/examples/{SYNTHETIC_ID}/audio").content == synthetic.read_bytes()


def test_missing_catalog_has_reason_and_no_examples(tmp_path):
    client = client_for(tmp_path, tmp_path / "absent.json")
    body = client.get("/api/examples").json()
    assert body["examples"] == []
    assert body["reason"]
    assert client.get(f"/api/examples/{GENUINE_ID}/audio").status_code == 404


def test_unpinned_revision_does_not_create_catalog(sample):
    root, provenance, _, _ = sample
    data = json.loads(provenance.read_text())
    data["revision"] = "unreviewed"
    provenance.write_text(json.dumps(data))
    client = client_for(root, provenance)
    assert client.get("/api/examples").json()["examples"] == []
    assert client.get(f"/api/examples/{GENUINE_ID}/audio").status_code == 404


def test_missing_or_tampered_audio_is_unavailable(sample):
    root, provenance, genuine, synthetic = sample
    genuine.unlink()
    synthetic.write_bytes(b"changed")
    client = client_for(root, provenance)
    assert [item["available"] for item in client.get("/api/examples").json()["examples"]] == [False, False]
    assert client.get(f"/api/examples/{GENUINE_ID}/audio").status_code == 404
    assert client.get(f"/api/examples/{SYNTHETIC_ID}/audio").status_code == 404


def test_rejects_symlink_escape_and_bad_ids(sample, tmp_path):
    root, provenance, genuine, _ = sample
    outside = tmp_path / "outside.wav"
    outside.write_bytes(genuine.read_bytes())
    genuine.unlink()
    genuine.symlink_to(outside)
    client = client_for(root, provenance)
    assert client.get("/api/examples").json()["examples"][0]["available"] is False
    assert client.get(f"/api/examples/{GENUINE_ID}/audio").status_code == 404
    for bad_id in ("unknown", "../" + GENUINE_ID, "%2e%2e%2f" + GENUINE_ID, GENUINE_ID + "%2f.."):
        assert client.get(f"/api/examples/{bad_id}/audio").status_code in (400, 404)


def test_provenance_cannot_redirect_to_an_outside_path(sample, tmp_path):
    root, provenance, genuine, _ = sample
    outside = tmp_path / "outside.wav"
    outside.write_bytes(genuine.read_bytes())
    data = json.loads(provenance.read_text())
    data["files"][0]["path"] = "../outside.wav"
    provenance.write_text(json.dumps(data))
    client = client_for(root, provenance)
    assert client.get("/api/examples").json()["examples"][0]["available"] is False
    assert client.get(f"/api/examples/{GENUINE_ID}/audio").status_code == 404


def test_app_mounts_catalog_with_independent_audio_root(sample, tmp_path):
    root, provenance, genuine, _ = sample
    with TestClient(create_app(root=tmp_path / "workspace", pilot_root=root,
                               pilot_provenance=provenance)) as client:
        assert len(client.get("/api/examples").json()["examples"]) == 2
        assert client.get(f"/api/examples/{GENUINE_ID}/audio").content == genuine.read_bytes()
