"""Bounded, leakage-aware whole-file evaluation of AASIST-L checkpoints.

Manifest label 1 means synthetic; AASIST-L softmax class 0 is the score.
This module makes no network requests and never changes the web detector.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

from .audio import AudioError, decode_audio, measure_audio
from .evaluation import load_manifest
from .model import (CONFIG_PATH, UPSTREAM_REVISION, WEIGHTS_PATH, WEIGHTS_SHA256,
                    WINDOW_SAMPLES, _sha256)
from .pipeline import _windows
from .training import _demo_hashes, validate_splits
from .vendor.AASIST import Model


PROVENANCE_FIELDS = ("file_id", "sha256", "label", "group_id", "speaker_id", "source_id")
LINK_FIELDS = ("sha256", "file_id", "group_id", "speaker_id", "source_id")
AGGREGATION = {"method": "mean_window_spoof_softmax", "window_samples": WINDOW_SAMPLES,
               "hop_samples": WINDOW_SAMPLES, "tail_policy": "end_anchored_overlap",
               "short_input_policy": "repeat_pad", "quality_gate": "shared_measure_audio"}


def _config() -> tuple[dict, str]:
    digest = _sha256(CONFIG_PATH)
    architecture = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["model_config"]
    if architecture["nb_samp"] != WINDOW_SAMPLES:
        raise RuntimeError("AASIST-L sample count mismatch")
    return architecture, digest


def _load_baseline() -> tuple[Model, str, str]:
    if not WEIGHTS_PATH.is_file() or _sha256(WEIGHTS_PATH) != WEIGHTS_SHA256:
        raise RuntimeError("Pinned AASIST-L weights are missing or failed checksum verification")
    architecture, config_sha256 = _config()
    model = Model(architecture)
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True), strict=True)
    return model, WEIGHTS_SHA256, config_sha256


def load_checkpoint(path: Path, expected_sha256: str | None) -> dict:
    """Verify identity and training metadata before model construction."""
    if expected_sha256 is None or len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("--checkpoint-sha256 must be a lowercase 64-character SHA-256 digest")
    path = Path(path)
    if not path.is_file() or _sha256(path) != expected_sha256:
        raise ValueError("Checkpoint SHA-256 mismatch or file missing")
    if not WEIGHTS_PATH.is_file() or _sha256(WEIGHTS_PATH) != WEIGHTS_SHA256:
        raise RuntimeError("Pinned AASIST-L pretrained weights are missing or failed checksum verification")
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("Checkpoint must be a dictionary")
    if checkpoint.get("pretrained_sha256") != WEIGHTS_SHA256:
        raise ValueError("Checkpoint pretrained SHA-256 does not match pinned AASIST-L")
    _, config_sha256 = _config()
    if checkpoint.get("model_config_sha256") != config_sha256:
        raise ValueError("Checkpoint model config SHA-256 is missing or mismatched")
    if checkpoint.get("upstream_revision") != UPSTREAM_REVISION:
        raise ValueError("Checkpoint upstream revision is missing or mismatched")
    if not isinstance(checkpoint.get("model_state_dict"), dict):
        raise ValueError("Checkpoint model_state_dict is missing")
    _validated_splits(checkpoint)
    return checkpoint


def _validated_splits(checkpoint: dict) -> dict[str, list[dict]]:
    splits = checkpoint.get("split_provenance")
    if not isinstance(splits, dict) or set(splits) != {"train", "validation"}:
        raise ValueError("Checkpoint split provenance is missing or malformed")
    for name in ("train", "validation"):
        rows = splits[name]
        if not isinstance(rows, list) or not rows:
            raise ValueError("Checkpoint split provenance is malformed")
        for row in rows:
            if (not isinstance(row, dict) or not set(PROVENANCE_FIELDS).issubset(row)
                    or type(row["label"]) is not int or row["label"] not in (0, 1)
                    or not isinstance(row["file_id"], str) or not row["file_id"].strip()
                    or not isinstance(row["sha256"], str) or len(row["sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in row["sha256"])
                    or any(not isinstance(row[field], str) for field in PROVENANCE_FIELDS if field != "label")):
                raise ValueError("Checkpoint split provenance is malformed")
        ids = [row["file_id"].strip() for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("Checkpoint split provenance has duplicate file IDs")
    try:
        validate_splits(splits["train"], splits["validation"])
    except ValueError as exc:
        raise ValueError(f"Checkpoint split provenance is invalid: {exc}") from exc
    return splits


def validate_provenance(records: list[dict], checkpoint: dict, *, role: str) -> None:
    """Reject exact content and optional metadata links to forbidden splits."""
    if role not in ("selection", "acceptance"):
        raise ValueError("Role must be selection or acceptance")
    splits = _validated_splits(checkpoint)
    prohibited = splits["train"] + (splits["validation"] if role == "acceptance" else [])
    for key in LINK_FIELDS:
        old = {row[key].strip() for row in prohibited if row[key].strip()}
        new = {str(row.get(key, "")).strip() for row in records if str(row.get(key, "")).strip()}
        if old & new:
            raise ValueError(f"Evaluation overlap with training provenance by {key}")


def _load_detector(checkpoint: dict | None, device: str) -> tuple[Model, str, str]:
    if checkpoint is None:
        model, digest, config_sha = _load_baseline()
    else:
        architecture, config_sha = _config()
        model = Model(architecture)
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        digest = ""  # Caller records the checked checkpoint file digest.
    model.to(torch.device(device))
    model.eval()
    return model, digest, config_sha


def _score_samples(samples: np.ndarray, model: Model, device: str, deadline: float) -> float:
    scores = []
    with torch.inference_mode():
        for _, _, window in _windows(samples):
            if time.monotonic() >= deadline:
                raise TimeoutError("Evaluation wall-clock limit reached")
            x = torch.from_numpy(np.asarray(window, dtype=np.float32).copy()).unsqueeze(0).to(device)
            result = model(x)
            logits = result[1] if isinstance(result, tuple) else result
            if logits.shape != (1, 2) or not torch.isfinite(logits).all():
                raise RuntimeError("AASIST-L returned invalid two-class logits")
            score = float(torch.softmax(logits, dim=-1)[0, 0].cpu())
            if not math.isfinite(score):
                raise RuntimeError("AASIST-L returned a non-finite score")
            scores.append(score)
    return float(np.mean(scores))


def _public_records(manifest: Path, records: list[dict]) -> list[dict]:
    with Path(manifest).open(encoding="utf-8-sig", newline="") as handle:
        raw = {row["file_id"].strip(): row for row in csv.DictReader(handle)}
    return [{**{key: record.get(key, "") for key in PROVENANCE_FIELDS},
             **{key: value for key, value in raw[record["file_id"]].items()
                if key in ("attack_id", "codec", "partition")}}
            for record in records]


def run(manifest: Path, dataset_root: Path, output: Path, *, device: str,
        checkpoint: Path | None = None, checkpoint_sha256: str | None = None,
        role: str = "acceptance", max_files: int = 10_000, max_seconds: int = 3_600) -> dict:
    """Write one complete score ledger, including explicit quiet/error rows."""
    if role not in ("selection", "acceptance"):
        raise ValueError("Role must be selection or acceptance")
    if device not in ("cpu", "cuda") or (device == "cuda" and not torch.cuda.is_available()):
        raise ValueError("Device must be available cpu or cuda")
    if type(max_files) is not int or not 1 <= max_files <= 10_000:
        raise ValueError("max_files must be an integer in [1, 10000]")
    if type(max_seconds) is not int or not 1 <= max_seconds <= 5_400:
        raise ValueError("max_seconds must be an integer in [1, 5400]")
    if (checkpoint is None) != (checkpoint_sha256 is None):
        raise ValueError("--checkpoint and --checkpoint-sha256 must be provided together")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a fresh directory")
    records = load_manifest(Path(manifest), Path(dataset_root))
    if len(records) > max_files:
        raise ValueError("Manifest exceeds max_files")
    if {record["label"] for record in records} != {0, 1}:
        raise ValueError("Evaluation requires both classes")
    candidate = checkpoint is not None
    loaded = load_checkpoint(checkpoint, checkpoint_sha256) if candidate else None
    if candidate:
        validate_provenance(records, loaded, role=role)
        if any(record["sha256"] in _demo_hashes() for record in records):
            raise ValueError("Public demonstration material is excluded from candidate evaluation")
    start = time.monotonic()
    deadline = start + max_seconds
    model, model_sha, config_sha = _load_detector(loaded, device)
    model_sha = checkpoint_sha256 if candidate else model_sha
    output.mkdir(parents=True, exist_ok=False)
    failures = []
    scores = []
    for record in records:
        status = "scored"
        score = None
        reason = None
        try:
            if time.monotonic() >= deadline:
                raise TimeoutError("Evaluation wall-clock limit reached")
            samples, _ = decode_audio(Path(record["path"]))
            _, _, too_quiet = measure_audio(samples)
            if too_quiet:
                status, reason = "quiet", "Audio is too quiet for a defensible synthesis assessment"
            else:
                score = _score_samples(samples, model, device, deadline)
        except (AudioError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
            status, reason = "failed", str(exc)
        if score is None:
            failures.append({"file_id": record["file_id"], "status": status, "reason": reason})
        scores.append((record["file_id"], score, status))
    scores_path = output / "scores.csv"
    with scores_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("file_id", "synthetic_score", "status"))
        for file_id, score, status in scores:
            writer.writerow((file_id, "" if score is None else format(score, ".17g"), status))
    result = {
        "role": role, "model_kind": "candidate" if candidate else "baseline",
        "checkpoint_sha256": model_sha, "config_sha256": config_sha,
        "upstream_revision": UPSTREAM_REVISION, "aggregation": AGGREGATION,
        "complete": not failures, "completed_count": len(scores) - len(failures),
        "failure_count": len(failures), "failures": failures,
        "records": _public_records(Path(manifest), records),
        "training_provenance": loaded["split_provenance"] if candidate else None,
        "scores_sha256": _sha256(scores_path),
        "elapsed_seconds": round(time.monotonic() - start, 3),
    }
    (output / "run.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded whole-file AASIST-L checkpoint evaluation")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--role", choices=("selection", "acceptance"), default="acceptance")
    parser.add_argument("--max-files", type=int, default=10_000)
    parser.add_argument("--max-seconds", "--max-wall-seconds", dest="max_seconds", type=int, default=3_600)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args.manifest, args.dataset_root, args.output, device=args.device,
                             checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256,
                             role=args.role, max_files=args.max_files, max_seconds=args.max_seconds),
                         allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"CHECKPOINT_EVAL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
