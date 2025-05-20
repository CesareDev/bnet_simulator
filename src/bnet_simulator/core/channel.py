import uuid
from typing import List, Tuple
import math
import random
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.utils.config import COMMUNICATION_RANGE
from bnet_simulator.utils import logging, config

class Channel:
    def __init__(self):
        # Store beacons transmitted during the current timestep
        self.transmissions: List[Beacon] = []

    def clear(self):
        self.transmissions.clear()

    def broadcast(self, beacon: Beacon) -> bool:
        for existing in self.transmissions:
            if beacon.sender_id == existing.sender_id:
                continue  # Ignore self-collisions
            if self.in_range(beacon.position, existing.position):
                return False  # Collision with a different sender
        self.transmissions.append(beacon)
        return True  # Successful transmission


    def receive_all(self, receiver_id: uuid.UUID, receiver_position: Tuple[float, float]) -> List[Beacon]:
        # Collect beacons in range, excluding self
        candidates = [
            beacon for beacon in self.transmissions
            if beacon.sender_id != receiver_id and self.in_range(receiver_position, beacon.position)
        ]
        
        # Simulate packet loss
        received = []
        for beacon in candidates:
            if random.random() < config.BEACON_LOSS_PROB:
                logging.log_warning(f"Packet lost from {str(beacon.sender_id)[:6]} to {str(receiver_id)[:6]}")
                continue  # Drop this beacon
            received.append(beacon)

        # If multiple are in range, local collision: nothing is received
        if len(received) > 1:
            return []

        return received

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> bool:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        return math.hypot(dx, dy) <= COMMUNICATION_RANGE
