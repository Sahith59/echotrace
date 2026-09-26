import numpy as np
import pytest


def test_primary_status_pins_weights_config_parity_and_scope():
    from echotrace.primary_detector import CONFIG_SHA256, model_status
    status = model_status()
    assert status["name"] == "NII wav2vec-small-anti-deepfake"
    assert status["role"] == "primary"
    assert status["available"] is True
    assert status["weights_sha256"] == "828ee456122f86d5d631cb7895a10e5c62c78a4fcb8a8b1c42cb5838a9abcfe0"
    assert status["config_sha256"] == CONFIG_SHA256
    assert status["parity_approved"] is True
    assert status["max_duration_s"] == 30
    assert status["min_samples"] == 400
    assert status["score_kind"] == "uncalibrated"


def test_primary_score_preserves_whole_file_contract(monkeypatch):
    from echotrace import primary_detector
    seen = []
    monkeypatch.setattr(primary_detector, "model_status", lambda: {
        "available": True, "reason": None})
    monkeypatch.setattr(primary_detector, "score_samples", lambda samples: (
        seen.append(samples.copy()) or {"score": .8, "raw_logits": [2., -1.],
                                        "aggregation": "whole_file_layer_norm_mean_pool"}))
    samples = np.linspace(-.1, .1, 1234, dtype=np.float32)
    result = primary_detector.score_primary(samples)
    np.testing.assert_array_equal(seen[0], samples)
    assert result["score"] == .8
    assert result["raw_logits"] == [2., -1.]


@pytest.mark.parametrize("count,message", [(399, "400"), (480001, "30 seconds")])
def test_primary_score_rejects_out_of_scope_lengths_before_model(monkeypatch, count, message):
    from echotrace import primary_detector
    monkeypatch.setattr(primary_detector, "score_samples", lambda samples: pytest.fail("model was called"))
    with pytest.raises(primary_detector.PrimaryDetectorError, match=message):
        primary_detector.score_primary(np.ones(count, dtype=np.float32))
