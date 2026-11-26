#!/usr/bin/env python3
"""Explore classification errors, paired shot modes and latency in one benchmark run."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_all_models_run import DEFAULT_INPUT, POWER_ORDER, load_results

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "test/data_procesisng/python/plots_benchmark_gaps_20261125-221751"
GROUP = ["model", "model_short", "shot_mode", "power_mode", "resolution", "dataset"]
PAIR_KEY = ["model", "model_short", "power_mode", "resolution", "dataset", "true_category", "test_image"]


def classify(data):
    data = data.copy()
    if data[["true_category", "answer_category", "test_image"]].isna().any().any():
        raise ValueError("Missing category or image path; cannot assess accuracy")
    data["is_defect"] = data.true_category.ne("good")
    data["pred_defect"] = data.answer_category.ne("good")
    return data


def paired_results(data):
    if data.duplicated(PAIR_KEY + ["shot_mode"]).any():
        raise ValueError("Duplicate image/configuration/shot rows; analyze repeat runs separately")
    one = data[data.shot_mode == "one-shot"]
    zero = data[data.shot_mode == "zero-shot"]
    # Include true_category in the key and fail on mismatching labels for the same image.
    identity = [key for key in PAIR_KEY if key != "true_category"]
    labels = one[identity + ["true_category"]].merge(zero[identity + ["true_category"]],
                on=identity, suffixes=("_one", "_zero"), validate="one_to_one")
    if labels.true_category_one.ne(labels.true_category_zero).any():
        raise ValueError("True categories differ between shot modes for a paired image")
    pair = one[PAIR_KEY + ["correct"]].merge(zero[PAIR_KEY + ["correct"]], on=PAIR_KEY,
                                              suffixes=("_one", "_zero"), validate="one_to_one")
    if pair.empty:
        raise ValueError("No images matched between one-shot and zero-shot")
    pair["one_only_correct"] = pair.correct_one & ~pair.correct_zero
    pair["zero_only_correct"] = ~pair.correct_one & pair.correct_zero
    keys = ["model", "model_short", "power_mode", "resolution", "dataset"]
    result = pair.groupby(keys).agg(n=("correct_one", "size"), one_accuracy=("correct_one", "mean"),
        zero_accuracy=("correct_zero", "mean"), one_only_correct=("one_only_correct", "sum"),
        zero_only_correct=("zero_only_correct", "sum")).reset_index()
    result["difference_pp"] = 100 * (result.one_accuracy - result.zero_accuracy)
    return result


def metrics(data):
    rows = []
    for key, group in data.groupby(GROUP, sort=True):
        defect = group[group.is_defect]
        good = group[~group.is_defect]
        class_recall = group.groupby("true_category").correct.mean()
        rows.append(dict(zip(GROUP, key), n=len(group), n_defect=len(defect), n_good=len(good),
            exact_accuracy=group.correct.mean(), balanced_accuracy=class_recall.mean(),
            defect_recall=defect.pred_defect.mean() if len(defect) else np.nan,
            false_positive_rate=good.pred_defect.mean() if len(good) else np.nan,
            response_mean_s=group.response_s.mean(), server_mean_s=group.inference_s.mean()))
    return pd.DataFrame(rows)


def save(fig, path):
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def heatmap(ax, matrix, labels_x, labels_y, percent=True, counts=None):
    image = ax.imshow(matrix, vmin=0, vmax=100 if percent else None, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(labels_x)), labels_x, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels_y)), labels_y, fontsize=8)
    for i in range(len(labels_y)):
        for j in range(len(labels_x)):
            value = matrix[i, j]
            if np.isfinite(value):
                label = f"{value:.0f}%" if percent else f"{value:.1f}"
                if counts is not None:
                    label += f"\n(n={counts[i, j]})"
                ax.text(j, i, label, ha="center", va="center", fontsize=7,
                        color="white" if value >= 60 else "black")
    return image


def confusion(data, out, power, resolution):
    selected = data[(data.power_mode == power) & (data.resolution == resolution)]
    for dataset, frame in selected.groupby("dataset"):
        models, shots = sorted(data.model_short.unique()), sorted(data.shot_mode.unique())
        fig, axes = plt.subplots(len(models), len(shots), figsize=(6.4 * len(shots), 5.2 * len(models)),
                                 squeeze=False, layout="constrained")
        fig.suptitle(f"{dataset}: category confusion · {power}, {resolution}px\nRow-normalized; n is the number of evaluated images", fontsize=14)
        for i, model in enumerate(models):
            for j, shot in enumerate(shots):
                ax = axes[i, j]
                subset = frame[(frame.model_short == model) & (frame.shot_mode == shot)]
                ax.set_title(f"{model} · {shot}", fontsize=10)
                if subset.empty:
                    ax.text(.5, .5, "No data", ha="center", transform=ax.transAxes)
                    continue
                labels = sorted(set(subset.true_category) | set(subset.answer_category))
                counts = pd.crosstab(subset.true_category, subset.answer_category).reindex(index=labels, columns=labels, fill_value=0)
                denom = counts.sum(axis=1).replace(0, np.nan)
                pct = counts.div(denom, axis=0).to_numpy() * 100
                image = heatmap(ax, pct, labels, labels)
                ax.set_yticks(range(len(labels)), [f"{label} (n={n})" for label, n in zip(labels, counts.sum(axis=1))], fontsize=8)
                ax.set_xlabel("Predicted category")
                ax.set_ylabel("True category")
        fig.colorbar(image, ax=axes, label="% of true category", shrink=.72)
        save(fig, out / f"01_confusion_{dataset}.png")


def category_accuracy(data, out, power, resolution):
    selected = data[(data.power_mode == power) & (data.resolution == resolution)]
    for dataset, frame in selected.groupby("dataset"):
        table = frame.groupby(["model_short", "shot_mode", "true_category"]).correct.agg(["mean", "size"])
        categories = sorted(frame.true_category.unique())
        configs = sorted(set(zip(frame.model_short, frame.shot_mode)))
        values = np.full((len(configs), len(categories)), np.nan)
        ns = np.zeros_like(values, dtype=int)
        for i, config in enumerate(configs):
            for j, cat in enumerate(categories):
                if (*config, cat) in table.index:
                    row = table.loc[(*config, cat)]
                    values[i, j], ns[i, j] = 100 * row["mean"], int(row["size"])
        fig, ax = plt.subplots(figsize=(max(8, len(categories) * 1.3), 4.3), layout="constrained")
        image = heatmap(ax, values, categories, [f"{m}\n{s}" for m, s in configs], counts=ns)
        ax.set_title(f"{dataset}: exact category recall · {power}, {resolution}px")
        ax.set_xlabel("True category")
        fig.colorbar(image, ax=ax, label="Correctly classified (%)")
        save(fig, out / f"02_category_recall_{dataset}.png")


def detection_plots(table, out, power, resolution):
    subset = table[(table.power_mode == power) & (table.resolution == resolution)]
    datasets = sorted(subset.dataset.unique())
    configs = sorted(set(zip(subset.model_short, subset.shot_mode)))
    fig, axes = plt.subplots(1, 2, figsize=(15, max(4, len(configs)*1.1)), layout="constrained")
    for ax, metric, title, count in zip(axes, ["defect_recall", "false_positive_rate"],
        ["Defect detection recall", "False positive rate on good images"], ["n_defect", "n_good"]):
        values = np.full((len(configs), len(datasets)), np.nan)
        ns = np.zeros_like(values, dtype=int)
        for i, (model, shot) in enumerate(configs):
            for j, dataset in enumerate(datasets):
                rows = subset[(subset.model_short == model) & (subset.shot_mode == shot) & (subset.dataset == dataset)]
                if len(rows):
                    values[i,j] = 100 * rows.iloc[0][metric]
                    ns[i,j] = int(rows.iloc[0][count])
        image = heatmap(ax, values, datasets, [f"{m}\n{s}" for m, s in configs], counts=ns)
        ax.set_title(title)
    fig.colorbar(image, ax=axes, label="Rate (%)", shrink=.8)
    fig.suptitle(f"Binary defect detection · {power}, {resolution}px", fontsize=14)
    save(fig, out / "03_defect_detection.png")


def balanced_plot(table, out, power, resolution):
    subset = table[(table.power_mode == power) & (table.resolution == resolution)]
    datasets = sorted(subset.dataset.unique())
    configs = sorted(set(zip(subset.model_short, subset.shot_mode)))
    fig, axes = plt.subplots(1, 2, figsize=(15, max(4, len(configs)*1.1)), layout="constrained")
    for ax, metric, title in zip(axes, ["exact_accuracy", "balanced_accuracy"], ["Overall exact accuracy", "Balanced accuracy (mean class recall)"]):
        values = np.full((len(configs), len(datasets)), np.nan)
        ns = np.zeros_like(values, dtype=int)
        for i, (model, shot) in enumerate(configs):
            for j, dataset in enumerate(datasets):
                rows = subset[(subset.model_short == model) & (subset.shot_mode == shot) & (subset.dataset == dataset)]
                if len(rows):
                    values[i,j] = 100 * rows.iloc[0][metric]
                    ns[i,j] = int(rows.iloc[0]["n"])
        image = heatmap(ax, values, datasets, [f"{m}\n{s}" for m, s in configs], counts=ns)
        ax.set_title(title)
    fig.colorbar(image, ax=axes, label="Accuracy (%)", shrink=.8)
    fig.suptitle(f"Effect of category imbalance · {power}, {resolution}px", fontsize=14)
    save(fig, out / "04_balanced_accuracy.png")


def paired_plot(pair, out, power):
    pair = pair[pair.power_mode == power]
    models = sorted(pair.model_short.unique())
    datasets = sorted(pair.dataset.unique())
    fig, axes = plt.subplots(len(models), len(datasets), figsize=(5 * len(datasets), 2.4 * len(models)),
                             squeeze=False, layout="constrained")
    image = None
    limit = max(10, np.ceil(pair.difference_pp.abs().max() / 10) * 10)
    for i, model in enumerate(models):
        for j, dataset in enumerate(datasets):
            ax = axes[i,j]
            frame = pair[(pair.model_short == model) & (pair.dataset == dataset)]
            resolutions = sorted(pair.resolution.unique())
            values = np.full((1, len(resolutions)), np.nan)
            ns = np.zeros_like(values, dtype=int)
            for x, res in enumerate(resolutions):
                row = frame[frame.resolution == res]
                if len(row):
                    values[0,x] = row.iloc[0].difference_pp
                    ns[0,x] = int(row.iloc[0].n)
            image = ax.imshow(values, cmap="RdBu", vmin=-limit, vmax=limit, aspect="auto")
            for x in range(len(resolutions)):
                if np.isfinite(values[0,x]):
                    ax.text(x, 0, f"{values[0,x]:+.1f} pp\n(n={ns[0,x]})", ha="center", va="center", fontsize=9)
            ax.set_xticks(range(len(resolutions)), resolutions)
            ax.set_yticks([])
            ax.set_xlabel("Maximum input dimension (px)")
            ax.set_title(f"{model}\n{dataset}", fontsize=10)
    fig.colorbar(image, ax=axes, label="One-shot minus zero-shot (percentage points)", shrink=.8)
    fig.suptitle(f"Paired exact accuracy difference on the same images · {power}", fontsize=14)
    save(fig, out / "05_paired_shot_accuracy.png")


def tradeoff(table, out):
    models, shots = sorted(table.model_short.unique()), sorted(table.shot_mode.unique())
    datasets = sorted(table.dataset.unique())
    colors = dict(zip(datasets, plt.get_cmap("tab10").colors))
    markers = dict(zip(POWER_ORDER, ["o", "s", "^"]))
    fig, axes = plt.subplots(len(models), len(shots), figsize=(7 * len(shots), 4.6 * len(models)),
                             squeeze=False, sharex=True, sharey=True, layout="constrained")
    for i, model in enumerate(models):
        for j, shot in enumerate(shots):
            ax = axes[i,j]
            frame = table[(table.model_short == model) & (table.shot_mode == shot)]
            for _, row in frame.iterrows():
                ax.scatter(row.response_mean_s, 100*row.defect_recall, c=[colors[row.dataset]],
                           marker=markers[row.power_mode], s=55)
                ax.annotate(str(int(row.resolution)), (row.response_mean_s, 100*row.defect_recall),
                            xytext=(4,4), textcoords="offset points", fontsize=7)
            ax.set_title(f"{model} · {shot}", fontsize=10)
            ax.set_xlabel("Mean preparation + request time (s)")
            ax.set_ylabel("Defect detection recall (%)")
            ax.set_ylim(0, 105)
            ax.grid(alpha=.2)
    from matplotlib.lines import Line2D
    legend = [Line2D([], [], marker="o", color=color, linestyle="", label=dataset) for dataset, color in colors.items()]
    legend += [Line2D([], [], marker=marker, color="black", linestyle="", label=power) for power, marker in markers.items()]
    fig.legend(handles=legend, loc="outside lower center", ncol=len(legend))
    fig.suptitle("Detection recall vs response time · labels show resolution (px)", fontsize=14)
    save(fig, out / "06_recall_vs_response_time.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--power-mode", default="15W", type=str.upper, choices=POWER_ORDER,
                        help="Power mode for detailed error plots (default: 15W)")
    parser.add_argument("--resolution", default=512, type=int, help="Resolution for detailed error plots (default: 512)")
    args = parser.parse_args()
    data = classify(load_results(args.results_dir))
    if data[(data.power_mode == args.power_mode) & (data.resolution == args.resolution)].empty:
        parser.error("No data for the selected power mode and resolution")
    table, pair = metrics(data), paired_results(data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    confusion(data, args.output_dir, args.power_mode, args.resolution)
    category_accuracy(data, args.output_dir, args.power_mode, args.resolution)
    detection_plots(table, args.output_dir, args.power_mode, args.resolution)
    balanced_plot(table, args.output_dir, args.power_mode, args.resolution)
    paired_plot(pair, args.output_dir, args.power_mode)
    tradeoff(table, args.output_dir)
    table.to_csv(args.output_dir / "detection_and_accuracy_metrics.csv", index=False)
    pair.to_csv(args.output_dir / "paired_shot_metrics.csv", index=False)
    print(f"Analyzed {len(data)} rows; {len(pair)} paired model/power/resolution/dataset groups; output: {args.output_dir}")


if __name__ == "__main__":
    main()
