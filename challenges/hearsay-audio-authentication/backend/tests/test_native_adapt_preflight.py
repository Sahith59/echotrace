import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "cluster" / "native-adapt-evaluate.sbatch"


def _write_csv(path, count, prefix, labels=None):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file_id", "speaker_id", "source_id", "label"])
        writer.writeheader()
        for index in range(count):
            writer.writerow({"file_id":f"{prefix}-f-{index}","speaker_id":f"{prefix}-spk-{index}",
                             "source_id":f"{prefix}-src-{index}","label":labels[index] if labels else index % 2})


def _run_preflight(tmp_path, audit_overrides=None):
    train, selection, acceptance = (tmp_path / name for name in ("train.csv", "selection.csv", "acceptance.csv"))
    _write_csv(train, 10000, "train")
    _write_csv(selection, 2000, "selection")
    _write_csv(acceptance, 2000, "accept", [0] * 1000 + [1] * 1000)
    audit = {"ready":True,"previous_content_hashes":12000,
             "manifest_sha256":hashlib.sha256(acceptance.read_bytes()).hexdigest()}
    audit.update(audit_overrides or {})
    audit_path=tmp_path/"audit.json";audit_path.write_text(json.dumps(audit),encoding="utf-8")
    source=SCRIPT.read_text(encoding="utf-8")
    embedded=source.split("<<'PY'\n",1)[1].split("\nPY",1)[0]
    return subprocess.run([sys.executable,"-c",embedded,train,selection,acceptance,audit_path],
                          text=True,capture_output=True)


def test_shell_preflight_accepts_bound_content_audit(tmp_path):
    result=_run_preflight(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "passed" in result.stdout


def test_shell_preflight_rejects_unbound_or_empty_audit(tmp_path):
    mismatch=_run_preflight(tmp_path,{"manifest_sha256":"0"*64})
    assert mismatch.returncode != 0
    empty=_run_preflight(tmp_path,{"previous_content_hashes":0})
    assert empty.returncode != 0

