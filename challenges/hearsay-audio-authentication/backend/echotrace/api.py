"""Local HTTP adapter over the exact CLI scoring pipeline."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import sqlite3
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from .case_report import create_case_router
from .pilot import create_pilot_router
from .interpretation import create_interpretation_router
from .speaker_router import create_speaker_router
from .claims_router import create_claims_router
from .detector_comparison import create_detector_comparison_router
from .analyst_review import create_analyst_review_router, load_analyst_review, load_analyst_reviews
from .model_provenance import model_identity, same_model

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
                result TEXT, error TEXT, parent_id TEXT, transform TEXT,
                reanalysis_of TEXT)""")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)").fetchall()}
            if "reanalysis_of" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN reanalysis_of TEXT")

    def connect(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, job_id, filename, path, parent_id=None, transform=None, reanalysis_of=None):
        with self.connect() as db:
            db.execute("""INSERT INTO jobs
                (id,filename,path,status,stage,created_at,result,error,parent_id,transform,reanalysis_of)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                job_id, filename, str(path), "queued", "queued", now(), None,
                None, parent_id, json.dumps(transform) if transform else None, reanalysis_of))
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
               pilot_provenance: Path | None = None, interpreter=None,
               detector_comparison_scorer=None, detector_comparison_status=None) -> FastAPI:
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
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_origin_guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in {
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:8000", "http://127.0.0.1:8000",
            "http://localhost:4173", "http://127.0.0.1:4173",
        }:
            return JSONResponse({"detail": "Cross-site requests are not permitted by this local workspace."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    app.state.store = store
    app.include_router(create_pilot_router(root=pilot_root, provenance_path=pilot_provenance))
    app.include_router(create_interpretation_router(store, interpreter))
    app.include_router(create_speaker_router(store))
    app.include_router(create_claims_router(store))
    app.include_router(create_analyst_review_router(store))
    app.include_router(create_case_router(store))
    app.include_router(create_detector_comparison_router(
        store, detector_comparison_scorer, detector_comparison_status))

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
                parent = store.get(job["parent_id"])
                if not same_model((parent.get("result") or {}).get("model"), result.get("model")):
                    raise ValueError(
                        "Stress comparison was not saved because the primary model changed. "
                        "Reanalyze the original recording with the current model first."
                    )
                result["parent_id"] = job["parent_id"]
                result["transform"] = job["transform"]
            if job.get("reanalysis_of"):
                result["reanalysis_of"] = job["reanalysis_of"]
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
        return {"status": "ok", "model": model_status(), "limits": {"max_bytes": MAX_BYTES, "max_duration_s": 30}}

    @app.post("/api/analyses", status_code=202)
    async def upload(file: UploadFile):
        job_id = uuid.uuid4().hex
        folder = root / job_id
        folder.mkdir()
        filename = (file.filename or "recording").replace("\\", "/").split("/")[-1][:240]
        suffix = Path(filename).suffix.lower()
        # Filename never becomes a path; FFmpeg verifies actual media contents.
        path = folder / ("original" + (suffix if suffix in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".webm", ".mp4"} else ".bin"))
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
        jobs = store.list()
        reviews = load_analyst_reviews(store, [job["id"] for job in jobs])
        return [{**public(job), "analyst_review": reviews.get(job["id"], {
            "status": "needs_review", "notes": "", "version": 0, "updated_at": None,
        })} for job in jobs]

    @app.get("/api/analyses/{job_id}")
    def detail(job_id: str):
        job = get_job(job_id)
        return {**public(job), "analyst_review": load_analyst_review(store, job_id)}

    @app.get("/api/analyses/{job_id}/audio")
    def audio(job_id: str):
        job = get_job(job_id)
        if not Path(job["path"]).is_file():
            raise HTTPException(409, "Audio is not ready")
        return FileResponse(job["path"], media_type="audio/ogg" if Path(job["path"]).suffix == ".opus" else None)

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

    @app.post("/api/analyses/{job_id}/reanalyze", status_code=202)
    def reanalyze(job_id: str):
        source = get_job(job_id)
        if source["status"] != "completed":
            raise HTTPException(409, "Complete the original analysis before reanalysis.")
        if source.get("parent_id") or source.get("reanalysis_of"):
            raise HTTPException(422, "Reanalysis must start from the original recording.")
        path = Path(source["path"])
        if not path.is_file():
            raise HTTPException(409, "The original recording is missing.")
        with path.open("rb") as source_file:
            actual_sha = hashlib.file_digest(source_file, "sha256").hexdigest()
        expected_sha = ((source.get("result") or {}).get("input") or {}).get("sha256")
        if not expected_sha or actual_sha != expected_sha:
            raise HTTPException(409, "The original recording changed after analysis.")
        new_id = uuid.uuid4().hex
        folder = root / new_id
        folder.mkdir()
        destination = folder / ("original" + path.suffix)
        try:
            shutil.copyfile(path, destination)
            with destination.open("rb") as copied, path.open("rb") as original:
                if (hashlib.file_digest(copied, "sha256").hexdigest() != actual_sha or
                        hashlib.file_digest(original, "sha256").hexdigest() != actual_sha):
                    raise HTTPException(409, "The original recording changed during reanalysis setup.")
            job = store.create(new_id, source["filename"], destination, reanalysis_of=job_id)
        except Exception:
            destination.unlink(missing_ok=True)
            folder.rmdir()
            raise
        schedule(new_id)
        return public(job)

    @app.post("/api/analyses/{job_id}/stress-tests", status_code=202)
    def stress(job_id: str, request: StressRequest):
        parent = get_job(job_id)
        if parent["status"] != "completed":
            raise HTTPException(409, "Complete the original analysis first")
        if parent["parent_id"]:
            raise HTTPException(422, "Run comparisons from the original recording")
        if request.kind not in {"mp3", "noise"}:
            raise HTTPException(422, "Choose mp3 or noise")
        from .pipeline import model_status as current_model_status
        if not same_model((parent.get("result") or {}).get("model"), current_model_status()):
            raise HTTPException(
                409,
                "The original used a different primary model. Reanalyze it before running stress comparisons.",
            )
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
        if len(jobs) > 1:
            identities = [model_identity((job.get("result") or {}).get("model")) for job in jobs]
            if any(identity is None for identity in identities) or len(set(identities)) != 1:
                raise HTTPException(409, "CSV export requires every recording to use the same identified model.")
        reviews = load_analyst_reviews(store, [job["id"] for job in jobs])
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["file_id", "filename", "synthetic_score", "analyst_review_status",
                         "analyst_review_notes", "analyst_review_version"])
        for job in jobs:
            # Protect spreadsheet users; original filename remains intact in JSON report.
            name = job["filename"]
            if name.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                name = "'" + name
            review = reviews.get(job["id"], {
                "status": "needs_review", "notes": "", "version": 0,
            })
            notes = review["notes"]
            if notes.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                notes = "'" + notes
            writer.writerow([job["id"], name, format(job["result"]["synthetic_score"], ".10g"),
                             review["status"], notes, review["version"]])
        return Response(output.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": 'attachment; filename="echotrace-analyst-export.csv"',
            "X-Export-Kind": "analyst-not-sponsor-schema"})

    return app


app = create_app()
