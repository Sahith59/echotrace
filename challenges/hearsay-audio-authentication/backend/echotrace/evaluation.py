"""Dataset audit, leak-aware validation, metrics, and strict CSV export.

Labels are explicit: 0 = genuine, 1 = synthetic. All internal scores are
finite numbers in [0, 1] with larger values meaning more likely synthetic.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, roc_auc_score


def _rows(path: Path, required: set[str]) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Missing or duplicate CSV headers: {path}")
        headers = list(reader.fieldnames)
        if not required.issubset(headers):
            raise ValueError(f"Missing columns {sorted(required - set(headers))}: {path}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"Malformed CSV row: {path}")
    return headers, rows


def _unique_ids(rows: list[dict[str, str]], column: str) -> list[str]:
    ids = [row[column].strip() for row in rows]
    if any(not item for item in ids):
        raise ValueError("Blank file_id")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate file_id")
    return ids


def _score(value: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid synthetic_score: {value!r}") from exc
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError(f"synthetic_score must be finite and in [0, 1]: {value!r}")
    return score


def load_manifest(manifest_csv: Path, dataset_root: Path, *, require_labels: bool = True) -> list[dict]:
    """Validate paths, IDs, labels, and file contents; return ordered records.

    ``path`` must be relative to dataset_root. SHA-256 is calculated from the
    original bytes, so exact duplicate content can be kept in one split.
    """
    _, rows = _rows(Path(manifest_csv), {"file_id", "path"})
    if not rows:
        raise ValueError("Empty manifest")
    _unique_ids(rows, "file_id")
    if require_labels and any("label" not in row for row in rows):
        raise ValueError("Manifest requires label column")
    root = Path(dataset_root).resolve(strict=True)
    records = []
    hash_labels: dict[str, int] = {}
    for row in rows:
        rel = Path(row["path"])
        if not row["path"].strip() or rel.is_absolute():
            raise ValueError(f"Path must be relative: {row['path']!r}")
        source = (root / rel).resolve(strict=True)
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError(f"Path escapes dataset root or is not a file: {rel}")
        label_text = row.get("label", "").strip()
        if label_text not in {"0", "1", ""} or (require_labels and not label_text):
            raise ValueError(f"Label must be 0=genuine or 1=synthetic: {row['file_id']}")
        label = int(label_text) if label_text else None
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        sha256 = digest.hexdigest()
        if label is not None and sha256 in hash_labels and hash_labels[sha256] != label:
            raise ValueError(f"Conflicting labels for identical content: {row['file_id']}")
        if label is not None:
            hash_labels[sha256] = label
        records.append({"file_id": row["file_id"].strip(), "path": str(source),
                        "label": label, "group_id": row.get("group_id", "").strip(),
                        "speaker_id": row.get("speaker_id", "").strip(),
                        "source_id": row.get("source_id", "").strip(),
                        "sha256": sha256})
    return records


def audit_manifest(records: list[dict]) -> dict:
    """Summarize a validated manifest and exact-content duplicates."""
    hashes = Counter(record["sha256"] for record in records)
    return {"sample_count": len(records),
            "label_counts": dict(sorted(Counter(str(record["label"]) for record in records).items())),
            "duplicate_content_groups": sum(count > 1 for count in hashes.values()),
            "duplicate_content_files": sum(count for count in hashes.values() if count > 1),
            "missing_group_count": sum(not record["group_id"] for record in records)}


def grouped_split(records: list[dict], *, validation_fraction: float = 0.2,
                  random_state: int = 42) -> dict[str, list[str]]:
    """Deterministic group split; linked group IDs and hashes never cross splits."""
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    if any(record["label"] not in (0, 1) for record in records):
        raise ValueError("Grouped split requires labels 0 and 1")
    if len(records) < 4:
        raise ValueError("At least four records are required for a two-class split")
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    by_group: dict[tuple[str, str], int] = {}
    by_hash: dict[str, int] = {}
    for i, record in enumerate(records):
        # Each metadata column is a separate namespace. Links are transitive:
        # same speaker OR source OR explicit group means one split component.
        for column in ("group_id", "speaker_id", "source_id"):
            value = record.get(column, "").strip()
            if value:
                key = (column, value)
                if key in by_group:
                    union(i, by_group[key])
                by_group[key] = i
        digest = record["sha256"]
        if digest in by_hash:
            union(i, by_hash[digest])
        by_hash[digest] = i
    components: dict[int, list[int]] = defaultdict(list)
    for i in range(len(records)):
        components[find(i)].append(i)
    groups = sorted(components.values(),
                    key=lambda members: tuple(sorted(records[i]["file_id"] for i in members)))
    if len(groups) < 2:
        raise ValueError("No independent groups available for validation")

    # A fixed RNG and bounded candidate search favor a class-valid split near
    # the requested size. Failure is explicit rather than leaking a group.
    import random
    rng = random.Random(random_state)
    best = None
    for _ in range(1000):
        shuffled = groups[:]
        rng.shuffle(shuffled)
        target = max(1, round(len(records) * validation_fraction))
        selected = []
        count = 0
        for group in shuffled:
            if count >= target and {records[i]["label"] for i in selected} == {0, 1}:
                break
            selected.extend(group)
            count += len(group)
        valid = set(selected)
        train = set(range(len(records))) - valid
        if {records[i]["label"] for i in valid} != {0, 1} or {records[i]["label"] for i in train} != {0, 1}:
            continue
        distance = abs(len(valid) / len(records) - validation_fraction)
        if best is None or distance < best[0]:
            best = (distance, valid)
            if distance == 0:
                break
    if best is None:
        raise ValueError("Cannot make independent train/validation splits containing both classes")
    valid = best[1]
    return {"train_ids": [r["file_id"] for i, r in enumerate(records) if i not in valid],
            "validation_ids": [r["file_id"] for i, r in enumerate(records) if i in valid]}


def evaluate_predictions(records: list[dict], predictions_csv: Path, *, threshold: float = 0.5) -> dict:
    """Evaluate one complete labeled set; threshold must be chosen beforehand."""
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and in [0, 1]")
    if any(r["label"] not in (0, 1) for r in records):
        raise ValueError("Evaluation requires binary labels")
    if len({r["file_id"] for r in records}) != len(records):
        raise ValueError("Duplicate IDs in records")
    _, rows = _rows(Path(predictions_csv), {"file_id", "synthetic_score"})
    ids = _unique_ids(rows, "file_id")
    expected = {record["file_id"] for record in records}
    if set(ids) != expected:
        raise ValueError(f"Prediction coverage mismatch: missing={sorted(expected-set(ids))}, extra={sorted(set(ids)-expected)}")
    scored = {row["file_id"].strip(): _score(row["synthetic_score"]) for row in rows}
    labels = [record["label"] for record in records]
    if set(labels) != {0, 1}:
        raise ValueError("ROC AUC requires both classes")
    scores = [scored[record["file_id"]] for record in records]
    predicted = [int(score >= threshold) for score in scores]
    tn, fp, fn, tp = (int(value) for value in confusion_matrix(labels, predicted, labels=[0, 1]).ravel())
    return {"sample_count": len(records), "genuine_count": labels.count(0),
            "synthetic_count": labels.count(1), "threshold": threshold,
            "roc_auc": float(roc_auc_score(labels, scores)),
            "pr_auc": float(average_precision_score(labels, scores)),
            "pr_auc_definition": "average_precision", "brier": float(brier_score_loss(labels, scores)),
            "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "specificity": tn / (tn + fp) if tn + fp else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}


def export_submission(predictions_csv: Path, expected_ids_csv: Path, config_json: Path,
                      output_csv: Path, *, require_official: bool = False) -> dict:
    """Export in exact expected-ID order after full schema/score preflight.

    The example config is an analyst format, not a claimed sponsor template.
    Set official_schema_confirmed in a reviewed config for require_official=True.
    """
    config = json.loads(Path(config_json).read_text(encoding="utf-8"))
    required = {"expected_id_column", "output_id_column", "output_score_column", "score_scale",
                "score_direction", "columns", "official_schema_confirmed"}
    if set(config) != required:
        raise ValueError(f"Config keys must be exactly {sorted(required)}")
    if require_official and config["official_schema_confirmed"] is not True:
        raise ValueError("Official sponsor schema has not been confirmed")
    if config["score_direction"] != "synthetic_high" or config["score_scale"] not in ("0-1", "0-100"):
        raise ValueError("Unsupported score direction or scale")
    columns = config["columns"]
    if columns != [config["output_id_column"], config["output_score_column"]] or len(set(columns)) != 2:
        raise ValueError("columns must list the ID and score headers exactly once, in output order")
    _, expected_rows = _rows(Path(expected_ids_csv), {config["expected_id_column"]})
    expected = _unique_ids(expected_rows, config["expected_id_column"])
    if not expected:
        raise ValueError("Expected ID list is empty")
    _, prediction_rows = _rows(Path(predictions_csv), {"file_id", "synthetic_score"})
    ids = _unique_ids(prediction_rows, "file_id")
    if set(ids) != set(expected):
        raise ValueError(f"Prediction coverage mismatch: missing={sorted(set(expected)-set(ids))}, extra={sorted(set(ids)-set(expected))}")
    scored = {row["file_id"].strip(): _score(row["synthetic_score"]) for row in prediction_rows}
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for file_id in expected:
        score = scored[file_id] * (100 if config["score_scale"] == "0-100" else 1)
        writer.writerow({config["output_id_column"]: file_id,
                         config["output_score_column"]: format(score, ".12g")})
    output.write_text(buffer.getvalue(), encoding="utf-8")
    return {"row_count": len(expected), "columns": columns,
            "score_scale": config["score_scale"],
            "official_schema_confirmed": config["official_schema_confirmed"],
            "output_path": str(output)}
