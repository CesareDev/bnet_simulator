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
        
        self.last_static_send_time = -random.uniform(0, config.STATIC_INTERVAL)
        self.last_dynamic_send_time = -random.uniform(0, self.min_interval)
        
        self.next_static_interval = config.STATIC_INTERVAL
        self.next_dynamic_interval = None
    
    def get_next_check_interval(self) -> float:
        if config.SCHEDULER_TYPE == "static":
            return max(0.1, config.STATIC_INTERVAL * 0.1)
        else:
            return max(0.1, self.min_interval * 0.2)

    def should_send(self, battery, velocity, neighbors, current_time):
        if config.SCHEDULER_TYPE == "static":
            return self.should_send_static(current_time)
        elif config.SCHEDULER_TYPE == "dynamic":
            return self.should_send_dynamic(battery, velocity, neighbors, current_time)
        else:
            raise ValueError(f"Unknown scheduler type: {config.SCHEDULER_TYPE}")

    def should_send_static(self, current_time: float) -> bool:
        time_since_last = current_time - self.last_static_send_time
        
        if time_since_last >= self.next_static_interval:
            self.last_static_send_time = current_time
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
        
        time_since_last = current_time - self.last_dynamic_send_time
        
        if time_since_last >= self.next_dynamic_interval:
            self.last_dynamic_send_time = current_time
            self.next_dynamic_interval = self.compute_interval(velocity, neighbors, current_time)
            return True
        return False

    def compute_interval(
        self,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> float:
        n_neighbors = len(neighbors)
        max_density = 15.0
        density_factor = min(1.0, n_neighbors / max_density)
        interval = self.min_interval + density_factor * (self.max_interval - self.min_interval)
        return max(self.min_interval, min(interval, self.max_interval))