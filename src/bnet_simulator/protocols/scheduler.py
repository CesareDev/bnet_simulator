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
            self.next_static_interval = config.STATIC_INTERVAL + random.uniform(-0.1, 0.1)
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
        N_neighbors = len(neighbors)
        
        # Contact score: 1 for recent contact, 0 for long time since contact
        CONTACT_THRESHOLD = 20.0  # seconds
        
        if neighbors:
            # Find the most recent neighbor contact
            last_contact = max((ts for _, ts, _ in neighbors), default=current_time)
            delta = current_time - last_contact
            
            contact_score = max(0.0, 1.0 - (delta / CONTACT_THRESHOLD))
        else:
            contact_score = 0.0
        
        max_density = 10.0  # Consider 10 neighbors as "high density"
        density_factor = min(1.0, N_neighbors / max_density)
        
        base_percent = 0.7
        base_interval = self.min_interval + base_percent * (self.max_interval - self.min_interval)
        
        contact_adjustment = 0.6 * contact_score * (base_interval - self.min_interval)
        
        density_adjustment = 0.4 * density_factor * (base_interval - self.min_interval)
        
        interval = base_interval - contact_adjustment - density_adjustment
        
        bounded_max = self.min_interval + 0.8 * (self.max_interval - self.min_interval)
        
        new_interval = max(self.min_interval, min(interval, bounded_max))
        
        return new_interval