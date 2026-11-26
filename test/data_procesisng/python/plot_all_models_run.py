#!/usr/bin/env python3
"""Plot a single all-models benchmark run; times are per evaluated image."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "test/test-result/all-models-20261125-221751"
DEFAULT_OUTPUT = ROOT / "test/data_procesisng/python/plots_all_models_20261125-221751"
POWER_ORDER = ["15W", "25W", "MAXN"]
COLORS = {"15W": "#3478b6", "25W": "#e0802c", "MAXN": "#3a9961"}


def load_results(directory: Path) -> pd.DataFrame:
    paths = sorted(directory.rglob("folder-analysis.csv"))
    if not paths:
        raise ValueError(f"No folder-analysis.csv files found under {directory}")
    required = {"true_category", "answer_category", "test_image", "processing_time",
                "request_time", "prompt_ms", "predicted_ms", "resolution", "model",
                "power_mode", "shot_mode"}
    frames = []
    for path in paths:
        frame = pd.read_csv(path)
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{path} missing columns: {sorted(missing)}")
        frame["dataset"] = path.parent.name
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    numeric = ["processing_time", "request_time", "prompt_ms", "predicted_ms", "resolution"]
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="raise")
    if data[numeric].isna().any().any():
        raise ValueError("Missing timing or resolution values; cannot calculate comparable plots")
    data["power_mode"] = data["power_mode"].str.upper()
    unknown = set(data["power_mode"]) - set(POWER_ORDER)
    if unknown:
        raise ValueError(f"Unknown power modes: {sorted(unknown)}")
    data["model_short"] = data["model"].str.split("/").str[-1].str.replace("-GGUF", "", regex=False)
    if data.groupby("model_short")["model"].nunique().max() > 1:
        raise ValueError("Shortened model names collide")
    data["inference_s"] = (data["prompt_ms"] + data["predicted_ms"]) / 1000
    data["response_s"] = data["processing_time"] + data["request_time"]
    data["correct"] = data["answer_category"].eq(data["true_category"])
    return data


def panels(data: pd.DataFrame, title: str, subtitle: str):
    models = sorted(data["model_short"].unique())
    shots = sorted(data["shot_mode"].unique())
    fig, axes = plt.subplots(len(models), len(shots), figsize=(6.2 * len(shots), 3.8 * len(models)),
                             squeeze=False, sharex=True, sharey=True, layout="constrained")
    fig.suptitle(f"{title}\n{subtitle}", fontsize=14, fontweight="bold")
    for i, model in enumerate(models):
        for j, shot in enumerate(shots):
            ax = axes[i, j]
            ax.set_title(f"{model} · {shot}", fontsize=10)
            ax.grid(True, alpha=.22)
            yield fig, ax, data[(data.model_short == model) & (data.shot_mode == shot)]


def finish(fig, path):
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def lines(data, output, metric, title, ylabel):
    fig = None
    subtitle = "Mean per image; datasets pooled by image count"
    for fig, ax, subset in panels(data, title, subtitle):
        grouped = subset.groupby(["power_mode", "resolution"], as_index=False)[metric].mean()
        for power in POWER_ORDER:
            part = grouped[grouped.power_mode == power].sort_values("resolution")
            if not part.empty:
                ax.plot(part.resolution, part[metric], marker="o", color=COLORS[power], label=power)
        ax.set_xticks(sorted(data.resolution.unique()))
        ax.set_xlabel("Maximum input dimension (px)")
        ax.set_ylabel(ylabel)
        ax.legend(title="Power", fontsize=8)
    finish(fig, output)


def statistics(data, output):
    fig = None
    for fig, ax, subset in panels(data, "Inference time statistics", "Server prompt + generation; datasets pooled by image count"):
        stats = subset.groupby(["power_mode", "resolution"])["inference_s"].agg(
            mean="mean", median="median", p99=lambda values: values.quantile(.99)).reset_index()
        for power in POWER_ORDER:
            part = stats[stats.power_mode == power].sort_values("resolution")
            for statistic, style in [("mean", "-"), ("median", "--"), ("p99", ":")]:
                ax.plot(part.resolution, part[statistic], marker="o", markersize=3,
                        color=COLORS[power], linestyle=style)
        ax.set_xticks(sorted(data.resolution.unique()))
        ax.set_xlabel("Maximum input dimension (px)")
        ax.set_ylabel("Server inference time (s)")
    from matplotlib.lines import Line2D
    power_handles = [Line2D([0], [0], color=COLORS[p], label=p) for p in POWER_ORDER]
    stat_handles = [Line2D([0], [0], color="black", linestyle=s, label=n)
                    for n, s in [("Mean", "-"), ("Median", "--"), ("99th percentile", ":")]]
    fig.legend(handles=power_handles + stat_handles, loc="outside lower center", ncol=6, fontsize=9)
    finish(fig, output)


def accuracy(data, output, dimension):
    fig = None
    values = POWER_ORDER if dimension == "power_mode" else sorted(data.dataset.unique())
    colors = COLORS if dimension == "power_mode" else dict(zip(values, ["#3478b6", "#e0802c", "#3a9961"]))
    subtitle = ("Datasets pooled by image count" if dimension == "power_mode"
                else "Power modes pooled by image count")
    for fig, ax, subset in panels(data, f"Classification accuracy by {dimension.replace('_', ' ')}", subtitle):
        grouped = subset.groupby([dimension, "resolution"], as_index=False)["correct"].mean()
        for value in values:
            part = grouped[grouped[dimension] == value].sort_values("resolution")
            if not part.empty:
                ax.plot(part.resolution, 100 * part.correct, marker="o", label=value, color=colors[value])
        ax.set_xticks(sorted(data.resolution.unique()))
        ax.set_ylim(0, 105)
        ax.set_xlabel("Maximum input dimension (px)")
        ax.set_ylabel("Exact category accuracy (%)")
        ax.legend(title="Power" if dimension == "power_mode" else "Dataset", fontsize=8)
    finish(fig, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    data = load_results(args.results_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    lines(data, args.output_dir / "01_inference_time.png", "inference_s", "Inference time vs resolution", "Server inference time (s)")
    statistics(data, args.output_dir / "02_inference_statistics.png")
    lines(data, args.output_dir / "03_total_response_time.png", "response_s", "Total response time vs resolution", "Preparation + request time (s)")
    accuracy(data, args.output_dir / "04_accuracy_by_dataset.png", "dataset")
    keys = ["model", "shot_mode", "power_mode", "dataset", "resolution"]
    summary = data.groupby(keys).agg(n=("correct", "size"), accuracy=("correct", "mean"),
        inference_mean_s=("inference_s", "mean"), inference_median_s=("inference_s", "median"),
        inference_p99_s=("inference_s", lambda values: values.quantile(.99)),
        response_mean_s=("response_s", "mean")).reset_index()
    summary.to_csv(args.output_dir / "summary_by_dataset.csv", index=False)
    print(f"Plotted {len(data)} rows from {len(list(args.results_dir.rglob('folder-analysis.csv')))} files to {args.output_dir}")


if __name__ == "__main__":
    main()
