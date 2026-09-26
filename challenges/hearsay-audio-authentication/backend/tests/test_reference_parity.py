"""Pin the interpretation of upstream AASIST-L inputs and pilot scores."""

import math
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from echotrace.audio import decode_audio
from echotrace.diagnostics import audit_predictions, main as audit_main
from echotrace.model import WINDOW_SAMPLES, score_window
from echotrace.pipeline import _windows


def test_short_input_repeats_like_pinned_upstream_eval_pad():
    # clovaai/aasist@a04c9863, data_utils.py pad(): tile then truncate.
    samples = np.array([0.25, -0.5, 0.75], dtype=np.float32)
    windows = list(_windows(samples))
    assert len(windows) == 1
    start, end, actual = windows[0]
    assert (start, end) == (0, 3)
    np.testing.assert_array_equal(actual, np.tile(samples, math.ceil(WINDOW_SAMPLES / 3))[:WINDOW_SAMPLES])


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_ffmpeg_float_decode_matches_soundfile_for_16k_pcm_wav(tmp_path):
    source = tmp_path / "pcm.wav"
    t = np.arange(16000, dtype=np.float32) / 16000
    sf.write(source, 0.7 * np.sin(2 * np.pi * 347 * t), 16000, subtype="PCM_16")
    reference, rate = sf.read(source, dtype="float32")
    decoded, info = decode_audio(source)
    assert rate == info["analysis_sample_rate"] == 16000
    np.testing.assert_allclose(decoded, reference, rtol=0, atol=1 / 32768)


def test_web_windows_cover_long_input_with_end_anchored_tail():
    samples = np.arange(2 * WINDOW_SAMPLES + 13, dtype=np.float32)
    windows = list(_windows(samples))
    assert [(a, b) for a, b, _ in windows] == [
        (0, WINDOW_SAMPLES), (WINDOW_SAMPLES, 2 * WINDOW_SAMPLES),
        (WINDOW_SAMPLES + 13, 2 * WINDOW_SAMPLES + 13),
    ]
    np.testing.assert_array_equal(windows[-1][2], samples[-WINDOW_SAMPLES:])
    # Pinned upstream evaluation takes only samples[:64600]. The web mean
    # scores all three intervals; it is intentionally a different policy.
    assert not np.array_equal(windows[-1][2], samples[:WINDOW_SAMPLES])
    window_scores = [float(window[0]) for _, _, window in windows]
    assert float(np.mean(window_scores)) != float(samples[:WINDOW_SAMPLES][0])


def test_spoof_is_class_zero(monkeypatch):
    import echotrace.model as model

    class Stub:
        def __call__(self, _):
            import torch
            return None, torch.tensor([[3.0, -3.0]])

    monkeypatch.setattr(model, "_load_model", lambda: Stub())
    result = score_window(np.zeros(WINDOW_SAMPLES, dtype=np.float32))
    assert result["logits"] == [3.0, -3.0]
    assert result["score"] > 0.99


def test_audit_includes_every_pilot_file_and_generator_counts():
    project = Path(__file__).resolve().parents[2]
    manifest = project / "reports/public-pilot/manifest.csv"
    scores = project / "reports/public-pilot/scores.csv"
    result = audit_predictions(manifest, scores)
    assert len(result["files"]) == 24
    assert result["metrics"]["sample_count"] == 24
    assert result["metrics"]["confusion"] == {"tn": 9, "fp": 3, "fn": 6, "tp": 6}
    assert {item["generator"]: item["count"] for item in result["generators"]} == {
        "Chatterbox": 3, "Edge-TTS": 3, "FishTTS": 3, "MeloTTS": 3,
    }
    assert sum(item["error"] for item in result["files"]) == 9


def test_audit_rejects_missing_prediction(tmp_path):
    manifest = tmp_path / "manifest.csv"
    scores = tmp_path / "scores.csv"
    manifest.write_text("file_id,path,label\na,original/a.wav,0\nb,fake/en/G/b.wav,1\n")
    scores.write_text("file_id,synthetic_score\na,0.1\n")
    with pytest.raises(ValueError, match="coverage"):
        audit_predictions(manifest, scores)


@pytest.mark.parametrize("alias", ["existing", "manifest", "scores", "symlink", "hardlink"])
def test_audit_cli_never_overwrites_existing_output_or_input(tmp_path, capsys, alias):
    manifest = tmp_path / "manifest.csv"
    scores = tmp_path / "scores.csv"
    manifest.write_text("file_id,path,label\na,original/a.wav,0\nb,fake/en/G/b.wav,1\n")
    scores.write_text("file_id,synthetic_score\na,0.1\nb,0.9\n")
    output = tmp_path / "audit.json"
    if alias == "existing":
        output.write_text("previous report")
    elif alias == "manifest":
        output = manifest
    elif alias == "scores":
        output = scores
    elif alias == "symlink":
        output.symlink_to(scores)
    else:
        output.hardlink_to(scores)
    before = {path: path.read_bytes() for path in (manifest, scores)}
    if alias == "existing":
        before[output] = output.read_bytes()
    assert audit_main([str(manifest), str(scores), "--output", str(output)]) == 2
    assert all(path.read_bytes() == contents for path, contents in before.items())
    assert "Traceback" not in capsys.readouterr().err


def test_audit_cli_creates_new_output_and_reports_invalid_input(tmp_path, capsys):
    manifest = tmp_path / "manifest.csv"
    scores = tmp_path / "scores.csv"
    output = tmp_path / "audit.json"
    manifest.write_text("file_id,path,label\na,original/a.wav,0\nb,fake/en/G/b.wav,1\n")
    scores.write_text("file_id,synthetic_score\na,0.1\n")
    assert audit_main([str(manifest), str(scores), "--output", str(output)]) == 2
    assert not output.exists()
    assert "Traceback" not in capsys.readouterr().err
    scores.write_text("file_id,synthetic_score\na,0.1\nb,0.9\n")
    assert audit_main([str(manifest), str(scores), "--output", str(output)]) == 0
    assert '"sample_count": 2' in output.read_text()
