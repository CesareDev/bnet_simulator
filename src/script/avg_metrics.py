import os
import pandas as pd
import numpy as np
import glob
import matplotlib.pyplot as plt
import re
from collections import defaultdict

def average_metrics(input_dirs, output_dir):
    # Identify subdirectories in each input directory
    all_subdirs = set()
    for input_dir in input_dirs:
        subdirs = [d for d in os.listdir(input_dir) 
                   if os.path.isdir(os.path.join(input_dir, d))]
        all_subdirs.update(subdirs)
    
    # Process each subdirectory separately
    for subdir in all_subdirs:
        # Extract the interval part from the subdirectory name
        interval_part = re.search(r'(interval\d+.*)', subdir)
        if interval_part:
            interval_suffix = interval_part.group(1)
        else:
            interval_suffix = subdir
        
        # Create results and plots directories directly in output_dir
        results_dir = os.path.join(output_dir, f"results_{interval_suffix}")
        plots_dir = os.path.join(output_dir, f"plots_{interval_suffix}")
        
        os.makedirs(results_dir, exist_ok=True)
        os.makedirs(plots_dir, exist_ok=True)
        
        # Collect input paths
        subdir_input_paths = [os.path.join(input_dir, subdir) for input_dir in input_dirs 
                             if os.path.isdir(os.path.join(input_dir, subdir))]
        
        print(f"Processing {subdir}...")
        print(f"  Results will be saved to: {results_dir}")
        print(f"  Plots will be saved to: {plots_dir}")
        
        # Process density files (static_density*.csv, dynamic_density*.csv)
        process_density_files(subdir_input_paths, results_dir)
        
        # Extract interval from subdirectory name for plotting
        interval = extract_interval_from_dirname(subdir)
        
        # Generate plots in the plot directory
        plot_averaged_metrics(results_dir, plots_dir, interval)

def extract_interval_from_dirname(dirname):
    """
    Hard-coded interval mapping based on directory naming convention.
    interval1_ideal -> 1.0s
    interval2_5_ideal -> 0.25s  
    interval5_ideal -> 0.5s
    """
    # Hard-coded mappings
    if 'interval1' in dirname:
        return 1.0
    elif 'interval2_5' in dirname or 'interval2.5' in dirname:
        return 0.25
    elif 'interval5' in dirname:
        return 0.5
    
    # Fallback: try to parse from dirname if it doesn't match known patterns
    match = re.search(r'interval(\d+(?:_\d+)?)', dirname)
    if match:
        interval_str = match.group(1).replace('_', '.')
        try:
            return float(interval_str)
        except ValueError:
            return None
    
    return None

def process_density_files(input_dirs, output_dir):
    # Dictionary to store dataframes by file pattern
    all_data = {}
    
    # Collect all CSV files from input directories
    for input_dir in input_dirs:
        csv_files = glob.glob(os.path.join(input_dir, "*_density*.csv"))
        
        for csv_file in csv_files:
            # Extract base filename (e.g., "static_density10.csv")
            base_name = os.path.basename(csv_file)
            
            # Load the data
            df = pd.read_csv(csv_file, index_col=0)
            
            if base_name not in all_data:
                all_data[base_name] = []
            
            all_data[base_name].append(df)
    
    # Average the metrics for each file pattern
    for base_name, dataframes in all_data.items():
        # Extract metrics common to all dataframes
        common_metrics = set(dataframes[0].index)
        for df in dataframes[1:]:
            common_metrics &= set(df.index)
        
        # Create a new dataframe with averaged values
        avg_data = {}
        for metric in common_metrics:
            values = [df.loc[metric, "Value"] for df in dataframes]
            
            # Try to convert to numeric for averaging
            try:
                numeric_values = [float(v) for v in values]
                avg_value = sum(numeric_values) / len(numeric_values)
                std_dev = np.std(numeric_values)
                avg_data[metric] = {"Value": avg_value, "StdDev": std_dev}
            except (ValueError, TypeError):
                # For non-numeric values, use the most common one
                from collections import Counter
                most_common = Counter(values).most_common(1)[0][0]
                avg_data[metric] = {"Value": most_common, "StdDev": "N/A"}
        
        # Save averaged results
        avg_df = pd.DataFrame.from_dict(avg_data, orient="index")
        avg_df.to_csv(os.path.join(output_dir, base_name))

