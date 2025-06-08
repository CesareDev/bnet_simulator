import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import re
import numpy as np
from scipy.interpolate import make_interp_spline

RESULTS_DIR = "simulation_results"
METRICS_TO_PLOT = [
    "Delivery Ratio", "Collisions", "Avg Latency",
    "Avg Scheduler Latency", "Throughput (beacons/sec)",
    "Avg Reaction Latency"
]

COLORS = {
    "static": "tab:blue",
    "dynamic": "tab:green",
    "rl": "tab:red"
}

LINESTYLES = {
    "Density": "-",
    "Mobility": "--",
    "Scale": "-."
}

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())

def classify_scenario(row):
    world_size = row.get("World Size", "")
    total = int(row.get("Mobile Buoys", 0)) + int(row.get("Fixed Buoys", 0))
    if world_size == "500.0x500.0":
        return "Density"
    elif world_size == "800.0x800.0" and total == 30:
        return "Mobility"
    elif world_size in {"400.0x400.0", "800.0x800.0", "1200.0x1200.0"}:
        return "Scale"
    return "Other"

def load_all_metrics():
    data = []
    for csv_file in glob.glob(os.path.join(RESULTS_DIR, "*.csv")):
        df = pd.read_csv(csv_file, index_col=0, header=0)
        row = df["Value"].to_dict()
        row["filename"] = os.path.basename(csv_file)
        try:
            row["Mobile Buoys"] = int(row.get("Mobile Buoys", 0))
            row["Fixed Buoys"] = int(row.get("Fixed Buoys", 0))
            row["Total Buoys"] = row["Mobile Buoys"] + row["Fixed Buoys"]
        except Exception:
            row["Mobile Buoys"] = 0
            row["Fixed Buoys"] = 0
            row["Total Buoys"] = 0
        row["Scenario"] = classify_scenario(row)
        data.append(row)
    return pd.DataFrame(data)

def plot_metrics(df: pd.DataFrame):
    for metric in METRICS_TO_PLOT:
        plt.figure(figsize=(10, 6))
        for scenario in sorted(df["Scenario"].unique()):
            for scheduler in sorted(df["Scheduler Type"].unique()):
                subset = df[(df["Scheduler Type"] == scheduler) & (df["Scenario"] == scenario)]
                if subset.empty:
                    continue
                subset = subset.copy()
                subset[metric] = pd.to_numeric(subset[metric], errors="coerce")
                grouped = subset.groupby("Total Buoys")[metric].mean().reset_index()
                x_vals = grouped["Total Buoys"].values
                y_vals = grouped[metric].clip(lower=0).values

                # Interpolate only if enough unique points
                if len(x_vals) >= 4:
                    try:
                        spline = make_interp_spline(x_vals, y_vals, k=2)
                        x_smooth = np.linspace(x_vals.min(), x_vals.max(), 100)
                        y_smooth = spline(x_smooth)
                        plt.plot(
                            x_smooth, y_smooth,
                            label=f"{scheduler} ({scenario})",
                            color=COLORS.get(scheduler, None),
                            linestyle=LINESTYLES.get(scenario, "-"),
                        )
                    except Exception:
                        plt.plot(
                            x_vals, y_vals,
                            label=f"{scheduler} ({scenario})",
                            color=COLORS.get(scheduler, None),
                            linestyle=LINESTYLES.get(scenario, "-"),
                        )
                # Always plot the real data points
                plt.scatter(
                    x_vals, y_vals,
                    color=COLORS.get(scheduler, None),
                    marker='o'
                )

        plt.title(f"{metric} vs Total Buoys")
        plt.xlabel("Total Buoys")
        plt.ylabel(metric)
        plt.grid(True)
        plt.legend(title="Scheduler (Scenario)")
        plt.tight_layout()
        filename = os.path.join(RESULTS_DIR, f"{sanitize_filename(metric)}.png")
        plt.savefig(filename, bbox_inches="tight")
        plt.close()

def main():
    df = load_all_metrics()
    if df.empty:
        print("No simulation results found.")
        return
    plot_metrics(df)
    print("Plots saved in:", RESULTS_DIR)

if __name__ == "__main__":
    main()
