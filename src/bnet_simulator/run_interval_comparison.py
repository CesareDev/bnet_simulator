import os
import subprocess

# Define intervals to test
INTERVALS = [0.1]
# Whether to use ideal channel
IDEAL = True
# Whether to run vessel scenario
VESSEL = False

def main():
    print("Running scenarios with multiple static intervals...")
    
    for interval in INTERVALS:
        print(f"\nRunning simulations with static interval = {interval}s")
        
        # Run tune_scheduler.py with the current interval
        cmd = [
            "uv", "run", "python", "src/bnet_simulator/tune_scheduler.py",
            "--static-interval", str(interval)
        ]
        
        if IDEAL:
            cmd.append("--ideal")
        if VESSEL:
            cmd.append("--vessel")
            
        # This will run simulations and create plots in their own directories
        subprocess.run(cmd)
        
        # Get directory names for results and plots
        if VESSEL:
            results_dir = os.path.join("metrics", f"vessel_results_interval{int(interval)}" + ("_ideal" if IDEAL else ""))
            plots_dir = os.path.join("metrics", f"vessel_plots_interval{int(interval)}" + ("_ideal" if IDEAL else ""))
        else:
            results_dir = os.path.join("metrics", f"tune_results_interval{int(interval)}" + ("_ideal" if IDEAL else ""))
            plots_dir = os.path.join("metrics", f"tune_plots_interval{int(interval)}" + ("_ideal" if IDEAL else ""))
        
        print(f"Completed scenario with interval = {interval}s")
        print(f"Results saved to {results_dir}")
        print(f"Plots saved to {plots_dir}")
        
    print("\nAll simulations complete!")

if __name__ == "__main__":
    main()