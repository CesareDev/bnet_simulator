import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from bnet_simulator.core.simulator import Simulator
from bnet_simulator.core.channel import Channel
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.buoys.vessel import Vessel  # Import the new Vessel class
from bnet_simulator.utils import config
from bnet_simulator.utils.metrics import Metrics
import random
import time
import argparse
import json
import math

def parse_args():
    parser = argparse.ArgumentParser(description="Run the BNet Simulator")
    parser.add_argument(
        "--mode",
        choices=["static", "dynamic", "auto"],
        default=config.SCHEDULER_TYPE,
        help="Scheduler mode to use for the simulation (default: static)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=config.SIMULATION_DURATION,
        help="Duration of the simulation in seconds (default: 60.0)"
    )
    parser.add_argument(
        "--seed",
        type=float,
        default=None,
        help="Random seed for reproducibility (default: None, uses current time)"
    )
    parser.add_argument(
        "--world-width",
        type=float,
        default=config.WORLD_WIDTH,
        help="Width of the simulation world (default: from config)"
    )
    parser.add_argument(
        "--world-height",
        type=float,
        default=config.WORLD_HEIGHT,
        help="Height of the simulation world (default: from config)"
    )
    parser.add_argument(
        "--mobile-buoy-count",
        type=int,
        default=config.MOBILE_BUOY_COUNT,
        help="Number of mobile buoys (default: from config)"
    )
    parser.add_argument(
        "--fixed-buoy-count",
        type=int,
        default=config.FIXED_BUOY_COUNT,
        help="Number of fixed buoys (default: from config)"
    )
    parser.add_argument(
        "--headless",
        action='store_true',
        help="Run in headless mode without GUI (default: False)"
    )
    parser.add_argument(
        "--result-file",
        type=str,
        default=None,
        help="Filename for metrics CSV output"
    )
    parser.add_argument(
        "--positions-file",
        type=str,
        default=None,
        help="Path to a file with buoy positions (optional)"
    )
    parser.add_argument(
        "--density",
        type=float,
        default=None,
        help="Density value for this scenario (optional)"
    )
    parser.add_argument(
        "--ideal",
        action='store_true',
        help="Use ideal channel conditions (no loss)"
    )
    parser.add_argument(
        "--vessel-index",
        type=int,
        default=None,
        help="Index of the buoy to convert to a vessel (listening-only)"
    )
    parser.add_argument(
        "--static-interval",
        type=float,
        default=config.STATIC_INTERVAL,
        help="Interval for static scheduler in seconds (default: 1.0)"
    )
    return parser.parse_args()

def random_position():
    # Place all buoys randomly within a small circle at the center of the world
    center_x = config.WORLD_WIDTH / 2
    center_y = config.WORLD_HEIGHT / 2
    # Use a radius smaller than the communication range to ensure all are in range
    max_radius = min(getattr(config, "COMMUNICATION_RANGE_HIGH_PROB", 70), config.WORLD_WIDTH, config.WORLD_HEIGHT) / 2.5
    angle = random.uniform(0, 2 * 3.1415926535)
    radius = random.uniform(0, max_radius)
    return (
        center_x + radius * math.cos(angle),
        center_y + radius * math.sin(angle)
    )

def random_velocity():
    return (
        random.uniform(-1, 1) * config.DEFAULT_BUOY_VELOCITY,
        random.uniform(-1, 1) * config.DEFAULT_BUOY_VELOCITY
    )

def compute_average_density(positions, comm_range):
    densities = []
    for i, (x0, y0) in enumerate(positions):
        count = 0
        for j, (x1, y1) in enumerate(positions):
            if i != j:
                dx = x0 - x1
                dy = y0 - y1
                if math.hypot(dx, dy) <= comm_range:
                    count += 1
        densities.append(count)
    avg_density = sum(densities) / len(densities)
    return math.ceil(avg_density)

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
    config.IDEAL_CHANNEL = args.ideal
    config.STATIC_INTERVAL = args.static_interval  # Add this line

    if args.seed is not None:
        random.seed(args.seed)
    else:
        random.seed(time.time())

    positions = None
    if args.positions_file:
        with open(args.positions_file, "r") as f:
            positions = json.load(f)

    # Instantiate metrics, pass density
    if config.ENABLE_METRICS:
        metrics = Metrics(density=args.density)
    else:
        metrics = None

    # Instantiate a channel
    channel = Channel(metrics=metrics)

    # Instantiate the buoys
    mobile_buoys = []
    for i in range(config.MOBILE_BUOY_COUNT):
        if args.vessel_index is not None and i == args.vessel_index:
            vessel = Vessel(
                channel=channel,
                position=random_position(),
                is_mobile=True,
                battery=config.DEFAULT_BATTERY,
                velocity=random_velocity(),
                metrics=metrics
            )
            mobile_buoys.append(vessel)
            # Set vessel ID in metrics
            if metrics:
                metrics.vessel_id = vessel.id
        else:
            mobile_buoys.append(
                Buoy(
                    channel=channel,
                    position=random_position(),
                    is_mobile=True,
                    battery=config.DEFAULT_BATTERY,
                    velocity=random_velocity(),
                    metrics=metrics
                )
            )
            
    static_buoys = []
    for i in range(config.FIXED_BUOY_COUNT):
        pos = positions[i] if positions else random_position()
        if args.vessel_index is not None and i + config.MOBILE_BUOY_COUNT == args.vessel_index:
            vessel = Vessel(
                channel=channel,
                position=pos,
                is_mobile=False,
                battery=config.DEFAULT_BATTERY,
                metrics=metrics
            )
            static_buoys.append(vessel)
            # Set vessel ID in metrics
            if metrics:
                metrics.vessel_id = vessel.id
        else:
            static_buoys.append(
                Buoy(
                    channel=channel,
                    position=pos,
                    is_mobile=False,
                    battery=config.DEFAULT_BATTERY,
                    metrics=metrics
                )
            )

    buoys = mobile_buoys + static_buoys

    channel.set_buoys(buoys)

    # Create a simulator instance
    sim = Simulator(buoys, channel)

    # Start the simulation (simulation time is defined in the config file)
    sim.start()

    summary = metrics.summary(sim.simulated_time) if metrics else None

    # Export metrics to CSV
    if metrics:
        metrics.export_metrics_to_csv(summary, filename=args.result_file)

    # Compute and print the measured density
    # positions = [buoy.position for buoy in static_buoys]
    # comm_range = config.COMMUNICATION_RANGE_HIGH_PROB
    # measured_density = compute_average_density(positions, comm_range)
    # print(f"Measured density: {measured_density}")

if __name__ == "__main__":
    main()