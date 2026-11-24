import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import run_inference
from mvtec_ad.run_test_folder_analysis import write_results_csv


class ServerTimingTests(unittest.TestCase):
    def test_server_timings_reach_csv_and_missing_values_remain_empty(self):
        for timings in ({"prompt_ms": 225.176, "predicted_ms": 4538.132}, {}):
            with self.subTest(timings=timings), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp) / "transistor" / "test" / "good"
                folder.mkdir(parents=True)
                (folder.parent / "bent_lead").mkdir()
                Image.new("RGB", (2, 2)).save(folder / "image.png")
                response = SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(
                        content='{"defect_category":"good"}'
                    ))],
                    model_dump=lambda: {"timings": timings},
                )
                with (
                    patch("run_inference.OpenAI") as client,
                    patch("run_inference.wait_for_safe_temperature"),
                ):
                    client.return_value.chat.completions.create.return_value = response
                    runner = run_inference.RunInference("prompt", "model")
                    runner.add_folder(str(folder))
                    runner.add_resolution(256)
                    scenarios = runner.run_inference()
                output = Path(temp) / "results.csv"
                write_results_csv(str(output), [(str(folder), 256, "prompt.md", scenarios[0]["results"])], "model", "15w")
                with output.open(newline="") as handle:
                    row = next(csv.DictReader(handle))
                self.assertEqual(row["prompt_ms"], str(timings.get("prompt_ms", "")))
                self.assertEqual(row["predicted_ms"], str(timings.get("predicted_ms", "")))
                self.assertGreaterEqual(float(row["request_time"]), 0)


if __name__ == "__main__":
    unittest.main()
