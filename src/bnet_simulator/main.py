from bnet_simulator.core.simulator import Simulator
from bnet_simulator.core.channel import Channel
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.utils import config
import random
import time

def random_position():
    return (
        random.uniform(0, config.WORLD_WIDTH),
        random.uniform(0, config.WORLD_HEIGHT)
    )

def random_velocity():
    return (
        random.uniform(-1, 1) * config.DEFAULT_VELOCITY,
        random.uniform(-1, 1) * config.DEFAULT_VELOCITY
    )

def main():
    random.seed(time.time())    

    # Instantiate a channel
    channel = Channel()

    # Instantiate 3 buoys
    buoys = [
        Buoy(channel=channel, position=random_position(), is_mobile=False),
        Buoy(channel=channel, position=random_position(), is_mobile=False),
        Buoy(channel=channel, position=random_position(), is_mobile=False),
        Buoy(channel=channel, position=random_position(), is_mobile=True, velocity=random_velocity()),
        Buoy(channel=channel, position=random_position(), is_mobile=True, velocity=random_velocity()),
        Buoy(channel=channel, position=random_position(), is_mobile=True, velocity=random_velocity()),
    ]

    # Create a simulator instance
    sim = Simulator(buoys, channel)

    # Start the simulation (simulation time is defined in the config file)
    sim.start()

if __name__ == "__main__":
    main()