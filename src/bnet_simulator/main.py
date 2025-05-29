from bnet_simulator.core.simulator import Simulator
from bnet_simulator.core.channel import Channel
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.utils import config
from bnet_simulator.utils.metrics import Metrics
import random
import time

def random_position():
    return (
        random.uniform(0, config.WORLD_WIDTH),
        random.uniform(0, config.WORLD_HEIGHT)
    )

def random_velocity():
    return (
        random.uniform(-1, 1) * config.DEFAULT_BUOY_VELOCITY,
        random.uniform(-1, 1) * config.DEFAULT_BUOY_VELOCITY
    )

def main():
    random.seed(time.time())

    # Instantiate metrics if enabled in the config
    if config.ENABLE_METRICS:
        metrics = Metrics()
    else:
        metrics = None

    # Instantiate a channel
    channel = Channel(metrics=metrics)

    # Instantiate the buoys
    mobile_buoys = [
        Buoy(
            channel=channel,
            position=random_position(),
            is_mobile=True,
            battery=config.DEFAULT_BATTERY,
            velocity=random_velocity(),
            metrics=metrics) for _ in range(config.MOBILE_BUOY_COUNT)]
    static_buoys = [
        Buoy(
            channel=channel,
            position=random_position(),
            is_mobile=False,
            battery=config.DEFAULT_BATTERY,
            metrics=metrics
        ) for _ in range(config.FIXED_BUOY_COUNT)
    ]

    buoys = mobile_buoys + static_buoys

    # Create a simulator instance
    sim = Simulator(buoys, channel)

    # Start the simulation (simulation time is defined in the config file)
    sim.start()

    summary = metrics.summary(sim.simulated_time)

    # Export metrics to CSV
    if metrics: metrics.export_metrics_to_csv(summary, filename="simulation_metrics.csv")

if __name__ == "__main__":
    main()