"""Convert official ASVspoof 5 track-1 protocols without changing their splits.

Metadata preparation only: this command does not download or verify audio.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

PARTITIONS = {'train': ('T', 'flac_T'), 'dev': ('D', 'flac_D'), 'eval': ('E', 'flac_E_eval')}
FIELDS = ['file_id', 'path', 'label', 'speaker_id', 'source_id', 'attack_id', 'codec', 'partition']


def convert_protocol(protocol: Path, output: Path, *, partition: str) -> dict:
    if partition not in PARTITIONS:
        raise ValueError('partition must be train, dev or eval')
    prefix, folder = PARTITIONS[partition]
    identifier = re.compile(prefix + r'_\d+\Z')
    seen = set()
    labels = Counter()
    speakers = set()
    attacks = Counter()
    digest = hashlib.sha256()
    # Spool validated rows rather than retaining hundreds of thousands of dicts.
    # No requested output is written until the entire source passes validation.
    with tempfile.TemporaryFile(mode='w+', encoding='utf-8', newline='') as staged:
        writer = csv.DictWriter(staged, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        with Path(protocol).open('rb') as source:
            for line_number, raw in enumerate(source, 1):
                digest.update(raw)
                columns = raw.decode('utf-8-sig').split()
                if not columns:
                    continue
                if len(columns) != 10:
                    raise ValueError(f'Line {line_number}: expected 10 protocol fields')
                speaker, file_id, _, codec, _, source_id, _, attack, key, _ = columns
                if not identifier.fullmatch(file_id) or not identifier.fullmatch(speaker):
                    raise ValueError(f'Line {line_number}: invalid ID or wrong partition')
                if source_id != '-' and not identifier.fullmatch(source_id):
                    raise ValueError(f'Line {line_number}: invalid source ID')
                if key not in ('bonafide', 'spoof'):
                    raise ValueError(f'Line {line_number}: unknown label {key!r}')
                if file_id in seen:
                    raise ValueError(f'Line {line_number}: duplicate file ID {file_id}')
                seen.add(file_id)
                speakers.add(speaker)
                labels[key] += 1
                attacks[attack] += 1
                writer.writerow(dict(file_id=file_id, path=f'{folder}/{file_id}.flac',
                                     label=int(key == 'spoof'), speaker_id=speaker,
                                     source_id=file_id if source_id == '-' else source_id,
                                     attack_id=attack, codec=codec, partition=partition))
        if not seen:
            raise ValueError('Empty protocol')
        staged.seek(0)
        # Exclusive creation rejects direct input aliases and existing files.
        with Path(output).open('x', encoding='utf-8', newline='') as destination:
            shutil.copyfileobj(staged, destination)
    return dict(dataset='ASVspoof5', partition=partition, sample_count=len(seen),
                label_counts=dict(labels), speaker_count=len(speakers), attack_counts=dict(attacks),
                protocol_sha256=digest.hexdigest(), audio_verified=False,
                note='Official partition preserved. Run dataset audit after installing audio; no performance result.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('protocol', type=Path)
    parser.add_argument('--partition', required=True, choices=PARTITIONS)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(convert_protocol(args.protocol, args.output, partition=args.partition), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'ASVspoof5 import: {exc}\n')


if __name__ == '__main__':
    main()
