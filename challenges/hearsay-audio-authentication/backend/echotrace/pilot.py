"""Read-only catalog of the pinned MLAAD-tiny diagnostic sample."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response


REVISION = "9143e5ea709575ebab6bec52840a1043aada7bb1"
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "public-pilot"
DEFAULT_PROVENANCE = Path(__file__).resolve().parents[2] / "reports" / "public-pilot" / "provenance.json"
NOTE = "Small selected diagnostic sample; results are not representative or calibrated."
ID_PATTERN = re.compile(r"[0-9a-f]{16}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _catalog(provenance_path: Path) -> tuple[list[dict], str | None]:
    try:
        data = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], "Pilot catalog is unavailable."
    if not isinstance(data, dict) or data.get("dataset") != "mueller91/MLAAD-tiny" or data.get("revision") != REVISION:
        return [], "Pilot catalog is invalid."
    records = data.get("files")
    if not isinstance(records, list):
        return [], "Pilot catalog is invalid."
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            return [], "Pilot catalog is invalid."
        file_id = record.get("file_id")
        raw_path = record.get("path")
        digest = record.get("sha256")
        if (not isinstance(file_id, str) or not ID_PATTERN.fullmatch(file_id)
                or file_id in seen or not isinstance(raw_path, str)
                or not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest)
                or record.get("label") not in (0, 1)
                or type(record.get("bytes")) is not int or record["bytes"] < 0):
            return [], "Pilot catalog is invalid."
        seen.add(file_id)
    return records, None


def _verified_audio(root: Path, record: dict) -> bytes | None:
    raw_path = record["path"]
    relative = PurePosixPath(raw_path)
    if (not raw_path or "\\" in raw_path or relative.is_absolute()
            or any(part in (".", "..", "") for part in raw_path.split("/"))):
        return None
    candidate = root.joinpath(*relative.parts)
    try:
        resolved_root = root.resolve(strict=True)
        # Reject links even when they point to another location inside the audio root.
        if any(path.is_symlink() for path in (root, *[root.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)])):
            return None
        resolved_file = candidate.resolve(strict=True)
        resolved_file.relative_to(resolved_root)
        if not resolved_file.is_file() or resolved_file.stat().st_size != record["bytes"]:
            return None
        content = resolved_file.read_bytes()
    except (OSError, ValueError):
        return None
    if hashlib.sha256(content).hexdigest() != record["sha256"]:
        return None
    return content


def create_pilot_router(*, root: Path | None = None, provenance_path: Path | None = None) -> APIRouter:
    """Build routes with a local audio root; the provenance is the sole ID allowlist."""
    root = Path(root) if root is not None else DEFAULT_ROOT
    provenance_path = Path(provenance_path) if provenance_path is not None else DEFAULT_PROVENANCE
    router = APIRouter()

    @router.get("/api/examples")
    def examples():
        records, reason = _catalog(provenance_path)
        result = {"dataset": "MLAAD-tiny", "note": NOTE,
                  "examples": [{"id": record["file_id"],
                                "filename": PurePosixPath(record["path"]).name,
                                "label": "genuine" if record["label"] == 0 else "synthetic",
                                "available": _verified_audio(root, record) is not None}
                               for record in records]}
        if reason:
            result["reason"] = reason
        return result

    @router.get("/api/examples/{example_id}/audio")
    def audio(example_id: str):
        if not ID_PATTERN.fullmatch(example_id):
            raise HTTPException(404, "Example not found")
        records, _ = _catalog(provenance_path)
        record = next((item for item in records if item["file_id"] == example_id), None)
        if record is None:
            raise HTTPException(404, "Example not found")
        content = _verified_audio(root, record)
        if content is None:
            raise HTTPException(404, "Example audio is unavailable")
        return Response(content, media_type="audio/wav")

    return router
