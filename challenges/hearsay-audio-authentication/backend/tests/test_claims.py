import pytest

from echotrace.claims import (
    ClaimReviewError,
    GrokClaimReviewer,
    GroqClaimReviewer,
    SEARCH_UNAVAILABLE_REASON,
    validate_public_url,
)


def test_groq_search_fails_closed_even_when_key_is_configured():
    called = []
    reviewer = GroqClaimReviewer(
        model="openai/gpt-oss-20b",
        api_key="not-a-real-key",
        transport=lambda payload: called.append(payload),
    )

    status = reviewer.status()

    assert status == {
        "available": False,
        "configured": True,
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "reason": SEARCH_UNAVAILABLE_REASON,
        "search_supported": False,
        "connection_verified": False,
    }
    with pytest.raises(ClaimReviewError, match="source provenance"):
        reviewer.review("A factual claim")
    assert called == []


def test_groq_claim_config_is_separate_and_never_uses_xai_key(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "XAI_API_KEY=must-not-be-used\n"
        "ECHOTRACE_LLM_MODEL=interpretation-only\n"
        "ECHOTRACE_CLAIM_MODEL=openai/gpt-oss-120b\n"
    )
    monkeypatch.setattr("echotrace.claims.ENV_PATH", env)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ECHOTRACE_CLAIM_MODEL", raising=False)

    reviewer = GroqClaimReviewer()
    assert reviewer._config() == ("openai/gpt-oss-120b", "")
    assert reviewer.status()["configured"] is False

    env.write_text(
        "GROQ_API_KEY=groq-secret\n"
        "ECHOTRACE_CLAIM_MODEL=openai/gpt-oss-20b\n"
    )
    assert reviewer._config() == ("openai/gpt-oss-20b", "groq-secret")
    assert reviewer.status()["configured"] is True


def test_legacy_reviewer_name_is_a_compatibility_alias():
    assert GrokClaimReviewer is GroqClaimReviewer


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "http://localhost/admin",
    "http://127.0.0.1/private",
    "https://user:password@example.com/report",
])
def test_evidence_urls_reject_nonpublic_or_credential_targets(url):
    with pytest.raises(ValueError, match="public|HTTP"):
        validate_public_url(url)
