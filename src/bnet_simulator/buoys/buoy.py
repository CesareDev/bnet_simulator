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
        self.neighbors: List[Tuple[uuid.UUID, float]] = []  # list of known neighbors IDs with a timestamp (last seen)
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

    def cleanup_neighbors(self, sim_time: float):
        before = len(self.neighbors)
        self.neighbors = [
            (nid, ts) for nid, ts in self.neighbors
            if sim_time - ts <= config.NEIGHBOR_TIMEOUT
        ]
        after = len(self.neighbors)
        if before != after:
            logging.log_debug(f"Buoy {str(self.id)[:6]}... removed {before - after} stale neighbors")


    def send_beacon(self, dt: float, sim_time: float) -> bool:
        # TODO: Implement the scheduler
        self.timeout += dt
        if (self.timeout > 1.0):
            if self.channel.is_busy():
                logging.log_error(f"Buoy {self.id} tried to send a beacon but the channel is busy")
                return False
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
            if result:
                logging.log_info(f"Buoy {self.id} sent a beacon")
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
            logging.log_debug(f"Buoy {str(self.id)[:6]}... received beacon from {str(beacon.sender_id)[:6]}...")

    def update(self, dt: float, sim_time: float):
        self.update_position(dt)
        self.send_beacon(dt, sim_time)
        self.receive_beacon(sim_time)
        self.cleanup_neighbors(sim_time)

    def get_id(self) -> uuid.UUID:
        return self.id

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]}... pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"