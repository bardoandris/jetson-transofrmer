# Draft plots: all-models-20261125-221751

Recreate from the repository root (requires Python, matplotlib, numpy, and pandas):

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache .venv/bin/python test/data_procesisng/python/plot_all_models_run.py
```

Pass `--results-dir` and `--output-dir` to select another run or destination.

- `01_inference_time.png`: mean server inference time by resolution and power mode.
- `02_inference_statistics.png`: mean, median, and 99th percentile server inference time by resolution and power mode.
- `03_total_response_time.png`: mean local image preparation plus client-observed request time by resolution and power mode.
- `04_accuracy_by_dataset.png`: exact category accuracy by dataset and resolution, pooling the three power modes.
- `summary_by_dataset.csv`: sample count, accuracy, inference statistics, and mean total response time for each model, shot mode, power mode, dataset, and resolution.

Server inference time means `(prompt_ms + predicted_ms) / 1000`, using the server-reported times; it may omit other server work. Total response time means `processing_time + request_time`, in seconds. It excludes warmup and thermal pauses. Accuracy is the fraction of rows whose predicted category exactly matches the true category. Pooled values weight each image equally, rather than weighting each dataset or category equally. The 99th percentile is computed over the pooled per-image observations, using linear interpolation.

One-shot reserves a reference image per category, while zero-shot does not, so shot-mode aggregates do not use identical image sets. Results are from one benchmark run, and repeated power-mode measurements are not independent images. The two resolutions are maximum dimensions after downscaling; images smaller than the limit are not enlarged. The lines connect measured settings and do not establish behavior between them. The requested Qwen3.5 model is not present in this run: it contains Qwen3-VL and Gemma 4.
