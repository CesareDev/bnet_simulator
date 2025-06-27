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

        # Load dynamic parameters from file if in dynamic mode
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

    def compute_interval(
        self,
        velocity: Tuple[float, float],
        neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]],
        current_time: float,
    ) -> float:
        # Calculate base scores
        speed = math.hypot(*velocity)
        motion_score = min(speed / max(config.DEFAULT_BUOY_VELOCITY, 1e-6), 1.0)
        
        num_neighbors = len(neighbors)
        
        # Set thresholds based on channel type
        if config.IDEAL_CHANNEL:
            # For ideal channels, be more collision-aware
            DENSITY_THRESHOLD = 6  # More sensitive to density
            CONTACT_THRESHOLD = 3.0  # Less sensitive to contacts
            
            # Adjust effective max interval based on density
            # For dense networks, use longer intervals to avoid collisions
            if num_neighbors > 8:
                effective_max_interval = self.max_interval  # Full interval for very dense
            elif num_neighbors > 5:
                effective_max_interval = self.max_interval * 0.8  # 80% of max for dense
            else:
                effective_max_interval = min(self.max_interval * 0.6, 3.0)  # Short for sparse
        else:
            # Keep your current non-ideal settings
            DENSITY_THRESHOLD = 5
            CONTACT_THRESHOLD = 2.0
            effective_max_interval = min(self.max_interval, 3.0)
        
        # Calculate scores
        density_score = 1 - min(1.0, num_neighbors / DENSITY_THRESHOLD)
        
        if not neighbors:
            last_contact_delta = CONTACT_THRESHOLD
        else:
            last_contact = max((ts for _, ts, _ in neighbors), default=0.0)
            last_contact_delta = current_time - last_contact
        contact_score = 1 - min(1.0, last_contact_delta / CONTACT_THRESHOLD)
        
        # Simplified weight calculation
        if config.IDEAL_CHANNEL:
            if num_neighbors > 8:
                # Very dense - heavily prioritize density to avoid collisions
                motion_weight = 0.05
                density_weight = 0.75  # Much higher weight on density
                contact_weight = 0.20
            elif num_neighbors > 5:
                # Moderately dense
                motion_weight = 0.10
                density_weight = 0.65
                contact_weight = 0.25
            else:
                # Sparse - be more aggressive with contact
                motion_weight = 0.15
                density_weight = 0.40
                contact_weight = 0.45
        else:
            # Keep your current non-ideal weights
            motion_weight = 0.1
            density_weight = 0.2
            contact_weight = 0.7
        
        # Apply the weights
        k = (
            motion_weight * motion_score +
            density_weight * density_score +
            contact_weight * contact_score
        )
        
        # Density-based boost for ideal channel only
        if config.IDEAL_CHANNEL:
            if num_neighbors <= 3:
                # Very sparse network - more aggressive
                k = min(k + 0.2, 1.0)  # Add significant boost
            elif num_neighbors <= 5:
                # Somewhat sparse - slightly more aggressive
                k = min(k + 0.1, 1.0)
            # No boost for dense networks
        else:
            # Keep your current boost for non-ideal
            k = min(k + 0.2, 1.0)
        
        k = max(0.0, min(k, 1.0))
        interval = self.min_interval + (1 - k) * (effective_max_interval - self.min_interval)
        return max(self.min_interval, min(interval, effective_max_interval))