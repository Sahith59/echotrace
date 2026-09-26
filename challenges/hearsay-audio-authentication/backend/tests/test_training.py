"""The experimental runner's data and optimization contract."""

import json

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader, TensorDataset

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

    config = {"dataset_root": str(tmp_path), "train_manifest": "train.csv",
              "validation_manifest": "val.csv", "output_dir": str(tmp_path / "fresh"),
              "max_wall_seconds": 30, "max_steps": 2, "max_epochs": 2,
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
    assert checkpoint["model_config_sha256"] == training._sha256(training.CONFIG_PATH)
    assert checkpoint["upstream_revision"] == training.UPSTREAM_REVISION
    assert checkpoint["split_provenance"] == {
        "train": [{key: item[key] for key in ("file_id", "sha256", "label", "group_id", "speaker_id", "source_id")}
                  for item in train],
        "validation": [{key: item[key] for key in ("file_id", "sha256", "label", "group_id", "speaker_id", "source_id")}
                       for item in valid],
    }
    assert (output / "config.json").is_file()
    assert (output / "metrics.json").is_file()
    with pytest.raises(ValueError, match="fresh"):
        training.fit(Toy(), train, valid, config, output,
                     decode_fn=decode, pretrained_sha256="test-sha")


def test_validation_loss_uses_global_weight_denominator():
    model = Toy()
    with torch.no_grad():
        model.head.weight.zero_()
        model.head.bias.copy_(torch.tensor([2.0, -1.0]))
    x = torch.zeros(3, 64_600)
    target = torch.tensor([0, 0, 1])
    criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor([1.0, 3.0]))
    loader = DataLoader(TensorDataset(x, target), batch_size=2)
    actual = training._validate(model, loader, criterion, torch.device("cpu"), float("inf"))
    with torch.no_grad():
        expected = float(criterion(model(x)[1], target))
    assert actual["loss"] == pytest.approx(expected)


def test_nonfinite_validation_loss_rejected():
    model = Toy()
    loader = DataLoader(TensorDataset(torch.zeros(1, 64_600), torch.zeros(1, dtype=torch.long)))

    def nan_loss(logits, target):
        return logits.sum() * float("nan")

    with pytest.raises(RuntimeError, match="Non-finite validation loss"):
        training._validate(model, loader, nan_loss, torch.device("cpu"), float("inf"))


def test_fit_rejects_bad_direct_config_before_output(tmp_path):
    train, valid = balanced()
    config = {"dataset_root": str(tmp_path), "train_manifest": "train.csv",
              "validation_manifest": "val.csv", "output_dir": str(tmp_path / "out"),
              "max_wall_seconds": 30, "max_steps": 2, "max_epochs": 2,
              "batch_size": 2, "num_workers": 0, "learning_rate": 0.1,
              "seed": 3, "device": "cpu"}
    for key, bad in (("max_steps", 100_001), ("num_workers", 17),
                     ("learning_rate", float("nan"))):
        with pytest.raises(ValueError):
            training.fit(Toy(), train, valid, {**config, key: bad}, tmp_path / "out",
                         pretrained_sha256="test-sha")
    assert not (tmp_path / "out").exists()


def test_demo_hash_provenance_missing_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(training, "__file__", str(tmp_path / "backend/echotrace/training.py"))
    with pytest.raises(RuntimeError, match="provenance"):
        training._demo_hashes()


def test_nonfinite_gradient_rejected(tmp_path):
    train, valid = balanced()
    config = {"dataset_root": str(tmp_path), "train_manifest": "train.csv",
              "validation_manifest": "val.csv", "output_dir": str(tmp_path / "out"),
              "max_wall_seconds": 30, "max_steps": 1, "max_epochs": 1,
              "batch_size": 2, "num_workers": 0, "learning_rate": 0.1,
              "seed": 3, "device": "cpu"}
    model = Toy()
    model.head.weight.register_hook(lambda grad: torch.full_like(grad, float("inf")))
    with pytest.raises(RuntimeError, match="non-finite|Non-finite"):
        training.fit(model, train, valid, config, tmp_path / "out",
                     decode_fn=lambda path: (np.ones(32, dtype=np.float32), {}),
                     pretrained_sha256="test-sha")
