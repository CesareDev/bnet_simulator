from typing import Tuple
import random
from bnet_simulator.utils import config

class BeaconScheduler:
    def __init__(self, min_interval: float = config.BEACON_MIN_INTERVAL, max_interval: float = config.BEACON_MAX_INTERVAL):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.elapsed_time = 0.0

    def should_send(self, dt: float, battery: float, velocity: Tuple[float, float], neighbors: int) -> bool:
        self.elapsed_time += dt
        if self.elapsed_time >= random.uniform(self.min_interval, self.max_interval):
            self.elapsed_time = 0.0
            return True
        return False
