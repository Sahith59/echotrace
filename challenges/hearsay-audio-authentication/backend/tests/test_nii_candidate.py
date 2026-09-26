from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from echotrace import nii_candidate
from echotrace.nii_reference_validation import (
    MAX_ABS_LOGIT_TOLERANCE,
    MAX_ABS_PROBABILITY_TOLERANCE,
    validate_parity,
)


class CapturingEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.received = None

    def forward(self, samples):
        self.received = samples.detach().clone()
        frames = samples[:, :6].reshape(1, 3, 2).mean(-1, keepdim=True)
        return frames.repeat(1, 1, 768)


def test_candidate_contract_normalizes_complete_waveform_and_uses_fake_class_zero():
    encoder = CapturingEncoder()
    head = torch.nn.Linear(768, 2)
    with torch.no_grad():
        head.weight.zero_()
        head.bias.copy_(torch.tensor([2.0, 1.0]))
    samples = np.linspace(-0.2, 0.4, 16_000, dtype=np.float32)

    result = nii_candidate._score_with_models(samples, encoder, head)

    assert encoder.received.shape == (1, len(samples))
    assert float(encoder.received.mean()) == pytest.approx(0, abs=1e-6)
    assert float(encoder.received.std(unbiased=False)) == pytest.approx(1, abs=1e-5)
    assert result["raw_logits"] == pytest.approx([2.0, 1.0])
    assert result["score"] == pytest.approx(torch.softmax(torch.tensor([2.0, 1.0]), 0)[0].item())
    assert result["score_kind"] == "uncalibrated"


@pytest.mark.parametrize("samples,match", [
    (np.array([], dtype=np.float32), "nonempty"),
    (np.zeros((2, 10), dtype=np.float32), "one-dimensional"),
    (np.array([0, np.nan], dtype=np.float32), "finite"),
    (np.zeros(30 * 16_000 + 1, dtype=np.float32), "30 seconds"),
])
def test_candidate_rejects_invalid_or_overlong_audio_without_truncation(samples, match, monkeypatch):
    monkeypatch.setattr(nii_candidate, "_load_models", lambda: pytest.fail("model must not load"))
    with pytest.raises(ValueError, match=match):
        nii_candidate.score_samples(samples)


def test_pinned_identity_and_local_status_do_not_download(tmp_path, monkeypatch):
    missing = tmp_path / "model.safetensors"
    monkeypatch.setattr(nii_candidate, "WEIGHTS_PATH", missing)
    status = nii_candidate.candidate_status()
    assert status == {
        "name": "NII wav2vec-small-anti-deepfake",
        "version": nii_candidate.HF_REVISION[:12],
        "upstream_revision": nii_candidate.HF_REVISION,
        "source_revision": nii_candidate.SOURCE_REVISION,
        "weights_sha256": nii_candidate.WEIGHTS_SHA256,
        "available": False,
        "device": "cpu",
        "max_duration_s": 30,
        "reason": "Pinned NII candidate weights are missing or failed checksum verification.",
        "evaluation_boundary": "ASVspoof5 was used to train this checkpoint and is not independent evaluation data.",
    }
    assert not missing.exists()


def test_reference_tolerances_are_predeclared_and_never_relaxed(tmp_path):
    assert MAX_ABS_LOGIT_TOLERANCE == 1e-3
    assert MAX_ABS_PROBABILITY_TOLERANCE == 1e-4
    reference = {"cases": [{"id": "tone", "raw_logits": [0.2, -0.1], "score": 0.5744425}]}
    candidate = {"cases": [{"id": "tone", "raw_logits": [0.2011, -0.1], "score": 0.5744425}]}
    ref_path, candidate_path = tmp_path / "reference.json", tmp_path / "candidate.json"
    ref_path.write_text(json.dumps(reference))
    candidate_path.write_text(json.dumps(candidate))
    with pytest.raises(RuntimeError, match="investigate; do not relax"):
        validate_parity(ref_path, candidate_path)


def test_reference_validation_accepts_all_five_fixed_cases_within_contract(tmp_path):
    cases = [
        {"id": name, "raw_logits": [index / 10, -index / 10], "score": 0.5 + index / 100}
        for index, name in enumerate(("real-1", "real-2", "synthetic-1", "synthetic-2", "tone"))
    ]
    reference = tmp_path / "reference.json"
    candidate = tmp_path / "candidate.json"
    reference.write_text(json.dumps({"runtime": "official-fairseq-cpu-fp32", "cases": cases}))
    candidate.write_text(json.dumps({"runtime": "transformers-cpu-fp32", "cases": cases}))
    report = validate_parity(reference, candidate)
    assert report["passed"] is True
    assert report["case_count"] == 5

