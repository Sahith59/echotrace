"""Whole-file checkpoint evaluation and its leakage/identity gates."""

import csv
import hashlib
import json
import shutil
import time
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
            amplitude = 0.00001 if quiet else 0.3
            samples = amplitude * np.sin(2 * np.pi * (180 + 80 * i) * t)
            sf.write(root / name, samples, 16_000)
            writer.writerow([f"id{i}", name, label, f"group{i}", f"speaker{i}", f"source{i}"])
    return manifest, root


def _provenance(**changes):
    base = {"file_id": "training", "sha256": "a" * 64, "label": 0,
            "group_id": "g", "speaker_id": "s", "source_id": "src"}
    return {**base, **changes}


def _valid_splits():
    return {"train": [_provenance(file_id="t0", sha256="a" * 64, label=0,
                                   group_id="tg0", speaker_id="ts0", source_id="to0"),
                      _provenance(file_id="t1", sha256="b" * 64, label=1,
                                  group_id="tg1", speaker_id="ts1", source_id="to1")],
            "validation": [_provenance(file_id="v0", sha256="c" * 64, label=0,
                                        group_id="vg0", speaker_id="vs0", source_id="vo0"),
                           _provenance(file_id="v1", sha256="d" * 64, label=1,
                                       group_id="vg1", speaker_id="vs1", source_id="vo1")]}


@pytest.mark.parametrize("mutation", [
    lambda splits: splits["train"].clear(),
    lambda splits: splits["validation"].pop(),
    lambda splits: splits["train"][1].update(sha256="not-a-hash"),
    lambda splits: splits["train"][1].update(file_id="t0"),
    lambda splits: splits["validation"][0].update(group_id="tg0"),
    lambda splits: splits["validation"][0].update(sha256="a" * 64),
])
def test_checkpoint_split_provenance_rejects_invalid_training_splits(mutation):
    splits = _valid_splits()
    mutation(splits)
    with pytest.raises(ValueError, match="provenance"):
        checkpoint_eval.validate_provenance([], {"split_provenance": splits}, role="selection")


def test_cli_accepts_max_wall_seconds_alias(tmp_path, monkeypatch):
    received = {}

    def fake_run(*args, **kwargs):
        received.update(kwargs)
        return {"complete": True}

    monkeypatch.setattr(checkpoint_eval, "run", fake_run)
    assert checkpoint_eval.main([str(tmp_path / "manifest.csv"), "--dataset-root", str(tmp_path),
                                 "--output", str(tmp_path / "out"), "--device", "cpu",
                                 "--max-wall-seconds", "42"]) == 0
    assert received["max_seconds"] == 42


@pytest.mark.parametrize("role", ["selection", "acceptance"])
def test_candidate_evaluation_rejects_pilot_hash(tmp_path, monkeypatch, role):
    manifest, root = _fixture(tmp_path)
    pilot_digest = hashlib.sha256((root / "audio0.wav").read_bytes()).hexdigest()
    monkeypatch.setattr(checkpoint_eval, "load_checkpoint", lambda *args: {"split_provenance": _valid_splits()})
    monkeypatch.setattr(checkpoint_eval, "_demo_hashes", lambda: {pilot_digest})
    with pytest.raises(ValueError, match="demonstration"):
        checkpoint_eval.run(manifest, root, tmp_path / "out", device="cpu", role=role,
                            checkpoint=tmp_path / "candidate.pt", checkpoint_sha256="e" * 64)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("role,split", [("selection", "train"), ("acceptance", "train"),
                                       ("acceptance", "validation")])
@pytest.mark.parametrize("key", ["file_id", "sha256", "group_id", "speaker_id", "source_id"])
def test_provenance_rejects_linked_files(role, split, key):
    candidate = _provenance(file_id="candidate", sha256="b" * 64,
                            group_id="other", speaker_id="other", source_id="other")
    checkpoint = {"split_provenance": _valid_splits()}
    candidate[key] = checkpoint["split_provenance"][split][0][key]
    with pytest.raises(ValueError, match="overlap|leak"):
        checkpoint_eval.validate_provenance([candidate], checkpoint, role=role)


