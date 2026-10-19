# ==============================================================================
# OLLAMA CONFIGURATION TEMPLATE
# ==============================================================================

# --- Networking & Security ---
# Listen address and port (Default: 127.0.0.1:11434)
# Use 0.0.0.0:11434 to allow connections from other machines on your LAN
export OLLAMA_HOST="0.0.0.0:11434"

# Allowed CORS origins for Web UIs (Open WebUI, LibreChat, browser extensions)
# Set to "*" to permit all origins, or comma-separated domains
export OLLAMA_ORIGINS="*"

# --- Storage & Model Management ---
# Custom storage directory for model weights and manifests
# (Default Linux: /usr/share/ollama/.ollama/models or ~/.ollama/models)
# export OLLAMA_MODELS="/mnt/storage/ollama/models"

# Keep-alive duration for models in VRAM after last inference
# Examples: 5m, 24h, 0 (unload immediately), -1 (never unload)
export OLLAMA_KEEP_ALIVE="-1"

# Model load timeout before giving up on stall (Default: 5m)
export OLLAMA_LOAD_TIMEOUT="1m"

# Disable Ollama cloud check/search features (1 = disable)
export OLLAMA_NO_CLOUD=1

# --- Performance & Concurrency ---
# Context window length override in tokens (Default: 0/auto or 4096)
export OLLAMA_CONTEXT_LENGTH="8192"

# Number of parallel requests each model processes simultaneously (Default: 1)
# Note: Scales required memory by (OLLAMA_NUM_PARALLEL * OLLAMA_CONTEXT_LENGTH)
export OLLAMA_NUM_PARALLEL="2"

# Max models concurrently kept in memory (Default: auto, 3 per GPU / 3 for CPU)
export OLLAMA_MAX_LOADED_MODELS="1"

# Request queue capacity before throwing 503 errors (Default: 512)
export OLLAMA_MAX_QUEUE="8"

# Force Flash Attention (1 = force on, 0 = force off, unset = auto)
export OLLAMA_FLASH_ATTENTION="1"

# KV Cache quantization type to save VRAM (f16, q8_0, q4_0)
export OLLAMA_KV_CACHE_TYPE="q4_0"

# --- GPU Selection & Hardware ---
# Standard CUDA visible devices (e.g., "0", "0,1")
# export CUDA_VISIBLE_DEVICES="0"

# Reserve specific VRAM in bytes per GPU for overhead
# export OLLAMA_GPU_OVERHEAD="1073741824"  # 1 GiB

# --- Logging & Debugging ---
# Enable detailed debug logging (1 = verbose, 0 = info level)
export OLLAMA_DEBUG="0"

# Keep prompt history in interactive CLI mode (1 = disable history)
export OLLAMA_NOHISTORY="0"