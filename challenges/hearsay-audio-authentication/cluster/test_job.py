"""Local, CPU-only guard checks for the Slurm template; no sbatch invocation."""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


JOB = Path(__file__).with_name("train-and-evaluate.sbatch")
BACKEND = JOB.parents[1] / "backend"


class JobGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name in ("data", "results"):
            (root / name).mkdir(parents=True)
        for name in ("train.csv", "selection.csv", "acceptance.csv"):
            (root / name).write_text("file_id,path,label\na,a.wav,0\nb,b.wav,1\n", encoding="utf-8")
        config = {
            "dataset_root": str(root / "data"),
            "train_manifest": str(root / "train.csv"),
            "validation_manifest": str(root / "selection.csv"),
            "output_dir": str(root / "results/train"),
            "device": "cuda", "max_wall_seconds": 10800,
        }
        self.config = root / "config.json"
        self.config.write_text(json.dumps(config), encoding="utf-8")
        fake = root / "fake.py"
        fake.write_text('''import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CALLS"], "a", encoding="utf-8") as out:
    out.write(json.dumps(args) + "\\n")
if args[1] == "echotrace.training":
    config = json.loads(pathlib.Path(args[2]).read_text())
    output = pathlib.Path(config["output_dir"])
    output.mkdir()
    (output / "best.pt").write_bytes(b"fake checkpoint")
    (output / "metrics.json").write_text(json.dumps({"checkpoint": "best.pt"}))
elif args[1] == "echotrace.checkpoint_eval":
    pathlib.Path(args[args.index("--output") + 1]).mkdir()
elif args[1] == "echotrace.acceptance":
    pathlib.Path(args[args.index("--output") + 1]).write_text("{}")
else:
    raise SystemExit(2)
''', encoding="utf-8")
        shim = root / "python-shim"
        shim.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = -m ]; then\n"
            f"  exec {shlex.quote(sys.executable)} {shlex.quote(str(fake))} \"$@\"\n"
            "fi\n"
            f"exec {shlex.quote(sys.executable)} \"$@\"\n",
            encoding="utf-8",
        )
        shim.chmod(0o700)
        self.calls = root / "calls.jsonl"
        self.env = {**os.environ,
                    "SLURM_JOB_ID": "local-test-only",
                    "ECHOTRACE_PYTHON": str(shim),
                    "ECHOTRACE_BACKEND": str(BACKEND),
                    "ECHOTRACE_CONFIG": str(self.config),
                    "ECHOTRACE_SELECTION_MANIFEST": str(root / "selection.csv"),
                    "ECHOTRACE_ACCEPTANCE_MANIFEST": str(root / "acceptance.csv"),
                    "ECHOTRACE_EVAL_DIR": str(root / "results/eval"),
                    "FAKE_CALLS": str(self.calls)}

    def run_job(self):
        return subprocess.run(["bash", str(JOB)], env=self.env,
                              text=True, capture_output=True, check=False)

    def make_eligible_manifests(self):
        root = Path(self.temp.name)
        for split, per_class in (("train", 2), ("selection", 100), ("acceptance", 100)):
            rows = ["file_id,path,label,group_id,speaker_id,source_id"]
            for label in (0, 1):
                for index in range(per_class):
                    file_id = f"{split}_{label}_{index}"
                    (root / "data" / f"{file_id}.wav").write_bytes(file_id.encode())
                    rows.append(f"{file_id},{file_id}.wav,{label},{file_id},{file_id},{file_id}")
            (root / f"{split}.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    def test_missing_required_environment_stops_before_training(self):
        del self.env["ECHOTRACE_CONFIG"]
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ECHOTRACE_CONFIG", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_direct_shell_invocation_stops_before_training(self):
        del self.env["SLURM_JOB_ID"]
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Slurm allocation", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_relative_path_stops_before_training(self):
        self.env["ECHOTRACE_EVAL_DIR"] = "relative/eval"
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute path", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_stale_output_stops_before_training(self):
        Path(self.env["ECHOTRACE_EVAL_DIR"]).mkdir()
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fresh", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_training_and_evaluation_outputs_must_differ(self):
        self.env["ECHOTRACE_EVAL_DIR"] = str(Path(self.temp.name) / "results/train")
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_acceptance_cannot_alias_selection(self):
        self.env["ECHOTRACE_ACCEPTANCE_MANIFEST"] = self.env["ECHOTRACE_SELECTION_MANIFEST"]
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("distinct", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_acceptance_cannot_alias_training(self):
        self.env["ECHOTRACE_ACCEPTANCE_MANIFEST"] = str(Path(self.temp.name) / "train.csv")
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("training manifest", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_missing_acceptance_audio_stops_before_training(self):
        self.make_eligible_manifests()
        (Path(self.temp.name) / "data/acceptance_0_0.wav").unlink()
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("acceptance_0_0.wav", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_too_few_examples_per_class_stops_before_training(self):
        self.make_eligible_manifests()
        rows = (Path(self.temp.name) / "acceptance.csv").read_text().splitlines()
        (Path(self.temp.name) / "acceptance.csv").write_text(
            "\n".join([rows[0], rows[1], rows[101]]) + "\n", encoding="utf-8")
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("100", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_content_overlap_with_acceptance_stops_before_training(self):
        self.make_eligible_manifests()
        root = Path(self.temp.name) / "data"
        (root / "acceptance_0_0.wav").write_bytes((root / "train_0_0.wav").read_bytes())
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overlap", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_full_pipeline_order_and_checkpoint_hash(self):
        self.make_eligible_manifests()
        result = self.run_job()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual([call[1] for call in calls],
                         ["echotrace.training"] + ["echotrace.checkpoint_eval"] * 4
                         + ["echotrace.acceptance"])
        for call in calls[1:5]:
            self.assertEqual(call[call.index("--max-wall-seconds") + 1], "1200")
        self.assertEqual([call[call.index("--role") + 1] for call in calls[1:5]],
                         ["selection", "selection", "acceptance", "acceptance"])
        for call in (calls[2], calls[4]):
            self.assertEqual(len(call[call.index("--checkpoint-sha256") + 1]), 64)
        self.assertTrue(Path(self.env["ECHOTRACE_EVAL_DIR"], "acceptance-report.json").is_file())


if __name__ == "__main__":
    unittest.main()
