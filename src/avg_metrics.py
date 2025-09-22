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
        
        # Process ramp timeseries files
        process_timeseries_files(subdir_input_paths, results_dir)
        
        # Extract interval from subdirectory name for plotting
        interval = extract_interval_from_dirname(subdir)
        
        # Generate plots in the plot directory
        plot_averaged_metrics(results_dir, plots_dir, interval)

def extract_interval_from_dirname(dirname):
    match = re.search(r'interval(\d+(?:_\d+)?)', dirname)
    if match:
        interval_str = match.group(1).replace('_', '.')  # "2_5" → "2.5"
        try:
            value = float(interval_str)
            # If it's a single-digit or decimal like 2.5, interpret as fraction of 10
            if value < 10:
                return value / 10.0
            return value
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

def process_timeseries_files(input_dirs, output_dir):
    # Dictionary to store timeseries data by mode
    timeseries_data = {"static": [], "dynamic": []}
    
    # Collect all timeseries CSV files
    for input_dir in input_dirs:
        for mode in ["static", "dynamic"]:
            ts_file = os.path.join(input_dir, f"{mode}_ramp_timeseries.csv")
            if os.path.exists(ts_file):
                df = pd.read_csv(ts_file)
                timeseries_data[mode].append(df)
    
    # Process each mode
    for mode, dataframes in timeseries_data.items():
        if not dataframes:
            continue
        
        # For timeseries, we need to align by time points
        # Get the set of time points from all dataframes
        all_times = sorted(set().union(*[set(df["time"]) for df in dataframes]))
        
        # Create a new dataframe with aligned time points
        avg_df = pd.DataFrame({"time": all_times})
        
        # Identify common columns across all dataframes
        common_cols = set(dataframes[0].columns)
        for df in dataframes[1:]:
            common_cols &= set(df.columns)
        
        # Remove 'time' from common columns
        if 'time' in common_cols:
            common_cols.remove('time')
        
        # For each dataframe, interpolate to match the aligned time points
        aligned_data = defaultdict(list)
        
        for df in dataframes:
            # Interpolate each column
            for col in common_cols:
                # Use nearest interpolation for categories or values that shouldn't be interpolated
                if col in ['n_buoys']:
                    interp_values = np.interp(all_times, df["time"], df[col], 
                                             left=df[col].iloc[0], right=df[col].iloc[-1])
                    interp_values = np.round(interp_values).astype(int)  # Round to nearest integer
                else:
                    interp_values = np.interp(all_times, df["time"], df[col], 
                                             left=np.nan, right=np.nan)
                
                aligned_data[col].append(interp_values)
        
        # Average across the interpolated dataframes
        for col in common_cols:
            values_array = np.array(aligned_data[col])
            avg_df[col] = np.nanmean(values_array, axis=0)
            avg_df[f"{col}_std"] = np.nanstd(values_array, axis=0)
        
        # Save the averaged timeseries
        avg_df.to_csv(os.path.join(output_dir, f"{mode}_ramp_timeseries.csv"), index=False)

def plot_averaged_metrics(data_dir, plot_dir, interval=None):
    # Plot block by density with error bars
    plot_block_by_density_with_errors(data_dir, plot_dir, interval)
    
    # Plot grouped density data if there are enough density points
    try:
        pdr_df, coll_df = get_density_dataframes(data_dir)
        if len(pdr_df["Density"].unique()) > 5:
            plot_grouped_by_density_with_errors(pdr_df, coll_df, plot_dir, interval)
    except Exception as e:
        print(f"Error creating grouped density plots: {e}")
    
    # Plot timeseries with error bands
    plot_timeseries_with_errors(data_dir, plot_dir, interval)
    
    # Plot ramp data grouped by buoy count
    plot_file = os.path.join(plot_dir, "b_pdr_grouped_by_buoy_count_ramp.png")
    plot_ramp_grouped_by_buoy_count_with_errors(data_dir, plot_file)

