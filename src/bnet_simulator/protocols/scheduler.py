import random
import math
import uuid
import json
import os
import sys
from typing import Tuple, List
from bnet_simulator.utils import config

class BeaconScheduler:
    def __init__(
        self,
        min_interval: float = config.BEACON_MIN_INTERVAL,
        max_interval: float = config.BEACON_MAX_INTERVAL,
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.elapsed_time = 0.0
        self.next_static_interval = random.uniform(self.min_interval, self.max_interval)
        self.next_dynamic_interval = None

        # For adaptive normalization (EMA)
        self.density_ema = 5.0
        self.contact_ema = 5.0
        self.ema_alpha = 0.1

        # For auto-tuning weights (start equal)
        self.density_weight = 0.5
        self.contact_weight = 0.5

        # For auto-tuning alphas (auto mode only)
        self.density_alpha = 0.1
        self.contact_alpha = 0.1

        # For tracking previous scores (for weight/alpha adaptation)
        self.prev_density_score = None
        self.prev_contact_score = None

        # Load dynamic parameters from file if in dynamic mode (for legacy, but not used for midpoints now)
        if config.SCHEDULER_TYPE == "dynamic":
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
                # config.DENSITY_MIDPOINT = params["DENSITY_MIDPOINT"]  # Not used
                # config.DENSITY_ALPHA = params["DENSITY_ALPHA"]        # Not used
                # config.CONTACT_MIDPOINT = params["CONTACT_MIDPOINT"]  # Not used
                # config.CONTACT_ALPHA = params["CONTACT_ALPHA"]        # Not used

    def tick(self, dt: float):
        self.elapsed_time += dt

    def should_send(self, battery, velocity, neighbors, current_time):
        if config.SCHEDULER_TYPE == "static":
            return self.should_send_static()
        elif config.SCHEDULER_TYPE == "dynamic":
            return self.should_send_dynamic(battery, velocity, neighbors, current_time)
        elif config.SCHEDULER_TYPE == "auto":
            return self.should_send_auto(battery, velocity, neighbors, current_time)
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
    ) -> bool:
        if self.next_dynamic_interval is None:
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time)
        if self.elapsed_time >= self.next_dynamic_interval:
            self.elapsed_time = 0.0
            self.next_dynamic_interval = None
            return True
        return False

    def score(self, value, norm, mode):
        if mode == "sigmoid":
            # Use norm as midpoint, alpha fixed
            alpha = 1.0
            return 1 / (1 + math.exp(-alpha * (value - norm)))
        elif mode == "tanh":
            alpha = 1.0
            return 0.5 * (1 + math.tanh(alpha * (value - norm)))
        elif mode == "linear":
            return max(0.0, min((value / max(norm, 1.0)), 1.0))
        else:
            raise ValueError(f"Unknown score function: {mode}")

    def compute_interval(
        self,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> float:
        # --- Motion score (always in [0,1]) ---
        speed = math.hypot(*velocity)
        motion_score = min(speed / max(config.DEFAULT_BUOY_VELOCITY, 1e-6), 1.0)

        # --- Density score: 1 for sparse, 0 for dense ---
        num_neighbors = len(neighbors)
        DENSITY_THRESHOLD = 8  # or make this configurable
        density_score = 1 - min(1.0, num_neighbors / DENSITY_THRESHOLD)

        # --- Contact score: 1 for recent contact, 0 for long time since contact ---
        CONTACT_THRESHOLD = 4.0  # seconds, or set as appropriate
        if not neighbors:
            last_contact_delta = CONTACT_THRESHOLD
        else:
            last_contact = max((ts for _, ts, _ in neighbors), default=0.0)
            last_contact_delta = current_time - last_contact
        contact_score = 1 - min(1.0, last_contact_delta / CONTACT_THRESHOLD)

        # --- Linear combination with config weights ---
        total_weight = config.MOTION_WEIGHT + config.DENSITY_WEIGHT + config.CONTACT_WEIGHT
        k = (
            config.MOTION_WEIGHT * motion_score +
            config.DENSITY_WEIGHT * density_score +
            config.CONTACT_WEIGHT * contact_score
        ) / total_weight if total_weight > 0 else 0.0

        k = max(0.0, min(k, 1.0))
        interval = self.min_interval + (1 - k) * (self.max_interval - self.min_interval)
        return max(self.min_interval, min(interval, self.max_interval))