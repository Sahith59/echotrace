"""HTTP routes for sign-in (email/password and Google), profile, settings and personal data."""
from __future__ import annotations

import shutil
import time
import urllib.parse
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from .accounts import AccountError, Accounts, AuthSettings, SESSION_DAYS, safe_next

COOKIE = "et_session"
RATE_WINDOW_S = 60
AUTH_ATTEMPTS_PER_WINDOW = 10
JOB_TABLES = ("analyst_reviews", "transcripts", "claim_reviews", "speaker_comparisons", "detector_comparisons")


def client_address(request: Request, settings: AuthSettings) -> str:
    forwarded = request.headers.get("x-forwarded-for", "") if settings.trust_proxy else ""
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


class RateLimiter:
    def __init__(self, limit: int):
        self.limit = limit
        self.hits: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        now = time.monotonic()
        if len(self.hits) > 5000:
            self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < RATE_WINDOW_S}
        recent = [t for t in self.hits.get(key, []) if now - t < RATE_WINDOW_S]
        if len(recent) >= self.limit:
            raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
        self.hits[key] = [*recent, now]


def set_session(response, token: str, settings: AuthSettings) -> None:
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                        secure=settings.secure_cookies, path="/")


def clear_session(response, settings: AuthSettings) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=settings.secure_cookies)


def delete_jobs(store, job_ids: list[str]) -> int:
    """Remove the recordings, every derived record keyed by them, and their folders."""
    if not job_ids:
        return 0
    root = store.root.resolve()
    with store.connect() as db:
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for start in range(0, len(job_ids), 500):
            batch = job_ids[start:start + 500]
            marks = ",".join("?" for _ in batch)
            for table in JOB_TABLES:
                if table in existing:
                    db.execute(f"DELETE FROM {table} WHERE job_id IN ({marks})", batch)
            db.execute(f"DELETE FROM jobs WHERE id IN ({marks})", batch)
    for job_id in job_ids:
        folder = (store.root / job_id).resolve()
        if folder.parent == root and folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
    return len(job_ids)


def user_job_ids(store, user_id: str) -> list[str]:
    with store.connect() as db:
        return [row[0] for row in db.execute("SELECT id FROM jobs WHERE user_id=?", (user_id,))]


