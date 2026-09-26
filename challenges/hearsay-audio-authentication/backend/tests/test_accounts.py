from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from echotrace.accounts import Accounts, AccountError, GoogleConfig
from echotrace.api import Store

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
VALID = {"name": "Ada Analyst", "email": "Ada@Example.org", "password": "correct horse battery"}


def make(tmp_path, *, now=None, google=None, http=None):
    store = Store(tmp_path)
    clock = now or (lambda: NOW)
    return store, Accounts(store.connect, now=clock, google=google, http=http)


def test_signup_normalizes_email_hashes_password_and_opens_a_session(tmp_path):
    store, accounts = make(tmp_path)
    user, token = accounts.signup(**VALID)
    assert user["email"] == "ada@example.org" and user["name"] == "Ada Analyst"
    assert user["has_password"] is True and user["google_linked"] is False
    assert accounts.user_for_token(token)["id"] == user["id"]
    with store.connect() as db:
        row = db.execute("SELECT password_hash FROM users").fetchone()
    assert row["password_hash"].startswith("scrypt$") and VALID["password"] not in row["password_hash"]
    assert "password_hash" not in user


@pytest.mark.parametrize("patch,status,message", [
    ({"email": "not-an-email"}, 422, "email"),
    ({"password": "short"}, 422, "10 characters"),
    ({"name": "   "}, 422, "name"),
])
def test_signup_rejects_invalid_input(tmp_path, patch, status, message):
    _, accounts = make(tmp_path)
    with pytest.raises(AccountError) as error:
        accounts.signup(**{**VALID, **patch})
    assert error.value.status == status and message in str(error.value).lower()


def test_duplicate_email_and_wrong_password_have_clear_outcomes(tmp_path):
    _, accounts = make(tmp_path)
    accounts.signup(**VALID)
    with pytest.raises(AccountError) as duplicate:
        accounts.signup(**{**VALID, "email": "ADA@example.org"})
    assert duplicate.value.status == 409
    for email, password in (("ada@example.org", "wrong password!"), ("nobody@example.org", VALID["password"])):
        with pytest.raises(AccountError) as failure:
            accounts.login(email, password)
        assert failure.value.status == 401 and str(failure.value) == "Email or password is incorrect."


def test_sessions_expire_and_can_be_revoked_individually_or_everywhere(tmp_path):
    clock = {"now": NOW}
    _, accounts = make(tmp_path, now=lambda: clock["now"])
    user, first = accounts.signup(**VALID)
    _, second = accounts.login("ada@example.org", VALID["password"])
    _, third = accounts.login("ada@example.org", VALID["password"])
    accounts.logout(first)
    assert accounts.user_for_token(first) is None and accounts.user_for_token(second)
    accounts.logout_everywhere(user["id"], keep=second)
    assert accounts.user_for_token(third) is None and accounts.user_for_token(second)
    clock["now"] = NOW + timedelta(days=31)
    assert accounts.user_for_token(second) is None


def test_profile_password_and_preferences_are_validated(tmp_path):
    _, accounts = make(tmp_path)
    user, _ = accounts.signup(**VALID)
    assert accounts.update_profile(user["id"], name="  Ada   Lovelace ")["name"] == "Ada Lovelace"
    with pytest.raises(AccountError):
        accounts.change_password(user["id"], current="wrong password!", new="another long phrase")
    accounts.change_password(user["id"], current=VALID["password"], new="another long phrase")
    assert accounts.login("ada@example.org", "another long phrase")[0]["id"] == user["id"]
    prefs = accounts.preferences(user["id"])
    assert prefs == {"ai_interpretation": True, "default_view": "investigation", "time_format": "12h", "motion": "system"}
    assert accounts.update_preferences(user["id"], {"ai_interpretation": False, "time_format": "24h"})["ai_interpretation"] is False
    with pytest.raises(AccountError):
        accounts.update_preferences(user["id"], {"time_format": "36h"})
    with pytest.raises(AccountError):
        accounts.update_preferences(user["id"], {"unknown": 1})


class FakeGoogle:
    def __init__(self, profile):
        self.profile = profile
        self.calls = []

    def __call__(self, method, url, data=None, headers=None):
        self.calls.append((method, url, data))
        if url.endswith("/token"):
            assert data["code"] == "auth-code" and data["code_verifier"]
            return {"access_token": "google-access-token"}
        return self.profile


GOOGLE = GoogleConfig(client_id="client-123", client_secret="secret-456", redirect_uri="https://echotrace.test/api/auth/google/callback")


def google_login(accounts, next_path="/app/"):
    url = accounts.google_begin(next_path)
    query = parse_qs(urlsplit(url).query)
    assert query["client_id"] == ["client-123"] and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [GOOGLE.redirect_uri]
    return accounts.google_finish(query["state"][0], "auth-code")


def test_google_sign_in_creates_a_verified_account_and_respects_safe_next_paths(tmp_path):
    fake = FakeGoogle({"sub": "g-1", "email": "Grace@Example.org", "email_verified": True, "name": "Grace", "picture": "https://lh3.googleusercontent.com/a/x"})
    _, accounts = make(tmp_path, google=GOOGLE, http=fake)
    user, token, next_path = google_login(accounts, "/app/")
    assert user["email"] == "grace@example.org" and user["google_linked"] and not user["has_password"]
    assert next_path == "/app/" and accounts.user_for_token(token)["id"] == user["id"]
    again, _, unsafe = google_login(accounts, "https://evil.example/steal")
    assert again["id"] == user["id"] and unsafe == "/app/"


def test_google_state_is_single_use_and_unverified_emails_are_refused(tmp_path):
    fake = FakeGoogle({"sub": "g-2", "email": "x@example.org", "email_verified": False, "name": "X"})
    _, accounts = make(tmp_path, google=GOOGLE, http=fake)
    state = parse_qs(urlsplit(accounts.google_begin("/app/")).query)["state"][0]
    with pytest.raises(AccountError):
        accounts.google_finish(state, "auth-code")
    with pytest.raises(AccountError):
        accounts.google_finish(state, "auth-code")
    with pytest.raises(AccountError):
        accounts.google_finish("forged-state", "auth-code")


def test_google_sign_in_takes_over_an_unverified_password_squatter_safely(tmp_path):
    # Someone pre-registers the victim's email with a password; the real owner then signs in with Google.
    _, accounts = make(tmp_path, google=GOOGLE, http=FakeGoogle(
        {"sub": "g-3", "email": "victim@example.org", "email_verified": True, "name": "Victim"}))
    squatter, squatter_token = accounts.signup(name="Squatter", email="victim@example.org", password="attacker phrase 123")
    owner, _, _ = google_login(accounts)
    assert owner["id"] == squatter["id"] and owner["google_linked"] and owner["has_password"] is False
    assert accounts.user_for_token(squatter_token) is None
    with pytest.raises(AccountError):
        accounts.login("victim@example.org", "attacker phrase 123")


def test_google_is_unavailable_without_configuration(tmp_path):
    _, accounts = make(tmp_path)
    assert accounts.google_enabled is False
    with pytest.raises(AccountError) as error:
        accounts.google_begin("/app/")
    assert error.value.status == 503
