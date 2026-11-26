#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'HELP'
Run bottle, transistor, and cable benchmarks for every served model, shot
mode, and Jetson power profile. One fixed reference per category is excluded
from both modes' evaluation images; only one-shot sends the references.

Usage: ./test/run_all_models_three_products.sh [--dataset-dir DIR] [--output-dir DIR]
       [--repetitions N] [--resolution PIXELS ...]
Defaults: one repetition; resolutions 256, 384, 512; res/mvtec-ad; and a new
 timestamped directory under test/test-result. Each --resolution replaces the
 defaults; values must be between 1 and 512. Power order rotates per repetition.
Each repetition has its own results and timestamped raw tegrastats.csv. A
required telemetry failure makes the run incomplete. Run state is written to
run-status.txt. Request timestamps and available server token timings are
included in each result CSV. Energy is not estimated from unverified rails.
Requires a Jetson with tegrastats, Docker Compose/NVIDIA runtime, configured
model server, Python/OpenAI/Pillow, and passwordless sudo for nvpmodel and
jetson_clocks. Environment: PYTHON, OPENAI_BASE_URL, OPENAI_API_KEY,
MODEL_READY_TIMEOUT (300 seconds).
HELP
}
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
dataset_dir=res/mvtec-ad
output_dir=''
repetitions=1
resolutions=()
while (($#)); do
    case "$1" in
        --dataset-dir|--output-dir|--repetitions|--resolution)
            (($# >= 2)) || fail "Missing value for $1"
            case "$1" in
                --dataset-dir) dataset_dir="$2" ;;
                --output-dir) output_dir="$2" ;;
                --repetitions) repetitions="$2" ;;
                --resolution) resolutions+=("$2") ;;
            esac
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
[[ "$repetitions" =~ ^[1-9][0-9]*$ ]] || fail 'Repetitions must be a positive integer.'
((${#resolutions[@]})) || resolutions=(256 384 512)
for resolution in "${resolutions[@]}"; do
    [[ "$resolution" =~ ^[1-9][0-9]*$ ]] && ((10#$resolution <= 512)) || fail "Resolution must be between 1 and 512: $resolution"
done
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
products=(bottle transistor cable)
# Fail before modifying power settings if any category has no evaluation image.
for product in "${products[@]}"; do
    for shot in one zero; do
        prompt="res/prompts/$product/${product}_prompt_${shot}shot.md"
        [[ -f "$prompt" ]] || fail "Prompt not found: $prompt"
    done
    test_dir="$dataset_dir/$product/test"
    [[ -d "$test_dir" ]] || fail "Test directory not found: $test_dir"
    count=0
    while IFS= read -r -d '' folder; do
        mapfile -d '' -t images < <(find -L "$folder" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) -print0)
        ((${#images[@]} >= 2)) || fail "Need a reference and at least one evaluation image in: $folder"
        count=$((count + 1))
    done < <(find -L "$test_dir" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
    ((count > 0)) || fail "No test-case folders found in $test_dir"
done
if [[ -z "${PYTHON:-}" ]]; then
    if [[ -x .venv/bin/python ]]; then PYTHON="$root/.venv/bin/python"; else PYTHON=python3; fi
fi
ready_timeout="${MODEL_READY_TIMEOUT:-300}"
[[ "$ready_timeout" =~ ^[0-9]+$ ]] && ((ready_timeout > 0)) || fail 'MODEL_READY_TIMEOUT must be a positive integer.'
compose=(docker compose -f "$root/deploy/docker/docker-compose.yaml")
sudo -n /usr/sbin/nvpmodel -q >/dev/null || fail 'Non-interactive sudo for nvpmodel is required.'
[[ -n "$output_dir" ]] || output_dir="test/test-result/all-models-$(date +%Y%m%d-%H%M%S)"
[[ ! -e "$output_dir" ]] || fail "Output path already exists: $output_dir"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
printf 'incomplete\n' > "$output_dir/run-status.txt"
command -v tegrastats >/dev/null || fail 'tegrastats is required for telemetry; run is incomplete.'
command -v setsid >/dev/null || fail 'setsid is required for safe telemetry failure handling.'
telemetry_pid=''
job_pid=''
cleanup() {
    if [[ -n "$job_pid" ]]; then
        kill -- "-$job_pid" 2>/dev/null || true
        wait "$job_pid" 2>/dev/null || true
    fi
    if [[ -n "$telemetry_pid" ]]; then
        kill "$telemetry_pid" 2>/dev/null || true
        wait "$telemetry_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" src/utils/write_reference_manifest.py "$dataset_dir" "$output_dir/references.csv"
{
    printf 'started_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'dataset_dir=%s\n' "$(realpath "$dataset_dir")"
    printf 'repetitions=%s\n' "$repetitions"
    printf 'resolutions=%s\n' "${resolutions[*]}"
    printf 'git_commit=%s\n' "$(git rev-parse HEAD 2>/dev/null || printf unknown)"
    printf 'host=%s\n' "$(hostname)"
    printf 'uname=%s\n' "$(uname -a)"
} > "$output_dir/run-metadata.txt"
cp "$root/deploy/docker/docker-compose.yaml" "$output_dir/docker-compose.yaml"

check_telemetry() {
    [[ -n "$telemetry_pid" ]] && kill -0 "$telemetry_pid" 2>/dev/null || fail 'tegrastats capture stopped; run is incomplete.'
}
start_telemetry() {
    local repeat_dir="$1" deadline=$((SECONDS + 15))
    "$PYTHON" "$root/src/utils/capture_tegrastats.py" "$repeat_dir/tegrastats.csv" "$repeat_dir/.telemetry-ready" &
    telemetry_pid=$!
    while [[ ! -f "$repeat_dir/.telemetry-ready" ]]; do
        check_telemetry
        ((SECONDS < deadline)) || fail 'No tegrastats sample received within 15 seconds.'
        sleep 0.2
    done
    check_telemetry
}
stop_telemetry() {
    check_telemetry
    kill "$telemetry_pid"
    wait "$telemetry_pid" || fail 'tegrastats capture failed while stopping.'
    telemetry_pid=''
}
wait_for_models() {
    local deadline=$((SECONDS + ready_timeout)) result
    while ((SECONDS < deadline)); do
        check_telemetry
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
run_with_telemetry() {
    setsid "$@" &
    job_pid=$!
    while kill -0 "$job_pid" 2>/dev/null; do
        check_telemetry
        sleep 0.2
    done
    wait "$job_pid" || fail 'Inference workflow failed; run is incomplete.'
    job_pid=''
    check_telemetry
}

models=()
first_start=1
for ((repeat=1; repeat<=repetitions; repeat++)); do
    repeat_dir="$output_dir/repetition-$repeat"
    mkdir -p "$repeat_dir"
    start_telemetry "$repeat_dir"
    for ((position=0; position<3; position++)); do
        mode=$(((position + repeat - 1) % 3))
        case "$mode" in 0) label=15w ;; 1) label=25w ;; 2) label=maxn ;; esac
        printf '\nRepetition %s: switching to %s (mode %s)\n' "$repeat" "$label" "$mode"
        check_telemetry
        sudo -n /usr/sbin/nvpmodel -m "$mode"
        sudo -n /usr/bin/jetson_clocks --restore 2>/dev/null || true
        sudo -n /usr/sbin/nvpmodel -q | tee "$repeat_dir/power-$label.txt"
        if ((first_start)); then
            running_container="$("${compose[@]}" ps --status running -q llama)"
            if [[ -n "$running_container" ]]; then "${compose[@]}" restart llama; else "${compose[@]}" up -d llama; fi
            first_start=0
        else
            "${compose[@]}" restart llama
        fi
        wait_for_models
        if ((${#models[@]} == 0)); then
            mapfile -t models <<< "$MODEL_LIST"
            printf '%s\n' "${models[@]}" > "$output_dir/models.txt"
        else
            for model in "${models[@]}"; do
                printf '%s\n' "$MODEL_LIST" | grep -Fxq -- "$model" || fail "Model no longer available: $model"
            done
            [[ $(printf '%s\n' "$MODEL_LIST" | wc -l) -eq ${#models[@]} ]] || fail 'Served model list changed after restart.'
        fi
        for shot in one zero; do
            for index in "${!models[@]}"; do
                model="${models[$index]}"
                slug="$(printf '%s' "$model" | sed 's/[^[:alnum:]._-]/_/g')"
                for product in "${products[@]}"; do
                    folders=()
                    while IFS= read -r -d '' folder; do folders+=(--folder "$folder"); done \
                        < <(find -L "$dataset_dir/$product/test" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
                    resolution_args=()
                    for resolution in "${resolutions[@]}"; do resolution_args+=(--resolution "$resolution"); done
                    run_with_telemetry ./run_tests.sh "${folders[@]}" "${resolution_args[@]}" \
                        --prompt-file "res/prompts/$product/${product}_prompt_${shot}shot.md" \
                        --shot-mode "$shot" --exclude-reference-images --model "$model" --power-mode "$label" \
                        --output-dir "$repeat_dir/${shot}shot/$label/model-$((index + 1))-$slug/$product"
                done
            done
        done
    done
    stop_telemetry
    printf 'complete\n' > "$repeat_dir/status.txt"
done
printf 'completed_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$output_dir/run-metadata.txt"
printf 'complete\n' > "$output_dir/run-status.txt"
printf '\nAll benchmarks completed: %s\n' "$output_dir"
