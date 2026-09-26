"""Compare frozen baseline/candidate runs; never promote a model automatically."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from .evaluation import _rows, _score, _unique_ids

LINKS = ("file_id", "sha256", "group_id", "speaker_id", "source_id")
GATES = {"max_false_positive_rate": .05, "min_recall": .8,
         "min_recall_gain": .1, "min_each_class": 100}


def _validate_values(labels, scores):
    if len(labels) != len(scores) or not labels or set(labels) != {0, 1}:
        raise ValueError("Both classes and matching nonempty scores are required")
    if any(type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1 for x in scores):
        raise ValueError("Scores must be finite and in [0,1]")


def _wilson(successes, count):
    z = 1.959963984540054
    p = successes / count
    denominator = 1 + z * z / count
    centre = (p + z * z / (2 * count)) / denominator
    half = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [max(0., centre - half), min(1., centre + half)]


def summarize(labels, scores, threshold):
    _validate_values(labels, scores)
    if not math.isfinite(threshold) or not 0 <= threshold <= np.nextafter(1., math.inf):
        raise ValueError("Invalid threshold")
    genuine = labels.count(0)
    synthetic = labels.count(1)
    fp = sum(y == 0 and s >= threshold for y, s in zip(labels, scores))
    tp = sum(y == 1 and s >= threshold for y, s in zip(labels, scores))
    return {"genuine_count": genuine, "synthetic_count": synthetic,
            "confusion": {"tn": genuine - fp, "fp": fp, "fn": synthetic - tp, "tp": tp},
            "recall": tp / synthetic, "false_positive_rate": fp / genuine,
            "recall_interval_95": _wilson(tp, synthetic),
            "false_positive_rate_interval_95": _wilson(fp, genuine),
            "roc_auc": float(roc_auc_score(labels, scores)),
            "average_precision": float(average_precision_score(labels, scores))}


def select_threshold(labels, scores, *, max_fpr=.05):
    """Highest recall under a selection-set FPR cap; ties stay together."""
    _validate_values(labels, scores)
    if not math.isfinite(max_fpr) or not 0 <= max_fpr <= 1:
        raise ValueError("max_fpr must be in [0,1]")
    # Sorting once avoids a quadratic threshold sweep on a large selection set.
    genuine, synthetic = labels.count(0), labels.count(1)
    tp = fp = 0
    best = (0., 0., float(np.nextafter(max(scores), math.inf)))
    grouped = {}
    for y, score in zip(labels, scores):
        counts = grouped.setdefault(score, [0, 0])
        counts[y] += 1
    for threshold, (real, fake) in sorted(grouped.items(), reverse=True):
        fp += real
        tp += fake
        fpr = fp / genuine
        if fpr <= max_fpr:
            candidate = (tp / synthetic, -fpr, float(threshold))
            best = max(best, candidate)
    return best[2]


def _disjoint(left, right):
    for key in LINKS:
        a = {r.get(key, "") for r in left} - {"", None}
        b = {r.get(key, "") for r in right} - {"", None}
        if a & b:
            raise ValueError(f"Evaluation partitions overlap by {key}")


def _read(folder, kind, role):
    folder = Path(folder)
    run = json.loads((folder / "run.json").read_text())
    if not isinstance(run, dict) or run.get("model_kind") != kind or run.get("role") != role or run.get("complete") is not True:
        raise ValueError("Expected complete evaluation run with matching kind and role")
    for key in ("checkpoint_sha256", "config_sha256", "scores_sha256"):
        value = run.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"Missing or invalid {key}")
    if hashlib.sha256((folder / "scores.csv").read_bytes()).hexdigest() != run["scores_sha256"]:
        raise ValueError("Score CSV digest mismatch")
    records = run.get("records")
    if not isinstance(records, list) or not records or any(not isinstance(r, dict) for r in records):
        raise ValueError("Missing evaluation records")
    for r in records:
        if (type(r.get("label")) is not int or r["label"] not in (0, 1)
                or not isinstance(r.get("file_id"), str) or not r["file_id"].strip()
                or r["file_id"] != r["file_id"].strip()
                or not isinstance(r.get("sha256"), str) or len(r["sha256"]) != 64):
            raise ValueError("Missing record label/content digest")
        if any(not isinstance(r.get(key, ""), str) for key in LINKS):
            raise ValueError("Invalid linkage metadata")
    ids = _unique_ids(records, "file_id")
    _, rows = _rows(folder / "scores.csv", {"file_id", "synthetic_score", "status"})
    if set(_unique_ids(rows, "file_id")) != set(ids) or any(r["status"] != "scored" for r in rows):
        raise ValueError("Missing, failed or unscored evaluation files")
    scores = {r["file_id"].strip(): _score(r["synthetic_score"]) for r in rows}
    labels = [r["label"] for r in records]
    ordered = [scores[r["file_id"]] for r in records]
    _validate_values(labels, ordered)
    return run, labels, ordered


def _same_records(a, b):
    def signature(records):
        return sorted(tuple(r.get(key, "") for key in (*LINKS, "label")) for r in records)
    if signature(a) != signature(b):
        raise ValueError("Baseline and candidate were evaluated on different records")


def compare_runs(baseline_selection, candidate_selection, baseline_acceptance, candidate_acceptance):
    runs = [_read(folder, kind, role) for folder, kind, role in (
        (baseline_selection, "baseline", "selection"), (candidate_selection, "candidate", "selection"),
        (baseline_acceptance, "baseline", "acceptance"), (candidate_acceptance, "candidate", "acceptance"))]
    bs, cs, ba, ca = [x[0] for x in runs]
    for key in ("config_sha256", "aggregation"):
        if not bs.get(key) or any(r.get(key) != bs[key] for r in (cs, ba, ca)):
            raise ValueError("Incompatible evaluation preprocessing/configuration")
    if bs["checkpoint_sha256"] != ba["checkpoint_sha256"] or cs["checkpoint_sha256"] != ca["checkpoint_sha256"]:
        raise ValueError("Model checkpoint changed between selection and acceptance")
    _same_records(bs["records"], cs["records"])
    _same_records(ba["records"], ca["records"])
    _disjoint(bs["records"], ba["records"])
    fitted = ca.get("training_provenance")
    if not isinstance(fitted, dict) or not isinstance(fitted.get("train"), list) or not fitted["train"] or not isinstance(fitted.get("validation"), list):
        raise ValueError("Candidate training provenance is required")
    if fitted != cs.get("training_provenance"):
        raise ValueError("Candidate training provenance changed")
    _disjoint(fitted["train"], bs["records"])
    _disjoint(fitted["train"] + fitted["validation"], ba["records"])
    thresholds = {"baseline": select_threshold(runs[0][1], runs[0][2]),
                  "candidate": select_threshold(runs[1][1], runs[1][2])}
    baseline = summarize(runs[2][1], runs[2][2], thresholds["baseline"])
    candidate = summarize(runs[3][1], runs[3][2], thresholds["candidate"])
    checks = {
        "acceptance_sample_counts": min(candidate["genuine_count"], candidate["synthetic_count"]) >= GATES["min_each_class"],
        "selection_sample_counts": min(runs[1][1].count(0), runs[1][1].count(1)) >= GATES["min_each_class"],
        "candidate_recall": candidate["recall"] >= GATES["min_recall"],
        "candidate_false_positive_rate": candidate["false_positive_rate"] <= GATES["max_false_positive_rate"],
        "recall_improvement": candidate["recall"] - baseline["recall"] >= GATES["min_recall_gain"] - 1e-12,
        "ranking_no_regression": candidate["roc_auc"] >= baseline["roc_auc"],
    }
    return {"threshold_source": "selection_only", "thresholds": thresholds,
            "baseline": baseline, "candidate": candidate, "gates": GATES,
            "failed_gates": [name for name, passed in checks.items() if not passed],
            "eligible_for_review": all(checks.values()), "promoted": False,
            "model_hashes": {"baseline": bs["checkpoint_sha256"], "candidate": cs["checkpoint_sha256"]},
            "source_score_hashes": [r[0]["scores_sha256"] for r in runs],
            "note": "Provisional internal point-estimate gates, not sponsor accuracy. Review confidence intervals, attack/codec slices and serving latency before promotion."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline-selection", "candidate-selection", "baseline-acceptance", "candidate-acceptance"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Output already exists")
        result = compare_runs(args.baseline_selection, args.candidate_selection, args.baseline_acceptance, args.candidate_acceptance)
        with args.output.open("x") as f:
            f.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"eligible_for_review": result["eligible_for_review"], "promoted": False}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"ACCEPTANCE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
