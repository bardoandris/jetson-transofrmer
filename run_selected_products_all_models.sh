#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Run all category folders for selected MVTec-AD products against every served model.

Expected dataset layout:
  DATASET_DIR/<product>/test/<category>/*.{png,jpg,jpeg}

Each product uses its matching prompt:
  PROMPT_DIR/<product>/<product>_prompt_<shot-mode>.md

Usage:
  bash run_selected_products_all_models.sh --product NAME... \
    --resolution PIXELS... --power-mode MODE [options]

Options:
      --product NAME         Product to test; repeat for each product.
  -r, --resolution PIXELS   Largest image dimension; repeat for each resolution.
      --power-mode MODE     Power mode recorded in the results.
      --dataset-dir DIR     Dataset root (default: res/mvtec-ad).
      --prompt-dir DIR      Prompt root (default: res/prompts).
      --shot-mode MODE      Prompt variant: zero or one (default: zero).
      --exclude-model REGEX Skip served model IDs matching ERE pattern.
  -o, --output-dir DIR      Results root (default: a timestamped directory
                            under test/test-result).
  -h, --help                Show this help and exit.

Environment:
  PYTHON              Python executable (default: .venv/bin/python, then python3).
  OPENAI_BASE_URL     OpenAI-compatible API URL (default: http://localhost:8080/v1).
  OPENAI_API_KEY      API key (default: ollama).
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 2
}

products=()
resolutions=()
power_mode=""
dataset_dir="res/mvtec-ad"
prompt_dir="res/prompts"
shot_mode="zero"
exclude_model_regex=""
output_dir=""

while (($#)); do
    case "$1" in
        --product)
            (($# >= 2)) || fail "Missing value for $1."
            products+=("$2")
            shift 2
            ;;
        -r|--resolution)
            (($# >= 2)) || fail "Missing value for $1."
            [[ "$2" =~ ^[0-9]+$ ]] || fail "Resolution must be a non-negative integer: $2"
            resolutions+=("$2")
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
        --exclude-model)
            (($# >= 2)) || fail "Missing value for $1."
            exclude_model_regex="$2"
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

((${#products[@]})) || fail "Provide at least one --product."
((${#resolutions[@]})) || fail "Provide at least one --resolution."
[[ -n "$power_mode" ]] || fail "Provide --power-mode."
case "$shot_mode" in
    zero|one) ;;
    *) fail "--shot-mode must be 'zero' or 'one'." ;;
esac
for product in "${products[@]}"; do
    [[ -n "$product" && "$product" != "." && "$product" != ".." && "$product" != */* ]] \
        || fail "Product must be a single folder name: $product"
done

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

[[ -d "$dataset_dir" ]] || fail "Dataset directory does not exist: $dataset_dir"
[[ -d "$prompt_dir" ]] || fail "Prompt directory does not exist: $prompt_dir"
dataset_dir="$(cd -P -- "$dataset_dir" && pwd)"
prompt_dir="$(cd -P -- "$prompt_dir" && pwd)"

if [[ -z "$output_dir" ]]; then
    output_dir="test/test-result/selected-products-$(date +%Y%m%d-%H%M%S)"
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

if ! model_output="$("$PYTHON" -c '
import os
from openai import OpenAI

base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1")
api_key = os.getenv("OPENAI_API_KEY", "ollama")
models = OpenAI(base_url=base_url, api_key=api_key).models.list().data
if not models:
    raise SystemExit(f"No models are available from the API at {base_url}.")
for model in models:
    print(model.id)
')"; then
    fail "Could not retrieve the model list from the inference API."
fi

models=()
while IFS= read -r model; do
    [[ -z "$model" ]] && continue
    if [[ -n "$exclude_model_regex" && "$model" =~ $exclude_model_regex ]]; then
        printf 'Skipping excluded model: %s\n' "$model"
        continue
    fi
    models+=("$model")
done <<< "$model_output"
((${#models[@]})) || fail "No runnable models remain after filtering."
printf 'Running %d served model(s): %s\n' "${#models[@]}" "${models[*]}"

# Pre-validate all product paths and prompts before starting model runs
image_extensions=( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' )
declare -A product_prompt_files=()
declare -A product_folder_lists=()

for product in "${products[@]}"; do
    test_dir="$dataset_dir/$product/test"
    [[ -d "$test_dir" ]] || fail "Product test directory not found: $test_dir"
    test_dir="$(cd -P -- "$test_dir" && pwd)"

    prompt_file="$prompt_dir/$product/${product}_prompt_${shot_mode}shot.md"
    [[ -f "$prompt_file" ]] || fail "Prompt file not found for '$product': $prompt_file"

    folders=()
    while IFS= read -r -d '' category_dir; do
        if find -L "$category_dir" -maxdepth 1 -type f \( "${image_extensions[@]}" \) -print -quit | grep -q .; then
            folders+=("$(cd -P -- "$category_dir" && pwd)")
        fi
    done < <(find -L "$test_dir" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
    ((${#folders[@]})) || fail "No category image folders found for '$product' under: $test_dir"

    printf 'Product %s: found %d image category folder(s).\n' "$product" "${#folders[@]}"
    product_prompt_files["$product"]="$prompt_file"
    # Store newline-delimited folder paths per product
    product_folder_lists["$product"]="$(printf '%s\n' "${folders[@]}")"
done

# Outer loop over models avoids unloading/reloading weights on every product
run_count=0
for model_index in "${!models[@]}"; do
    model="${models[$model_index]}"
    model_slug="$(printf '%s' "$model" | sed 's/[^[:alnum:]._-]/_/g')"

    for product in "${products[@]}"; do
        model_dir="$output_dir/$product/model-$((model_index + 1))-$model_slug"
        args=()

        while IFS= read -r folder; do
            [[ -n "$folder" ]] && args+=(--folder "$folder")
        done <<< "${product_folder_lists[$product]}"

        for resolution in "${resolutions[@]}"; do
            args+=(--resolution "$resolution")
        done

        args+=(
            --prompt-file "${product_prompt_files[$product]}"
            --model "$model"
            --power-mode "$power_mode"
        )

        start_ts=$SECONDS
        printf 'Running model [%s] on product [%s] (all folders & resolutions in one batch)...\n' \
            "$model" "$product"
        ./run_tests.sh "${args[@]}" --output-dir "$model_dir"
        elapsed=$((SECONDS - start_ts))
        printf 'Finished [%s] on [%s] in %ds.\n' "$model" "$product" "$elapsed"
        run_count=$((run_count + 1))
    done
done

printf 'Completed %d model/product run(s). Results: %s\n' "$run_count" "$output_dir"