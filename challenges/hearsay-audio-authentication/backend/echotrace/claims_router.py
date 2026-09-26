"""FastAPI persistence and validation for transcripts and factual claims."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .claims import ClaimReviewError, GrokClaimReviewer, VERDICTS, validate_public_url
from .transcription import MAX_DURATION_S, MAX_SEGMENTS, MAX_TRANSCRIPT_CHARS, Transcriber, TranscriptionError

MAX_CLAIM_CHARS = 2000
MAX_RATIONALE_CHARS = 1500
MAX_EVIDENCE = 12


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_transcript_versions(store, job_id: str) -> list[dict]:
    """Persistence getter for reports and other local API adapters."""
    with store.connect() as db:
        rows = db.execute(
            "SELECT payload FROM transcripts WHERE job_id=? ORDER BY version", (job_id,)
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def load_claim_records(store, job_id: str) -> list[dict]:
    """Return stored claim records newest first without contacting providers."""
    with store.connect() as db:
        rows = db.execute(
            "SELECT payload FROM claim_reviews WHERE job_id=? ORDER BY created_at DESC", (job_id,)
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def load_claim_artifacts(store, job_id: str) -> dict:
    """Stable export shape with transcript staleness computed from local versions."""
    versions = load_transcript_versions(store, job_id)
    latest = next((row for row in reversed(versions) if row["status"] == "generated"), None)
    records = []
    for claim in load_claim_records(store, job_id):
        item = dict(claim)
        version = item.get("transcript_version")
        item["stale_transcript"] = bool(version and latest and version != latest["version"])
        records.append(item)
    transcript = {"status": "not_generated", "versions": []} if not versions else dict(
        versions[-1], versions=versions
    )
    return {"transcript": transcript, "claims": records}


class SegmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    start_s: float = Field(ge=0, le=MAX_DURATION_S)
    end_s: float = Field(gt=0, le=MAX_DURATION_S)
    text: str = Field(min_length=1, max_length=4000)


class TranscriptCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    base_version: int = Field(ge=1)
    text: str | None = Field(default=None, min_length=1, max_length=MAX_TRANSCRIPT_CHARS)
    segments: list[SegmentInput] | None = Field(default=None, max_length=MAX_SEGMENTS)

    @model_validator(mode="after")
    def has_content(self):
        if self.text is None and self.segments is None:
            raise ValueError("Provide corrected text or timestamped segments.")
        if self.segments is not None:
            prior = 0.0
            for segment in self.segments:
                if segment.end_s <= segment.start_s or segment.start_s + 0.01 < prior:
                    raise ValueError("Transcript segments must be ordered, non-overlapping, and non-empty.")
                prior = segment.end_s
            joined = " ".join(segment.text for segment in self.segments)
            if self.text is not None and " ".join(self.text.split()) != " ".join(joined.split()):
                raise ValueError("Corrected text must match the supplied segments.")
        return self


class SpanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_s: float = Field(ge=0, le=MAX_DURATION_S)
    end_s: float = Field(gt=0, le=MAX_DURATION_S)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_s <= self.start_s:
            raise ValueError("Claim span end must be after its start.")
        return self


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    url: str = Field(min_length=8, max_length=2000)
    title: str | None = Field(default=None, max_length=300)
    publisher: str | None = Field(default=None, max_length=200)
    published_at: str | None = Field(default=None, max_length=40)
    quote: str | None = Field(default=None, max_length=300)
    stance: str

    @model_validator(mode="after")
    def valid(self):
        validate_public_url(self.url)
        if self.stance not in {"supports", "contradicts", "context"}:
            raise ValueError("Evidence stance must be supports, contradicts, or context.")
        return self


class AnalystReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    verdict: str
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)
    evidence: list[EvidenceInput] = Field(default_factory=list, max_length=MAX_EVIDENCE)

    @model_validator(mode="after")
    def supported_by_evidence(self):
        if self.verdict not in VERDICTS:
            raise ValueError("Invalid analyst verdict.")
        expected = "supports" if self.verdict == "supported" else "contradicts"
        if self.verdict in {"supported", "contradicted"} and not any(
            item.stance == expected for item in self.evidence
        ):
            raise ValueError("Supported or contradicted verdicts require matching analyst evidence.")
        return self


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=3, max_length=MAX_CLAIM_CHARS)
    transcript_version: int | None = Field(default=None, ge=1)
    span: SpanInput | None = None
    external_search_consent: bool = False
    analyst_review: AnalystReviewInput | None = None

    @model_validator(mode="after")
    def one_review_path(self):
        if self.external_search_consent and self.analyst_review is not None:
            raise ValueError("Choose external search or analyst review, not both.")
        if self.span is not None and self.transcript_version is None:
            raise ValueError("A transcript span requires a transcript version.")
        return self


def create_claims_router(store, transcriber=None, reviewer=None):
    router = APIRouter()
    transcription = transcriber or Transcriber.configured(store.root / "models" / "faster-whisper")
    claims = reviewer or GrokClaimReviewer()
    transcription_lock = threading.Lock()
    review_lock = threading.Lock()

    with store.connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS transcripts (
            job_id TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(job_id, version))""")
        db.execute("""CREATE TABLE IF NOT EXISTS claim_reviews (
            id TEXT PRIMARY KEY, job_id TEXT NOT NULL, created_at TEXT NOT NULL,
            payload TEXT NOT NULL)""")

    def job_for(job_id: str):
        try:
            job = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "Recording not found") from None
        if job["status"] != "completed":
            raise HTTPException(409, "Complete analysis before reviewing transcript or claims.")
        if not Path(job["path"]).is_file():
            raise HTTPException(409, "Recording audio is unavailable.")
        return job

    def transcript_rows(job_id: str) -> list[dict]:
        return load_transcript_versions(store, job_id)

    def next_version(job_id: str) -> int:
        with store.connect() as db:
            row = db.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS version FROM transcripts WHERE job_id=?", (job_id,)
            ).fetchone()
        return int(row["version"])

    def save_transcript(job_id: str, payload: dict) -> None:
        with store.connect() as db:
            db.execute(
                "INSERT INTO transcripts(job_id,version,created_at,payload) VALUES (?,?,?,?)",
                (job_id, payload["version"], payload["created_at"], json.dumps(payload, allow_nan=False)),
            )

    def latest_success(job_id: str) -> dict | None:
        rows = transcript_rows(job_id)
        return next((row for row in reversed(rows) if row["status"] == "generated"), None)

    def with_stale(job_id: str, claim: dict) -> dict:
        result = dict(claim)
        version = claim.get("transcript_version")
        latest = latest_success(job_id)
        result["stale_transcript"] = bool(version and latest and version != latest["version"])
        return result

    @router.get("/api/claims/status")
    def status():
        return {
            "provider": claims.status(),
            "transcription": transcription.status(),
            "limits": {
                "max_duration_s": int(MAX_DURATION_S),
                "max_transcript_chars": MAX_TRANSCRIPT_CHARS,
                "max_segments": MAX_SEGMENTS,
                "max_claim_chars": MAX_CLAIM_CHARS,
                "max_evidence": MAX_EVIDENCE,
            },
            "external_disclosure": "With consent, only claim text is sent to xAI web search; audio and the full transcript stay local.",
        }

    @router.get("/api/analyses/{job_id}/transcript")
    def get_transcript(job_id: str):
        job_for(job_id)
        rows = transcript_rows(job_id)
        if not rows:
            return {"status": "not_generated", "versions": []}
        return dict(rows[-1], versions=rows)

    @router.post("/api/analyses/{job_id}/transcript", status_code=201)
    def generate_transcript(job_id: str):
        job = job_for(job_id)
        if not transcription_lock.acquire(blocking=False):
            raise HTTPException(409, "Another transcription is running. Retry shortly.")
        try:
            version = next_version(job_id)
            created_at = _now()
            try:
                output = transcription.transcribe(Path(job["path"]))
            except TranscriptionError as exc:
                failed = {
                    "status": "error",
                    "version": version,
                    "source": "automatic",
                    "provider": "faster-whisper",
                    "model": transcription.status()["model"],
                    "created_at": created_at,
                    "text": None,
                    "segments": [],
                    "error": str(exc),
                }
                save_transcript(job_id, failed)
                raise HTTPException(503, str(exc)) from None
            payload = {
                "status": "generated",
                "version": version,
                "source": "automatic",
                "provider": "faster-whisper",
                "model": transcription.status()["model"],
                "created_at": created_at,
                "error": None,
                **output,
            }
            save_transcript(job_id, payload)
            return payload
        finally:
            transcription_lock.release()

    @router.put("/api/analyses/{job_id}/transcript")
    def correct_transcript(job_id: str, correction: TranscriptCorrection):
        job_for(job_id)
        if not transcription_lock.acquire(blocking=False):
            raise HTTPException(409, "Another transcription update is running. Retry shortly.")
        try:
            base = latest_success(job_id)
            if base is None or base["version"] != correction.base_version:
                raise HTTPException(409, "Transcript changed or does not exist; reload before correcting it.")
            if correction.segments is None:
                segments = []
                text = correction.text or ""
                duration = base.get("duration_s", 0.0)
            else:
                segments = [dict(id=index, **item.model_dump()) for index, item in enumerate(correction.segments)]
                text = correction.text or " ".join(item["text"] for item in segments)
                duration = segments[-1]["end_s"] if segments else 0.0
            payload = {
                "status": "generated",
                "version": next_version(job_id),
                "source": "analyst_corrected",
                "provider": None,
                "model": None,
                "created_at": _now(),
                "error": None,
                "text": text,
                "segments": segments,
                "language": base.get("language"),
                "language_probability": None,
                "duration_s": duration,
                "based_on_version": base["version"],
            }
            save_transcript(job_id, payload)
            return payload
        finally:
            transcription_lock.release()

    @router.get("/api/analyses/{job_id}/claims")
    def get_claims(job_id: str):
        job_for(job_id)
        return {"claims": [with_stale(job_id, item) for item in load_claim_records(store, job_id)]}

    def save_claim(job_id: str, payload: dict) -> None:
        with store.connect() as db:
            db.execute(
                "INSERT INTO claim_reviews(id,job_id,created_at,payload) VALUES (?,?,?,?)",
                (payload["id"], job_id, payload["created_at"], json.dumps(payload, allow_nan=False)),
            )

    @router.post("/api/analyses/{job_id}/claims", status_code=201)
    def create_claim(job_id: str, request: ClaimInput):
        job_for(job_id)
        associated = None
        if request.transcript_version is not None:
            associated = next(
                (row for row in transcript_rows(job_id) if row["version"] == request.transcript_version and row["status"] == "generated"),
                None,
            )
            if associated is None:
                raise HTTPException(422, "Transcript version does not exist or failed.")
            if request.span is not None and request.span.end_s > associated.get("duration_s", 0.0) + 0.01:
                raise HTTPException(422, "Claim span falls outside the selected transcript version.")

        claim_id = uuid.uuid4().hex
        created_at = _now()
        base = {
            "id": claim_id,
            "status": "reviewed",
            "text": request.text,
            "transcript_version": request.transcript_version,
            "span": request.span.model_dump() if request.span else None,
            "created_at": created_at,
            "updated_at": created_at,
            "error": None,
            "external_search_consent": request.external_search_consent,
            "external_disclosure": "claim_text_only" if request.external_search_consent else "none",
        }

        if request.analyst_review is not None:
            manual = request.analyst_review
            payload = dict(base, verdict=manual.verdict, rationale=manual.rationale,
                           evidence=[dict(item.model_dump(), provenance="analyst_supplied") for item in manual.evidence],
                           method="analyst", provider=None, model=None, prompt_version=None)
        elif not request.external_search_consent:
            payload = dict(base, verdict="uncheckable",
                           rationale="No source-backed review has been completed. Add analyst evidence or consent to external search.",
                           evidence=[], method="manual_pending", provider=None, model=None, prompt_version=None)
        else:
            if not review_lock.acquire(blocking=False):
                raise HTTPException(409, "Another claim review is running. Retry shortly.")
            try:
                provider_status = claims.status()
                if not provider_status["available"]:
                    error = provider_status["reason"] or "Grok is unavailable."
                    failed = dict(base, status="error", verdict="uncheckable", rationale=error,
                                  evidence=[], method="ai_web_search", provider="xai",
                                  model=provider_status["model"], prompt_version=None, error=error)
                    save_claim(job_id, failed)
                    raise HTTPException(503, error)
                try:
                    review = claims.review(request.text)
                except ClaimReviewError as exc:
                    error = str(exc)
                    failed = dict(base, status="error", verdict="uncheckable", rationale=error,
                                  evidence=[], method="ai_web_search", provider="xai",
                                  model=provider_status["model"], prompt_version=None, error=error)
                    save_claim(job_id, failed)
                    raise HTTPException(503, error) from None
                payload = dict(base, **review)
            finally:
                review_lock.release()
        save_claim(job_id, payload)
        return with_stale(job_id, payload)

    return router
