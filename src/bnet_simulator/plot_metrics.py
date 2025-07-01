import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re

def plot_block_by_density(results_dir, plot_dir, interval=None):
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

def plot_vessel_metrics(results_dir, plot_dir, interval=None):
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    vessel_files = []
    
    # Find all vessel scenario files
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Is Vessel Scenario" in df.index:
            vessel_files.append(f)
            
    if not vessel_files:
        print("No vessel scenario data found.")
        return
        
    # Process data for vessel delivery ratio
    vessel_data = []
    for f in vessel_files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
        
        # Extract vessel delivery ratio
        vessel_dr = 0
        if "Vessel Delivery Ratio" in df.index:
            vessel_dr = float(df.loc["Vessel Delivery Ratio", "Value"])
        
        # Extract buoy count (density)
        buoy_count = 0
        if "Density" in df.index:
            buoy_count = int(float(df.loc["Density", "Value"]))
        elif "Fixed Buoys" in df.index:
            # Subtract 1 for the vessel itself
            buoy_count = int(float(df.loc["Fixed Buoys", "Value"])) - 1
                
        vessel_data.append((sched_type, buoy_count, vessel_dr))
    
    # Group data by scheduler type and buoy count
    grouped_data = {}
    for sched_type, buoy_count, dr in vessel_data:
        if sched_type not in grouped_data:
            grouped_data[sched_type] = {}
        if buoy_count not in grouped_data[sched_type]:
            grouped_data[sched_type][buoy_count] = []
        grouped_data[sched_type][buoy_count].append(dr)
    
    # Plot vessel delivery ratio by buoy count
    schedulers = sorted(grouped_data.keys())
    buoy_counts = sorted(set(buoy_count for _, buoy_count, _ in vessel_data))
    
    fig, ax = plt.subplots(figsize=(12, 6))
    bar_width = 0.35
    x = np.arange(len(buoy_counts))
    
    # Always use SBP and ACAB names
    scheduler_labels = {"static": "SBP", "dynamic": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic": "tab:green"}
    
    for i, sched in enumerate(schedulers):
        drs = []
        for count in buoy_counts:
            if count in grouped_data[sched]:
                drs.append(np.mean(grouped_data[sched][count]))
            else:
                drs.append(0)
        
        offset = i * bar_width - bar_width/2 if len(schedulers) > 1 else 0
        ax.bar(x + offset, drs, bar_width, label=scheduler_labels[sched], color=color_map[sched])
    
    ax.set_xlabel("Number of Buoys")
    ax.set_ylabel("Vessel Delivery Ratio")
    
    # Add interval to title if provided
    if interval:
        ax.set_title(f"Vessel Delivery Ratio by Number of Buoys (Static Interval: {interval}s)")
    else:
        ax.set_title("Vessel Delivery Ratio by Number of Buoys")
        
    ax.set_xticks(x)
    ax.set_xticklabels(buoy_counts)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    # Include interval in filename if provided
    if interval:
        plt.savefig(os.path.join(plot_dir, f"vessel_delivery_ratio_interval{interval}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "vessel_delivery_ratio.png"))
    plt.close()

def detect_data_type(results_dir):
    """Detect if the results directory contains vessel or regular density data"""
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    
    # Check for vessel data
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Is Vessel Scenario" in df.index:
            return "vessel"
    
    # If no vessel data found, check for regular density data
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Density" in df.index and "Delivery Ratio" in df.index:
            return "density"
    
    # If still no match, try to infer from directory name
    if "vessel" in results_dir.lower():
        return "vessel"
    else:
        return "density"  # Default to density

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

    # Detect data type and plot only the relevant graph
    data_type = detect_data_type(results_dir)
    
    if data_type == "vessel":
        print("Detected vessel data - plotting vessel delivery ratio...")
        plot_vessel_metrics(results_dir, plot_dir, interval=interval)
    else:
        print("Detected density data - plotting standard delivery ratio...")
        plot_block_by_density(results_dir, plot_dir, interval=interval)
    
    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()