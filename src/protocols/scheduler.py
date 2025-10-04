import random
import uuid
import math
from typing import Tuple, List
from utils import config

class BeaconScheduler:
    def __init__(
        self,
        min_interval: float = config.BEACON_MIN_INTERVAL,
        max_interval: float = config.BEACON_MAX_INTERVAL
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        
        self.last_static_send_time = -random.uniform(0, config.STATIC_INTERVAL)
        self.last_dynamic_send_time = -random.uniform(0, self.min_interval)
        
        self.next_static_interval = config.STATIC_INTERVAL
        self.next_dynamic_interval = None
    
    def get_next_check_interval(self) -> float:
        if config.SCHEDULER_TYPE == "static":
            return config.STATIC_INTERVAL
        else:
            # Use the most recently computed dynamic interval, or min_interval if not set
            return self.next_dynamic_interval if self.next_dynamic_interval is not None else self.min_interval

    def should_send(self, battery, velocity, neighbors, current_time):
        if config.SCHEDULER_TYPE == "static":
            return self.should_send_static(current_time)
        elif config.SCHEDULER_TYPE in ["dynamic_adab", "dynamic_acab"]:
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
        if config.SCHEDULER_TYPE == "dynamic_acab":
            # ACAB
            # DENSITY FACTOR
            # More neighbors = higher congestion = beacon less frequently
            n_neighbors = len(neighbors)
            NEIGHBORS_THRESHOLD = 10
            density_score = min(1.0, n_neighbors / NEIGHBORS_THRESHOLD)

            # 2. CONTACT SCORE
            # Recent contact = information is fresh = can beacon less frequently
            CONTACT_THRESHOLD = 20.0  # seconds
            if neighbors:
                # Find the most recent neighbor contact
                last_contact = max((ts for _, ts, _ in neighbors), default=current_time)
                delta = current_time - last_contact
                # contact_score = 1.0 (just contacted) → 0.0 (long time since contact)
                contact_score = max(0.0, 1.0 - (delta / CONTACT_THRESHOLD))
            else:
                # No neighbors = need to beacon frequently to discover
                contact_score = 0.0

            # 3. MOBILITY SCORE
            # Higher velocity = position changes fast = need to beacon more frequently
            vx, vy = velocity
            speed = math.hypot(vx, vy)  # Calculate magnitude of velocity vector
            MAX_SPEED = config.DEFAULT_BUOY_VELOCITY  # Maximum expected buoy speed

            # Normalize to [0, 1]: 0 = stationary, 1 = maximum speed
            mobility_score = min(1.0, speed / MAX_SPEED)

            # === WEIGHTED COMBINATION ===
            # Weights for each factor (must sum to 1.0)
            w_density = 0.4   # 40% weight: congestion avoidance
            w_contact = 0.3   # 30% weight: freshness of information
            w_mobility = 0.3  # 30% weight: rate of position change

            # Combined score calculation:
            # - High density_score → increase interval (beacon less)
            # - High contact_score → increase interval (info is fresh)
            # - High mobility_score → decrease interval (beacon more)
            #
            # We invert mobility_score because high mobility should REDUCE interval
            combined = (w_density * density_score + 
                       w_contact * contact_score + 
                       w_mobility * (1.0 - mobility_score))
        else:  # dynamic_adab
            # ADAB
            n_neighbors = len(neighbors)
            NEIGHBORS_THRESHOLD = 15
            density_score = min(1.0, n_neighbors / NEIGHBORS_THRESHOLD)

            # Weighted combination (density only)
            combined = density_score  # Only density, no contact score

        # Square the factor to get Fq = combined^2 (exponential scaling)
        fq = combined * combined

        # INTERVAL CALCULATION
        # BI = BImin + Fq × (BImax - BImin)
        bi_min = config.STATIC_INTERVAL
        bi = bi_min + fq * (self.max_interval - bi_min)

        # Add random jitter to avoid synchronization
        # Jitter range: ±50% relative variation
        jitter = random.uniform(-0.5, 0.5)
        bi_final = bi * (1 + jitter)

        # Ensure the interval stays within reasonable bounds
        return max(self.min_interval, min(bi_final, self.max_interval))