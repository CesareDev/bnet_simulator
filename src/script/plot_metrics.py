import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re

def plot_block_by_density(results_dir, plot_dir, interval=None):
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    data = []
    collision_data = []
    avg_neighbors_data = {}
    multihop_modes = set()  # Track multihop modes
    
    # Extract data from CSV files
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Density" in df.index and ("Delivery Ratio" in df.index or "B-PDR" in df.index):
            density = float(df.loc["Density", "Value"])
            pdr = float(df.loc["B-PDR", "Value"]) if "B-PDR" in df.index else float(df.loc["Delivery Ratio", "Value"])
            
            if "Average Neighbors" in df.index:
                avg_neighbors = float(df.loc["Average Neighbors", "Value"])
                avg_neighbors_data[density] = avg_neighbors
            
            # Extract multihop mode
            if "Multihop Mode" in df.index:
                mode = str(df.loc["Multihop Mode", "Value"]).lower()
                multihop_modes.add(mode)
            
            # Determine scheduler type
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_acab_"):
                sched_type = "dynamic_acab"
            elif f.startswith("dynamic_adab_"):
                sched_type = "dynamic_adab"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic_adab"
            else:
                sched_type = "unknown"
                
            data.append((density, pdr, sched_type))
            
        if "Density" in df.index and "Collision Rate" in df.index:
            density = float(df.loc["Density", "Value"])
            collision_rate = float(df.loc["Collision Rate", "Value"])
            
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_acab_"):
                sched_type = "dynamic_acab"
            elif f.startswith("dynamic_adab_"):
                sched_type = "dynamic_adab"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic_adab"
            else:
                sched_type = "unknown"
                
            collision_data.append((density, collision_rate, sched_type))
    
    if not data:
        print("No B-PDR data with density found.")
        return
    
    # Determine mode string for title
    mode_str = ""
    if multihop_modes:
        if len(multihop_modes) == 1:
            mode = list(multihop_modes)[0]
            if mode == "none":
                mode_str = "Single-Hop"
            elif mode == "append":
                mode_str = "Append Mode"
            elif mode == "forwarded":
                mode_str = "Forward Mode"
            else:
                mode_str = mode.capitalize()
        else:
            mode_str = "Mixed Modes"
    
    # Create B-PDR by density plot
    df = pd.DataFrame(data, columns=["Density", "B-PDR", "Scheduler"])
    grouped = df.groupby(["Density", "Scheduler"]).mean().reset_index()
    densities = sorted(df["Density"].unique())
    schedulers = ["dynamic_acab", "dynamic_adab", "static"]
    scheduler_labels = {"static": "SBP", "dynamic_adab": "ADAB", "dynamic_acab": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic_adab": "tab:orange", "dynamic_acab": "tab:green"}
    bar_width = 0.25
    x = np.arange(len(densities))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax2 = ax.twinx()
    ax2.set_ylabel("Average Neighbors", color="black")
    ax2.tick_params(axis='y', labelcolor="black")
    ax2.grid(False)
    
    offset = -(len(schedulers) - 1) * bar_width / 2
    for i, sched in enumerate(schedulers):
        pdrs = []
        for d in densities:
            row = grouped[(grouped["Density"] == d) & (grouped["Scheduler"] == sched)]
            pdrs.append(row["B-PDR"].values[0] if not row.empty else 0)
        ax.bar(x + offset + i * bar_width, pdrs, bar_width, label=scheduler_labels[sched], color=color_map[sched])
    
    # Plot average neighbors as a connected line across all densities
    if avg_neighbors_data:
        # Prepare data points for the line
        density_points = []
        neighbor_values = []
        
        # Collect data points in order of density
        for d in densities:
            if d in avg_neighbors_data:
                density_points.append(d)
                neighbor_values.append(avg_neighbors_data[d])
        
        # Only proceed if we have points to plot
        if density_points:
            # Convert density values to x-positions for plotting
            x_positions = [list(densities).index(d) for d in density_points]
            
            # Plot the connected line
            ax2.plot(x_positions, neighbor_values, color='black', marker='o', 
                   linestyle='-', linewidth=1, label='Avg Neighbors')
            
            # Add text labels at each point
            for i, (x_pos, value) in enumerate(zip(x_positions, neighbor_values)):
                ax2.text(x_pos, value, f"{value:.1f}", color='black', 
                       ha='center', va='bottom', fontsize=8)
            
            # Set y-limits for average neighbors axis
            max_avg_neighbors = max(neighbor_values)
            ax2.set_ylim(0, max_avg_neighbors * 1.2)
    
    ax.set_xlabel("Total Buoys")
    ax.set_ylabel("B-PDR")
    
    # Update title to include mode
    title_parts = ["B-PDR vs Buoy Count"]
    if mode_str:
        title_parts.append(f"({mode_str}")
        if interval:
            title_parts.append(f", Static Interval: {interval}s)")
        else:
            title_parts.append(")")
    elif interval:
        title_parts.append(f"(Static Interval: {interval}s)")
    ax.set_title(" ".join(title_parts))
    
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(d)) for d in densities])
    
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='lower right')
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"b_pdr_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "b_pdr_block_by_density.png"))
    plt.close()
    
    if not collision_data:
        print("No collision rate data with density found.")
        return
    
    # Create collision rate by density plot
    coll_df = pd.DataFrame(collision_data, columns=["Density", "CollisionRate", "Scheduler"])
    grouped_coll = coll_df.groupby(["Density", "Scheduler"]).mean().reset_index()
    densities = sorted(coll_df["Density"].unique())
    
    fig, ax = plt.subplots(figsize=(10, 6))
    offset = -(len(schedulers) - 1) * bar_width / 2
    for i, sched in enumerate(schedulers):
        rates = []
        for d in densities:
            row = grouped_coll[(grouped_coll["Density"] == d) & (grouped_coll["Scheduler"] == sched)]
            rates.append(row["CollisionRate"].values[0] if not row.empty else 0)
        ax.bar(x + offset + i * bar_width, rates, bar_width, label=scheduler_labels[sched], color=color_map[sched])
    
    ax.set_xlabel("Total Buoys")
    ax.set_ylabel("Collision Rate")
    
    # Update title to include mode
    title_parts = ["Collision Rate vs Buoy Count"]
    if mode_str:
        title_parts.append(f"({mode_str}")
        if interval:
            title_parts.append(f", Static Interval: {interval}s)")
        else:
            title_parts.append(")")
    elif interval:
        title_parts.append(f"(Static Interval: {interval}s)")
    ax.set_title(" ".join(title_parts))
    
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(d)) for d in densities])
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"collision_rate_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "collision_rate_block_by_density.png"))
    plt.close()

