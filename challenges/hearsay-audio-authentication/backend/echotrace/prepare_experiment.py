"""Prepare bounded, audio-verified three-way ASVspoof5 experiment manifests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from .evaluation import _rows, grouped_split, load_manifest

REQUIRED = {'file_id', 'path', 'label', 'partition'}
GROUP_COLUMNS = ('group_id', 'speaker_id', 'source_id')
PILOT_PROVENANCE = Path(__file__).resolve().parents[2] / 'reports' / 'public-pilot' / 'provenance.json'


def _positive_limit(value: int, ceiling: int, name: str) -> int:
    if type(value) is not int or not 0 < value <= ceiling:
        raise ValueError(f'{name} must be a positive integer <= {ceiling}')
    return value


def _input(path: Path, partition: str) -> tuple[list[str], list[dict[str, str]]]:
    fields, rows = _rows(path, REQUIRED)
    if not rows:
        raise ValueError(f'Empty {partition} manifest')
    if not any(column in fields for column in GROUP_COLUMNS):
        raise ValueError('Manifest requires speaker/source/group metadata')
    ids = set()
    for row in rows:
        file_id = row['file_id'].strip()
        if not file_id or file_id in ids:
            raise ValueError(f'Blank or duplicate file_id in {partition} manifest')
        ids.add(file_id)
        if row['partition'].strip() != partition:
            raise ValueError(f'Wrong partition in {partition} manifest: {file_id}')
        if row['label'].strip() not in ('0', '1'):
            raise ValueError(f'Invalid label in {partition} manifest: {file_id}')
        if not any(row.get(column, '').strip() for column in GROUP_COLUMNS):
            raise ValueError(f'Missing group metadata: {file_id}')
    return fields, rows


def _select(rows: list[dict[str, str]], *, seed: int, limit: int, partition: str) -> list[dict[str, str]]:
    """Stable class-stratified rank; no manifest row order enters membership."""
    ranked = {}
    for label in ('0', '1'):
        candidates = (row for row in rows if row['label'].strip() == label)
        ranked[label] = sorted(candidates, key=lambda row: (
            hashlib.sha256(f'{seed}:{partition}:{row["file_id"].strip()}'.encode()).hexdigest(),
            row['file_id'].strip()))
    if not ranked['0'] or not ranked['1'] or limit < 2:
        raise ValueError(f'Insufficient classes or limit for {partition}')
    # Allocate half to each class, then fill any remaining capacity by rank.
    target = min(limit, len(rows))
    quota = target // 2
    selected = ranked['0'][:quota] + ranked['1'][:quota]
    selected_ids = {row['file_id'] for row in selected}
    extras = sorted((row for label in ('0', '1') for row in ranked[label]
                     if row['file_id'] not in selected_ids), key=lambda row: (
                         hashlib.sha256(f'{seed}:{partition}:{row["file_id"].strip()}'.encode()).hexdigest(),
                         row['file_id'].strip()))
    selected.extend(extras[:target - len(selected)])
    return sorted(selected, key=lambda row: row['file_id'].strip())


def _pilot_exclusions() -> tuple[set[str], set[str]]:
    data = json.loads(PILOT_PROVENANCE.read_text(encoding='utf-8'))
    files = data['files']
    if data.get('dataset') != 'mueller91/MLAAD-tiny' or len(files) != 24:
        raise ValueError('Pinned 24-recording provenance is unavailable or invalid')
    return ({row['file_id'] for row in files}, {row['sha256'] for row in files})


def _summary(records: list[dict]) -> dict:
    hashes = sorted({record['sha256'] for record in records})
    return {'sample_count': len(records),
            'label_counts': dict(sorted(Counter(str(row['label']) for row in records).items())),
            'unique_audio_hashes': len(hashes), 'sha256_slice': hashes[:8]}


def _assert_disjoint(splits: dict[str, list[dict]]) -> None:
    for column in ('file_id', 'sha256', *GROUP_COLUMNS):
        values = {name: {str(row.get(column, '')).strip() for row in records
                         if str(row.get(column, '')).strip()} for name, records in splits.items()}
        names = list(values)
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                if values[left] & values[right]:
                    raise ValueError(f'{column} overlap between {left} and {right}')
    for name, records in splits.items():
        if {row['label'] for row in records} != {0, 1}:
            raise ValueError(f'{name} requires both classes')


def prepare_experiment(train_manifest: Path, dev_manifest: Path, dataset_root: Path,
                       output_dir: Path, *, seed: int = 42, train_limit: int = 30000,
                       dev_limit: int = 10000) -> dict:
    """Select bounded official T/D rows; divide D into selection and locked acceptance."""
    train_limit = _positive_limit(train_limit, 30000, 'train_limit')
    dev_limit = _positive_limit(dev_limit, 10000, 'dev_limit')
    if type(seed) is not int or not -(2**63) <= seed < 2**63:
        raise ValueError('seed must be a signed 64-bit integer')
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    train_manifest, dev_manifest = Path(train_manifest), Path(dev_manifest)
    fields_t, rows_t = _input(train_manifest, 'train')
    fields_d, rows_d = _input(dev_manifest, 'dev')
    if fields_t != fields_d:
        raise ValueError('Train and dev manifest columns must match')
    chosen_t = _select(rows_t, seed=seed, limit=train_limit, partition='train')
    chosen_d = _select(rows_d, seed=seed, limit=dev_limit, partition='dev')
    pilot_ids, pilot_hashes = _pilot_exclusions()
    if pilot_ids & {row['file_id'] for row in chosen_t + chosen_d}:
        raise ValueError('Pinned 24-recording IDs are excluded')
    # load_manifest verifies actual bytes for exactly the selected subset.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=output.parent) as staging:
        stage = Path(staging)
        for name, rows in (('selected_train', chosen_t), ('selected_dev', chosen_d)):
            with (stage / f'{name}.csv').open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields_t, lineterminator='\n')
                writer.writeheader()
                writer.writerows(rows)
        verified_t = load_manifest(stage / 'selected_train.csv', dataset_root)
        verified_d = load_manifest(stage / 'selected_dev.csv', dataset_root)
        if pilot_hashes & {r['sha256'] for r in verified_t + verified_d}:
            raise ValueError('Pinned 24-recording audio hashes are excluded')
        if len(verified_d) < 4:
            raise ValueError('Insufficient independent dev groups for a two-class split')
        # grouped_split resolves transitive speaker/source/group/content links.
        split = grouped_split(verified_d, validation_fraction=0.5, random_state=seed)
        # Preserve every original CSV field; membership follows verified IDs.
        selection_ids = set(split['train_ids'])
        acceptance_ids = set(split['validation_ids'])
        selection_rows = [row for row in chosen_d if row['file_id'] in selection_ids]
        acceptance_rows = [row for row in chosen_d if row['file_id'] in acceptance_ids]
        verified_by_id = {row['file_id']: row for row in verified_d}
        sets = {'train': verified_t,
                'selection': [verified_by_id[row['file_id']] for row in selection_rows],
                'acceptance': [verified_by_id[row['file_id']] for row in acceptance_rows]}
        _assert_disjoint(sets)
        report = {'dataset': 'ASVspoof5', 'seed': seed,
                  'limits': {'train': train_limit, 'dev': dev_limit},
                  'input_sha256': {'train': hashlib.sha256(train_manifest.read_bytes()).hexdigest(),
                                   'dev': hashlib.sha256(dev_manifest.read_bytes()).hexdigest()},
                  'input_row_counts': {'train': len(rows_t), 'dev': len(rows_d)},
                  'audio_verified': True, 'audio_verification_scope': 'selected_subset_only',
                  'pinned_24_excluded': True,
                  'splits': {name: _summary(records) for name, records in sets.items()}}
        for name, rows in (('train', chosen_t), ('selection', selection_rows),
                           ('acceptance', acceptance_rows)):
            with (stage / f'{name}.csv').open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields_t, lineterminator='\n')
                writer.writeheader()
                writer.writerows(rows)
        (stage / 'preparation.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        (stage / 'selected_train.csv').unlink()
        (stage / 'selected_dev.csv').unlink()
        stage.rename(output)
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-manifest', required=True, type=Path)
    parser.add_argument('--dev-manifest', required=True, type=Path)
    parser.add_argument('--dataset-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--train-limit', type=int, default=30000)
    parser.add_argument('--dev-limit', type=int, default=10000)
    args = parser.parse_args(argv)
    try:
        result = prepare_experiment(args.train_manifest, args.dev_manifest, args.dataset_root,
                                    args.output_dir, seed=args.seed, train_limit=args.train_limit,
                                    dev_limit=args.dev_limit)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Experiment preparation: {exc}\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
