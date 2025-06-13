import os
import json
import pandas as pd
import subprocess
import glob
import time
import random
from itertools import product, islice
from tqdm import tqdm
from bnet_simulator.utils import config

# ---- Directory Utility ----
def get_metrics_dir(base, ideal):
    return os.path.join("metrics", f"{base}{'_ideal' if ideal else ''}")

IDEAL = getattr(config, "IDEAL_CHANNEL", False)
RESULTS_DIR = get_metrics_dir("tune_results", IDEAL)
PLOTS_DIR = get_metrics_dir("tune_plot", IDEAL)
BEST_PARAMS_FILE = os.path.join("metrics", f"best_dynamic_params{'_ideal' if IDEAL else ''}.json")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs("metrics", exist_ok=True)

BASE_CMD = ["uv", "run", "python", "src/bnet_simulator/main.py"]
METRICS = [
    "Delivery Ratio"
]
PARAM_BATCH_SIZE = 2

# ---- Search Space ----
PARAM_SPACE = {
    "MOTION_WEIGHT": [0.1, 0.3],
    "DENSITY_WEIGHT": [0.2, 0.4],
    "CONTACT_WEIGHT": [0.1, 0.3],
    "CONGESTION_WEIGHT": [0.1, 0.3],
    "DENSITY_MIDPOINT": [2.5],
    "DENSITY_ALPHA": [3.0, 4.0],
    "CONTACT_MIDPOINT": [6.0],
    "CONTACT_ALPHA": [1.5],
}

# ---- Scenarios ----
BASE_PARAM_SETS = [
    # 500x500 world
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 4, "fixed_buoy_count": 4, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 8, "fixed_buoy_count": 8, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 12, "fixed_buoy_count": 12, "duration": 180, "headless": True},
    # 800x800 world (scaled up)
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 8, "fixed_buoy_count": 8, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 12, "fixed_buoy_count": 12, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 16, "fixed_buoy_count": 16, "duration": 180, "headless": True},
]

def collect_metrics(scheduler_type):
    pattern = os.path.join(RESULTS_DIR, f"{scheduler_type}_*.csv")
    metrics = []
    for file in glob.glob(pattern):
        df = pd.read_csv(file, index_col=0)
        row = df["Value"].to_dict()
        row["filename"] = os.path.basename(file)
        metrics.append(row)
    return pd.DataFrame(metrics)

def evaluate_metrics(df):
    # Only consider Delivery Ratio
    return {"Delivery Ratio": pd.to_numeric(df["Delivery Ratio"], errors="coerce").mean() if "Delivery Ratio" in df.columns else float('nan')}

def batched(iterable, n):
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            break
        yield batch

