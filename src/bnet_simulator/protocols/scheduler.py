import random
import math
import uuid
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
            self.next_static_interval = config.STATIC_INTERVAL
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

    def compute_interval(
        self,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> float:
        # Parameters
        N_neighbors = len(neighbors)  # Number of neighbors

        # Even more responsive thresholds
        if config.IDEAL_CHANNEL:
            N_threshold = 3  # Lower threshold for ideal channel (was 4)
        else:
            N_threshold = 1  # Lower threshold for non-ideal channel (was 2)

        # Calculate speed factor - move faster, beacon MUCH more frequently
        speed = math.hypot(*velocity)
        default_velocity = config.DEFAULT_BUOY_VELOCITY if hasattr(config, 'DEFAULT_BUOY_VELOCITY') else 1.0
        speed_factor = min(1.0, speed / default_velocity)

        # More aggressive base interval - start closer to minimum
        base_interval_factor = 0.7  # Was effectively 1.0

        # Standard calculation for low-to-medium densities - LINEAR scaling instead of quadratic
        if N_neighbors <= N_threshold:
            # Linear factor instead of quadratic - much less aggressive scaling
            factor = N_neighbors / N_threshold

            # Apply stronger speed adjustment - up to 50% reduction when moving fast
            adjusted_factor = factor * (1.0 - 0.5 * speed_factor)

            # Start from a lower base (70% of range)
            interval = self.min_interval + adjusted_factor * base_interval_factor * (self.max_interval - self.min_interval)
        else:
            # Start from a lower base for high densities too
            base_interval = self.min_interval + base_interval_factor * (self.max_interval - self.min_interval)

            # Calculate how much above threshold we are
            excess_neighbors = N_neighbors - N_threshold

            # Much less aggressive scaling for excess neighbors
            extra_time = min(1.0, 0.2 * (excess_neighbors / 2))

            # Apply stronger speed adjustment
            interval = base_interval + extra_time * (1.0 - 0.5 * speed_factor)

        # Tighter bounds - cap maximum interval lower
        extended_max = self.max_interval * 0.9  # Cap at 90% of max interval

        # Much more aggressive for sparse networks
        if N_neighbors <= 1:
            interval = max(self.min_interval, interval * 0.4)  # 60% reduction for sparse networks

        return max(self.min_interval, min(interval, extended_max))