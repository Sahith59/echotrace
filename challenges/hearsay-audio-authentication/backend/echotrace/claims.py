"""Claim evidence validation and fail-closed Groq hosted-search status."""
from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
DEFAULT_CLAIM_MODEL = "openai/gpt-oss-20b"
SEARCH_UNAVAILABLE_REASON = (
    "Hosted Groq claim search is disabled because this integration has not validated a URL-level "
    "source provenance contract for Groq's current browser-search API. Record an analyst review "
    "with source URLs instead."
)
VERDICTS = {"supported", "contradicted", "insufficient_evidence", "uncheckable"}


class ClaimReviewError(ValueError):
    pass


def validate_public_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError("Evidence URL is invalid.")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Evidence URL must be a public HTTP(S) URL without credentials.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".localhost", ".local")):
        raise ValueError("Evidence URL must use a public hostname.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname:
            raise ValueError("Evidence URL must use a public hostname.") from None
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            raise ValueError("Evidence URL must use a public hostname.") from None
        if len(ascii_hostname) > 253 or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in ascii_hostname.split(".")
        ):
            raise ValueError("Evidence URL must use a public hostname.")
    else:
        if not address.is_global:
            raise ValueError("Evidence URL must use a public hostname.")
    return value


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    url: str = Field(min_length=8, max_length=2000)
    title: str | None = Field(default=None, max_length=300)
    publisher: str | None = Field(default=None, max_length=200)
    published_at: str | None = Field(default=None, max_length=40)
    quote: str | None = Field(default=None, max_length=300)
    stance: Literal["supports", "contradicts", "context"]


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    verdict: Literal["supported", "contradicted", "insufficient_evidence", "uncheckable"]
    rationale: str = Field(min_length=1, max_length=1500)
    evidence: list[Evidence] = Field(max_length=12)


def _review_schema() -> dict:
    schema = Review.model_json_schema()
    # Retained for compatibility with previously stored structured reviews.
    return schema


class GroqClaimReviewer:
    """Expose honest provider status pending validated source provenance.

    Groq's current GPT-OSS browser-search interface returns a synthesized text
    response with inline source markers, but this integration has not validated
    a stable URL-level record that the application can enforce. Sending a claim
    and accepting model-authored URLs would weaken the existing fail-closed
    evidence boundary, so hosted review remains unavailable.
    """

    def __init__(self, *, model=None, api_key=None, transport=None):
        self.model_override = model
        self.key_override = api_key
        self.transport = transport

    def _config(self):
        # Read at use time and never consult XAI_API_KEY or interpretation config.
        values = dotenv_values(ENV_PATH) if ENV_PATH.is_file() else {}
        model = (
            self.model_override
            or os.environ.get("ECHOTRACE_CLAIM_MODEL")
            or values.get("ECHOTRACE_CLAIM_MODEL")
            or DEFAULT_CLAIM_MODEL
        )
        key = (
            self.key_override
            if self.key_override is not None
            else os.environ.get("GROQ_API_KEY") or values.get("GROQ_API_KEY") or ""
        )
        return model, key.strip()

    def status(self) -> dict:
        model, key = self._config()
        return {
            "available": False,
            "configured": bool(key),
            "provider": "groq",
            "model": model,
            "reason": SEARCH_UNAVAILABLE_REASON,
            "search_supported": False,
            "connection_verified": False,
        }

    def review(self, claim: str) -> dict:
        raise ClaimReviewError(SEARCH_UNAVAILABLE_REASON)


# Compatibility for callers and historical tests that used the product name.
GrokClaimReviewer = GroqClaimReviewer
