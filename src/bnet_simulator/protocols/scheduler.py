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
        self.next_dynamic_interval = None  # For dynamic scheduling

    def should_send_static(self, dt: float) -> bool:
        self.elapsed_time += dt
        if self.elapsed_time >= self.next_static_interval:
            self.elapsed_time = 0.0
            self.next_static_interval = random.uniform(self.min_interval, self.max_interval)
            return True
        return False

    def should_send_dynamic(
        self,
        dt: float,
        battery: float,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float]],
        current_time: float
    ) -> bool:
        self.elapsed_time += dt

        if self.next_dynamic_interval is None:
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time)

        if self.elapsed_time >= self.next_dynamic_interval:
            self.elapsed_time = 0.0
            self.next_dynamic_interval = None
            return True

        return False

    def compute_interval(self, velocity, neighbors, current_time):
        # Motion Score
        speed = math.hypot(*velocity)
        motion_score = min(speed / config.DEFAULT_BUOY_VELOCITY, 1.0)

        # Density Score
        num_neighbors = len(neighbors)
        if num_neighbors <= 2:
            density_score = 0.0
        elif num_neighbors <= 5:
            density_score = 0.5
        else:
            density_score = 1.0

        # Contact Score
        if not neighbors:
            contact_score = 1.0
        else:
            last_contact_time = max((ts for _, ts in neighbors), default=0.0)
            last_contact_delta = current_time - last_contact_time
            if last_contact_delta < 5.0:
                contact_score = 0.0
            elif last_contact_delta < 15.0:
                contact_score = 0.5
            else:
                contact_score = 1.0

        # Composite Score
        k = (
            0.3 * motion_score +
            0.3 * (1 - density_score) +
            0.4 * contact_score
        )

        return self.min_interval + (1 - k) * (self.max_interval - self.min_interval)
