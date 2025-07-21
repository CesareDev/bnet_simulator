import random
import uuid
from typing import Tuple, List
from bnet_simulator.utils import config, logging

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
        self.next_dynamic_interval = random.uniform(self.min_interval, self.max_interval)

    def tick(self, dt: float):
        self.elapsed_time += dt

    def should_send(self, battery, velocity, neighbors, current_time):
        if config.SCHEDULER_TYPE == "static":
            return self.should_send_static()
        elif config.SCHEDULER_TYPE == "dynamic":
            return self.should_send_dynamic(battery, velocity, neighbors, current_time)
        else:
            raise ValueError(f"Unknown scheduler type: {config.SCHEDULER_TYPE}")

    def should_send_static(self) -> bool:
        if self.elapsed_time >= self.next_static_interval:
            self.elapsed_time = 0.0
            self.next_static_interval = config.STATIC_INTERVAL # + random.uniform(-0.1, 0.1)
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
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time)
            return True
        return False

    def compute_interval(
        self,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> float:
        # Count number of neighbors
        n_neighbors = len(neighbors)

        # Define what constitutes high density
        max_density = 15.0  # Consider 15 neighbors as "high density"

        # Simple linear scaling: more neighbors = longer interval
        # 0 neighbors -> min_interval
        # max_density neighbors -> max_interval
        density_factor = min(1.0, n_neighbors / max_density)

        # Linear interpolation between min and max interval based on density
        interval = self.min_interval + density_factor * (self.max_interval - self.min_interval)

        # Ensure interval stays within bounds
        new_interval = max(self.min_interval, min(interval, self.max_interval))

        return new_interval