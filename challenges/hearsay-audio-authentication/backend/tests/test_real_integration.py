"""Local synthetic speech checks wiring, not detector accuracy."""

from __future__ import annotations

import json
import csv
import io
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
import numpy as np
import soundfile as sf

from echotrace.api import Store, create_app
from echotrace.nii_candidate import WEIGHTS_PATH, WEIGHTS_SHA256, _valid_weights


@pytest.mark.skipif(not Path("/usr/bin/say").exists() or not shutil.which("ffmpeg"),
                    reason="macOS say and FFmpeg are needed for this local integration fixture")
def test_api_cli_parity_on_labeled_macos_tts(tmp_path: Path) -> None:
    text = ("This recording is a synthetic speech demonstration for audio analysis. "
            "Please verify important messages through a trusted channel.")
    aiff = tmp_path / "macos-say-synthetic.aiff"
    wav = tmp_path / "macos-say-synthetic.wav"
    subprocess.run(["/usr/bin/say", "-o", str(aiff), text], check=True, timeout=20)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(aiff),
                    "-ac", "1", "-ar", "16000", str(wav)], check=True, timeout=20)

    output = tmp_path / "cli.json"
    subprocess.run([sys.executable, "-m", "echotrace.cli", "score", str(wav),
                    "--output", str(output)], check=True, timeout=25)
    cli = json.loads(output.read_text())

    app = create_app(tmp_path / "api-workspace")
    with TestClient(app) as client:
        with wav.open("rb") as source:
            response = client.post("/api/analyses", files={"file": (wav.name, source, "audio/wav")})
        assert response.status_code == 202
        job_id = response.json()["id"]
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            job = client.get(f"/api/analyses/{job_id}").json()
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(.05)
        assert job["status"] == "completed", job.get("error")
        api = job["result"]
        assert client.get(f"/api/analyses/{job_id}/report").json() == api

    assert api["input"]["sha256"] == cli["input"]["sha256"]
    assert api["input"]["filename"] == wav.name
    assert api["synthetic_score"] == pytest.approx(cli["synthetic_score"], abs=1e-7)
    assert api["intervals"] == cli["intervals"]
    assert api["model"] == cli["model"]
    assert api["aggregation"] == cli["aggregation"]
    assert api["score_kind"] == "uncalibrated"
    assert len(api["intervals"]) >= 1


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_real_report_export_and_interrupted_retry_survive_lifespan_restart(tmp_path: Path) -> None:
    if not _valid_weights(WEIGHTS_PATH):
        pytest.skip("Pinned detector weights required")
    source = tmp_path / "source.wav"
    t = np.arange(72_000, dtype=np.float32) / 16_000
    sf.write(source, .3 * np.sin(2 * np.pi * 220 * t), 16_000)
    workspace = tmp_path / "isolated-workspace"

    with TestClient(create_app(workspace)) as client:
        with source.open("rb") as handle:
            response = client.post("/api/analyses", files={"file": ("source.wav", handle, "audio/wav")})
        assert response.status_code == 202
        original_id = response.json()["id"]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            original = client.get(f"/api/analyses/{original_id}").json()
            if original["status"] in ("completed", "failed"):
                break
            time.sleep(.05)
        assert original["status"] == "completed", original.get("error")
        report_before = client.get(f"/api/analyses/{original_id}/report").content
        export_before = client.post("/api/exports", json={"ids": [original_id]}).content

    interrupted_id = "disposable-interrupted"
    interrupted_path = workspace / interrupted_id / "original.wav"
    interrupted_path.parent.mkdir()
    interrupted_path.write_bytes(source.read_bytes())
    store = Store(workspace)
    store.create(interrupted_id, "retry.wav", interrupted_path)
    store.update(interrupted_id, status="running", stage="detector")

    with TestClient(create_app(workspace)) as client:
        restored = client.get(f"/api/analyses/{original_id}").json()
        assert restored["status"] == "completed"
        assert client.get(f"/api/analyses/{original_id}/report").content == report_before
        assert client.post("/api/exports", json={"ids": [original_id]}).content == export_before
        interrupted = client.get(f"/api/analyses/{interrupted_id}").json()
        assert (interrupted["status"], interrupted["stage"]) == ("failed", "interrupted")
        assert client.get(f"/api/analyses/{interrupted_id}/report").status_code == 409
        assert client.post("/api/exports", json={"ids": [original_id, interrupted_id]}).status_code == 409
        assert client.post(f"/api/analyses/{interrupted_id}/retry").status_code == 202
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            retried = client.get(f"/api/analyses/{interrupted_id}").json()
            if retried["status"] in ("completed", "failed"):
                break
            time.sleep(.05)
        assert retried["status"] == "completed", retried.get("error")
        exported = client.post("/api/exports", json={"ids": [original_id, interrupted_id]})
        assert exported.status_code == 200
        rows = list(csv.DictReader(io.StringIO(exported.text)))
        assert [row["file_id"] for row in rows] == [original_id, interrupted_id]
        assert [row["synthetic_score"] for row in rows] == [
            format(job["result"]["synthetic_score"], ".10g") for job in (restored, retried)]
        assert {job["id"] for job in client.get("/api/analyses").json()} == {original_id, interrupted_id}

    report = json.loads(report_before)
    assert report["input"]["filename"] == "source.wav"
    assert report["model"]["weights_sha256"] == WEIGHTS_SHA256
    assert report["synthetic_score"] == restored["result"]["synthetic_score"]
