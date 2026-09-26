import sys
import hashlib
from types import SimpleNamespace

import numpy as np
import pytest

from echotrace.speaker import (
    EMBEDDING_WINDOW_SECONDS,
    MAX_EMBEDDING_WINDOWS,
    MODEL_ID,
    MODEL_REVISION,
    SpeakerComparisonError,
    WavLMSpeakerEmbedder,
)
import echotrace.speaker as speaker


def test_long_audio_is_bounded_to_evenly_spaced_model_windows():
    samples = np.arange(120 * 16_000, dtype=np.float32)
    windows = WavLMSpeakerEmbedder._windows(samples)
    assert len(windows) == MAX_EMBEDDING_WINDOWS
    assert all(len(window) == EMBEDDING_WINDOW_SECONDS * 16_000 for window in windows)
    assert windows[0][0] == 0
    assert windows[-1][-1] == samples[-1]


def test_download_uses_only_pinned_allowlist_and_rejects_bad_weights(tmp_path, monkeypatch):
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        path = kwargs["local_dir"] / kwargs["filename"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"wrong")
        return str(path)

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(hf_hub_download=download))
    embedder = WavLMSpeakerEmbedder(tmp_path)
    with pytest.raises(SpeakerComparisonError, match="SHA-256"):
        embedder._download()
    assert {call["filename"] for call in calls} == {
        "config.json", "preprocessor_config.json", "model.safetensors"
    }
    assert all(call["repo_id"] == MODEL_ID for call in calls)
    assert all(call["revision"] == MODEL_REVISION for call in calls)
    assert not (embedder.model_dir / "model.safetensors").exists()


def test_safe_local_model_loader_options_are_fixed(tmp_path, monkeypatch):
    embedder = WavLMSpeakerEmbedder(tmp_path)
    processor_calls, model_calls = [], []

    class Processor:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            processor_calls.append((args, kwargs))
            return object()

    class Model:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            model_calls.append((args, kwargs))
            return cls()

        def to(self, device):
            assert device == "cpu"
            return self

        def eval(self):
            return self

    monkeypatch.setattr(embedder, "_dependencies_available", lambda: True)
    monkeypatch.setattr(embedder, "_weights_valid", lambda: True)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        Wav2Vec2FeatureExtractor=Processor, WavLMForXVector=Model
    ))
    embedder._load()
    assert processor_calls[0][1] == {"local_files_only": True, "trust_remote_code": False}
    assert model_calls[0][1] == {
        "local_files_only": True,
        "trust_remote_code": False,
        "use_safetensors": True,
    }


def test_runtime_load_never_downloads_missing_speaker_model(tmp_path, monkeypatch):
    embedder = WavLMSpeakerEmbedder(tmp_path)
    monkeypatch.setattr(embedder, "_dependencies_available", lambda: True)
    monkeypatch.setattr(embedder, "_download", lambda: pytest.fail("runtime download attempted"))
    with pytest.raises(SpeakerComparisonError, match="explicit setup"):
        embedder._load()


def test_verified_weight_hash_is_cached_until_file_metadata_changes(tmp_path, monkeypatch):
    payload = b"weights"
    monkeypatch.setattr(speaker, "MODEL_WEIGHTS_BYTES", len(payload))
    monkeypatch.setattr(speaker, "MODEL_WEIGHTS_SHA256", hashlib.sha256(payload).hexdigest())
    embedder = WavLMSpeakerEmbedder(tmp_path)
    embedder.model_dir.mkdir(parents=True)
    for filename in speaker.MODEL_FILES:
        (embedder.model_dir / filename).write_bytes(payload if filename == "model.safetensors" else b"{}")
    calls = []
    original = speaker._sha256
    monkeypatch.setattr(speaker, "_sha256", lambda path: calls.append(path) or original(path))

    assert embedder.status()["ready"] is True
    assert embedder.status()["ready"] is True
    assert len(calls) == 1

    (embedder.model_dir / "model.safetensors").write_bytes(b"changed")
    assert embedder.status()["ready"] is False
    assert len(calls) == 2


def test_tampered_pinned_model_config_is_not_treated_as_ready(tmp_path, monkeypatch):
    weights = b"weights"
    embedder = WavLMSpeakerEmbedder(tmp_path)
    embedder.model_dir.mkdir(parents=True)
    (embedder.model_dir / "model.safetensors").write_bytes(weights)
    (embedder.model_dir / "config.json").write_bytes(b"safe-config")
    (embedder.model_dir / "preprocessor_config.json").write_bytes(b"safe-preprocessor")
    monkeypatch.setattr(speaker, "MODEL_WEIGHTS_BYTES", len(weights))
    monkeypatch.setattr(speaker, "MODEL_WEIGHTS_SHA256", hashlib.sha256(weights).hexdigest())

    assert embedder.status()["ready"] is True
    (embedder.model_dir / "config.json").write_bytes(b"evil-config")
    assert embedder.status()["ready"] is False
