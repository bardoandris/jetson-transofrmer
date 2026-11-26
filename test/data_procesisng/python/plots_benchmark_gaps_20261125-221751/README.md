# Benchmark gap analysis

Generate the plots from the project root with Python, matplotlib, numpy and pandas:

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache .venv/bin/python test/data_procesisng/python/explore_benchmark_gaps.py
```

The script uses `all-models-20261125-221751` by default. Select another run with `--results-dir PATH`, and another output directory with `--output-dir PATH`. Detailed error plots default to 15W and 512px. To inspect a different configuration, for example:

```bash
MPLCONFIGDIR=/tmp/matplotlib-cache .venv/bin/python test/data_procesisng/python/explore_benchmark_gaps.py --power-mode 25w --resolution 256 --output-dir /tmp/gap-plots-25w-256
```

Outputs:

- `01_confusion_<dataset>.png`: row-normalized category confusion, by model and shot mode. A cell shows the fraction of images in a true category assigned to a predicted category. The row label gives its sample count.
- `02_category_recall_<dataset>.png`: exact classification recall per true category, including sample counts.
- `03_defect_detection.png`: defect recall (any non-good prediction for a defective image) and false-positive rate (any non-good prediction for a good image).
- `04_balanced_accuracy.png`: overall exact accuracy versus the unweighted mean of per-category exact recalls, including good.
- `05_paired_shot_accuracy.png`: one-shot minus zero-shot exact accuracy, in percentage points, for the selected power mode, on matched image paths, model, dataset, true category and resolution. It excludes unmatched images and rejects duplicate or inconsistently labeled pairs.
- `06_recall_vs_response_time.png`: defect recall versus mean local image preparation plus client-observed request time, with resolution, model, dataset, shot mode and power mode distinguished.
- `detection_and_accuracy_metrics.csv`: the accuracy, binary rates, sample counts and mean times per model, mode, dataset, power and resolution; `paired_shot_metrics.csv` contains paired counts, accuracies and discordant-pair counts.

The detailed plots use all available images in each shot mode; only the paired plot and its CSV restrict both modes to the common images. Matching uses the recorded image path, so inputs must use consistent paths across shot modes. Category examples in these files are small (often around 10 images), so percentages are descriptive and should not be treated as precise estimates. Results across power modes are repeated measurements of the same images, not independent samples. Power-mode names describe settings, not measured energy consumption. Response time excludes warmup and thermal pauses.

## Suggested further data collection

1. **Replicate and pair:** Repeat the complete run at least three times, varying or counterbalancing configuration order. Keep a stable image identifier and record run ID, iteration, timestamps and actual power mode. Retain per-image records rather than only means. Use paired per-image comparisons and image-level or run-level uncertainty estimates appropriate to the question; report the number of independent images and runs.
2. **Reference sensitivity:** Run several explicitly recorded, reproducible one-shot reference sets, while holding a separate evaluation set fixed for *both* modes. Record reference image paths or hashes, category and selection seed. The current script always picks the first sorted image per category; trying alternatives requires changing the selection mechanism. Ensure no reference image is evaluated. This distinguishes reference-selection effects from shot-mode effects.
3. **Resolution and small defects:** Add intermediate and higher resolutions, subject to the server's limits and hardware memory, using the same images and settings. Record original, client-resized and server-processed image dimensions. Compare defect recall by category and response time; avoid assuming larger inputs improve every defect.
4. **Energy and sustained operation:** Record timestamped power readings with rail names, units and sampling interval, together with per-request start/end timestamps, temperature, CPU/GPU clocks and utilization. Measure idle baseline and confirm what each rail covers; integrate power over time to obtain joules per image, and report total and, if appropriate, baseline-subtracted energy separately. Sample over batches long enough for the sensor cadence, and repeat cold and warmed sustained runs. The existing CSV has no energy, temperature, clock or utilization measurements, so these plots cannot be reconstructed from it.
5. **Explain latency:** Record server version/build and command line, hardware, model and vision-projector file versions/quantization, GPU offload and context/cache settings. Capture per-request cache tokens, prompt tokens, generated tokens, image/vision tokens or encoder timing if the server exposes them, prompt and generation timings, response text/status, and retry/error counts. Use the same model, images, resolution and prompt while varying one setting at a time; distinguish warmup from measured requests.
6. **Test data coverage:** Collect more independent examples of underrepresented defect categories and inspect false negatives and false positives. Keep dataset/source IDs and split identities to prevent reference/evaluation leakage. Add other product types and representative real-world lighting or camera conditions when available. Fixed counts of repeated predictions on the same image do not replace additional independent images.

Qwen3.5 is not in this run; add it as a separate, controlled model condition if investigating the earlier Qwen3.5 timing result. These are proposed experiments, not measurements made by this analysis.
