import subprocess
import time
import json
import os
import shutil
from tqdm import tqdm

# ---- Scenarios ----
BASE_PARAM_SETS = [
    # 500x500 world
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 5, "fixed_buoy_count": 5, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 10, "fixed_buoy_count": 10, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 180, "headless": True},
    # 800x800 world (scaled up)
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 10, "fixed_buoy_count": 10, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 20, "fixed_buoy_count": 20, "duration": 180, "headless": True},
]

BEST_PARAMS_FILE = "best_dynamic_params.json"
PARAM_KEYS = [
    "MOTION_WEIGHT", "DENSITY_WEIGHT", "CONTACT_WEIGHT", "CONGESTION_WEIGHT",
    "DENSITY_MIDPOINT", "DENSITY_ALPHA", "CONTACT_MIDPOINT", "CONTACT_ALPHA"
]

TEST_RESULTS_DIR = "test_results"
SRC_RESULTS_DIR = "tune_results"
METRICS = ["Delivery Ratio"]

def average_best_params(best_params):
    # best_params: dict of metric -> param dict (and possibly floats)
    param_lists = {k: [] for k in PARAM_KEYS}
    for metric_params in best_params.values():
        if not isinstance(metric_params, dict):
            continue  # skip floats like "Best Delivery Ratio Value"
        for k in PARAM_KEYS:
            param_lists[k].append(metric_params[k])
    # Compute average for each param
    avg_params = {k: sum(v)/len(v) if v else 0.0 for k, v in param_lists.items()}
    return avg_params

def write_param_file(params, filename):
    with open(filename, "w") as f:
        json.dump(params, f)

def run_batch(mode, avg_params=None):
    procs = []
    param_files = []
    max_duration = max(base_params["duration"] for base_params in BASE_PARAM_SETS)
    for i, base_params in enumerate(BASE_PARAM_SETS):
        result_file = os.path.join(
            TEST_RESULTS_DIR,
            f"{mode}_{int(base_params['world_width'])}x{int(base_params['world_height'])}_"
            f"mob{base_params['mobile_buoy_count']}_fix{base_params['fixed_buoy_count']}.csv"
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
            "--result-file", result_file
        ]
        if mode == "dynamic" and avg_params is not None:
            param_file = f"test_parameters_{i}.json"
            write_param_file(avg_params, param_file)
            param_files.append(param_file)
            cmd += ["--param-file", param_file]
        procs.append(subprocess.Popen(cmd))
        time.sleep(0.1)
    # Progress bar for the max duration (in seconds)
    with tqdm(total=max_duration, desc=f"{mode.capitalize()} test set", unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    # Wait for all processes to finish (if any are still running)
    for proc in procs:
        proc.wait()
    for param_file in param_files:
        if os.path.exists(param_file):
            os.remove(param_file)

def move_results_to_test_dir():
    if not os.path.exists(SRC_RESULTS_DIR):
        print(f"Source results directory '{SRC_RESULTS_DIR}' does not exist. Skipping move.")
        return
    for f in os.listdir(SRC_RESULTS_DIR):
        if f.startswith("static_") or f.startswith("dynamic_"):
            src = os.path.join(SRC_RESULTS_DIR, f)
            dst = os.path.join(TEST_RESULTS_DIR, f)
            shutil.move(src, dst)

def main():
    # Check if test results already exist
    test_csvs = [
        f for f in os.listdir(TEST_RESULTS_DIR)
        if f.startswith("static_") or f.startswith("dynamic_")
    ] if os.path.exists(TEST_RESULTS_DIR) else []

    if test_csvs:
        print(f"Found {len(test_csvs)} test CSV files in '{TEST_RESULTS_DIR}', skipping test runs.")
    else:
        # Load and average best parameters
        if not os.path.exists(BEST_PARAMS_FILE):
            print(f"Best parameters file '{BEST_PARAMS_FILE}' not found.")
            return
        with open(BEST_PARAMS_FILE, "r") as f:
            best_params = json.load(f)
        avg_params = average_best_params(best_params)

        print("Running static test set...")
        run_batch("static")
        print("Running dynamic test set...")
        run_batch("dynamic", avg_params=avg_params)

    print("Plotting test results...")
    import subprocess
    subprocess.run([
        "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
        "--results-dir", TEST_RESULTS_DIR,
        "--plot-dir", "test_plots"
    ])
    print("Done.")

if __name__ == "__main__":
    if not os.path.exists(TEST_RESULTS_DIR):
        os.makedirs(TEST_RESULTS_DIR)
    main()