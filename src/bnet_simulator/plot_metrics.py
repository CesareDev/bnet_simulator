import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import argparse

score_func_hatch = {
    "sigmoid": "",
    "linear": "xx",
    "tanh": "//",
}

def extract_info(filename, results_dir):
    match = re.match(r"(static|dynamic)_(\d+)x(\d+)_mob(\d+)_fix(\d+)", filename)
    if match:
        scheduler = match.group(1)
        total_buoys = int(match.group(4)) + int(match.group(5))
        df = pd.read_csv(os.path.join(results_dir, filename), index_col=0)
        score_func = "sigmoid"
        if "Score Function" in df.index:
            score_func = str(df.loc["Score Function", "Value"])
        return scheduler, total_buoys, score_func
    return None, None, None

def plot_grouped_bar_metric(results_dir, plot_dir, metric, filename, ylabel, title):
    static_files = [f for f in os.listdir(results_dir) if f.startswith("static_") and f.endswith(".csv")]
    dynamic_files = [f for f in os.listdir(results_dir) if f.startswith("dynamic_") and f.endswith(".csv")]

    data = {}
    schedulers = ["static", "dynamic"]
    total_buoys_set = set()
    score_funcs = set()

    for f in static_files + dynamic_files:
        scheduler, total_buoys, score_func = extract_info(f, results_dir)
        if scheduler and total_buoys is not None:
            df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
            if metric in df.index:
                data[(total_buoys, scheduler, score_func)] = float(df.loc[metric, "Value"])
                total_buoys_set.add(total_buoys)
                score_funcs.add(score_func)

    total_buoys_list = sorted(total_buoys_set)
    score_funcs = sorted(score_funcs)
    n_sched = len(schedulers)
    n_score = len(score_funcs)
    n_bars_per_group = n_sched * n_score

    color_map = {
        "static": "tab:blue",
        "dynamic": "tab:green",
    }

    fig, ax = plt.subplots(figsize=(max(10, len(total_buoys_list)*1.5), 7))

    bar_handles = []
    bar_labels = []
    width = 0.8 / n_bars_per_group

    for j, scheduler in enumerate(schedulers):
        for k, score_func in enumerate(score_funcs):
            bar_vals = []
            for total_buoys in total_buoys_list:
                bar_vals.append(data.get((total_buoys, scheduler, score_func), 0))
            offset = (j * n_score + k - n_bars_per_group / 2) * width + width/2
            color = color_map[scheduler]
            hatch = score_func_hatch.get(score_func, "") if scheduler == "dynamic" else ""
            rects = ax.bar(np.arange(len(total_buoys_list)) + offset, bar_vals, width,
                           label=f"{scheduler.capitalize()} ({score_func})",
                           color=color, hatch=hatch, edgecolor='black')
            bar_handles.append(rects[0])
            bar_labels.append(f"{scheduler.capitalize()} ({score_func})")

            for rect in rects:
                height = rect.get_height()
                ax.annotate(f'{height:.2f}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=8)

    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(total_buoys_list)))
    ax.set_xticklabels([str(t) for t in total_buoys_list], rotation=0, ha='center')
    ax.legend(bar_handles, bar_labels, fontsize="small", ncol=2)
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, filename), bbox_inches="tight")
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=str, default=None, help="Directory with result CSVs")
    parser.add_argument("--plot-dir", type=str, default=None, help="Directory to save plots")
    args = parser.parse_args()

    results_dir = args.results_dir or os.environ.get("RESULTS_DIR", "tune_results")
    plot_dir = args.plot_dir or os.environ.get("PLOT_DIR", "tune_plots")

    print(f"Loading results from: {results_dir}")
    print(f"Saving plots to: {plot_dir}")

    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir, exist_ok=True)

    plot_grouped_bar_metric(
        results_dir, plot_dir,
        metric="Delivery Ratio",
        filename="delivery_ratio_grouped_bar.png",
        ylabel="Delivery Ratio",
        title="Delivery Ratio by Total Buoys, Scheduler, Score Function"
    )
    plot_grouped_bar_metric(
        results_dir, plot_dir,
        metric="Collision Rate",
        filename="collision_rate_grouped_bar.png",
        ylabel="Collision Rate",
        title="Collision Rate by Total Buoys, Scheduler, Score Function"
    )

    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()