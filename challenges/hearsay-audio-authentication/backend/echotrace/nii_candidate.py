"""Non-serving NII wav2vec anti-deepfake candidate adapter.

The released checkpoint uses Fairseq parameter names. This module maps only
the inference encoder into Transformers and loads the released two-class head
separately. It is intentionally not imported by the web scoring pipeline.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from transformers import Wav2Vec2Config, Wav2Vec2Model


HF_REPOSITORY = "nii-yamagishilab/wav2vec-small-anti-deepfake"
HF_REVISION = "9a13264b5dcc827a8d5a4f8e01fccefa392f886b"
SOURCE_REVISION = "0dea622bde8f064c8ee5a557f2598643123fc6b6"
WEIGHTS_SHA256 = "828ee456122f86d5d631cb7895a10e5c62c78a4fcb8a8b1c42cb5838a9abcfe0"
WEIGHTS_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "nii-model" / "model.safetensors"
SAMPLE_RATE = 16_000
MIN_SAMPLES = 400
MAX_DURATION_S = 30
MAX_SAMPLES = SAMPLE_RATE * MAX_DURATION_S
FAKE_CLASS_INDEX = 0

_load_lock = threading.Lock()
_models: tuple[Wav2Vec2Model, torch.nn.Linear] | None = None
_threads_configured = False


def _config() -> Wav2Vec2Config:
    """Return the inference-relevant architecture from the pinned HF config."""
    return Wav2Vec2Config(
        hidden_size=768,
        num_hidden_layers=12,
        num_attention_heads=12,
        intermediate_size=3072,
        hidden_act="gelu",
        hidden_dropout=0.1,
        attention_dropout=0.1,
        activation_dropout=0.0,
        feat_proj_dropout=0.1,
        layerdrop=0.0,
        do_stable_layer_norm=False,
        conv_dim=(512, 512, 512, 512, 512, 512, 512),
        conv_stride=(5, 2, 2, 2, 2, 2, 2),
        conv_kernel=(10, 3, 3, 3, 3, 2, 2),
        conv_bias=False,
        feat_extract_norm="group",
        feat_extract_activation="gelu",
        num_conv_pos_embeddings=128,
        num_conv_pos_embedding_groups=16,
        apply_spec_augment=False,
    )


def _mapped_key(key: str) -> str | None:
    prefix = "m_ssl.model."
    if not key.startswith(prefix):
        return None
    key = key[len(prefix):]
    if key.startswith(("final_proj.", "project_q.", "quantizer.")):
        return None
    key = key.replace("mask_emb", "masked_spec_embed")
    key = re.sub(
        r"^feature_extractor\.conv_layers\.(\d+)\.0\.",
        r"feature_extractor.conv_layers.\1.conv.", key,
    )
    key = re.sub(
        r"^feature_extractor\.conv_layers\.0\.2\.",
        "feature_extractor.conv_layers.0.layer_norm.", key,
    )
    key = re.sub(r"^layer_norm\.", "feature_projection.layer_norm.", key)
    key = re.sub(r"^post_extract_proj\.", "feature_projection.projection.", key)
    positional = {
        "encoder.pos_conv.0.bias": "encoder.pos_conv_embed.conv.bias",
        "encoder.pos_conv.0.weight_g": "encoder.pos_conv_embed.conv.parametrizations.weight.original0",
        "encoder.pos_conv.0.weight_v": "encoder.pos_conv_embed.conv.parametrizations.weight.original1",
    }
    key = positional.get(key, key)
    return (key.replace(".self_attn.", ".attention.")
            .replace(".self_attn_layer_norm.", ".layer_norm.")
            .replace(".fc1.", ".feed_forward.intermediate_dense.")
            .replace(".fc2.", ".feed_forward.output_dense."))


def _map_encoder_state(source: dict[str, torch.Tensor], target: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    mapped = {_mapped_key(key): value for key, value in source.items() if _mapped_key(key) is not None}
    missing = sorted(set(target) - set(mapped))
    extra = sorted(set(mapped) - set(target))
    mismatched = sorted(
        key for key in set(mapped) & set(target) if mapped[key].shape != target[key].shape
    )
    if missing or extra or mismatched:
        raise RuntimeError(
            f"NII checkpoint mapping mismatch: missing={missing}, extra={extra}, shape={mismatched}"
        )
    return mapped


def _configure_cpu() -> None:
    global _threads_configured
    if not _threads_configured:
        torch.set_num_threads(4)
        _threads_configured = True


@lru_cache(maxsize=8)
def _hash_local_file(path: str, modified_ns: int, size: int) -> str:
    del modified_ns, size
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _valid_weights(path: Path = WEIGHTS_PATH) -> bool:
    if not path.is_file():
        return False
    stat = path.stat()
    return _hash_local_file(str(path), stat.st_mtime_ns, stat.st_size) == WEIGHTS_SHA256


def setup_candidate_weights() -> Path:
    """Explicitly fetch the pinned checkpoint; scoring never calls this."""
    if _valid_weights(WEIGHTS_PATH):
        return WEIGHTS_PATH
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    downloaded = Path(hf_hub_download(
        repo_id=HF_REPOSITORY,
        filename="model.safetensors",
        revision=HF_REVISION,
    ))
    if not _valid_weights(downloaded):
        raise RuntimeError("Downloaded NII checkpoint failed its pinned SHA-256")
    temporary = WEIGHTS_PATH.with_suffix(".download")
    try:
        shutil.copyfile(downloaded, temporary)
        os.replace(temporary, WEIGHTS_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    _hash_local_file.cache_clear()
    if not _valid_weights(WEIGHTS_PATH):
        raise RuntimeError("Installed NII checkpoint failed its pinned SHA-256")
    return WEIGHTS_PATH


def candidate_status() -> dict:
    available = _valid_weights(WEIGHTS_PATH)
    return {
        "name": "NII wav2vec-small-anti-deepfake",
        "version": HF_REVISION[:12],
        "upstream_revision": HF_REVISION,
        "source_revision": SOURCE_REVISION,
        "weights_sha256": WEIGHTS_SHA256,
        "available": available,
        "device": "cpu",
        "max_duration_s": MAX_DURATION_S,
        "reason": None if available else "Pinned NII candidate weights are missing or failed checksum verification.",
        "evaluation_boundary": "ASVspoof5 was used to train this checkpoint and is not independent evaluation data.",
    }


def _load_models() -> tuple[Wav2Vec2Model, torch.nn.Linear]:
    global _models
    with _load_lock:
        if _models is None:
            if not _valid_weights(WEIGHTS_PATH):
                raise RuntimeError("Pinned NII candidate weights are unavailable or invalid")
            _configure_cpu()
            source = load_file(WEIGHTS_PATH, device="cpu")
            encoder = Wav2Vec2Model(_config())
            encoder.load_state_dict(_map_encoder_state(source, encoder.state_dict()), strict=True)
            head = torch.nn.Linear(768, 2)
            head.load_state_dict({"weight": source["proj_fc.weight"], "bias": source["proj_fc.bias"]}, strict=True)
            encoder.eval()
            head.eval()
            _models = encoder, head
        return _models


def _score_with_models(samples: np.ndarray, encoder: torch.nn.Module, head: torch.nn.Linear) -> dict:
    waveform = torch.from_numpy(np.asarray(samples, dtype=np.float32).copy())
    waveform = F.layer_norm(waveform, waveform.shape).unsqueeze(0)
    with torch.inference_mode():
        encoded = encoder(waveform)
        frames = encoded.last_hidden_state if hasattr(encoded, "last_hidden_state") else encoded
        logits_tensor = head(frames.mean(dim=1))[0]
        score = float(torch.softmax(logits_tensor, dim=0)[FAKE_CLASS_INDEX])
    logits = [float(value) for value in logits_tensor]
    if not np.isfinite(score) or not all(np.isfinite(logits)):
        raise RuntimeError("NII candidate returned a non-finite result")
    return {"score": score, "raw_logits": logits, "score_kind": "uncalibrated"}


def score_samples(samples: np.ndarray) -> dict:
    """Score one complete mono 16 kHz waveform, without truncation or padding."""
    samples = np.asarray(samples)
    if samples.ndim != 1:
        raise ValueError("NII candidate input must be one-dimensional")
    if not samples.size:
        raise ValueError("NII candidate input must be nonempty")
    if not np.all(np.isfinite(samples)):
        raise ValueError("NII candidate input must contain only finite samples")
    if samples.size < MIN_SAMPLES:
        raise ValueError("NII candidate input must contain at least 400 samples")
    if samples.size > MAX_SAMPLES:
        raise ValueError("NII candidate input must not exceed 30 seconds")
    encoder, head = _load_models()
    result = _score_with_models(samples, encoder, head)
    result["model"] = candidate_status()
    result["aggregation"] = "whole_file_layer_norm_mean_pool"
    return result
