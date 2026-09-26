from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from echotrace.audio import AudioError, decode_audio
from echotrace.model import WINDOW_SAMPLES, model_status, score_window
from echotrace.pipeline import analyze_file


def make_wave(path: Path, seconds: float, silent: bool = False) -> None:
    sample_rate = 16_000
    n = round(seconds * sample_rate)
    samples = np.zeros(n, dtype=np.int16) if silent else (
        0.24 * np.sin(np.arange(n) * 2 * math.pi * 231 / sample_rate) * 32767
    ).astype(np.int16)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(samples.tobytes())


@pytest.mark.parametrize("extension", ["wav", "mp3", "m4a"])
def test_real_decoding_and_analysis(tmp_path: Path, extension: str) -> None:
    source = tmp_path / "source.wav"
    make_wave(source, 0.6)
    target = tmp_path / f"voice.{extension}"
    if extension == "wav":
        target = source
    else:
        codec = "libmp3lame" if extension == "mp3" else "aac"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-c:a", codec, str(target)], check=True)
    stages: list[str] = []
    result = analyze_file(target, stages.append)
    assert result["input"]["analysis_sample_rate"] == 16000
    assert result["input"]["sha256"]
    assert result["synthetic_score"] is not None
    assert 0 <= result["synthetic_score"] <= 1
    assert result["score_kind"] == "uncalibrated"
    assert len(result["intervals"]) == 1
    assert result["intervals"][0]["end_s"] == pytest.approx(result["input"]["duration_s"], abs=.001)
    assert 0 < len(result["waveform"]) <= 256
    assert {item["kind"] for item in result["evidence"]} == {"quality", "spectral", "temporal"}
    assert stages == ["decoding", "quality", "detector", "aggregation", "completed"]
    json.dumps(result, allow_nan=False)


def test_silent_audio_has_no_synthetic_score(tmp_path: Path) -> None:
    source = tmp_path / "silent.wav"
    make_wave(source, 1, silent=True)
    result = analyze_file(source)
    assert result["synthetic_score"] is None
    assert result["intervals"] == []
    assert any("too quiet" in item for item in result["limitations"])


def test_full_recording_coverage(tmp_path: Path) -> None:
    source = tmp_path / "long.wav"
    make_wave(source, 8.7)
    result = analyze_file(source)
    intervals = result["intervals"]
    assert len(intervals) == 3
    assert intervals[0]["start_s"] == 0
    assert intervals[-1]["end_s"] == pytest.approx(8.7, abs=.001)
    assert all(a["end_s"] >= b["start_s"] for a, b in zip(intervals, intervals[1:]))
    assert result["synthetic_score"] == pytest.approx(np.mean([x["score"] for x in intervals]), abs=.000002)


def test_decode_rejects_invalid_and_over_limit(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.wav"
    invalid.write_bytes(b"not audio")
    with pytest.raises(AudioError):
        decode_audio(invalid)
    long_audio = tmp_path / "long.wav"
    make_wave(long_audio, 121, silent=True)
    with pytest.raises(AudioError, match="120-second"):
        decode_audio(long_audio)


def test_checkpoint_and_spoof_index() -> None:
    assert model_status()["available"]
    waveform = (np.sin(np.arange(WINDOW_SAMPLES) * 2 * math.pi * 220 / 16_000) * .1).astype(np.float32)
    output = score_window(waveform)
    a, b = output["logits"]
    assert output["score"] == pytest.approx(1 / (1 + math.exp(b - a)), rel=1e-5)
