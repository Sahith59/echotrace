"""Prevent related speakers/sources from leaking into development evaluation."""
import csv
from echotrace.evaluation import load_manifest, grouped_split


def test_manifest_retains_speaker_and_source_links(tmp_path):
    audio = tmp_path / 'a.wav'
    audio.write_bytes(b'fixture, not audio inference')
    manifest = tmp_path / 'manifest.csv'
    with manifest.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['file_id', 'path', 'label', 'speaker_id', 'source_id'])
        writer.writerow(['a', 'a.wav', 0, ' speaker-a ', ' source-a '])
    record = load_manifest(manifest, tmp_path)[0]
    assert record.get('speaker_id') == 'speaker-a'
    assert record.get('source_id') == 'source-a'


def test_speaker_source_transitive_links_never_cross_splits():
    records = [dict(file_id=str(i), label=i % 2, group_id='', sha256=f'h{i}',
                    speaker_id='', source_id='') for i in range(12)]
    records[0]['speaker_id'] = records[1]['speaker_id'] = 'speaker-a'
    records[1]['source_id'] = records[2]['source_id'] = 'source-a'
    for seed in range(20):
        split = grouped_split(records, validation_fraction=.4, random_state=seed)
        for partition in split.values():
            assert len(set(partition) & {'0', '1', '2'}) in (0, 3)


def test_split_membership_is_independent_of_manifest_order():
    records = [dict(file_id=str(i), label=i % 2, group_id=f'g{i}', sha256=f'h{i}')
               for i in range(12)]
    first = grouped_split(records, random_state=7)
    second = grouped_split(list(reversed(records)), random_state=7)
    assert set(first['validation_ids']) == set(second['validation_ids'])
