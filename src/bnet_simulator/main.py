from bnet_simulator.core import simulator

def main():
    # Instantiate 3 buoys
    buoys = [
        simulator.Buoy(),
        simulator.Buoy(),
        simulator.Buoy()
    ]

    # Create a simulator instance
    sim = simulator.Simulator(buoys=buoys)

    # Log the initial state of the buoys
    sim.log_buoys()

    # Start the simulation (simulation time is defined in the config file)
    sim.start()

if __name__ == "__main__":
    main()