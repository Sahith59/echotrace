"""Local, consent-gated speaker-embedding comparison.

The cosine value produced here is descriptive and uncalibrated. It is never an
identity decision and is intentionally stored outside the synthesis result.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from .audio import MAX_SECONDS, SAMPLE_RATE, decode_audio


MODEL_ID = "microsoft/wavlm-base-plus-sv"
MODEL_REVISION = "1bfd64eca136543feb28c5ffaf05381c6af33121"
MODEL_WEIGHTS_SHA256 = "94c3defe08248d81c7b2bd0a058ea9985269cefed13076434669c47fade41182"
MODEL_WEIGHTS_BYTES = 404_479_908
MODEL_CONFIG_SHA256 = "c6ac8c0ce55b18d4612677931036fe5ce78093e87361c552a173f00a0bb07514"
MODEL_CONFIG_BYTES = 58_639
MODEL_PREPROCESSOR_SHA256 = "99272fe8ccfab114b68b478681ea47ee3a1ce62bb788cb92dd6e4f69fb1f1da2"
MODEL_PREPROCESSOR_BYTES = 215
MODEL_FILES = ("config.json", "preprocessor_config.json", "model.safetensors")
DEFAULT_MODEL_CACHE = Path(__file__).resolve().parents[1] / "artifacts" / "speaker-model"
MAX_REFERENCE_BYTES = 20 * 1024 * 1024
MIN_AUDIO_SECONDS = 2.0
EMBEDDING_WINDOW_SECONDS = 10.0
MAX_EMBEDDING_WINDOWS = 4
EMBEDDING_AUDIO_CAP_SECONDS = EMBEDDING_WINDOW_SECONDS * MAX_EMBEDDING_WINDOWS

LIMITATIONS = [
    "Cosine similarity is uncalibrated and is not a probability or an identity verdict.",
    "Voice cloning, replay, editing, background sound, illness, microphones, and codecs can change similarity.",
    "A high similarity does not prove identity; a low similarity does not prove different speakers.",
    "The comparison does not establish authenticity, consent, origin, or whether speech is synthetic.",
]


class SpeakerComparisonError(ValueError):
    pass


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def audio_quality(samples: np.ndarray) -> dict:
    """Apply minimal signal gates needed for meaningful model input."""
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim != 1 or not samples.size or not np.all(np.isfinite(samples)):
        raise SpeakerComparisonError("Decoded audio samples are invalid.")
    duration = samples.size / SAMPLE_RATE
    if duration < MIN_AUDIO_SECONDS:
        raise SpeakerComparisonError("Each recording must contain at least 2 seconds of audio.")
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(samples)))
    rms_dbfs = 20 * math.log10(max(rms, 1e-12))
    if rms_dbfs < -50 or peak < 0.005:
        raise SpeakerComparisonError("Audio is too quiet for speaker comparison.")
    return {
        "duration_s": round(duration, 5),
        "rms_dbfs": round(rms_dbfs, 2),
        "peak": round(peak, 5),
        "embedding_audio_used_s": round(min(duration, EMBEDDING_AUDIO_CAP_SECONDS), 5),
    }


class WavLMSpeakerEmbedder:
    """Pinned SafeTensors-only loader for Microsoft's WavLM speaker model."""

    def __init__(self, cache_root: Path, *, allow_download: bool = False):
        self.cache_root = Path(cache_root)
        self.model_dir = self.cache_root / MODEL_REVISION
        self.allow_download = allow_download
        self._model = None
        self._processor = None
        self._load_lock = threading.Lock()
        self._verified_model_signature = None

    @staticmethod
    def _dependencies_available() -> bool:
        return all(importlib.util.find_spec(name) is not None
                   for name in ("transformers", "huggingface_hub", "safetensors"))

    def _weights_valid(self) -> bool:
        expected = {
            "config.json": (MODEL_CONFIG_BYTES, MODEL_CONFIG_SHA256),
            "preprocessor_config.json": (MODEL_PREPROCESSOR_BYTES, MODEL_PREPROCESSOR_SHA256),
            "model.safetensors": (MODEL_WEIGHTS_BYTES, MODEL_WEIGHTS_SHA256),
        }
        stats = {}
        for filename, (size, _) in expected.items():
            path = self.model_dir / filename
            if not path.is_file():
                self._verified_model_signature = None
                return False
            stat = path.stat()
            if stat.st_size != size:
                self._verified_model_signature = None
                return False
            stats[filename] = stat
        signature = tuple(
            (name, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            for name, stat in sorted(stats.items())
        )
        if signature == self._verified_model_signature:
            return True
        valid = all(
            _sha256(self.model_dir / filename) == digest
            for filename, (_, digest) in expected.items()
        )
        self._verified_model_signature = signature if valid else None
        return valid

    def status(self) -> dict:
        model = {"id": MODEL_ID, "revision": MODEL_REVISION,
                 "weights_sha256": MODEL_WEIGHTS_SHA256}
        if not self._dependencies_available():
            return {"available": False, "ready": False, "model": model,
                    "reason": "Speaker model dependencies are unavailable."}
        ready = self._weights_valid()
        return {"available": True, "ready": ready, "model": model,
                "reason": None if ready else
                "Pinned speaker weights are not cached. Run the explicit speaker model setup command before comparison."}

    def _download(self) -> None:
        from huggingface_hub import hf_hub_download

        self.model_dir.mkdir(parents=True, exist_ok=True)
        try:
            for filename in MODEL_FILES:
                hf_hub_download(
                    repo_id=MODEL_ID,
                    filename=filename,
                    revision=MODEL_REVISION,
                    local_dir=self.model_dir,
                )
        except Exception as exc:
            raise SpeakerComparisonError(
                "Pinned speaker weights could not be downloaded from the official model repository."
            ) from exc
        if not self._weights_valid():
            (self.model_dir / "model.safetensors").unlink(missing_ok=True)
            self._verified_model_signature = None
            raise SpeakerComparisonError("Downloaded speaker weights failed size or SHA-256 verification.")

    def prepare(self) -> None:
        if not self.allow_download:
            raise SpeakerComparisonError("Speaker model download is disabled outside explicit setup.")
        self._download()

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if not self._dependencies_available():
                raise SpeakerComparisonError("Speaker model dependencies are unavailable.")
            if not self._weights_valid():
                raise SpeakerComparisonError(
                    "Pinned speaker weights are unavailable; run the explicit setup command."
                )
            try:
                from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector

                self._processor = Wav2Vec2FeatureExtractor.from_pretrained(
                    self.model_dir, local_files_only=True, trust_remote_code=False
                )
                self._model = WavLMForXVector.from_pretrained(
                    self.model_dir,
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                ).to("cpu").eval()
            except Exception as exc:
                self._model = self._processor = None
                raise SpeakerComparisonError("Pinned speaker model could not be loaded safely.") from exc

    @staticmethod
    def _windows(samples: np.ndarray) -> list[np.ndarray]:
        width = round(EMBEDDING_WINDOW_SECONDS * SAMPLE_RATE)
        if samples.size <= width:
            return [samples]
        count = min(MAX_EMBEDDING_WINDOWS, math.ceil(samples.size / width))
        starts = np.linspace(0, samples.size - width, count, dtype=np.int64)
        return [samples[start:start + width] for start in starts]

    def embed(self, samples: np.ndarray) -> np.ndarray:
        self._load()
        import torch

        vectors = []
        with torch.inference_mode():
            for window in self._windows(np.asarray(samples, dtype=np.float32)):
                inputs = self._processor(
                    window, sampling_rate=SAMPLE_RATE, return_tensors="pt"
                )
                vector = self._model(**inputs).embeddings[0].detach().cpu().numpy()
                norm = float(np.linalg.norm(vector))
                if not math.isfinite(norm) or norm <= 0:
                    raise SpeakerComparisonError("Speaker model returned an invalid embedding.")
                vectors.append(vector / norm)
        combined = np.mean(vectors, axis=0)
        norm = float(np.linalg.norm(combined))
        if not math.isfinite(norm) or norm <= 0:
            raise SpeakerComparisonError("Speaker model returned an invalid embedding.")
        return combined / norm


class SpeakerComparisonService:
    def __init__(self, store, *, embedder=None, decoder: Callable = decode_audio):
        self.store = store
        self.decoder = decoder
        self.embedder = embedder or WavLMSpeakerEmbedder(DEFAULT_MODEL_CACHE)
        self.operation_lock = threading.Lock()
        with store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS speaker_comparisons (
                job_id TEXT PRIMARY KEY, report TEXT NOT NULL, created_at TEXT NOT NULL)""")

    def status(self) -> dict:
        result = dict(self.embedder.status())
        result["limits"] = {
            "max_reference_bytes": MAX_REFERENCE_BYTES,
            "max_audio_duration_s": MAX_SECONDS,
            "min_audio_duration_s": MIN_AUDIO_SECONDS,
            "embedding_audio_cap_s": EMBEDDING_AUDIO_CAP_SECONDS,
        }
        return result

    def get(self, job_id: str) -> dict | None:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT report FROM speaker_comparisons WHERE job_id=?", (job_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, job_id: str) -> bool:
        with self.store.connect() as db:
            cursor = db.execute("DELETE FROM speaker_comparisons WHERE job_id=?", (job_id,))
        return cursor.rowcount > 0

    def compare(self, job: dict, reference_path: Path, reference_label: str) -> dict:
        if not self.operation_lock.acquire(blocking=False):
            raise SpeakerComparisonError("Another speaker comparison is running. Try again shortly.")
        try:
            state = self.embedder.status()
            if not state.get("available") or not state.get("ready"):
                raise SpeakerComparisonError(state.get("reason") or "Speaker model is unavailable.")
            try:
                source_samples, source_meta = self.decoder(Path(job["path"]))
                reference_samples, reference_meta = self.decoder(reference_path)
            except SpeakerComparisonError:
                raise
            except ValueError as exc:
                raise SpeakerComparisonError(str(exc)) from None
            source_quality = audio_quality(source_samples)
            reference_quality = audio_quality(reference_samples)
            source_vector = np.asarray(self.embedder.embed(source_samples), dtype=np.float64)
            reference_vector = np.asarray(self.embedder.embed(reference_samples), dtype=np.float64)
            denominator = float(np.linalg.norm(source_vector) * np.linalg.norm(reference_vector))
            if denominator <= 0 or not math.isfinite(denominator):
                raise SpeakerComparisonError("Speaker model returned an invalid embedding.")
            cosine = float(np.dot(source_vector, reference_vector) / denominator)
            if not math.isfinite(cosine):
                raise SpeakerComparisonError("Speaker model returned an invalid similarity.")
            created_at = datetime.now(timezone.utc).isoformat()
            model = state.get("model") or {
                "id": MODEL_ID, "revision": MODEL_REVISION,
                "weights_sha256": MODEL_WEIGHTS_SHA256,
            }
            report = {
                "job_id": job["id"],
                "status": "completed",
                "similarity": {
                    "cosine": round(max(-1.0, min(1.0, cosine)), 6),
                    "calibration": "uncalibrated",
                    "identity_verdict": None,
                },
                "reference": {
                    "label": reference_label,
                    "sha256": reference_meta["sha256"],
                    "retained": False,
                },
                "source": {"sha256": source_meta["sha256"]},
                "model": model,
                "quality": {"source": source_quality, "reference": reference_quality},
                "created_at": created_at,
                "limitations": list(LIMITATIONS),
            }
            with self.store.connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO speaker_comparisons(job_id,report,created_at) VALUES (?,?,?)",
                    (job["id"], json.dumps(report, allow_nan=False), created_at),
                )
            return report
        finally:
            self.operation_lock.release()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the pinned ECHOTRACE speaker model.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_MODEL_CACHE)
    args = parser.parse_args(argv)
    embedder = WavLMSpeakerEmbedder(args.cache_dir, allow_download=True)
    embedder.prepare()
    print(f"Prepared pinned speaker model revision {MODEL_REVISION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
