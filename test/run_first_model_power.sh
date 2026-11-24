#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'HELP'
Run the first served model on every transistor test category at 256, 512,
and 1024 pixels in Jetson power modes 0 (15W), 1 (25W), and 2 (MAXN).

Usage: ./test/run_first_model_power.sh [--shot-mode one|zero] [--dataset-dir DIR]
                                  [--output-dir DIR] [--category NAME ...]
Repeat --category to select test folders; by default all categories are tested.
Defaults: one-shot (zero-shot wrapper: zero), res/mvtec-ad, and a
timestamped test/test-result directory.
Requires Docker Compose, NVIDIA runtime, a configured model server, the OpenAI
Python package, and non-interactive sudo for nvpmodel and jetson_clocks.
OPENAI_BASE_URL and OPENAI_API_KEY configure the model API; PYTHON selects Python.
MODEL_READY_TIMEOUT sets the API readiness timeout in seconds (default 300).
HELP
}
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
shot_mode=one
dataset_dir=res/mvtec-ad
output_dir=""
categories=()
while (($#)); do
    case "$1" in
        --shot-mode|--dataset-dir|--output-dir|--category)
            (($# >= 2)) || fail "Missing value for $1"
            case "$1" in
                --shot-mode) shot_mode="$2" ;;
                --dataset-dir) dataset_dir="$2" ;;
                --output-dir) output_dir="$2" ;;
                --category) categories+=("$2") ;;
            esac
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
[[ "$shot_mode" == one || "$shot_mode" == zero ]] || fail 'Shot mode must be one or zero.'
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$script_dir"
prompt="res/prompts/transistor/transistor_prompt_${shot_mode}shot.md"
[[ -f "$prompt" ]] || fail "Prompt not found: $prompt"
test_dir="$dataset_dir/transistor/test"
[[ -d "$test_dir" ]] || fail "Dataset directory not found: $test_dir"
folders=()
if ((${#categories[@]})); then
    for category in "${categories[@]}"; do
        [[ -n "$category" && "$category" != . && "$category" != .. && "$category" != */* ]] \
            || fail "Category must be a single folder name: $category"
        folder="$test_dir/$category"
        [[ -d "$folder" ]] || fail "Category directory not found: $folder"
        if ! find -L "$folder" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) -print -quit | grep -q .; then
            fail "No images found in category: $folder"
        fi
        folders+=(--folder "$folder")
    done
else
    while IFS= read -r -d '' folder; do
        if find -L "$folder" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) -print -quit | grep -q .; then
            folders+=(--folder "$folder")
        fi
    done < <(find -L "$test_dir" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
fi
((${#folders[@]})) || fail "No image categories found in $test_dir"
[[ -n "$output_dir" ]] || output_dir="test/test-result/first-model-${shot_mode}shot-$(date +%Y%m%d-%H%M%S)"
if [[ -z "${PYTHON:-}" ]]; then
    if [[ -x .venv/bin/python ]]; then PYTHON="$script_dir/.venv/bin/python"; else PYTHON=python3; fi
fi
ready_timeout="${MODEL_READY_TIMEOUT:-300}"
[[ "$ready_timeout" =~ ^[0-9]+$ ]] && ((ready_timeout > 0)) || fail 'MODEL_READY_TIMEOUT must be a positive integer.'
compose=(docker compose -f "$script_dir/deploy/docker/docker-compose.yaml")
sudo -n /usr/sbin/nvpmodel -q >/dev/null || fail 'Non-interactive sudo for nvpmodel is required.'

# Querying models also confirms the API is ready after a start or restart.
wait_for_model() {
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
print(models[0].id)
' 2>/dev/null)" && [[ -n "$result" ]]; then
            MODEL_ID="$result"
            return 0
        fi
        sleep 2
    done
    fail "Model API did not become ready within ${ready_timeout}s."
}

model=""
for mode in 0 1 2; do
    case "$mode" in 0) label=15w ;; 1) label=25w ;; 2) label=maxn ;; esac
    printf 'Switching to %s (mode %s)\n' "$label" "$mode"
    sudo -n /usr/sbin/nvpmodel -m "$mode"
    sudo -n /usr/bin/jetson_clocks --restore 2>/dev/null || true
    sudo -n /usr/sbin/nvpmodel -q
    if [[ "$mode" == 0 ]]; then
        # up is idempotent: it starts the service only if needed.
        "${compose[@]}" up -d llama
    else
        "${compose[@]}" restart llama
    fi
    wait_for_model
    if [[ -z "$model" ]]; then
        model="$MODEL_ID"
        printf 'Using first served model: %s\n' "$model"
    elif [[ "$MODEL_ID" != "$model" ]]; then
        fail "First served model changed after restart ($model -> $MODEL_ID)."
    fi
    ./run_tests.sh "${folders[@]}" --resolution 256 --resolution 512 --resolution 1024 \
        --prompt-file "$prompt" --shot-mode "$shot_mode" --model "$model" --power-mode "$label" \
        --output-dir "$output_dir/$label"
done
printf 'All power-mode benchmarks completed: %s\n' "$output_dir"