def plot_averaged_metrics(data_dir, plot_dir, interval=None):
    # Plot block by density with error bars
    plot_block_by_density_with_errors(data_dir, plot_dir, interval)
    
    # Plot unique nodes by density with error bars
    plot_unique_nodes_by_density_with_errors(data_dir, plot_dir, interval)

def get_density_dataframes(data_dir):
    files = glob.glob(os.path.join(data_dir, "*_density*.csv"))
    pdr_data = []
    collision_data = []
    unique_nodes_data = []
    
    # Extract data from CSV files
    for f in files:
        df = pd.read_csv(f, index_col=0)
        
        # Extract multihop mode
        multihop_mode = "none"
        if "Multihop Mode" in df.index:
            multihop_mode = str(df.loc["Multihop Mode", "Value"]).lower()
        
        # Determine scheduler type
        if "Scheduler Type" in df.index:
            sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
        elif os.path.basename(f).startswith("static_"):
            sched_type = "static"
        elif os.path.basename(f).startswith("dynamic_acab_"):
            sched_type = "dynamic_acab"
        elif os.path.basename(f).startswith("dynamic_adab_"):
            sched_type = "dynamic_adab"
        elif os.path.basename(f).startswith("dynamic_"):
            sched_type = "dynamic_adab"
        else:
            sched_type = "unknown"
        
        # Extract B-PDR data
        if "Density" in df.index and ("Delivery Ratio" in df.index or "B-PDR" in df.index):
            density = float(df.loc["Density", "Value"])
            pdr = float(df.loc["B-PDR", "Value"]) if "B-PDR" in df.index else float(df.loc["Delivery Ratio", "Value"])
            pdr_std = float(df.loc["B-PDR", "StdDev"]) if "B-PDR" in df.index else float(df.loc["Delivery Ratio", "StdDev"])
            
            avg_neighbors = None
            if "Average Neighbors" in df.index:
                avg_neighbors = float(df.loc["Average Neighbors", "Value"])
            elif "Avg Neighbors" in df.index:
                avg_neighbors = float(df.loc["Avg Neighbors", "Value"])
            
            pdr_data.append((density, pdr, pdr_std, sched_type, avg_neighbors, multihop_mode))
        
        # Extract collision rate data
        if "Density" in df.index and "Collision Rate" in df.index:
            density = float(df.loc["Density", "Value"])
            collision_rate = float(df.loc["Collision Rate", "Value"])
            collision_std = float(df.loc["Collision Rate", "StdDev"])
            
            avg_neighbors = None
            if "Average Neighbors" in df.index:
                avg_neighbors = float(df.loc["Average Neighbors", "Value"])
            elif "Avg Neighbors" in df.index:
                avg_neighbors = float(df.loc["Avg Neighbors", "Value"])
            
            collision_data.append((density, collision_rate, collision_std, sched_type, avg_neighbors, multihop_mode))
        
        # Extract unique nodes data
        if "Density" in df.index and "Avg Unique Nodes Discovered" in df.index:
            density = float(df.loc["Density", "Value"])
            avg_unique = float(df.loc["Avg Unique Nodes Discovered", "Value"])
            avg_unique_std = float(df.loc["Avg Unique Nodes Discovered", "StdDev"])
            
            unique_nodes_data.append((density, avg_unique, avg_unique_std, sched_type, multihop_mode))
    
    # Create dataframes
    pdr_df = pd.DataFrame(pdr_data, columns=["Density", "B-PDR", "StdDev", "Scheduler", "AvgNeighbors", "MultihopMode"])
    coll_df = pd.DataFrame(collision_data, columns=["Density", "CollisionRate", "StdDev", "Scheduler", "AvgNeighbors", "MultihopMode"])
    unique_df = pd.DataFrame(unique_nodes_data, columns=["Density", "AvgUniqueNodes", "StdDev", "Scheduler", "MultihopMode"])
    
    return pdr_df, coll_df, unique_df

