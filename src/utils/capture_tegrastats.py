"""Capture timestamped raw tegrastats samples until terminated by the runner."""
import argparse
import csv
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("ready_file", type=Path)
    args = parser.parse_args()
    process = subprocess.Popen(["tegrastats", "--interval", "1000"], stdout=subprocess.PIPE,
                               text=True, bufsize=1)

    def stop(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sample_received_utc", "tegrastats_raw"])
            handle.flush()
            for line in process.stdout:
                if not line.strip():
                    continue
                writer.writerow([datetime.now(timezone.utc).isoformat(), line.rstrip()])
                handle.flush()
                args.ready_file.touch(exist_ok=True)
        print(f"tegrastats stopped unexpectedly (exit {process.wait()})", file=sys.stderr)
        return 1
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    sys.exit(main())
