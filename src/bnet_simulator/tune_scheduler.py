import os
import json
import pandas as pd
import subprocess
import glob
import time
import math
from tqdm import tqdm
from bnet_simulator.utils import config

def arrange_buoys_exact_density(world_width, world_height, neighbor_density, range_type="high_prob"):
    comm_range = config.COMMUNICATION_RANGE_HIGH_PROB
    k = neighbor_density
    n_buoys = max(20, k + 1)
    angle_step = 2 * math.pi / n_buoys
    theta = k * angle_step / 2
    radius = comm_range / (2 * math.sin(theta / 2))
    center_x = world_width / 2
    center_y = world_height / 2
    positions = []
    for i in range(n_buoys):
        angle = i * angle_step
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        positions.append((x, y))
    return positions

def generate_density_scenarios(
    densities=range(2, 11),
    duration=120,
    headless=True,
    world_width=200,
    world_height=200
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
    """Check if at least one result CSV exists for a given scheduler type."""
    return bool(glob.glob(os.path.join(results_dir, f"{prefix}_*.csv")))

def run_static_scenarios(scenario_seeds, results_dir):
    procs = []
    for i, scenario in enumerate(BASE_PARAM_SETS):
        seed = scenario_seeds[i] if scenario_seeds else int(time.time())
        positions_file = f"positions_{i}.json"
        with open(positions_file, "w") as f:
            json.dump(scenario["positions"], f)
        result_file = os.path.join(
            results_dir,
            f"static_density{scenario['density']}_n{scenario['fixed_buoy_count']}.csv"
        )
        cmd = BASE_CMD + [
            "--mode", "static",
            "--seed", str(seed),
            "--world-width", str(scenario["world_width"]),
            "--world-height", str(scenario["world_height"]),
            "--mobile-buoy-count", str(scenario["mobile_buoy_count"]),
            "--fixed-buoy-count", str(scenario["fixed_buoy_count"]),
            "--duration", str(scenario["duration"]),
            "--result-file", result_file,
            "--positions-file", positions_file,
            "--density", str(scenario["density"]),
        ]
        if scenario.get("headless"):
            cmd.append("--headless")
        if IDEAL:
            cmd.append("--ideal")
        procs.append(subprocess.Popen(cmd))
        time.sleep(0.1)
    max_duration = max(scenario["duration"] for scenario in BASE_PARAM_SETS)
    with tqdm(total=max_duration, desc="Simulating static", leave=False, unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    for proc in procs:
        proc.wait()
    for i in range(len(BASE_PARAM_SETS)):
        positions_file = f"positions_{i}.json"
        if os.path.exists(positions_file):
            os.remove(positions_file)

def run_dynamic_scenarios(scenario_seeds, results_dir):
    procs = []
    for i, scenario in enumerate(BASE_PARAM_SETS):
        seed = scenario_seeds[i] if scenario_seeds else int(time.time())
        positions_file = f"positions_{i}.json"
        with open(positions_file, "w") as f:
            json.dump(scenario["positions"], f)
        result_file = os.path.join(
            results_dir,
            f"dynamic_density{scenario['density']}_n{scenario['fixed_buoy_count']}.csv"
        )
        cmd = BASE_CMD + [
            "--mode", "dynamic",
            "--seed", str(seed),
            "--world-width", str(scenario["world_width"]),
            "--world-height", str(scenario["world_height"]),
            "--mobile-buoy-count", str(scenario["mobile_buoy_count"]),
            "--fixed-buoy-count", str(scenario["fixed_buoy_count"]),
            "--duration", str(scenario["duration"]),
            "--result-file", result_file,
            "--headless",
            "--positions-file", positions_file,
            "--density", str(scenario["density"]),
        ]
        if IDEAL:
            cmd.append("--ideal")
        procs.append(subprocess.Popen(cmd))
        time.sleep(0.1)
    max_duration = max(scenario["duration"] for scenario in BASE_PARAM_SETS)
    with tqdm(total=max_duration, desc="Simulating dynamic", leave=False, unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    for proc in procs:
        proc.wait()
    for i in range(len(BASE_PARAM_SETS)):
        positions_file = f"positions_{i}.json"
        if os.path.exists(positions_file):
            os.remove(positions_file)

def run_all_scenarios_parallel(scenario_seeds, results_dir):
    """Run both static and dynamic scenarios in parallel"""
    all_procs = []
    positions_files = []
    
    # Start all simulations (both static and dynamic) in parallel
    print(f"Starting parallel simulations for {len(BASE_PARAM_SETS)} density scenarios...")
    for i, scenario in enumerate(BASE_PARAM_SETS):
        seed = scenario_seeds[i] if scenario_seeds else int(time.time())
        
        # Setup static scenario
        static_positions_file = f"positions_static_{i}.json"
        positions_files.append(static_positions_file)
        with open(static_positions_file, "w") as f:
            json.dump(scenario["positions"], f)
        static_result_file = os.path.join(
            results_dir,
            f"static_density{scenario['density']}_n{scenario['fixed_buoy_count']}.csv"
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
        ]
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
            f"dynamic_density{scenario['density']}_n{scenario['fixed_buoy_count']}.csv"
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
        ]
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
    args = parser.parse_args()
    global IDEAL, BASE_PARAM_SETS
    IDEAL = args.ideal

    RESULTS_DIR = os.path.join("metrics", f"tune_results{'_ideal' if IDEAL else ''}")
    PLOTS_DIR = os.path.join("metrics", f"tune_plots{'_ideal' if IDEAL else ''}")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)

    BASE_PARAM_SETS = generate_density_scenarios(
        densities=range(2, 11), duration=300, headless=True, world_width=300, world_height=300
    )

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

    print("Plotting results...")
    subprocess.run([
        "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
        "--results-dir", RESULTS_DIR,
        "--plot-dir", PLOTS_DIR
    ])
    print("All simulations complete.")

if __name__ == "__main__":
    main()