def get_density_dataframes(data_dir):
    files = glob.glob(os.path.join(data_dir, "*_density*.csv"))
    pdr_data = []
    collision_data = []
    
    # Extract data from CSV files
    for f in files:
        df = pd.read_csv(f, index_col=0)
        if "Density" in df.index and ("Delivery Ratio" in df.index or "B-PDR" in df.index):
            density = float(df.loc["Density", "Value"])
            pdr = float(df.loc["B-PDR", "Value"]) if "B-PDR" in df.index else float(df.loc["Delivery Ratio", "Value"])
            pdr_std = float(df.loc["B-PDR", "StdDev"]) if "B-PDR" in df.index else float(df.loc["Delivery Ratio", "StdDev"])
            
            # Extract average neighbors if available
            avg_neighbors = None
            if "Average Neighbors" in df.index:
                avg_neighbors = float(df.loc["Average Neighbors", "Value"])
            elif "Avg Neighbors" in df.index:
                avg_neighbors = float(df.loc["Avg Neighbors", "Value"])
            
            # Determine scheduler type
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif os.path.basename(f).startswith("static_"):
                sched_type = "static"
            elif os.path.basename(f).startswith("dynamic_"):
                sched_type = "dynamic"
            else:
                sched_type = "unknown"
                
            pdr_data.append((density, pdr, pdr_std, sched_type, avg_neighbors))
            
        if "Density" in df.index and "Collision Rate" in df.index:
            density = float(df.loc["Density", "Value"])
            collision_rate = float(df.loc["Collision Rate", "Value"])
            collision_std = float(df.loc["Collision Rate", "StdDev"])
            
            # Extract average neighbors if available
            avg_neighbors = None
            if "Average Neighbors" in df.index:
                avg_neighbors = float(df.loc["Average Neighbors", "Value"])
            elif "Avg Neighbors" in df.index:
                avg_neighbors = float(df.loc["Avg Neighbors", "Value"])
            
            # Determine scheduler type
            if "Scheduler Type" in df.index:
                sched_type = str(df.loc["Scheduler Type", "Value"]).lower()
            elif os.path.basename(f).startswith("static_"):
                sched_type = "static"
            elif os.path.basename(f).startswith("dynamic_"):
                sched_type = "dynamic"
            else:
                sched_type = "unknown"
                
            collision_data.append((density, collision_rate, collision_std, sched_type, avg_neighbors))
    
    # Create dataframes
    pdr_df = pd.DataFrame(pdr_data, columns=["Density", "B-PDR", "StdDev", "Scheduler", "AvgNeighbors"])
    coll_df = pd.DataFrame(collision_data, columns=["Density", "CollisionRate", "StdDev", "Scheduler", "AvgNeighbors"])
    
    return pdr_df, coll_df

