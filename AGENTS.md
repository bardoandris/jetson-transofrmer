# Repository Guidelines

## Project Structure & Module Organization

- `src/run_inference.py` contains image inference and thermal control; `src/mvtec_ad/` contains MVTec folder analysis. Shared schemas and timing helpers live in `src/utils/`.
- `res/prompts/<product>/` holds one-shot and zero-shot prompt files. Keep the existing `<product>_prompt_<mode>.md` naming pattern.
- `test/` contains unit tests, experiment results, and data-processing scripts and plots under `test/data_procesisng/`. `conf/` holds Jetson and Ollama configuration; `deploy/docker/` contains the inference server image and Compose configuration.
- Root-level `run_*.sh` scripts orchestrate experiments across products, models, and power modes.

## Build, Test, and Development Commands

- `PYTHONPATH=src python -m unittest discover -s test -p 'test_*.py'` runs the unit tests. The inference module requires its Python dependencies, including Pillow and the OpenAI client.
- `./run_tests.sh --help` lists experiment options. Run it with image folders, resolutions, prompt files, and a power mode to produce CSV results; it requires a running OpenAI-compatible model API.
- `docker compose -f deploy/docker/docker-compose.yaml up --build` builds and starts the NVIDIA inference server; this requires the NVIDIA container runtime and appropriate model configuration.

## Coding Style & Naming Conventions

Use four spaces for Python and follow the existing type annotations, descriptive `snake_case` functions and variables, and `PascalCase` classes. Shell scripts use Bash and descriptive lowercase names. Follow nearby formatting and keep command-line options consistent with existing scripts. No repository-wide formatter or linter is configured.

## Testing Guidelines

Use Python's `unittest` framework for automated tests, with files named `test_*.py` and methods named `test_*`. Mock hardware and external services when practical, as in `test/test_thermal_control.py`. Run the unit suite above for code changes and document any hardware or model-dependent experiment separately. No coverage threshold is configured.

## Commit & Pull Request Guidelines

Recent commits often use short prefixes such as `fix(param):`, `perf(scripts):`, and `data:` followed by a concise description; use that style when practical. Pull requests should explain the change, identify relevant issues, and report tests run. For experiment or plot changes, include the relevant configuration and example results or screenshots.

## Configuration & Security

Set `OPENAI_BASE_URL` and `OPENAI_API_KEY` through the environment when needed; avoid committing credentials. Review `conf/setup_env.sh` and Docker network settings before exposing a model server beyond the local machine.
