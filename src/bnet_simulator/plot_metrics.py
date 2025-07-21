import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re

def plot_block_by_density(results_dir, plot_dir, interval=None):
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    data = []
    collision_data = []  # Added for collision rate
    
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        
        # Process delivery ratio data
        if "Density" in df.index and "Delivery Ratio" in df.index:
            density = float(df.loc["Density", "Value"])
            pdr = float(df.loc["Delivery Ratio", "Value"])
            
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic"
            else:
                sched_type = "unknown"
                
            data.append((density, pdr, sched_type))
            
        # Process collision rate data
        if "Density" in df.index and "Collision Rate" in df.index:
            density = float(df.loc["Density", "Value"])
            collision_rate = float(df.loc["Collision Rate", "Value"])
            
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic"
            else:
                sched_type = "unknown"
                
            collision_data.append((density, collision_rate, sched_type))
    
    if not data:
        print("No delivery ratio data with density found.")
    else:
        # Plot delivery ratio
        # Group by density and scheduler type
        df = pd.DataFrame(data, columns=["Density", "PDR", "Scheduler"])
        grouped = df.groupby(["Density", "Scheduler"]).mean().reset_index()

        densities = sorted(df["Density"].unique())
        schedulers = ["static", "dynamic"]
        
        # Always use SBP and ACAB names
        scheduler_labels = {"static": "SBP", "dynamic": "ACAB"}
        color_map = {"static": "tab:blue", "dynamic": "tab:green"}

        bar_width = 0.25
        x = np.arange(len(densities))

        fig, ax = plt.subplots(figsize=(10, 6))

        for i, sched in enumerate(schedulers):
            pdrs = []
            for d in densities:
                row = grouped[(grouped["Density"] == d) & (grouped["Scheduler"] == sched)]
                pdrs.append(row["PDR"].values[0] if not row.empty else 0)
            ax.bar(x + i * bar_width, pdrs, bar_width, label=scheduler_labels[sched], color=color_map[sched])

        ax.set_xlabel("Local Density (neighbors in range)")
        ax.set_ylabel("Delivery Ratio")
        
        # Add interval to title if provided
        if interval:
            ax.set_title(f"Delivery Ratio vs Local Density (Static Interval: {interval}s)")
        else:
            ax.set_title("Delivery Ratio vs Local Density")
            
        ax.set_xticks(x + bar_width/2)
        ax.set_xticklabels([str(int(d)) for d in densities])
        ax.legend()
        ax.grid(axis="y", linestyle="--", alpha=0.6)
        plt.tight_layout()
        
        # Include interval in filename if provided
        if interval:
            plt.savefig(os.path.join(plot_dir, f"delivery_ratio_interval{interval}.png"))
        else:
            plt.savefig(os.path.join(plot_dir, "delivery_ratio_block_by_density.png"))
        plt.close()
    
    # Plot collision rate
    if not collision_data:
        print("No collision rate data with density found.")
        return
    
    # Group by density and scheduler type for collision rate
    coll_df = pd.DataFrame(collision_data, columns=["Density", "CollisionRate", "Scheduler"])
    grouped_coll = coll_df.groupby(["Density", "Scheduler"]).mean().reset_index()
    
    densities = sorted(coll_df["Density"].unique())
    schedulers = ["static", "dynamic"]
    
    # Always use SBP and ACAB names
    scheduler_labels = {"static": "SBP", "dynamic": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic": "tab:green"}
    
    bar_width = 0.25
    x = np.arange(len(densities))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for i, sched in enumerate(schedulers):
        rates = []
        for d in densities:
            row = grouped_coll[(grouped_coll["Density"] == d) & (grouped_coll["Scheduler"] == sched)]
            rates.append(row["CollisionRate"].values[0] if not row.empty else 0)
        ax.bar(x + i * bar_width, rates, bar_width, label=scheduler_labels[sched], color=color_map[sched])
    
    ax.set_xlabel("Local Density (neighbors in range)")
    ax.set_ylabel("Collision Rate")
    
    if interval:
        ax.set_title(f"Collision Rate vs Local Density (Static Interval: {interval}s)")
    else:
        ax.set_title("Collision Rate vs Local Density")
        
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels([str(int(d)) for d in densities])
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"collision_rate_interval{interval}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "collision_rate_block_by_density.png"))
    plt.close()

def detect_data_type(results_dir):
    """Detect if the results directory contains regular density data"""
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    
    # Check for regular density data
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Density" in df.index and "Delivery Ratio" in df.index:
            return "density"
    
    # Default to density
    return "density"

def extract_interval_from_dirname(dirname):
    """Extract interval value from directory name if present"""
    match = re.search(r'interval(\d+)', dirname)
    if match:
        return int(match.group(1))
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=str, default=None, help="Directory with result CSVs")
    parser.add_argument("--plot-dir", type=str, default=None, help="Directory to save plots")
    parser.add_argument("--interval", type=float, default=None, help="Static interval value to display in plot")
    args = parser.parse_args()

    results_dir = args.results_dir or os.environ.get("RESULTS_DIR", "tune_results")
    plot_dir = args.plot_dir or os.environ.get("PLOT_DIR", "tune_plots")

    # Try to extract interval from directory name if not provided
    interval = args.interval
    if interval is None:
        interval = extract_interval_from_dirname(results_dir)

    print(f"Loading results from: {results_dir}")
    print(f"Saving plots to: {plot_dir}")
    if interval:
        print(f"Using static interval: {interval}s")

    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir, exist_ok=True)

    print("Plotting standard metrics...")
    plot_block_by_density(results_dir, plot_dir, interval=interval)
    
    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()