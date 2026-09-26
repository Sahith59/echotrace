"""The experimental runner's data and optimization contract."""

import json

import numpy as np
import pytest
import torch

from echotrace import training


def record(file_id, label, digest, **links):
    return {"file_id": file_id, "label": label, "sha256": digest,
            "path": file_id, "group_id": "", "speaker_id": "", "source_id": "", **links}


def balanced():
    return ([record("tr-real", 0, "a"), record("tr-fake", 1, "b")],
            [record("va-real", 0, "c"), record("va-fake", 1, "d")])


def test_config_rejects_unbounded_limits(tmp_path):
    good = {"dataset_root": str(tmp_path), "train_manifest": "train.csv",
            "validation_manifest": "val.csv", "output_dir": "out",
            "max_wall_seconds": 60, "max_steps": 2, "max_epochs": 2,
            "batch_size": 2, "num_workers": 0, "learning_rate": 0.00001,
            "seed": 7, "device": "cpu"}
    for key, bad in (("max_wall_seconds", 10801), ("max_steps", 0),
                     ("max_epochs", 0), ("batch_size", 0),
                     ("num_workers", -1), ("learning_rate", float("nan"))):
        config = {**good, key: bad}
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        with pytest.raises(ValueError):
            training.load_config(path)
    path.write_text(json.dumps(good))
    assert training.load_config(path)["max_steps"] == 2


@pytest.mark.parametrize("field,value", [("sha256", "a"), ("file_id", "tr-real"),
                                         ("group_id", "g"), ("speaker_id", "s"),
                                         ("source_id", "src")])
def test_split_overlap_rejected(field, value):
    train, valid = balanced()
    train[0][field] = value
    valid[0][field] = value
    with pytest.raises(ValueError, match="overlap"):
        training.validate_splits(train, valid)


def test_both_classes_and_demo_hash_exclusion():
    train, valid = balanced()
    with pytest.raises(ValueError, match="both classes"):
        training.validate_splits(train[:1], valid)
    with pytest.raises(ValueError, match="demonstration"):
        training.validate_splits(train, valid, excluded_hashes={"a"})


def test_label_conversion_and_window_parity():
    assert training.model_target(1) == 0
    assert training.model_target(0) == 1
    with pytest.raises(ValueError):
        training.model_target(2)
    short = np.array([1, 2, 3], dtype=np.float32)
    np.testing.assert_array_equal(training.first_window(short)[:8],
                                  np.array([1, 2, 3, 1, 2, 3, 1, 2]))
    long = np.arange(70_000, dtype=np.float32)
    np.testing.assert_array_equal(training.first_window(long), long[:64_600])


class Toy(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.head = torch.nn.Linear(1, 2)

    def forward(self, x):
        logits = self.head(x.mean(dim=1, keepdim=True))
        return None, logits


def test_optimizer_checkpoint_and_provenance(tmp_path):
    train, valid = balanced()
    values = {"tr-real": -0.5, "tr-fake": 0.5,
              "va-real": -0.6, "va-fake": 0.6}

    def decode(path):
        return np.full(32, values[path.name], dtype=np.float32), {}

    config = {"max_wall_seconds": 30, "max_steps": 2, "max_epochs": 2,
              "batch_size": 2, "num_workers": 0, "learning_rate": 0.1,
              "seed": 3, "device": "cpu"}
    model = Toy()
    before = {k: v.clone() for k, v in model.state_dict().items()}
    output = tmp_path / "fresh"
    result = training.fit(model, train, valid, config, output,
                          decode_fn=decode, pretrained_sha256="test-sha")
    assert result["steps"] == 2
    assert result["validation"]["count"] == 2
    assert any(not torch.equal(before[k], v) for k, v in model.state_dict().items())
    checkpoint = torch.load(output / "best.pt", map_location="cpu", weights_only=True)
    restored = Toy()
    restored.load_state_dict(checkpoint["model_state_dict"])
    assert checkpoint["pretrained_sha256"] == "test-sha"
    assert checkpoint["data_sha256"] == result["data_sha256"]
    assert (output / "config.json").is_file()
    assert (output / "metrics.json").is_file()
    with pytest.raises(ValueError, match="fresh"):
        training.fit(Toy(), train, valid, config, output,
                     decode_fn=decode, pretrained_sha256="test-sha")