def extract_interval_from_dirname(dirname):
    match = re.search(r'interval(\d+(?:_\d+)?)', dirname)
    if match:
        interval_str = match.group(1).replace('_', '.')
        try:
            if int(interval_str) < 10:
                return float(interval_str) / 10.0
            else:
                return float(interval_str)
        except ValueError:
            interval_value = int(match.group(1))
            if interval_value < 10:
                return interval_value / 10.0
            return interval_value
    return None

def plot_unique_nodes_by_density(results_dir, plot_dir, interval=None):
    """Plot average unique nodes discovered vs density for different schedulers"""
    files = [f for f in os.listdir(results_dir) if f.endswith(".csv")]
    data = []
    
    for f in files:
        df = pd.read_csv(os.path.join(results_dir, f), index_col=0)
        if "Density" in df.index and "Avg Unique Nodes Discovered" in df.index:
            density = float(df.loc["Density", "Value"])
            avg_unique = float(df.loc["Avg Unique Nodes Discovered", "Value"])
            
            avg_neighbors = float(df.loc["Average Neighbors", "Value"]) if "Average Neighbors" in df.index else 0
            
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif f.startswith("static_"):
                sched_type = "static"
            elif f.startswith("dynamic_acab_"):
                sched_type = "dynamic_acab"
            elif f.startswith("dynamic_adab_"):
                sched_type = "dynamic_adab"
            elif f.startswith("dynamic_"):
                sched_type = "dynamic_adab"
            else:
                sched_type = "unknown"
            
            multihop_mode = "none"
            if "Multihop Mode" in df.index:
                multihop_mode = str(df.loc["Multihop Mode", "Value"]).lower()
                
            data.append((density, avg_unique, avg_neighbors, sched_type, multihop_mode))
    
    if not data:
        print("No unique nodes data with density found.")
        return
    
    df = pd.DataFrame(data, columns=["Density", "AvgUniqueNodes", "AvgNeighbors", "Scheduler", "MultihopMode"])
    
    # Calculate percentage - (avg_unique / (density - 1)) * 100
    # density - 1 because we exclude self from potential discoveries
    df["PercentageDiscovered"] = (df["AvgUniqueNodes"] / (df["Density"] - 1)) * 100
    
    grouped = df.groupby(["Density", "Scheduler", "MultihopMode"]).mean().reset_index()
    
    densities = sorted(df["Density"].unique())
    schedulers = ["dynamic_acab", "dynamic_adab", "static"]
    scheduler_labels = {"static": "SBP", "dynamic_adab": "ADAB", "dynamic_acab": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic_adab": "tab:orange", "dynamic_acab": "tab:green"}
    
    multihop_modes = sorted(df["MultihopMode"].unique())
    
    if len(multihop_modes) > 1:
        fig, axes = plt.subplots(1, len(multihop_modes), figsize=(8 * len(multihop_modes), 6))
        if len(multihop_modes) == 1:
            axes = [axes]
        
        for ax, mode in zip(axes, multihop_modes):
            mode_data = grouped[grouped["MultihopMode"] == mode]
            bar_width = 0.25
            x = np.arange(len(densities))
            
            offset = -(len(schedulers) - 1) * bar_width / 2
            for i, sched in enumerate(schedulers):
                values = []
                for d in densities:
                    row = mode_data[(mode_data["Density"] == d) & (mode_data["Scheduler"] == sched)]
                    values.append(row["PercentageDiscovered"].values[0] if not row.empty else 0)  # UPDATED
                ax.bar(x + offset + i * bar_width, values, bar_width, 
                      label=scheduler_labels[sched], color=color_map[sched])
            
            ax.set_xlabel("Total Buoys")
            ax.set_ylabel("Avg % of Network Discovered")  # UPDATED
            ax.set_ylim(0, 100)  # Set y-axis from 0 to 100%
            mode_title = mode.capitalize() if mode != "none" else "Single-Hop"
            ax.set_title(f"{mode_title} Mode")
            ax.set_xticks(x)
            ax.set_xticklabels([str(int(d)) for d in densities])
            ax.legend(loc='upper left')
            ax.grid(axis="y", linestyle="--", alpha=0.6)
        
        if interval:
            fig.suptitle(f"Avg % of Network Discovered vs Buoy Count (Static Interval: {interval}s)")  # UPDATED
        else:
            fig.suptitle("Avg % of Network Discovered vs Buoy Count")  # UPDATED
        plt.tight_layout()
        
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        bar_width = 0.25
        x = np.arange(len(densities))
        
        offset = -(len(schedulers) - 1) * bar_width / 2
        for i, sched in enumerate(schedulers):
            values = []
            for d in densities:
                row = grouped[(grouped["Density"] == d) & (grouped["Scheduler"] == sched)]
                values.append(row["PercentageDiscovered"].values[0] if not row.empty else 0)  # UPDATED
            ax.bar(x + offset + i * bar_width, values, bar_width, 
                  label=scheduler_labels[sched], color=color_map[sched])
        
        ax.set_xlabel("Total Buoys")
        ax.set_ylabel("Avg % of Network Discovered")  # UPDATED
        ax.set_ylim(0, 100)  # Set y-axis from 0 to 100%
        mode = multihop_modes[0]
        mode_title = mode.capitalize() if mode != "none" else "Single-Hop"
        
        title_parts = ["Avg % of Network Discovered vs Buoy Count"]  # UPDATED
        title_parts.append(f"({mode_title} Mode")
        if interval:
            title_parts.append(f", Static Interval: {interval}s)")
        else:
            title_parts.append(")")
        ax.set_title(" ".join(title_parts))
        
        ax.set_xticks(x)
        ax.set_xticklabels([str(int(d)) for d in densities])
        ax.legend(loc='upper left')
        ax.grid(axis="y", linestyle="--", alpha=0.6)
        plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"avg_percentage_network_discovered_interval{int(interval*10)}.png"))  # UPDATED
    else:
        plt.savefig(os.path.join(plot_dir, "avg_percentage_network_discovered_by_density.png"))  # UPDATED
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
    else:
        interval = float(interval)
        
    print(f"Loading results from: {results_dir}")
    print(f"Saving plots to: {plot_dir}")
    if interval:
        print(f"Using static interval: {interval}s")

    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir, exist_ok=True)

    print("Plotting standard metrics...")
    plot_block_by_density(results_dir, plot_dir, interval=interval)

    print("Plotting unique nodes by density...")
    plot_unique_nodes_by_density(results_dir, plot_dir, interval=interval)

    print("Plots saved to:", plot_dir)

if __name__ == "__main__":
    main()