def test_selection_allows_validation_link_but_acceptance_rejects():
    checkpoint = {"split_provenance": _valid_splits()}
    candidate = checkpoint["split_provenance"]["validation"][0].copy()
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
                "split_provenance": _valid_splits()}, path)
    with pytest.raises(ValueError, match="sha256|SHA"):
        checkpoint_eval.load_checkpoint(path, None)
    with pytest.raises(ValueError, match="sha256|SHA"):
        checkpoint_eval.load_checkpoint(path, "0" * 64)


def test_checkpoint_rejects_missing_config_hash(tmp_path):
    path = tmp_path / "checkpoint.pt"
    torch.save({"model_state_dict": {}, "pretrained_sha256": WEIGHTS_SHA256,
                "upstream_revision": UPSTREAM_REVISION,
                "split_provenance": _valid_splits()}, path)
    with pytest.raises(ValueError, match="config"):
        checkpoint_eval.load_checkpoint(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_window_score_uses_spoof_class_zero_and_tail_mean():
    class Stub:
        def __call__(self, x):
            sign = float(x[0, 0])
            return None, torch.tensor([[5.0 * sign, -5.0 * sign]])

    samples = np.concatenate((np.ones(64_600, dtype=np.float32),
                              -np.ones(64_600, dtype=np.float32)))
    score = checkpoint_eval._score_samples(samples, Stub(), "cpu", time.monotonic() + 10)
    assert score == pytest.approx(0.5, abs=1e-6)
    assert checkpoint_eval._score_samples(np.ones(64_600, dtype=np.float32), Stub(),
                                          "cpu", time.monotonic() + 10) > 0.99


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_offline_aasist_baseline_remains_separate_from_promoted_primary(tmp_path):
    from echotrace.pipeline import analyze_file
    manifest, root = _fixture(tmp_path)
    primary = {f"id{i}": analyze_file(root / f"audio{i}.wav")["synthetic_score"] for i in (0, 1)}
    result = checkpoint_eval.run(manifest, root, tmp_path / "out", device="cpu", role="selection")
    assert result["complete"] is True
    assert result["model_kind"] == "baseline"
    assert result["checkpoint_sha256"] == WEIGHTS_SHA256
    assert result["aggregation"]["method"] == "mean_window_spoof_softmax"
    with (tmp_path / "out/scores.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert all(0 <= float(row["synthetic_score"]) <= 1 for row in rows)
    assert any(float(row["synthetic_score"]) != pytest.approx(primary[row["file_id"]], abs=1e-7)
               for row in rows)
    assert result["scores_sha256"] == hashlib.sha256((tmp_path / "out/scores.csv").read_bytes()).hexdigest()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_quiet_files_are_explicit_and_run_incomplete(tmp_path):
    manifest, root = _fixture(tmp_path, quiet=True)
    result = checkpoint_eval.run(manifest, root, tmp_path / "out", device="cpu", role="selection")
    assert result["complete"] is False
    assert len(result["failures"]) == 2
    with (tmp_path / "out/scores.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["status"] for row in rows] == ["quiet", "quiet"]
    assert [row["synthetic_score"] for row in rows] == ["", ""]
    assert "metrics" not in result or result["metrics"] is None


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_decode_failure_is_kept_in_ledger(tmp_path):
    manifest, root = _fixture(tmp_path)
    (root / "audio1.wav").write_text("not audio")
    result = checkpoint_eval.run(manifest, root, tmp_path / "out", device="cpu", role="selection")
    assert result["complete"] is False
    assert result["failure_count"] == 1
    with (tmp_path / "out/scores.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[1]["status"] == "failed"
    assert rows[1]["synthetic_score"] == ""