def plot_block_by_density_with_errors(data_dir, plot_dir, interval=None):
    try:
        pdr_df, coll_df = get_density_dataframes(data_dir)
    except Exception as e:
        print(f"Error getting density data: {e}")
        return
    
    # Handle no data case
    if pdr_df.empty:
        print("No B-PDR data with density found.")
        return
    
    # Create B-PDR by density plot with error bars
    densities = sorted(pdr_df["Density"].unique())
    schedulers = ["static", "dynamic"]
    scheduler_labels = {"static": "SBP", "dynamic": "ADAB"}
    color_map = {"static": "tab:blue", "dynamic": "tab:green"}
    bar_width = 0.35
    x = np.arange(len(densities))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Add second y-axis for average neighbors
    ax2 = ax.twinx()
    ax2.set_ylabel("Average Neighbors", color="red")
    ax2.tick_params(axis='y', labelcolor="red")
    ax2.grid(False)
    
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
        
        ax.bar(x + i * bar_width, values, bar_width, 
               label=scheduler_labels[sched], color=color_map[sched])
        ax.errorbar(x + i * bar_width, values, yerr=errors, fmt='none', 
                   ecolor='black', capsize=5, alpha=0.7)
    
    # Plot average neighbors as a connected line across all densities
    avg_neighbors_data = {}
    for d in densities:
        # Use the average from both schedulers since it should be roughly the same
        rows = pdr_df[pdr_df["Density"] == d]
        if not rows.empty and not rows["AvgNeighbors"].isna().all():
            avg_neighbors_data[d] = rows["AvgNeighbors"].mean()
    
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
            ax2.plot(x_positions, neighbor_values, color='red', marker='o', 
                   linestyle='-', linewidth=2, label='Avg Neighbors')
            
            # Add text labels at each point
            for i, (x_pos, value) in enumerate(zip(x_positions, neighbor_values)):
                ax2.text(x_pos, value, f"{value:.1f}", color='red', 
                       ha='center', va='bottom', fontsize=8)
            
            # Set y-limits for average neighbors axis
            max_avg_neighbors = max(neighbor_values)
            ax2.set_ylim(0, max_avg_neighbors * 1.2)
    
    ax.set_xlabel("Total Buoys")
    ax.set_ylabel("B-PDR")
    if interval:
        ax.set_title(f"B-PDR vs Buoy Count (Static Interval: {interval}s)")
    else:
        ax.set_title("B-PDR vs Buoy Count")
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels([str(int(d)) for d in densities])
    
    # Create a combined legend
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
    
    # Skip collision rate plot if no data
    if coll_df.empty:
        print("No collision rate data with density found.")
        return
    
    # Create collision rate by density plot with error bars
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Add second y-axis for average neighbors
    ax2 = ax.twinx()
    ax2.set_ylabel("Average Neighbors", color="red")
    ax2.tick_params(axis='y', labelcolor="red")
    ax2.grid(False)
    
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
        
        ax.bar(x + i * bar_width, values, bar_width, 
               label=scheduler_labels[sched], color=color_map[sched])
        ax.errorbar(x + i * bar_width, values, yerr=errors, fmt='none', 
                   ecolor='black', capsize=5, alpha=0.7)
    
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
            ax2.plot(x_positions, neighbor_values, color='red', marker='o', 
                   linestyle='-', linewidth=2, label='Avg Neighbors')
            
            # Add text labels at each point
            for i, (x_pos, value) in enumerate(zip(x_positions, neighbor_values)):
                ax2.text(x_pos, value, f"{value:.1f}", color='red', 
                       ha='center', va='bottom', fontsize=8)
            
            # Set y-limits for average neighbors axis
            max_avg_neighbors = max(neighbor_values)
            ax2.set_ylim(0, max_avg_neighbors * 1.2)
    
    ax.set_xlabel("Total Buoys")
    ax.set_ylabel("Collision Rate")
    if interval:
        ax.set_title(f"Collision Rate vs Buoy Count (Static Interval: {interval}s)")
    else:
        ax.set_title("Collision Rate vs Buoy Count")
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels([str(int(d)) for d in densities])
    
    # Create a combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"collision_rate_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "collision_rate_block_by_density.png"))
    plt.close()

