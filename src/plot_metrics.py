import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re

def plot_block_by_density(results_dir, plot_dir, interval=None):
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    data = []
    collision_data = []
    
    # Extract data from CSV files
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Density" in df.index and ("Delivery Ratio" in df.index or "B-PDR" in df.index):
            density = float(df.loc["Density", "Value"])
            pdr = float(df.loc["B-PDR", "Value"]) if "B-PDR" in df.index else float(df.loc["Delivery Ratio", "Value"])
            
            # Determine scheduler type
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic"
            else:
                sched_type = "unknown"
                
            data.append((density, pdr, sched_type))
            
        if "Density" in df.index and "Collision Rate" in df.index:
            density = float(df.loc["Density", "Value"])
            collision_rate = float(df.loc["Collision Rate", "Value"])
            
            # Determine scheduler type
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic"
            else:
                sched_type = "unknown"
                
            collision_data.append((density, collision_rate, sched_type))
    
    # Handle no data case
    if not data:
        print("No B-PDR data with density found.")
        return
    
    # Create B-PDR by density plot
    df = pd.DataFrame(data, columns=["Density", "B-PDR", "Scheduler"])
    grouped = df.groupby(["Density", "Scheduler"]).mean().reset_index()
    densities = sorted(df["Density"].unique())
    schedulers = ["static", "dynamic"]
    scheduler_labels = {"static": "SBP", "dynamic": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic": "tab:green"}
    bar_width = 0.25
    x = np.arange(len(densities))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, sched in enumerate(schedulers):
        pdrs = []
        for d in densities:
            row = grouped[(grouped["Density"] == d) & (grouped["Scheduler"] == sched)]
            pdrs.append(row["B-PDR"].values[0] if not row.empty else 0)
        ax.bar(x + i * bar_width, pdrs, bar_width, label=scheduler_labels[sched], color=color_map[sched])
    
    ax.set_xlabel("Local Density (neighbors in range)")
    ax.set_ylabel("B-PDR")
    if interval:
        ax.set_title(f"B-PDR vs Local Density (Static Interval: {interval}s)")
    else:
        ax.set_title("B-PDR vs Local Density")
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels([str(int(d)) for d in densities])
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"b_pdr_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "b_pdr_block_by_density.png"))
    plt.close()
    
    # Skip collision rate plot if no data
    if not collision_data:
        print("No collision rate data with density found.")
        return
    
    # Create collision rate by density plot
    coll_df = pd.DataFrame(collision_data, columns=["Density", "CollisionRate", "Scheduler"])
    grouped_coll = coll_df.groupby(["Density", "Scheduler"]).mean().reset_index()
    densities = sorted(coll_df["Density"].unique())
    
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
        plt.savefig(os.path.join(plot_dir, f"collision_rate_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "collision_rate_block_by_density.png"))
    plt.close()
    
    # Create grouped plots if we have enough density values
    if len(densities) > 5:
        plot_grouped_by_density(df, coll_df, plot_dir, interval)

def plot_grouped_by_density(pdr_df, coll_df, plot_dir, interval=None):
    def get_density_group(density):
        return f"{5*((int(density)-1)//5) + 1}-{5*((int(density)-1)//5) + 5}"
    
    pdr_df['DensityGroup'] = pdr_df['Density'].apply(get_density_group)
    coll_df['DensityGroup'] = coll_df['Density'].apply(get_density_group)
    
    grouped_pdr = pdr_df.groupby(['DensityGroup', 'Scheduler']).mean().reset_index()
    grouped_coll = coll_df.groupby(['DensityGroup', 'Scheduler']).mean().reset_index()
    
    def sort_key(group):
        return int(group.split('-')[0])
    
    density_groups = sorted(grouped_pdr['DensityGroup'].unique(), key=sort_key)
    schedulers = ["static", "dynamic"]
    scheduler_labels = {"static": "SBP", "dynamic": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic": "tab:green"}
    bar_width = 0.35
    x = np.arange(len(density_groups))
    
    # Create B-PDR by density group plot
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, sched in enumerate(schedulers):
        pdrs = []
        for grp in density_groups:
            row = grouped_pdr[(grouped_pdr["DensityGroup"] == grp) & (grouped_pdr["Scheduler"] == sched)]
            pdrs.append(row["B-PDR"].values[0] if not row.empty else 0)
        ax.bar(x + i * bar_width, pdrs, bar_width, label=scheduler_labels[sched], color=color_map[sched])
    
    ax.set_xlabel("Local Density Groups (neighbors in range)")
    ax.set_ylabel("Average B-PDR")
    if interval:
        ax.set_title(f"B-PDR vs Density Groups (Static Interval: {interval}s)")
    else:
        ax.set_title("B-PDR vs Density Groups")
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels(density_groups)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"b_pdr_grouped_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "b_pdr_grouped.png"))
    plt.close()
    
    # Create collision rate by density group plot
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, sched in enumerate(schedulers):
        rates = []
        for grp in density_groups:
            row = grouped_coll[(grouped_coll["DensityGroup"] == grp) & (grouped_coll["Scheduler"] == sched)]
            rates.append(row["CollisionRate"].values[0] if not row.empty else 0)
        ax.bar(x + i * bar_width, rates, bar_width, label=scheduler_labels[sched], color=color_map[sched])
    
    ax.set_xlabel("Local Density Groups (neighbors in range)")
    ax.set_ylabel("Average Collision Rate")
    if interval:
        ax.set_title(f"Collision Rate vs Density Groups (Static Interval: {interval}s)")
    else:
        ax.set_title("Collision Rate vs Density Groups")
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels(density_groups)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"collision_rate_grouped_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "collision_rate_grouped.png"))
    plt.close()

def plot_ramp_grouped_by_buoy_count(results_dir, plot_file):
    modes = [("static", "tab:blue"), ("dynamic", "tab:green")]
    
    # First, collect data and determine overall min/max buoy counts
    min_buoys = float('inf')
    max_buoys = 0
    all_data = {}
    
    for mode, _ in modes:
        csv_file = os.path.join(results_dir, f"{mode}_ramp_timeseries.csv")
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            if "n_buoys" in df.columns:
                min_buoys = min(min_buoys, df["n_buoys"].min())
                max_buoys = max(max_buoys, df["n_buoys"].max())
                all_data[mode] = df
    
    # If no data found, exit early
    if not all_data:
        print("No valid data files found for buoy count grouping")
        return
    
    # Determine appropriate number of groups based on data range
    # Use 5-10 groups depending on range
    buoy_range = max_buoys - min_buoys
    if buoy_range <= 10:
        num_groups = max(5, buoy_range)
    else:
        num_groups = min(10, max(5, buoy_range // 5))
    
    # Create group edges with consistent bin sizes
    # Add 1 to max_buoys to ensure it's included in the last bin
    group_edges = np.linspace(min_buoys, max_buoys + 1, num_groups + 1).astype(int)
    
    # Ensure the first bin starts from the actual minimum
    group_edges[0] = int(min_buoys)
    
    # Create readable group labels
    group_labels = [f"{group_edges[i]}-{group_edges[i+1]-1}" for i in range(len(group_edges)-1)]
    
    # Process data for each mode
    grouped_data = {}
    valid_modes = []
    
    for mode, color in modes:
        if mode in all_data:
            df = all_data[mode]
            
            if "B-PDR" in df.columns:
                y_col = "B-PDR"
            elif "delivery_ratio" in df.columns:
                y_col = "delivery_ratio"
            else:
                print(f"Warning: No B-PDR or delivery_ratio column in data for {mode}")
                continue
            
            # Group by buoy count
            df["group"] = pd.cut(df["n_buoys"], bins=group_edges, labels=group_labels, right=False)
            grouped = df.groupby("group", observed=False)[y_col].mean().reindex(group_labels)
            
            # Only include modes with non-empty data
            if not grouped.empty and len(grouped.values) > 0:
                grouped_data[mode] = grouped.values
                valid_modes.append((mode, color))
            else:
                print(f"Warning: No valid grouped data for {mode}")
    
    # If no valid data found, exit early
    if not valid_modes:
        print("No valid data to plot for any mode")
        return
    
    # Plot the results
    x = np.arange(len(group_labels))
    bar_width = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for i, (mode, color) in enumerate(valid_modes):
        # Ensure data length matches x length
        data = grouped_data[mode]
        if len(data) == len(x):
            ax.bar(x + i * bar_width, data, bar_width, 
                  label=mode.capitalize(), color=color)
        else:
            print(f"Warning: Data length mismatch for {mode}. Expected {len(x)}, got {len(data)}")
    
    ax.set_xlabel("Buoy Count Group")
    ax.set_ylabel("Average B-PDR")
    ax.set_title("Average B-PDR vs Buoy Count Group (Ramp Scenario)")
    ax.set_xticks(x + (bar_width / 2 if len(valid_modes) > 1 else 0))
    ax.set_xticklabels(group_labels)
    ax.legend(loc="lower right")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(plot_file)
    plt.close()

def extract_interval_from_dirname(dirname):
    match = re.search(r'interval(\d+)', dirname)
    if match:
        interval_value = int(match.group(1))
        if interval_value < 10:
            return interval_value / 10.0
        return interval_value
    return None

def plot_delivery_ratio_vs_time(results_dir, plot_file, interval=None):
    modes = [("static", "tab:blue"), ("dynamic", "tab:green")]
    plt.figure(figsize=(10, 6))
    found = False

    time_buoy = None
    max_buoys = 0

    for mode, color in modes:
        csv_file = os.path.join(results_dir, f"{mode}_ramp_timeseries.csv")
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            if "B-PDR" in df.columns:
                y_col = "B-PDR"
            elif "delivery_ratio" in df.columns:
                y_col = "delivery_ratio"
            else:
                print(f"Warning: No B-PDR or delivery_ratio column in {csv_file}")
                continue
            plt.plot(df["time"], df[y_col], label=mode.capitalize(), color=color)
            found = True
            if time_buoy is None and "n_buoys" in df.columns:
                time_buoy = (df["time"], df["n_buoys"])
                max_buoys = df["n_buoys"].max()

    if not found:
        print("No ramp timeseries files found for plotting.")
        return

    ax = plt.gca()
    handles, labels = ax.get_legend_handles_labels()

    if time_buoy is not None:
        ax2 = ax.twinx()
        gray_area = ax2.fill_between(time_buoy[0], time_buoy[1], color="gray", alpha=0.2, label="Buoy Count")
        ax2.set_ylabel("Buoy Count", fontsize=12)
        ax2.set_ylim(0, max(40, int(max_buoys)))
        ax2.tick_params(axis='y', colors='gray')
        ax2.grid(False)
        handles2, labels2 = ax2.get_legend_handles_labels()
        handles += [gray_area]
        labels += ["Buoy Count"]

    ax.set_xlabel("Time (s)", fontsize=12)
    ax.set_ylabel("B-PDR", fontsize=12)
    if interval:
        plt.title(f"B-PDR vs Time (Ramp Scenario, Static Interval: {interval}s)")
    else:
        plt.title("B-PDR vs Time (Ramp Scenario)")

    ax.legend(handles, labels, loc="lower right", fontsize=11)
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(plot_file)
    plt.close()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=str, default=None, help="Directory with result CSVs")
    parser.add_argument("--plot-dir", type=str, default=None, help="Directory to save plots")
    parser.add_argument("--interval", type=float, default=None, help="Static interval value to display in plot")
    args = parser.parse_args()

    results_dir = args.results_dir or os.environ.get("RESULTS_DIR", "test_results")
    plot_dir = args.plot_dir or os.environ.get("PLOT_DIR", "test_plots")

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

    print("Plotting B-PDR vs time for ramp scenarios...")
    plot_file = os.path.join(plot_dir, "b_pdr_vs_time_ramp.png")
    plot_delivery_ratio_vs_time(results_dir, plot_file, interval=interval)

    print("Plotting B-PDR grouped by buoy count for ramp scenario...")
    plot_group_file = os.path.join(plot_dir, "b_pdr_grouped_by_buoy_count_ramp.png")
    plot_ramp_grouped_by_buoy_count(results_dir, plot_group_file)

    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()