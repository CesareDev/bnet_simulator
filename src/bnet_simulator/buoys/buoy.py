import uuid
from typing import List, Tuple
from bnet_simulator.protocols.scheduler import BeaconScheduler
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.core.channel import Channel
from bnet_simulator.utils import config, logging

import random

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
        self.neighbors: List[Tuple[uuid.UUID, float]] = []  # list of known neighbors IDs with a timestamp (last seen)
        self.scheduler = BeaconScheduler()
        self.channel = channel


        self.elapsed_time = 0.0

    def update_position(self, dt: float):
        if not self.is_mobile:
            return
        x, y = self.position
        dx, dy = self.velocity
        self.position = (x + dx * dt, y + dy * dt)

    def cleanup_neighbors(self, sim_time: float):
        self.neighbors = [
            (nid, ts) for nid, ts in self.neighbors
            if sim_time - ts <= config.NEIGHBOR_TIMEOUT
        ]

    def send_beacon(self, dt: float, sim_time: float) -> bool:
        # TODO: Implement the scheduler
        self.elapsed_time += dt
        if self.elapsed_time > random.uniform(1, 5):
            beacon = Beacon(
                sender_id=self.id,
                mobile=self.is_mobile,
                position=self.position,
                battery=self.battery,
                neighbors=self.neighbors.copy(),
                timestamp=sim_time
            )
            self.elapsed_time = 0.0
            result = self.channel.broadcast(beacon)
            logging.log_info(f"Buoy {str(self.id)[:6]} try to send beacon")
            return result
        return False

    def receive_beacon(self, sim_time: float):
        beacons = self.channel.receive_all(self.id, self.position)
        for beacon in beacons:
            if beacon.sender_id == self.id:
                continue
            # Update or add the neighbor
            existing = next((n for n in self.neighbors if n[0] == beacon.sender_id), None)
            if existing:
                self.neighbors = [
                    (nid, sim_time) if nid == beacon.sender_id else (nid, ts)
                    for nid, ts in self.neighbors
                ]
            else:
                self.neighbors.append((beacon.sender_id, sim_time))

    def get_id(self) -> uuid.UUID:
        return self.id

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]}... pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"