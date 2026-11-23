import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "true_category",
    "test_image",
    "processing_time",
    "request_time",
    "answer_category",
    "width",
    "height",
    "prompt_file",
    "resolution",
    "model",
    "power_mode",
    "shot_mode",
}

ALLOWED_POWER_MODES = {"15W", "25W"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot VLM benchmark accuracy, inference time, and resolution scaling for 15W and 25W."
    )
    parser.add_argument(
        "-d",
        "--results-dir",
        type=Path,
        default=Path.home() / "jetson-test/test/test-result",
        help="Root directory containing test result folders (default: ~/jetson-test/test/test-result).",
    )
    parser.add_argument(
        "-f",
        "--filter",
        type=str,
        default="",
        help="Optional substring filter on folder/file path (e.g. '2B-models-optimized').",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("./plots_15w_25w"),
        help="Directory where PNG plots will be saved (default: ./plots_15w_25w).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display plots interactively after saving.",
    )
    return parser.parse_args()


def shorten_model_name(model_name: str) -> str:
    """Shorten HuggingFace/GGUF repo strings for cleaner plot legends."""
    short = model_name.split("/")[-1]
    short = short.replace("-GGUF", "").replace("_GGUF", "")
    return short


def load_all_results(results_dir: Path, path_filter: str = "") -> pd.DataFrame:
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    frames: list[pd.DataFrame] = []
    for csv_path in sorted(results_dir.rglob("*.csv")):
        if path_filter and path_filter not in str(csv_path):
            continue

        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            print(f"Skipping unreadable CSV {csv_path}: {exc}")
            continue

        if not REQUIRED_COLUMNS.issubset(df.columns) or df.empty:
            continue

        rel_parts = csv_path.relative_to(results_dir).parts
        df["experiment_suite"] = rel_parts[0] if len(rel_parts) > 1 else "root"
        df["source_csv"] = str(csv_path)
        frames.append(df)

    if not frames:
        raise ValueError(
            f"No valid result CSVs matching the expected schema found in {results_dir}"
            + (f" with filter '{path_filter}'" if path_filter else "")
        )

    combined = pd.concat(frames, ignore_index=True)

    # Normalize fields and filter strictly to 15W and 25W
    combined["power_mode_clean"] = (
        combined["power_mode"].astype(str).str.strip().str.upper()
    )
    combined = combined[combined["power_mode_clean"].isin(ALLOWED_POWER_MODES)].copy()

    if combined.empty:
        raise ValueError(
            f"No rows found with power_mode in {sorted(ALLOWED_POWER_MODES)}."
        )

    combined["true_category_clean"] = (
        combined["true_category"].astype(str).str.strip().str.lower()
    )
    combined["answer_category_clean"] = (
        combined["answer_category"].astype(str).str.strip().str.lower()
    )
    combined["is_correct"] = (
        combined["true_category_clean"] == combined["answer_category_clean"]
    )
    combined["shot_mode_clean"] = (
        combined["shot_mode"].astype(str).str.strip().str.lower()
    )
    combined["resolution"] = pd.to_numeric(combined["resolution"], errors="coerce")
    combined["request_time"] = pd.to_numeric(combined["request_time"], errors="coerce")
    combined["processing_time"] = pd.to_numeric(
        combined["processing_time"], errors="coerce"
    )
    combined["model_short"] = combined["model"].astype(str).apply(shorten_model_name)

    return combined.dropna(subset=["resolution", "request_time"])


def build_model_color_map(models: list[str]) -> dict[str, tuple]:
    cmap = plt.get_cmap("tab10")
    return {model: cmap(idx % 10) for idx, model in enumerate(sorted(models))}


def aggregate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(
            [
                "experiment_suite",
                "model",
                "model_short",
                "power_mode_clean",
                "shot_mode_clean",
                "resolution",
            ],
            as_index=False,
        )
        .agg(
            accuracy=("is_correct", lambda s: s.mean() * 100.0),
            mean_inference_time=("request_time", "mean"),
            std_inference_time=("request_time", "std"),
            mean_processing_time=("processing_time", "mean"),
            sample_count=("is_correct", "count"),
        )
        .sort_values(["power_mode_clean", "model_short", "resolution"])
    )
    return grouped


