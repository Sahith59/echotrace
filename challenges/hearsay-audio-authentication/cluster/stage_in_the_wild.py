"""Verify and stage a fixed In-the-Wild external evaluation sample.

The archive is downloaded separately so a failed checksum or audit never removes
the cache. Selection depends only on immutable metadata and is completed before
any decoder or detector runs.
"""

from __future__ import annotations

import argparse
import array
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Callable


DATASET = "mueller91/In-The-Wild"
REVISION = "eee168f92c367f8c82ff2cf42b6f61e362fd6211"
ARCHIVE_NAME = "release_in_the_wild.zip"
ARCHIVE_BYTES = 8_161_489_023
ARCHIVE_SHA256 = "46665f30a6758b45642c659c7e0e80da2ba3d121b064716824a56a010ddf9e1a"
ARCHIVE_URL = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{ARCHIVE_NAME}"
SEED = "external-itw-20260926"
ROOT = "release_in_the_wild"
MAX_MEMBERS = 40_000
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024 * 1024
MAX_META_BYTES = 32 * 1024 * 1024
MAX_PCM_BYTES = 256 * 1024 * 1024
CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(path: Path) -> str:
    size = path.stat().st_size
    if size != ARCHIVE_BYTES:
        raise ValueError(f"Archive size mismatch: expected {ARCHIVE_BYTES}, got {size}")
    digest = sha256_file(path)
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"Archive checksum mismatch: expected {ARCHIVE_SHA256}, got {digest}")
    return digest


def _safe_name(info: zipfile.ZipInfo) -> str | None:
    name = info.filename.rstrip("/")
    if not name:
        return None
    path = PurePosixPath(name)
    mode = info.external_attr >> 16
    if (info.flag_bits & 1 or path.is_absolute() or "\\" in info.filename
            or any(part in ("", ".", "..") for part in path.parts)
            or len(info.filename) > 255 or (mode and not (mode & 0o170000) in (0, 0o040000, 0o100000))):
        raise ValueError(f"Unsafe archive member: {info.filename}")
    if info.is_dir():
        if name != ROOT:
            raise ValueError(f"Unexpected archive directory: {info.filename}")
        return None
    if len(path.parts) != 2 or path.parts[0] != ROOT:
        raise ValueError(f"Unexpected archive member: {info.filename}")
    if path.name not in {"meta.csv", "attribution.txt"} and not re.fullmatch(r"[^/]+\.wav", path.name, re.IGNORECASE):
        raise ValueError(f"Unexpected archive member: {info.filename}")
    if info.file_size <= 0 or info.file_size > (MAX_META_BYTES if path.name == "meta.csv" else MAX_MEMBER_BYTES):
        raise ValueError(f"Unsafe archive member size: {info.filename}")
    return name


