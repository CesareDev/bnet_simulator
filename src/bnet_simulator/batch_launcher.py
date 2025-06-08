import subprocess
import time

def main():

    # 500x500 area with increasing total buoy count
    density_variants = [
        {"world_width": 500, "world_height": 500, "mobile_buoy_count": 5, "fixed_buoy_count": 5, "duration": 150, "headless": True},
        {"world_width": 500, "world_height": 500, "mobile_buoy_count": 10, "fixed_buoy_count": 10, "duration": 150, "headless": True},
        {"world_width": 500, "world_height": 500, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 150, "headless": True},
        {"world_width": 500, "world_height": 500, "mobile_buoy_count": 20, "fixed_buoy_count": 20, "duration": 150, "headless": True},
    ]

    # 30 buoys total in 800x800, different mobile/fixed splits
    mobility_variants = [
        {"world_width": 800, "world_height": 800, "mobile_buoy_count": 5, "fixed_buoy_count": 25, "duration": 180, "headless": True},
        {"world_width": 800, "world_height": 800, "mobile_buoy_count": 10, "fixed_buoy_count": 20, "duration": 180, "headless": True},
        {"world_width": 800, "world_height": 800, "mobile_buoy_count": 15, "fixed_buoy_count": 15, "duration": 180, "headless": True},
        {"world_width": 800, "world_height": 800, "mobile_buoy_count": 25, "fixed_buoy_count": 5, "duration": 180, "headless": True},
    ]

    scale_variants = [
        {"world_width": 400, "world_height": 400, "mobile_buoy_count": 10, "fixed_buoy_count": 10, "duration": 120, "headless": True},
        {"world_width": 800, "world_height": 800, "mobile_buoy_count": 20, "fixed_buoy_count": 20, "duration": 180, "headless": True},
        {"world_width": 1200, "world_height": 1200, "mobile_buoy_count": 30, "fixed_buoy_count": 30, "duration": 240, "headless": True},
    ]

    base_param_sets = density_variants + mobility_variants + scale_variants

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