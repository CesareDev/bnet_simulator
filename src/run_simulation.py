import os
import json
import subprocess
import time
import math
import random

IDEAL = True # Use ideal channel conditions (no loss)

DENSITIES = [5, 10, 20] # Buoy densities to simulate
INTERVALS = [0.25, 0.5] # Static scheduler intervals to test
DURATION = 500 # Simulation duration in seconds
RANDOM_POS = False # Use random buoy positions instead of density-based

RAMP = False # Use ramp scenario (buoy count increases over time)
TOTAL_BUOY = 30 # Maximum number of buoys for ramp scenario

WORLD_WIDTH = 800 # World width
WORLD_HEIGHT = 800 # World height
HEADLESS = True # Run without GUI

def arrange_buoys_for_density(density):
    # Determine communication range based on ideal setting
    comm_range = 70 * 0.9 if IDEAL else 100 * 0.9
    
    # Calculate parameters for positioning
    n_buoys = density + 1
    area_radius = comm_range * (1.5 - (0.5 * density / 30))
    area_radius = max(comm_range * 0.5, min(comm_range, area_radius))
    center_x = WORLD_WIDTH / 2
    center_y = WORLD_HEIGHT / 2
    
    # Generate positions
    positions = []
    random.seed(time.time())
    for i in range(n_buoys):
        angle = random.uniform(0, 2 * math.pi)
        distance = math.sqrt(random.random()) * area_radius
        x = center_x + distance * math.cos(angle)
        y = center_y + distance * math.sin(angle)
        x = max(10, min(WORLD_WIDTH - 10, x))
        y = max(10, min(WORLD_HEIGHT - 10, y))
        positions.append((x, y))
    return positions

def arrange_buoys_randomly(n_buoys):
    positions = []
    random.seed(time.time())
    for _ in range(n_buoys):
        x = random.uniform(10, WORLD_WIDTH - 10)
        y = random.uniform(10, WORLD_HEIGHT - 10)
        positions.append((x, y))
    return positions

def run_simulation(mode, interval, density, positions, results_dir):
    # Create positions file
    positions_file = f"positions_{mode}_{density}.json"
    with open(positions_file, "w") as f:
        json.dump(positions, f)
    
    # Create result file path
    if RAMP:
        result_file = os.path.join(results_dir, f"{mode}_ramp_timeseries.csv")
    else:
        result_file = os.path.join(results_dir, f"{mode}_density{density}.csv")
    
    # Build command
    cmd = ["uv", "run", "src/init.py",
           "--mode", mode,
           "--seed", str(int(time.time())),
           "--world-width", str(WORLD_WIDTH),
           "--world-height", str(WORLD_HEIGHT),
           "--mobile-buoy-count", "0",
           "--fixed-buoy-count", str(len(positions)),
           "--duration", str(DURATION),
           "--result-file", result_file,
           "--positions-file", positions_file,
           "--density", str(density),
           "--static-interval", str(interval)]
    
    if HEADLESS:
        cmd.append("--headless")
    if RAMP:
        cmd.append("--ramp")
    if IDEAL:
        cmd.append("--ideal")
    
    # Run simulation
    print(f"Running {mode} simulation with interval={interval}s...")
    subprocess.run(cmd)
    
    # Clean up
    if os.path.exists(positions_file):
        os.remove(positions_file)

def plot_results(results_dir, plots_dir, interval):
    plot_cmd = ["uv", "run", "src/plot_metrics.py",
                "--results-dir", results_dir,
                "--plot-dir", plots_dir,
                "--interval", str(interval)]
    subprocess.run(plot_cmd)

def main():
    # Process each interval
    for interval in INTERVALS:
        # Create directories
        interval_str = str(int(interval * 10))
        ideal_suffix = "_ideal" if IDEAL else ""
        ramp_suffix = "_ramp" if RAMP else ""
        
        results_dir = os.path.join("metrics", f"results_interval{interval_str}{ideal_suffix}{ramp_suffix}")
        plots_dir = os.path.join("metrics", f"plots_interval{interval_str}{ideal_suffix}{ramp_suffix}")
        
        os.makedirs(results_dir, exist_ok=True)
        os.makedirs(plots_dir, exist_ok=True)
        
        print(f"Running simulations with interval = {interval}s")
        
        if RAMP:
            # For ramp scenario, we only need one density
            if RANDOM_POS:
                positions = arrange_buoys_randomly(TOTAL_BUOY - 1)
            else:
                positions = arrange_buoys_for_density(TOTAL_BUOY - 1)
            run_simulation("static", interval, TOTAL_BUOY - 1, positions, results_dir)
            run_simulation("dynamic", interval, TOTAL_BUOY - 1, positions, results_dir)
        else:
            # For density sweep, run each density
            for density in DENSITIES:
                if RANDOM_POS:
                    positions = arrange_buoys_randomly(density)
                else:
                    positions = arrange_buoys_for_density(density)
                run_simulation("static", interval, density, positions, results_dir)
                run_simulation("dynamic", interval, density, positions, results_dir)
        
        # Plot results
        print(f"Plotting results for interval = {interval}s")
        plot_results(results_dir, plots_dir, interval)
        
    print("\nAll simulations complete!")
    print("Check the metrics directory for results and plots.")

if __name__ == "__main__":
    main()