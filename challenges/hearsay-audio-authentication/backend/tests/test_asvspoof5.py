import csv
import pytest
from echotrace.asvspoof5 import convert_protocol


def test_official_protocol_mapping_preserves_partition_and_metadata(tmp_path):
    src=tmp_path/'protocol.tsv'; out=tmp_path/'manifest.csv'
    src.write_text('T_0001 T_00000001 F - - - - bonafide bonafide -\nT_0001 T_00000002 F C01 1 T_00000001 AC1 A01 spoof -\n')
    result=convert_protocol(src,out,partition='train')
    rows=list(csv.DictReader(out.open()))
    assert [r['label'] for r in rows]==['0','1']
    assert [r['path'] for r in rows]==['flac_T/T_00000001.flac','flac_T/T_00000002.flac']
    assert rows[0]['source_id']==rows[1]['source_id']=='T_00000001'
    assert rows[1]['speaker_id']=='T_0001'
    assert rows[1]['attack_id']=='A01'
    assert result['sample_count']==2 and result['audio_verified'] is False
    assert result['protocol_sha256']


@pytest.mark.parametrize('row',[
 'T_0001 T_01 F - - - - bonafide unknown -',
 'T_0001 ../escape F - - - - bonafide bonafide -',
 'D_0001 D_01 F - - - - bonafide bonafide -',
 'T_0001 T_01 F - - - - bonafide bonafide',
])
def test_rejects_bad_labels_paths_partitions_or_fields_without_output(tmp_path,row):
    src=tmp_path/'p';out=tmp_path/'out';src.write_text(row+'\n')
    with pytest.raises(ValueError): convert_protocol(src,out,partition='train')
    assert not out.exists()


def test_rejects_duplicates_and_preserves_existing_output(tmp_path):
    src=tmp_path/'p';out=tmp_path/'out';row='T_0001 T_01 F - - - - bonafide bonafide -\n'
    src.write_text(row*2)
    with pytest.raises(ValueError): convert_protocol(src,out,partition='train')
    src.write_text(row);out.write_text('keep')
    with pytest.raises(FileExistsError): convert_protocol(src,out,partition='train')
    assert out.read_text()=='keep'


@pytest.mark.parametrize('partition,prefix,folder',[('dev','D','flac_D'),('eval','E','flac_E_eval')])
def test_preserves_dev_and_eval_partitions(tmp_path,partition,prefix,folder):
    src=tmp_path/'p';out=tmp_path/'out'
    src.write_text(f'{prefix}_0001 {prefix}_01 M - - - - bonafide bonafide -\n')
    convert_protocol(src,out,partition=partition)
    assert list(csv.DictReader(out.open()))[0]['path']==f'{folder}/{prefix}_01.flac'


def test_empty_and_unknown_partition_rejected(tmp_path):
    src=tmp_path/'p';out=tmp_path/'out';src.write_text('')
    with pytest.raises(ValueError): convert_protocol(src,out,partition='train')
    with pytest.raises(ValueError): convert_protocol(src,out,partition='test')
