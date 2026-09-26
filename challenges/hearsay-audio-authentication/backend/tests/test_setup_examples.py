import hashlib
import json
from pathlib import Path

import pytest

from echotrace.setup_examples import (
    DATASET,
    REVISION,
    _PinnedRedirect,
    SetupExamplesError,
    expected_url,
    load_catalog,
    main,
    setup_examples,
    setup_paired_reference,
)
import echotrace.setup_examples as example_setup
from urllib.request import Request


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.offset = 0
        self.headers = {"Content-Length": str(len(content))}

    def read(self, size: int) -> bytes:
        chunk = self.content[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def catalog_fixture(tmp_path: Path):
    records = []
    content = {}
    for index in range(24):
        relative = (
            f"original/en/genuine_{index:02}.wav" if index < 12
            else f"fake/en/TestTTS/synthetic_{index:02}.wav"
        )
        payload = f"audio-{index}".encode()
        url = expected_url(relative)
        content[url] = payload
        records.append({
            "file_id": f"{index:016x}",
            "path": relative,
            "label": 0 if index < 12 else 1,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "url": url,
        })
    provenance = tmp_path / "provenance.json"
    provenance.write_text(json.dumps({
        "dataset": DATASET,
        "revision": REVISION,
        "seed": 42,
        "files": records,
    }))
    return provenance, records, content


def test_catalog_requires_exact_pinned_24_record_contract(tmp_path):
    provenance, records, _ = catalog_fixture(tmp_path)
    loaded = load_catalog(provenance)
    assert len(loaded) == 24
    assert {item["label"] for item in loaded} == {0, 1}

    for mutation in (
        lambda data: data.update(dataset="other/repository"),
        lambda data: data.update(revision="main"),
        lambda data: data["files"].pop(),
        lambda data: data["files"][0].update(path="../escape.wav"),
        lambda data: data["files"][0].update(path="original\\escape.wav"),
        lambda data: data["files"][0].update(url="https://attacker.example/audio.wav"),
        lambda data: data["files"][0].update(bytes=2_000_000),
    ):
        data = json.loads(provenance.read_text())
        mutation(data)
        bad = tmp_path / f"bad-{len(list(tmp_path.iterdir()))}.json"
        bad.write_text(json.dumps(data))
        with pytest.raises(SetupExamplesError):
            load_catalog(bad)


def test_setup_streams_fixed_urls_and_verifies_bytes_and_hashes(tmp_path):
    provenance, records, content = catalog_fixture(tmp_path)
    calls = []

    def transport(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(content[url])

    destination = tmp_path / "examples"
    result = setup_examples(destination, provenance, transport=transport)

    assert result["downloaded"] == 24
    assert result["skipped"] == 0
    assert result["files"] == 24
    assert {url for url, timeout in calls if timeout == 30} == set(content)
    for record in records:
        path = destination.joinpath(*record["path"].split("/"))
        assert path.read_bytes() == content[record["url"]]
        assert not path.with_name(path.name + ".part").exists()


def test_paired_original_is_verified_separately_from_fixed_pilot(tmp_path, monkeypatch):
    payload = b"same-passage human reference"
    record = {
        "path": "original/en/jane_eyre_21_f000371.wav",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "url": expected_url("original/en/jane_eyre_21_f000371.wav"),
    }
    monkeypatch.setattr(example_setup, "PAIRED_ORIGINAL", record)
    destination = tmp_path / "examples"
    first = setup_paired_reference(destination, transport=lambda url, timeout: FakeResponse(payload))
    second = setup_paired_reference(destination, transport=lambda url, timeout: pytest.fail("verified file triggered network"))
    assert first["downloaded"] == 1
    assert second["downloaded"] == 0
    assert (destination / record["path"]).read_bytes() == payload


def test_correct_existing_files_skip_network_but_wrong_files_are_never_overwritten(tmp_path):
    provenance, records, content = catalog_fixture(tmp_path)
    destination = tmp_path / "examples"
    setup_examples(destination, provenance, transport=lambda url, timeout: FakeResponse(content[url]))

    second = setup_examples(
        destination,
        provenance,
        transport=lambda url, timeout: pytest.fail("verified existing file triggered network"),
    )
    assert second["downloaded"] == 0
    assert second["skipped"] == 24

    wrong = destination.joinpath(*records[0]["path"].split("/"))
    wrong.write_bytes(b"wrong")
    with pytest.raises(SetupExamplesError, match="refusing to overwrite"):
        setup_examples(destination, provenance, transport=lambda url, timeout: FakeResponse(content[url]))
    assert wrong.read_bytes() == b"wrong"


def test_download_overrun_or_hash_mismatch_is_removed_without_partial_output(tmp_path):
    provenance, records, content = catalog_fixture(tmp_path)
    first = records[0]
    destination = tmp_path / "examples"

    def oversized(url, timeout):
        payload = content[url] + (b"extra" if url == first["url"] else b"")
        return FakeResponse(payload)

    with pytest.raises(SetupExamplesError, match="declared byte size"):
        setup_examples(destination, provenance, transport=oversized)
    target = destination.joinpath(*first["path"].split("/"))
    assert not target.exists()
    assert not target.with_name(target.name + ".part").exists()

    def wrong_hash(url, timeout):
        payload = b"x" * len(content[url]) if url == first["url"] else content[url]
        return FakeResponse(payload)

    with pytest.raises(SetupExamplesError, match="SHA-256"):
        setup_examples(tmp_path / "hash-examples", provenance, transport=wrong_hash)


def test_destination_symlinks_are_rejected(tmp_path):
    provenance, _, content = catalog_fixture(tmp_path)
    destination = tmp_path / "examples"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (destination / "original").symlink_to(outside, target_is_directory=True)

    with pytest.raises(SetupExamplesError, match="symbolic link"):
        setup_examples(destination, provenance, transport=lambda url, timeout: FakeResponse(content[url]))
    assert list(outside.iterdir()) == []


def test_cli_requires_source_review_without_claiming_legal_acceptance(tmp_path, capsys):
    provenance, _, _ = catalog_fixture(tmp_path)
    result = main(["--provenance", str(provenance), "--output", str(tmp_path / "examples")])
    output = capsys.readouterr()
    assert result == 2
    assert "--confirm-source-review" in output.err
    assert "does not accept or determine legal terms" in output.err
    assert "CC BY-NC 4.0" in output.err


def test_redirects_are_limited_to_one_https_hugging_face_delivery_hop():
    handler = _PinnedRedirect()
    origin = Request(expected_url("original/en/example.wav"))
    delivery = "https://us.aws.cdn.hf.co/xet-bridge-us/content?Signature=example"

    redirected = handler.redirect_request(origin, None, 302, "Found", {}, delivery)
    assert redirected.full_url == delivery
    assert handler.redirect_request(
        origin, None, 302, "Found", {}, "https://attacker.example/content"
    ) is None
    assert handler.redirect_request(
        origin, None, 302, "Found", {}, "http://us.aws.cdn.hf.co/content"
    ) is None
    assert handler.redirect_request(redirected, None, 302, "Found", {}, delivery) is None
