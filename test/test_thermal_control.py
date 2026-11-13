import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_inference


class ThermalControlTests(unittest.TestCase):
    def test_waits_until_temperature_is_at_most_70c(self) -> None:
        with (
            patch(
                "run_inference.read_system_temperature",
                side_effect=[72.5, 70.0],
            ),
            patch("run_inference.time.sleep") as sleep,
        ):
            run_inference.wait_for_safe_temperature()

        sleep.assert_called_once_with(30)

    def test_does_not_wait_at_70c(self) -> None:
        with (
            patch("run_inference.read_system_temperature", return_value=70.0),
            patch("run_inference.time.sleep") as sleep,
        ):
            run_inference.wait_for_safe_temperature()

        sleep.assert_not_called()

    def test_one_shot_helper_reads_uppercase_tegrastats_sensors(self) -> None:
        helper = Path(__file__).resolve().parents[1] / "conf" / "tegra-thermal.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_tegrastats = Path(temp_dir) / "tegrastats"
            fake_tegrastats.write_text(
                "#!/bin/sh\nprintf 'CPU@68.5C GPU@72.0C SOC0@69.0C tj@70.0C\\n'\n",
                encoding="utf-8",
            )
            fake_tegrastats.chmod(0o755)
            result = subprocess.run(
                ["/bin/bash", str(helper), "--once"],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{temp_dir}:{os.environ['PATH']}",
                },
            )

        self.assertEqual(result.stdout.strip(), "72.0")


if __name__ == "__main__":
    unittest.main()
