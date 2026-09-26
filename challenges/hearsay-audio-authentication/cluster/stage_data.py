"""Stage the two pinned ASVspoof5 aa archives and matching Track 1 manifest rows.

Only official train/dev metadata is accepted. This is a bounded subset, not a
full-corpus audit. Audio is downloaded on explicit invocation only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import tarfile
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path


PINS = {
    'flac_T_aa.tar': (7522498560, 'b0cc86b14826a7701b52aad4f53daf9c'),
    'flac_D_aa.tar': (6647265280, 'df0be44957623991028cce59792beb17'),
}
ARCHIVE_NAMES = ('flac_T_aa.tar', 'flac_D_aa.tar')
RECORD = '14498691'
CHUNK = 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 50000
MAX_NAME = 255


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding='utf-8'))
    files = data.get('audio_files')
    if not isinstance(files, list):
        raise ValueError('Inventory has no audio_files list')
    if any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in files):
        raise ValueError('Invalid inventory entries')
    by_name = {item['name']: item for item in files}
    if len(by_name) != len(files):
        raise ValueError('Duplicate or invalid inventory entries')
    for name in ARCHIVE_NAMES:
        item = by_name.get(name)
        size, md5 = PINS[name]
        url = f'https://zenodo.org/api/records/{RECORD}/files/{name}/content'
        if not item or item.get('bytes') != size or item.get('checksum') != f'md5:{md5}' or item.get('url') != url:
            raise ValueError(f'Pinned inventory mismatch: {name}')
    return {name: by_name[name] for name in ARCHIVE_NAMES}


def _read_manifest(path: Path, partition: str, folder: str) -> tuple[list[str], list[dict[str, str]]]:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        if fields is None or len(fields) != len(set(fields)):
            raise ValueError(f'Invalid CSV headers: {path}')
        required = {'file_id', 'path', 'label', 'partition'}
        if not required <= set(fields):
            raise ValueError(f'Missing manifest columns: {path}')
        rows = list(reader)
    if not rows:
        raise ValueError(f'Empty {partition} manifest')
    seen = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f'Malformed {partition} manifest row')
        file_id = row['file_id'].strip()
        relative = row['path'].strip()
        prefix = 'T' if partition == 'train' else 'D'
        if (not re.fullmatch(prefix + r'_\d+', file_id)
                or not relative == f'{folder}/{file_id}.flac'):
            raise ValueError(f'Invalid {partition} manifest path or ID: {file_id}')
        if file_id in seen:
            raise ValueError(f'Duplicate {partition} manifest ID: {file_id}')
        seen.add(file_id)
        if row['partition'].strip() != partition:
            raise ValueError(f'Wrong partition for {file_id}')
        if row['label'].strip() not in ('0', '1'):
            raise ValueError(f'Invalid label for {file_id}')
    return fields, rows


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def _open_fixed(url: str, timeout: int):
    return urllib.request.build_opener(_NoRedirect).open(url, timeout=timeout)


def _download(item: dict, destination: Path, opener) -> dict:
    name = item['name']
    expected_size, expected_md5 = PINS[name]
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    with opener(item['url'], timeout=60) as response, destination.open('xb') as target:
        while chunk := response.read(CHUNK):
            size += len(chunk)
            if size > expected_size:
                raise ValueError(f'Archive size exceeds pin: {name}')
            target.write(chunk)
            md5.update(chunk)
            sha256.update(chunk)
    if size != expected_size or md5.hexdigest() != expected_md5:
        raise ValueError(f'Archive size or checksum mismatch: {name}')
    return {'bytes': size, 'md5': md5.hexdigest(), 'sha256': sha256.hexdigest(),
            'url': item['url']}


def _safe_member(member: tarfile.TarInfo, folder: str) -> tuple[str, str] | None:
    name = member.name
    if name.startswith('./'):
        name = name[2:]
    if member.isdir() and name in ('', '.'):
        return None
    parts = name.split('/')
    if (len(name) > MAX_NAME or name.startswith('/') or '\\' in name
            or any(part in ('', '.', '..') for part in parts if part != parts[-1])
            or any(part == '..' for part in parts)):
        raise ValueError(f'Unsafe archive member: {member.name}')
    if member.isdir():
        if name.rstrip('/') != folder:
            raise ValueError(f'Unexpected archive member directory: {member.name}')
        return None
    prefix = 'T' if folder == 'flac_T' else 'D'
    if (not member.isfile() or len(parts) != 2 or parts[0] != folder
            or not re.fullmatch(prefix + r'_\d+\.flac', parts[1])
            or member.size <= 0 or member.size > MAX_MEMBER_BYTES):
        raise ValueError(f'Unsafe archive member: {member.name}')
    return parts[0], parts[1]


def _extract(archive: Path, audio: Path, folder: str) -> set[str]:
    destination = audio / folder
    destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    with tarfile.open(archive, mode='r|') as tar:
        for member in tar:
            safe = _safe_member(member, folder)
            if safe is None:
                continue
            if len(seen) >= MAX_MEMBERS:
                raise ValueError(f'Too many archive members: {archive.name}')
            filename = safe[1]
            if filename in seen:
                raise ValueError(f'Duplicate archive member: {filename}')
            seen.add(filename)
            source = tar.extractfile(member)
            if source is None:
                raise ValueError(f'Cannot read archive member: {filename}')
            remaining = member.size
            with source, (destination / filename).open('xb') as target:
                while remaining:
                    chunk = source.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ValueError(f'Truncated archive member: {filename}')
                    target.write(chunk)
                    remaining -= len(chunk)
    if not seen:
        raise ValueError(f'Archive has no FLAC members: {archive.name}')
    return {f'{folder}/{filename}' for filename in seen}


def _write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def stage_data(inventory_path: Path, train_manifest: Path, dev_manifest: Path,
               output_dir: Path, *, opener=None) -> dict:
    """Download, verify, extract, and publish a fresh bounded T/D subset."""
    inventory_path, train_manifest, dev_manifest = map(Path, (inventory_path, train_manifest, dev_manifest))
    output = Path(output_dir)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Output already exists: {output}')
    inventory = _inventory(inventory_path)
    train_fields, train_rows = _read_manifest(train_manifest, 'train', 'flac_T')
    dev_fields, dev_rows = _read_manifest(dev_manifest, 'dev', 'flac_D')
    if train_fields != dev_fields:
        raise ValueError('Train and dev manifest columns differ')
    opener = opener or _open_fixed
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage-asvspoof5-', dir=output.parent) as temporary:
        temp = Path(temporary)
        audio = temp / 'audio'
        audio.mkdir()
        details = {}
        members = {}
        for name, folder in (('flac_T_aa.tar', 'flac_T'), ('flac_D_aa.tar', 'flac_D')):
            print(f'Staging {name}: download started', file=sys.stderr, flush=True)
            archive_path = temp / name
            details[name] = _download(inventory[name], archive_path, opener)
            print(f'Staging {name}: size and MD5 verified', file=sys.stderr, flush=True)
            members[folder] = _extract(archive_path, audio, folder)
            details[name]['extracted_files'] = len(members[folder])
            archive_path.unlink()
            print(f'Staging {name}: extracted {len(members[folder])} FLAC files', file=sys.stderr, flush=True)
        selected_train = [row for row in train_rows if row['path'] in members['flac_T']]
        selected_dev = [row for row in dev_rows if row['path'] in members['flac_D']]
        if not selected_train or not selected_dev:
            raise ValueError('No official Track 1 manifest rows matched staged audio')
        _write_rows(temp / 'train.csv', train_fields, selected_train)
        _write_rows(temp / 'dev.csv', dev_fields, selected_dev)
        report = {
            'dataset': 'ASVspoof5 Track 1', 'record': f'https://zenodo.org/records/{RECORD}',
            'subset_only': True,
            'note': 'Only the two aa archives were staged; these manifests are filtered subsets of the official train/dev protocols, not a full-corpus audit.',
            'input_manifest_sha256': {'train': _sha256(train_manifest), 'dev': _sha256(dev_manifest)},
            'input_manifest_rows': {'train': len(train_rows), 'dev': len(dev_rows)},
            'staged_manifest_rows': {'train': len(selected_train), 'dev': len(selected_dev)},
            'staged_label_counts': {
                'train': dict(sorted(Counter(row['label'] for row in selected_train).items())),
                'dev': dict(sorted(Counter(row['label'] for row in selected_dev).items()))},
            'archives': details,
            'unmatched_archive_members': {
                'train': len(members['flac_T']) - len(selected_train),
                'dev': len(members['flac_D']) - len(selected_dev)},
        }
        (temp / 'provenance.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        if output.exists() or output.is_symlink():
            raise FileExistsError(f'Output already exists: {output}')
        temp.rename(output)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--train-manifest', type=Path, required=True)
    parser.add_argument('--dev-manifest', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = stage_data(args.inventory, args.train_manifest, args.dev_manifest, args.output_dir)
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        parser.exit(2, f'ASVspoof5 staging: {exc}\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