def plot_grouped_by_density_with_errors(pdr_df, coll_df, plot_dir, interval=None):
    """Plot grouped density data with error bars."""
    def get_density_group(density):
        return f"{5*((int(density)-1)//5) + 1}-{5*((int(density)-1)//5) + 5}"
    
    # Create density groups
    pdr_df['DensityGroup'] = pdr_df['Density'].apply(get_density_group)
    coll_df['DensityGroup'] = coll_df['Density'].apply(get_density_group)
    
    # Group the data and calculate means and standard deviations
    pdr_grouped = pdr_df.groupby(['DensityGroup', 'Scheduler']).agg({
        'B-PDR': 'mean',
        'StdDev': 'mean',  # Average the standard deviations
        'AvgNeighbors': 'mean'  # Average the neighbor counts within groups
    }).reset_index()
    
    coll_grouped = coll_df.groupby(['DensityGroup', 'Scheduler']).agg({
        'CollisionRate': 'mean',
        'StdDev': 'mean',  # Average the standard deviations
        'AvgNeighbors': 'mean'  # Average the neighbor counts within groups
    }).reset_index()
    
    def sort_key(group):
        return int(group.split('-')[0])
    
    # Get sorted density groups
    density_groups = sorted(pdr_grouped['DensityGroup'].unique(), key=sort_key)
    schedulers = ["static", "dynamic"]
    scheduler_labels = {"static": "SBP", "dynamic": "ADAB"}
    color_map = {"static": "tab:blue", "dynamic": "tab:green"}
    bar_width = 0.35
    x = np.arange(len(density_groups))
    
    # Create B-PDR by density group plot with error bars
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Create secondary y-axis for average neighbors
    ax2 = ax.twinx()
    ax2.set_ylabel("Average Neighbors", color="red")
    ax2.tick_params(axis='y', labelcolor="red")
    ax2.grid(False)
    
    for i, sched in enumerate(schedulers):
        values = []
        errors = []
        for grp in density_groups:
            row = pdr_grouped[(pdr_grouped["DensityGroup"] == grp) & (pdr_grouped["Scheduler"] == sched)]
            if not row.empty:
                values.append(row["B-PDR"].values[0])
                errors.append(row["StdDev"].values[0])
            else:
                values.append(0)
                errors.append(0)
        
        ax.bar(x + i * bar_width, values, bar_width, 
               label=scheduler_labels[sched], color=color_map[sched])
        ax.errorbar(x + i * bar_width, values, yerr=errors, fmt='none', 
                   ecolor='black', capsize=5, alpha=0.7)
    
    # Calculate average neighbors for each density group (averaging across schedulers)
    avg_neighbors_by_group = {}
    for grp in density_groups:
        rows = pdr_grouped[pdr_grouped["DensityGroup"] == grp]
        if not rows.empty and not rows["AvgNeighbors"].isna().all():
            avg_neighbors_by_group[grp] = rows["AvgNeighbors"].mean()
    
    # Plot average neighbors as a connected line
    if avg_neighbors_by_group:
        group_positions = list(range(len(density_groups)))
        neighbor_values = [avg_neighbors_by_group.get(grp, 0) for grp in density_groups]
        
        ax2.plot(group_positions, neighbor_values, color='red', marker='o',
               linestyle='-', linewidth=2, label='Avg Neighbors')
        
        # Add text labels at each point
        for i, value in enumerate(neighbor_values):
            if value > 0:  # Only label non-zero values
                ax2.text(i, value, f"{value:.1f}", color='red',
                       ha='center', va='bottom', fontsize=8)
        
        # Set y-limits for average neighbors axis
        max_avg_neighbors = max(filter(lambda x: x > 0, neighbor_values), default=1)
        ax2.set_ylim(0, max_avg_neighbors * 1.2)
    
    ax.set_xlabel("Total Buoys (Grouped)")
    ax.set_ylabel("Average B-PDR")
    if interval:
        ax.set_title(f"B-PDR vs Buoy Count Groups (Static Interval: {interval}s)")
    else:
        ax.set_title("B-PDR vs Buoy Count Groups")
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels(density_groups)
    
    # Create a combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='lower right')
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"b_pdr_grouped_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "b_pdr_grouped.png"))
    plt.close()
    
    # Create collision rate by density group plot with error bars
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Create secondary y-axis for average neighbors
    ax2 = ax.twinx()
    ax2.set_ylabel("Average Neighbors", color="red")
    ax2.tick_params(axis='y', labelcolor="red")
    ax2.grid(False)
    
    for i, sched in enumerate(schedulers):
        values = []
        errors = []
        for grp in density_groups:
            row = coll_grouped[(coll_grouped["DensityGroup"] == grp) & (coll_grouped["Scheduler"] == sched)]
            if not row.empty:
                values.append(row["CollisionRate"].values[0])
                errors.append(row["StdDev"].values[0])
            else:
                values.append(0)
                errors.append(0)
        
        ax.bar(x + i * bar_width, values, bar_width, 
               label=scheduler_labels[sched], color=color_map[sched])
        ax.errorbar(x + i * bar_width, values, yerr=errors, fmt='none', 
                   ecolor='black', capsize=5, alpha=0.7)
    
    # Plot average neighbors as a connected line
    if avg_neighbors_by_group:
        group_positions = list(range(len(density_groups)))
        neighbor_values = [avg_neighbors_by_group.get(grp, 0) for grp in density_groups]
        
        ax2.plot(group_positions, neighbor_values, color='red', marker='o',
               linestyle='-', linewidth=2, label='Avg Neighbors')
        
        # Add text labels at each point
        for i, value in enumerate(neighbor_values):
            if value > 0:  # Only label non-zero values
                ax2.text(i, value, f"{value:.1f}", color='red',
                       ha='center', va='bottom', fontsize=8)
        
        # Set y-limits for average neighbors axis
        max_avg_neighbors = max(filter(lambda x: x > 0, neighbor_values), default=1)
        ax2.set_ylim(0, max_avg_neighbors * 1.2)
    
    ax.set_xlabel("Total Buoys (Grouped)")
    ax.set_ylabel("Average Collision Rate")
    if interval:
        ax.set_title(f"Collision Rate vs Buoy Count Groups (Static Interval: {interval}s)")
    else:
        ax.set_title("Collision Rate vs Buoy Count Groups")
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels(density_groups)
    
    # Create a combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    
    if interval:
        plt.savefig(os.path.join(plot_dir, f"collision_rate_grouped_interval{int(interval*10)}.png"))
    else:
        plt.savefig(os.path.join(plot_dir, "collision_rate_grouped.png"))
    plt.close()

