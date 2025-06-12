import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline
import re
import argparse

# Colors based on World Size
WORLD_SIZE_COLORS = {
    "500.0x500.0": "tab:blue",
    "800.0x800.0": "tab:green",
    "1200.0x1200.0": "tab:red",
    "Other": "tab:gray"
}

# Line styles based on Scheduler Type
SCHEDULER_STYLES = {
    "static": "solid",
    "dynamic": "dashed",
    "rl": "dotted"
}

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())

def load_all_metrics(results_dir):
    data = []
    for csv_file in glob.glob(os.path.join(results_dir, "*.csv")):
        df = pd.read_csv(csv_file, index_col=0)
        row = df["Value"].to_dict()
        row["filename"] = os.path.basename(csv_file)

        try:
            row["Mobile Buoys"] = int(row.get("Mobile Buoys", 0))
            row["Fixed Buoys"] = int(row.get("Fixed Buoys", 0))
            row["Total Buoys"] = row["Mobile Buoys"] + row["Fixed Buoys"]
        except:
            row["Mobile Buoys"] = 0
            row["Fixed Buoys"] = 0
            row["Total Buoys"] = 0

        row["World Size"] = str(row.get("World Size", "Other"))
        data.append(row)

    return pd.DataFrame(data)

def smooth_curve(x_vals, y_vals):
    if len(x_vals) < 4:
        return x_vals, y_vals
    x_sorted = np.array(sorted(x_vals))
    y_sorted = np.array([y for _, y in sorted(zip(x_vals, y_vals))])
    try:
        spline = make_interp_spline(x_sorted, y_sorted, k=2)
        x_smooth = np.linspace(x_sorted.min(), x_sorted.max(), 200)
        y_smooth = spline(x_smooth)
        return x_smooth, y_smooth
    except Exception:
        return x_sorted, y_sorted

def plot_metrics(df: pd.DataFrame, plot_dir):
    metric = "Delivery Ratio"
    plt.figure(figsize=(10, 6))
    for world_size in sorted(df["World Size"].unique()):
        for scheduler in sorted(df["Scheduler Type"].unique()):
            subset = df[(df["World Size"] == world_size) & (df["Scheduler Type"] == scheduler)].copy()
            if subset.empty:
                continue
            subset[metric] = pd.to_numeric(subset[metric], errors="coerce")
            subset = subset.dropna(subset=[metric])
            if subset.empty:
                continue
            grouped = subset.groupby("Total Buoys")[metric].mean().reset_index()
            x_vals = grouped["Total Buoys"].values
            y_vals = grouped[metric].values
            plt.plot(x_vals, y_vals, label=f"{scheduler} ({world_size})")
            plt.scatter(x_vals, y_vals)
    plt.title(f"{metric} vs Total Buoys")
    plt.xlabel("Total Buoys")
    plt.ylabel(metric)
    plt.grid(True)
    plt.legend(title="Scheduler + World Size", loc="best", fontsize="small")
    plt.tight_layout()
    filename = os.path.join(plot_dir, f"{sanitize_filename(metric)}.png")
    plt.savefig(filename, bbox_inches="tight")
    plt.close()

def plot_delivery_ratio(results_dir, plot_dir):
    static_files = [f for f in os.listdir(results_dir) if f.startswith("static_") and f.endswith(".csv")]
    dynamic_files = [f for f in os.listdir(results_dir) if f.startswith("dynamic_") and f.endswith(".csv")]

    static_ratios = []
    dynamic_ratios = []

    for f in static_files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Delivery Ratio" in df.index:
            try:
                val = float(df.loc["Delivery Ratio", "Value"])
                static_ratios.append(val)
            except Exception:
                pass
    for f in dynamic_files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Delivery Ratio" in df.index:
            try:
                val = float(df.loc["Delivery Ratio", "Value"])
                dynamic_ratios.append(val)
            except Exception:
                pass

    plt.figure(figsize=(8, 5))
    plt.boxplot([static_ratios, dynamic_ratios], tick_labels=["Static", "Dynamic"])
    plt.ylabel("Delivery Ratio")
    plt.title("Delivery Ratio: Static vs Dynamic (Test Set)")
    plt.grid(True)
    plt.savefig(os.path.join(plot_dir, "delivery_ratio_boxplot.png"), bbox_inches="tight")
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=str, default=None, help="Directory with result CSVs")
    parser.add_argument("--plot-dir", type=str, default=None, help="Directory to save plots")
    args = parser.parse_args()

    # Default: tune_results for tuning, tune_plots for tuning plots
    results_dir = args.results_dir or os.environ.get("RESULTS_DIR", "tune_results")
    plot_dir = args.plot_dir or os.environ.get("PLOT_DIR", "tune_plots")

    print(f"Loading results from: {results_dir}")
    print(f"Saving plots to: {plot_dir}")

    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir, exist_ok=True)

    df = load_all_metrics(results_dir)
    if df.empty:
        print("No simulation results found.")
        return

    plot_metrics(df, plot_dir)
    plot_delivery_ratio(results_dir, plot_dir)

    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()
