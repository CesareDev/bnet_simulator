import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import argparse

def plot_line_metrics(results_dir, plot_dir):
    # Line plot: Delivery Ratio vs Total Buoys, one line per (scheduler, world size)
    static_files = [f for f in os.listdir(results_dir) if f.startswith("static_") and f.endswith(".csv")]
    dynamic_files = [f for f in os.listdir(results_dir) if f.startswith("dynamic_") and f.endswith(".csv")]

    def extract_info(filename):
        match = re.match(r"(static|dynamic)_(\d+)x(\d+)_mob(\d+)_fix(\d+)", filename)
        if match:
            scheduler = match.group(1)
            world_size = f"{match.group(2)}x{match.group(3)}"
            total_buoys = int(match.group(4)) + int(match.group(5))
            return scheduler, world_size, total_buoys
        return None, None, None

    data = {}
    schedulers = ["static", "dynamic"]
    world_sizes = set()
    total_buoys_set = set()

    for f in static_files + dynamic_files:
        scheduler, world_size, total_buoys = extract_info(f)
        if scheduler and world_size and total_buoys is not None:
            df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
            if "Delivery Ratio" in df.index:
                data[(scheduler, world_size, total_buoys)] = float(df.loc["Delivery Ratio", "Value"])
                world_sizes.add(world_size)
                total_buoys_set.add(total_buoys)

    # Only keep 500x500 and 800x800
    world_sizes = [ws for ws in sorted(world_sizes) if ws in ("500x500", "800x800")]
    total_buoys_list = sorted(total_buoys_set)

    color_map = {
        "500x500": "tab:blue",
        "800x800": "tab:green",
    }
    default_color = "tab:gray"

    plt.figure(figsize=(10, 6))
    for world_size in world_sizes:
        for scheduler in schedulers:
            y_vals = []
            for total_buoys in total_buoys_list:
                y_vals.append(data.get((scheduler, world_size, total_buoys), np.nan))
            label = f"{scheduler.capitalize()} {world_size}"
            color = color_map.get(world_size, default_color)
            linestyle = "-" if scheduler == "static" else "--"
            plt.plot(total_buoys_list, y_vals, label=label, color=color, linestyle=linestyle, marker="o")
    plt.title("Delivery Ratio vs Total Buoys")
    plt.xlabel("Total Buoys")
    plt.ylabel("Delivery Ratio")
    plt.grid(True)
    plt.legend(title="Scheduler + World Size", loc="best", fontsize="small")
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "delivery_ratio_line.png"), bbox_inches="tight")
    plt.close()

def plot_grouped_bar_green_blue(results_dir, plot_dir):
    # Grouped bar plot: for each total buoys, bars for each (scheduler, world size)
    static_files = [f for f in os.listdir(results_dir) if f.startswith("static_") and f.endswith(".csv")]
    dynamic_files = [f for f in os.listdir(results_dir) if f.startswith("dynamic_") and f.endswith(".csv")]

    def extract_info(filename):
        match = re.match(r"(static|dynamic)_(\d+)x(\d+)_mob(\d+)_fix(\d+)", filename)
        if match:
            scheduler = match.group(1)
            world_size = f"{match.group(2)}x{match.group(3)}"
            total_buoys = int(match.group(4)) + int(match.group(5))
            return scheduler, world_size, total_buoys
        return None, None, None

    data = {}
    world_sizes = set()
    total_buoys_set = set()
    schedulers = ["static", "dynamic"]

    for f in static_files + dynamic_files:
        scheduler, world_size, total_buoys = extract_info(f)
        if scheduler and world_size and total_buoys is not None:
            if world_size not in ("500x500", "800x800"):
                continue
            df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
            if "Delivery Ratio" in df.index:
                data[(total_buoys, world_size, scheduler)] = float(df.loc["Delivery Ratio", "Value"])
                world_sizes.add(world_size)
                total_buoys_set.add(total_buoys)

    world_sizes = [ws for ws in sorted(world_sizes) if ws in ("500x500", "800x800")]
    total_buoys_list = sorted(total_buoys_set)
    n_world = len(world_sizes)
    n_sched = len(schedulers)
    n_bars_per_group = n_world * n_sched

    color_map = {
        "500x500": "tab:blue",
        "800x800": "tab:green",
    }
    default_color = "tab:gray"

    fig, ax = plt.subplots(figsize=(max(10, len(total_buoys_list)*1.5), 7))

    bar_handles = []
    bar_labels = []
    width = 0.8 / n_bars_per_group

    for i, world_size in enumerate(world_sizes):
        color = color_map.get(world_size, default_color)
        for j, scheduler in enumerate(schedulers):
            bar_vals = []
            for total_buoys in total_buoys_list:
                val = data.get((total_buoys, world_size, scheduler), 0)
                bar_vals.append(val)
            offset = (i * n_sched + j - n_bars_per_group / 2) * width + width/2
            hatch = "//" if scheduler == "dynamic" else ""
            rects = ax.bar(np.arange(len(total_buoys_list)) + offset, bar_vals, width,
                           label=f"{scheduler.capitalize()} {world_size}",
                           color=color, hatch=hatch, edgecolor='black')
            bar_handles.append(rects[0])
            bar_labels.append(f"{scheduler.capitalize()} {world_size}")

            for rect in rects:
                height = rect.get_height()
                ax.annotate(f'{height:.2f}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=8)

    ax.set_ylabel('Delivery Ratio')
    ax.set_title('Delivery Ratio by Total Buoys, Scheduler, and World Size')
    ax.set_xticks(np.arange(len(total_buoys_list)))
    ax.set_xticklabels([str(t) for t in total_buoys_list], rotation=0, ha='center')
    ax.legend(bar_handles, bar_labels, fontsize="small", ncol=2)
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "delivery_ratio_grouped_bar_green_blue.png"), bbox_inches="tight")
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

    plot_line_metrics(results_dir, plot_dir)
    plot_grouped_bar_green_blue(results_dir, plot_dir)

    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()