def plot_block_by_density_with_errors(data_dir, plot_dir, interval=None):
    try:
        pdr_df, coll_df, _ = get_density_dataframes(data_dir)
    except Exception as e:
        print(f"Error getting density data: {e}")
        return
    
    if pdr_df.empty:
        print("No B-PDR data with density found.")
        return
    
    # Get multihop mode for title
    multihop_modes = set(pdr_df["MultihopMode"].unique())
    mode_str = ""
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
    elif len(multihop_modes) > 1:
        mode_str = "Mixed Modes"
    
    # Create B-PDR by density plot with error bars
    densities = sorted(pdr_df["Density"].unique())
    schedulers = ["dynamic_acab", "dynamic_adab", "static"]
    scheduler_labels = {"static": "SBP", "dynamic_adab": "ADAB", "dynamic_acab": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic_adab": "tab:orange", "dynamic_acab": "tab:green"}
    bar_width = 0.25
    x = np.arange(len(densities))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Add second y-axis for average neighbors
    ax2 = ax.twinx()
    ax2.set_ylabel("Average Neighbors", color="black")
    ax2.tick_params(axis='y', labelcolor="black")
    ax2.grid(False)
    
    offset = -(len(schedulers) - 1) * bar_width / 2
    for i, sched in enumerate(schedulers):
        values = []
        errors = []
        for d in densities:
            rows = pdr_df[(pdr_df["Density"] == d) & (pdr_df["Scheduler"] == sched)]
            if not rows.empty:
                values.append(rows["B-PDR"].mean())
                errors.append(rows["StdDev"].mean())
            else:
                values.append(0)
                errors.append(0)
        
        values_arr = np.array(values)
        errors_arr = np.array(errors)
        lower_errors = np.minimum(errors_arr, values_arr)
        upper_errors = errors_arr
        
        ax.bar(x + offset + i * bar_width, values_arr, bar_width, 
               label=scheduler_labels[sched], color=color_map[sched])
        ax.errorbar(x + offset + i * bar_width, values_arr, 
                   yerr=[lower_errors, upper_errors], fmt='none', 
                   ecolor='black', capsize=5, alpha=0.7)
    
    # Plot average neighbors
    avg_neighbors_data = {}
    for d in densities:
        rows = pdr_df[pdr_df["Density"] == d]
        if not rows.empty and not rows["AvgNeighbors"].isna().all():
            avg_neighbors_data[d] = rows["AvgNeighbors"].mean()
    
    if avg_neighbors_data:
        density_points = []
        neighbor_values = []
        
        for d in densities:
            if d in avg_neighbors_data:
                density_points.append(d)
                neighbor_values.append(avg_neighbors_data[d])
        
        if density_points:
            x_positions = [list(densities).index(d) for d in density_points]
            
            ax2.plot(x_positions, neighbor_values, color='black', marker='o', 
                   linestyle='-', linewidth=1, label='Avg Neighbors')
            
            for i, (x_pos, value) in enumerate(zip(x_positions, neighbor_values)):
                ax2.text(x_pos, value, f"{value:.1f}", color='black', 
                       ha='center', va='bottom', fontsize=8)
            
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
    
    if coll_df.empty:
        print("No collision rate data with density found.")
        return
    
    # Create collision rate by density plot with error bars
    fig, ax = plt.subplots(figsize=(10, 6))
    
    offset = -(len(schedulers) - 1) * bar_width / 2
    for i, sched in enumerate(schedulers):
        values = []
        errors = []
        for d in densities:
            rows = coll_df[(coll_df["Density"] == d) & (coll_df["Scheduler"] == sched)]
            if not rows.empty:
                values.append(rows["CollisionRate"].mean())
                errors.append(rows["StdDev"].mean())
            else:
                values.append(0)
                errors.append(0)
        
        values_arr = np.array(values)
        errors_arr = np.array(errors)
        lower_errors = np.minimum(errors_arr, values_arr)
        upper_errors = errors_arr
        
        ax.bar(x + offset + i * bar_width, values_arr, bar_width, 
               label=scheduler_labels[sched], color=color_map[sched])
        ax.errorbar(x + offset + i * bar_width, values_arr, 
                   yerr=[lower_errors, upper_errors], fmt='none', 
                   ecolor='black', capsize=5, alpha=0.7)
    
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
    ax.legend(loc='upper left')
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"collision_rate_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "collision_rate_block_by_density.png"))
    plt.close()

def plot_unique_nodes_by_density_with_errors(data_dir, plot_dir, interval=None):
    """Plot average unique nodes discovered (as percentage) vs density with error bars"""
    try:
        _, _, unique_df = get_density_dataframes(data_dir)
    except Exception as e:
        print(f"Error getting unique nodes data: {e}")
        return
    
    if unique_df.empty:
        print("No unique nodes data with density found.")
        return
    
    # Calculate percentage
    unique_df["PercentageDiscovered"] = (unique_df["AvgUniqueNodes"] / (unique_df["Density"] - 1)) * 100
    unique_df["PercentageStdDev"] = (unique_df["StdDev"] / (unique_df["Density"] - 1)) * 100
    
    # Get multihop mode for title
    multihop_modes = set(unique_df["MultihopMode"].unique())
    mode_str = ""
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
    elif len(multihop_modes) > 1:
        mode_str = "Mixed Modes"
    
    densities = sorted(unique_df["Density"].unique())
    schedulers = ["dynamic_acab", "dynamic_adab", "static"]
    scheduler_labels = {"static": "SBP", "dynamic_adab": "ADAB", "dynamic_acab": "ACAB"}
    color_map = {"static": "tab:blue", "dynamic_adab": "tab:orange", "dynamic_acab": "tab:green"}
    bar_width = 0.25
    x = np.arange(len(densities))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    offset = -(len(schedulers) - 1) * bar_width / 2
    for i, sched in enumerate(schedulers):
        values = []
        errors = []
        for d in densities:
            rows = unique_df[(unique_df["Density"] == d) & (unique_df["Scheduler"] == sched)]
            if not rows.empty:
                values.append(rows["PercentageDiscovered"].mean())
                errors.append(rows["PercentageStdDev"].mean())
            else:
                values.append(0)
                errors.append(0)
        
        values_arr = np.array(values)
        errors_arr = np.array(errors)
        lower_errors = np.minimum(errors_arr, values_arr)
        upper_errors = np.minimum(errors_arr, 100 - values_arr)
        
        ax.bar(x + offset + i * bar_width, values_arr, bar_width, 
               label=scheduler_labels[sched], color=color_map[sched])
        ax.errorbar(x + offset + i * bar_width, values_arr, 
                   yerr=[lower_errors, upper_errors], fmt='none', 
                   ecolor='black', capsize=5, alpha=0.7)
    
    ax.set_xlabel("Total Buoys")
    ax.set_ylabel("Avg % of Network Discovered")
    ax.set_ylim(0, 100)
    
    # Update title to include mode
    title_parts = ["Avg % of Network Discovered vs Buoy Count"]
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
    ax.legend(loc='upper left')
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"avg_percentage_network_discovered_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "avg_percentage_network_discovered_by_density.png"))
    plt.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Average metrics across multiple simulation runs")
    parser.add_argument("--input-dirs", nargs="+", required=True, help="Input metrics directories")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Input directories: {args.input_dirs}")
    print(f"Output directory: {args.output_dir}")
    
    average_metrics(args.input_dirs, args.output_dir)
    print(f"Metrics averaging complete.")

if __name__ == "__main__":
    main()