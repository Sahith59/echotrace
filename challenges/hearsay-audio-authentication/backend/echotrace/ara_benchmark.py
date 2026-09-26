"""Frozen, model-only stress check on a bounded ArA-DF-2026 shard sample.

This is deliberately separate from the sponsor evaluation and from model fitting.
It reads the official gold metadata and audio archive without extracting paths.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import tarfile
import time
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf
from sklearn.metrics import roc_auc_score

from .primary_detector import MAX_SAMPLES, MIN_SAMPLES, model_status, score_primary


ARCHIVE_REPO_PATH = "data/track-2_development_test/track-2_development_test-000000.tar"
ARCHIVE_SHA256 = "c266140c6ade2e7064233f11ef21c727f5f57317fe8e915ee3c096aa9d683840"
LABELS_SHA256 = "1cd36378c09301e2ea7c4056e96cff1cf35da28203bb14572feb098e7121f90e"
SELECTION_SEED = "echotrace-ara-df-2026-09-26-v1"
THRESHOLD = 0.5


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def select_rows(rows, archive_repo_path: str, per_class: int, seed: str) -> list[dict]:
    """Freeze a label-balanced subset before any detector scores are inspected."""
    if per_class < 1:
        raise ValueError("per_class must be positive")
    pools: dict[str, list[dict]] = {"0": [], "1": []}
    seen: set[str] = set()
    for row in rows:
        identifier = row["id"]
        if identifier in seen:
            raise ValueError(f"Duplicate audio id: {identifier}")
        seen.add(identifier)
        if row["file_name"].split("::", 1)[0] != archive_repo_path:
            continue
        label = row["label"]
        if label not in pools:
            raise ValueError(f"Unexpected label: {label}")
        if row["file_name"] != f"{archive_repo_path}::{identifier}.flac":
            raise ValueError(f"Unexpected archive member mapping: {identifier}")
        pools[label].append(row)
    if any(len(pool) < per_class for pool in pools.values()):
        raise ValueError("Not enough genuine and synthetic records in this archive")
    def ordering(row: dict) -> str:
        return hashlib.sha256(f"{seed}|{row['id']}".encode()).hexdigest()
    chosen = sorted(pools["0"], key=ordering)[:per_class]
    chosen += sorted(pools["1"], key=ordering)[:per_class]
    return sorted(chosen, key=ordering)


def summarize(ledger: list[dict], threshold: float = THRESHOLD) -> dict:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between zero and one")
    good = [row for row in ledger if row["error"] is None]
    for row in good:
        if row["label"] not in {"0", "1"}:
            raise ValueError("Unexpected gold label")
        if not isinstance(row["score"], (float, int)) or not math.isfinite(row["score"]) or not 0 <= row["score"] <= 1:
            raise ValueError("Invalid detector score")
    tp = sum(row["label"] == "0" and row["score"] >= threshold for row in good)
    fn = sum(row["label"] == "0" and row["score"] < threshold for row in good)
    fp = sum(row["label"] == "1" and row["score"] >= threshold for row in good)
    tn = sum(row["label"] == "1" and row["score"] < threshold for row in good)
    labels = [int(row["label"] == "0") for row in good]
    return {
        "coverage": {"selected": len(ledger), "scored": len(good), "failed": len(ledger) - len(good)},
        "confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "recall": tp / (tp + fn) if tp + fn else None,
        "fpr": fp / (fp + tn) if fp + tn else None,
        "auroc": float(roc_auc_score(labels, [row["score"] for row in good])) if len(set(labels)) == 2 else None,
        "errors": dict(Counter(row["error"] for row in ledger if row["error"])),
    }


def evaluate(archive: Path, labels: Path, output: Path, *, per_class: int = 100,
             scorer=score_primary, detector_status=model_status,
             detector_name: str = "NII whole-file") -> dict:
    if file_sha256(archive) != ARCHIVE_SHA256:
        raise ValueError("Audio archive does not match the pinned upstream SHA-256")
    if file_sha256(labels) != LABELS_SHA256:
        raise ValueError("Gold labels do not match the frozen SHA-256")
    with gzip.open(labels, "rt", newline="", encoding="utf-8") as source:
        selected = select_rows(csv.DictReader(source), ARCHIVE_REPO_PATH, per_class, SELECTION_SEED)
    if output.exists():
        raise FileExistsError("Use a new output directory to preserve earlier evidence")
    output.mkdir(parents=True)
    manifest_fields = ("id", "file_name", "split", "label", "duration_sec", "sample_rate", "channels", "sha256", "flac_bytes")
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=manifest_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected)
    started = time.monotonic()
    ledger: list[dict] = []
    with tarfile.open(archive, "r") as source, (output / "scores.csv").open("w", newline="", encoding="utf-8") as target:
        fields = ("id", "label", "duration_sec", "sha256", "score", "error")
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(selected, 1):
            record = {"id": row["id"], "label": row["label"],
                      "duration_sec": row["duration_sec"], "sha256": row["sha256"],
                      "score": None, "error": None}
            try:
                member = source.getmember(row["id"] + ".flac")
                if not member.isfile():
                    raise ValueError("Archive member is not a regular file")
                file = source.extractfile(member)
                if file is None:
                    raise ValueError("Audio archive member cannot be read")
                audio_bytes = file.read()
                if hashlib.sha256(audio_bytes).hexdigest() != row["sha256"]:
                    raise ValueError("Audio SHA-256 does not match gold metadata")
                samples, rate = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
                if rate != 16_000 or samples.shape[1] != 1:
                    raise ValueError("Expected 16 kHz mono audio")
                if not MIN_SAMPLES <= samples.shape[0] <= MAX_SAMPLES:
                    raise ValueError("Audio is outside the primary detector duration scope")
                record["score"] = float(scorer(np.asarray(samples[:, 0], dtype=np.float32))["score"])
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"[:180]
            writer.writerow(record)
            target.flush()
            ledger.append(record)
            if index % 25 == 0:
                print(f"scored {index}/{len(selected)}", flush=True)
    metrics = summarize(ledger)
    report = {
        "benchmark": "ArA-DF-2026 track-2 development-test, frozen balanced shard-0 subset",
        "source": "https://huggingface.co/datasets/ArabicSpeech/ArA-DF-2026",
        "archive_sha256": ARCHIVE_SHA256,
        "labels_sha256": LABELS_SHA256,
        "manifest_sha256": file_sha256(output / "manifest.csv"),
        "selection_seed": SELECTION_SEED,
        "per_class": per_class,
        "threshold": THRESHOLD,
        "score_polarity": "higher means more synthetic; gold 0 is synthetic and gold 1 genuine",
        "detector": detector_name,
        "model": detector_status(),
        "metrics": metrics,
        "runtime_s": round(time.monotonic() - started, 3),
        "limits": "One shard and a balanced subset only; no fitting or threshold selection; model-only input gates; not the sponsor dataset or a full corpus estimate.",
    }
    (output / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--per-class", type=int, default=100)
    parser.add_argument("--detector", choices=("nii", "aasist"), default="nii")
    args = parser.parse_args()
    if args.detector == "aasist":
        from .model import model_status as aasist_status, score_window
        from .pipeline import _windows

        def score_aasist(samples: np.ndarray) -> dict:
            return {"score": float(np.mean([
                score_window(window)["score"] for _, _, window in _windows(samples)
            ]))}

        report = evaluate(args.archive, args.labels, args.output, per_class=args.per_class,
                          scorer=score_aasist, detector_status=aasist_status,
                          detector_name="AASIST-L mean full-coverage windows")
    else:
        report = evaluate(args.archive, args.labels, args.output, per_class=args.per_class)
    print(json.dumps(report["metrics"], indent=2))
    return 0 if report["metrics"]["coverage"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
