"""Serve the built landing page at / and the workspace at /app/ from the API origin."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

CHALLENGE_ROOT = Path(__file__).resolve().parents[2]


def _locate(static_root: Path | None) -> tuple[Path | None, Path | None]:
    configured = static_root or (Path(os.environ["ECHOTRACE_STATIC_ROOT"]) if os.environ.get("ECHOTRACE_STATIC_ROOT") else None)
    if configured:
        landing, workspace = configured / "landing", configured / "app"
    else:
        landing, workspace = CHALLENGE_ROOT / "landing" / "dist", CHALLENGE_ROOT / "frontend" / "dist"
    return (landing if (landing / "index.html").is_file() else None,
            workspace if (workspace / "index.html").is_file() else None)


def _file_or_index(folder: Path, relative: str) -> FileResponse:
    root = folder.resolve()
    candidate = (root / relative).resolve() if relative else root / "index.html"
    if candidate.is_file() and candidate.is_relative_to(root):
        cache = "public, max-age=31536000, immutable" if "/assets/" in candidate.as_posix() else "no-cache"
        return FileResponse(candidate, headers={"Cache-Control": cache})
    if Path(relative).suffix:  # a missing asset is a real 404, not the app shell
        raise HTTPException(404, "Not found")
    return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})


def mount_frontends(app: FastAPI, static_root: Path | None = None) -> None:
    landing, workspace = _locate(static_root)

    if workspace is not None:
        @app.get("/app", include_in_schema=False)
        def workspace_root():
            return RedirectResponse("/app/", status_code=308)

        @app.get("/app/{relative:path}", include_in_schema=False)
        def workspace_files(relative: str):
            return _file_or_index(workspace, relative)

    if landing is not None:
        @app.get("/{relative:path}", include_in_schema=False)
        def landing_files(relative: str):
            if relative.startswith("api/"):
                raise HTTPException(404, "Not found")
            return _file_or_index(landing, relative)
