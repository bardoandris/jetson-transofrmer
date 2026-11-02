FROM ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-orin

# Document the expected volume mount for Hugging Face cache
VOLUME /root/.cache/huggingface

# Ensure the entrypoint is the server binary itself
ENTRYPOINT ["llama-server"]

# Set safe default arguments (these get overridden if you pass arguments at runtime)
CMD ["--host", "0.0.0.0", "--port", "8080"]
