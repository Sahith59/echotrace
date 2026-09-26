import time
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from echotrace.accounts import AuthSettings, GoogleConfig
from echotrace.api import create_app

ORIGIN = {"Origin": "https://echotrace.test"}


def fake_analyzer(path, progress=None):
    return {"input": {"filename": path.name}, "synthetic_score": 0.4, "score_kind": "uncalibrated", "limitations": []}


def app_with_auth(tmp_path, **settings):
    auth = AuthSettings(public_origins=("https://echotrace.test",), **settings)
    return create_app(tmp_path, fake_analyzer, auth=auth)


def signup(client, email, name="Analyst"):
    response = client.post("/api/auth/signup", json={"name": name, "email": email, "password": "correct horse battery"}, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()["user"]


def upload(client, name="call.wav"):
    response = client.post("/api/analyses", files={"file": (name, b"audio bytes")}, headers=ORIGIN)
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    for _ in range(200):
        job = client.get(f"/api/analyses/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("analysis did not finish")


def test_product_api_requires_a_session_but_public_routes_stay_open(tmp_path):
    with TestClient(app_with_auth(tmp_path)) as client:
        assert client.get("/api/analyses").status_code == 401
        assert client.post("/api/analyses", files={"file": ("x.wav", b"x")}, headers=ORIGIN).status_code == 401
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/auth/providers").json() == {"password": True, "google": False}
        assert client.get("/api/auth/me").json() == {"user": None}
        guide = client.post("/api/assistant", json={"messages": [{"role": "user", "content": "hello"}]}, headers=ORIGIN)
        assert guide.status_code == 200 and "ECHOTRACE" in guide.json()["text"]


def test_writes_need_a_matching_origin_or_referer(tmp_path):
    with TestClient(app_with_auth(tmp_path)) as client:
        body = {"name": "A", "email": "a@example.org", "password": "correct horse battery"}
        assert client.post("/api/auth/signup", json=body).status_code == 403
        assert client.post("/api/auth/signup", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/auth/signup", json=body, headers={"Referer": "https://echotrace.test/signup"}).status_code == 201


def test_each_user_sees_and_touches_only_their_own_recordings(tmp_path):
    app = app_with_auth(tmp_path)
    with TestClient(app) as alice, TestClient(app) as bob:
        signup(alice, "alice@example.org", "Alice")
        signup(bob, "bob@example.org", "Bob")
        job = upload(alice)
        assert job["status"] == "completed"
        assert [item["id"] for item in alice.get("/api/analyses").json()] == [job["id"]]
        assert bob.get("/api/analyses").json() == []
        for path in ("", "/audio", "/report", "/analyst-review", "/interpretation", "/case-report", "/transcript"):
            assert bob.get(f"/api/analyses/{job['id']}{path}").status_code == 404, path
        assert bob.post(f"/api/analyses/{job['id']}/stress-tests", json={"kind": "mp3"}, headers=ORIGIN).status_code == 404
        assert bob.post("/api/exports", json={"ids": [job["id"]]}, headers=ORIGIN).status_code == 404
        assert alice.post("/api/exports", json={"ids": [job["id"]]}, headers=ORIGIN).status_code == 200


def test_profile_security_and_privacy_settings_round_trip(tmp_path):
    with TestClient(app_with_auth(tmp_path)) as client:
        user = signup(client, "ada@example.org", "Ada")
        profile = client.patch("/api/account/profile", json={"name": "Ada Lovelace"}, headers=ORIGIN)
        assert profile.status_code == 200 and profile.json()["user"]["name"] == "Ada Lovelace"
        prefs = client.patch("/api/account/preferences", json={"ai_interpretation": False}, headers=ORIGIN).json()
        assert prefs["preferences"]["ai_interpretation"] is False
        job = upload(client)
        blocked = client.post(f"/api/analyses/{job['id']}/interpretation", headers=ORIGIN)
        assert blocked.status_code == 403 and "settings" in blocked.json()["detail"].lower()
        changed = client.post("/api/account/password", json={"current": "correct horse battery", "new": "a brand new phrase"}, headers=ORIGIN)
        assert changed.status_code == 200
        export = client.get("/api/account/export").json()
        assert export["profile"]["email"] == user["email"] and [item["id"] for item in export["analyses"]] == [job["id"]]
        assert "password_hash" not in str(export)


def test_deleting_recordings_and_the_account_removes_data_and_signs_out(tmp_path):
    with TestClient(app_with_auth(tmp_path)) as client:
        signup(client, "del@example.org")
        first = upload(client)
        assert (tmp_path / first["id"]).is_dir()
        cleared = client.post("/api/account/recordings/delete", json={"confirm": "DELETE"}, headers=ORIGIN)
        assert cleared.status_code == 200 and cleared.json()["deleted"] == 1
        assert client.get("/api/analyses").json() == [] and not (tmp_path / first["id"]).exists()
        second = upload(client)
        assert client.post("/api/account/delete", json={"confirm": "wrong"}, headers=ORIGIN).status_code == 422
        gone = client.post("/api/account/delete", json={"confirm": "DELETE"}, headers=ORIGIN)
        assert gone.status_code == 200 and not (tmp_path / second["id"]).exists()
        assert client.get("/api/auth/me").json() == {"user": None}
        assert client.post("/api/auth/login", json={"email": "del@example.org", "password": "correct horse battery"}, headers=ORIGIN).status_code == 401


def test_sign_out_everywhere_keeps_only_the_current_session(tmp_path):
    app = app_with_auth(tmp_path)
    with TestClient(app) as laptop, TestClient(app) as phone:
        signup(laptop, "multi@example.org")
        assert phone.post("/api/auth/login", json={"email": "multi@example.org", "password": "correct horse battery"}, headers=ORIGIN).status_code == 200
        assert laptop.post("/api/account/sessions/revoke-others", headers=ORIGIN).status_code == 200
        assert laptop.get("/api/auth/me").json()["user"] is not None
        assert phone.get("/api/auth/me").json()["user"] is None


def test_google_redirect_and_callback_sign_the_user_in(tmp_path):
    def fake_http(method, url, data=None, headers=None):
        if url.endswith("/token"):
            return {"access_token": "t"}
        return {"sub": "g-9", "email": "g@example.org", "email_verified": True, "name": "Gee", "picture": None}

    google = GoogleConfig(client_id="cid", client_secret="secret", redirect_uri="https://echotrace.test/api/auth/google/callback")
    with TestClient(app_with_auth(tmp_path, google=google, http=fake_http), follow_redirects=False) as client:
        assert client.get("/api/auth/providers").json()["google"] is True
        start = client.get("/api/auth/google/start?next=/app/")
        assert start.status_code == 302 and start.headers["location"].startswith("https://accounts.google.com/")
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        done = client.get(f"/api/auth/google/callback?state={state}&code=abc")
        assert done.status_code == 302 and done.headers["location"] == "/app/"
        assert "et_session=" in done.headers["set-cookie"] and "HttpOnly" in done.headers["set-cookie"]
        assert client.get("/api/auth/me").json()["user"]["email"] == "g@example.org"
        failed = client.get("/api/auth/google/callback?error=access_denied")
        assert failed.status_code == 302 and failed.headers["location"].startswith("/login?error=")


def test_password_guessing_against_one_account_is_limited_even_across_addresses(tmp_path):
    with TestClient(app_with_auth(tmp_path, trust_proxy=True)) as client:
        signup(client, "target@example.org")
        statuses = []
        for attempt in range(12):
            headers = {**ORIGIN, "X-Forwarded-For": f"203.0.113.{attempt}"}
            statuses.append(client.post("/api/auth/login", json={"email": "Target@example.org", "password": "wrong guess!!"}, headers=headers).status_code)
        assert statuses[:10] == [401] * 10 and statuses[10:] == [429, 429]


def test_proxied_api_host_is_accepted_only_when_configured(tmp_path, monkeypatch):
    with TestClient(app_with_auth(tmp_path), base_url="https://api.echotrace.test") as client:
        assert client.get("/api/health").status_code == 400
    monkeypatch.setenv("ECHOTRACE_ALLOWED_HOSTS", "api.echotrace.test")
    with TestClient(app_with_auth(tmp_path / "second"), base_url="https://api.echotrace.test") as client:
        assert client.get("/api/health").status_code == 200
