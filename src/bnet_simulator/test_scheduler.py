import subprocess
import time
import json
import os
import math
from tqdm import tqdm
from bnet_simulator.utils import config

def arrange_buoys_exact_density(world_width, world_height, neighbor_density, range_type="high_prob"):
    if range_type == "max":
        comm_range = config.COMMUNICATION_RANGE_MAX
    else:
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

PARAM_KEYS = [
    "MOTION_WEIGHT", "DENSITY_WEIGHT", "CONTACT_WEIGHT", "SCORE_FUNCTION"
]

def average_best_params(best_params):
    param_lists = {k: [] for k in PARAM_KEYS}
    for metric_params in best_params.values():
        if not isinstance(metric_params, dict):
            continue
        for k in PARAM_KEYS:
            param_lists[k].append(metric_params[k])
    avg_params = {}
    for k, v in param_lists.items():
        if not v:
            avg_params[k] = 0.0
        elif isinstance(v[0], (int, float)):
            avg_params[k] = sum(v) / len(v)
        elif k == "SCORE_FUNCTION":
            from collections import Counter
            avg_params[k] = Counter(v).most_common(1)[0][0]
        else:
            avg_params[k] = v[0]
    return avg_params

def write_param_file(params, filename):
    with open(filename, "w") as f:
        json.dump(params, f)

def run_batch(mode, avg_params=None):
    procs = []
    param_files = []
    max_duration = max(base_params["duration"] for base_params in BASE_PARAM_SETS)
    for i, base_params in enumerate(BASE_PARAM_SETS):
        positions_file = f"positions_{i}.json"
        with open(positions_file, "w") as f:
            json.dump(base_params["positions"], f)
        result_file = os.path.join(
            TEST_RESULTS_DIR,
            f"{mode}_density{base_params['density']}_n{base_params['fixed_buoy_count']}.csv"
        )
        cmd = [
            "uv", "run", "python", "src/bnet_simulator/main.py",
            "--mode", mode,
            "--seed", str(time.time()),
            "--world-width", str(base_params["world_width"]),
            "--world-height", str(base_params["world_height"]),
            "--mobile-buoy-count", str(base_params["mobile_buoy_count"]),
            "--fixed-buoy-count", str(base_params["fixed_buoy_count"]),
            "--duration", str(base_params["duration"]),
            "--headless",
            "--result-file", result_file,
            "--positions-file", positions_file,
            "--density", str(base_params["density"]),
        ]
        if IDEAL:
            cmd.append("--ideal")
        if mode == "dynamic" and avg_params is not None:
            param_file = f"test_parameters_{i}.json"
            write_param_file(avg_params, param_file)
            param_files.append(param_file)
            cmd += ["--param-file", param_file]
        procs.append(subprocess.Popen(cmd))
        time.sleep(0.1)
    with tqdm(total=max_duration, desc=f"{mode.capitalize()} test set", unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    for proc in procs:
        proc.wait()
    for param_file in param_files:
        if os.path.exists(param_file):
            os.remove(param_file)
    for i in range(len(BASE_PARAM_SETS)):
        positions_file = f"positions_{i}.json"
        if os.path.exists(positions_file):
            os.remove(positions_file)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ideal", 
        action="store_true",
        help="Use ideal channel conditions (no loss)"
    )
    args = parser.parse_args()
    global IDEAL
    IDEAL = args.ideal

    TEST_RESULTS_DIR = os.path.join("metrics", f"test_results{'_ideal' if IDEAL else ''}")
    TEST_PLOTS_DIR = os.path.join("metrics", f"test_plot{'_ideal' if IDEAL else ''}")
    BEST_PARAMS_FILE = os.path.join("metrics", f"best_dynamic_params{'_ideal' if IDEAL else ''}.json")

    os.makedirs(TEST_RESULTS_DIR, exist_ok=True)
    os.makedirs(TEST_PLOTS_DIR, exist_ok=True)
    os.makedirs("metrics", exist_ok=True)
    
    global BASE_PARAM_SETS
    BASE_PARAM_SETS = generate_density_scenarios(
        densities=range(2, 11), duration=120, headless=True, world_width=200, world_height=200
    )

    test_csvs = [
        f for f in os.listdir(TEST_RESULTS_DIR)
        if f.startswith("static_") or f.startswith("dynamic_")
    ] if os.path.exists(TEST_RESULTS_DIR) else []

    if test_csvs:
        print(f"Found {len(test_csvs)} test CSV files in '{TEST_RESULTS_DIR}', skipping test runs.")
    else:
        if not os.path.exists(BEST_PARAMS_FILE):
            print(f"Best parameters file '{BEST_PARAMS_FILE}' not found.")
            return
        with open(BEST_PARAMS_FILE, "r") as f:
            best_params = json.load(f)
        avg_params = average_best_params(best_params)

        if "SCORE_FUNCTION" in best_params["Delivery Ratio"]:
            config.SCORE_FUNCTION = best_params["Delivery Ratio"]["SCORE_FUNCTION"]

        print("Running static test set...")
        run_batch("static")
        print("Running dynamic test set...")
        run_batch("dynamic", avg_params=avg_params)

    print("Plotting test results...")
    subprocess.run([
        "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
        "--results-dir", TEST_RESULTS_DIR,
        "--plot-dir", TEST_PLOTS_DIR
    ])
    print("Done.")

if __name__ == "__main__":
    main()