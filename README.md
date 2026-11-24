# Jetson VLM benchmarks

This repository tests vision-language models on MVTec-AD images using an OpenAI-compatible inference server. Commands below are run from the repository root.

## Requirements

- A Jetson configured with the power-mode IDs used by the scripts: 0 (15W), 1 (25W), and 2 (MAXN).
- Docker Compose, the NVIDIA container runtime, and a model configured for `deploy/docker/docker-compose.yaml`. The power sweep requires non-interactive `sudo` access to `/usr/sbin/nvpmodel` and `/usr/bin/jetson_clocks`.
- Python with `openai`, `Pillow`, and `pydantic` installed. The scripts prefer `.venv/bin/python`; set `PYTHON` to select another interpreter.
- An MVTec-AD dataset. The dataset is not included in the prompt directory.

The default API URL is `http://localhost:8080/v1` and the default API key is `ollama`. Set `OPENAI_BASE_URL` and `OPENAI_API_KEY` to override them.

## Supply a test case

Put images in category directories under a product's `test` directory. For example, a minimal transistor dataset could be:

```text
res/mvtec-ad/transistor/test/
├── good/000.png
├── good/001.png
├── bent_lead/000.png
└── bent_lead/001.png
```

Use PNG, JPG, or JPEG images. The folder name is recorded as the true category; use labels supported by the product prompt and schema. The transistor prompts are in `res/prompts/transistor/`.

Prompt and reference preparation is centralized in `src/prompt_preparation.py`. Folder analysis accepts `--shot-mode one` or `--shot-mode zero` to override the filename convention; without it, filenames ending in `_oneshot` select one-shot and all others select zero-shot. The power sweep passes its chosen mode explicitly.

For one-shot tests, the first image in sorted filename order from **each** category is used as a labeled reference and excluded from inference. Each category must contain an image; provide at least two per category to also obtain a result for it. Zero-shot tests do not reserve reference images. Both modes request server-side prompt caching and perform a dummy-image warm-up; zero-shot means no labeled reference images, not an uncached run. Actual cache reuse depends on the server.

## Run a single test case

Start the model server first, for example with `docker compose -f deploy/docker/docker-compose.yaml up -d`, then run the folder analysis directly:

```bash
mkdir -p test/test-result/example
PYTHONPATH=src .venv/bin/python src/mvtec_ad/run_test_folder_analysis.py \
  --folder res/mvtec-ad/transistor/test/good \
  --folder res/mvtec-ad/transistor/test/bent_lead \
  --resolution 256 --resolution 512 \
  --prompt-file res/prompts/transistor/transistor_prompt_zeroshot.md \
  --power-mode 15w --csv test/test-result/example/results.csv
```

Replace `.venv/bin/python` if using another environment. Repeat `--folder`, `--resolution`, or `--prompt-file` to test combinations. Add `--model MODEL_ID` to select a model; otherwise the first model returned by the API is used. `--power-mode` records a label in the CSV; this direct command does **not** change the Jetson power mode. The CSV contains per-image categories, timings, model, resolution, and prompt information. `request_time` is the client-observed request duration in seconds; `prompt_ms` and `predicted_ms` are the server-reported prompt processing and token generation times in milliseconds. Server timing fields are empty when unavailable.

## Run the power sweep

```bash
./test/run_first_model_power.sh --dataset-dir /path/to/mvtec-ad --output-dir test/test-result/one-shot
./test/run_first_model_power_zeroshot.sh --dataset-dir /path/to/mvtec-ad --output-dir test/test-result/zero-shot
```

Pass `--category good --category bent_lead` to either script to test only those category folders. Repeat the option for each category; if omitted, all nonempty categories are selected. One-shot reference images are still drawn from every category under `transistor/test`.

These scripts discover transistor category folders, select the first served model, and test resolutions 256, 512, and 1024 in each power mode. They start the Compose service if needed, restart it between modes, and wait for the API after each start. `MODEL_READY_TIMEOUT` sets the readiness timeout in seconds (default 300). Run `./test/run_first_model_power.sh --help` for options. Relative dataset and output paths are interpreted from the repository root.

The sweep scripts call `./run_tests.sh`, which runs folder analysis and writes `folder-analysis.csv` under each power-mode output directory.

Inference pauses when temperature reaches 85°C and checks every 30 seconds until it falls below 70°C.

## Run unit tests

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s test -p 'test_*.py'
```