def plot_ramp_grouped_by_buoy_count_with_errors(data_dir, plot_file):
    modes = [("static", "tab:blue"), ("dynamic", "tab:green")]
    
    # First, collect data and determine overall min/max buoy counts
    min_buoys = float('inf')
    max_buoys = 0
    all_data = {}
    
    for mode, _ in modes:
        csv_file = os.path.join(data_dir, f"{mode}_ramp_timeseries.csv")
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
    grouped_std = {}
    avg_neighbors_by_group = {}  # Store average neighbors by buoy count group
    valid_modes = []
    
    for mode, color in modes:
        if mode in all_data:
            df = all_data[mode]
            
            if "B-PDR" in df.columns:
                y_col = "B-PDR"
                std_col = "B-PDR_std"
            elif "delivery_ratio" in df.columns:
                y_col = "delivery_ratio"
                std_col = "delivery_ratio_std"
            else:
                print(f"Warning: No B-PDR or delivery_ratio column in data for {mode}")
                continue
            
            # Check for average neighbors data
            avg_neighbors_col = None
            if "avg_neighbors" in df.columns:
                avg_neighbors_col = "avg_neighbors"
            elif "average_neighbors" in df.columns:
                avg_neighbors_col = "average_neighbors"
            
            # Group by buoy count
            df["group"] = pd.cut(df["n_buoys"], bins=group_edges, labels=group_labels, right=False)
            
            # Calculate mean and standard deviation for each group
            grouped = df.groupby("group", observed=False)[y_col].mean().reindex(group_labels)
            
            # Check if standard deviation column exists
            if std_col in df.columns:
                grouped_errors = df.groupby("group", observed=False)[std_col].mean().reindex(group_labels)
            else:
                grouped_errors = pd.Series(0, index=group_labels)
            
            # Calculate average neighbors by group if available
            if avg_neighbors_col:
                neighbors_by_group = df.groupby("group", observed=False)[avg_neighbors_col].mean().reindex(group_labels)
                for group, value in neighbors_by_group.items():
                    if group not in avg_neighbors_by_group:
                        avg_neighbors_by_group[group] = []
                    avg_neighbors_by_group[group].append(value)
            
            # Only include modes with non-empty data
            if not grouped.empty and len(grouped.values) > 0:
                grouped_data[mode] = grouped.values
                grouped_std[mode] = grouped_errors.values
                valid_modes.append((mode, color))
            else:
                print(f"Warning: No valid grouped data for {mode}")
    
    # Average the neighbors across modes for each group
    for group in avg_neighbors_by_group:
        avg_neighbors_by_group[group] = np.mean(avg_neighbors_by_group[group])
    
    # If no valid data found, exit early
    if not valid_modes:
        print("No valid data to plot for any mode")
        return
    
    # Plot the results with error bars
    x = np.arange(len(group_labels))
    bar_width = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create secondary y-axis for average neighbors
    ax2 = ax.twinx()
    ax2.set_ylabel("Average Neighbors", color="red")
    ax2.tick_params(axis='y', labelcolor="red")
    ax2.grid(False)
    
    for i, (mode, color) in enumerate(valid_modes):
        # Ensure data length matches x length
        data = grouped_data[mode]
        errors = grouped_std[mode]
        
        if len(data) == len(x):
            ax.bar(x + i * bar_width, data, bar_width, 
                  label=mode.capitalize(), color=color)
            
            # Add error bars if we have standard deviation data
            if np.any(errors > 0):
                ax.errorbar(x + i * bar_width, data, yerr=errors, fmt='none', 
                           ecolor='black', capsize=5, alpha=0.7)
        else:
            print(f"Warning: Data length mismatch for {mode}. Expected {len(x)}, got {len(data)}")
    
    # Plot average neighbors as a connected line
    if avg_neighbors_by_group:
        neighbor_values = [avg_neighbors_by_group.get(group, 0) for group in group_labels]
        
        ax2.plot(x, neighbor_values, color='red', marker='o',
               linestyle='-', linewidth=2, label='Avg Neighbors')
        
        # Add text labels at each point
        for i, value in enumerate(neighbor_values):
            if value > 0:  # Only label non-zero values
                ax2.text(i, value, f"{value:.1f}", color='red',
                       ha='center', va='bottom', fontsize=8)
        
        # Set y-limits for average neighbors axis
        max_avg_neighbors = max(filter(lambda x: x > 0, neighbor_values), default=1)
        ax2.set_ylim(0, max_avg_neighbors * 1.2)
    
    ax.set_xlabel("Buoy Count Group")
    ax.set_ylabel("Average B-PDR")
    ax.set_title("Average B-PDR vs Buoy Count Group (Ramp Scenario)")
    ax.set_xticks(x + (bar_width / 2 if len(valid_modes) > 1 else 0))
    ax.set_xticklabels(group_labels)
    
    # Create a combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='lower right')
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    
    plt.tight_layout()
    plt.savefig(plot_file)
    plt.close()

