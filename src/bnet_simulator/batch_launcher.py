import subprocess
import time

def main():

    base_param_sets = [
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

    modes = ["static", "dynamic"]

    procs = []
    for base_params in base_param_sets:
        seed = time.time()
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
        time.sleep(0.1)  # ensure different seeds

    # Wait for all processes to complete
    for proc in procs:
        proc.wait()


if __name__ == "__main__":
    main()