def _inventory(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        raise ValueError(f"Archive has too many members: {len(infos)}")
    total = sum(info.file_size for info in infos)
    if total > MAX_TOTAL_BYTES:
        raise ValueError(f"Archive expands beyond limit: {total}")
    members: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        name = _safe_name(info)
        if name is None:
            continue
        if name in members:
            raise ValueError(f"Duplicate archive member: {name}")
        members[name] = info
    metadata_name = f"{ROOT}/meta.csv"
    attribution_name = f"{ROOT}/attribution.txt"
    if metadata_name not in members or attribution_name not in members:
        raise ValueError("Archive is missing required metadata or author attribution")
    return members


def _metadata(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[list[str], list[dict[str, str]]]:
    raw = archive.read(info)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Metadata is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = reader.fieldnames
    if not fields or len(fields) != len(set(fields)) or not {"file", "speaker", "label"} <= set(fields):
        raise ValueError("Metadata must have unique file, speaker, and label columns")
    rows = list(reader)
    if not rows or any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Metadata is empty or malformed")
    seen = set()
    for row in rows:
        filename = row["file"].strip()
        if not re.fullmatch(r"[^/\\]+\.wav", filename, re.IGNORECASE):
            raise ValueError(f"Invalid metadata filename: {filename}")
        if filename in seen:
            raise ValueError(f"Duplicate metadata filename: {filename}")
        seen.add(filename)
        if not row["speaker"].strip():
            raise ValueError(f"Missing speaker metadata: {filename}")
        _label(row["label"])
    return fields, rows


def _label(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"real", "genuine", "bonafide", "bona-fide", "0"}:
        return "0"
    if normalized in {"fake", "spoof", "synthetic", "1"}:
        return "1"
    raise ValueError(f"Unknown metadata label: {value}")


def _rank(row: dict[str, str]) -> bytes:
    return hashlib.sha256(f"{SEED}:{row['file'].strip()}".encode("utf-8")).digest()


def _select(rows: list[dict[str, str]], sample_per_class: int) -> list[dict[str, str]]:
    if sample_per_class <= 0 or sample_per_class > 10_000:
        raise ValueError("sample_per_class must be between 1 and 10000")
    selected = []
    for label in ("0", "1"):
        candidates = [row for row in rows if _label(row["label"]) == label]
        if len(candidates) < sample_per_class:
            raise ValueError(f"Not enough label {label} rows: {len(candidates)}")
        selected.extend(sorted(candidates, key=_rank)[:sample_per_class])
    return sorted(selected, key=lambda row: row["file"].strip())


def audit_audio(path: Path) -> dict:
    """Decode one selected file with explicitly resolved FFmpeg binaries."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,sample_rate,channels:format=duration",
         "-of", "json", str(path)], check=True, capture_output=True, timeout=60,
    )
    parsed = json.loads(probe.stdout)
    streams = parsed.get("streams") or []
    if len(streams) != 1:
        raise ValueError(f"Expected one audio stream: {path.name}")
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", "16000",
         "-f", "f32le", "pipe:1"], check=True, capture_output=True, timeout=120,
    ).stdout
    if not decoded or len(decoded) % 4 or len(decoded) > MAX_PCM_BYTES:
        raise ValueError(f"Invalid decoded PCM size: {path.name}")
    samples = array.array("f")
    samples.frombytes(decoded)
    if sys.byteorder != "little":
        samples.byteswap()
    rms = math.sqrt(math.fsum(float(value) * float(value) for value in samples) / len(samples))
    return {
        "codec": str(streams[0].get("codec_name", "")),
        "sample_rate": int(streams[0].get("sample_rate", 0)),
        "channels": int(streams[0].get("channels", 0)),
        "duration_s": float(parsed.get("format", {}).get("duration", 0.0)),
        "quiet": rms < 0.001,
        "decoded_rms": rms,
    }


def _extract_selected(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo],
                      selected: list[dict[str, str]], audio_dir: Path) -> None:
    audio_dir.mkdir()
    for row in selected:
        filename = row["file"].strip()
        member_name = f"{ROOT}/{filename}"
        info = members.get(member_name)
        if info is None:
            raise ValueError(f"Metadata audio is missing from archive: {filename}")
        destination = audio_dir / filename
        with archive.open(info) as source, destination.open("xb") as target:
            copied = shutil.copyfileobj(source, target, CHUNK)
        if destination.stat().st_size != info.file_size:
            raise ValueError(f"Truncated extracted audio: {filename}")


def stage_archive(archive_path: Path, output_dir: Path, *, sample_per_class: int = 1000,
                  auditor: Callable[[Path], dict] = audit_audio) -> dict:
    archive_path, output = Path(archive_path), Path(output_dir)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    digest = verify_archive(archive_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stage-itw-", dir=output.parent) as temporary:
        temp = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            members = _inventory(archive)
            original_fields, metadata_rows = _metadata(archive, members[f"{ROOT}/meta.csv"])
            selected = _select(metadata_rows, sample_per_class)
            _extract_selected(archive, members, selected, temp / "audio")
            attribution = archive.read(members[f"{ROOT}/attribution.txt"])
            try:
                attribution.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Author attribution is not UTF-8") from exc
            (temp / "attribution.txt").write_bytes(attribution)

        manifest_rows = []
        hashes: dict[str, str] = {}
        codecs = Counter()
        failures = []
        duplicates = []
        quiet_count = 0
        decoded_count = 0
        duration_distribution = {"0": {"lte_30s": 0, "gt_30s": 0, "unavailable": 0},
                                 "1": {"lte_30s": 0, "gt_30s": 0, "unavailable": 0}}
        for index, row in enumerate(selected, 1):
            filename = row["file"].strip()
            path = temp / "audio" / filename
            file_hash = sha256_file(path)
            duplicate_of = hashes.get(file_hash, "")
            if duplicate_of:
                duplicates.append({"file": filename, "duplicate_of": duplicate_of, "sha256": file_hash})
            else:
                hashes[file_hash] = filename
            details: dict = {}
            audit_status = "decoded"
            audit_reason = ""
            try:
                details = auditor(path)
                decoded_count += 1
                if details.get("quiet"):
                    quiet_count += 1
                    audit_status = "quiet"
                    audit_reason = "quiet audio"
                duration = float(details.get("duration_s", 0))
                if duration <= 0:
                    raise ValueError("non-positive duration")
                codecs[str(details.get("codec", "unknown"))] += 1
                duration_distribution[_label(row["label"])]["lte_30s" if duration <= 30 else "gt_30s"] += 1
            except Exception as exc:
                audit_status = "failed"
                audit_reason = str(exc)
                failures.append({"file": filename, "reason": str(exc)})
                duration_distribution[_label(row["label"])]["unavailable"] += 1
            source_id = next((row.get(field, "").strip() for field in ("source_id", "source", "url")
                              if row.get(field, "").strip()), "")
            manifest_rows.append({
                "file_id": Path(filename).stem,
                "path": f"audio/{filename}",
                "label": _label(row["label"]),
                "group_id": row["speaker"].strip(),
                "speaker_id": row["speaker"].strip(),
                "source_id": source_id,
                "attack_id": "",
                "codec": str(details.get("codec", "")),
                "sample_rate": str(details.get("sample_rate", "")),
                "channels": str(details.get("channels", "")),
                "duration_s": str(details.get("duration_s", "")),
                "audit_status": audit_status,
                "audit_reason": audit_reason,
                "duplicate_of": duplicate_of,
                "partition": "external_test",
                "sha256": file_hash,
                "original_metadata_json": json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            })
            if index % 250 == 0:
                print(f"audited {index}/{len(selected)}", flush=True)
        fields = list(manifest_rows[0])
        manifest = temp / "manifest.csv"
        with manifest.open("x", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(manifest_rows)
        source_missing = sum(not row["source_id"] for row in manifest_rows)
        report = {
            "dataset": DATASET,
            "purpose": "locked external evaluation only; never used for training, threshold selection, or calibration",
            "repository_revision": REVISION,
            "repository_api_checked_utc": "2026-09-26",
            "archive": {"name": ARCHIVE_NAME, "url": ARCHIVE_URL, "bytes": ARCHIVE_BYTES, "sha256": digest},
            "selection": {
                "seed": SEED,
                "rule": f"lowest sha256({SEED}:file), {sample_per_class} per class",
                "selected_before_inference": True,
                "model_predictions_inspected": False,
                "rows": len(manifest_rows),
                "labels": dict(sorted(Counter(row["label"] for row in manifest_rows).items())),
                "manifest_sha256": sha256_file(manifest),
            },
            "metadata": {
                "archive_rows": len(metadata_rows),
                "original_columns": original_fields,
                "speaker_id_unique": len({row["speaker_id"] for row in manifest_rows}),
                "speaker_id_missing": sum(not row["speaker_id"] for row in manifest_rows),
                "source_id_unique": len({row["source_id"] for row in manifest_rows if row["source_id"]}),
                "source_id_missing": source_missing,
                "source_note": "Blank means the author metadata did not provide a source identifier; none was inferred.",
                "original_metadata_preserved_in_manifest": True,
                "author_attribution_preserved": True,
                "author_attribution_sha256": hashlib.sha256(attribution).hexdigest(),
            },
            "audit": {
                "decoded": decoded_count, "failures": len(failures), "failure_rows": failures,
                "quiet": quiet_count, "duplicate_content": len(duplicates),
                "duplicate_rows": duplicates, "codecs": dict(sorted(codecs.items())),
                "duration_distribution_by_label": duration_distribution,
                "duration_boundary_seconds": 30,
                "all_selected_rows_preserved": True,
            },
            "independence": {
                "project_training_use": False,
                "project_selection_use": False,
                "upstream_pretraining_overlap": "unknown",
                "note": "External to ECHOTRACE training ledgers only; incomplete upstream checkpoint inventories prevent a universal independence claim.",
            },
            "license": {
                "conservative_handling": "CC BY-SA 4.0 attribution; no audio redistribution",
                "hugging_face_card": "CC BY-SA 4.0",
                "author_project_page": "Apache-2.0",
                "discrepancy": "Author-controlled sources disagree; confirm with the maintainer before redistribution or license-dependent use.",
            },
        }
        (temp / "provenance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"Output already exists: {output}")
        os.rename(temp, output)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-per-class", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        report = stage_archive(args.archive, args.output_dir, sample_per_class=args.sample_per_class)
    except (OSError, ValueError, KeyError, csv.Error, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        parser.exit(2, f"In-the-Wild staging: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