def plot_accuracy_scatter(
    summary: pd.DataFrame,
    color_map: dict[str, tuple],
    output_dir: Path,
) -> None:
    """Plot 1: Accuracy of models using a scatterplot (15W vs 25W)."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    suites = sorted(summary["experiment_suite"].unique())
    suite_to_x = {suite: idx for idx, suite in enumerate(suites)}
    models = sorted(summary["model_short"].unique())

    offsets = (
        np.linspace(-0.22, 0.22, num=max(len(models), 1))
        if len(models) > 1
        else [0.0]
    )
    model_offset = dict(zip(models, offsets))
    shot_markers = {"one-shot": "o", "zero-shot": "^"}

    for model in models:
        m_df = summary[summary["model_short"] == model]
        for shot_mode, s_df in m_df.groupby("shot_mode_clean"):
            x_vals = [
                suite_to_x[s] + model_offset[model] for s in s_df["experiment_suite"]
            ]
            sizes = 70 + (s_df["resolution"] / s_df["resolution"].max()) * 110
            ax.scatter(
                x_vals,
                s_df["accuracy"],
                color=color_map[model],
                marker=shot_markers.get(shot_mode, "o"),
                s=sizes,
                alpha=0.85,
                edgecolors="black",
                linewidths=0.7,
                label=f"{model} ({shot_mode})",
            )

            for x, (_, row) in zip(x_vals, s_df.iterrows()):
                ax.annotate(
                    f"{row['accuracy']:.1f}% ({int(row['resolution'])}px)",
                    (x, row["accuracy"]),
                    textcoords="offset points",
                    xytext=(0, 7),
                    ha="center",
                    fontsize=7.5,
                    color="#222222",
                )

    ax.set_xticks(range(len(suites)))
    ax.set_xticklabels(suites, rotation=15, ha="right")
    ax.set_ylabel("Accuracy (%)")
    ax.set_xlabel("Experiment Suite (15W vs. 25W)")
    ax.set_title("Model Accuracy Across 15W & 25W Power Modes")
    ax.set_ylim(0, 108)
    ax.grid(True, linestyle="--", alpha=0.4)

    handles, labels = ax.get_legend_handles_labels()
    unique_legend = dict(zip(labels, handles))
    ax.legend(
        unique_legend.values(),
        unique_legend.keys(),
        title="Model (Shot Mode)",
        loc="best",
        framealpha=0.9,
    )

    fig.tight_layout()
    fig.savefig(output_dir / "1_model_accuracy_scatterplot_15w_25w.png", dpi=300)


def plot_inference_time_vs_accuracy(
    summary: pd.DataFrame,
    color_map: dict[str, tuple],
    output_dir: Path,
) -> None:
    """Plot 2: Inference time vs. Accuracy colored by model (15W vs 25W)."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    power_markers = {"15W": "o", "25W": "s"}
    models = sorted(summary["model_short"].unique())

    for model in models:
        m_df = summary[summary["model_short"] == model]
        for power_mode, p_df in m_df.groupby("power_mode_clean"):
            ax.scatter(
                p_df["mean_inference_time"],
                p_df["accuracy"],
                color=color_map[model],
                marker=power_markers.get(power_mode, "P"),
                s=115,
                alpha=0.88,
                edgecolors="black",
                linewidths=0.7,
                label=f"{model} [{power_mode}]",
            )

            for _, row in p_df.iterrows():
                ax.annotate(
                    f"{int(row['resolution'])}px | {row['shot_mode_clean']}",
                    (row["mean_inference_time"], row["accuracy"]),
                    textcoords="offset points",
                    xytext=(6, 4),
                    fontsize=7.5,
                    color="#222222",
                )

    ax.set_xlabel("Mean Inference Time per Image (seconds) [request_time]")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Inference Time vs. Accuracy by Model (15W vs. 25W)")
    ax.set_ylim(0, 108)
    ax.grid(True, linestyle="--", alpha=0.4)

    handles, labels = ax.get_legend_handles_labels()
    unique_legend = dict(zip(labels, handles))
    ax.legend(
        unique_legend.values(),
        unique_legend.keys(),
        title="Model [Power Mode]",
        loc="best",
        framealpha=0.9,
    )

    fig.tight_layout()
    fig.savefig(output_dir / "2_inference_time_vs_accuracy_15w_25w.png", dpi=300)


def plot_accuracy_vs_resolution(
    summary: pd.DataFrame,
    color_map: dict[str, tuple],
    output_dir: Path,
) -> None:
    """Plot 3: Accuracy of models scaled with image resolution (15W vs 25W)."""
    fig, ax = plt.subplots(figsize=(11, 6.5))

    line_styles = {"15W": "-", "25W": "--"}
    shot_markers = {"one-shot": "o", "zero-shot": "^"}
    resolutions = sorted(summary["resolution"].unique())

    group_cols = ["model_short", "experiment_suite", "power_mode_clean", "shot_mode_clean"]
    for (model, suite, power_mode, shot_mode), g_df in summary.groupby(group_cols):
        g_df = g_df.sort_values("resolution")
        ax.plot(
            g_df["resolution"],
            g_df["accuracy"],
            color=color_map[model],
            linestyle=line_styles.get(power_mode, "-."),
            marker=shot_markers.get(shot_mode, "o"),
            markersize=8,
            linewidth=2.0,
            alpha=0.9,
            label=f"{model} | {power_mode} | {suite} ({shot_mode})",
        )

        for _, row in g_df.iterrows():
            ax.annotate(
                f"{row['accuracy']:.1f}%",
                (row["resolution"], row["accuracy"]),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=7.5,
            )

    ax.set_xticks(resolutions)
    ax.set_xticklabels([f"{int(r)}x{int(r)}" for r in resolutions])
    ax.set_xlabel("Input Resolution (px)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Model Accuracy Scaling with Resolution (15W vs. 25W)")
    ax.set_ylim(0, 108)
    ax.grid(True, linestyle="--", alpha=0.4)

    handles, labels = ax.get_legend_handles_labels()
    unique_legend = dict(zip(labels, handles))
    ax.legend(
        unique_legend.values(),
        unique_legend.keys(),
        title="Model | Power | Suite (Shot Mode)",
        loc="best",
        fontsize=8.5,
        framealpha=0.9,
    )

    fig.tight_layout()
    fig.savefig(output_dir / "3_accuracy_vs_resolution_15w_25w.png", dpi=300)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = load_all_results(args.results_dir, args.filter)
    summary = aggregate_metrics(df)

    print("\n=== Aggregated Benchmark Summary (15W & 25W Only) ===")
    print(summary.to_string(index=False))

    color_map = build_model_color_map(summary["model_short"].unique().tolist())

    plot_accuracy_scatter(summary, color_map, args.output_dir)
    plot_inference_time_vs_accuracy(summary, color_map, args.output_dir)
    plot_accuracy_vs_resolution(summary, color_map, args.output_dir)

    print(f"\nSaved 3 plots to: {args.output_dir.resolve()}")
    if args.show:
        plt.show()


if __name__ == "__main__":
    main()