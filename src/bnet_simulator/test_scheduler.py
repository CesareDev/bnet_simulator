import subprocess
import time
import json
import os
from tqdm import tqdm
from bnet_simulator.utils import config

def get_metrics_dir(base, ideal):
    return os.path.join("metrics", f"{base}{'_ideal' if ideal else ''}")

IDEAL = getattr(config, "IDEAL_CHANNEL", False)
TEST_RESULTS_DIR = get_metrics_dir("test_results", IDEAL)
TEST_PLOTS_DIR = get_metrics_dir("test_plot", IDEAL)
BEST_PARAMS_FILE = os.path.join("metrics", f"best_dynamic_params{'_ideal' if IDEAL else ''}.json")

os.makedirs(TEST_RESULTS_DIR, exist_ok=True)
os.makedirs(TEST_PLOTS_DIR, exist_ok=True)
os.makedirs("metrics", exist_ok=True)

BASE_PARAM_SETS = [
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 4, "fixed_buoy_count": 4, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 8, "fixed_buoy_count": 8, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 12, "fixed_buoy_count": 12, "duration": 180, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 8, "fixed_buoy_count": 8, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 12, "fixed_buoy_count": 12, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 16, "fixed_buoy_count": 16, "duration": 180, "headless": True},
]
PARAM_KEYS = [
    "MOTION_WEIGHT", "DENSITY_WEIGHT", "CONTACT_WEIGHT", "CONGESTION_WEIGHT",
    "DENSITY_MIDPOINT", "DENSITY_ALPHA", "CONTACT_MIDPOINT", "CONTACT_ALPHA"
]

def average_best_params(best_params):
    param_lists = {k: [] for k in PARAM_KEYS}
    for metric_params in best_params.values():
        if not isinstance(metric_params, dict):
            continue
        for k in PARAM_KEYS:
            param_lists[k].append(metric_params[k])
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
    with tqdm(total=max_duration, desc=f"{mode.capitalize()} test set", unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    for proc in procs:
        proc.wait()
    for param_file in param_files:
        if os.path.exists(param_file):
            os.remove(param_file)

def main():
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