"""Comparability guards for saved detector results."""
from __future__ import annotations

import json


IDENTITY_FIELDS = (
    "name", "version", "upstream_revision", "source_revision",
    "weights_sha256", "config_sha256",
)


def model_identity(model) -> str | None:
    """Return a stable identity only when minimum model provenance is present."""
    if not isinstance(model, dict) or not model.get("name") or not model.get("weights_sha256"):
        return None
    identity = {key: model[key] for key in IDENTITY_FIELDS if model.get(key) is not None}
    return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def same_model(left, right) -> bool:
    left_identity = model_identity(left)
    return left_identity is not None and left_identity == model_identity(right)


def is_legacy_aasist(model) -> bool:
    return isinstance(model, dict) and model.get("name") == "AASIST-L"
