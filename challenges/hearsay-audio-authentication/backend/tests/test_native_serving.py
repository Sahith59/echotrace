from __future__ import annotations

import hashlib
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from echotrace.native_serving import (
    MODEL_ID,
    MODEL_REVISION,
    WINDOW_SAMPLES,
    NativeServingAdapter,
    NativeServingError,
)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def artifact(tmp_path):
    weights = b"safe-tensors-test-weights"
    config = b'{"model_type":"wav2vec2"}'
    processor = b'{"sampling_rate":16000}'
    validation = b'{"decision":"promoted","independent":true}\n'
    for name, payload in (
        ("model.safetensors", weights),
        ("config.json", config),
        ("preprocessor_config.json", processor),
        ("validation_summary.json", validation),
    ):
        (tmp_path / name).write_bytes(payload)
    spec = {
        "schema_version": 1,
        "adapter": "echotrace-native-wav2vec2-v1",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "promotion_decision": "promoted",
        "weights_sha256": sha(weights),
        "weights_bytes": len(weights),
        "config_sha256": sha(config),
        "processor_sha256": sha(processor),
        "validation_summary_sha256": sha(validation),
        "fake_label_index": 1,
        "sample_rate": 16_000,
        "window_samples": WINDOW_SAMPLES,
        "aggregation": "mean_window_spoof_softmax",
    }
    spec_payload = (json.dumps(spec, sort_keys=True) + "\n").encode()
    (tmp_path / "serving-spec.json").write_bytes(spec_payload)
    kwargs = {
        "expected_spec_sha256": sha(spec_payload),
        "expected_weights_sha256": sha(weights),
        "expected_validation_summary_sha256": sha(validation),
        "allowed_config_sha256": {sha(config)},
        "allowed_processor_sha256": {sha(processor)},
    }
    return spec, kwargs


def test_artifact_requires_explicit_promotion_hashes_and_allowlisted_config(tmp_path):
    spec, kwargs = artifact(tmp_path)
    adapter = NativeServingAdapter(tmp_path, **kwargs)

    verified = adapter.verify_artifacts()
    assert verified.weights_sha256 == spec["weights_sha256"]
    assert adapter.model_status()["available"] is True

    with pytest.raises(NativeServingError, match="serving spec SHA-256"):
        NativeServingAdapter(tmp_path, **{**kwargs, "expected_spec_sha256": "0" * 64}).verify_artifacts()
    with pytest.raises(NativeServingError, match="explicit weights SHA-256"):
        NativeServingAdapter(tmp_path, **{**kwargs, "expected_weights_sha256": "0" * 64}).verify_artifacts()
    with pytest.raises(NativeServingError, match="configuration is not allowlisted"):
        NativeServingAdapter(tmp_path, **{**kwargs, "allowed_config_sha256": {"0" * 64}}).verify_artifacts()


def test_cached_verification_uses_cheap_fingerprint_to_detect_replacement(tmp_path):
    _, kwargs = artifact(tmp_path)
    adapter = NativeServingAdapter(tmp_path, **kwargs)
    assert adapter.model_status()["available"] is True

    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"x" * weights.stat().st_size)

    status = adapter.model_status()
    assert status["available"] is False
    assert "changed after verification" in status["reason"]


def test_artifact_rejects_unpromoted_wrong_polarity_changed_or_symlinked_files(tmp_path):
    _, kwargs = artifact(tmp_path)
    data = json.loads((tmp_path / "serving-spec.json").read_text())
    data["promotion_decision"] = "failed"
    changed_spec = (json.dumps(data, sort_keys=True) + "\n").encode()
    (tmp_path / "serving-spec.json").write_bytes(changed_spec)
    with pytest.raises(NativeServingError, match="promoted"):
        NativeServingAdapter(
            tmp_path, **{**kwargs, "expected_spec_sha256": sha(changed_spec)}
        ).verify_artifacts()

    _, kwargs = artifact(tmp_path)
    data = json.loads((tmp_path / "serving-spec.json").read_text())
    data["fake_label_index"] = 0
    changed_spec = (json.dumps(data, sort_keys=True) + "\n").encode()
    (tmp_path / "serving-spec.json").write_bytes(changed_spec)
    with pytest.raises(NativeServingError, match="polarity"):
        NativeServingAdapter(
            tmp_path, **{**kwargs, "expected_spec_sha256": sha(changed_spec)}
        ).verify_artifacts()

    _, kwargs = artifact(tmp_path)
    (tmp_path / "model.safetensors").write_bytes(b"changed")
    with pytest.raises(NativeServingError, match="weights"):
        NativeServingAdapter(tmp_path, **kwargs).verify_artifacts()

    link_root = tmp_path / "links"
    link_root.mkdir()
    _, link_kwargs = artifact(link_root)
    target = link_root / "real-config.json"
    (link_root / "config.json").replace(target)
    (link_root / "config.json").symlink_to(target)
    with pytest.raises(NativeServingError, match="symbolic link"):
        NativeServingAdapter(link_root, **link_kwargs).verify_artifacts()


