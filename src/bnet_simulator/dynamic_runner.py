from bnet_simulator.main import main
import sys

def main_wrapper():
    if "--seed" in sys.argv:
        seed_index = sys.argv.index("--seed") + 1
        seed = sys.argv[seed_index]
    sys.argv = ["sim", "--mode", "dynamic", "--seed", seed]
    main()
