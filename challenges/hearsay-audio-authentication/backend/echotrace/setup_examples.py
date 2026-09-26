"""Explicit, reproducible setup for the optional public-pilot audio clips."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import quote, urlsplit


DATASET = "mueller91/MLAAD-tiny"
REVISION = "9143e5ea709575ebab6bec52840a1043aada7bb1"
BASE_URL = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
DATASET_CARD = f"https://huggingface.co/datasets/{DATASET}"
PINNED_ORIGINAL_LICENSE = (
    f"https://huggingface.co/datasets/{DATASET}/blob/{REVISION}/original/LICENSE"
)
MLAAD_CARD = "https://huggingface.co/datasets/mueller91/MLAAD"
CC_BY_NC = "https://creativecommons.org/licenses/by-nc/4.0/"
HF_TERMS = "https://huggingface.co/terms-of-service"

DEFAULT_PROVENANCE = Path(__file__).parents[2] / "reports/public-pilot/provenance.json"
DEFAULT_OUTPUT = Path(__file__).parents[1] / "artifacts/public-pilot"
MAX_CATALOG_BYTES = 1_000_000
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 6_000_000
RECORD_COUNT = 24
DOWNLOAD_TIMEOUT_SECONDS = 30
CHUNK_BYTES = 64 * 1024
PAIRED_ORIGINAL = {
    "file_id": "acbd08fac7031654",
    "path": "original/en/jane_eyre_21_f000371.wav",
    "label": 0,
    "sha256": "acbd08fac7031654ff5a746568a165fed77dc41d5b4c535518f11c90c6a5d3bf",
    "bytes": 269258,
    "url": BASE_URL + "original/en/jane_eyre_21_f000371.wav",
}
_HEX_16 = re.compile(r"[0-9a-f]{16}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class SetupExamplesError(RuntimeError):
    """The pinned example catalog or a download failed validation."""


def expected_url(relative_path: str) -> str:
    """Return the sole allowed download URL for a catalog path."""
    return BASE_URL + quote(relative_path, safe="/")


def _relative_parts(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise SetupExamplesError("catalog path must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SetupExamplesError("catalog path must remain within the output directory")
    if path.as_posix() != value:
        raise SetupExamplesError("catalog path is not canonical")
    return path.parts


def load_catalog(provenance: Path | str = DEFAULT_PROVENANCE) -> list[dict]:
    """Load and strictly validate the checked-in, pinned 24-record manifest."""
    path = Path(provenance)
    try:
        if path.stat().st_size > MAX_CATALOG_BYTES:
            raise SetupExamplesError("provenance file exceeds the size limit")
        data = json.loads(path.read_text(encoding="utf-8"))
    except SetupExamplesError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SetupExamplesError(f"cannot read provenance catalog: {exc}") from exc

    if not isinstance(data, dict) or data.get("dataset") != DATASET:
        raise SetupExamplesError(f"catalog dataset must be {DATASET}")
    if data.get("revision") != REVISION:
        raise SetupExamplesError(f"catalog revision must be {REVISION}")
    records = data.get("files")
    if not isinstance(records, list) or len(records) != RECORD_COUNT:
        raise SetupExamplesError(f"catalog must contain exactly {RECORD_COUNT} files")

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    total = 0
    counts = {0: 0, 1: 0}
    validated: list[dict] = []
    for record in records:
        if not isinstance(record, dict):
            raise SetupExamplesError("each catalog file must be an object")
        file_id = record.get("file_id")
        relative = record.get("path")
        label = record.get("label")
        digest = record.get("sha256")
        size = record.get("bytes")
        parts = _relative_parts(relative)
        if not isinstance(file_id, str) or not _HEX_16.fullmatch(file_id):
            raise SetupExamplesError("catalog file_id must be 16 lowercase hexadecimal characters")
        if file_id in seen_ids or relative in seen_paths:
            raise SetupExamplesError("catalog file IDs and paths must be unique")
        if type(label) is not int or label not in counts:
            raise SetupExamplesError("catalog labels must be 0 or 1")
        expected_root = "original" if label == 0 else "fake"
        if parts[0] != expected_root:
            raise SetupExamplesError("catalog path does not agree with its label")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise SetupExamplesError("catalog SHA-256 must be lowercase hexadecimal")
        if type(size) is not int or not 0 < size <= MAX_FILE_BYTES:
            raise SetupExamplesError("catalog file exceeds the per-file byte limit")
        if record.get("url") != expected_url(relative):
            raise SetupExamplesError("catalog URL is not the pinned dataset URL")
        seen_ids.add(file_id)
        seen_paths.add(relative)
        counts[label] += 1
        total += size
        validated.append(dict(record))
    if counts != {0: 12, 1: 12}:
        raise SetupExamplesError("catalog must contain 12 genuine and 12 synthetic clips")
    if total > MAX_TOTAL_BYTES:
        raise SetupExamplesError("catalog exceeds the total download byte limit")
    return validated


DELIVERY_HOSTS = frozenset({
    "us.aws.cdn.hf.co",
    "eu.aws.cdn.hf.co",
    "cdn-lfs.hf.co",
    "cdn-lfs-us-1.hf.co",
    "cdn-lfs-eu-1.hf.co",
    "cas-bridge.xethub.hf.co",
})


class _PinnedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        source = urlsplit(req.full_url)
        target = urlsplit(newurl)
        source_path = f"/datasets/{DATASET}/resolve/{REVISION}/"
        permitted = (
            code == 302
            and source.scheme == "https"
            and source.hostname == "huggingface.co"
            and source.port is None
            and source.path.startswith(source_path)
            and target.scheme == "https"
            and target.hostname in DELIVERY_HOSTS
            and target.port is None
            and target.username is None
            and target.password is None
            and not target.fragment
        )
        if not permitted:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_PinnedRedirect)


def _open_fixed_url(url: str, timeout: int):
    request = urllib.request.Request(url, headers={"User-Agent": "ECHOTRACE-example-setup/1"})
    return _OPENER.open(request, timeout=timeout)


def _verified_existing(path: Path, record: dict) -> bool:
    if path.is_symlink():
        raise SetupExamplesError(f"refusing symbolic link output: {record['path']}")
    if not path.exists():
        return False
    if not path.is_file():
        raise SetupExamplesError(f"refusing non-file output: {record['path']}")
    if path.stat().st_size != record["bytes"]:
        raise SetupExamplesError(f"refusing to overwrite existing file: {record['path']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record["sha256"]:
        raise SetupExamplesError(f"refusing to overwrite existing file: {record['path']}")
    return True


def _safe_parent(root: Path, parts: tuple[str, ...]) -> Path:
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise SetupExamplesError(f"refusing symbolic link directory: {current}")
        if current.exists() and not current.is_dir():
            raise SetupExamplesError(f"output directory component is not a directory: {current}")
        current.mkdir(mode=0o700, exist_ok=True)
    return current


def _download_one(target: Path, record: dict, transport: Callable) -> None:
    partial = target.with_name(target.name + ".part")
    if partial.exists() or partial.is_symlink():
        raise SetupExamplesError(f"refusing existing partial file: {partial.name}")
    descriptor = None
    try:
        descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            digest = hashlib.sha256()
            received = 0
            with transport(record["url"], DOWNLOAD_TIMEOUT_SECONDS) as response:
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        advertised = int(content_length)
                    except (TypeError, ValueError) as exc:
                        raise SetupExamplesError("download returned an invalid Content-Length") from exc
                    if advertised != record["bytes"]:
                        raise SetupExamplesError("download differs from the declared byte size")
                while True:
                    chunk = response.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > record["bytes"]:
                        raise SetupExamplesError("download exceeds the declared byte size")
                    output.write(chunk)
                    digest.update(chunk)
            if received != record["bytes"]:
                raise SetupExamplesError("download differs from the declared byte size")
            if digest.hexdigest() != record["sha256"]:
                raise SetupExamplesError("download failed SHA-256 verification")
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(partial, target)
        except FileExistsError as exc:
            raise SetupExamplesError(f"refusing to overwrite existing file: {record['path']}") from exc
    except SetupExamplesError:
        raise
    except (OSError, ValueError) as exc:
        raise SetupExamplesError(f"download failed for {record['path']}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            partial.unlink()
        except FileNotFoundError:
            pass


def setup_examples(
    destination: Path | str = DEFAULT_OUTPUT,
    provenance: Path | str = DEFAULT_PROVENANCE,
    *,
    transport: Callable | None = None,
) -> dict:
    """Download the pinned examples after validating every byte and hash."""
    records = load_catalog(provenance)
    root = Path(destination)
    if root.is_symlink():
        raise SetupExamplesError(f"refusing symbolic link output directory: {root}")
    if root.exists() and not root.is_dir():
        raise SetupExamplesError(f"output path is not a directory: {root}")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    fetch = transport or _open_fixed_url
    downloaded = 0
    skipped = 0
    for record in records:
        parts = _relative_parts(record["path"])
        parent = _safe_parent(root, parts[:-1])
        target = parent / parts[-1]
        if _verified_existing(target, record):
            skipped += 1
            continue
        _download_one(target, record, fetch)
        downloaded += 1
    return {
        "dataset": DATASET,
        "revision": REVISION,
        "files": len(records),
        "bytes": sum(record["bytes"] for record in records),
        "downloaded": downloaded,
        "skipped": skipped,
    }


def setup_paired_reference(destination: Path | str = DEFAULT_OUTPUT, *, transport: Callable | None = None) -> dict:
    """Prepare the verified same-passage human reference outside the fixed 24-file pilot."""
    root = Path(destination)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise SetupExamplesError(f"invalid paired-example output directory: {root}")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    record = PAIRED_ORIGINAL
    parts = _relative_parts(record["path"])
    target = _safe_parent(root, parts[:-1]) / parts[-1]
    if _verified_existing(target, record):
        return {"paired_original": "ready", "downloaded": 0}
    _download_one(target, record, transport or _open_fixed_url)
    return {"paired_original": "ready", "downloaded": 1}


def _source_notice() -> str:
    return f"""Optional public examples come from {DATASET} at pinned revision {REVISION}.
