import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline
import re
import argparse

RESULTS_DIR = "train_results"

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

def plot_metrics(df: pd.DataFrame, results_dir):
    config_fields = {
        "Scheduler Type", "World Size", "Mobile Buoys", "Fixed Buoys",
        "Simulation Duration", "Sent", "Received", "Lost", "Collisions",
        "filename", "Total Buoys",
        "Motion Weight", "Density Weight", "Contact Weight", "Congestion Weight",
        "Density Midpoint", "Density Alpha", "Contact Midpoint", "Contact Alpha"
    }

    metric_columns = [col for col in df.columns if col not in config_fields]

    for metric in metric_columns:
        plt.figure(figsize=(10, 6))

        for world_size in sorted(df["World Size"].unique()):
            for scheduler in sorted(df["Scheduler Type"].unique()):
                subset = df[(df["World Size"] == world_size) & (df["Scheduler Type"] == scheduler)].copy()

                if subset.empty:
                    continue

                # Convert to numeric and drop NaNs
                subset[metric] = pd.to_numeric(subset[metric], errors="coerce")
                subset = subset.dropna(subset=[metric])

                if subset.empty:
                    continue

                grouped = subset.groupby("Total Buoys")[metric].mean().reset_index()
                x_vals = grouped["Total Buoys"].values
                y_vals = grouped[metric].values

                x_smooth, y_smooth = smooth_curve(x_vals, y_vals)
                label = f"{scheduler} ({world_size})"
                color = WORLD_SIZE_COLORS.get(world_size, "tab:gray")
                linestyle = SCHEDULER_STYLES.get(scheduler, "solid")

                plt.plot(x_smooth, y_smooth, label=label, color=color, linestyle=linestyle)
                plt.scatter(x_vals, y_vals, color=color, edgecolor='black')

        plt.title(f"{metric} vs Total Buoys")
        plt.xlabel("Total Buoys")
        plt.ylabel(metric)
        plt.grid(True)
        plt.legend(title="Scheduler + World Size", loc="best", fontsize="small")
        plt.tight_layout()
        filename = os.path.join(results_dir, f"{sanitize_filename(metric)}.png")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()

def plot_delivery_ratio(results_dir):
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
    plt.savefig(os.path.join(results_dir, "delivery_ratio_boxplot.png"), bbox_inches="tight")
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=str, default=None, help="Directory with result CSVs")
    args = parser.parse_args()

    # Priority: CLI arg > ENV > default
    results_dir = args.results_dir or os.environ.get("RESULTS_DIR", "train_results")

    print(f"Loading results from: {results_dir}")

    df = load_all_metrics(results_dir)
    if df.empty:
        print("No simulation results found.")
        return

    plot_metrics(df, results_dir)
    plot_delivery_ratio(results_dir)

    print("Plots saved to:", results_dir)

if __name__ == "__main__":
    main()
