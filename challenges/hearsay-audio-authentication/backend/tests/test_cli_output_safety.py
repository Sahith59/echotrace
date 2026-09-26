"""CLI outputs must not replace source files used by the same command."""

import json
import os

import pytest

from echotrace.cli import main


def _manifest(tmp_path, *, labeled=False):
    audio = tmp_path / "source.wav"
    audio.write_bytes(b"audio fixture")
    manifest = tmp_path / "manifest.csv"
    header = "file_id,path,label\n" if labeled else "file_id,path\n"
    row = "clip,source.wav,0\n" if labeled else "clip,source.wav\n"
    if labeled:
        (tmp_path / "synthetic.wav").write_bytes(b"synthetic fixture")
        row += "synthetic,synthetic.wav,1\n"
    manifest.write_text(header + row)
    return manifest, audio


@pytest.mark.parametrize("input_name", ["manifest", "audio"])
@pytest.mark.parametrize("alias_kind", ["direct", "symlink", "hardlink"])
def test_batch_rejects_output_alias_of_source(tmp_path, monkeypatch, input_name, alias_kind, capsys):
    manifest, audio = _manifest(tmp_path)
    source = manifest if input_name == "manifest" else audio
    output = source
    if alias_kind == "symlink":
        output = tmp_path / "alias.csv"
        output.symlink_to(source)
    elif alias_kind == "hardlink":
        output = tmp_path / "alias.csv"
        os.link(source, output)
    original = source.read_bytes()
    monkeypatch.setattr("echotrace.pipeline.analyze_file", lambda path: pytest.fail("scoring started"))

    assert main(["batch", str(manifest), "--root", str(tmp_path), "--output", str(output)]) == 2
    assert source.read_bytes() == original
    assert "output" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("source_kind", ["manifest", "audio"])
def test_batch_rejects_sidecar_alias_of_source(tmp_path, monkeypatch, source_kind):
    manifest, audio = _manifest(tmp_path)
    source = manifest if source_kind == "manifest" else audio
    output = tmp_path / "scores.csv"
    sidecar = output.with_suffix(".run.json")
    os.link(source, sidecar)
    original = source.read_bytes()
    monkeypatch.setattr("echotrace.pipeline.analyze_file", lambda path: pytest.fail("scoring started"))

    assert main(["batch", str(manifest), "--root", str(tmp_path), "--output", str(output)]) == 2
    assert source.read_bytes() == original
    assert not output.exists()


def test_score_rejects_output_hardlink_to_audio(tmp_path, monkeypatch):
    audio = tmp_path / "source.wav"
    audio.write_bytes(b"audio fixture")
    output = tmp_path / "report.json"
    os.link(audio, output)
    monkeypatch.setattr("echotrace.pipeline.analyze_file", lambda path: pytest.fail("scoring started"))

    assert main(["score", str(audio), "--output", str(output)]) == 2
    assert audio.read_bytes() == b"audio fixture"


@pytest.mark.parametrize("command", ["audit", "evaluate"])
def test_report_command_rejects_output_alias_of_input(tmp_path, command):
    manifest, _ = _manifest(tmp_path, labeled=True)
    predictions = tmp_path / "predictions.csv"
    predictions.write_text("file_id,synthetic_score\nclip,0.2\nsynthetic,0.8\n")
    source = manifest if command == "audit" else predictions
    output = tmp_path / "output.json"
    os.link(source, output)
    original = source.read_bytes()
    args = [command, str(manifest)]
    if command == "evaluate":
        args.append(str(predictions))
    args.extend(["--root", str(tmp_path), "--output", str(output)])

    assert main(args) == 2
    assert source.read_bytes() == original


@pytest.mark.parametrize("input_name", ["predictions", "expected", "schema"])
def test_export_rejects_output_alias_of_input(tmp_path, input_name):
    predictions = tmp_path / "predictions.csv"
    predictions.write_text("file_id,synthetic_score\nclip,0.2\n")
    expected = tmp_path / "expected.csv"
    expected.write_text("file_id\nclip\n")
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({
        "expected_id_column": "file_id", "output_id_column": "file_id",
        "output_score_column": "synthetic_score", "score_scale": "0-1",
        "score_direction": "synthetic_high", "columns": ["file_id", "synthetic_score"],
        "official_schema_confirmed": True,
    }))
    source = {"predictions": predictions, "expected": expected, "schema": schema}[input_name]
    output = tmp_path / "submission.csv"
    os.link(source, output)
    original = source.read_bytes()

    assert main(["export", str(predictions), "--expected", str(expected),
                 "--schema", str(schema), "--output", str(output)]) == 2
    assert source.read_bytes() == original
