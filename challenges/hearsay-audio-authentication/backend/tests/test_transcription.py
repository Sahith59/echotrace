from pathlib import Path
from types import SimpleNamespace

import pytest

from echotrace.transcription import MAX_SEGMENTS, TranscriptionError, Transcriber


class FakeWhisperModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, path, **options):
        self.calls.append((path, options))
        segments = [
            SimpleNamespace(id=0, start=0.0, end=1.25, text=" Hello"),
            SimpleNamespace(id=1, start=1.25, end=2.5, text=" world."),
        ]
        info = SimpleNamespace(language="en", language_probability=0.98, duration=2.5)
        return iter(segments), info


def test_transcriber_runs_real_model_contract_with_timestamps(tmp_path):
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"audio fixture")
    model = FakeWhisperModel()
    service = Transcriber(
        model="tiny.en",
        cache_dir=tmp_path / "models",
        download_allowed=False,
        model_factory=lambda **kwargs: model,
    )

    result = service.transcribe(audio)

    assert result["text"] == "Hello world."
    assert result["language"] == "en"
    assert result["language_probability"] == pytest.approx(0.98)
    assert result["segments"] == [
        {"id": 0, "start_s": 0.0, "end_s": 1.25, "text": "Hello"},
        {"id": 1, "start_s": 1.25, "end_s": 2.5, "text": "world."},
    ]
    assert model.calls == [(str(audio), {
        "beam_size": 5,
        "vad_filter": True,
        "word_timestamps": False,
        "condition_on_previous_text": True,
    })]


def test_transcriber_has_bounded_explicit_setup_and_no_stub(tmp_path):
    calls = []

    def unavailable_factory(**kwargs):
        calls.append(kwargs)
        raise OSError("model is not cached")

    service = Transcriber(
        model="tiny.en",
        cache_dir=tmp_path / "models",
        download_allowed=False,
        model_factory=unavailable_factory,
    )

    status = service.status()
    assert status["provider"] == "faster-whisper"
    assert status["model"] == "tiny.en"
    assert status["device"] == "cpu"
    assert status["compute_type"] == "int8"
    assert status["download_allowed"] is False
    assert "cache_dir" not in status
    assert status["cache_state"] in {"ready", "not_ready"}

    with pytest.raises(TranscriptionError, match="could not be loaded"):
        service.transcribe(Path(tmp_path / "missing.wav"))
    assert calls == [{
        "model_size_or_path": "tiny.en",
        "device": "cpu",
        "compute_type": "int8",
        "download_root": str(tmp_path / "models"),
        "local_files_only": True,
        "cpu_threads": 4,
        "num_workers": 1,
    }]


def test_transcriber_rejects_model_output_beyond_audio_contract(tmp_path):
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"audio fixture")

    class BadModel:
        def transcribe(self, path, **options):
            return iter([SimpleNamespace(id=0, start=0, end=121, text="too long")]), SimpleNamespace(
                language="en", language_probability=1.0, duration=121
            )

    service = Transcriber(model_factory=lambda **kwargs: BadModel(), cache_dir=tmp_path / "models")
    with pytest.raises(TranscriptionError, match="duration limit"):
        service.transcribe(audio)


def test_transcriber_stops_consuming_unbounded_segment_generator(tmp_path):
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"audio fixture")

    class RunawayModel:
        def transcribe(self, path, **options):
            def segments():
                for index in range(MAX_SEGMENTS + 2):
                    if index > MAX_SEGMENTS:
                        pytest.fail("transcriber consumed beyond its declared segment cap")
                    yield SimpleNamespace(id=index, start=0.0, end=1.0, text="word")
            return segments(), SimpleNamespace(language="en", language_probability=1.0, duration=1)

    service = Transcriber(model_factory=lambda **kwargs: RunawayModel(), cache_dir=tmp_path / "models")
    with pytest.raises(TranscriptionError, match="too many"):
        service.transcribe(audio)


def test_transcriber_rejects_oversized_segment_text_before_aggregation(tmp_path):
    audio = tmp_path / "recording.wav"
    audio.write_bytes(b"audio fixture")

    class OversizedTextModel:
        def transcribe(self, path, **options):
            segment = SimpleNamespace(id=0, start=0.0, end=1.0, text="x" * 100_001)
            return iter([segment]), SimpleNamespace(language="en", language_probability=1.0, duration=1)

    service = Transcriber(model_factory=lambda **kwargs: OversizedTextModel(), cache_dir=tmp_path / "models")
    with pytest.raises(TranscriptionError, match="character limit"):
        service.transcribe(audio)