class SignupBody(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""


class LoginBody(BaseModel):
    email: str = ""
    password: str = ""


class ProfileBody(BaseModel):
    name: str


class PasswordBody(BaseModel):
    current: str | None = None
    new: str


class ConfirmBody(BaseModel):
    confirm: str


def create_account_router(store, accounts: Accounts, settings: AuthSettings) -> APIRouter:
    router = APIRouter()
    limiter = RateLimiter(AUTH_ATTEMPTS_PER_WINDOW)
    # A second limit per account, so guessing one password cannot be spread across many addresses.
    account_limiter = RateLimiter(AUTH_ATTEMPTS_PER_WINDOW)

    def token_of(request: Request) -> str | None:
        return request.cookies.get(COOKIE)

    def current(request: Request) -> dict:
        user = accounts.user_for_token(token_of(request))
        if user is None:
            raise HTTPException(401, "Sign in to continue.")
        return user

    def fail(error: AccountError):
        raise HTTPException(error.status, str(error))

    @router.get("/api/auth/providers")
    def providers():
        return {"password": True, "google": accounts.google_enabled}

    @router.get("/api/auth/me")
    def me(request: Request):
        return {"user": accounts.user_for_token(token_of(request))}

    @router.post("/api/auth/signup", status_code=201)
    def signup(body: SignupBody, request: Request):
        limiter.check(client_address(request, settings))
        try:
            user, token = accounts.signup(name=body.name, email=body.email, password=body.password,
                                          user_agent=request.headers.get("user-agent"))
        except AccountError as error:
            fail(error)
        response = JSONResponse({"user": user}, status_code=201)
        set_session(response, token, settings)
        return response

    @router.post("/api/auth/login")
    def login(body: LoginBody, request: Request):
        limiter.check(client_address(request, settings))
        account_limiter.check("login:" + body.email.strip().lower()[:254])
        try:
            user, token = accounts.login(body.email, body.password, user_agent=request.headers.get("user-agent"))
        except AccountError as error:
            fail(error)
        response = JSONResponse({"user": user})
        set_session(response, token, settings)
        return response

    @router.post("/api/auth/logout")
    def logout(request: Request):
        accounts.logout(token_of(request))
        response = JSONResponse({"user": None})
        clear_session(response, settings)
        return response

    @router.get("/api/auth/google/start")
    def google_start(request: Request, next: str = "/app/"):
        limiter.check(client_address(request, settings))
        try:
            return RedirectResponse(accounts.google_begin(safe_next(next)), status_code=302)
        except AccountError:
            return RedirectResponse("/login?error=" + urllib.parse.quote("Google sign-in is not available yet."), status_code=302)

    @router.get("/api/auth/google/callback")
    def google_callback(request: Request, state: str = "", code: str = "", error: str = ""):
        if error or not code:
            return RedirectResponse("/login?error=" + urllib.parse.quote("Google sign-in was cancelled."), status_code=302)
        try:
            _, token, next_path = accounts.google_finish(state, code, user_agent=request.headers.get("user-agent"))
        except AccountError as failure:
            return RedirectResponse("/login?error=" + urllib.parse.quote(str(failure)), status_code=302)
        response = RedirectResponse(next_path, status_code=302)
        set_session(response, token, settings)
        return response

    @router.get("/api/account")
    def account(request: Request):
        user = current(request)
        return {"user": user, "preferences": accounts.preferences(user["id"]),
                "active_sessions": accounts.session_count(user["id"]),
                "recordings": len(user_job_ids(store, user["id"]))}

    @router.patch("/api/account/profile")
    def profile(body: ProfileBody, request: Request):
        user = current(request)
        try:
            return {"user": accounts.update_profile(user["id"], name=body.name)}
        except AccountError as error:
            fail(error)

    @router.post("/api/account/password")
    def password(body: PasswordBody, request: Request):
        user = current(request)
        limiter.check("password:" + user["id"])
        try:
            accounts.change_password(user["id"], current=body.current, new=body.new)
        except AccountError as error:
            fail(error)
        accounts.logout_everywhere(user["id"], keep=token_of(request))
        return {"changed": True}

    @router.get("/api/account/preferences")
    def get_preferences(request: Request):
        return {"preferences": accounts.preferences(current(request)["id"])}

    @router.patch("/api/account/preferences")
    def patch_preferences(patch: dict, request: Request):
        user = current(request)
        try:
            return {"preferences": accounts.update_preferences(user["id"], patch)}
        except AccountError as error:
            fail(error)

    @router.post("/api/account/sessions/revoke-others")
    def revoke_others(request: Request):
        user = current(request)
        return {"revoked": accounts.logout_everywhere(user["id"], keep=token_of(request))}

    @router.get("/api/account/export")
    def export(request: Request):
        user = current(request)
        with store.connect() as db:
            rows = db.execute("SELECT id, filename, status, created_at, result, error, parent_id, transform "
                              "FROM jobs WHERE user_id=? ORDER BY created_at", (user["id"],)).fetchall()
        import json as _json
        analyses = [{**dict(row), "result": _json.loads(row["result"]) if row["result"] else None,
                     "transform": _json.loads(row["transform"]) if row["transform"] else None} for row in rows]
        body = {"exported_at": datetime.now(timezone.utc).isoformat(), "profile": user,
                "preferences": accounts.preferences(user["id"]), "analyses": analyses,
                "note": "Original audio files are not included. Download them from each recording in the workspace."}
        return JSONResponse(body, headers={"Content-Disposition": 'attachment; filename="echotrace-my-data.json"'})

    @router.post("/api/account/recordings/delete")
    def delete_recordings(body: ConfirmBody, request: Request):
        user = current(request)
        if body.confirm != "DELETE":
            raise HTTPException(422, "Type DELETE to confirm.")
        return {"deleted": delete_jobs(store, user_job_ids(store, user["id"]))}

    @router.post("/api/account/delete")
    def delete_account(body: ConfirmBody, request: Request):
        user = current(request)
        if body.confirm != "DELETE":
            raise HTTPException(422, "Type DELETE to confirm.")
        delete_jobs(store, user_job_ids(store, user["id"]))
        accounts.delete_user(user["id"])
        response = JSONResponse({"deleted": True})
        clear_session(response, settings)
        return response

    return router
