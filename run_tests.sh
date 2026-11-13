#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Run both inference test workflows from the project root.

Usage:
  ./run_tests.sh --folder DIR... --resolution PIXELS... --prompt-file FILE... \
    --power-mode MODE [--model MODEL_ID] [--output-dir DIR]

Options:
  -f, --folder DIR          Image folder to test; repeat for each folder.
  -r, --resolution PIXELS   Largest image dimension; repeat for each resolution.
  -p, --prompt-file FILE    Prompt file; repeat for each prompt.
  -m, --model MODEL_ID      Override the first model returned by the inference API.
      --power-mode MODE     Power mode recorded in the results.
  -o, --output-dir DIR      Results directory (default: a timestamped directory
                            under test/test-result).
  -h, --help                Show this help and exit.

Environment:
  PYTHON              Python executable (default: .venv/bin/python, then python3).
  OPENAI_BASE_URL     OpenAI-compatible API URL (uses the Python scripts' default
                      when unset).
  OPENAI_API_KEY      API key (uses the Python scripts' default when unset).

Example:
  ./run_tests.sh \
    --folder /data/mvtec/bottle/test/good \
    --resolution 256 \
    --prompt-file res/prompts/bottle/bottle_prompt_zeroshot.md \
    --power-mode 25w

Each workflow processes all supplied folder/resolution/prompt combinations.
The model API must be running before you start the script.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 2
}

folders=()
resolutions=()
prompt_files=()
model=""
model_set=0
power_mode=""
output_dir=""

while (($#)); do
    case "$1" in
        -f|--folder)
            (($# >= 2)) || fail "Missing value for $1."
            folders+=("$2")
            shift 2
            ;;
        -r|--resolution)
            (($# >= 2)) || fail "Missing value for $1."
            [[ "$2" =~ ^[0-9]+$ ]] || fail "Resolution must be a non-negative integer: $2"
            resolutions+=("$2")
            shift 2
            ;;
        -p|--prompt-file)
            (($# >= 2)) || fail "Missing value for $1."
            prompt_files+=("$2")
            shift 2
            ;;
        -m|--model)
            (($# >= 2)) || fail "Missing value for $1."
            model="$2"
            model_set=1
            shift 2
            ;;
        --power-mode)
            (($# >= 2)) || fail "Missing value for $1."
            power_mode="$2"
            shift 2
            ;;
        -o|--output-dir)
            (($# >= 2)) || fail "Missing value for $1."
            output_dir="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1 (use --help for usage)."
            ;;
    esac
done

((${#folders[@]})) || fail "Provide at least one --folder."
((${#resolutions[@]})) || fail "Provide at least one --resolution."
((${#prompt_files[@]})) || fail "Provide at least one --prompt-file."
[[ -n "$power_mode" ]] || fail "Provide --power-mode."
if ((model_set)) && [[ -z "$model" ]]; then
    fail "--model must not be empty."
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

for folder in "${folders[@]}"; do
    [[ -d "$folder" ]] || fail "Image folder does not exist: $folder"
    if ! find "$folder" -maxdepth 1 -type f \( \
        -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \
    \) -print -quit | grep -q .; then
        fail "Image folder contains no PNG/JPG/JPEG files: $folder"
    fi
done

for prompt_file in "${prompt_files[@]}"; do
    [[ -f "$prompt_file" ]] || fail "Prompt file does not exist: $prompt_file"
done

if [[ -z "$output_dir" ]]; then
    output_dir="test/test-result/automated-run-$(date +%Y%m%d-%H%M%S)"
fi

if [[ -z "${PYTHON:-}" ]]; then
    if [[ -x "$script_dir/.venv/bin/python" ]]; then
        PYTHON="$script_dir/.venv/bin/python"
    else
        PYTHON="python3"
    fi
fi
if [[ "$PYTHON" == */* ]]; then
    [[ -x "$PYTHON" ]] || fail "Python executable is not executable: $PYTHON"
else
    command -v "$PYTHON" >/dev/null 2>&1 || fail "Python executable not found: $PYTHON"
fi
mkdir -p "$output_dir"

common_args=()
for folder in "${folders[@]}"; do
    common_args+=(--folder "$folder")
done
for resolution in "${resolutions[@]}"; do
    common_args+=(--resolution "$resolution")
done
for prompt_file in "${prompt_files[@]}"; do
    common_args+=(--prompt-file "$prompt_file")
done
if ((model_set)); then
    common_args+=(--model "$model")
fi
common_args+=(--power-mode "$power_mode")

printf 'Running scaffold results workflow...\n'
"$PYTHON" src/scaffold_test.py \
    "${common_args[@]}" \
    --csv "$output_dir/scaffold-results.csv"

printf 'Running MVTec folder analysis workflow...\n'
PYTHONPATH="$script_dir/src${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON" src/mvtec_ad/run_test_folder_analysis.py \
    "${common_args[@]}" \
    --csv "$output_dir/folder-analysis.csv"

printf 'Both workflows completed. Results: %s\n' "$output_dir"
