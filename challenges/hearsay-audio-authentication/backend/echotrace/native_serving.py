"""Opt-in CPU serving adapter for a separately promoted native wav2vec2 artifact.

This module is deliberately not registered by the live pipeline. Integration must
pin the serving spec, weights, validation summary, and allowed configuration hashes.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Collection

import numpy as np
import torch


MODEL_ID = "garystafford/wav2vec2-deepfake-voice-detector"
MODEL_REVISION = "c66306024a7ede0be291e9c4558b37634782dc4e"
WINDOW_SAMPLES = 64_600
SAMPLE_RATE = 16_000
SPEC_NAME = "serving-spec.json"
ADAPTER_ID = "echotrace-native-wav2vec2-v1"
MAX_SPEC_BYTES = 64 * 1024
MAX_WEIGHTS_BYTES = 2_000_000_000
MAX_CONFIG_BYTES = 1_000_000
MAX_VALIDATION_BYTES = 5_000_000
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SPEC_KEYS = {
    "schema_version", "adapter", "model_id", "model_revision",
    "promotion_decision", "weights_sha256", "weights_bytes",
    "config_sha256", "processor_sha256", "validation_summary_sha256",
    "fake_label_index", "sample_rate", "window_samples", "aggregation",
}


class NativeServingError(RuntimeError):
    """A candidate artifact is not safe or eligible for local serving."""


@dataclass(frozen=True)
class NativeArtifactSpec:
    weights_sha256: str
    weights_bytes: int
    config_sha256: str
    processor_sha256: str
    validation_summary_sha256: str


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise NativeServingError(f"{label} must be an explicit lowercase SHA-256")
    return value


def _sha256(path: Path, *, byte_limit: int) -> str:
    try:
        size = path.stat().st_size
        if size <= 0 or size > byte_limit:
            raise NativeServingError(f"{path.name} exceeds its bounded artifact size")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except NativeServingError:
        raise
    except OSError as exc:
        raise NativeServingError(f"cannot verify {path.name}: {exc}") from exc


class NativeServingAdapter:
    """Lazy single-window scorer for an explicitly pinned promoted artifact."""

    def __init__(
        self,
        artifact_dir: Path | str,
        *,
        expected_spec_sha256: str,
        expected_weights_sha256: str,
        expected_validation_summary_sha256: str,
        allowed_config_sha256: Collection[str],
        allowed_processor_sha256: Collection[str],
    ) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.expected_spec_sha256 = _require_sha(
            expected_spec_sha256, "expected serving spec SHA-256"
        )
        self.expected_weights_sha256 = _require_sha(
            expected_weights_sha256, "expected explicit weights SHA-256"
        )
        self.expected_validation_summary_sha256 = _require_sha(
            expected_validation_summary_sha256, "expected validation summary SHA-256"
        )
        self.allowed_config_sha256 = frozenset(
            _require_sha(value, "allowed configuration SHA-256")
            for value in allowed_config_sha256
        )
        self.allowed_processor_sha256 = frozenset(
            _require_sha(value, "allowed processor SHA-256")
            for value in allowed_processor_sha256
        )
        if not self.allowed_config_sha256 or not self.allowed_processor_sha256:
            raise NativeServingError("configuration and processor allowlists must be nonempty")
        self._lock = threading.Lock()
        self._spec: NativeArtifactSpec | None = None
        self._fingerprints: dict[str, tuple[int, int, int, int]] | None = None
        self._extractor = None
        self._model = None

    def _path(self, name: str) -> Path:
        path = self.artifact_dir / name
        if path.is_symlink():
            raise NativeServingError(f"artifact {name} must not be a symbolic link")
        if not path.is_file():
            raise NativeServingError(f"artifact {name} is missing")
        return path

    def _fingerprint(self, names: Collection[str]) -> dict[str, tuple[int, int, int, int]]:
        result = {}
        for name in names:
            stat = self._path(name).stat()
            result[name] = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        return result

    def verify_artifacts(self) -> NativeArtifactSpec:
        """Verify all serving trust anchors once; no model is loaded or downloaded."""
        with self._lock:
            if self._spec is not None:
                assert self._fingerprints is not None
                if self._fingerprint(self._fingerprints) != self._fingerprints:
                    raise NativeServingError("native serving artifacts changed after verification")
                return self._spec
            if self.artifact_dir.is_symlink() or not self.artifact_dir.is_dir():
                raise NativeServingError("native serving artifact directory is missing or symbolic")
            spec_path = self._path(SPEC_NAME)
            if _sha256(spec_path, byte_limit=MAX_SPEC_BYTES) != self.expected_spec_sha256:
                raise NativeServingError("serving spec SHA-256 does not match the explicit pin")
            try:
                data = json.loads(spec_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise NativeServingError(f"serving spec is unreadable: {exc}") from exc
            if not isinstance(data, dict) or set(data) != _SPEC_KEYS:
                raise NativeServingError("serving spec fields do not match schema version 1")
            fixed = {
                "schema_version": 1,
                "adapter": ADAPTER_ID,
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "promotion_decision": "promoted",
                "fake_label_index": 1,
                "sample_rate": SAMPLE_RATE,
                "window_samples": WINDOW_SAMPLES,
                "aggregation": "mean_window_spoof_softmax",
            }
            if data.get("promotion_decision") != "promoted":
                raise NativeServingError("artifact is not explicitly marked promoted")
            if data.get("fake_label_index") != 1:
                raise NativeServingError("native detector class polarity does not mark class 1 fake")
            if any(data.get(key) != value for key, value in fixed.items()):
                raise NativeServingError("serving spec is incompatible with the native adapter contract")

            weights_sha = _require_sha(data.get("weights_sha256"), "spec weights SHA-256")
            config_sha = _require_sha(data.get("config_sha256"), "spec configuration SHA-256")
            processor_sha = _require_sha(data.get("processor_sha256"), "spec processor SHA-256")
            validation_sha = _require_sha(
                data.get("validation_summary_sha256"), "spec validation summary SHA-256"
            )
            weights_bytes = data.get("weights_bytes")
            if type(weights_bytes) is not int or not 0 < weights_bytes <= MAX_WEIGHTS_BYTES:
                raise NativeServingError("weights byte count is invalid or exceeds the serving bound")
            if weights_sha != self.expected_weights_sha256:
                raise NativeServingError("spec does not match the explicit weights SHA-256")
            if validation_sha != self.expected_validation_summary_sha256:
                raise NativeServingError("spec does not match the explicit validation summary SHA-256")
            if config_sha not in self.allowed_config_sha256:
                raise NativeServingError("native detector configuration is not allowlisted")
            if processor_sha not in self.allowed_processor_sha256:
                raise NativeServingError("native detector processor is not allowlisted")

            paths = {
                "model.safetensors": (weights_sha, MAX_WEIGHTS_BYTES),
                "config.json": (config_sha, MAX_CONFIG_BYTES),
                "preprocessor_config.json": (processor_sha, MAX_CONFIG_BYTES),
                "validation_summary.json": (validation_sha, MAX_VALIDATION_BYTES),
            }
            for name, (expected, limit) in paths.items():
                path = self._path(name)
                if name == "model.safetensors" and path.stat().st_size != weights_bytes:
                    raise NativeServingError("native detector weights byte count changed")
                if _sha256(path, byte_limit=limit) != expected:
                    label = "weights" if name == "model.safetensors" else name
                    raise NativeServingError(f"native detector {label} failed SHA-256 verification")
            spec = NativeArtifactSpec(
                weights_sha256=weights_sha,
                weights_bytes=weights_bytes,
                config_sha256=config_sha,
                processor_sha256=processor_sha,
                validation_summary_sha256=validation_sha,
            )
            names = [SPEC_NAME, *paths]
            self._fingerprints = self._fingerprint(names)
            self._spec = spec
            return spec

    def _load(self):
        self.verify_artifacts()
        with self._lock:
            if self._model is not None:
                return self._extractor, self._model
            assert self._fingerprints is not None
            if self._fingerprint(self._fingerprints) != self._fingerprints:
                raise NativeServingError("native serving artifacts changed after verification")
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

            extractor = AutoFeatureExtractor.from_pretrained(
                self.artifact_dir, local_files_only=True, trust_remote_code=False
            )
            model = AutoModelForAudioClassification.from_pretrained(
                self.artifact_dir,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
            ).to("cpu").eval()
            if getattr(extractor, "sampling_rate", None) != SAMPLE_RATE:
                raise NativeServingError("native detector preprocessing sample rate changed")
            if getattr(model.config, "label2id", None) != {"fake": 1, "real": 0}:
                raise NativeServingError("native detector class polarity changed")
            self._extractor, self._model = extractor, model
            return extractor, model

    def model_status(self) -> dict:
        try:
            spec = self.verify_artifacts()
        except (NativeServingError, OSError, ValueError) as exc:
            return {
                "name": "Native wav2vec2 candidate",
                "version": "unavailable",
                "upstream_revision": MODEL_REVISION,
                "weights_sha256": self.expected_weights_sha256,
                "config_sha256": None,
                "available": False,
                "device": "cpu",
                "reason": str(exc),
            }
        return {
            "name": "Native wav2vec2 candidate",
            "version": spec.weights_sha256[:12],
            "upstream_revision": MODEL_REVISION,
            "weights_sha256": spec.weights_sha256,
            "config_sha256": spec.config_sha256,
            "available": True,
            "device": "cpu",
            "reason": None,
        }

    def score_window(self, samples: np.ndarray) -> dict:
        window = np.asarray(samples)
        if window.ndim != 1 or len(window) != WINDOW_SAMPLES:
            raise ValueError(f"Native wav2vec2 expects exactly {WINDOW_SAMPLES} samples")
        window = np.asarray(window, dtype=np.float32)
        extractor, model = self._load()
        batch = extractor(
            [window], sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True
        )
        batch = {key: value.to("cpu") for key, value in batch.items()}
        with torch.inference_mode():
            logits = model(**batch).logits
        if logits.ndim != 2 or logits.shape != (1, 2) or not torch.isfinite(logits).all():
            raise NativeServingError("native detector returned invalid two-class logits")
        raw = logits[0].float().cpu()
        score = float(torch.softmax(raw, dim=-1)[1])
        values = [float(value) for value in raw.tolist()]
        if not math.isfinite(score) or not 0 <= score <= 1 or not all(map(math.isfinite, values)):
            raise NativeServingError("native detector returned an invalid score")
        return {"score": score, "logits": values}
