"""Generated fixtures only; these tests say nothing about sponsor performance."""

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from echotrace.evaluation import (  # noqa: E402
    audit_manifest,
    evaluate_predictions,
    export_submission,
    grouped_split,
    load_manifest,
)


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def fixture_manifest(tmp_path):
    root = tmp_path / "audio"
    root.mkdir()
    entries = [
        ("real-a", "real-a.wav", "0", "speaker-a", b"genuine A"),
        ("real-a-copy", "real-a-copy.wav", "0", "", b"genuine A"),
        ("real-b", "real-b.wav", "0", "speaker-b", b"genuine B"),
        ("real-c", "real-c.wav", "0", "speaker-c", b"genuine C"),
        ("fake-a", "fake-a.wav", "1", "source-a", b"synthetic A"),
        ("fake-b", "fake-b.wav", "1", "source-b", b"synthetic B"),
        ("fake-c", "fake-c.wav", "1", "source-c", b"synthetic C"),
    ]
    for _, name, _, _, content in entries:
        (root / name).write_bytes(content)
    manifest = tmp_path / "manifest.csv"
    write_csv(manifest, ["file_id", "path", "label", "group_id"],
              [item[:4] for item in entries])
    return manifest, root


def test_manifest_audit_and_grouped_split_keep_duplicate_bytes_together(tmp_path):
    manifest, root = fixture_manifest(tmp_path)
    records = load_manifest(manifest, root)
    assert audit_manifest(records)["duplicate_content_groups"] == 1
    one = grouped_split(records, validation_fraction=0.4, random_state=7)
    assert one == grouped_split(records, validation_fraction=0.4, random_state=7)
    assert ("real-a" in one["train_ids"]) == ("real-a-copy" in one["train_ids"])
    by_id = {record["file_id"]: record for record in records}
    for ids in one.values():
        assert {by_id[file_id]["label"] for file_id in ids} == {0, 1}


def test_grouped_split_extends_small_target_until_both_classes_present():
    records = [{"file_id": f"item-{i}", "label": i // 2,
                "group_id": f"group-{i}", "sha256": f"hash-{i}"}
               for i in range(4)]
    split = grouped_split(records, validation_fraction=0.2, random_state=7)
    for ids in split.values():
        assert len(ids) == 2
        assert {records[int(file_id[-1])]["label"] for file_id in ids} == {0, 1}


def test_manifest_rejects_duplicate_id_conflicting_hash_labels_and_traversal(tmp_path):
    manifest, root = fixture_manifest(tmp_path)
    write_csv(manifest, ["file_id", "path", "label"],
              [("same", "real-a.wav", "0"), ("same", "fake-a.wav", "1")])
    with pytest.raises(ValueError, match="Duplicate file_id"):
        load_manifest(manifest, root)
    write_csv(manifest, ["file_id", "path", "label"],
              [("a", "real-a.wav", "0"), ("b", "real-a-copy.wav", "1")])
    with pytest.raises(ValueError, match="Conflicting labels"):
        load_manifest(manifest, root)
    write_csv(manifest, ["file_id", "path", "label"], [("a", "../manifest.csv", "0")])
    with pytest.raises(ValueError, match="escapes dataset root"):
        load_manifest(manifest, root)


def test_evaluation_reports_metrics_and_rejects_incomplete_or_nonfinite_scores(tmp_path):
    manifest, root = fixture_manifest(tmp_path)
    records = load_manifest(manifest, root)
    predictions = tmp_path / "predictions.csv"
    scores = [(record["file_id"], "0.9" if record["label"] else "0.1") for record in records]
    write_csv(predictions, ["file_id", "synthetic_score"], scores)
    result = evaluate_predictions(records, predictions, threshold=0.5)
    assert result["sample_count"] == 7
    assert result["confusion"] == {"tn": 4, "fp": 0, "fn": 0, "tp": 3}
    assert result["roc_auc"] == result["pr_auc"] == 1.0
    assert result["brier"] == pytest.approx(0.01)
    write_csv(predictions, ["file_id", "synthetic_score"], scores[:-1])
    with pytest.raises(ValueError, match="coverage mismatch"):
        evaluate_predictions(records, predictions)
    write_csv(predictions, ["file_id", "synthetic_score"], scores[:-1] + [(scores[-1][0], "nan")])
    with pytest.raises(ValueError, match="finite"):
        evaluate_predictions(records, predictions)


def test_submission_preserves_template_order_headers_and_scale(tmp_path):
    predictions = tmp_path / "predictions.csv"
    expected = tmp_path / "expected.csv"
    config = tmp_path / "config.json"
    output = tmp_path / "submission.csv"
    write_csv(predictions, ["file_id", "synthetic_score"], [("b", "0.75"), ("a", "0.2")])
    write_csv(expected, ["clip", "other"], [("a", "x"), ("b", "y")])
    settings = {"expected_id_column": "clip", "output_id_column": "id",
                "output_score_column": "probability_synthetic", "score_scale": "0-100",
                "score_direction": "synthetic_high", "columns": ["id", "probability_synthetic"],
                "official_schema_confirmed": False}
    config.write_text(json.dumps(settings))
    with pytest.raises(ValueError, match="not been confirmed"):
        export_submission(predictions, expected, config, output, require_official=True)
    assert not output.exists()
    summary = export_submission(predictions, expected, config, output)
    assert summary["official_schema_confirmed"] is False
    assert output.read_text() == "id,probability_synthetic\na,20\nb,75\n"
    settings["official_schema_confirmed"] = True
    config.write_text(json.dumps(settings))
    assert export_submission(predictions, expected, config, output, require_official=True)["row_count"] == 2
    write_csv(predictions, ["file_id", "synthetic_score"], [("a", "0.2"), ("a", "0.3")])
    with pytest.raises(ValueError, match="Duplicate file_id"):
        export_submission(predictions, expected, config, output)
