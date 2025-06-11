import random
import math
import uuid
import json
import os
import sys
from typing import Tuple, List
from bnet_simulator.utils import config

class BeaconScheduler:
    def __init__(self, min_interval: float = config.BEACON_MIN_INTERVAL, max_interval: float = config.BEACON_MAX_INTERVAL):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.elapsed_time = 0.0
        self.next_static_interval = random.uniform(self.min_interval, self.max_interval)
        self.next_dynamic_interval = None

        # Load dynamic parameters from file if in dynamic mode
        if config.SCHEDULER_TYPE == "dynamic":
            # Look for --param-file argument in sys.argv
            param_file = None
            for i, arg in enumerate(sys.argv):
                if arg == "--param-file" and i + 1 < len(sys.argv):
                    param_file = sys.argv[i + 1]
                    break
            if param_file and os.path.exists(param_file):
                with open(param_file, "r") as f:
                    params = json.load(f)
                config.MOTION_WEIGHT = params["MOTION_WEIGHT"]
                config.DENSITY_WEIGHT = params["DENSITY_WEIGHT"]
                config.CONTACT_WEIGHT = params["CONTACT_WEIGHT"]
                config.CONGESTION_WEIGHT = params["CONGESTION_WEIGHT"]
                config.DENSITY_MIDPOINT = params["DENSITY_MIDPOINT"]
                config.DENSITY_ALPHA = params["DENSITY_ALPHA"]
                config.CONTACT_MIDPOINT = params["CONTACT_MIDPOINT"]
                config.CONTACT_ALPHA = params["CONTACT_ALPHA"]

    def tick(self, dt: float):
        self.elapsed_time += dt

    def should_send(self, battery, velocity, neighbors, current_time, collision_rate=0.0):
        if config.SCHEDULER_TYPE == "static":
            return self.should_send_static()
        elif config.SCHEDULER_TYPE == "dynamic":
            return self.should_send_dynamic(battery, velocity, neighbors, current_time, collision_rate)
        elif config.SCHEDULER_TYPE == "rl":
            raise ValueError("RL scheduler not yet implemented.")
        else:
            raise ValueError(f"Unknown scheduler type: {config.SCHEDULER_TYPE}")

    def should_send_static(self) -> bool:
        if self.elapsed_time >= self.next_static_interval:
            self.elapsed_time = 0.0
            self.next_static_interval = random.uniform(self.min_interval, self.max_interval)
            return True
        return False

    def should_send_dynamic(
        self,
        battery,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
        collision_rate=0.0
    ) -> bool:

        if self.next_dynamic_interval is None:
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time, collision_rate)

        if self.elapsed_time >= self.next_dynamic_interval:
            self.elapsed_time = 0.0
            self.next_dynamic_interval = None
            return True

        return False

    def score(value, midpoint, alpha, mode):
        if mode == "sigmoid":
            return 1 / (1 + math.exp(-alpha * (value - midpoint)))
        elif mode == "tanh":
            return 0.5 * (1 + math.tanh(alpha * (value - midpoint)))
        elif mode == "linear":
            # For density: value = num_neighbors, for contact: value = delta
            # Linear scaling between 0 and 1, centered at midpoint
            return max(0.0, min((value / midpoint), 1.0))
        else:
            raise ValueError(f"Unknown score function: {mode}")

    def compute_interval(
        self,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
        collision_rate: float = 0.0
    ) -> float:
        # --- Motion Score ---
        speed = math.hypot(*velocity)
        motion_score = min(speed / config.DEFAULT_BUOY_VELOCITY, 1.0)

        # --- Density Score ---
        num_neighbors = len(neighbors)
        density_score = self.score(
            num_neighbors,
            config.DENSITY_MIDPOINT,
            config.DENSITY_ALPHA,
            config.SCORE_FUNCTION
        )

        # --- Contact Score ---
        if not neighbors:
            contact_score = 1.0
        else:
            last_contact = max((ts for _, ts, _ in neighbors), default=0.0)
            delta = current_time - last_contact
            contact_score = self.score(
                delta,
                config.CONTACT_MIDPOINT,
                config.CONTACT_ALPHA,
                config.SCORE_FUNCTION
            )

        # --- Congestion Score ---
        congestion_score = min(collision_rate, 1.0)

        # --- Composite (linear blend) ---
        k = (
            config.MOTION_WEIGHT * motion_score +
            config.DENSITY_WEIGHT * density_score +
            config.CONTACT_WEIGHT * contact_score +
            config.CONGESTION_WEIGHT * (1 - congestion_score)
        )

        interval = self.min_interval + (1 - k) * (self.max_interval - self.min_interval)
        return max(self.min_interval, min(interval, self.max_interval))