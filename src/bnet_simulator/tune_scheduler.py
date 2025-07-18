import os
import json
import pandas as pd
import subprocess
import glob
import time
import math
import random
from tqdm import tqdm
from bnet_simulator.utils import config

def arrange_buoys_exact_density(world_width, world_height, neighbor_density, range_type="high_prob", jitter=1.0):
    """
    Arrange buoys randomly within an area to achieve approximate neighbor density.
    Uses random positions instead of a perfect circle to create more realistic scenarios.
    """
    comm_range = config.COMMUNICATION_RANGE_HIGH_PROB * 0.9  # Use 90% of the range for safety
    k = neighbor_density
    
    # Use k+1 buoys for the minimum needed to achieve density k
    n_buoys = k + 1
    
    # Calculate the area size needed for this density
    # For higher densities, we need a smaller area to keep buoys in range of each other
    area_radius = comm_range * (1.5 - (0.5 * k / 30))  # Shrinks area as density increases
    
    # Ensure radius is reasonable - between 0.5 and 1.0 of comm_range
    area_radius = max(comm_range * 0.5, min(comm_range, area_radius))
    
    center_x = world_width / 2
    center_y = world_height / 2
    positions = []
    
    # Use current time as seed for random generator
    random.seed(time.time())
    
    # Generate random positions within the calculated area
    for i in range(n_buoys):
        # Random angle and distance from center
        angle = random.uniform(0, 2 * math.pi)
        # Use square root for distance to ensure uniform distribution in circle
        distance = math.sqrt(random.random()) * area_radius
        
        x = center_x + distance * math.cos(angle)
        y = center_y + distance * math.sin(angle)
        
        # Ensure positions are within world bounds
        x = max(10, min(world_width - 10, x))
        y = max(10, min(world_height - 10, y))
        
        positions.append((x, y))
    
    return positions

def generate_density_scenarios(
    densities,
    duration,
    headless,
    world_width,
    world_height
):
    range_type = "max" if not IDEAL else "high_prob"
    scenarios = []
    for d in densities:
        positions = arrange_buoys_exact_density(world_width, world_height, d, range_type=range_type)
        scenarios.append({
            "world_width": world_width,
            "world_height": world_height,
            "mobile_buoy_count": 0,
            "fixed_buoy_count": len(positions),
            "duration": duration,
            "headless": headless,
            "positions": positions,
            "density": d
        })
    return scenarios

BASE_CMD = ["uv", "run", "python", "src/bnet_simulator/main.py"]
METRICS = ["Delivery Ratio"]

def collect_metrics(scheduler_type, results_dir):
    pattern = os.path.join(results_dir, f"{scheduler_type}_*.csv")
    metrics = []
    for file in glob.glob(pattern):
        df = pd.read_csv(file, index_col=0)
        row = df["Value"].to_dict()
        row["filename"] = os.path.basename(file)
        metrics.append(row)
    return pd.DataFrame(metrics)

def results_exist(results_dir, prefix):
    return bool(glob.glob(os.path.join(results_dir, f"{prefix}_*.csv")))

