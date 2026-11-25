#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'HELP'
Run bottle, transistor, and cable benchmarks at 256 and 512 pixels
for every served model in one-shot, then zero-shot mode. Each shot mode
covers Jetson power modes 0 (15W), 1 (25W), and 2 (MAXN). The llama Compose
service is started if needed and restarted after every later power change.

Usage: ./test/run_all_models_three_products.sh [--dataset-dir DIR] [--output-dir DIR]
Defaults: res/mvtec-ad and test/test-result/all-models-<timestamp>.
Requires the MVTec-AD dataset, product prompts, Docker Compose with NVIDIA
runtime, a configured model server, the OpenAI Python package, and passwordless
sudo for /usr/sbin/nvpmodel and /usr/bin/jetson_clocks.
Environment: PYTHON, OPENAI_BASE_URL, OPENAI_API_KEY, MODEL_READY_TIMEOUT (300s).
HELP
}
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
dataset_dir=res/mvtec-ad
output_dir=''
while (($#)); do
    case "$1" in
        --dataset-dir|--output-dir)
            (($# >= 2)) || fail "Missing value for $1"
            if [[ "$1" == --dataset-dir ]]; then dataset_dir="$2"; else output_dir="$2"; fi
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
products=(bottle transistor cable)
# Validate all prompts and test folders before changing the power mode.
for product in "${products[@]}"; do
    for shot in one zero; do
        prompt="res/prompts/$product/${product}_prompt_${shot}shot.md"
        [[ -f "$prompt" ]] || fail "Prompt not found: $prompt"
    done
    test_dir="$dataset_dir/$product/test"
    [[ -d "$test_dir" ]] || fail "Test directory not found: $test_dir"
    count=0
    while IFS= read -r -d '' folder; do
        if ! find -L "$folder" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) -print -quit | grep -q .; then
            fail "One-shot requires an image in every test-case folder: $folder"
        fi
        count=$((count + 1))
    done < <(find -L "$test_dir" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
    ((count > 0)) || fail "No test-case folders found in $test_dir"
done
[[ -n "$output_dir" ]] || output_dir="test/test-result/all-models-$(date +%Y%m%d-%H%M%S)"
if [[ -z "${PYTHON:-}" ]]; then
    if [[ -x .venv/bin/python ]]; then PYTHON="$root/.venv/bin/python"; else PYTHON=python3; fi
fi
ready_timeout="${MODEL_READY_TIMEOUT:-300}"
[[ "$ready_timeout" =~ ^[0-9]+$ ]] && ((ready_timeout > 0)) || fail 'MODEL_READY_TIMEOUT must be a positive integer.'
compose=(docker compose -f "$root/deploy/docker/docker-compose.yaml")
sudo -n /usr/sbin/nvpmodel -q >/dev/null || fail 'Non-interactive sudo for nvpmodel is required.'

wait_for_models() {
    local deadline=$((SECONDS + ready_timeout)) result
    while ((SECONDS < deadline)); do
        if result="$("$PYTHON" -c '
import os
from openai import OpenAI
client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1"),
                api_key=os.getenv("OPENAI_API_KEY", "ollama"), timeout=5, max_retries=0)
models = client.models.list().data
if not models:
    raise SystemExit(1)
for model in models:
    print(model.id)
' 2>/dev/null)" && [[ -n "$result" ]]; then
            MODEL_LIST="$result"
            return
        fi
        sleep 2
    done
    fail "Model API did not become ready within ${ready_timeout}s."
}

models=()
first_start=1
for shot in one zero; do
    for mode in 0 1 2; do
        case "$mode" in 0) label=15w ;; 1) label=25w ;; 2) label=maxn ;; esac
        printf '\nSwitching to %s (mode %s), %s-shot\n' "$label" "$mode" "$shot"
        sudo -n /usr/sbin/nvpmodel -m "$mode"
        sudo -n /usr/bin/jetson_clocks --restore 2>/dev/null || true
        sudo -n /usr/sbin/nvpmodel -q
        if ((first_start)); then
            running_container="$("${compose[@]}" ps --status running -q llama)"
            if [[ -n "$running_container" ]]; then
                "${compose[@]}" restart llama
            else
                "${compose[@]}" up -d llama
            fi
            first_start=0
        else
            "${compose[@]}" restart llama
        fi
        wait_for_models
        if ((${#models[@]} == 0)); then
            mapfile -t models <<< "$MODEL_LIST"
            ((${#models[@]} > 0)) || fail 'No models returned by the API.'
        else
            # Never silently skip a model after a restart, even if order changes.
            for model in "${models[@]}"; do
                if ! printf '%s\n' "$MODEL_LIST" | grep -Fxq -- "$model"; then
                    fail "Model no longer available after restart: $model"
                fi
            done
            [[ $(printf '%s\n' "$MODEL_LIST" | wc -l) -eq ${#models[@]} ]] || fail 'Served model list changed after restart.'
        fi
        for index in "${!models[@]}"; do
            model="${models[$index]}"
            slug="$(printf '%s' "$model" | sed 's/[^[:alnum:]._-]/_/g')"
            for product in "${products[@]}"; do
                folders=()
                while IFS= read -r -d '' folder; do folders+=(--folder "$folder"); done \
                    < <(find -L "$dataset_dir/$product/test" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
                ((${#folders[@]})) || fail "No test-case folders found for $product"
                ./run_tests.sh "${folders[@]}" --resolution 256 --resolution 512 \
                    --prompt-file "res/prompts/$product/${product}_prompt_${shot}shot.md" \
                    --shot-mode "$shot" --model "$model" --power-mode "$label" \
                    --output-dir "$output_dir/${shot}shot/$label/model-$((index + 1))-$slug/$product"
            done
        done
    done
done
printf '\nAll model, product, shot-mode, and power-mode benchmarks completed: %s\n' "$output_dir"
