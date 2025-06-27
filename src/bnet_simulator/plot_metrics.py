import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def plot_block_by_density(results_dir, plot_dir):
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    data = []
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Density" in df.index and "Delivery Ratio" in df.index and "Scheduler Type" in df.index:
            density = float(df.loc["Density", "Value"])
            pdr = float(df.loc["Delivery Ratio", "Value"])
            sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            data.append((density, pdr, sched_type))
        # fallback: infer scheduler type from filename if not present
        elif "Density" in df.index and "Delivery Ratio" in df.index:
            density = float(df.loc["Density", "Value"])
            pdr = float(df.loc["Delivery Ratio", "Value"])
            if f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic"
            else:
                sched_type = "unknown"
            data.append((density, pdr, sched_type))
    if not data:
        print("No data with density found.")
        return

    # Group by density and scheduler type
    df = pd.DataFrame(data, columns=["Density", "PDR", "Scheduler"])
    grouped = df.groupby(["Density", "Scheduler"]).mean().reset_index()

    densities = sorted(df["Density"].unique())
    schedulers = ["static", "dynamic"]
    color_map = {"static": "tab:blue", "dynamic": "tab:green"}

    bar_width = 0.25
    x = np.arange(len(densities))

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, sched in enumerate(schedulers):
        pdrs = []
        for d in densities:
            row = grouped[(grouped["Density"] == d) & (grouped["Scheduler"] == sched)]
            pdrs.append(row["PDR"].values[0] if not row.empty else 0)
        ax.bar(x + i * bar_width, pdrs, bar_width, label=sched.capitalize(), color=color_map[sched])

    ax.set_xlabel("Local Density (neighbors in range)")
    ax.set_ylabel("Delivery Ratio")
    ax.set_title("Delivery Ratio vs Local Density (Block Plot)")
    ax.set_xticks(x + bar_width)
    ax.set_xticklabels([str(int(d)) for d in densities])
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "delivery_ratio_block_by_density.png"))
    plt.close()

def main():
    import argparse
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

    plot_block_by_density(results_dir, plot_dir)

    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()