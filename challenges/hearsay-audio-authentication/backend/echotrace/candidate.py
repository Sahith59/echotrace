"""Offline, bounded comparison using the official full AASIST checkpoint.

Run ``python -m echotrace.candidate --setup`` once, then score a labeled
manifest into a new directory. This module never changes the web detector.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
import torch

from .audio import SAMPLE_RATE, decode_audio
from .evaluation import evaluate_predictions, load_manifest
from .pipeline import _windows
from .vendor.AASIST import Model


UPSTREAM_REVISION = "a04c9863f63d44471dde8a6abcb3b082b07cd1d1"
UPSTREAM_REPOSITORY = "https://github.com/clovaai/aasist"
WEIGHTS_URL = f"https://raw.githubusercontent.com/clovaai/aasist/{UPSTREAM_REVISION}/models/weights/AASIST.pth"
CONFIG_URL = f"https://raw.githubusercontent.com/clovaai/aasist/{UPSTREAM_REVISION}/config/AASIST.conf"
WEIGHTS_SHA256 = "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
CONFIG_SHA256 = "c25023331685027cce90e1b9a0d2df10aa04b2a27d9b27d5afa36e6815b0fe76"
WEIGHTS_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "AASIST.pth"
CONFIG_PATH = Path(__file__).resolve().parent / "vendor" / "AASIST.conf"
WINDOW_SAMPLES = 64_600
MAX_FILES = 256
MAX_WEIGHTS_BYTES = 20 * 1024 * 1024
_model: Model | None = None


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify_weights() -> str:
    """Require an already cached, exact official checkpoint for inference."""
    if not WEIGHTS_PATH.is_file() or _sha256(WEIGHTS_PATH) != WEIGHTS_SHA256:
        raise RuntimeError("Full AASIST checkpoint is missing or failed hash verification; run --setup")
    if _sha256(CONFIG_PATH) != CONFIG_SHA256:
        raise RuntimeError("Full AASIST config failed hash verification")
    return WEIGHTS_SHA256


def setup() -> Path:
    """Only explicit setup may fetch the revision-pinned checkpoint."""
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if WEIGHTS_PATH.is_file() and _sha256(WEIGHTS_PATH) == WEIGHTS_SHA256:
        return WEIGHTS_PATH
    target = WEIGHTS_PATH.with_suffix(".download")
    try:
        with urllib.request.urlopen(WEIGHTS_URL, timeout=30) as response, target.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_WEIGHTS_BYTES:
                    raise RuntimeError("Full AASIST checkpoint exceeds download limit")
                output.write(chunk)
        if _sha256(target) != WEIGHTS_SHA256:
            raise RuntimeError("Full AASIST checkpoint hash mismatch")
        target.replace(WEIGHTS_PATH)
    finally:
        target.unlink(missing_ok=True)
    return WEIGHTS_PATH


def _load_model() -> Model:
    global _model
    if _model is None:
        verify_weights()
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if config["model_config"]["nb_samp"] != WINDOW_SAMPLES:
            raise RuntimeError("Full AASIST config window size mismatch")
        model = Model(config["model_config"])
        state = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        model.eval()
        _model = model
    return _model


def score_window(samples: np.ndarray) -> dict:
    if len(samples) != WINDOW_SAMPLES:
        raise ValueError(f"Full AASIST expects {WINDOW_SAMPLES} samples")
    x = torch.from_numpy(np.asarray(samples, dtype=np.float32).copy()).unsqueeze(0)
    with torch.inference_mode():
        _, output = _load_model()(x)
        logits = [float(value) for value in output[0].cpu().tolist()]
        score = float(torch.softmax(output, dim=-1)[0, 0].cpu())
    if len(logits) != 2 or not math.isfinite(score) or not all(map(math.isfinite, logits)):
        raise RuntimeError("Full AASIST returned invalid logits")
    return {"score": score, "logits": logits}


def run(manifest: Path, root: Path, output: Path) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a fresh directory")
    records = load_manifest(manifest, root)
    if len(records) > MAX_FILES:
        raise ValueError(f"Candidate run is limited to {MAX_FILES} files")
    if {record["label"] for record in records} != {0, 1}:
        raise ValueError("Candidate evaluation requires both genuine and synthetic labels")
    checkpoint_hash = verify_weights()
    files = []
    predictions = []
    for record in records:
        samples, input_info = decode_audio(Path(record["path"]))
        intervals = []
        scores = []
        for start, end, window in _windows(samples):
            result = score_window(window)
            scores.append(result["score"])
            intervals.append({
                "start_s": round(start / SAMPLE_RATE, 5),
                "end_s": round(end / SAMPLE_RATE, 5),
                "score": result["score"],
                "raw_logits": result["logits"],
            })
        score = float(np.mean(scores))
        predictions.append((record["file_id"], score))
        files.append({
            "file_id": record["file_id"], "path": record["path"],
            "label": record["label"], "sha256": record["sha256"],
            "input": input_info, "synthetic_score": score, "intervals": intervals,
        })
    details = {
        "schema_version": "1.0", "score_kind": "uncalibrated",
        "intended_scope": "Offline comparison on labeled speech samples; every decoded clip is scored. Quiet audio is not gated as in the web pipeline.",
        "model": {
            "name": "AASIST", "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_revision": UPSTREAM_REVISION, "weights_url": WEIGHTS_URL,
            "weights_sha256": checkpoint_hash, "config_url": CONFIG_URL,
            "config_sha256": CONFIG_SHA256, "device": "cpu",
            "spoof_logit_index": 0, "bonafide_logit_index": 1,
        },
        "aggregation": {
            "method": "mean_window_spoof_softmax", "window_samples": WINDOW_SAMPLES,
            "hop_samples": WINDOW_SAMPLES, "tail_policy": "end_anchored_overlap",
            "short_input_policy": "repeat_pad", "validated_on_sponsor_data": False,
        },
        "files": files,
    }
    output.mkdir(parents=True, exist_ok=False)
    predictions_path = output / "predictions.csv"
    with predictions_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(["file_id", "synthetic_score"])
        writer.writerows((file_id, repr(score)) for file_id, score in predictions)
    (output / "details.json").write_text(json.dumps(details, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    metrics = evaluate_predictions(records, predictions_path)
    metrics["note"] = "Metrics describe only this supplied labeled set; scores are uncalibrated."
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline full-AASIST comparison candidate")
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--setup", action="store_true", help="explicitly download the pinned checkpoint")
    args = parser.parse_args(argv)
    try:
        if args.setup:
            if args.manifest or args.root or args.output:
                parser.error("--setup cannot be combined with a run")
            print(setup())
        else:
            if not all((args.manifest, args.root, args.output)):
                parser.error("manifest, --root, and --output are required")
            print(json.dumps(run(args.manifest, args.root, args.output), allow_nan=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"AASIST CANDIDATE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
