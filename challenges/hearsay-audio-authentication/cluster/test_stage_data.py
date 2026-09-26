"""Offline contracts for bounded, fail-closed ASVspoof5 archive staging."""
import csv
import hashlib
import io
import json
import tarfile

import pytest

import stage_data as staging


FIELDS = ['file_id', 'path', 'label', 'speaker_id', 'source_id',
          'attack_id', 'codec', 'partition']


def archive(folder, names, *, unsafe=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as tar:
        for name in names:
            content = name.encode()
            member = tarfile.TarInfo(f'{folder}/{name}.flac')
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
        if unsafe:
            member = tarfile.TarInfo(unsafe)
            member.type = tarfile.SYMTYPE if unsafe.endswith('link') else tarfile.REGTYPE
            member.linkname = '../../escape'
            member.size = 0
            tar.addfile(member, io.BytesIO())
    return buffer.getvalue()


def manifest(path, partition, prefix):
    rows = []
    for i in (1, 2, 3):
        file_id = f'{prefix}_{i:04d}'
        rows.append(dict(file_id=file_id, path=f'flac_{prefix}/{file_id}.flac',
                         label=str(i % 2), speaker_id=f'{prefix}_s{i}',
                         source_id=f'{prefix}_x{i}', attack_id='A1', codec='C1',
                         partition=partition))
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def fixture(tmp_path, monkeypatch, *, unsafe=None, extra_dev=False):
    archives = {'flac_T_aa.tar': archive('flac_T', ['T_0001', 'T_0002'], unsafe=unsafe),
                'flac_D_aa.tar': archive('flac_D', ['D_0001', 'D_0002'] + (['D_9999'] if extra_dev else []))}
    pins = {name: (len(data), hashlib.md5(data).hexdigest()) for name, data in archives.items()}
    monkeypatch.setattr(staging, 'PINS', pins)
    inventory = tmp_path / 'inventory.json'
    inventory.write_text(json.dumps({'audio_files': [
        {'name': name, 'bytes': len(data), 'checksum': f'md5:{pins[name][1]}',
         'url': f'https://zenodo.org/api/records/14498691/files/{name}/content'}
        for name, data in archives.items()]}))
    train = tmp_path / 'official_train.csv'
    dev = tmp_path / 'official_dev.csv'
    manifest(train, 'train', 'T')
    manifest(dev, 'dev', 'D')

    def open_fixture(url, timeout):
        assert timeout > 0
        name = url.split('/')[-2]
        return io.BytesIO(archives[name])

    return inventory, train, dev, open_fixture


def read_rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def test_stages_only_two_pinned_archives_and_filters_official_rows(tmp_path, monkeypatch):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'staged'
    report = staging.stage_data(inventory, train, dev, output, opener=opener)
    assert {p.name for p in output.iterdir()} == {'audio', 'train.csv', 'dev.csv', 'provenance.json'}
    assert (output / 'audio/flac_T/T_0001.flac').read_bytes() == b'T_0001'
    assert (output / 'audio/flac_D/D_0002.flac').read_bytes() == b'D_0002'
    assert len(read_rows(output / 'train.csv')) == 2
    assert len(read_rows(output / 'dev.csv')) == 2
    assert set(read_rows(output / 'train.csv')[0]) == set(FIELDS)
    assert {r['partition'] for r in read_rows(output / 'train.csv')} == {'train'}
    assert report['subset_only'] is True
    assert report['archives']['flac_T_aa.tar']['extracted_files'] == 2
    assert report['archives']['flac_D_aa.tar']['md5'] == staging.PINS['flac_D_aa.tar'][1]
    assert report == json.loads((output / 'provenance.json').read_text())


def test_rejects_existing_output_before_download(tmp_path, monkeypatch):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'staged'
    output.mkdir()
    (output / 'keep').write_text('keep')
    with pytest.raises(FileExistsError):
        staging.stage_data(inventory, train, dev, output, opener=opener)
    assert (output / 'keep').read_text() == 'keep'


def test_rejects_bad_archive_checksum_without_publishing(tmp_path, monkeypatch):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch)
    def corrupted(url, timeout):
        data = opener(url, timeout).read()
        return io.BytesIO(data + b'wrong')
    output = tmp_path / 'staged'
    with pytest.raises(ValueError, match='size|checksum'):
        staging.stage_data(inventory, train, dev, output, opener=corrupted)
    assert not output.exists()


def test_rejects_same_size_corruption_by_md5(tmp_path, monkeypatch):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch)
    def corrupted(url, timeout):
        data = bytearray(opener(url, timeout).read())
        data[-1] ^= 1
        return io.BytesIO(data)
    output = tmp_path / 'staged'
    with pytest.raises(ValueError, match='checksum'):
        staging.stage_data(inventory, train, dev, output, opener=corrupted)
    assert not output.exists()


def test_rejects_dangling_symlink_output_before_download(tmp_path, monkeypatch):
    inventory, train, dev, _ = fixture(tmp_path, monkeypatch)
    output = tmp_path / 'staged'
    output.symlink_to(tmp_path / 'missing-target', target_is_directory=True)
    calls = []
    def forbidden(url, timeout):
        calls.append(url)
        raise AssertionError('download should not start')
    with pytest.raises(FileExistsError):
        staging.stage_data(inventory, train, dev, output, opener=forbidden)
    assert calls == []
    assert output.is_symlink()


@pytest.mark.parametrize('unsafe', ['../../escape.flac', 'flac_T/evil-link'])
def test_rejects_traversal_and_link_members(tmp_path, monkeypatch, unsafe):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch, unsafe=unsafe)
    output = tmp_path / 'staged'
    with pytest.raises(ValueError, match='archive member'):
        staging.stage_data(inventory, train, dev, output, opener=opener)
    assert not output.exists()
    assert not (tmp_path / 'escape.flac').exists()


def test_rejects_wrong_official_partition(tmp_path, monkeypatch):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch)
    rows = read_rows(dev)
    rows[0]['partition'] = 'train'
    with dev.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match='partition'):
        staging.stage_data(inventory, train, dev, tmp_path / 'staged', opener=opener)


def test_reports_dev_archive_members_outside_track1_manifest(tmp_path, monkeypatch):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch, extra_dev=True)
    report = staging.stage_data(inventory, train, dev, tmp_path / 'staged', opener=opener)
    assert report['unmatched_archive_members']['dev'] == 1
    assert report['staged_manifest_rows']['dev'] == 2


def test_rejects_inventory_url_changed_from_fixed_zenodo_record(tmp_path, monkeypatch):
    inventory, train, dev, opener = fixture(tmp_path, monkeypatch)
    data = json.loads(inventory.read_text())
    data['audio_files'][0]['url'] = 'https://example.com/other.tar'
    inventory.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Pinned inventory mismatch'):
        staging.stage_data(inventory, train, dev, tmp_path / 'staged', opener=opener)
