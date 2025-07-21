import os
import subprocess

# Define intervals to test
INTERVALS = [1.0]
# Whether to use ideal channel
IDEAL = True

def main():
    for interval in INTERVALS:
        print(f"Running simulations with static interval = {interval}s")
        
        # Run tune_scheduler.py with the current interval
        cmd = [
            "uv", "run", "python", "src/bnet_simulator/tune_scheduler.py",
            "--static-interval", str(interval)
        ]
        
        if IDEAL:
            cmd.append("--ideal")
            
        # This will run simulations and create plots in their own directories
        subprocess.run(cmd)
        
        # Get directory names for results and plots
        results_dir = os.path.join("metrics", f"tune_results_interval{int(interval)}" + ("_ideal" if IDEAL else ""))
        plots_dir = os.path.join("metrics", f"tune_plots_interval{int(interval)}" + ("_ideal" if IDEAL else ""))
        
        print(f"Completed scenario with interval = {interval}s")
        print(f"Results saved to {results_dir}")
        print(f"Plots saved to {plots_dir}")
        
    print("\nAll simulations complete!")

    subprocess.run(["notify-send", "-e", "BNet Simulator", "All simulations complete! Check metrics directory for results."])

if __name__ == "__main__":
    main()