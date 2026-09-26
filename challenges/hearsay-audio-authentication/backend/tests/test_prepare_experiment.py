"""A bounded, reproducible ASVspoof5 preparation must fail closed."""
import csv
import json
from pathlib import Path

import pytest

from echotrace.prepare_experiment import prepare_experiment


FIELDS = ['file_id', 'path', 'label', 'speaker_id', 'source_id',
          'attack_id', 'codec', 'partition']


def fixture_manifests(tmp_path: Path):
    root = tmp_path / 'audio'
    root.mkdir()
    paths = {}
    for partition, prefix, count in [('train', 'T', 8), ('dev', 'D', 12)]:
        rows = []
        for i in range(count):
            file_id = f'{prefix}_{i:04d}'
            audio = root / f'{file_id}.flac'
            audio.write_bytes(file_id.encode())
            rows.append(dict(file_id=file_id, path=audio.name, label=str(i % 2),
                             speaker_id=f'{prefix}_speaker_{i // 2}',
                             source_id=f'{prefix}_source_{i // 2}', attack_id=f'A{i}',
                             codec='flac', partition=partition))
        manifest = tmp_path / f'{partition}.csv'
        write_manifest(manifest, rows)
        paths[partition] = manifest
    return paths['train'], paths['dev'], root


def write_manifest(path, rows, fields=FIELDS):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def test_three_way_deterministic_order_independent_and_metadata_preserved(tmp_path):
    train, dev, root = fixture_manifests(tmp_path)
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    prepare_experiment(train, dev, root, first, seed=17, train_limit=8, dev_limit=12)
    for manifest in (train, dev):
        rows = read_rows(manifest)
        write_manifest(manifest, list(reversed(rows)))
    prepare_experiment(train, dev, root, second, seed=17, train_limit=8, dev_limit=12)
    splits = {}
    for name in ('train', 'selection', 'acceptance'):
        one = read_rows(first / f'{name}.csv')
        two = read_rows(second / f'{name}.csv')
        assert one == two
        assert len(one) > 0
        assert {row['label'] for row in one} == {'0', '1'}
        assert set(one[0]) == set(FIELDS)
        splits[name] = one
    assert {r['partition'] for r in splits['train']} == {'train'}
    assert {r['partition'] for r in splits['selection'] + splits['acceptance']} == {'dev'}
    for column in ('file_id', 'speaker_id', 'source_id'):
        values = [set(row[column] for row in splits[name]) for name in splits]
        assert not any(values[i] & values[j] for i in range(3) for j in range(i + 1, 3))
    report = json.loads((first / 'preparation.json').read_text())
    assert report['seed'] == 17
    assert report['audio_verified'] is True
    assert report['input_sha256']['train'] != report['input_sha256']['dev']
    assert all(report['splits'][name]['sample_count'] == len(splits[name]) for name in splits)


def test_missing_audio_requires_real_bytes_and_leaves_no_output(tmp_path):
    train, dev, root = fixture_manifests(tmp_path)
    (root / 'D_0000.flac').unlink()
    output = tmp_path / 'prepared'
    with pytest.raises((FileNotFoundError, ValueError)):
        prepare_experiment(train, dev, root, output, seed=1, train_limit=8, dev_limit=12)
    assert not output.exists()


def test_existing_output_not_overwritten(tmp_path):
    train, dev, root = fixture_manifests(tmp_path)
    output = tmp_path / 'prepared'
    output.mkdir()
    sentinel = output / 'keep.txt'
    sentinel.write_text('keep')
    with pytest.raises(FileExistsError):
        prepare_experiment(train, dev, root, output, seed=1, train_limit=8, dev_limit=12)
    assert sentinel.read_text() == 'keep'


@pytest.mark.parametrize('value', [0, -1, 1.5, float('nan'), float('inf'), True])
def test_limits_must_be_positive_finite_integers(tmp_path, value):
    train, dev, root = fixture_manifests(tmp_path)
    with pytest.raises(ValueError):
        prepare_experiment(train, dev, root, tmp_path / 'out', train_limit=value)


def test_wrong_partition_rejected(tmp_path):
    train, dev, root = fixture_manifests(tmp_path)
    rows = read_rows(dev)
    rows[0]['partition'] = 'train'
    write_manifest(dev, rows)
    with pytest.raises(ValueError, match='partition'):
        prepare_experiment(train, dev, root, tmp_path / 'out')


def test_missing_group_metadata_rejected(tmp_path):
    train, dev, root = fixture_manifests(tmp_path)
    rows = read_rows(dev)
    for row in rows:
        row['speaker_id'] = row['source_id'] = ''
    write_manifest(dev, rows)
    with pytest.raises(ValueError, match='metadata'):
        prepare_experiment(train, dev, root, tmp_path / 'out')


def test_insufficient_independent_dev_groups_rejected(tmp_path):
    train, dev, root = fixture_manifests(tmp_path)
    rows = read_rows(dev)
    for row in rows:
        row['speaker_id'] = 'one-speaker'
    write_manifest(dev, rows)
    with pytest.raises(ValueError, match='group'):
        prepare_experiment(train, dev, root, tmp_path / 'out')


def test_cross_partition_speaker_rejected(tmp_path):
    train, dev, root = fixture_manifests(tmp_path)
    rows = read_rows(dev)
    rows[0]['speaker_id'] = read_rows(train)[0]['speaker_id']
    write_manifest(dev, rows)
    with pytest.raises(ValueError, match='overlap'):
        prepare_experiment(train, dev, root, tmp_path / 'out', train_limit=8, dev_limit=12)