--include-paired-reference adds one human reading of the same Jane Eyre passage as
the Chatterbox-generated pilot clip. It is separate from the fixed 24-file sample.
The dataset card labels the collection CC BY-NC 4.0 and separately identifies the
M-AILABS-derived genuine audio. Review the source and license materials yourself:
  Dataset card: {DATASET_CARD}
  Pinned original-audio license: {PINNED_ORIGINAL_LICENSE}
  MLAAD attribution/card: {MLAAD_CARD}
  CC BY-NC 4.0: {CC_BY_NC}
  Hugging Face terms: {HF_TERMS}
Passing --confirm-source-review only confirms that you reviewed these links and chose
to download. This tool does not accept or determine legal terms for you."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download ECHOTRACE's pinned public examples")
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--confirm-source-review", action="store_true")
    parser.add_argument("--include-paired-reference", action="store_true", help="Also prepare the same-passage human comparison clip")
    args = parser.parse_args(argv)
    print(_source_notice(), file=sys.stderr)
    if not args.confirm_source_review:
        print("Re-run with --confirm-source-review to start the bounded download.", file=sys.stderr)
        return 2
    try:
        result = setup_examples(args.output, args.provenance)
        if args.include_paired_reference:
            result["paired_reference"] = setup_paired_reference(args.output)
    except SetupExamplesError as exc:
        print(f"ECHOTRACE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
