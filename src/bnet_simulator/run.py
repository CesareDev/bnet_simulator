import os
import subprocess

# Define intervals to test
INTERVALS = [0.25]

# Whether to use ideal channel
IDEAL = True

# Increasing scenario
RAMP = True

def main():
    for interval in INTERVALS:
        print(f"Running simulations with static interval = {interval}s")
        
        cmd = [
            "uv", "run", "python", "src/bnet_simulator/test_scheduler.py",
            "--static-interval", str(interval)
        ]
        
        if IDEAL:
            cmd.append("--ideal")
        if RAMP:
            cmd.append("--ramp")
            
        subprocess.run(cmd)
        
        interval_str = str(int(interval * 10))
        ideal_suffix = "_ideal" if IDEAL else ""
        ramp_suffix = "_ramp" if RAMP else ""
        
        results_dir = os.path.join("metrics", f"test_results_interval{interval_str}{ideal_suffix}{ramp_suffix}")
        plots_dir = os.path.join("metrics", f"test_plots_interval{interval_str}{ideal_suffix}{ramp_suffix}")
        
        print(f"Completed scenario with interval = {interval}s")
        print(f"Results saved to {results_dir}")
        print(f"Plots saved to {plots_dir}")
        
    print("\nAll simulations complete!")

    subprocess.run(["notify-send", "-e", "BNet Simulator", "All simulations complete! Check metrics directory for results."])

if __name__ == "__main__":
    main()