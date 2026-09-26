"""Whole-file checkpoint evaluation and its leakage/identity gates."""

import csv
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import torch

from echotrace import checkpoint_eval
from echotrace.model import CONFIG_PATH, UPSTREAM_REVISION, WEIGHTS_SHA256


def _fixture(tmp_path, *, quiet=False):
    root = tmp_path / "data"
    root.mkdir()
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file_id", "path", "label", "group_id", "speaker_id", "source_id"])
        for i, label in enumerate((0, 1)):
            name = f"audio{i}.wav"
            t = np.arange(72_000, dtype=np.float32) / 16_000
            samples = np.zeros_like(t) if quiet else 0.3 * np.sin(2 * np.pi * (180 + 80 * i) * t)
            sf.write(root / name, samples, 16_000)
            writer.writerow([f"id{i}", name, label, f"group{i}", f"speaker{i}", f"source{i}"])
    return manifest, root


def _provenance(**changes):
    base = {"file_id": "training", "sha256": "a" * 64, "label": 0,
            "group_id": "g", "speaker_id": "s", "source_id": "src"}
    return {**base, **changes}


@pytest.mark.parametrize("role,split", [("selection", "train"), ("acceptance", "train"),
                                       ("acceptance", "validation")])
@pytest.mark.parametrize("key", ["file_id", "sha256", "group_id", "speaker_id", "source_id"])
def test_provenance_rejects_linked_files(role, split, key):
    candidate = _provenance(file_id="candidate", sha256="b" * 64,
                            group_id="other", speaker_id="other", source_id="other")
    candidate[key] = _provenance()[key]
    checkpoint = {"split_provenance": {"train": [], "validation": []}}
    checkpoint["split_provenance"][split].append(_provenance())
    with pytest.raises(ValueError, match="overlap|leak"):
        checkpoint_eval.validate_provenance([candidate], checkpoint, role=role)


def test_selection_allows_validation_link_but_acceptance_rejects():
    candidate = _provenance()
    checkpoint = {"split_provenance": {"train": [], "validation": [_provenance()]}}
    checkpoint_eval.validate_provenance([candidate], checkpoint, role="selection")
    with pytest.raises(ValueError, match="overlap|leak"):
        checkpoint_eval.validate_provenance([candidate], checkpoint, role="acceptance")


@pytest.mark.parametrize("split", [None, {}, {"train": [], "validation": [{"file_id": "x"}]}])
def test_malformed_provenance_rejected(split):
    with pytest.raises(ValueError, match="provenance"):
        checkpoint_eval.validate_provenance([_provenance()], {"split_provenance": split}, role="acceptance")


def test_checkpoint_hash_required_and_wrong_hash_rejected(tmp_path):
    path = tmp_path / "checkpoint.pt"
    torch.save({"model_state_dict": {}, "pretrained_sha256": WEIGHTS_SHA256,
                "model_config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
                "upstream_revision": UPSTREAM_REVISION,
                "split_provenance": {"train": [], "validation": []}}, path)
    with pytest.raises(ValueError, match="sha256|SHA"):
        checkpoint_eval.load_checkpoint(path, None)
    with pytest.raises(ValueError, match="sha256|SHA"):
        checkpoint_eval.load_checkpoint(path, "0" * 64)


def test_checkpoint_rejects_missing_config_hash(tmp_path):
    path = tmp_path / "checkpoint.pt"
    torch.save({"model_state_dict": {}, "pretrained_sha256": WEIGHTS_SHA256,
                "upstream_revision": UPSTREAM_REVISION,
                "split_provenance": {"train": [], "validation": []}}, path)
    with pytest.raises(ValueError, match="config"):
        checkpoint_eval.load_checkpoint(path, hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_baseline_whole_file_matches_pipeline_and_score_polarity(tmp_path):
    from echotrace.pipeline import analyze_file
    manifest, root = _fixture(tmp_path)
    expected = {f"id{i}": analyze_file(root / f"audio{i}.wav")["synthetic_score"] for i in (0, 1)}
    result = checkpoint_eval.run(manifest, root, tmp_path / "out", device="cpu", role="selection")
    assert result["completed"] is True
    assert result["model_kind"] == "baseline"
    assert result["aggregation"]["method"] == "mean_window_spoof_softmax"
    with (tmp_path / "out/scores.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    for row in rows:
        assert float(row["synthetic_score"]) == pytest.approx(expected[row["file_id"]], abs=1e-7)
    assert result["score_sha256"] == hashlib.sha256((tmp_path / "out/scores.csv").read_bytes()).hexdigest()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_quiet_files_are_explicit_and_run_incomplete(tmp_path):
    manifest, root = _fixture(tmp_path, quiet=True)
    result = checkpoint_eval.run(manifest, root, tmp_path / "out", device="cpu", role="selection")
    assert result["completed"] is False
    assert len(result["failures"]) == 2
    with (tmp_path / "out/scores.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["status"] for row in rows] == ["quiet", "quiet"]
    assert [row["synthetic_score"] for row in rows] == ["", ""]
    assert "metrics" not in result or result["metrics"] is None
