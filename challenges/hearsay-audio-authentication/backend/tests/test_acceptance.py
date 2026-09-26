import csv
import hashlib
import json

import pytest

from echotrace.acceptance import compare_runs, select_threshold, summarize


AGGREGATION = {"method": "mean_window_spoof_softmax", "window_samples": 64600,
               "hop_samples": 64600, "tail_policy": "end_anchored_overlap",
               "short_input_policy": "repeat_pad", "quality_gate": "shared_measure_audio"}


def write_run(root, kind, role, scores, *, prefix=None):
    folder = root / f"{kind}-{role}"
    folder.mkdir()
    prefix = prefix or role
    records = [{"file_id": f"{prefix}-{i}", "sha256": hashlib.sha256(f"{prefix}-{i}".encode()).hexdigest(),
                "label": i % 2, "group_id": f"{prefix}-{i}", "speaker_id": "", "source_id": ""}
               for i in range(len(scores))]
    with (folder / "scores.csv").open("w") as f:
        w = csv.writer(f)
        w.writerow(["file_id", "synthetic_score", "status"])
        w.writerows((r["file_id"], s, "scored") for r, s in zip(records, scores))
    data = {"role": role, "model_kind": kind, "checkpoint_sha256": ("a" if kind == "baseline" else "b") * 64,
            "config_sha256": "c" * 64, "complete": True, "aggregation": AGGREGATION,
            "records": records, "scores_sha256": hashlib.sha256((folder / "scores.csv").read_bytes()).hexdigest(),
            "training_provenance": {"train": [{"file_id": "fitted", "sha256": "d" * 64,
                "label": 0, "group_id": "fitted", "speaker_id": "", "source_id": ""}], "validation": []}
                if kind == "candidate" else None}
    (folder / "run.json").write_text(json.dumps(data))
    return folder


def four_runs(tmp_path, n=200):
    return [write_run(tmp_path, kind, role, ([.2, .1] if kind == "baseline" else [.1, .9]) * (n // 2))
            for role in ("selection", "acceptance") for kind in ("baseline", "candidate")]


def test_selection_uses_score_ties_without_exceeding_fpr():
    threshold = select_threshold([0, 0, 1, 1], [1, .2, 1, .9], max_fpr=.05)
    # Genuine and fake tied at1 cannot be separated. Reject-all threshold is explicit.
    assert threshold > 1
    assert summarize([0, 0, 1, 1], [1, .2, 1, .9], threshold)["false_positive_rate"] == 0


def test_candidate_meets_review_gate_without_automatic_promotion(tmp_path):
    paths = four_runs(tmp_path)
    report = compare_runs(*paths)
    assert report["eligible_for_review"] is True and report["promoted"] is False
    assert report["candidate"]["recall"] == 1
    assert report["candidate"]["false_positive_rate"] == 0
    assert report["candidate"]["recall_interval_95"][0] < 1
    assert report["threshold_source"] == "selection_only"


def test_acceptance_failures_do_not_reselect_threshold(tmp_path):
    paths = four_runs(tmp_path)
    first = compare_runs(*paths)
    folder = paths[3]
    rows = list(csv.DictReader((folder / "scores.csv").open()))
    for row in rows: row["synthetic_score"] = ".95"  # All genuine now trigger too.
    with (folder / "scores.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    data = json.loads((folder / "run.json").read_text())
    data["scores_sha256"] = hashlib.sha256((folder / "scores.csv").read_bytes()).hexdigest()
    (folder / "run.json").write_text(json.dumps(data))
    second = compare_runs(*paths)
    assert second["thresholds"] == first["thresholds"]
    assert second["eligible_for_review"] is False
    assert "candidate_false_positive_rate" in second["failed_gates"]


def test_tiny_set_cannot_pass_even_with_perfect_predictions(tmp_path):
    report = compare_runs(*four_runs(tmp_path, 24))
    assert report["eligible_for_review"] is False
    assert "acceptance_sample_counts" in report["failed_gates"]


@pytest.mark.parametrize("change", ["hash", "incomplete", "checkpoint", "overlap", "mismatched_labels", "fit_overlap"])
def test_invalid_experiment_refused(tmp_path, change):
    paths = four_runs(tmp_path)
    folder = paths[3]
    data = json.loads((folder / "run.json").read_text())
    if change == "hash": data["scores_sha256"] = "0" * 64
    elif change == "incomplete": data["complete"] = False
    elif change == "checkpoint": data["checkpoint_sha256"] = "9" * 64
    elif change == "overlap":
        # Linked speaker crossing selection/acceptance, even with different IDs and hashes.
        for p in paths:
            other = json.loads((p / "run.json").read_text())
            other["records"][0]["speaker_id"] = "same-person"
            (p / "run.json").write_text(json.dumps(other))
        data["records"][0]["speaker_id"] = "same-person"
    elif change == "mismatched_labels": data["records"][0]["label"] = 1
    elif change == "fit_overlap":
        data["training_provenance"]["train"][0]["sha256"] = data["records"][0]["sha256"]
    (folder / "run.json").write_text(json.dumps(data))
    with pytest.raises(ValueError): compare_runs(*paths)
