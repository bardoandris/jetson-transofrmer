#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Run both inference workflows for every MVTec-AD product in a dataset.

Expected dataset layout:
  DATASET_DIR/<product>/test/<category>/*.{png,jpg,jpeg}

Each product uses its matching prompt:
  PROMPT_DIR/<product>/<product>_prompt_<shot-mode>.md

Usage:
  ./run_all_products.sh --resolution PIXELS... --power-mode MODE \
    [--model MODEL_ID] [--dataset-dir DIR] [--shot-mode zero|one]
    [--prompt-dir DIR] [--output-dir DIR]

Options:
  -r, --resolution PIXELS   Largest image dimension; repeat for each resolution.
  -m, --model MODEL_ID      Override the first model returned by the inference API.
      --power-mode MODE     Power mode recorded in results.
      --dataset-dir DIR     MVTec-AD dataset root (default: res/mvtec-ad).
      --shot-mode MODE      Prompt variant: zero or one (default: zero).
      --prompt-dir DIR      Prompt root (default: res/prompts).
  -o, --output-dir DIR      Results root (default: a timestamped directory
                            under test/test-result).
  -h, --help                Show this help and exit.

Environment:
  PYTHON              Python executable (default: .venv/bin/python, then python3).
  OPENAI_BASE_URL     OpenAI-compatible API URL.
  OPENAI_API_KEY      API key.

Example:
  ./run_all_products.sh --resolution 256 --power-mode 25w

The inference API must be running before you start the script. Each product's
results are written to its own subdirectory under the output root.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 2
}

resolutions=()
model=""
model_set=0
power_mode=""
dataset_dir="res/mvtec-ad"
prompt_dir="res/prompts"
shot_mode="zero"
output_dir=""

while (($#)); do
    case "$1" in
        -r|--resolution)
            (($# >= 2)) || fail "Missing value for $1."
            [[ "$2" =~ ^[0-9]+$ ]] || fail "Resolution must be a non-negative integer: $2"
            resolutions+=("$2")
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
        --dataset-dir)
            (($# >= 2)) || fail "Missing value for $1."
            dataset_dir="$2"
            shift 2
            ;;
        --prompt-dir)
            (($# >= 2)) || fail "Missing value for $1."
            prompt_dir="$2"
            shift 2
            ;;
        --shot-mode)
            (($# >= 2)) || fail "Missing value for $1."
            shot_mode="$2"
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

((${#resolutions[@]})) || fail "Provide at least one --resolution."
[[ -n "$power_mode" ]] || fail "Provide --power-mode."
if ((model_set)) && [[ -z "$model" ]]; then
    fail "--model must not be empty."
fi
case "$shot_mode" in
    zero|one) ;;
    *) fail "--shot-mode must be 'zero' or 'one'." ;;
esac

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

[[ -d "$dataset_dir" ]] || fail "Dataset directory does not exist: $dataset_dir"
[[ -d "$prompt_dir" ]] || fail "Prompt directory does not exist: $prompt_dir"
dataset_dir="$(cd -P -- "$dataset_dir" && pwd)"
prompt_dir="$(cd -- "$prompt_dir" && pwd)"

if [[ -z "$output_dir" ]]; then
    output_dir="test/test-result/automated-run-$(date +%Y%m%d-%H%M%S)"
fi

image_extensions=( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' )
product_test_dirs=()
while IFS= read -r -d '' test_dir; do
    product_test_dirs+=("$test_dir")
done < <(find "$dataset_dir" -mindepth 2 -maxdepth 2 -type d -name test -print0 | sort -z)

((${#product_test_dirs[@]})) || fail "No <product>/test directories found under: $dataset_dir"

products_run=0
for test_dir in "${product_test_dirs[@]}"; do
    product_dir="$(dirname -- "$test_dir")"
    product="$(basename -- "$product_dir")"
    prompt_file="$prompt_dir/$product/${product}_prompt_${shot_mode}shot.md"
    [[ -f "$prompt_file" ]] || fail "No $shot_mode-shot prompt found for product '$product': $prompt_file"

    folders=()
    while IFS= read -r -d '' category_dir; do
        if find "$category_dir" -maxdepth 1 -type f \( "${image_extensions[@]}" \) -print -quit | grep -q .; then
            folders+=("$category_dir")
        fi
    done < <(find "$test_dir" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

    ((${#folders[@]})) || fail "No category image folders found for product '$product' under: $test_dir"

    printf 'Running product %s (%d image categories)...\n' "$product" "${#folders[@]}"
    args=()
    for folder in "${folders[@]}"; do
        args+=(--folder "$folder")
    done
    for resolution in "${resolutions[@]}"; do
        args+=(--resolution "$resolution")
    done
    args+=(--prompt-file "$prompt_file")
    if ((model_set)); then
        args+=(--model "$model")
    fi
    args+=(--power-mode "$power_mode")
    ./run_tests.sh "${args[@]}" --output-dir "$output_dir/$product"
    products_run=$((products_run + 1))
done

printf 'Completed all %d products. Results: %s\n' "$products_run" "$output_dir"
