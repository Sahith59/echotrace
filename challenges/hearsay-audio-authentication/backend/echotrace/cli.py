"""Reproducible local scoring and evaluation commands."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path


def _guard_outputs(outputs, inputs):
    """Reject outputs that refer to an input or to another output."""
    protected = [Path(path) for path in inputs]
    for output in map(Path, outputs):
        for other in protected:
            if output.resolve() == other.resolve() or (output.exists() and other.exists() and output.samefile(other)):
                raise ValueError(f"Output path conflicts with an input or another output: {output}")
        protected.append(output)


def emit(value, target=None):
    content = json.dumps(value, indent=2, allow_nan=False)
    if target:
        Path(target).write_text(content + "\n")
    else:
        print(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description="ECHOTRACE local audio analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup-model", help="Download and verify the pinned NII primary checkpoint")
    single = sub.add_parser("score", help="Analyze a file using the same pipeline as the web app")
    single.add_argument("file", type=Path)
    single.add_argument("--output", type=Path)
    batch = sub.add_parser("batch", help="Score a manifest; output is internal, not sponsor-format")
    batch.add_argument("manifest", type=Path)
    batch.add_argument("--root", type=Path, required=True)
    batch.add_argument("--output", type=Path, required=True)
    audit = sub.add_parser("audit", help="Audit labels/IDs/content and optionally create grouped split")
    audit.add_argument("manifest", type=Path)
    audit.add_argument("--root", type=Path, required=True)
    audit.add_argument("--split", action="store_true")
    audit.add_argument("--output", type=Path)
    evaluate = sub.add_parser("evaluate", help="Evaluate labeled development data, never tune on test labels")
    evaluate.add_argument("manifest", type=Path)
    evaluate.add_argument("predictions", type=Path)
    evaluate.add_argument("--root", type=Path, required=True)
    evaluate.add_argument("--threshold", type=float, default=0.5)
    evaluate.add_argument("--output", type=Path)
    export = sub.add_parser("export", help="Validate coverage and convert to a confirmed submission schema")
    export.add_argument("predictions", type=Path)
    export.add_argument("--expected", type=Path, required=True)
    export.add_argument("--schema", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--allow-example-schema", action="store_true",
                        help="Permit an explicitly non-official example schema")
    args = parser.parse_args(argv)
    try:
        if args.command == "setup-model":
            from .primary_detector import model_status, setup_primary_weights
            path = setup_primary_weights()
            emit({"path": str(path), **model_status()})
        elif args.command == "score":
            from .pipeline import analyze_file
            if args.output:
                _guard_outputs([args.output], [args.file])
            emit(analyze_file(args.file), args.output)
        elif args.command == "batch":
            from .evaluation import load_manifest
            from .pipeline import analyze_file
            records = load_manifest(args.manifest, args.root, require_labels=False)
            _guard_outputs([args.output, args.output.with_suffix(".run.json")],
                           [args.manifest, *(record["path"] for record in records)])
            args.output.parent.mkdir(parents=True, exist_ok=True)
            reports = []
            failed = 0
            with args.output.open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["file_id", "synthetic_score", "status", "error"])
                for index, record in enumerate(records, 1):
                    print(f"Analyzing {index}/{len(records)}: {record['file_id']}", file=sys.stderr)
                    try:
                        result = analyze_file(Path(record["path"]))
                        reports.append({"file_id": record["file_id"], "result": result})
                        score = result["synthetic_score"]
                        if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                            raise ValueError("No usable model score; review result limitations")
                        writer.writerow([record["file_id"], format(score, ".10g"), "completed", ""])
                    except Exception as exc:
                        failed += 1
                        writer.writerow([record["file_id"], "", "failed", str(exc)])
            emit({"manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                  "count": len(records), "failures": failed, "results": reports},
                 args.output.with_suffix(".run.json"))
            emit({"output": str(args.output), "count": len(records), "failures": failed,
                  "export_kind": "internal; official schema conversion required"})
            return 2 if failed else 0
        elif args.command == "audit":
            from .evaluation import load_manifest, audit_manifest, grouped_split
            records = load_manifest(args.manifest, args.root)
            if args.output:
                _guard_outputs([args.output], [args.manifest, *(record["path"] for record in records)])
            result = audit_manifest(records)
            if args.split:
                result["split"] = grouped_split(records)
            emit(result, args.output)
        elif args.command == "evaluate":
            from .evaluation import load_manifest, evaluate_predictions
            records = load_manifest(args.manifest, args.root)
            if args.output:
                _guard_outputs([args.output], [args.manifest, args.predictions,
                                               *(record["path"] for record in records)])
            result = evaluate_predictions(records, args.predictions, threshold=args.threshold)
            result["note"] = "Metrics describe only this supplied labeled set; not proof of field accuracy or calibration."
            emit(result, args.output)
        elif args.command == "export":
            from .evaluation import export_submission
            _guard_outputs([args.output], [args.predictions, args.expected, args.schema])
            emit(export_submission(args.predictions, args.expected, args.schema, args.output,
                                   require_official=not args.allow_example_schema))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ECHOTRACE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
