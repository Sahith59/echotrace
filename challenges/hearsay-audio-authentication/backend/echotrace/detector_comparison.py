"""Optional research-only comparison against the pinned NII candidate detector."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .audio import AudioError, decode_audio, measure_audio
from .nii_candidate import MIN_SAMPLES, MAX_DURATION_S, candidate_status, score_samples
from .model_provenance import is_legacy_aasist


PARITY_PATH = Path(__file__).with_name("nii_parity.json")
PARITY_SHA256 = "63cce2d5d70e7ac4c507452228cc913fc738bf2a3402fd56640287add4c0e6ff"
PARITY_PROVENANCE = {
    "evidence_job": "4504660",
    "reference_sha256": "57b300af09cbf887d0c2d2ca67a62f5650ffc23d3f609aeca62e5496c3eda038",
    "fixed_bundle_sha256": "f4e7250aa2053d7639334d47f6be7b9699afb4a1f88c034fd44f8530a043e12a",
    "weights_sha256": "828ee456122f86d5d631cb7895a10e5c62c78a4fcb8a8b1c42cb5838a9abcfe0",
    "adapter_red_commit": "512c3e5",
    "adapter_green_commit": "6cc6fed",
    "source_revision": "0dea622bde8f064c8ee5a557f2598643123fc6b6",
}
LIMITATION = (
    "Experimental, uncalibrated research comparison. The score difference is descriptive, not confidence, "
    "and neither score establishes authenticity. Existing project candidates failed promotion gates; this "
    "research comparison does not alter that record and never replaces or changes the primary AASIST-L result."
)


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _parity_status(path: Path = PARITY_PATH) -> dict:
    if not path.is_file():
        return {"approved": False, "reason": "Release parity marker is missing."}
    if _sha256(path) != PARITY_SHA256:
        return {"approved": False, "reason": "Release parity marker failed SHA-256 verification."}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        approved = (
            value.get("passed") is True
            and value.get("case_count") == 5
            and value.get("logit_tolerance") == 0.001
            and value.get("probability_tolerance") == 0.0001
            and float(value.get("max_abs_logit_difference")) <= 0.001
            and float(value.get("max_abs_probability_difference")) <= 0.0001
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        approved = False
    return {"approved": approved, "reason": None if approved else "Release parity marker schema or thresholds did not pass."}


def comparison_status() -> dict:
    model = candidate_status()
    parity = _parity_status()
    available = bool(model.get("available") and parity["approved"])
    reason = None if available else (model.get("reason") or parity["reason"])
    return {**model, "available": available, "reason": reason, "parity_approved": parity["approved"],
            "parity_sha256": PARITY_SHA256, "parity_provenance": PARITY_PROVENANCE,
            "experimental": True, "research_only": True,
            "promotion_status": "research_only_not_promoted", "limitation": LIMITATION}


def create_detector_comparison_router(store, scorer=None, status_provider=None):
    score = scorer or score_samples
    status_source = status_provider or comparison_status
    router = APIRouter()
    lock = threading.Lock()
    with store.connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS detector_comparisons (
            job_id TEXT PRIMARY KEY, report TEXT NOT NULL, input_sha TEXT NOT NULL)""")

    def current_status():
        return {**status_source(), "experimental": True, "research_only": True,
                "promotion_status": "research_only_not_promoted", "limitation": LIMITATION}

    def job_for(job_id: str):
        try:
            job = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "Recording not found") from None
        if job["status"] != "completed" or not isinstance(job.get("result"), dict):
            raise HTTPException(409, "Complete the primary analysis before comparing detectors.")
        if job.get("parent_id"):
            raise HTTPException(422, "Detector comparison is available only for the original recording.")
        if not is_legacy_aasist(job["result"].get("model")):
            raise HTTPException(
                422,
                "Research comparison is only available for legacy AASIST-L primary results; "
                "NII-on-NII comparison is not meaningful.",
            )
        primary = job["result"].get("synthetic_score")
        if not isinstance(primary, (int, float)) or not math.isfinite(primary) or not 0 <= primary <= 1:
            raise HTTPException(422, "The primary detector has no finite synthesis score to compare.")
        path = Path(job["path"])
        if not path.is_file():
            raise HTTPException(409, "The original recording is missing.")
        actual_sha = _sha256(path)
        expected_sha = (job["result"].get("input") or {}).get("sha256")
        if actual_sha != expected_sha:
            raise HTTPException(409, "The original recording changed after primary analysis.")
        return job, path, actual_sha

    def cached(job, actual_sha: str, model: dict):
        with store.connect() as db:
            row = db.execute("SELECT report,input_sha FROM detector_comparisons WHERE job_id=?", (job["id"],)).fetchone()
        if row is None:
            return {"status": "not_generated"}
        report = json.loads(row["report"])
        valid = (
            row["input_sha"] == actual_sha == report.get("input_sha256")
            and report.get("primary_score") == job["result"].get("synthetic_score")
            and report.get("primary_model") == job["result"].get("model")
            and (report.get("model") or {}).get("weights_sha256") == model.get("weights_sha256")
        )
        if not valid:
            raise HTTPException(409, "Saved detector comparison no longer matches the source or model provenance.")
        return report

    @router.get("/api/detector-comparison/status")
    def status():
        return current_status()

    @router.get("/api/analyses/{job_id}/detector-comparison")
    def get(job_id: str):
        job, _, actual_sha = job_for(job_id)
        return cached(job, actual_sha, current_status())

    @router.post("/api/analyses/{job_id}/detector-comparison")
    def generate(job_id: str):
        if not lock.acquire(blocking=False):
            raise HTTPException(409, "Another detector comparison is running. Try again shortly.")
        try:
            job, path, actual_sha = job_for(job_id)
            model = current_status()
            if not model.get("available") or not model.get("parity_approved"):
                raise HTTPException(503, model.get("reason") or "Experimental detector is unavailable.")
            saved = cached(job, actual_sha, model)
            if saved["status"] == "generated":
                return saved
            try:
                samples, input_info = decode_audio(path)
            except AudioError as exc:
                raise HTTPException(422, str(exc)) from None
            if len(samples) < MIN_SAMPLES:
                raise HTTPException(422, "Recording is too short for the experimental detector (minimum 400 samples).")
            if input_info["duration_s"] > MAX_DURATION_S or len(samples) > 16000 * MAX_DURATION_S:
                raise HTTPException(422, "Recording exceeds the experimental detector's 30-second whole-file limit.")
            _, _, quiet = measure_audio(samples)
            if quiet:
                raise HTTPException(422, "Recording is too quiet for a defensible detector comparison.")
            try:
                candidate = score(samples)
                candidate_score = float(candidate["score"])
                raw_logits = [float(value) for value in candidate["raw_logits"]]
            except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                raise HTTPException(422, f"Experimental detector could not score this recording: {exc}") from None
            if not math.isfinite(candidate_score) or not 0 <= candidate_score <= 1 or not raw_logits or not all(map(math.isfinite, raw_logits)):
                raise HTTPException(422, "Experimental detector returned an invalid score.")
            primary_score = float(job["result"]["synthetic_score"])
            report = {
                "status": "generated", "experimental": True, "research_only": True,
                "promotion_status": "research_only_not_promoted", "primary_score_unchanged": True,
                "primary_score": primary_score, "candidate_score": candidate_score,
                "score_difference": round(candidate_score - primary_score, 10),
                "score_kind": "uncalibrated", "raw_logits": raw_logits,
                "model": {key: model.get(key) for key in ("name", "version", "upstream_revision", "source_revision", "weights_sha256", "device")},
                "primary_model": job["result"].get("model"),
                "primary_provenance": {"score_kind": job["result"].get("score_kind"),
                                       "aggregation": job["result"].get("aggregation")},
                "input_sha256": actual_sha, "duration_s": input_info["duration_s"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "configuration": {"fake_class_index": 0, "aggregation": candidate.get("aggregation", "whole_file_layer_norm_mean_pool")},
                "preprocessing": {"decode": "mono_float32", "analysis_sample_rate": 16000,
                                  "whole_file": True, "min_samples": MIN_SAMPLES, "max_duration_s": MAX_DURATION_S,
                                  "padding": "none", "truncation": "rejected"},
                "parity": {"approved": True, "marker_sha256": model.get("parity_sha256")},
                "limitation": LIMITATION,
            }
            try:
                source_unchanged = path.is_file() and _sha256(path) == actual_sha
            except OSError:
                source_unchanged = False
            if not source_unchanged:
                raise HTTPException(409, "The original recording changed while detector comparison was running.")
            encoded = json.dumps(report, allow_nan=False, separators=(",", ":"))
            try:
                with store.connect() as db:
                    db.execute("INSERT INTO detector_comparisons(job_id,report,input_sha) VALUES (?,?,?)",
                               (job_id, encoded, actual_sha))
            except sqlite3.IntegrityError:
                return cached(job, actual_sha, model)
            return report
        finally:
            lock.release()

    return router
