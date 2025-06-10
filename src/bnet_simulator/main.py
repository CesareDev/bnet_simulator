import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

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
    parser.add_argument(
        "--world-width",
        type=float,
        default=config.WORLD_WIDTH,
        help="Width of the simulation world (default: from config)")
    parser.add_argument(
        "--world-height",
        type=float,
        default=config.WORLD_HEIGHT,
        help="Height of the simulation world (default: from config)")
    parser.add_argument(
        "--mobile-buoy-count",
        type=int,
        default=config.MOBILE_BUOY_COUNT,
        help="Number of mobile buoys (default: from config)")
    parser.add_argument(
        "--fixed-buoy-count",
        type=int,
        default=config.FIXED_BUOY_COUNT,
        help="Number of fixed buoys (default: from config)"),
    parser.add_argument(
        "--headless",
        action='store_true',
        help="Run in headless mode without GUI (default: False)"
    )
    

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
    config.WORLD_WIDTH = args.world_width
    config.WORLD_HEIGHT = args.world_height
    config.MOBILE_BUOY_COUNT = args.mobile_buoy_count
    config.FIXED_BUOY_COUNT = args.fixed_buoy_count
    config.SEED = args.seed
    config.HEADLESS = args.headless

    if args.seed is not None:
        random.seed(args.seed)
    else:
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

    summary = metrics.summary(sim.simulated_time) if metrics else None

    # Export metrics to CSV
    if metrics: 
        metrics.export_metrics_to_csv(summary)

if __name__ == "__main__":
    main()