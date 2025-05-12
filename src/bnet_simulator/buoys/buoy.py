import uuid
from typing import List, Tuple
from bnet_simulator.protocols.scheduler import BeaconScheduler
from bnet_simulator.core.channel import Channel

class Buoy:
    def __init__(
        self,
        channel: Channel,
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
        self.neighbors: List[Tuple[uuid.UUID, str]] = []  # list of known neighbors IDs with a timestamp (last seen)
        self.scheduler = BeaconScheduler()
        self.channel = channel

    def update_position(self, dt: float):
        if not self.is_mobile:
            return
        x, y = self.position
        dx, dy = self.velocity
        self.position = (x + dx * dt, y + dy * dt)

    def update_neighbors(self):
        pass # TODO: Implement the neighbor update logic (Based on received beacons)

    def send_beacon(self):
        pass # TODO: Implement the beacon sending logic (Sensing the channel and sending using the scheduler)

    def receive_beacon(self):
        pass # TODO: Implement the beacon receiving logic (Sensing the channel and updating neighbors)

    def update(self, dt: float):
        self.update_position(dt)
        self.send_beacon()
        self.receive_beacon()

    def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) ** 0.5

    def get_id(self) -> uuid.UUID:
        return self.id

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]}... pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"