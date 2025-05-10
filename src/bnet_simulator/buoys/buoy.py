import uuid
from typing import List, Tuple

class Buoy:
    def __init__(
        self,
        position: Tuple[float, float] = (0.0, 0.0),
        is_mobile: bool = False,
        battery: float = 100.0,
        velocity: Tuple[float, float] = (0.0, 0.0),
    ):
        self.id = uuid.uuid4()
        self.position = position  # (lat, lon)
        self.is_mobile = is_mobile
        self.battery = battery  # percentage
        self.velocity = velocity  # (dx, dy) if mobile
        self.neighbors: List[uuid.UUID, str] = []  # list of known neighbors IDs with a timestamp (last seen)

    def send_beacon(self):
        pass #TODO: Implement the beacon sending logic

    def receive_beacon(self, beacon: dict):
        pass #TODO: Implement the beacon receiving logic

    def update_position(self, dt: float):
        if not self.is_mobile:
            return

        x, y = self.position
        dx, dy = self.velocity
        self.position = (x + dx * dt, y + dy * dt)

    def update_neighbors(self, visible_neighbors: List[uuid.UUID, str]):
        self.neighbors = visible_neighbors

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]}... pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"