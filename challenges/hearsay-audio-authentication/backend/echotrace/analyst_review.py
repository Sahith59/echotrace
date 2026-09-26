"""Persistent human review state kept separate from detector results."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


ReviewStatus = Literal["needs_review", "corroboration_requested", "review_complete"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_review() -> dict:
    return {"status": "needs_review", "notes": "", "version": 0, "updated_at": None}


class ReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ReviewStatus
    notes: str = Field(default="", max_length=8000)
    expected_version: int = Field(ge=0)


def initialize(store) -> None:
    with store.connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS analyst_reviews (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK(status IN ('needs_review','corroboration_requested','review_complete')),
            notes TEXT NOT NULL,
            version INTEGER NOT NULL CHECK(version >= 1),
            updated_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id))""")


def load_analyst_reviews(store, job_ids: list[str]) -> dict[str, dict]:
    if not job_ids:
        return {}
    rows = []
    # Stay below common SQLite bind-variable limits while retaining batched reads.
    with store.connect() as db:
        for start in range(0, len(job_ids), 900):
            batch = job_ids[start:start + 900]
            placeholders = ",".join("?" for _ in batch)
            rows.extend(db.execute(
                f"SELECT job_id,status,notes,version,updated_at FROM analyst_reviews "
                f"WHERE job_id IN ({placeholders})",
                batch,
            ).fetchall())
    return {
        row["job_id"]: {key: row[key] for key in ("status", "notes", "version", "updated_at")}
        for row in rows
    }


def load_analyst_review(store, job_id: str) -> dict:
    return load_analyst_reviews(store, [job_id]).get(job_id, default_review())


def create_analyst_review_router(store) -> APIRouter:
    initialize(store)
    router = APIRouter()

    def completed(job_id: str) -> None:
        try:
            job = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "Recording not found") from None
        if job["status"] != "completed":
            raise HTTPException(409, "Complete analysis before updating analyst review.")

    @router.get("/api/analyses/{job_id}/analyst-review")
    def get_review(job_id: str):
        completed(job_id)
        return load_analyst_review(store, job_id)

    @router.put("/api/analyses/{job_id}/analyst-review")
    def update_review(job_id: str, request: ReviewUpdate):
        completed(job_id)
        timestamp = _now()
        try:
            with store.connect() as db:
                if request.expected_version == 0:
                    cursor = db.execute(
                        "INSERT OR IGNORE INTO analyst_reviews(job_id,status,notes,version,updated_at) "
                        "VALUES (?,?,?,?,?)",
                        (job_id, request.status, request.notes, 1, timestamp),
                    )
                else:
                    cursor = db.execute(
                        "UPDATE analyst_reviews SET status=?,notes=?,version=version+1,updated_at=? "
                        "WHERE job_id=? AND version=?",
                        (request.status, request.notes, timestamp, job_id, request.expected_version),
                    )
                changed = cursor.rowcount == 1
        except sqlite3.IntegrityError:
            changed = False
        if not changed:
            current = load_analyst_review(store, job_id)
            raise HTTPException(409, detail={
                "message": "Analyst review changed. Reload before saving.",
                "current_version": current["version"],
            })
        return load_analyst_review(store, job_id)

    return router
