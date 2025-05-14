import uuid
from typing import Dict, List, Tuple
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.utils.config import COMMUNICATION_RANGE
import math

class Channel:
    def __init__(self):
        # Beacon queue for the current time step
        self.transmissions: List[Beacon] = []
        self.collided: bool = False

    def clear(self):
        self.transmissions.clear()
        self.collided = False

    def is_busy(self) -> bool:
        return len(self.transmissions) > 0

    def broadcast(self, beacon: Beacon) -> bool:

        if self.is_busy():
            # Collision: mark all transmissions as invalid
            self.collided = True
        self.transmissions.append(beacon)
        return not self.collided

    def receive_all(self, receiver_id: uuid.UUID, receiver_position: Tuple[float, float]) -> List[Beacon]:
        if self.collided:
            return []  # No message can be received due to collision

        received = []
        for beacon in self.transmissions:
            if beacon.sender_id == receiver_id:
                continue  # Skip own beacon
            if self.in_range(receiver_position, beacon.position):
                received.append(beacon)

        return received

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> bool:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        distance = math.hypot(dx, dy)
        return distance <= COMMUNICATION_RANGE
