import csv
import json

from echotrace.cli import main


def test_setup_model_installs_pinned_nii_primary(tmp_path, monkeypatch, capsys):
    from echotrace import primary_detector
    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"weights")
    monkeypatch.setattr(primary_detector, "setup_primary_weights", lambda: weights)
    monkeypatch.setattr(primary_detector, "model_status", lambda: {
        "name": "NII wav2vec-small-anti-deepfake", "role": "primary",
        "available": True, "weights_sha256": "b" * 64})
    assert main(["setup-model"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["path"] == str(weights)
    assert output["name"] == "NII wav2vec-small-anti-deepfake"
    assert output["role"] == "primary"


def test_batch_retains_failed_ids_and_returns_failure_for_invalid_scores(tmp_path, monkeypatch):
    from echotrace import pipeline
    (tmp_path / "a.wav").write_bytes(b"fixture a")
    (tmp_path / "b.wav").write_bytes(b"fixture b")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("file_id,path\na,a.wav\nb,b.wav\n")
    monkeypatch.setattr(pipeline, "analyze_file", lambda path: {
        "synthetic_score": 1.4 if path.name == "a.wav" else 0.2})
    output = tmp_path / "scores.csv"
    assert main(["batch", str(manifest), "--root", str(tmp_path), "--output", str(output)]) == 2
    with output.open() as f:
        rows = list(csv.DictReader(f))
    assert [r["file_id"] for r in rows] == ["a", "b"]
    assert rows[0]["status"] == "failed"
    assert rows[0]["synthetic_score"] == ""
    assert rows[1]["status"] == "completed"
    assert json.loads(output.with_suffix(".run.json").read_text())["failures"] == 1
