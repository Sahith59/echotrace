"""CPU-only, bounded preparation and audio audit before one GPU experiment."""

from __future__ import annotations

import argparse
import csv
import json
import signal
import sys
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from .acceptance import GATES
from .audio import SAMPLE_RATE, AudioError, decode_audio, measure_audio
from .evaluation import load_manifest
from .pipeline import _windows
from .prepare_experiment import prepare_experiment
from .training import validate_splits


class _WallExpired(TimeoutError):
    pass


@contextmanager
def _wall_alarm(seconds: int):
    """Interrupt slow preparation or decoding on the Unix CPU worker."""
    def expire(_signum, _frame):
        raise _WallExpired("CPU preflight wall cap expired")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise _WallExpired("CPU preflight wall cap expired")


def _training_config(root: Path, output: Path) -> dict:
    return {
        "dataset_root": str(root.resolve()),
        "train_manifest": str((output / "manifests/train.csv").resolve()),
        "validation_manifest": str((output / "manifests/selection.csv").resolve()),
        "output_dir": str((output / "training").resolve()),
        "max_wall_seconds": 10_800,
        "max_steps": 6_000,
        "max_epochs": 10,
        "batch_size": 8,
        "num_workers": 4,
        "learning_rate": 1e-5,
        "seed": 42,
        "device": "cuda",
    }


def _metadata_summary(manifest: Path) -> dict:
    with manifest.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    def value(row: dict, key: str) -> str:
        return (row.get(key) or "").strip() or "<missing>"
    speakers = [value(row, "speaker_id") for row in rows]
    return {
        "speaker_id_unique_count": len(set(speakers) - {"<missing>"}),
        "speaker_id_missing_count": speakers.count("<missing>"),
        "attack_id_counts": dict(sorted(Counter(value(row, "attack_id") for row in rows).items())),
        "codec_counts": dict(sorted(Counter(value(row, "codec") for row in rows).items())),
    }


def run(staged_root: Path, output_dir: Path, *, train_limit: int = 10_000,
        dev_limit: int = 4_000, max_wall_seconds: int = 3_600) -> dict:
    """Freeze splits, audit all selected audio, and write config only on success."""
    if type(max_wall_seconds) is not int or not 1 <= max_wall_seconds <= 3_600:
        raise ValueError("max_wall_seconds must be an integer in [1, 3600]")
    if type(train_limit) is not int or not 1 <= train_limit <= 30_000:
        raise ValueError("train_limit must be an integer in [1, 30000]")
    if type(dev_limit) is not int or not 1 <= dev_limit <= 10_000:
        raise ValueError("dev_limit must be an integer in [1, 10000]")
    minimum = GATES["min_each_class"]
    staged = Path(staged_root).resolve(strict=True)
    audio_root = staged / "audio"
    if not audio_root.is_dir():
        raise ValueError("Staged root must contain audio/")
    output = Path(output_dir).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output directory must be fresh: {output}")
    output.mkdir(parents=True, exist_ok=False)

    start = time.monotonic()
    deadline = start + max_wall_seconds
    report = {"ready": False, "reason": None, "staged_root": str(staged),
              "output_dir": str(output), "limits": {"train": train_limit, "dev": dev_limit,
              "cpu_wall_seconds": max_wall_seconds, "min_each_class": minimum},
              "expected_count": 0, "audited_count": 0,
              "files": [], "failures": [], "quiet": [], "splits": {}}
    try:
        with _wall_alarm(max_wall_seconds):
            _check_deadline(deadline)
            prepare_experiment(staged / "train.csv", staged / "dev.csv", audio_root,
                               output / "manifests", seed=42, train_limit=train_limit,
                               dev_limit=dev_limit)
            _check_deadline(deadline)
            records = {name: load_manifest(output / "manifests" / f"{name}.csv", audio_root)
                       for name in ("train", "selection", "acceptance")}
            report["expected_count"] = sum(map(len, records.values()))
            for name, items in records.items():
                counts = Counter(item["label"] for item in items)
                report["splits"][name] = {"count": len(items),
                                          "label_counts": {str(k): counts[k] for k in (0, 1)},
                                          **_metadata_summary(output / "manifests" / f"{name}.csv")}
                if name in ("selection", "acceptance") and min(counts[0], counts[1]) < minimum:
                    raise ValueError(f"{name} requires at least {minimum} files per class")
            for left, right in (("train", "selection"), ("train", "acceptance"),
                                ("selection", "acceptance")):
                validate_splits(records[left], records[right])
            _check_deadline(deadline)
            for name, items in records.items():
                for item in items:
                    _check_deadline(deadline)
                    row = {"split": name, "file_id": item["file_id"],
                           "sha256": item["sha256"], "status": "ok"}
                    try:
                        samples, _metadata = decode_audio(Path(item["path"]))
                        _check_deadline(deadline)
                        _evidence, _limitations, too_quiet = measure_audio(samples)
                        row["duration_s"] = round(len(samples) / SAMPLE_RATE, 5)
                        row["window_count"] = sum(1 for _ in _windows(samples))
                        if too_quiet:
                            row["status"] = "quiet"
                            row["reason"] = "Audio is too quiet for scoring"
                            report["quiet"].append({"split": name, "file_id": item["file_id"],
                                                    "reason": row["reason"]})
                    except _WallExpired:
                        row["status"] = "failed"
                        row["reason"] = "CPU preflight wall cap expired"
                        report["failures"].append({"split": name, "file_id": item["file_id"],
                                                   "reason": row["reason"]})
                        report["files"].append(row)
                        report["audited_count"] += 1
                        raise
                    except (AudioError, OSError, ValueError, RuntimeError) as exc:
                        row["status"] = "failed"
                        row["reason"] = str(exc)
                        report["failures"].append({"split": name, "file_id": item["file_id"],
                                                   "reason": str(exc)})
                    report["files"].append(row)
                    report["audited_count"] += 1
                    if report["audited_count"] % 500 == 0:
                        print(f"CPU audit: {report['audited_count']}/{report['expected_count']}",
                              file=sys.stderr, flush=True)
            _check_deadline(deadline)
            if report["failures"] or report["quiet"]:
                report["reason"] = "One or more selected files failed decoding or quality review"
            else:
                report["ready"] = True
    except (_WallExpired, OSError, ValueError, RuntimeError) as exc:
        report["ready"] = False
        report["reason"] = str(exc)
    if report["ready"]:
        try:
            _check_deadline(deadline)
            config = _training_config(audio_root, output)
            (output / "training-config.json").write_text(
                json.dumps(config, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            _check_deadline(deadline)
        except (_WallExpired, OSError, ValueError, RuntimeError) as exc:
            report["ready"] = False
            report["reason"] = str(exc)
            (output / "training-config.json").unlink(missing_ok=True)
    report["elapsed_seconds"] = round(time.monotonic() - start, 3)
    (output / "preflight.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                                             encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-limit", type=int, default=10_000)
    parser.add_argument("--dev-limit", type=int, default=4_000)
    parser.add_argument("--max-wall-seconds", type=int, default=3_600)
    args = parser.parse_args(argv)
    try:
        report = run(args.staged_root, args.output_dir, train_limit=args.train_limit,
                     dev_limit=args.dev_limit, max_wall_seconds=args.max_wall_seconds)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"CPU preflight: {exc}\n")
    print(json.dumps({"ready": report["ready"], "reason": report["reason"],
                      "report": str(Path(args.output_dir).absolute() / "preflight.json")},
                     allow_nan=False))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
