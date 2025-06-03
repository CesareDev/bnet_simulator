import subprocess
import time

def main_wrapper():
    shared_seed = time.time()
    static_proc = subprocess.Popen(
        ["uv", "run", "static", "--seed", str(shared_seed)]
    )
    dynamic_proc = subprocess.Popen(
        ["uv", "run", "dynamic", "--seed", str(shared_seed)]
    )

    static_proc.wait()
    dynamic_proc.wait()
