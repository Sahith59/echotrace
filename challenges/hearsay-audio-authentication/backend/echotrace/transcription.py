"""Bounded local speech-to-text using a pre-trained faster-whisper model."""
from __future__ import annotations

import argparse
import importlib.util
import math
import os
import threading
from pathlib import Path

from dotenv import dotenv_values

from .interpretation import ENV_PATH

MAX_DURATION_S = 120.0
MAX_SEGMENTS = 1000
MAX_TRANSCRIPT_CHARS = 100_000
DEFAULT_MODEL = "base"
DOWNLOADABLE_MODELS = {"tiny", "tiny.en", "base", "base.en", "small", "small.en"}


class TranscriptionError(ValueError):
    pass


def _default_factory(**kwargs):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise TranscriptionError(
            "Local transcription is unavailable because faster-whisper is not installed."
        ) from None
    return WhisperModel(**kwargs)


class Transcriber:
    """Lazy, single-model local transcriber with explicit cache/download policy."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        cache_dir: Path | str | None = None,
        download_allowed: bool = False,
        model_factory=None,
        cpu_threads: int = 4,
    ):
        self.model_name = model
        self.cache_dir = Path(cache_dir or Path.cwd() / ".echotrace-models").resolve()
        self.download_allowed = download_allowed
        self.model_factory = model_factory or _default_factory
        self.cpu_threads = max(1, min(int(cpu_threads), 16))
        self._loaded_model = None
        self._load_lock = threading.Lock()

    @classmethod
    def configured(cls, cache_dir: Path | str) -> "Transcriber":
        values = dotenv_values(ENV_PATH) if ENV_PATH.is_file() else {}
        model = os.environ.get("ECHOTRACE_WHISPER_MODEL") or values.get("ECHOTRACE_WHISPER_MODEL") or DEFAULT_MODEL
        threads = os.environ.get("ECHOTRACE_WHISPER_CPU_THREADS") or values.get("ECHOTRACE_WHISPER_CPU_THREADS") or "4"
        try:
            thread_count = int(threads)
        except (TypeError, ValueError):
            thread_count = 4
        return cls(model=str(model), cache_dir=cache_dir, download_allowed=False, cpu_threads=thread_count)

    def _cache_ready(self) -> bool:
        if Path(self.model_name).is_dir():
            return True
        return self.cache_dir.is_dir() and any(self.cache_dir.iterdir())

    def status(self) -> dict:
        package_ready = importlib.util.find_spec("faster_whisper") is not None
        cache_state = "ready" if self._cache_ready() else "not_ready"
        available = package_ready and cache_state == "ready"
        reason = None
        if not package_ready:
            reason = "Install the faster-whisper runtime dependency."
        elif not available:
            reason = (
                f"Model {self.model_name!r} is not prepared. Run the documented bounded model setup command."
            )
        return {
            "available": available,
            "provider": "faster-whisper",
            "model": self.model_name,
            "device": "cpu",
            "compute_type": "int8",
            "cache_state": cache_state,
            "download_allowed": self.download_allowed,
            "max_duration_s": int(MAX_DURATION_S),
            "reason": reason,
        }

    def _model(self):
        if self._loaded_model is not None:
            return self._loaded_model
        with self._load_lock:
            if self._loaded_model is not None:
                return self._loaded_model
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._loaded_model = self.model_factory(
                    model_size_or_path=self.model_name,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(self.cache_dir),
                    local_files_only=not self.download_allowed,
                    cpu_threads=self.cpu_threads,
                    num_workers=1,
                )
            except TranscriptionError:
                raise
            except Exception:
                raise TranscriptionError(
                    f"The local transcription model {self.model_name!r} could not be loaded. "
                    "Prepare it with the documented setup command and retry."
                ) from None
        return self._loaded_model

    def prepare(self) -> None:
        if self.model_name not in DOWNLOADABLE_MODELS:
            raise TranscriptionError(
                "Automatic setup is limited to tiny, base, or small Whisper models."
            )
        self.download_allowed = True
        self._model()

    def transcribe(self, audio_path: Path) -> dict:
        try:
            segments_iter, info = self._model().transcribe(
                str(audio_path),
                beam_size=5,
                vad_filter=True,
                word_timestamps=False,
                condition_on_previous_text=True,
            )
            raw_segments = list(segments_iter)
        except TranscriptionError:
            raise
        except Exception:
            raise TranscriptionError(
                "Local transcription failed. Verify the prepared model and audio, then retry."
            ) from None

        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if not math.isfinite(duration) or duration < 0:
            raise TranscriptionError("Transcription returned an invalid audio duration.")
        if duration > MAX_DURATION_S:
            raise TranscriptionError("Audio exceeds the 120 second transcription duration limit.")
        if len(raw_segments) > MAX_SEGMENTS:
            raise TranscriptionError("Transcription returned too many timestamped segments.")

        segments = []
        prior_end = 0.0
        for index, segment in enumerate(raw_segments):
            start = round(float(segment.start), 3)
            end = round(float(segment.end), 3)
            text = str(segment.text).strip()
            if not text:
                continue
            if (not math.isfinite(start) or not math.isfinite(end) or start < 0 or
                    end <= start or end > MAX_DURATION_S or start + 0.01 < prior_end):
                raise TranscriptionError("Transcription returned invalid timestamp boundaries.")
            segments.append({
                "id": int(getattr(segment, "id", index)),
                "start_s": start,
                "end_s": end,
                "text": text,
            })
            prior_end = end
        text = " ".join(item["text"] for item in segments).strip()
        if len(text) > MAX_TRANSCRIPT_CHARS:
            raise TranscriptionError("Transcript exceeds the 100,000 character limit.")
        probability = getattr(info, "language_probability", None)
        if probability is not None:
            probability = float(probability)
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                probability = None
        return {
            "text": text,
            "segments": segments,
            "language": getattr(info, "language", None),
            "language_probability": probability,
            "duration_s": duration or (segments[-1]["end_s"] if segments else 0.0),
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a bounded local Whisper model for ECHOTRACE.")
    parser.add_argument("--model", choices=sorted(DOWNLOADABLE_MODELS), default=DEFAULT_MODEL)
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    service = Transcriber(model=args.model, cache_dir=args.cache_dir, download_allowed=True)
    service.prepare()
    print(f"Prepared {args.model} for local CPU int8 transcription.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
