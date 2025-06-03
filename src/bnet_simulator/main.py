from bnet_simulator.core.simulator import Simulator
from bnet_simulator.core.channel import Channel
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.utils import config
from bnet_simulator.utils.metrics import Metrics
import random
import time
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Run the BNet Simulator")
    parser.add_argument(
        "--mode",
        choices=["static", "dynamic", "rl"],
        default=config.SCHEDULER_TYPE,
        help="Scheduler mode to use for the simulation (default: static)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=config.SIMULATION_DURATION,
        help="Duration of the simulation in seconds (default: 60.0)")
    parser.add_argument(
        "--seed",
        type=float,
        default=None,
        help="Random seed for reproducibility (default: None, uses current time)")
    return parser.parse_args()

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
    # Parse command line arguments
    args = parse_args()
    config.SCHEDULER_TYPE = args.mode
    config.SIMULATION_DURATION = args.duration
    
    if args.seed is not None:
        random.seed(args.seed)
    else:
        random.seed(time.time())

    print(args.seed)

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
    if metrics: 
        metrics.export_metrics_to_csv(summary, filename="simulation_metrics.csv")

if __name__ == "__main__":
    main()