def run_static_scenarios(seeds):
    procs = []
    for i, scenario in enumerate(BASE_PARAM_SETS):
        seed = seeds[i] if seeds else int(random.uniform(1, 1e9))
        result_file = os.path.join(
            RESULTS_DIR,
            f"static_{int(scenario['world_width'])}x{int(scenario['world_height'])}_"
            f"mob{scenario['mobile_buoy_count']}_fix{scenario['fixed_buoy_count']}.csv"
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
        ]
        if scenario.get("headless"):
            cmd.append("--headless")
        procs.append(subprocess.Popen(cmd))
        time.sleep(0.1)
    max_duration = max(scenario["duration"] for scenario in BASE_PARAM_SETS)
    with tqdm(total=max_duration, desc="Simulating static", leave=False, unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    for proc in procs:
        proc.wait()

def run_dynamic_batch(param_batch, batch_start_idx, scenario_seeds, total_pbar=None):
    procs = []
    param_idx_offset = batch_start_idx
    for batch_param_idx, params in enumerate(param_batch):
        param_idx = param_idx_offset + batch_param_idx
        for scenario_idx, scenario in enumerate(BASE_PARAM_SETS):
            param_file = f"current_parameters_{scenario_idx}_{param_idx}.json"
            with open(param_file, "w") as f:
                json.dump(params, f)
            result_file = os.path.join(
                RESULTS_DIR,
                f"dynamic_{int(scenario['world_width'])}x{int(scenario['world_height'])}_"
                f"mob{scenario['mobile_buoy_count']}_fix{scenario['fixed_buoy_count']}_param{param_idx}.csv"
            )
            cmd = BASE_CMD + [
                "--mode", "dynamic",
                "--seed", str(scenario_seeds[scenario_idx]),
                "--world-width", str(scenario["world_width"]),
                "--world-height", str(scenario["world_height"]),
                "--mobile-buoy-count", str(scenario["mobile_buoy_count"]),
                "--fixed-buoy-count", str(scenario["fixed_buoy_count"]),
                "--duration", str(scenario["duration"]),
                "--param-file", param_file,
                "--result-file", result_file,
                "--headless"
            ]
            procs.append(subprocess.Popen(cmd))
            time.sleep(0.1)
    max_duration = max(scenario["duration"] for scenario in BASE_PARAM_SETS)
    with tqdm(total=max_duration, desc="Dynamic batch", leave=False, unit="s") as batch_pbar:
        for _ in range(max_duration):
            time.sleep(1)
            batch_pbar.update(1)
    for proc in procs:
        proc.wait()
        if total_pbar is not None:
            total_pbar.update(1)
    # Clean up param files
    for batch_param_idx, params in enumerate(param_batch):
        param_idx = param_idx_offset + batch_param_idx
        for scenario_idx, scenario in enumerate(BASE_PARAM_SETS):
            param_file = f"current_parameters_{scenario_idx}_{param_idx}.json"
            if os.path.exists(param_file):
                os.remove(param_file)

def main():
    scenario_seeds = [int(random.uniform(1, 1e9)) for _ in BASE_PARAM_SETS]

    # 1. Run all static scenarios (only if not already present)
    static_csvs = glob.glob(os.path.join(RESULTS_DIR, "static_*.csv"))
    if static_csvs:
        print(f"Found {len(static_csvs)} static CSV files, skipping static simulation.")
    else:
        print("Running all static scenarios...")
        run_static_scenarios(scenario_seeds)
    static_df = collect_metrics("static")
    static_scores = evaluate_metrics(static_df)

    # 2. Prepare all parameter sets
    keys, values = zip(*PARAM_SPACE.items())
    all_param_sets = [dict(zip(keys, combo)) for combo in product(*values)]
    print(f"Total parameter sets: {len(all_param_sets)}")
    print(f"Running dynamic scenarios in batches of {PARAM_BATCH_SIZE}...")

    total_jobs = len(all_param_sets) * len(BASE_PARAM_SETS)
    with tqdm(total=total_jobs, desc="TOTAL dynamic tuning progress", position=0, unit="sim") as total_pbar:
        for batch_start_idx, param_batch in enumerate(batched(all_param_sets, PARAM_BATCH_SIZE)):
            run_dynamic_batch(param_batch, batch_start_idx * PARAM_BATCH_SIZE, scenario_seeds, total_pbar=total_pbar)

    # 4. Collect and evaluate
    best_delivery_ratio = -float("inf")
    best_params = None

    for param_idx, params in enumerate(all_param_sets):
        param_results = []
        for file in glob.glob(os.path.join(RESULTS_DIR, f"dynamic_*_param{param_idx}.csv")):
            df = pd.read_csv(file, index_col=0)
            if "Delivery Ratio" in df.index:
                try:
                    val = float(df.loc["Delivery Ratio", "Value"])
                    param_results.append(val)
                except Exception:
                    continue
        if not param_results:
            avg_delivery_ratio = float('-inf')
        else:
            avg_delivery_ratio = sum(param_results) / len(param_results)
        if best_params is None or avg_delivery_ratio > best_delivery_ratio:
            best_delivery_ratio = avg_delivery_ratio
            best_params = params

    # Always write the best found, even if it's not better than static
    with open(BEST_PARAMS_FILE, "w") as f:
        json.dump({
            "Delivery Ratio": best_params,
            "Best Delivery Ratio Value": best_delivery_ratio
        }, f, indent=2)

    print("Best parameters for Delivery Ratio:")
    print(json.dumps(best_params, indent=2))
    print(f"Best parameter set saved to {BEST_PARAMS_FILE}")

    print("Plotting tuning results...")
    subprocess.run([
        "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
        "--results-dir", RESULTS_DIR,
        "--plot-dir", PLOTS_DIR
    ])
    print("Done.")

if __name__ == "__main__":
    main()