import sys
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
