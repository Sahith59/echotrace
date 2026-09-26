"""Read-only error audit for existing labeled score CSVs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .evaluation import _rows, _score, _unique_ids, evaluate_predictions


def _generator(path: str, label: int) -> str | None:
    if label == 0:
        return None
    parts = Path(path).parts
    if len(parts) < 4 or parts[:2] != ("fake", "en") or not parts[2]:
        return "unknown"
    return parts[2]


def audit_predictions(manifest_csv: Path, predictions_csv: Path, *, threshold: float = 0.5) -> dict:
    """Join complete CSVs by ID, report mistakes and generator sample counts.

    Audio is never opened and scores are never recomputed. The generator name
    comes from the manifest's ``fake/en/<generator>/...`` path convention.
    """
    _, manifest = _rows(Path(manifest_csv), {"file_id", "path", "label"})
    if not manifest:
        raise ValueError("Empty manifest")
    _unique_ids(manifest, "file_id")
    _, score_rows = _rows(Path(predictions_csv), {"file_id", "synthetic_score"})
    _unique_ids(score_rows, "file_id")
    scores = {row["file_id"].strip(): _score(row["synthetic_score"]) for row in score_rows}
    expected = {row["file_id"].strip() for row in manifest}
    if set(scores) != expected:
        raise ValueError(f"Prediction coverage mismatch: missing={sorted(expected-set(scores))}, extra={sorted(set(scores)-expected)}")
    records = []
    files = []
    for row in manifest:
        file_id = row["file_id"].strip()
        label_text = row["label"].strip()
        if label_text not in {"0", "1"}:
            raise ValueError(f"Label must be 0=genuine or 1=synthetic: {file_id}")
        label = int(label_text)
        score = scores[file_id]
        predicted = int(score >= threshold)
        records.append({"file_id": file_id, "label": label})
        files.append({"file_id": file_id, "path": row["path"], "label": label,
                      "generator": _generator(row["path"], label),
                      "synthetic_score": score, "predicted_label": predicted,
                      "error": predicted != label,
                      "outcome": ("tp" if label else "fp") if predicted else ("fn" if label else "tn")})
    metrics = evaluate_predictions(records, Path(predictions_csv), threshold=threshold)
    generator_counts = Counter(item["generator"] for item in files if item["generator"] is not None)
    generators = [{"generator": name, "count": count,
                   "missed": sum(item["outcome"] == "fn" for item in files if item["generator"] == name),
                   "detected": sum(item["outcome"] == "tp" for item in files if item["generator"] == name)}
                  for name, count in sorted(generator_counts.items())]
    return {"manifest": str(manifest_csv), "scores": str(predictions_csv),
            "score_direction": "synthetic_high", "threshold": threshold,
            "metrics": metrics, "generators": generators, "files": files}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("scores", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path, help="Write JSON here; otherwise print it")
    args = parser.parse_args(argv)
    try:
        if args.output and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError(f"Output already exists: {args.output}")
        result = audit_predictions(args.manifest, args.scores, threshold=args.threshold)
        rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            # Exclusive creation closes the check/write race and rejects
            # symlinks, hardlinks, input aliases, and prior reports.
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(rendered)
        else:
            print(rendered, end="")
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
