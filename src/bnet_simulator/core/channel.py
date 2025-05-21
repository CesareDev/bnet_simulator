import uuid
from typing import List, Tuple
import math
import random
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.utils import logging, config

class Channel:
    def __init__(self):
        self.active_transmissions: List[Tuple[Beacon, float, float]] = []

    def update(self, sim_time: float):
        # Removed expired transmissions
        self.active_transmissions = [
            (b, start, end) for b, start, end in self.active_transmissions
            if end > sim_time
        ]

    def broadcast(self, beacon: Beacon, sim_time: float) -> bool:
        for existing, start, end in self.active_transmissions:
            if beacon.sender_id == existing.sender_id:
                continue
            if start <= sim_time <= end and self.in_range(beacon.position, existing.position, beacon.range):
                return False  # Collision or busy channel in range
        duration = config.TRASMISSION_TIME  # e.g. 0.1
        self.active_transmissions.append((beacon, sim_time, sim_time + duration))
        return True

    def is_busy(self, position: Tuple[float, float], sim_time: float) -> bool:
        for beacon, start, end in self.active_transmissions:
            if start <= sim_time <= end and self.in_range(position, beacon.position, beacon.range):
                return True
        return False

    def receive_all(self, receiver_id: uuid.UUID, receiver_position: Tuple[float, float], sim_time: float) -> List[Beacon]:
        # self.update(sim_time)
        candidates = [
            beacon for beacon, start, end in self.active_transmissions
            if beacon.sender_id != receiver_id and start <= sim_time <= end and self.in_range(receiver_position, beacon.position, beacon.range)
        ]

        received = []
        for beacon in candidates:
            if random.random() < config.BEACON_LOSS_PROB:
                logging.log_warning(f"Packet lost from {str(beacon.sender_id)[:6]} to {str(receiver_id)[:6]}")
                continue
            received.append(beacon)

        return received if len(received) <= 1 else []

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float], range: float) -> bool:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        return math.hypot(dx, dy) <= range
