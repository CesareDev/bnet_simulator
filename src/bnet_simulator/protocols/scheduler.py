from typing import Tuple
from bnet_simulator.utils import config

class BeaconScheduler:
    def __init__(self, min_interval: float = config.BEACON_MIN_INTERVAL, max_interval: float = config.BEACON_MAX_INTERVAL):
        self.min_interval = min_interval
        self.max_interval = max_interval

    def compute_interval(self, battery: float, velocity: Tuple[float, float], neighbors: int):
        pass # TODO: Implement the logic to compute the interval based on various parameters (crucial part)
