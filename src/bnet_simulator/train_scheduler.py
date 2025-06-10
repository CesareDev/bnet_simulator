import os
import json
import pandas as pd
import subprocess
import glob
import time
import random
from itertools import product
from tqdm import tqdm

# ---- Configurable ----
BASE_CMD = ["uv", "run", "python", "src/bnet_simulator/main.py"]
RESULTS_DIR = "simulation_results"
BEST_PARAMS_FILE = "best_dynamic_params.json"
CURRENT_PARAMS_FILE = "current_parameters.json"
METRICS = [
    "Delivery Ratio", "Collisions", "Avg Latency",
    "Avg Scheduler Latency", "Throughput (beacons/sec)",
    "Avg Reaction Latency"
]

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
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 5, "fixed_buoy_count": 5, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 10, "fixed_buoy_count": 10, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 20, "fixed_buoy_count": 20, "duration": 150, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 5, "fixed_buoy_count": 25, "duration": 180, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 10, "fixed_buoy_count": 20, "duration": 180, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 180, "headless": True},
    {"world_width": 500, "world_height": 500, "mobile_buoy_count": 25, "fixed_buoy_count": 5, "duration": 180, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 5, "fixed_buoy_count": 5, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 10, "fixed_buoy_count": 10, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 20, "fixed_buoy_count": 20, "duration": 150, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 5, "fixed_buoy_count": 25, "duration": 180, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 10, "fixed_buoy_count": 20, "duration": 180, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 180, "headless": True},
    {"world_width": 800, "world_height": 800, "mobile_buoy_count": 25, "fixed_buoy_count": 5, "duration": 180, "headless": True},
]

def write_dynamic_config(params: dict):
    with open(CURRENT_PARAMS_FILE, "w") as f:
        json.dump(params, f)

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
    return {metric: pd.to_numeric(df[metric], errors="coerce").mean() for metric in METRICS if metric in df.columns}

def run_all_scenarios_for_mode(mode, params=None, seeds=None):
    procs = []
    max_duration = max(scenario["duration"] for scenario in BASE_PARAM_SETS)
    for i, scenario in enumerate(BASE_PARAM_SETS):
        if params:
            write_dynamic_config(params)
        seed = seeds[i] if seeds else int(random.uniform(1, 1e9))
        cmd = BASE_CMD + [
            "--mode", mode,
            "--seed", str(seed),
            "--world-width", str(scenario["world_width"]),
            "--world-height", str(scenario["world_height"]),
            "--mobile-buoy-count", str(scenario["mobile_buoy_count"]),
            "--fixed-buoy-count", str(scenario["fixed_buoy_count"]),
            "--duration", str(scenario["duration"]),
        ]
        if scenario.get("headless"):
            cmd.append("--headless")
        procs.append(subprocess.Popen(cmd))
        time.sleep(0.1)
    # Progress bar for the max duration
    with tqdm(total=max_duration, desc=f"Simulating {mode}", leave=False, unit="s") as pbar:
        for _ in range(max_duration):
            time.sleep(1)
            pbar.update(1)
    # Wait for all processes to finish (if any are still running)
    for proc in procs:
        proc.wait()

def main():
    # 1. Generate a fixed seed for each scenario (used for both static and dynamic)
    scenario_seeds = [int(random.uniform(1, 1e9)) for _ in BASE_PARAM_SETS]

    # 2. Run all static scenarios (only if not already present)
    static_csvs = glob.glob(os.path.join(RESULTS_DIR, "static_*.csv"))
    if static_csvs:
        print(f"Found {len(static_csvs)} static CSV files, skipping static simulation.")
    else:
        print("Running all static scenarios...")
        run_all_scenarios_for_mode("static", seeds=scenario_seeds)
    static_df = collect_metrics("static")
    static_scores = evaluate_metrics(static_df)

    # 3. For each parameter set, run all dynamic scenarios and evaluate
    keys, values = zip(*PARAM_SPACE.items())
    all_param_sets = [dict(zip(keys, combo)) for combo in product(*values)]
    print(f"Total parameter sets: {len(all_param_sets)}")

    # Metrics where lower is better
    LOWER_IS_BETTER = {"Collisions", "Avg Latency", "Avg Scheduler Latency", "Avg Reaction Latency", "Collision Rate"}

    best_per_metric = {m: (None, -float("inf")) for m in METRICS}

    for params in tqdm(all_param_sets, desc="Parameter search"):
        run_all_scenarios_for_mode("dynamic", params, seeds=scenario_seeds)
        dyn_df = collect_metrics("dynamic")
        dyn_scores = evaluate_metrics(dyn_df)
        improvements = {}
        for metric in METRICS:
            if metric in LOWER_IS_BETTER:
                improvement = static_scores.get(metric, 0.0) - dyn_scores.get(metric, 0.0)
            else:
                improvement = dyn_scores.get(metric, 0.0) - static_scores.get(metric, 0.0)
            improvements[metric] = improvement
        for metric, improvement in improvements.items():
            if improvement > best_per_metric[metric][1]:
                best_per_metric[metric] = (params, improvement)

    # 4. Save best params for each metric
    best_params = {metric: best_per_metric[metric][0] for metric in METRICS}
    with open(BEST_PARAMS_FILE, "w") as f:
        json.dump(best_params, f, indent=2)

    # 5. Delete current_parameters.json after training
    if os.path.exists(CURRENT_PARAMS_FILE):
        os.remove(CURRENT_PARAMS_FILE)

    print("Best configurations per metric (compared to static):")
    for metric, (params, improvement) in best_per_metric.items():
        print(f"{metric} improved by {improvement:.4f}")
        print(json.dumps(params, indent=2))
    print(f"Best parameter sets saved to {BEST_PARAMS_FILE}")

if __name__ == "__main__":
    main()