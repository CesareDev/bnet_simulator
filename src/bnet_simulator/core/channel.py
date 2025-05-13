from typing import Dict, List
from bnet_simulator.protocols.beacon import Beacon
import uuid

class Channel:
    def __init__(self):
        # Maps buoy ID to the last beacon it heard in the current time step
        self.current_transmissions: Dict[uuid.UUID, Beacon] = {}

    def clear(self):
        # TODO: Implement a more sophisticated clearing mechanism
        self.current_transmissions.clear()

    def is_busy(self) -> bool:
        return len(self.current_transmissions) > 0

    def broadcast(self, beacon: Beacon) -> bool:
        if self.is_busy():
            return False
        self.current_transmissions[beacon.sender_id] = beacon
        return True

    def receive_all(self, receiver_id: uuid.UUID) -> List[Beacon]:
        return [
            beacon for sid, beacon in self.current_transmissions.items()
            if sid != receiver_id
        ]
