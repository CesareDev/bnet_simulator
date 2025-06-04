import subprocess
import time

def main():
    base_param_sets = [
        {"world_width": 200, "world_height": 200, "mobile_buoy_count": 5, "fixed_buoy_count": 5},
        {"world_width": 300, "world_height": 300, "mobile_buoy_count": 10, "fixed_buoy_count": 10},
        # Here you can add more configurations
    ]

    modes = ["static", "dynamic"]

    for base_params in base_param_sets:
        seed = time.time()
        procs = []
        for mode in modes:
            cmd = [
                "uv", "run", "python", "src/bnet_simulator/main.py",
                "--mode", mode,
                "--seed", str(seed),
                "--world-width", str(base_params["world_width"]),
                "--world-height", str(base_params["world_height"]),
                "--mobile-buoy-count", str(base_params["mobile_buoy_count"]),
                "--fixed-buoy-count", str(base_params["fixed_buoy_count"]),
            ]
            print("Launching:", " ".join(cmd))
            procs.append(subprocess.Popen(cmd))
        # Wait for both simulations to finish before starting the next configuration
        for proc in procs:
            proc.wait()
        # Optional: small sleep to ensure unique seeds if running very fast
        time.sleep(0.1)

if __name__ == "__main__":
    main()