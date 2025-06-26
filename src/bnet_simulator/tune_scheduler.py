import os
import json
import pandas as pd
import subprocess
import glob
import time
import math
from itertools import product, islice
from tqdm import tqdm
from bnet_simulator.utils import config

def arrange_buoys_exact_density(world_width, world_height, neighbor_density, range_type="high_prob"):
    #if range_type == "max":
    #    comm_range = config.COMMUNICATION_RANGE_MAX
    #else:
    #    comm_range = config.COMMUNICATION_RANGE_HIGH_PROB
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
METRICS = [
    "Delivery Ratio"
]
PARAM_BATCH_SIZE = 4

PARAM_SPACE = {
    "MOTION_WEIGHT": [0.2],
    "DENSITY_WEIGHT": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
    "CONTACT_WEIGHT": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
    "SCORE_FUNCTION": ["linear"],
}

def collect_metrics(scheduler_type, results_dir):
    pattern = os.path.join(results_dir, f"{scheduler_type}_*.csv")
    metrics = []
    for file in glob.glob(pattern):
        df = pd.read_csv(file, index_col=0)
        row = df["Value"].to_dict()
        row["filename"] = os.path.basename(file)
        metrics.append(row)
    return pd.DataFrame(metrics)

def evaluate_metrics(df):
    return {"Delivery Ratio": pd.to_numeric(df["Delivery Ratio"], errors="coerce").mean() if "Delivery Ratio" in df.columns else float('nan')}

def batched(iterable, n):
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            break
        yield batch

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

def run_dynamic_batch(param_batch, batch_start_idx, scenario_seeds, results_dir, total_pbar=None):
    procs = []
    param_idx_offset = batch_start_idx
    for batch_param_idx, params in enumerate(param_batch):
        param_idx = param_idx_offset + batch_param_idx
        for scenario_idx, scenario in enumerate(BASE_PARAM_SETS):
            param_file = f"current_parameters_{scenario_idx}_{param_idx}.json"
            with open(param_file, "w") as f:
                json.dump(params, f)
            positions_file = f"positions_{scenario_idx}.json"
            with open(positions_file, "w") as f:
                json.dump(scenario["positions"], f)
            result_file = os.path.join(
                results_dir,
                f"dynamic_density{scenario['density']}_n{scenario['fixed_buoy_count']}_param{param_idx}.csv"
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
                "--headless",
                "--positions-file", positions_file,
                "--density", str(scenario["density"]),
            ]
            if IDEAL:
                cmd.append("--ideal")
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
    for batch_param_idx, params in enumerate(param_batch):
        param_idx = param_idx_offset + batch_param_idx
        for scenario_idx, scenario in enumerate(BASE_PARAM_SETS):
            param_file = f"current_parameters_{scenario_idx}_{param_idx}.json"
            if os.path.exists(param_file):
                os.remove(param_file)
            positions_file = f"positions_{scenario_idx}.json"
            if os.path.exists(positions_file):
                os.remove(positions_file)

def results_exist(results_dir, prefix):
    """Check if at least one result CSV exists for a given scheduler type."""
    return bool(glob.glob(os.path.join(results_dir, f"{prefix}_*.csv")))

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ideal",
        action='store_true',
        help="Use ideal channel conditions (no loss)"
    )
    args = parser.parse_args()
    global IDEAL
    IDEAL = args.ideal

    RESULTS_DIR = os.path.join("metrics", f"tune_results{'_ideal' if IDEAL else ''}")
    PLOTS_DIR = os.path.join("metrics", f"tune_plots{'_ideal' if IDEAL else ''}")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)

    global BASE_PARAM_SETS
    BASE_PARAM_SETS = generate_density_scenarios(
        densities=range(2, 11), duration=180, headless=True, world_width=300, world_height=300
    )

    scenario_seeds = [int(time.time()) + i for i in range(len(BASE_PARAM_SETS))]

    # --- STATIC ---
    if results_exist(RESULTS_DIR, "static"):
        print("Found static CSV files, skipping static simulation.")
    else:
        print("Running all static scenarios...")
        run_static_scenarios(scenario_seeds, RESULTS_DIR)
        print("Static batch complete.")

    # --- DYNAMIC ---
    if results_exist(RESULTS_DIR, "dynamic"):
        print("Found dynamic CSV files, skipping dynamic simulation.")
    else:
        print("Running dynamic batch...")
        keys, values = zip(*PARAM_SPACE.items())
        all_param_sets = [dict(zip(keys, combo)) for combo in product(*values)]
        print(f"Total parameter sets: {len(all_param_sets)}")
        print(f"Running dynamic scenarios in batches of {PARAM_BATCH_SIZE}...")

        total_jobs = len(all_param_sets) * len(BASE_PARAM_SETS)
        with tqdm(total=total_jobs, desc="TOTAL dynamic tuning progress", position=0, unit="sim") as total_pbar:
            for batch_start_idx, param_batch in enumerate(batched(all_param_sets, PARAM_BATCH_SIZE)):
                run_dynamic_batch(param_batch, batch_start_idx * PARAM_BATCH_SIZE, scenario_seeds, RESULTS_DIR, total_pbar=total_pbar)

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

        best_params_file = os.path.join("metrics", f"best_dynamic_params{'_ideal' if IDEAL else ''}.json")
        with open(best_params_file, "w") as f:
            json.dump({
                "Delivery Ratio": best_params,
                "Best Delivery Ratio Value": best_delivery_ratio
            }, f, indent=2)

        print("Best parameters for Delivery Ratio:")
        print(json.dumps(best_params, indent=2))
        print(f"Best parameter set saved to {best_params_file}")

    print("Plotting tuning results...")
    subprocess.run([
        "uv", "run", "python", "src/bnet_simulator/plot_metrics.py",
        "--results-dir", RESULTS_DIR,
        "--plot-dir", PLOTS_DIR
    ])
    print("All batches complete.")

if __name__ == "__main__":
    main()