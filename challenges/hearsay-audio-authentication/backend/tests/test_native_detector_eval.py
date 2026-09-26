from types import SimpleNamespace

import numpy as np
import pytest
import torch

from echotrace import native_detector_eval as native


def test_verify_requires_exact_safe_artifacts(tmp_path, monkeypatch):
    for name in native.FILES:
        (tmp_path / name).write_bytes(name.encode())
    monkeypatch.setattr(native, "_sha", lambda path: native.FILES[path.name])
    monkeypatch.setattr(native, "WEIGHTS_BYTES", len(b"model.safetensors"))
    native.verify(tmp_path)
    (tmp_path / "config.json").write_bytes(b"changed")
    monkeypatch.setattr(native, "_sha", lambda path: "0" * 64 if path.name == "config.json"
                        else native.FILES[path.name])
    with pytest.raises(RuntimeError, match="SHA-256"):
        native.verify(tmp_path)


def test_fake_label_polarity_and_window_mean(monkeypatch):
    class Extractor:
        def __call__(self, windows, **kwargs):
            return {"input_values": torch.zeros((len(windows), 10))}

    class Model:
        def __call__(self, **kwargs):
            count = len(kwargs["input_values"])
            return SimpleNamespace(logits=torch.tensor([[0.0, 2.0]] * count))

    monkeypatch.setattr(native, "_windows", lambda samples: [
        (0, len(samples), samples), (0, len(samples), samples)])
    score = native.score_samples(np.ones(10, dtype=np.float32), Extractor(), Model(),
                                 "cpu", float("inf"))
    assert score == pytest.approx(torch.softmax(torch.tensor([0.0, 2.0]), 0)[1].item())


def test_candidate_provenance_is_external_and_not_local_fit():
    assert native.MODEL_REVISION == "c66306024a7ede0be291e9c4558b37634782dc4e"
    assert native.WEIGHTS_SHA256 == "905e330265c40a76955911ce86691fb4c8f2ed9c8085f4f046cac1383592a0ac"
    assert native.WEIGHTS_BYTES == 1_262_859_296
