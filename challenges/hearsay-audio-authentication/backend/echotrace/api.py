"""Local HTTP adapter over the exact CLI scoring pipeline."""
from __future__ import annotations

import csv
import io
import json
import math
import os
import sqlite3
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from .pilot import create_pilot_router
from .interpretation import create_interpretation_router
from .speaker_router import create_speaker_router

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / "workspace"
MAX_BYTES = 50 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = root / "jobs.sqlite3"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, path TEXT NOT NULL,
                status TEXT NOT NULL, stage TEXT NOT NULL, created_at TEXT NOT NULL,
                result TEXT, error TEXT, parent_id TEXT, transform TEXT)""")

    def connect(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, job_id, filename, path, parent_id=None, transform=None):
        with self.connect() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)", (
                job_id, filename, str(path), "queued", "queued", now(), None,
                None, parent_id, json.dumps(transform) if transform else None))
        return self.get(job_id)

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        result = dict(row)
        for field in ("result", "transform"):
            result[field] = json.loads(result[field]) if result[field] else None
        return result

    def list(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            for field in ("result", "transform"):
                job[field] = json.loads(job[field]) if job[field] else None
            jobs.append(job)
        return jobs

    def pending_count(self):
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]

    def update(self, job_id, **fields):
        allowed = {"status", "stage", "result", "error"}
        if not fields or not set(fields) <= allowed:
            raise ValueError("Invalid job update")
        if "result" in fields:
            fields["result"] = json.dumps(fields["result"], allow_nan=False)
        with self.connect() as db:
            db.execute(f"UPDATE jobs SET {','.join(k+'=?' for k in fields)} WHERE id=?",
                       (*fields.values(), job_id))

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='failed',stage='interrupted',"
                       "error='Server restarted before analysis finished. Retry this recording.' "
                       "WHERE status IN ('queued','running')")


def public(job):
    return {key: value for key, value in job.items() if key != "path"}


class ExportRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=1000)


class StressRequest(BaseModel):
    kind: str


def create_app(root: Path | None = None, analyzer=None, *, pilot_root: Path | None = None,
               pilot_provenance: Path | None = None, interpreter=None) -> FastAPI:
    root = root or Path(os.environ.get("ECHOTRACE_WORKSPACE", DEFAULT_ROOT))
    store = Store(root)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="echotrace")
    scheduling_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="ECHOTRACE", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.include_router(create_pilot_router(root=pilot_root, provenance_path=pilot_provenance))
    app.include_router(create_interpretation_router(store, interpreter))
    app.include_router(create_speaker_router(store))

    def get_job(job_id):
        try:
            return store.get(job_id)
        except KeyError:
            raise HTTPException(404, "Recording not found")

    def transform_audio(job):
        parent = get_job(job["parent_id"])
        transform = job["transform"]
        output = job["path"]
        if transform["kind"] == "mp3":
            cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", parent["path"],
                   "-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", "64k", output]
            subprocess.run(cmd, check=True, capture_output=True, timeout=45)
        else:
            import numpy as np
            import soundfile as sf
            decoded = subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", parent["path"],
                 "-vn", "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
                check=True, capture_output=True, timeout=45)
            audio = np.frombuffer(decoded.stdout, dtype="<f4").copy()
            rms = float(np.sqrt(np.mean(audio ** 2)))
            noise = np.random.default_rng(42).normal(0, rms / 10, len(audio))
            # FLOAT WAV preserves the chosen SNR without nonlinear clipping.
            sf.write(output, audio + noise, 16000, subtype="FLOAT")

    def run(job_id):
        try:
            job = store.get(job_id)
            store.update(job_id, status="running", stage="transforming" if job["parent_id"] else "decoding")
            if job["parent_id"]:
                transform_audio(job)
            if analyzer is None:
                from .pipeline import analyze_file
                fn = analyze_file
            else:
                fn = analyzer
            result = fn(Path(job["path"]), progress=lambda stage: store.update(job_id, stage=stage))
            result["input"]["filename"] = job["filename"]
            if job["parent_id"]:
                result["parent_id"] = job["parent_id"]
                result["transform"] = job["transform"]
            store.update(job_id, status="completed", stage="completed", result=result)
        except Exception as exc:
            message = str(exc)[:500] or type(exc).__name__
            if isinstance(exc, subprocess.CalledProcessError):
                message = "Audio conversion failed. Check that the recording contains a supported audio stream."
            store.update(job_id, status="failed", stage="failed", error=message)

    def schedule(job_id):
        with scheduling_lock:
            pending = store.pending_count()
            if pending > 100:
                store.update(job_id, status="failed", stage="failed", error="Queue is full. Retry later.")
                raise HTTPException(429, "Queue is full. Retry later.")
            executor.submit(run, job_id)

    @app.get("/api/health")
    def health():
        from .pipeline import model_status
        return {"status": "ok", "model": model_status(), "limits": {"max_bytes": MAX_BYTES, "max_duration_s": 120}}

    @app.post("/api/analyses", status_code=202)
    async def upload(file: UploadFile):
        job_id = uuid.uuid4().hex
        folder = root / job_id
        folder.mkdir()
        filename = (file.filename or "recording").replace("\\", "/").split("/")[-1][:240]
        suffix = Path(filename).suffix.lower()
        # Filename never becomes a path; FFmpeg verifies actual media contents.
        path = folder / ("original" + (suffix if suffix in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".webm", ".mp4"} else ".bin"))
        total = 0
        try:
            with path.open("wb") as target:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise HTTPException(413, "Recording exceeds the 50 MiB upload limit.")
                    target.write(chunk)
            if total == 0:
                raise HTTPException(422, "The recording is empty.")
        except Exception:
            path.unlink(missing_ok=True)
            folder.rmdir()
            raise
        finally:
            await file.close()
        job = store.create(job_id, filename, path)
        schedule(job_id)
        return public(job)

    @app.get("/api/analyses")
    def history():
        return [public(j) for j in store.list()]

    @app.get("/api/analyses/{job_id}")
    def detail(job_id: str):
        return public(get_job(job_id))

    @app.get("/api/analyses/{job_id}/audio")
    def audio(job_id: str):
        job = get_job(job_id)
        if not Path(job["path"]).is_file():
            raise HTTPException(409, "Audio is not ready")
        return FileResponse(job["path"])

    @app.get("/api/analyses/{job_id}/report")
    def report(job_id: str):
        job = get_job(job_id)
        if job["status"] != "completed":
            raise HTTPException(409, "Analysis is not complete")
        return JSONResponse(job["result"], headers={"Content-Disposition": f'attachment; filename="echotrace-{job_id[:8]}.json"'})

    @app.post("/api/analyses/{job_id}/retry", status_code=202)
    def retry(job_id: str):
        with scheduling_lock:
            job = get_job(job_id)
            if job["status"] != "failed":
                raise HTTPException(409, "Only failed analyses can be retried")
            store.update(job_id, status="queued", stage="queued", error=None)
        schedule(job_id)
        return public(store.get(job_id))

    @app.post("/api/analyses/{job_id}/stress-tests", status_code=202)
    def stress(job_id: str, request: StressRequest):
        parent = get_job(job_id)
        if parent["status"] != "completed":
            raise HTTPException(409, "Complete the original analysis first")
        if parent["parent_id"]:
            raise HTTPException(422, "Run comparisons from the original recording")
        if request.kind not in {"mp3", "noise"}:
            raise HTTPException(422, "Choose mp3 or noise")
        new_id = uuid.uuid4().hex
        folder = root / new_id
        folder.mkdir()
        ext = ".mp3" if request.kind == "mp3" else ".wav"
        transform = {"kind": "mp3", "bitrate": "64k"} if request.kind == "mp3" else {"kind": "noise", "snr_db": 20, "seed": 42}
        job = store.create(new_id, f"{Path(parent['filename']).stem} · {request.kind}{ext}",
                           folder / ("derived" + ext), job_id, transform)
        schedule(new_id)
        return public(job)

    @app.post("/api/exports")
    def export(request: ExportRequest):
        if len(set(request.ids)) != len(request.ids):
            raise HTTPException(422, "Duplicate recording IDs")
        jobs = [get_job(key) for key in request.ids]
        for job in jobs:
            score = (job["result"] or {}).get("synthetic_score")
            if job["status"] != "completed" or not isinstance(score, (float, int)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise HTTPException(409, f"{job['filename']}: a completed, finite model score is required")
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["file_id", "filename", "synthetic_score"])
        for job in jobs:
            # Protect spreadsheet users; original filename remains intact in JSON report.
            name = job["filename"]
            if name.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                name = "'" + name
            writer.writerow([job["id"], name, format(job["result"]["synthetic_score"], ".10g")])
        return Response(output.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": 'attachment; filename="echotrace-analyst-export.csv"',
            "X-Export-Kind": "analyst-not-sponsor-schema"})

    return app


app = create_app()
