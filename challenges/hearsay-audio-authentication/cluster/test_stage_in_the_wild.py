"""Offline contracts for the locked In-the-Wild external benchmark."""

import csv
import hashlib
import io
import json
import zipfile

import pytest

import stage_in_the_wild as staging


def make_archive(*, unsafe: str | None = None, duplicate: bool = False) -> bytes:
    rows = [
        {"file": "0.wav", "speaker": "alice", "label": "real", "note": "source-a"},
        {"file": "1.wav", "speaker": "alice", "label": "fake", "note": "source-b"},
        {"file": "2.wav", "speaker": "bob", "label": "real", "note": "source-c"},
        {"file": "3.wav", "speaker": "bob", "label": "fake", "note": "source-d"},
        {"file": "4.wav", "speaker": "carol", "label": "real", "note": "source-e"},
        {"file": "5.wav", "speaker": "carol", "label": "fake", "note": "source-f"},
    ]
    meta = io.StringIO()
    writer = csv.DictWriter(meta, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("release_in_the_wild/meta.csv", meta.getvalue())
        archive.writestr("release_in_the_wild/attribution.txt", "Author attribution\n")
        for index, row in enumerate(rows):
            payload = b"same" if duplicate and index in (0, 1) else f"audio-{index}".encode()
            archive.writestr(f"release_in_the_wild/{row['file']}", payload)
        if unsafe:
            if unsafe.endswith("link"):
                member = zipfile.ZipInfo(unsafe)
                member.create_system = 3
                member.external_attr = 0o120777 << 16
                archive.writestr(member, "../../escape.wav")
            else:
                archive.writestr(unsafe, b"escape")
    return output.getvalue()


def fixture(tmp_path, monkeypatch, **archive_options):
    payload = make_archive(**archive_options)
    archive = tmp_path / staging.ARCHIVE_NAME
    archive.write_bytes(payload)
    monkeypatch.setattr(staging, "ARCHIVE_BYTES", len(payload))
    monkeypatch.setattr(staging, "ARCHIVE_SHA256", hashlib.sha256(payload).hexdigest())
    return archive


def successful_audit(path):
    return {
        "codec": "pcm_f32le",
        "sample_rate": 16000,
        "channels": 1,
        "duration_s": 1.25,
        "quiet": False,
    }


def rows(path):
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def test_builds_fixed_balanced_manifest_and_preserves_original_metadata(tmp_path, monkeypatch):
    archive = fixture(tmp_path, monkeypatch)
    output = tmp_path / "staged"

    report = staging.stage_archive(archive, output, sample_per_class=2, auditor=successful_audit)

    manifest = rows(output / "manifest.csv")
    assert (output / "attribution.txt").read_text() == "Author attribution\n"
    assert len(manifest) == 4
    assert {row["label"] for row in manifest} == {"0", "1"}
    assert [row["label"] for row in manifest].count("0") == 2
    assert [row["label"] for row in manifest].count("1") == 2
    assert all(json.loads(row["original_metadata_json"])["note"].startswith("source-") for row in manifest)
    assert all(row["speaker_id"] for row in manifest)
    assert all(row["source_id"] == "" for row in manifest)
    assert all(row["audit_status"] == "decoded" for row in manifest)
    assert all(row["duration_s"] == "1.25" for row in manifest)
    assert report["selection"]["rule"] == "lowest sha256(external-itw-20260926:file), 2 per class"
    assert report["audit"]["decoded"] == 4
    assert report["audit"]["quiet"] == 0
    assert report["metadata"]["source_id_missing"] == 4
    assert report["metadata"]["author_attribution_preserved"] is True
    assert report == json.loads((output / "provenance.json").read_text())


def test_selection_is_deterministic_before_audio_audit(tmp_path, monkeypatch):
    archive = fixture(tmp_path, monkeypatch)
    calls = []

    def auditor(path):
        calls.append(path.name)
        return successful_audit(path)

    staging.stage_archive(archive, tmp_path / "one", sample_per_class=2, auditor=auditor)
    first = [(row["file_id"], row["label"]) for row in rows(tmp_path / "one/manifest.csv")]
    calls.clear()
    staging.stage_archive(archive, tmp_path / "two", sample_per_class=2, auditor=auditor)
    second = [(row["file_id"], row["label"]) for row in rows(tmp_path / "two/manifest.csv")]
    assert first == second
    assert sorted(calls) == sorted(row[0] + ".wav" for row in second)


def test_rejects_corrupt_archive_without_removing_cache(tmp_path, monkeypatch):
    archive = fixture(tmp_path, monkeypatch)
    original = archive.read_bytes()
    monkeypatch.setattr(staging, "ARCHIVE_SHA256", "0" * 64)

    with pytest.raises(ValueError, match="checksum"):
        staging.stage_archive(archive, tmp_path / "staged", sample_per_class=2, auditor=successful_audit)

    assert archive.read_bytes() == original
    assert not (tmp_path / "staged").exists()


@pytest.mark.parametrize("unsafe", ["../escape.wav", "/absolute.wav", "release_in_the_wild/link"])
def test_rejects_unsafe_or_non_audio_members(tmp_path, monkeypatch, unsafe):
    archive = fixture(tmp_path, monkeypatch, unsafe=unsafe)
    with pytest.raises(ValueError, match="Unsafe|Unexpected"):
        staging.stage_archive(archive, tmp_path / "staged", sample_per_class=2, auditor=successful_audit)
    assert archive.exists()
    assert not (tmp_path / "staged").exists()
    assert not (tmp_path / "escape.wav").exists()


def test_preserves_duplicate_selected_audio_with_explicit_status(tmp_path, monkeypatch):
    archive = fixture(tmp_path, monkeypatch, duplicate=True)
    report = staging.stage_archive(archive, tmp_path / "staged", sample_per_class=3, auditor=successful_audit)
    assert archive.exists()
    manifest = rows(tmp_path / "staged/manifest.csv")
    assert len(manifest) == 6
    assert report["audit"]["duplicate_content"] == 1
    assert sum(bool(row["duplicate_of"]) for row in manifest) == 1


def test_preserves_quiet_audio_in_fixed_manifest(tmp_path, monkeypatch):
    archive = fixture(tmp_path, monkeypatch)

    def quiet(path):
        result = successful_audit(path)
        result["quiet"] = path.name == "0.wav"
        return result

    report = staging.stage_archive(archive, tmp_path / "staged", sample_per_class=3, auditor=quiet)
    assert archive.exists()
    manifest = rows(tmp_path / "staged/manifest.csv")
    assert len(manifest) == 6
    quiet_rows = [row for row in manifest if row["audit_status"] == "quiet"]
    assert [row["file_id"] for row in quiet_rows] == ["0"]
    assert quiet_rows[0]["audit_reason"] == "quiet audio"
    assert report["audit"]["quiet"] == 1


def test_preserves_decode_failure_and_marks_duration_unavailable(tmp_path, monkeypatch):
    archive = fixture(tmp_path, monkeypatch)

    def fails(path):
        if path.name == "0.wav":
            raise RuntimeError("decoder rejected fixture")
        return successful_audit(path)

    report = staging.stage_archive(archive, tmp_path / "staged", sample_per_class=3, auditor=fails)
    manifest = rows(tmp_path / "staged/manifest.csv")
    failed = [row for row in manifest if row["audit_status"] == "failed"]
    assert [row["file_id"] for row in failed] == ["0"]
    assert failed[0]["duration_s"] == ""
    assert report["audit"]["failures"] == 1
    assert report["audit"]["duration_distribution_by_label"]["0"]["unavailable"] == 1


def test_rejects_existing_or_symlink_output_before_archive_read(tmp_path, monkeypatch):
    archive = fixture(tmp_path, monkeypatch)
    output = tmp_path / "staged"
    output.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(FileExistsError):
        staging.stage_archive(archive, output, sample_per_class=2, auditor=successful_audit)
    assert output.is_symlink()
