"""Bounded experimental AASIST-L fine-tuning; never promotes a checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from .audio import decode_audio
from .evaluation import load_manifest
from .model import CONFIG_PATH, UPSTREAM_REVISION, WEIGHTS_PATH, WEIGHTS_SHA256, WINDOW_SAMPLES, _sha256
from .pipeline import _windows
from .vendor.AASIST import Model


CONFIG_KEYS = {"dataset_root", "train_manifest", "validation_manifest", "output_dir",
               "max_wall_seconds", "max_steps", "max_epochs", "batch_size", "num_workers",
               "learning_rate", "seed", "device"}


def load_config(path: Path) -> dict:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    return _validate_config(config)


def _validate_config(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
        raise ValueError(f"Config must contain exactly {sorted(CONFIG_KEYS)}")
    for key in ("dataset_root", "train_manifest", "validation_manifest", "output_dir"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"{key} must be a nonempty path")
    for key, ceiling in (("max_wall_seconds", 10_800), ("max_steps", 100_000),
                         ("max_epochs", 1_000), ("batch_size", 256)):
        value = config[key]
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError(f"{key} must be an integer in [1, {ceiling}]")
    if type(config["num_workers"]) is not int or not 0 <= config["num_workers"] <= 16:
        raise ValueError("num_workers must be an integer in [0, 16]")
    if type(config["seed"]) is not int or not 0 <= config["seed"] < 2**32:
        raise ValueError("seed must be a nonnegative 32-bit integer")
    rate = config["learning_rate"]
    if type(rate) not in (float, int) or not math.isfinite(rate) or not 0 < rate <= 1:
        raise ValueError("learning_rate must be finite and in (0, 1]")
    if config["device"] not in ("cpu", "cuda"):
        raise ValueError("device must be cpu or cuda")
    if config["device"] == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable")
    return config


def _demo_hashes() -> set[str]:
    path = Path(__file__).resolve().parents[2] / "reports/public-pilot/provenance.json"
    if not path.is_file():
        raise RuntimeError("Pinned demonstration provenance is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    hashes = {entry["sha256"] for entry in data["files"]}
    if len(hashes) != 24 or any(len(value) != 64 for value in hashes):
        raise RuntimeError("Pinned demonstration provenance is invalid")
    return hashes


def validate_splits(train: list[dict], valid: list[dict],
                    *, excluded_hashes: set[str] | None = None) -> None:
    """Reject exact and metadata-linked leakage, including the 24 pilot files."""
    for name, records in (("train", train), ("validation", valid)):
        if {record["label"] for record in records} != {0, 1}:
            raise ValueError(f"{name} split requires both classes")
    if excluded_hashes is None:
        excluded_hashes = _demo_hashes()
    if any(record["sha256"] in excluded_hashes for record in train + valid):
        raise ValueError("Public demonstration material is excluded from training and validation")
    for key in ("sha256", "file_id", "group_id", "speaker_id", "source_id"):
        left = {str(r.get(key, "")).strip() for r in train} - {""}
        right = {str(r.get(key, "")).strip() for r in valid} - {""}
        if left & right:
            raise ValueError(f"Train/validation overlap by {key}")


def model_target(manifest_label: int) -> int:
    """Manifest 1=synthetic maps to AASIST target 0=spoof."""
    if manifest_label not in (0, 1):
        raise ValueError("Manifest label must be 0 or 1")
    return 1 - manifest_label


def first_window(samples: np.ndarray) -> np.ndarray:
    """The shared 64,600-sample first window, with repeat-padding for short audio."""
    return next(_windows(samples))[2]


class _AudioDataset(Dataset):
    def __init__(self, records: list[dict], decode_fn: Callable):
        self.records = records
        self.decode_fn = decode_fn

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        record = self.records[index]
        samples, _ = self.decode_fn(Path(record["path"]))
        window = first_window(samples)
        return torch.from_numpy(np.asarray(window, dtype=np.float32).copy()), model_target(record["label"])


def _data_hash(train: list[dict], valid: list[dict]) -> str:
    summary = {name: sorted((r["file_id"], r["sha256"], r["label"],
                             r.get("group_id", ""), r.get("speaker_id", ""), r.get("source_id", ""))
                            for r in records)
               for name, records in (("train", train), ("validation", valid))}
    return hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()


def _logits(model: torch.nn.Module, x: torch.Tensor) -> torch.Tensor:
    result = model(x)
    logits = result[1] if isinstance(result, tuple) else result
    if logits.ndim != 2 or logits.shape != (x.shape[0], 2) or not torch.isfinite(logits).all():
        raise RuntimeError("Model returned invalid two-class logits")
    return logits


def _validate(model, loader, criterion, device, deadline) -> dict:
    model.eval()
    loss_total = loss_weight = correct = count = 0
    with torch.inference_mode():
        for x, target in loader:
            if time.monotonic() >= deadline:
                raise TimeoutError("Training wall-clock limit reached during validation")
            x, target = x.to(device), target.to(device)
            logits = _logits(model, x)
            batch_loss = float(criterion(logits, target))
            if not math.isfinite(batch_loss):
                raise RuntimeError("Non-finite validation loss")
            batch_weight = (float(criterion.weight[target].sum())
                            if getattr(criterion, "weight", None) is not None else len(target))
            loss_total += batch_loss * batch_weight
            loss_weight += batch_weight
            correct += int((logits.argmax(dim=1) == target).sum())
            count += len(target)
    return {"count": count, "loss": loss_total / loss_weight, "accuracy": correct / count}


def fit(model: torch.nn.Module, train: list[dict], valid: list[dict], config: dict,
        output: Path, *, decode_fn: Callable = decode_audio,
        pretrained_sha256: str) -> dict:
    """Run bounded optimization and save the best validation-loss state."""
    _validate_config(config)
    validate_splits(train, valid)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a fresh directory")
    random.seed(config["seed"])
    np.random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config["seed"])
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    device = torch.device(config["device"])
    model.to(device)
    generator = torch.Generator().manual_seed(config["seed"])
    kwargs = {"batch_size": config["batch_size"], "num_workers": config["num_workers"],
              "pin_memory": device.type == "cuda"}
    train_loader = DataLoader(_AudioDataset(train, decode_fn), shuffle=True, generator=generator, **kwargs)
    val_loader = DataLoader(_AudioDataset(valid, decode_fn), shuffle=False, **kwargs)
    counts = Counter(model_target(r["label"]) for r in train)
    class_weights = torch.tensor([len(train) / (2 * counts[i]) for i in (0, 1)],
                                 dtype=torch.float32, device=device)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.json").write_text(json.dumps(config, indent=2, allow_nan=False) + "\n")
    data_sha256 = _data_hash(train, valid)
    fields = ("file_id", "sha256", "label", "group_id", "speaker_id", "source_id")
    split_provenance = {
        "train": [{key: record.get(key, "") for key in fields} for record in train],
        "validation": [{key: record.get(key, "") for key in fields} for record in valid],
    }
    model_config_sha256 = _sha256(CONFIG_PATH)
    start = time.monotonic()
    deadline = start + config["max_wall_seconds"]
    steps = 0
    best_loss = float("inf")
    best_validation = None
    completed_epochs = 0
    stop_reason = "max_epochs"
    for epoch in range(config["max_epochs"]):
        model.train()
        for x, target in train_loader:
            if time.monotonic() >= deadline:
                stop_reason = "wall_seconds"
                break
            x, target = x.to(device), target.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = _logits(model, x)
            loss = criterion(logits, target)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
            steps += 1
            if steps >= config["max_steps"]:
                stop_reason = "max_steps"
                break
        if steps == 0:
            break
        if time.monotonic() >= deadline:
            stop_reason = "wall_seconds"
            break
        try:
            validation = _validate(model, val_loader, criterion, device, deadline)
        except TimeoutError:
            stop_reason = "wall_seconds"
            break
        completed_epochs = epoch + 1
        if validation["loss"] < best_loss:
            best_loss = validation["loss"]
            best_validation = validation
            torch.save({"model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "epoch": completed_epochs, "steps": steps,
                        "validation": validation, "pretrained_sha256": pretrained_sha256,
                        "data_sha256": data_sha256, "config": config,
                        "model_config_sha256": model_config_sha256,
                        "upstream_revision": UPSTREAM_REVISION,
                        "split_provenance": split_provenance}, output / "best.pt")
        if stop_reason == "max_steps":
            break
    result = {"steps": steps, "epochs": completed_epochs, "stop_reason": stop_reason,
              "elapsed_seconds": round(time.monotonic() - start, 3),
              "validation": best_validation, "data_sha256": data_sha256,
              "pretrained_sha256": pretrained_sha256,
              "checkpoint": "best.pt" if best_validation is not None else None,
              "experimental": True, "promoted": False,
              "validation_policy": "fixed first 64600 samples; not whole-file web aggregation"}
    (output / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def run(config_path: Path) -> dict:
    config = load_config(config_path)
    root = Path(config["dataset_root"])
    train = load_manifest(Path(config["train_manifest"]), root)
    valid = load_manifest(Path(config["validation_manifest"]), root)
    validate_splits(train, valid)
    if not WEIGHTS_PATH.is_file() or _sha256(WEIGHTS_PATH) != WEIGHTS_SHA256:
        raise RuntimeError("Pinned AASIST-L weights are missing or failed checksum verification")
    architecture = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["model_config"]
    if architecture["nb_samp"] != WINDOW_SAMPLES:
        raise RuntimeError("AASIST-L sample count mismatch")
    model = Model(architecture)
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True), strict=True)
    return fit(model, train, valid, config, Path(config["output_dir"]),
               pretrained_sha256=WEIGHTS_SHA256)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded experimental AASIST-L fine-tuning")
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args.config), allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"TRAINING: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