def run_all_scenarios_parallel(scenario_seeds, results_dir):
    all_procs = []
    positions_files = []
    
    # Start all simulations (both static and dynamic) in parallel
    print(f"Starting parallel simulations for {len(BASE_PARAM_SETS)} scenarios...")
    for i, scenario in enumerate(BASE_PARAM_SETS):
        seed = scenario_seeds[i] if scenario_seeds else int(time.time())
        
        # Handle vessel scenarios
        vessel_args = []
        if scenario.get("has_vessel", False):
            vessel_args = ["--vessel-index", str(scenario.get("vessel_index", 0))]
        
        # Setup static scenario
        static_positions_file = f"positions_static_{i}.json"
        positions_files.append(static_positions_file)
        with open(static_positions_file, "w") as f:
            json.dump(scenario["positions"], f)
        static_result_file = os.path.join(
            results_dir,
            f"static_{'vessel_' if scenario.get('has_vessel', False) else ''}density{scenario['density']}_n{scenario['fixed_buoy_count']}.csv"
        )
        static_cmd = BASE_CMD + [
            "--mode", "static",
            "--seed", str(seed),
            "--world-width", str(scenario["world_width"]),
            "--world-height", str(scenario["world_height"]),
            "--mobile-buoy-count", str(scenario["mobile_buoy_count"]),
            "--fixed-buoy-count", str(scenario["fixed_buoy_count"]),
            "--duration", str(scenario["duration"]),
            "--result-file", static_result_file,
            "--positions-file", static_positions_file,
            "--density", str(scenario["density"]),
            "--static-interval", str(STATIC_INTERVAL),  # Add this line
        ] + vessel_args
        
        if scenario.get("headless"):
            static_cmd.append("--headless")
        if IDEAL:
            static_cmd.append("--ideal")
        all_procs.append(subprocess.Popen(static_cmd))
        time.sleep(0.1)
        
        # Setup dynamic scenario
        dynamic_positions_file = f"positions_dynamic_{i}.json"
        positions_files.append(dynamic_positions_file)
        with open(dynamic_positions_file, "w") as f:
            json.dump(scenario["positions"], f)
        dynamic_result_file = os.path.join(
            results_dir,
            f"dynamic_{'vessel_' if scenario.get('has_vessel', False) else ''}density{scenario['density']}_n{scenario['fixed_buoy_count']}.csv"
        )
        dynamic_cmd = BASE_CMD + [
            "--mode", "dynamic",
            "--seed", str(seed),
            "--world-width", str(scenario["world_width"]),
            "--world-height", str(scenario["world_height"]),
            "--mobile-buoy-count", str(scenario["mobile_buoy_count"]),
            "--fixed-buoy-count", str(scenario["fixed_buoy_count"]),
            "--duration", str(scenario["duration"]),
            "--result-file", dynamic_result_file,
            "--headless",
            "--positions-file", dynamic_positions_file,
            "--density", str(scenario["density"]),
        ] + vessel_args
        
        if IDEAL:
            dynamic_cmd.append("--ideal")
        all_procs.append(subprocess.Popen(dynamic_cmd))
        time.sleep(0.1)
    
    # Wait for all processes to complete
    max_duration = max(scenario["duration"] for scenario in BASE_PARAM_SETS)
    total_sims = len(all_procs)
    print(f"Running {total_sims} simulations in parallel...")
    with tqdm(total=max_duration, desc="Simulating all scenarios", unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    
    # Wait for any stragglers to finish
    for proc in all_procs:
        proc.wait()
    
    # Clean up temp files
    for file in positions_files:
        if os.path.exists(file):
            os.remove(file)
    
    print(f"All {total_sims} simulations completed.")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ideal",
        action='store_true',
        help="Use ideal channel conditions (no loss)"
    )
    parser.add_argument(
        "--vessel",
        action='store_true',
        help="Run scenario with a vessel (listening-only buoy)"
    )
    parser.add_argument(
        "--static-interval",
        type=float,
        default=1.0,
        help="Static interval value (default: 1.0)"
    )
    args = parser.parse_args()
    global IDEAL, BASE_PARAM_SETS, STATIC_INTERVAL
    IDEAL = args.ideal
    STATIC_INTERVAL = args.static_interval
    
    # Regular density scenarios
    duration = 900  # 10 minutes
    BASE_PARAM_SETS = generate_density_scenarios(densities=range(2, 30), duration=duration, headless=True, world_width=800, world_height=800)
    # Include interval in directory names
    RESULTS_DIR = os.path.join("metrics", f"tune_results_interval{int(STATIC_INTERVAL)}" + ("_ideal" if IDEAL else ""))
    PLOTS_DIR = os.path.join("metrics", f"tune_plots_interval{int(STATIC_INTERVAL)}" + ("_ideal" if IDEAL else ""))
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)

    scenario_seeds = [int(time.time()) + i for i in range(len(BASE_PARAM_SETS))]

    # Check if we need to run any simulations
    need_static = not results_exist(RESULTS_DIR, "static")
    need_dynamic = not results_exist(RESULTS_DIR, "dynamic")
    
    if need_static or need_dynamic:
        print("Running simulations in parallel...")
        run_all_scenarios_parallel(scenario_seeds, RESULTS_DIR)
        print("All simulations complete.")
    else:
        print("Found existing CSV files for both static and dynamic, skipping simulations.")

    # Uncommented plotting section
    print("Plotting results...")
    subprocess.run([
        "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
        "--results-dir", RESULTS_DIR,
        "--plot-dir", PLOTS_DIR,
        "--interval", str(STATIC_INTERVAL)  # Pass interval to plotting script
    ])
    print("All simulations complete.")

if __name__ == "__main__":
    main()
