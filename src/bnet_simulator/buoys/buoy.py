import uuid
from typing import List, Tuple
from bnet_simulator.protocols.scheduler import BeaconScheduler
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.core.channel import Channel
from bnet_simulator.utils import config, logging

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

        # Temporary initial random timeout
        import random
        self.timeout = random.uniform(0.0, 1.0)

    def update_position(self, dt: float):
        if not self.is_mobile:
            return
        x, y = self.position
        dx, dy = self.velocity
        self.position = (x + dx * dt, y + dy * dt)

    def send_beacon(self, dt: float, sim_time: float) -> bool:
        if self.channel.is_busy():
            return False
        
        # TODO: Implement the scheduler
        self.timeout += dt
        if (self.timeout > 1.0):
            beacon = Beacon(
                sender_id=self.id,
                mobile=self.is_mobile,
                position=self.position,
                battery=self.battery,
                neighbors=self.neighbors.copy(),
                timestamp=sim_time
            )
            self.timeout = 0.0
            result = self.channel.broadcast(beacon)
            return result
        
        return False

    def receive_beacon(self):
        beacons = self.channel.receive_all(self.id)
        for beacon in beacons:
            if beacon.sender_id == self.id:
                continue
            if self.euclidean_distance(self.position, beacon.position) < config.COMMUNICATION_RANGE:
                self.neighbors.append((beacon.sender_id, beacon.timestamp))


    def update(self, dt: float, sim_time: float):
        self.update_position(dt)
        self.send_beacon(dt, sim_time=sim_time)
        self.receive_beacon()

    def euclidean_distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) ** 0.5

    def get_id(self) -> uuid.UUID:
        return self.id

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]}... pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"