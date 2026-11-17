#!/usr/bin/env bash
set -Eeuo pipefail

NVPMODEL_BIN="/usr/sbin/nvpmodel"
JETSON_CLOCKS_BIN="/usr/bin/jetson_clocks"

# Verify non-interactive NOPASSWD sudo access works without a TTY
if ! sudo -n "$NVPMODEL_BIN" -q >/dev/null 2>&1; then
  printf 'Error: non-interactive sudo failed for %s.\n' "$NVPMODEL_BIN" >&2
  printf 'Ensure /etc/sudoers.d/nvpmodel-nopasswd allows NOPASSWD for %s and %s.\n' \
    "$NVPMODEL_BIN" "$JETSON_CLOCKS_BIN" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

# Jetson Orin Nano Super nvpmodel IDs:
#   0 = 15W
#   1 = 25W
#   2 = MAXN
W15_MODE_ID=0
W25_MODE_ID=1
MAXN_MODE_ID=2

COMMON_ARGS=(
  --product transistor
  --resolution 256
  -r 512
  -r 1024
  --shot-mode one
)

switch_power_mode() {
  local mode_id="$1"
  local label="$2"
  printf '\n=== [%s] Switching Jetson power mode (nvpmodel -m %s -> %s) ===\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$mode_id" "$label"
  sudo -n "$NVPMODEL_BIN" -m "$mode_id"
  sudo -n "$JETSON_CLOCKS_BIN" --restore 2>/dev/null || true
  sudo -n "$NVPMODEL_BIN" -q
}

run_sweep() {
  local power_flag="$1"
  local out_dir="$2"
  printf '\n=== [%s] Starting %s benchmark -> %s ===\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$power_flag" "$out_dir"
  bash run_selected_products_all_models.sh \
    "${COMMON_ARGS[@]}" \
    --power-mode "$power_flag" \
    -o "$out_dir"
  printf '=== [%s] Completed %s benchmark ===\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$power_flag"
}

# 1. Switch to 15W (mode 0) and run sweep
switch_power_mode "$W15_MODE_ID" "15W"
run_sweep "15w" "test/test-result/15W-multimodel-with-2B-models-optimized"

# 2. Switch to 25W (mode 1) and run sweep
switch_power_mode "$W25_MODE_ID" "25W"
run_sweep "25w" "test/test-result/25W-multimodel-with-2B-models-optimized"

# 3. Switch to MAXN (mode 2) and run sweep
switch_power_mode "$MAXN_MODE_ID" "MAXN"
run_sweep "maxn" "test/test-result/MAXN-multimodel-with-2B-models-optimized"

printf '\n=== [%s] All power-mode sweeps finished successfully! ===\n' \
  "$(date '+%Y-%m-%d %H:%M:%S')"
