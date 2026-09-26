"""Bounded decoding and measured audio observations."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np


SAMPLE_RATE = 16_000
MAX_BYTES = 50 * 1024 * 1024
MAX_SECONDS = 120.0


class AudioError(ValueError):
    pass


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AudioError("Audio decoding timed out") from exc
    except FileNotFoundError as exc:
        raise AudioError(f"Required audio tool is unavailable: {args[0]}") from exc


def decode_audio(path: Path) -> tuple[np.ndarray, dict]:
    """Return mono 16 kHz float32 samples and original stream metadata."""
    path = Path(path)
    if not path.is_file():
        raise AudioError("Audio file does not exist")
    size = path.stat().st_size
    if size == 0 or size > MAX_BYTES:
        raise AudioError("Audio file must be nonempty and at most 50 MiB")
    probe = _run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,duration:format=duration",
        "-of", "json", str(path),
    ], timeout=12)
    if probe.returncode:
        raise AudioError("No readable audio stream was found")
    try:
        info = json.loads(probe.stdout)
        stream = info["streams"][0]
        original_duration = float(stream.get("duration") or info.get("format", {}).get("duration") or 0)
        channels = int(stream["channels"])
        original_rate = int(stream["sample_rate"])
        codec = str(stream["codec_name"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AudioError("Audio stream metadata is invalid") from exc
    if original_duration > MAX_SECONDS + 0.02:
        raise AudioError("Audio exceeds the 120-second limit")
    if channels < 1 or original_rate < 1:
        raise AudioError("Audio stream metadata is invalid")
    # Decode slightly past the limit so an unknown-duration stream cannot be
    # silently accepted after truncation. Size remains bounded to ~7.7 MiB.
    decoded = _run([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-t", "120.05", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1",
    ], timeout=45)
    if decoded.returncode:
        raise AudioError("Audio could not be decoded")
    if len(decoded.stdout) % 4:
        raise AudioError("Decoded audio is incomplete")
    samples = np.frombuffer(decoded.stdout, dtype="<f4").copy()
    if samples.size == 0:
        raise AudioError("Decoded audio is empty")
    if samples.size > round(MAX_SECONDS * SAMPLE_RATE):
        raise AudioError("Audio exceeds the 120-second limit")
    if not np.all(np.isfinite(samples)):
        raise AudioError("Decoded audio contains invalid samples")
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return samples, {
        "filename": path.name,
        "sha256": digest,
        "duration_s": round(samples.size / SAMPLE_RATE, 5),
        "sample_rate": original_rate,
        "channels": channels,
        "codec": codec,
        "analysis_sample_rate": SAMPLE_RATE,
    }


def waveform_buckets(samples: np.ndarray, count: int = 256) -> list[float]:
    count = min(count, len(samples))
    boundaries = np.linspace(0, len(samples), count + 1, dtype=int)
    return [round(float(np.max(np.abs(samples[boundaries[i]:boundaries[i + 1]]))), 5)
            for i in range(count)]


def measure_audio(samples: np.ndarray) -> tuple[list[dict], list[str], bool]:
    """Quality and spectral observations; none determine the model score."""
    x = samples.astype(np.float64, copy=False)
    rms = float(np.sqrt(np.mean(x * x)))
    rms_db = 20 * math.log10(max(rms, 1e-12))
    peak = float(np.max(np.abs(x)))
    clipping = float(np.mean(np.abs(x) >= 0.999))
    frame_size = 1024
    frames = x[: len(x) // frame_size * frame_size].reshape(-1, frame_size)
    if frames.size:
        frame_rms = np.sqrt(np.mean(frames * frames, axis=1))
        quiet_fraction = float(np.mean(frame_rms < 10 ** (-45 / 20)))
        spectra = np.abs(np.fft.rfft(frames * np.hanning(frame_size), axis=1)) ** 2
        powers = spectra.sum(axis=1)
        frequencies = np.fft.rfftfreq(frame_size, 1 / SAMPLE_RATE)
        centroid = float(np.sum(spectra * frequencies, axis=1).sum() / max(powers.sum(), 1e-12))
        high_fraction = float(spectra[:, frequencies >= 4000].sum() / max(powers.sum(), 1e-12))
    else:
        quiet_fraction, centroid, high_fraction = 1.0, 0.0, 0.0
    evidence = [
        _item("rms", "RMS level", round(rms_db, 2), "dBFS", "Measured average signal level.", "quality"),
        _item("peak", "Peak level", round(peak, 4), "FS", "Largest absolute decoded sample.", "quality"),
        _item("clipping", "Near-clipped samples", round(100 * clipping, 3), "%", "Samples at or above 0.999 full scale.", "quality"),
        _item("quiet", "Quiet frames", round(100 * quiet_fraction, 2), "%", "1024-sample frames below -45 dBFS RMS.", "temporal"),
        _item("centroid", "Spectral centroid", round(centroid, 1), "Hz", "Power-weighted center frequency of decoded audio.", "spectral"),
        _item("high_band", "High-band energy", round(100 * high_fraction, 2), "%", "Share of frame spectral power at or above 4 kHz.", "spectral"),
    ]
    limitations = []
    if clipping > 0.001:
        limitations.append("Near-clipped samples may affect the detector.")
    if quiet_fraction > 0.8:
        limitations.append("Most of the recording is quiet; the detector may have little speech evidence.")
    too_quiet = rms_db < -55 or peak < 0.005
    if too_quiet:
        limitations.append("Audio is too quiet for a defensible synthesis assessment.")
    return evidence, limitations, too_quiet


def _item(id: str, label: str, value: float, unit: str, detail: str, kind: str) -> dict:
    return {"id": id, "label": label, "value": value, "unit": unit, "detail": detail, "kind": kind}
