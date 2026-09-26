"""Official AASIST-L checkpoint adapter. Index 0 is spoof; index 1 bonafide."""

from __future__ import annotations

import hashlib
import json
import threading
import urllib.request
from pathlib import Path

import numpy as np
import torch

from .vendor.AASIST import Model


UPSTREAM_REVISION = "a04c9863f63d44471dde8a6abcb3b082b07cd1d1"
WEIGHTS_SHA256 = "814331d088032bb4c3fa61cc014789eadeed464209dd094ab3a2dd6ffbdce27a"
WEIGHTS_URL = f"https://raw.githubusercontent.com/clovaai/aasist/{UPSTREAM_REVISION}/models/weights/AASIST-L.pth"
WEIGHTS_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "AASIST-L.pth"
CONFIG_PATH = Path(__file__).resolve().parent / "vendor" / "AASIST-L.conf"
WINDOW_SAMPLES = 64_600
SAMPLE_RATE = 16_000
_lock = threading.Lock()
_model: Model | None = None


def download_weights() -> Path:
    """Explicit cache operation; called at setup, never during analysis."""
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if WEIGHTS_PATH.is_file() and _sha256(WEIGHTS_PATH) == WEIGHTS_SHA256:
        return WEIGHTS_PATH
    target = WEIGHTS_PATH.with_suffix(".download")
    try:
        with urllib.request.urlopen(WEIGHTS_URL, timeout=30) as response, target.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if _sha256(target) != WEIGHTS_SHA256:
            raise RuntimeError("AASIST-L checkpoint hash mismatch")
        target.replace(WEIGHTS_PATH)
    finally:
        target.unlink(missing_ok=True)
    return WEIGHTS_PATH


def model_status() -> dict:
    exists = WEIGHTS_PATH.is_file()
    valid = exists and _sha256(WEIGHTS_PATH) == WEIGHTS_SHA256
    return {
        "name": "AASIST-L",
        "version": UPSTREAM_REVISION[:12],
        "upstream_revision": UPSTREAM_REVISION,
        "weights_sha256": WEIGHTS_SHA256,
        "config_sha256": _sha256(CONFIG_PATH),
        "available": bool(valid),
        "device": "cpu",
        "reason": None if valid else "Official AASIST-L weights are missing or failed checksum verification.",
    }


def _load_model() -> Model:
    global _model
    with _lock:
        if _model is None:
            if not WEIGHTS_PATH.is_file() or _sha256(WEIGHTS_PATH) != WEIGHTS_SHA256:
                raise RuntimeError("Official AASIST-L checkpoint is unavailable or invalid")
            config = json.loads(CONFIG_PATH.read_text())
            model = Model(config["model_config"])
            state = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
            model.load_state_dict(state, strict=True)
            model.eval()
            _model = model
        return _model


def score_window(samples: np.ndarray) -> dict:
    """Return an actual uncalibrated spoof softmax plus both raw logits."""
    if len(samples) != WINDOW_SAMPLES:
        raise ValueError(f"AASIST-L expects {WINDOW_SAMPLES} samples")
    model = _load_model()
    x = torch.from_numpy(np.asarray(samples, dtype=np.float32).copy()).unsqueeze(0)
    with torch.inference_mode():
        _, output = model(x)
        logits = output[0].cpu().tolist()
        spoof_score = float(torch.softmax(output, dim=-1)[0, 0].cpu())
    if not np.isfinite(spoof_score) or not all(np.isfinite(logits)):
        raise RuntimeError("AASIST-L returned a non-finite score")
    return {"score": spoof_score, "logits": [float(logits[0]), float(logits[1])]}


def _sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()
