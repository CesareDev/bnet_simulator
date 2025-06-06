import random
import math
import uuid
from typing import Tuple, List
from bnet_simulator.utils import config

class BeaconScheduler:
    def __init__(self, min_interval: float = config.BEACON_MIN_INTERVAL, max_interval: float = config.BEACON_MAX_INTERVAL):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.elapsed_time = 0.0
        self.next_static_interval = random.uniform(self.min_interval, self.max_interval)
        self.next_dynamic_interval = None

    def tick(self, dt: float):
        self.elapsed_time += dt

    def should_send(self, battery: float, velocity: Tuple[float, float], neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]], current_time: float) -> bool:
        if config.SCHEDULER_TYPE == "static":
            return self.should_send_static()
        elif config.SCHEDULER_TYPE == "dynamic":
            return self.should_send_dynamic(battery, velocity, neighbors, current_time)
        elif config.SCHEDULER_TYPE == "rl":
            raise ValueError("RL scheduler not yet implemented.")
        else:
            raise ValueError(f"Unknown scheduler type: {config.SCHEDULER_TYPE}")

    def should_send_static(self, dt: float) -> bool:
        if self.elapsed_time >= self.next_static_interval:
            self.elapsed_time = 0.0
            self.next_static_interval = random.uniform(self.min_interval, self.max_interval)
            return True
        return False

    def should_send_dynamic(
        self,
        battery: float,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float
    ) -> bool:

        if self.next_dynamic_interval is None:
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time)

        if self.elapsed_time >= self.next_dynamic_interval:
            self.elapsed_time = 0.0
            self.next_dynamic_interval = None
            return True

        return False

    def compute_interval(self, velocity: Tuple[float, float], neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]], current_time: float) -> float:
        # --- Motion Score ---
        speed = math.hypot(*velocity)
        motion_score = min(speed / config.DEFAULT_BUOY_VELOCITY, 1.0)

        # --- Density Score ---
        num_neighbors = len(neighbors)
        density_midpoint = 3.0
        density_alpha = 0.7
        density_score = 1 / (1 + math.exp(-density_alpha * (num_neighbors - density_midpoint)))

        # --- Contact Score ---
        if not neighbors:
            contact_score = 1.0
        else:
            last_contact = max((ts for _, ts, _ in neighbors), default=0.0)
            delta = current_time - last_contact
            contact_midpoint = 8.0
            contact_alpha = 0.3
            contact_score = 1 / (1 + math.exp(-contact_alpha * (delta - contact_midpoint)))

        # --- Composite Score ---
        k = 0.2 * motion_score + 0.4 * density_score + 0.4 * contact_score
        interval = self.min_interval + ((1 - k) ** 2) * (self.max_interval - self.min_interval)

        return interval