def plot_timeseries_with_errors(data_dir, plot_dir, interval=None):
    modes = [("static", "tab:blue"), ("dynamic", "tab:green")]
    plt.figure(figsize=(10, 6))
    found = False

    time_buoy = None
    max_buoys = 0
    time_neighbors = None

    for mode, color in modes:
        csv_file = os.path.join(data_dir, f"{mode}_ramp_timeseries.csv")
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            if "B-PDR" in df.columns:
                y_col = "B-PDR"
                std_col = "B-PDR_std"
            elif "delivery_ratio" in df.columns:
                y_col = "delivery_ratio"
                std_col = "delivery_ratio_std"
            else:
                print(f"Warning: No B-PDR or delivery_ratio column in {csv_file}")
                continue
                
            # Plot mean line
            plt.plot(df["time"], df[y_col], label=mode.capitalize(), color=color)
            
            # Add error band if standard deviation is available
            if std_col in df.columns:
                plt.fill_between(
                    df["time"],
                    df[y_col] - df[std_col],
                    df[y_col] + df[std_col],
                    color=color, alpha=0.2
                )
            
            found = True
            if time_buoy is None and "n_buoys" in df.columns:
                time_buoy = (df["time"], df["n_buoys"])
                max_buoys = df["n_buoys"].max()
            
            # Check for average neighbors data in timeseries
            if time_neighbors is None:
                if "avg_neighbors" in df.columns:
                    time_neighbors = (df["time"], df["avg_neighbors"])
                elif "average_neighbors" in df.columns:
                    time_neighbors = (df["time"], df["average_neighbors"])

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
        handles += [gray_area]
        labels += ["Buoy Count"]
        
        # Add average neighbors on third y-axis if available
        if time_neighbors is not None:
            ax3 = ax.twinx()
            # Offset the axis to the right
            ax3.spines["right"].set_position(("axes", 1.1))
            neighbor_line = ax3.plot(time_neighbors[0], time_neighbors[1], 
                                   color="red", linestyle="-", label="Avg. Neighbors")
            ax3.set_ylabel("Avg. Neighbors", color="red", fontsize=12)
            ax3.tick_params(axis='y', colors='red')
            ax3.grid(False)
            handles += neighbor_line
            labels += ["Avg. Neighbors"]

    ax.set_xlabel("Time (s)", fontsize=12)
    ax.set_ylabel("B-PDR", fontsize=12)
    if interval:
        plt.title(f"B-PDR vs Time (Ramp Scenario, Static Interval: {interval}s)")
    else:
        plt.title("B-PDR vs Time (Ramp Scenario)")

    ax.legend(handles, labels, loc="lower right", fontsize=11)
    ax.grid(True)
    plt.tight_layout()
    
    plt.savefig(os.path.join(plot_dir, "b_pdr_vs_time_ramp.png"))
    plt.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Average metrics across multiple simulation runs")
    parser.add_argument("--input-dirs", nargs="+", required=True, help="Input metrics directories")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    
    args = parser.parse_args()
    
    # Make sure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Input directories: {args.input_dirs}")
    print(f"Output directory: {args.output_dir}")
    
    average_metrics(args.input_dirs, args.output_dir)
    print(f"Metrics averaging complete.")

if __name__ == "__main__":
    main()