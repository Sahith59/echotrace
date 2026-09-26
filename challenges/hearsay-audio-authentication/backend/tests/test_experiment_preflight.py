"""CPU preparation must audit every frozen file before declaring GPU readiness."""

import csv
import json
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest

from echotrace import experiment_preflight
from echotrace.audio import AudioError


FIELDS = ["file_id", "path", "label", "speaker_id", "source_id",
          "attack_id", "codec", "partition"]


def staged_subset(tmp_path: Path) -> Path:
    stage = tmp_path / "staged"
    audio = stage / "audio"
    audio.mkdir(parents=True)
    for partition, count in (("train", 8), ("dev", 12)):
        rows = []
        for index in range(count):
            file_id = f"{partition}_{index:03d}"
            (audio / f"{file_id}.flac").write_bytes(file_id.encode())
            rows.append({"file_id": file_id, "path": f"{file_id}.flac",
                         "label": str(index % 2), "speaker_id": file_id,
                         "source_id": file_id, "attack_id": f"A{index % 2}",
                         "codec": "flac", "partition": partition})
        with (stage / f"{partition}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return stage


def decoded(path: Path):
    samples = np.full(64_600, .1, dtype=np.float32)
    return samples, {"duration_s": len(samples) / 16_000, "codec": "flac"}


@pytest.fixture(autouse=True)
def small_test_gate(monkeypatch):
    monkeypatch.setitem(experiment_preflight.GATES, "min_each_class", 1)


def test_ready_audits_all_selected_files_and_writes_config(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    monkeypatch.setattr(experiment_preflight, "decode_audio", decoded)
    output = tmp_path / "prepared"
    report = experiment_preflight.run(stage, output, train_limit=8, dev_limit=12,
                                      max_wall_seconds=60)
    assert report["ready"] is True
    assert report["audited_count"] == report["expected_count"] == 20
    assert report["failures"] == [] and report["quiet"] == []
    assert len(report["files"]) == 20
    assert report["splits"]["train"]["speaker_id_unique_count"] == 8
    assert report["splits"]["train"]["attack_id_counts"] == {"A0": 4, "A1": 4}
    assert report["splits"]["train"]["codec_counts"] == {"flac": 8}
    assert all(row["duration_s"] == 4.0375 and row["window_count"] == 1
               for row in report["files"])
    assert (output / "preflight.json").is_file()
    assert all((output / "manifests" / f"{split}.csv").is_file()
               for split in ("train", "selection", "acceptance"))
    config = json.loads((output / "training-config.json").read_text())
    assert config["dataset_root"] == str((stage / "audio").resolve())
    assert config["output_dir"] == str((output / "training").resolve())
    assert config["max_wall_seconds"] == 10800 and config["device"] == "cuda"
    assert config["batch_size"] == 8 and config["max_steps"] == 6000
    assert not (output / "training").exists()


def test_decode_failure_is_logged_and_blocks_config(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    def fail_one(path):
        if path.name == "train_000.flac":
            raise AudioError("corrupt stream")
        return decoded(path)
    monkeypatch.setattr(experiment_preflight, "decode_audio", fail_one)
    output = tmp_path / "prepared"
    report = experiment_preflight.run(stage, output, train_limit=8, dev_limit=12,
                                      max_wall_seconds=60)
    assert report["ready"] is False
    assert any(row["file_id"] == "train_000" and "corrupt stream" in row["reason"]
               for row in report["failures"])
    assert not (output / "training-config.json").exists()
    assert json.loads((output / "preflight.json").read_text())["ready"] is False


def test_quiet_audio_is_logged_and_blocks_config(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    def quiet_one(path):
        if path.name == "dev_000.flac":
            return np.zeros(64_600, dtype=np.float32), {"duration_s": 4.0375}
        return decoded(path)
    monkeypatch.setattr(experiment_preflight, "decode_audio", quiet_one)
    output = tmp_path / "prepared"
    report = experiment_preflight.run(stage, output, train_limit=8, dev_limit=12,
                                      max_wall_seconds=60)
    assert report["ready"] is False
    assert any(row["file_id"] == "dev_000" for row in report["quiet"])
    assert not (output / "training-config.json").exists()


def test_class_minimum_blocks_readiness_without_decoding(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    monkeypatch.setitem(experiment_preflight.GATES, "min_each_class", 100)
    calls = []
    monkeypatch.setattr(experiment_preflight, "decode_audio",
                        lambda path: (calls.append(path), decoded(path))[1])
    output = tmp_path / "prepared"
    report = experiment_preflight.run(stage, output, train_limit=8, dev_limit=12,
                                      max_wall_seconds=60)
    assert report["ready"] is False
    assert "100" in report["reason"]
    assert calls == []
    assert not (output / "training-config.json").exists()


def test_cli_returns_nonzero_when_not_ready(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    monkeypatch.setitem(experiment_preflight.GATES, "min_each_class", 100)
    output = tmp_path / "prepared"
    code = experiment_preflight.main([
        "--staged-root", str(stage), "--output-dir", str(output),
        "--train-limit", "8", "--dev-limit", "12", "--max-wall-seconds", "60",
    ])
    assert code == 2
    assert json.loads((output / "preflight.json").read_text())["ready"] is False
    assert not (output / "training-config.json").exists()


def test_expired_wall_cap_blocks_config(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    monkeypatch.setattr(experiment_preflight, "decode_audio", decoded)
    ticks = iter([0.0, 0.1, 61.0])
    monkeypatch.setattr(experiment_preflight.time, "monotonic", lambda: next(ticks, 61.0))
    output = tmp_path / "prepared"
    report = experiment_preflight.run(stage, output, train_limit=8, dev_limit=12,
                                      max_wall_seconds=60)
    assert report["ready"] is False
    assert "wall" in report["reason"].lower()
    assert not (output / "training-config.json").exists()


def test_wall_expiry_at_completion_cannot_leave_ready_true(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    monkeypatch.setattr(experiment_preflight, "decode_audio", decoded)
    @contextmanager
    def expire_after_audit(_seconds):
        yield
        raise experiment_preflight._WallExpired("CPU preflight wall cap expired")
    monkeypatch.setattr(experiment_preflight, "_wall_alarm", expire_after_audit)
    output = tmp_path / "prepared"
    report = experiment_preflight.run(stage, output, train_limit=8, dev_limit=12,
                                      max_wall_seconds=60)
    assert report["ready"] is False
    assert not (output / "training-config.json").exists()


def test_config_write_failure_cannot_publish_ready_report(tmp_path, monkeypatch):
    stage = staged_subset(tmp_path)
    monkeypatch.setattr(experiment_preflight, "decode_audio", decoded)
    original = Path.write_text
    def fail_config_write(path, *args, **kwargs):
        if path.name == "training-config.json":
            raise OSError("disk full")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail_config_write)
    output = tmp_path / "prepared"
    report = experiment_preflight.run(stage, output, train_limit=8, dev_limit=12,
                                      max_wall_seconds=60)
    assert report["ready"] is False
    assert "disk full" in report["reason"]
    assert json.loads((output / "preflight.json").read_text())["ready"] is False


@pytest.mark.parametrize("value", [0, -1, 3601, 1.5, True])
def test_wall_limit_validation(tmp_path, value):
    with pytest.raises(ValueError, match="wall"):
        experiment_preflight.run(tmp_path, tmp_path / "prepared", max_wall_seconds=value)
