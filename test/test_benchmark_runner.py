import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BenchmarkRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = Path(__file__).resolve().parents[1]
        for directory in ("test", "bin", "deploy/docker"):
            (self.root / directory).mkdir(parents=True)
        shutil.copy(self.source / "test/run_all_models_three_products.sh", self.root / "test")
        (self.root / "src").symlink_to(self.source / "src", target_is_directory=True)
        (self.root / "deploy/docker/docker-compose.yaml").write_text("services: {}\n")
        for product in ("bottle", "transistor", "cable"):
            for category in ("good", "defect"):
                folder = self.root / "data" / product / "test" / category
                folder.mkdir(parents=True)
                for image in ("000.png", "001.png"):
                    (folder / image).write_bytes(b"image")
            prompt_dir = self.root / "res/prompts" / product
            prompt_dir.mkdir(parents=True)
            for shot in ("one", "zero"):
                (prompt_dir / f"{product}_prompt_{shot}shot.md").write_text("prompt")
        self.write_executable("bin/sudo", 'if [ "$3" = "-m" ]; then printf "%s\\n" "$4" >> "$POWER_TRACE"; fi\nexit 0')
        self.write_executable("bin/docker", 'exit 0')
        self.write_executable("bin/python", f'if [ "$1" = "-c" ]; then echo mock-model; else exec "{sys.executable}" "$@"; fi')
        self.write_executable("bin/tegrastats", 'while :; do echo "RAM 100/1000 CPU@40C VDD_IN 1000mW/1000mW"; sleep 1; done')
        self.write_executable("run_tests.sh", 'printf "%s\\n" "$*" >> "$TRACE"')
        self.trace = self.root / "trace"
        self.power_trace = self.root / "power-trace"
        self.env = {**os.environ, "PATH": str(self.root / "bin") + ":" + os.environ["PATH"],
                    "PYTHON": str(self.root / "bin/python"), "TRACE": str(self.trace),
                    "POWER_TRACE": str(self.power_trace)}

    def write_executable(self, name, body):
        path = self.root / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_runner(self, *args):
        return subprocess.run([str(self.root / "test/run_all_models_three_products.sh"),
                               "--dataset-dir", str(self.root / "data"),
                               "--output-dir", str(self.root / "results"), *args],
                              env=self.env, capture_output=True, text=True, timeout=40)

    def test_repetitions_rotate_power_and_preserve_shared_set(self):
        result = self.run_runner("--repetitions", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.power_trace.read_text().splitlines(), ["0", "1", "2", "1", "2", "0"])
        calls = self.trace.read_text().splitlines()
        self.assertEqual(len(calls), 36)
        self.assertTrue(all("--exclude-reference-images" in call for call in calls))
        self.assertTrue(all(all(f"--resolution {n}" in call for n in (256, 384, 512)) for call in calls))
        self.assertEqual((self.root / "results/run-status.txt").read_text().strip(), "complete")
        with (self.root / "results/references.csv").open(newline="") as handle:
            references = list(csv.DictReader(handle))
        self.assertEqual(len(references), 6)
        self.assertTrue(all(row["reference_image"].endswith("000.png") for row in references))
        for repeat in (1, 2):
            folder = self.root / f"results/repetition-{repeat}"
            self.assertEqual((folder / "status.txt").read_text().strip(), "complete")
            with (folder / "tegrastats.csv").open(newline="") as handle:
                self.assertGreaterEqual(len(list(csv.DictReader(handle))), 1)

    def test_out_of_range_resolution_fails_before_power_change(self):
        result = self.run_runner("--resolution", "513")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.power_trace.exists())

    def test_telemetry_failure_marks_run_incomplete(self):
        self.write_executable("bin/tegrastats", 'echo "CPU@40C"; sleep 1; exit 1')
        self.write_executable("run_tests.sh", 'sleep 5')
        result = self.run_runner()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tegrastats", result.stderr)
        self.assertEqual((self.root / "results/run-status.txt").read_text().strip(), "incomplete")
        self.assertFalse((self.root / "results/repetition-1/status.txt").exists())


if __name__ == "__main__":
    unittest.main()
