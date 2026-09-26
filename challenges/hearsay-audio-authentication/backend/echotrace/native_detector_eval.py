"""Bounded evaluation of a pinned native Transformers deepfake detector."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from .audio import AudioError, decode_audio, measure_audio
from .checkpoint_eval import PROVENANCE_FIELDS, _public_records
from .evaluation import load_manifest
from .pipeline import _windows

MODEL_ID = "garystafford/wav2vec2-deepfake-voice-detector"
MODEL_REVISION = "c66306024a7ede0be291e9c4558b37634782dc4e"
WEIGHTS_SHA256 = "905e330265c40a76955911ce86691fb4c8f2ed9c8085f4f046cac1383592a0ac"
WEIGHTS_BYTES = 1_262_859_296
CONFIG_SHA256 = "c5791d2fc2e5506b228fa99387c2b2619c7836ad7e244699f8e5e8510b8f2574"
PROCESSOR_SHA256 = "35818933f1836450939a59d1f0ae7e4386d0d64d1560ce60a65001af62ac3f71"
FILES = {"model.safetensors": WEIGHTS_SHA256, "config.json": CONFIG_SHA256,
         "preprocessor_config.json": PROCESSOR_SHA256}
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / "artifacts" / "native-detector"


def _sha(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify(cache: Path) -> None:
    cache = Path(cache)
    for name, expected in FILES.items():
        path = cache / name
        if not path.is_file() or _sha(path) != expected:
            raise RuntimeError(f"Pinned native detector {name} is missing or failed SHA-256")
    if (cache / "model.safetensors").stat().st_size != WEIGHTS_BYTES:
        raise RuntimeError("Pinned native detector weights failed size verification")


def setup(cache: Path) -> None:
    from huggingface_hub import hf_hub_download

    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        hf_hub_download(repo_id=MODEL_ID, revision=MODEL_REVISION,
                        filename=name, local_dir=cache)
    verify(cache)


def _load(cache: Path, device: str):
    verify(cache)
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

    extractor = AutoFeatureExtractor.from_pretrained(
        cache, local_files_only=True, trust_remote_code=False)
    model = AutoModelForAudioClassification.from_pretrained(
        cache, local_files_only=True, trust_remote_code=False,
        use_safetensors=True).to(device).eval()
    if model.config.label2id != {"fake": 1, "real": 0}:
        raise RuntimeError("Pinned native detector label polarity changed")
    return extractor, model


def score_samples(samples: np.ndarray, extractor, model, device: str, deadline: float) -> float:
    windows = [window for _, _, window in _windows(samples)]
    scores = []
    for offset in range(0, len(windows), 8):
        if time.monotonic() >= deadline:
            raise TimeoutError("Evaluation wall-clock limit reached")
        batch = extractor(windows[offset:offset + 8], sampling_rate=16_000,
                          return_tensors="pt", padding=True)
        batch = {key: value.to(device) for key, value in batch.items()}
        with torch.inference_mode(), torch.autocast(
                device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
            logits = model(**batch).logits
        if logits.ndim != 2 or logits.shape[1] != 2 or not torch.isfinite(logits).all():
            raise RuntimeError("Native detector returned invalid two-class logits")
        scores.extend(torch.softmax(logits.float(), dim=-1)[:, 1].cpu().tolist())
    score = float(np.mean(scores))
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise RuntimeError("Native detector returned an invalid score")
    return score


def run(manifest: Path, dataset_root: Path, output: Path, *, cache: Path,
        compatibility_run: Path, device: str, role: str, max_seconds: int = 3600,
        adapted_model: Path | None = None) -> dict:
    if role not in ("selection", "acceptance"):
        raise ValueError("Role must be selection or acceptance")
    if device not in ("cpu", "cuda") or device == "cuda" and not torch.cuda.is_available():
        raise ValueError("Requested device is unavailable")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a fresh directory")
    records = load_manifest(Path(manifest), Path(dataset_root))
    if len(records) > 10_000 or {r["label"] for r in records} != {0, 1}:
        raise ValueError("Evaluation requires at most 10000 files and both classes")
    compatible = json.loads(Path(compatibility_run).read_text())
    aggregation = compatible["aggregation"]
    expected = {"window_samples": 64_600, "hop_samples": 64_600,
                "tail_policy": "end_anchored_overlap", "short_input_policy": "repeat_pad"}
    if any(aggregation.get(key) != value for key, value in expected.items()):
        raise ValueError("Compatibility run uses different audio windows")
    training_provenance = None
    checkpoint_sha = WEIGHTS_SHA256
    if adapted_model:
        adapted_model = Path(adapted_model)
        provenance = json.loads((adapted_model.parent / "provenance.json").read_text())
        checkpoint_sha = provenance["adapted_weights_sha256"]
        if _sha(adapted_model / "model.safetensors") != checkpoint_sha:
            raise RuntimeError("Adapted SafeTensors checkpoint hash mismatch")
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
        extractor = AutoFeatureExtractor.from_pretrained(adapted_model, local_files_only=True,
                                                          trust_remote_code=False)
        model = AutoModelForAudioClassification.from_pretrained(
            adapted_model, local_files_only=True, trust_remote_code=False,
            use_safetensors=True).to(device).eval()
        training_provenance = provenance["split_provenance"]
    else:
        extractor, model = _load(cache, device)
    started = time.monotonic()
    deadline = started + max_seconds
    failures, rows = [], []
    for record in records:
        score, status, reason = None, "scored", None
        try:
            samples, _ = decode_audio(Path(record["path"]))
            _, _, quiet = measure_audio(samples)
            if quiet:
                status, reason = "quiet", "Audio is too quiet for a defensible synthesis assessment"
            else:
                score = score_samples(samples, extractor, model, device, deadline)
        except (AudioError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
            status, reason = "failed", str(exc)
        if score is None:
            failures.append({"file_id": record["file_id"], "status": status, "reason": reason})
        rows.append((record["file_id"], score, status))
    output.mkdir(parents=True)
    scores_path = output / "scores.csv"
    with scores_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("file_id", "synthetic_score", "status"))
        writer.writerows((file_id, "" if score is None else format(score, ".17g"), status)
                         for file_id, score, status in rows)
    training_provenance = training_provenance or {"train": [{
        "file_id": "external-garystafford-training-set",
        "sha256": WEIGHTS_SHA256, "label": 1, "group_id": "external",
        "speaker_id": "external", "source_id": MODEL_ID,
    }], "validation": [], "note": "External model training rows are not published; no local fitting."}
    result = {
        "role": role, "model_kind": "candidate", "checkpoint_sha256": checkpoint_sha,
        "config_sha256": compatible["config_sha256"], "upstream_revision": MODEL_REVISION,
        "aggregation": aggregation, "complete": not failures,
        "completed_count": len(rows) - len(failures), "failure_count": len(failures),
        "failures": failures, "records": _public_records(Path(manifest), records),
        "training_provenance": training_provenance,
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION,
                  "weights_sha256": checkpoint_sha, "base_weights_sha256": WEIGHTS_SHA256,
                  "adapted": bool(adapted_model), "config_sha256": CONFIG_SHA256,
                  "processor_sha256": PROCESSOR_SHA256, "fake_label_index": 1,
                  "safe_loading": {"trust_remote_code": False, "use_safetensors": True}},
        "scores_sha256": _sha(scores_path),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    (output / "run.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--compatibility-run", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--role", choices=("selection", "acceptance"))
    parser.add_argument("--max-seconds", type=int, default=3600)
    parser.add_argument("--adapted-model", type=Path)
    parser.add_argument("--setup", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.setup:
            setup(args.cache)
            print(json.dumps({"ready": True, "cache": str(args.cache), "sha256": WEIGHTS_SHA256}))
        else:
            if not all((args.manifest, args.dataset_root, args.output,
                        args.compatibility_run, args.role)):
                parser.error("run arguments are required")
            print(json.dumps(run(args.manifest, args.dataset_root, args.output,
                                 cache=args.cache, compatibility_run=args.compatibility_run,
                                 device=args.device, role=args.role,
                                 max_seconds=args.max_seconds,
                                 adapted_model=args.adapted_model), allow_nan=False))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"NATIVE DETECTOR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
