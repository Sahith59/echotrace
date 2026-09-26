import pytest

from echotrace.ara_benchmark import select_rows, summarize


def test_fixed_balanced_selection_is_stable_and_disjoint():
    rows = [
        {"id": f"sample_{i:03d}", "label": str(i % 2),
         "file_name": f"data/track-2_development_test/shard.tar::sample_{i:03d}.flac"}
        for i in range(40)
    ]
    selected = select_rows(rows, "data/track-2_development_test/shard.tar", 8, "echotrace-2026")
    assert len(selected) == 16
    assert [row["label"] for row in selected].count("0") == 8
    assert [row["label"] for row in selected].count("1") == 8
    assert {row["id"] for row in selected} == {
        row["id"] for row in select_rows(reversed(rows), "data/track-2_development_test/shard.tar", 8, "echotrace-2026")
    }
    with pytest.raises(ValueError, match="Duplicate"):
        select_rows(rows + [rows[0]], "data/track-2_development_test/shard.tar", 8, "echotrace-2026")


def test_summary_uses_zero_as_fake_and_retains_failures():
    scored = [
        {"label": "0", "score": 0.9, "error": None},
        {"label": "0", "score": 0.2, "error": None},
        {"label": "1", "score": 0.6, "error": None},
        {"label": "1", "score": 0.1, "error": None},
        {"label": "0", "score": None, "error": "bad_audio"},
    ]
    report = summarize(scored, threshold=0.5)
    assert report["coverage"] == {"selected": 5, "scored": 4, "failed": 1}
    assert report["confusion"] == {"tp": 1, "fn": 1, "fp": 1, "tn": 1}
    assert report["recall"] == 0.5
    assert report["fpr"] == 0.5
    assert report["auroc"] == 0.75
