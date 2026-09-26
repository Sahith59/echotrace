"""FastAPI routes for local speaker-reference comparison."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from .speaker import MAX_REFERENCE_BYTES, SpeakerComparisonError, SpeakerComparisonService


def create_speaker_router(store, service=None) -> APIRouter:
    service = service or SpeakerComparisonService(store)
    router = APIRouter()
    temp_root = store.root / ".speaker-temp"
    temp_root.mkdir(parents=True, exist_ok=True)

    def job_for(job_id: str, *, require_complete: bool = False):
        try:
            job = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "Recording not found") from None
        if require_complete and job["status"] != "completed":
            raise HTTPException(409, "Complete the original analysis before comparing a speaker.")
        return job

    @router.get("/api/speaker/status")
    def status():
        return service.status()

    @router.get("/api/analyses/{job_id}/speaker-comparison")
    def get_comparison(job_id: str):
        job_for(job_id)
        report = service.get(job_id)
        if report is None:
            raise HTTPException(404, "Speaker comparison not found")
        return report

    @router.post("/api/analyses/{job_id}/speaker-comparison")
    def compare(
        job_id: str,
        consent: bool = Form(...),
        file: UploadFile = File(...),
        reference_label: str | None = Form(None),
    ):
        if not consent:
            raise HTTPException(422, "Explicit consent is required to process a trusted voice reference.")
        job = job_for(job_id, require_complete=True)
        label = re.sub(r"\s+", " ", (reference_label or "Trusted reference").strip())
        if not label or len(label) > 80 or any(ord(char) < 32 for char in label):
            raise HTTPException(422, "Reference label must contain 1 to 80 printable characters.")
        temp_path = temp_root / (uuid.uuid4().hex + ".upload")
        total = 0
        try:
            with temp_path.open("wb") as target:
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_REFERENCE_BYTES:
                        raise HTTPException(413, "Reference exceeds the 20 MiB upload limit.")
                    target.write(chunk)
            if not total:
                raise HTTPException(422, "Reference recording is empty.")
            try:
                return service.compare(job, temp_path, label)
            except SpeakerComparisonError as exc:
                message = str(exc)
                if "Another speaker comparison" in message:
                    raise HTTPException(409, message) from None
                if "dependencies are unavailable" in message or "weights" in message or "model could not" in message:
                    raise HTTPException(503, message) from None
                raise HTTPException(422, message) from None
        finally:
            file.file.close()
            temp_path.unlink(missing_ok=True)

    @router.delete("/api/analyses/{job_id}/speaker-comparison", status_code=204)
    def delete_comparison(job_id: str):
        job_for(job_id)
        if not service.delete(job_id):
            raise HTTPException(404, "Speaker comparison not found")
        return Response(status_code=204)

    return router