def test_lazy_cpu_safe_loading_and_native_evaluation_preprocessing(tmp_path, monkeypatch):
    _, kwargs = artifact(tmp_path)
    calls = []

    class Extractor:
        sampling_rate = 16_000

        @classmethod
        def from_pretrained(cls, path, **options):
            calls.append(("extractor", path, options))
            return cls()

        def __call__(self, windows, **options):
            calls.append(("preprocess", windows, options))
            return {"input_values": torch.zeros((len(windows), WINDOW_SAMPLES))}

    class Model:
        config = SimpleNamespace(label2id={"fake": 1, "real": 0})

        @classmethod
        def from_pretrained(cls, path, **options):
            calls.append(("model", path, options))
            return cls()

        def to(self, device):
            calls.append(("device", device))
            return self

        def eval(self):
            calls.append(("eval",))
            return self

        def __call__(self, **batch):
            calls.append(("inference", batch))
            return SimpleNamespace(logits=torch.tensor([[-1.0, 2.0]]))

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoFeatureExtractor=Extractor,
        AutoModelForAudioClassification=Model,
    ))
    adapter = NativeServingAdapter(tmp_path, **kwargs)
    assert calls == []
    assert adapter.model_status()["available"] is True
    assert calls == []

    output = adapter.score_window(np.ones(WINDOW_SAMPLES, dtype=np.float32))

    assert output["score"] == pytest.approx(torch.softmax(torch.tensor([-1.0, 2.0]), 0)[1].item())
    assert output["logits"] == [-1.0, 2.0]
    assert calls[0] == ("extractor", tmp_path, {
        "local_files_only": True, "trust_remote_code": False,
    })
    assert calls[1] == ("model", tmp_path, {
        "local_files_only": True, "trust_remote_code": False, "use_safetensors": True,
    })
    assert ("device", "cpu") in calls
    preprocess = next(call for call in calls if call[0] == "preprocess")
    assert len(preprocess[1]) == 1
    assert np.array_equal(preprocess[1][0], np.ones(WINDOW_SAMPLES, dtype=np.float32))
    assert preprocess[2] == {"sampling_rate": 16_000, "return_tensors": "pt", "padding": True}


def test_scoring_fails_closed_for_wrong_window_polarity_or_nonfinite_logits(tmp_path, monkeypatch):
    _, kwargs = artifact(tmp_path)

    class Extractor:
        sampling_rate = 16_000

        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def __call__(self, windows, **kwargs):
            return {"input_values": torch.zeros((1, WINDOW_SAMPLES))}

    class Model:
        config = SimpleNamespace(label2id={"fake": 0, "real": 1})

        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def to(self, device):
            return self

        def eval(self):
            return self

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoFeatureExtractor=Extractor,
        AutoModelForAudioClassification=Model,
    ))
    adapter = NativeServingAdapter(tmp_path, **kwargs)
    with pytest.raises(ValueError, match="64600"):
        adapter.score_window(np.ones(10, dtype=np.float32))
    with pytest.raises(NativeServingError, match="polarity"):
        adapter.score_window(np.ones(WINDOW_SAMPLES, dtype=np.float32))

    Model.config = SimpleNamespace(label2id={"fake": 1, "real": 0})
    Model.__call__ = lambda self, **batch: SimpleNamespace(
        logits=torch.tensor([[float("nan"), 0.0]])
    )
    adapter = NativeServingAdapter(tmp_path, **kwargs)
    with pytest.raises(NativeServingError, match="invalid two-class logits"):
        adapter.score_window(np.ones(WINDOW_SAMPLES, dtype=np.float32))
