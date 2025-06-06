import subprocess
import time

def main():
    base_param_sets = [
        {"world_width": 400, "world_height": 400, "mobile_buoy_count": 5, "fixed_buoy_count": 5, "duration": 120, "headless": True},
        {"world_width": 700, "world_height": 700, "mobile_buoy_count": 10, "fixed_buoy_count": 10, "duration": 180, "headless": True},
        {"world_width": 1000, "world_height": 1000, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 240, "headless": True},
        {"world_width": 1300, "world_height": 1300, "mobile_buoy_count": 20, "fixed_buoy_count": 20, "duration": 300, "headless": True},
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
                "--duration", str(base_params["duration"]),
            ]
            if base_params.get("headless"):
                cmd.append("--headless")
            print("Launching:", " ".join(cmd))
            procs.append(subprocess.Popen(cmd))
        # Wait for both simulations to finish before starting the next configuration
        for proc in procs:
            proc.wait()
        # Optional: small sleep to ensure unique seeds if running very fast
        time.sleep(0.1)

if __name__ == "__main__":
    main()