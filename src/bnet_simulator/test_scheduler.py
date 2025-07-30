import os
import json
import pandas as pd
import subprocess
import glob
import time
import math
import random
from bnet_simulator.utils import config

TOTAL_BUOY = 50
DURATION = 1800 # 30 minutes

def arrange_buoys_exact_density(world_width, world_height, neighbor_density):
    # Use a wider range for non-ideal channel
    if not IDEAL:
        comm_range = config.COMMUNICATION_RANGE_MAX * 0.9
    else:
        comm_range = config.COMMUNICATION_RANGE_HIGH_PROB * 0.9
    k = neighbor_density
    n_buoys = k + 1
    area_radius = comm_range * (1.5 - (0.5 * k / 30))
    area_radius = max(comm_range * 0.5, min(comm_range, area_radius))
    center_x = world_width / 2
    center_y = world_height / 2
    positions = []
    random.seed(time.time())
    for i in range(n_buoys):
        angle = random.uniform(0, 2 * math.pi)
        distance = math.sqrt(random.random()) * area_radius
        x = center_x + distance * math.cos(angle)
        y = center_y + distance * math.sin(angle)
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
    scenarios = []
    # insert the scenario for the ramp
    if RAMP:
        positions = arrange_buoys_exact_density(world_width, world_height, densities[0])
        scenarios.append({
            "world_width": world_width,
            "world_height": world_height,
            "mobile_buoy_count": 0,
            "fixed_buoy_count": len(positions),
            "duration": duration,
            "headless": headless,
            "positions": positions,
            "ramp": True,
            "density": 1
        })
        return scenarios
    for d in densities:
        positions = arrange_buoys_exact_density(world_width, world_height, d)
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
            "--static-interval", str(STATIC_INTERVAL),
        ]
        
        if scenario.get("headless"):
            static_cmd.append("--headless")
        if scenario.get("ramp"):
            static_cmd.append("--ramp")
            result_file_path = os.path.join(results_dir, "static_ramp_timeseries.csv")
            static_cmd[static_cmd.index("--result-file") + 1] = result_file_path
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
            "--positions-file", dynamic_positions_file,
            "--density", str(scenario["density"]),
            "--static-interval", str(STATIC_INTERVAL),
        ]
        
        if scenario.get("headless"):
            dynamic_cmd.append("--headless")
        if scenario.get("ramp"):
            dynamic_cmd.append("--ramp")
            result_file_path = os.path.join(results_dir, "dynamic_ramp_timeseries.csv")
            dynamic_cmd[dynamic_cmd.index("--result-file") + 1] = result_file_path
        if IDEAL:
            dynamic_cmd.append("--ideal")
            
        all_procs.append(subprocess.Popen(dynamic_cmd))
        time.sleep(0.1)

    # Wait for any stragglers to finish
    for proc in all_procs:
        proc.wait()
    
    # Clean up temp files
    for file in positions_files:
        if os.path.exists(file):
            os.remove(file)
    
    total_sims = len(all_procs)    
    print(f"All {total_sims} simulations completed.")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ideal", action='store_true', help="Use ideal channel conditions (no loss)")
    parser.add_argument("--static-interval", type=float, default=1.0, help="Static interval value (default: 1.0)")
    parser.add_argument("--ramp", action='store_true', help="Use ramp scenario (buoy count increases)")
    args = parser.parse_args()

    global IDEAL, BASE_PARAM_SETS, STATIC_INTERVAL, RAMP
    IDEAL = args.ideal
    STATIC_INTERVAL = args.static_interval
    RAMP = args.ramp

    config.STATIC_INTERVAL = STATIC_INTERVAL
    config.BEACON_MIN_INTERVAL = STATIC_INTERVAL
    config.IDEAL_CHANNEL = IDEAL

    interval_str = str(int(STATIC_INTERVAL * 10))
    ideal_suffix = "_ideal" if IDEAL else ""
    ramp_suffix = "_ramp" if RAMP else ""

    duration = DURATION

    if RAMP:
        RESULTS_DIR = os.path.join("metrics", f"test_results_interval{interval_str}{ideal_suffix}{ramp_suffix}")
        PLOTS_DIR = os.path.join("metrics", f"test_plots_interval{interval_str}{ideal_suffix}{ramp_suffix}")
        os.makedirs(RESULTS_DIR, exist_ok=True)
        os.makedirs(PLOTS_DIR, exist_ok=True)

        BASE_PARAM_SETS = generate_density_scenarios(
            densities=[TOTAL_BUOY - 1],
            duration=duration,
            headless=True,
            world_width=800,
            world_height=800
        )
        scenario = BASE_PARAM_SETS[0]

        # Check if ramp results already exist
        static_ramp_file = os.path.join(RESULTS_DIR, "static_ramp_timeseries.csv")
        dynamic_ramp_file = os.path.join(RESULTS_DIR, "dynamic_ramp_timeseries.csv")
        if os.path.exists(static_ramp_file) and os.path.exists(dynamic_ramp_file):
            print("Ramp results already exist, skipping simulation.")
        else:
            for mode in ["static", "dynamic"]:
                result_file = os.path.join(RESULTS_DIR, f"{mode}_ramp_timeseries.csv")
                positions_file = f"positions_{mode}_ramp.json"
                with open(positions_file, "w") as f:
                    json.dump(scenario["positions"], f)
                cmd = [
                    "uv", "run", "python", "src/bnet_simulator/main.py",
                    "--mode", mode,
                    "--seed", str(int(time.time())),
                    "--world-width", str(scenario["world_width"]),
                    "--world-height", str(scenario["world_height"]),
                    "--mobile-buoy-count", str(scenario["mobile_buoy_count"]),
                    "--fixed-buoy-count", str(scenario["fixed_buoy_count"]),
                    "--duration", str(scenario["duration"]),
                    "--result-file", result_file,
                    "--positions-file", positions_file,
                    "--static-interval", str(STATIC_INTERVAL),
                    "--ramp"
                ]
                if IDEAL:
                    cmd.append("--ideal")
                print(f"Running: {' '.join(cmd)}")
                subprocess.run(cmd)
                if os.path.exists(positions_file):
                    os.remove(positions_file)

        print("Plotting results...")
        plot_cmd = [
            "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
            "--results-dir", RESULTS_DIR,
            "--plot-dir", PLOTS_DIR,
            "--interval", str(STATIC_INTERVAL)
        ]
        subprocess.run(plot_cmd)
        print("All ramp simulations complete.")
        return

    # Non-ramp scenario (density sweep)
    RESULTS_DIR = os.path.join("metrics", f"test_results_interval{interval_str}{ideal_suffix}")
    PLOTS_DIR = os.path.join("metrics", f"test_plots_interval{interval_str}{ideal_suffix}")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)
    BASE_PARAM_SETS = generate_density_scenarios(
        densities=range(2, TOTAL_BUOY),  # 2 to 39 buoys, or 50 for ideal
        duration=duration,
        headless=True,
        world_width=800,
        world_height=800
    )
    scenario_seeds = [int(time.time()) + i for i in range(len(BASE_PARAM_SETS))]

    need_static = not results_exist(RESULTS_DIR, "static")
    need_dynamic = not results_exist(RESULTS_DIR, "dynamic")

    if need_static or need_dynamic:
        print("Running simulations in parallel...")
        run_all_scenarios_parallel(scenario_seeds, RESULTS_DIR)
        print("All simulations complete.")
    else:
        print("Found existing CSV files for both static and dynamic, skipping simulations.")

    print("Plotting results...")
    plot_cmd = [
        "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
        "--results-dir", RESULTS_DIR,
        "--plot-dir", PLOTS_DIR,
        "--interval", str(STATIC_INTERVAL)
    ]
    subprocess.run(plot_cmd)
    print("All simulations complete.")

if __name__ == "__main__":
    main()