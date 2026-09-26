"""User accounts: email/password and Google sign-in, sessions and per-user preferences.

Passwords use salted scrypt. Session tokens are random and stored only as
SHA-256 digests. Google sign-in uses the authorization-code flow with PKCE
and a single-use state; only verified Google emails are accepted.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

SESSION_DAYS = 30
STATE_MINUTES = 10
MIN_PASSWORD = 10
MAX_PASSWORD = 200
MAX_NAME = 80
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SCRYPT = {"n": 16384, "r": 8, "p": 1, "dklen": 64}
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DEFAULT_NEXT = "/app/"
DEFAULT_PREFERENCES = {"ai_interpretation": True, "default_view": "investigation", "time_format": "12h", "motion": "system"}
ALLOWED_PREFERENCES = {
    "ai_interpretation": (True, False),
    "default_view": ("investigation", "batch"),
    "time_format": ("12h", "24h"),
    "motion": ("system", "reduce"),
}

Http = Callable[..., dict]


class AccountError(ValueError):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class GoogleConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class AuthSettings:
    """Enables accounts on the product API. Omit it (tests, local use) to keep the open single-user mode."""
    public_origins: tuple[str, ...] = ()
    google: GoogleConfig | None = None
    http: Http | None = None
    secure_cookies: bool = False
    trust_proxy: bool = False
    extra: dict = field(default_factory=dict)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **SCRYPT)
    return hmac.compare_digest(actual, bytes.fromhex(digest_hex))


_DECOY_HASH = _hash_password("decoy-password-for-equal-timing")


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _clean_name(value) -> str:
    name = " ".join(value.split()) if isinstance(value, str) else ""
    if not name or len(name) > MAX_NAME or any(ord(c) < 32 for c in name):
        raise AccountError(f"Enter your name using 1 to {MAX_NAME} characters.", 422)
    return name


def _clean_email(value) -> str:
    email = value.strip().lower() if isinstance(value, str) else ""
    if not email or len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise AccountError("Enter a valid email address, like name@example.org.", 422)
    return email


def _clean_password(value) -> str:
    if not isinstance(value, str) or not MIN_PASSWORD <= len(value) <= MAX_PASSWORD:
        raise AccountError(f"Use a password with at least {MIN_PASSWORD} characters.", 422)
    return value


def safe_next(value) -> str:
    """Only same-site absolute paths; anything else falls back to the workspace."""
    if isinstance(value, str) and value.startswith("/") and not value.startswith("//") and "\\" not in value and len(value) <= 300:
        return value
    return DEFAULT_NEXT


def _default_http(method: str, url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        "Accept": "application/json", "User-Agent": "ECHOTRACE/1.0", **(headers or {})})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read(65536))


class Accounts:
    def __init__(self, connect: Callable[[], sqlite3.Connection], *, now: Callable[[], datetime] | None = None,
                 google: GoogleConfig | None = None, http: Http | None = None):
        self.connect = connect
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.google = google
        self.http = http or _default_http
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    password_hash TEXT, google_sub TEXT UNIQUE, avatar_url TEXT,
                    email_verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                    preferences TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL, user_agent TEXT);
                CREATE INDEX IF NOT EXISTS sessions_by_user ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY, verifier TEXT NOT NULL, next_path TEXT NOT NULL, expires_at TEXT NOT NULL);
            """)

    @property
    def google_enabled(self) -> bool:
        return self.google is not None

    # --- helpers -----------------------------------------------------------------
    def _iso(self, delta: timedelta = timedelta()) -> str:
        return (self.now() + delta).isoformat()

    @staticmethod
    def _public(row) -> dict:
        return {"id": row["id"], "email": row["email"], "name": row["name"], "avatar_url": row["avatar_url"],
                "created_at": row["created_at"], "has_password": bool(row["password_hash"]),
                "google_linked": bool(row["google_sub"]), "email_verified": bool(row["email_verified"])}

    def _row(self, db, user_id: str):
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise AccountError("Account not found.", 404)
        return row

    def _open_session(self, db, user_id: str, user_agent: str | None = None) -> str:
        token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (self._iso(),))
        db.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (
            _digest(token), user_id, self._iso(), self._iso(timedelta(days=SESSION_DAYS)), (user_agent or "")[:200]))
        return token

    # --- email and password ---------------------------------------------------------
    def signup(self, *, name, email, password, user_agent: str | None = None):
        name, email, password = _clean_name(name), _clean_email(email), _clean_password(password)
        password_hash = _hash_password(password)  # hash first: existing and new emails cost the same time
        with self.connect() as db:
            if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                raise AccountError("An account with this email already exists. Log in instead.", 409)
            user_id = uuid.uuid4().hex
            db.execute("INSERT INTO users (id,email,name,password_hash,created_at,preferences) VALUES (?,?,?,?,?,?)",
                       (user_id, email, name, password_hash, self._iso(), json.dumps(DEFAULT_PREFERENCES)))
            token = self._open_session(db, user_id, user_agent)
            return self._public(self._row(db, user_id)), token

    def login(self, email, password, user_agent: str | None = None):
        email = email.strip().lower() if isinstance(email, str) else ""
        password = password[:MAX_PASSWORD] if isinstance(password, str) else ""
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone() if email else None
            matches = _verify_password(password, (row["password_hash"] if row else None) or _DECOY_HASH)
            if row is None or not row["password_hash"] or not matches:
                raise AccountError("Email or password is incorrect.", 401)
            return self._public(row), self._open_session(db, row["id"], user_agent)

    def user_for_token(self, token: str | None):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute("SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id "
                             "WHERE token_hash=? AND expires_at > ?", (_digest(token), self._iso())).fetchone()
        return self._public(row) if row else None

    def logout(self, token: str | None) -> None:
        if token:
            with self.connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (_digest(token),))

    def logout_everywhere(self, user_id: str, keep: str | None = None) -> int:
        with self.connect() as db:
            cursor = db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash != ?", (user_id, _digest(keep or "")))
            return cursor.rowcount

    def session_count(self, user_id: str) -> int:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM sessions WHERE user_id=? AND expires_at > ?",
                              (user_id, self._iso())).fetchone()[0]

    # --- profile ---------------------------------------------------------------------
    def update_profile(self, user_id: str, *, name) -> dict:
        name = _clean_name(name)
        with self.connect() as db:
            db.execute("UPDATE users SET name=? WHERE id=?", (name, user_id))
            return self._public(self._row(db, user_id))

    def change_password(self, user_id: str, *, current, new) -> None:
        new = _clean_password(new)
        with self.connect() as db:
            row = self._row(db, user_id)
            if row["password_hash"] and not _verify_password(current if isinstance(current, str) else "", row["password_hash"]):
                raise AccountError("Your current password is incorrect.", 403)
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (_hash_password(new), user_id))

    def preferences(self, user_id: str) -> dict:
        with self.connect() as db:
            stored = json.loads(self._row(db, user_id)["preferences"] or "{}")
        return {**DEFAULT_PREFERENCES, **{k: v for k, v in stored.items() if k in ALLOWED_PREFERENCES}}

    def update_preferences(self, user_id: str, patch) -> dict:
        if not isinstance(patch, dict) or not patch:
            raise AccountError("Send at least one setting to change.", 422)
        for key, value in patch.items():
            if key not in ALLOWED_PREFERENCES or value not in ALLOWED_PREFERENCES[key] or type(value) is not type(ALLOWED_PREFERENCES[key][0]):
                raise AccountError(f"Unsupported setting: {key}.", 422)
        merged = {**self.preferences(user_id), **patch}
        with self.connect() as db:
            db.execute("UPDATE users SET preferences=? WHERE id=?", (json.dumps(merged), user_id))
        return merged

    def delete_user(self, user_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            db.execute("DELETE FROM users WHERE id=?", (user_id,))

    # --- Google ----------------------------------------------------------------------
    def google_begin(self, next_path) -> str:
        if not self.google:
            raise AccountError("Google sign-in is not configured.", 503)
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        with self.connect() as db:
            db.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (self._iso(),))
            db.execute("INSERT INTO oauth_states VALUES (?,?,?,?)",
                       (state, verifier, safe_next(next_path), self._iso(timedelta(minutes=STATE_MINUTES))))
        return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": self.google.client_id, "redirect_uri": self.google.redirect_uri, "response_type": "code",
            "scope": "openid email profile", "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256", "prompt": "select_account"})

    def google_finish(self, state, code, user_agent: str | None = None):
        if not self.google:
            raise AccountError("Google sign-in is not configured.", 503)
        with self.connect() as db:
            row = db.execute("SELECT * FROM oauth_states WHERE state=?", (state or "",)).fetchone()
            db.execute("DELETE FROM oauth_states WHERE state=?", (state or "",))
        if row is None or row["expires_at"] <= self._iso() or not code:
            raise AccountError("Google sign-in expired or was not started here. Try again.", 400)
        try:
            tokens = self.http("POST", GOOGLE_TOKEN_URL, data={
                "code": code, "client_id": self.google.client_id, "client_secret": self.google.client_secret,
                "redirect_uri": self.google.redirect_uri, "grant_type": "authorization_code", "code_verifier": row["verifier"]})
            profile = self.http("GET", GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
        except Exception:
            raise AccountError("Google did not confirm the sign-in. Try again.", 502) from None
        sub, email = profile.get("sub"), profile.get("email")
        if not sub or not email or profile.get("email_verified") is not True:
            raise AccountError("Google did not provide a verified email address.", 403)
        email = _clean_email(email)
        name = profile.get("name") or email.split("@")[0]
        picture = profile.get("picture") if isinstance(profile.get("picture"), str) and profile["picture"].startswith("https://") else None
        with self.connect() as db:
            user = db.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
            if user is None:
                user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if user is not None:
                    if not user["email_verified"]:
                        # Nobody proved ownership of this email before; revoke whoever set the password.
                        db.execute("UPDATE users SET password_hash=NULL WHERE id=?", (user["id"],))
                        db.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
                    db.execute("UPDATE users SET google_sub=?, email_verified=1, avatar_url=COALESCE(avatar_url, ?) WHERE id=?",
                               (sub, picture, user["id"]))
                    user_id = user["id"]
                else:
                    user_id = uuid.uuid4().hex
                    db.execute("INSERT INTO users (id,email,name,google_sub,avatar_url,email_verified,created_at,preferences) "
                               "VALUES (?,?,?,?,?,1,?,?)", (user_id, email, _clean_name(name), sub, picture, self._iso(),
                                                              json.dumps(DEFAULT_PREFERENCES)))
            else:
                user_id = user["id"]
            token = self._open_session(db, user_id, user_agent)
            return self._public(self._row(db, user_id)), token, row["next_path"]


def settings_from_env(environ: dict | None = None) -> AuthSettings | None:
    """Production switch. Auth turns on when a public URL is configured or ECHOTRACE_AUTH=required."""
    import os
    from pathlib import Path

    from dotenv import dotenv_values

    env_path = Path(__file__).resolve().parents[4] / ".env"
    values = {**(dotenv_values(env_path) if env_path.is_file() else {}), **(environ if environ is not None else os.environ)}
    public_url = (values.get("ECHOTRACE_PUBLIC_URL") or "").rstrip("/")
    mode = (values.get("ECHOTRACE_AUTH") or ("required" if public_url else "disabled")).lower()
    if mode == "disabled":
        return None
    extra = [o.strip().rstrip("/") for o in (values.get("ECHOTRACE_ALLOWED_ORIGINS") or "").split(",") if o.strip()]
    origins = tuple(dict.fromkeys([o for o in [public_url, *extra] if o]))
    client_id = (values.get("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (values.get("GOOGLE_CLIENT_SECRET") or "").strip()
    base = public_url or "http://127.0.0.1:8000"
    google = GoogleConfig(client_id, client_secret, f"{base}/api/auth/google/callback") if client_id and client_secret else None
    return AuthSettings(public_origins=origins, google=google, secure_cookies=base.startswith("https://"),
                        trust_proxy=values.get("ECHOTRACE_TRUST_PROXY") == "1")
