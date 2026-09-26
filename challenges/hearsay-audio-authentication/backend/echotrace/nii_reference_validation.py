"""Prepare and compare the fixed NII Fairseq/Transformers parity bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch


MAX_ABS_LOGIT_TOLERANCE = 1e-3
MAX_ABS_PROBABILITY_TOLERANCE = 1e-4
FIXED_CASE_IDS = ("real-1", "real-2", "synthetic-1", "synthetic-2", "tone")


def validate_parity(reference_path: Path, candidate_path: Path) -> dict:
    reference = json.loads(Path(reference_path).read_text())
    candidate = json.loads(Path(candidate_path).read_text())
    reference_cases = {case["id"]: case for case in reference["cases"]}
    candidate_cases = {case["id"]: case for case in candidate["cases"]}
    if set(reference_cases) != set(candidate_cases):
        raise RuntimeError("Parity case IDs differ; investigate; do not relax tolerances")
    if tuple(reference_cases) != FIXED_CASE_IDS or tuple(candidate_cases) != FIXED_CASE_IDS:
        raise RuntimeError("Parity requires the five fixed case IDs in order; investigate; do not relax tolerances")
    max_logit = 0.0
    max_probability = 0.0
    for case_id in sorted(reference_cases):
        expected, actual = reference_cases[case_id], candidate_cases[case_id]
        if len(expected["raw_logits"]) != len(actual["raw_logits"]):
            raise RuntimeError("Parity logit dimensions differ; investigate; do not relax tolerances")
        max_logit = max(max_logit, max(abs(a - b) for a, b in zip(expected["raw_logits"], actual["raw_logits"])))
        max_probability = max(max_probability, abs(expected["score"] - actual["score"]))
    if max_logit > MAX_ABS_LOGIT_TOLERANCE or max_probability > MAX_ABS_PROBABILITY_TOLERANCE:
        raise RuntimeError(
            "NII reference parity exceeded its predeclared tolerance; investigate; do not relax tolerances"
        )
    return {
        "passed": True,
        "case_count": len(reference_cases),
        "max_abs_logit_difference": max_logit,
        "max_abs_probability_difference": max_probability,
        "logit_tolerance": MAX_ABS_LOGIT_TOLERANCE,
        "probability_tolerance": MAX_ABS_PROBABILITY_TOLERANCE,
    }


def prepare_fixed_inputs(pilot_root: Path, output: Path) -> None:
    from .audio import decode_audio

    paths = (
        pilot_root / "original/en/northandsouth_03_f000065.wav",
        pilot_root / "original/en/jane_eyre_19_f000009.wav",
        pilot_root / "fake/en/Edge-TTS/jane_eyre_15_f000218.wav",
        pilot_root / "fake/en/FishTTS/northandsouth_20_f000133.wav",
    )
    arrays = {}
    for case_id, path in zip(FIXED_CASE_IDS[:4], paths, strict=True):
        samples, _ = decode_audio(path)
        if len(samples) > 30 * 16_000:
            raise ValueError(f"{case_id} exceeds the frozen 30-second parity bound")
        arrays[case_id] = samples
    time = np.arange(4 * 16_000, dtype=np.float32) / 16_000
    arrays["tone"] = (0.1 * np.sin(2 * np.pi * 223 * time)).astype(np.float32)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(output, **arrays)


def score_bundle(bundle_path: Path, output_path: Path, engine: str, source_root: Path | None = None,
                 weights_path: Path | None = None) -> None:
    bundle = np.load(bundle_path, allow_pickle=False)
    if tuple(bundle.files) != FIXED_CASE_IDS:
        raise ValueError(f"Expected fixed cases {FIXED_CASE_IDS}, received {tuple(bundle.files)}")
    if engine == "candidate":
        from . import nii_candidate
        scorer = nii_candidate.score_samples
        runtime = "transformers-cpu-fp32"
    else:
        if source_root is None:
            raise ValueError("Official reference scoring requires --source-root")
        import sys
        sys.path.insert(0, str(source_root))
        from models.W2V import Model
        from safetensors.torch import load_file

        if weights_path is None:
            raise ValueError("Official reference scoring requires --weights")
        torch.set_num_threads(4)
        model = Model("w2v_small")
        model.load_state_dict(load_file(weights_path, device="cpu"), strict=True)
        model.eval()

        def scorer(samples):
            waveform = torch.from_numpy(np.asarray(samples, dtype=np.float32).copy())
            waveform = torch.nn.functional.layer_norm(waveform, waveform.shape).unsqueeze(0)
            with torch.inference_mode():
                logits_tensor = model(waveform)[0]
                score = torch.softmax(logits_tensor, dim=0)[0]
            return {"score": float(score), "raw_logits": [float(value) for value in logits_tensor]}

        runtime = "official-fairseq-cpu-fp32"
    cases = [{"id": case_id, **scorer(bundle[case_id])} for case_id in FIXED_CASE_IDS]
    output_path.write_text(json.dumps({"runtime": runtime, "cases": cases}, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("pilot_root", type=Path)
    prepare.add_argument("output", type=Path)
    score = commands.add_parser("score")
    score.add_argument("engine", choices=("candidate", "reference"))
    score.add_argument("bundle", type=Path)
    score.add_argument("output", type=Path)
    score.add_argument("--source-root", type=Path)
    score.add_argument("--weights", type=Path)
    compare = commands.add_parser("compare")
    compare.add_argument("reference", type=Path)
    compare.add_argument("candidate", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_fixed_inputs(args.pilot_root, args.output)
    elif args.command == "score":
        score_bundle(args.bundle, args.output, args.engine, args.source_root, args.weights)
    else:
        print(json.dumps(validate_parity(args.reference, args.candidate), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
