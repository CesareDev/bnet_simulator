import uuid
from enum import Enum
from typing import List, Tuple
import random
from bnet_simulator.protocols.scheduler import BeaconScheduler
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.core.channel import Channel
from bnet_simulator.utils import config, logging

class BuoyState(Enum):
    SLEEPING = 0
    RECEIVING = 1

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
        self.range = random.uniform(config.COMMUNICATION_RANGE_MIN, config.COMMUNICATION_RANGE_MAX)
        self.state = BuoyState.RECEIVING
        self.sleep_timer = 0.0

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
        if self.scheduler.should_send(dt, self.battery, self.velocity, len(self.neighbors)):
            # Step 1: Carrier sense
            if self.channel.is_busy(self.position, sim_time):
                logging.log_warning(f"Buoy {str(self.id)[:6]} senses busy channel at {sim_time:.2f}s")
                return False  # Wait
            # Step 2: Wait DIFS
            if self.channel.is_busy(self.position, sim_time + config.DIFS_TIME):
                logging.log_warning(f"Buoy {str(self.id)[:6]} senses busy channel after DIFS at {sim_time + config.DIFS_TIME:.2f}s")
                return False  # Channel became busy during DIFS

            # Step 3: Transmit
            self.range = random.uniform(config.COMMUNICATION_RANGE_MIN, config.COMMUNICATION_RANGE_MAX)
            beacon = Beacon(
                sender_id=self.id,
                mobile=self.is_mobile,
                position=self.position,
                battery=self.battery,
                neighbors=self.neighbors.copy(),
                timestamp=sim_time,
                range=self.range,
            )
            success = self.channel.broadcast(beacon, sim_time)
            if success:
                logging.log_info(f"Buoy {str(self.id)[:6]} sent beacon at {sim_time:.2f}s")
            else:
                logging.log_warning(f"Buoy {str(self.id)[:6]} failed to send beacon at {sim_time:.2f}s (collision)")
            return success

        return False

    def receive_beacon(self, sim_time: float):
        beacons = self.channel.receive_all(self.id, self.position, sim_time)
        for beacon in beacons:
            # Here the same beacon is received multiple times because of the channel that keeps it in the buffer until the trasmission is over
            existing = next((n for n in self.neighbors if n[0] == beacon.sender_id), None)
            if existing:
                self.neighbors = [
                    (nid, sim_time) if nid == beacon.sender_id else (nid, ts)
                    for nid, ts in self.neighbors
                ]
            else:
                self.neighbors.append((beacon.sender_id, sim_time))

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]}... pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"