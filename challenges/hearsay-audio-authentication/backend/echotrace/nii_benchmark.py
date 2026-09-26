"""Frozen external benchmark runner for the non-serving NII candidate."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf
from sklearn.metrics import roc_auc_score

from .nii_candidate import MAX_SAMPLES, MIN_SAMPLES, SAMPLE_RATE, candidate_status, score_samples


MANIFEST_SHA256 = "dbfa528249c855261d64b864956a6b346b0faf40897622bae6e5a28ba1f9309a"
FIXED_THRESHOLD = 0.5
MIN_RECALL = 0.80
MAX_FPR = 0.05


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _load_samples(path: Path) -> np.ndarray:
    samples, rate = sf.read(path, dtype="float32", always_2d=True)
    if rate != SAMPLE_RATE:
        raise ValueError(f"sample_rate:{rate}")
    return samples.mean(axis=1, dtype=np.float32)


def evaluate(manifest_path: Path, dataset_root: Path, output_dir: Path, scorer=score_samples) -> dict:
    manifest_path = Path(manifest_path)
    dataset_root = Path(dataset_root).resolve()
    if _sha256(manifest_path) != MANIFEST_SHA256:
        raise ValueError("In-the-Wild manifest does not match the frozen SHA-256")
    with manifest_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 2_000 or Counter(row["label"] for row in rows) != {"0": 1_000, "1": 1_000}:
        raise ValueError("Frozen benchmark must contain exactly 1,000 genuine and 1,000 spoof rows")
    if any(len(row.get("sha256", "")) != 64 for row in rows):
        raise ValueError("Frozen benchmark requires a SHA-256 for every input")
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Benchmark output directory must be new")
    output_dir.mkdir(parents=True)

    started = time.monotonic()
    ledger = []
    for index, row in enumerate(rows):
        record = {"file_id": row["file_id"], "label": int(row["label"]),
                  "duration_s": float(row["duration_s"]), "score": None, "error": None}
        try:
            path = (dataset_root / row["path"]).resolve()
            if dataset_root not in path.parents or not path.is_file():
                raise ValueError("audio_path_unavailable")
            if _sha256(path) != row["sha256"]:
                raise ValueError("audio_sha256_mismatch")
            samples = _load_samples(path)
            if len(samples) < MIN_SAMPLES:
                raise ValueError("shorter_than_400_samples")
            if len(samples) > MAX_SAMPLES:
                raise ValueError("longer_than_30_seconds")
            result = scorer(samples)
            score = float(result["score"])
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("invalid_score")
            record["score"] = score
        except Exception as exc:
            record["error"] = str(exc)[:300] or type(exc).__name__
        ledger.append(record)
        if (index + 1) % 100 == 0:
            print(f"scored {index + 1}/{len(rows)}", flush=True)

    eligible = [record for record in ledger if record["error"] is None]
    labels = np.asarray([record["label"] for record in eligible], dtype=np.int64)
    scores = np.asarray([record["score"] for record in eligible], dtype=np.float64)
    predicted = scores >= FIXED_THRESHOLD
    tp = int(np.sum(predicted & (labels == 1)))
    fn = int(np.sum(~predicted & (labels == 1)))
    fp = int(np.sum(predicted & (labels == 0)))
    tn = int(np.sum(~predicted & (labels == 0)))
    recall = tp / (tp + fn) if tp + fn else None
    fpr = fp / (fp + tn) if fp + tn else None
    auroc = float(roc_auc_score(labels, scores)) if set(labels.tolist()) == {0, 1} else None
    errors = Counter(record["error"] for record in ledger if record["error"] is not None)
    report = {
        "schema_version": "1.0",
        "benchmark": "In-the-Wild frozen external 2k",
        "manifest": {"sha256": MANIFEST_SHA256, "rows": len(rows), "genuine": 1_000, "spoof": 1_000},
        "model": candidate_status(),
        "protocol": {
            "score": "class-0 fake softmax",
            "threshold": FIXED_THRESHOLD,
            "threshold_selected_on_this_benchmark": False,
            "recall_gate": MIN_RECALL,
            "fpr_gate": MAX_FPR,
            "max_duration_s": 30,
            "long_or_failed_rows_retained": True,
            "eligibility_scope": "model input eligibility; app quality gates are evaluated separately",
        },
        "coverage": {
            "total": len(ledger), "eligible": len(eligible), "failed": len(ledger) - len(eligible),
            "fraction": len(eligible) / len(ledger), "errors": dict(sorted(errors.items())),
            "duration_le_30_s": sum(record["duration_s"] <= 30 for record in ledger),
            "duration_gt_30_s": sum(record["duration_s"] > 30 for record in ledger),
        },
        "metrics": {
            "auroc": auroc, "recall": recall, "fpr": fpr,
            "true_positive": tp, "false_negative": fn, "false_positive": fp, "true_negative": tn,
        },
        "gate": {
            "recall_passed": recall is not None and recall >= MIN_RECALL,
            "fpr_passed": fpr is not None and fpr <= MAX_FPR,
            "coverage_passed": len(eligible) == len(ledger),
        },
        "runtime_s": round(time.monotonic() - started, 3),
        "claim_boundary": "Benchmark replication; not sponsor validation; not used for fitting. Upstream pretraining overlap is unknown. ASVspoof5 trained this model and is not independent evaluation data.",
    }
    report["gate"]["eligible_for_review"] = all(report["gate"].values())
    with (output_dir / "scores.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=("file_id", "label", "duration_s", "score", "error"))
        writer.writeheader()
        writer.writerows(ledger)
    (output_dir / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    report = evaluate(args.manifest, args.dataset_root, args.output_dir)
    print(json.dumps(report, indent=2))
    return 0 if report["gate"]["eligible_for_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
