import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import run_inference
import scaffold_test
from mvtec_ad.run_test_folder_analysis import write_results_csv


class ServerTimingTests(unittest.TestCase):
    def test_scaffold_csv_accepts_extended_result_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prompt = root / "prompt.md"
            prompt.write_text("Inspect", encoding="utf-8")
            output = root / "results.csv"
            result = {"image_path": "image.png", "response": "{}", "inference_time": "1",
                      "prompt_ms": 10, "predicted_ms": 20, "processing_time": "0.1",
                      "width": 2, "height": 2, "original_width": 4, "original_height": 4,
                      "request_start_utc": "start", "request_end_utc": "end",
                      "cache_n": 1, "prompt_n": 2, "predicted_n": 3}
            args = ["scaffold", "--folder", "folder", "--resolution", "256", "--prompt-file",
                    str(prompt), "--model", "model", "--power-mode", "15w", "--csv", str(output)]
            with patch("sys.argv", args), patch("scaffold_test.run_inference.RunInference") as runner:
                runner.return_value.run_inference.return_value = [{"folder": "folder", "resolution": 256, "results": [result]}]
                scaffold_test.main()
            with output.open(newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual((row["cache_n"], row["original_width"]), ("1", "4"))

    def test_server_timings_reach_csv_and_missing_values_remain_empty(self):
        for timings in ({"prompt_ms": 225.176, "predicted_ms": 4538.132, "cache_n": 123, "prompt_n": 456, "predicted_n": 7}, {}):
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
                for key in ("cache_n", "prompt_n", "predicted_n"):
                    self.assertEqual(row[key], str(timings.get(key, "")))
                self.assertTrue(row["request_start_utc"].endswith("+00:00"))
                self.assertTrue(row["request_end_utc"].endswith("+00:00"))
                self.assertLessEqual(row["request_start_utc"], row["request_end_utc"])
                self.assertEqual((row["original_width"], row["original_height"]), ("2", "2"))
                self.assertGreaterEqual(float(row["request_time"]), 0)


if __name__ == "__main__":
    unittest.main()
