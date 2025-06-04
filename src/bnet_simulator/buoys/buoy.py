import uuid
import random
import math
from enum import Enum
from typing import List, Tuple
from bnet_simulator.protocols.scheduler import BeaconScheduler
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.core.channel import Channel
from bnet_simulator.utils.metrics import Metrics
from bnet_simulator.utils import config, logging

class BuoyState(Enum):
    SLEEPING = 0
    RECEIVING = 1
    WAITING_DIFS = 2
    BACKOFF = 3

class Buoy:
    def __init__(
        self,
        channel: Channel,
        position: Tuple[float, float] = (0.0, 0.0),
        is_mobile: bool = False,
        battery: float = 100.0,
        velocity: Tuple[float, float] = (0.0, 0.0),
        metrics: Metrics = None
    ):
        self.id = uuid.uuid4()
        self.position = position
        self.is_mobile = is_mobile
        self.is_boat = False
        self.battery = battery
        self.velocity = velocity
        self.neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]] = [] #  (Neighbor ID, timestamp, last position)
        self.scheduler = BeaconScheduler()
        self.channel = channel
        self.state = BuoyState.RECEIVING
        self.sleep_timer = 0.0
        self.metrics = metrics

        # Internal transmission state
        self.backoff_time = 0.0
        self.backoff_remaining = 0.0
        self.next_try_time = 0.0
        self.want_to_send = False
        self.scheduler_decision_time = 0.0

    def update_position(self, dt: float):
        if self.is_mobile:
            x, y = self.position
            dx, dy = self.velocity
            self.position = (x + dx * dt, y + dy * dt)

    def cleanup_neighbors(self, sim_time: float):
        self.neighbors = [
            (nid, ts, p) for nid, ts, p in self.neighbors
            if sim_time - ts <= config.NEIGHBOR_TIMEOUT
        ]

    def send_beacon(self, dt: float, sim_time: float) -> bool:
        # Determine if we should initiate transmission
        if not self.want_to_send:
            if self.scheduler.should_send(dt, self.battery, self.velocity, self.neighbors, sim_time):
                self.want_to_send = True
                self.state = BuoyState.RECEIVING
                self.scheduler_decision_time = sim_time
            else:
                self.state = BuoyState.RECEIVING
                return False

        # State: RECEIVING (channel sensing before DIFS)
        if self.state == BuoyState.RECEIVING:
            if self.channel.is_busy(self.position, sim_time):
                return False
            logging.log_info(f"Buoy {str(self.id)[:6]} channel free, waiting DIFS")
            self.state = BuoyState.WAITING_DIFS
            self.next_try_time = sim_time + config.DIFS_TIME
            return False

        # State: WAITING_DIFS
        if self.state == BuoyState.WAITING_DIFS:
            if self.channel.is_busy(self.position, sim_time):
                logging.log_info(f"Buoy {str(self.id)[:6]} channel became busy during DIFS")
                self.state = BuoyState.RECEIVING
                return False
            if sim_time < self.next_try_time:
                return False
            logging.log_info(f"Buoy {str(self.id)[:6]} DIFS complete, starting backoff")
            self.backoff_time = random.uniform(config.BACKOFF_TIME_MIN, config.BACKOFF_TIME_MAX)
            self.backoff_remaining = self.backoff_time
            self.state = BuoyState.BACKOFF
            self.next_try_time = sim_time + self.backoff_remaining
            return False

        # State: BACKOFF
        if self.state == BuoyState.BACKOFF:
            if self.channel.is_busy(self.position, sim_time):
                waited = sim_time - (self.next_try_time - self.backoff_remaining)
                self.backoff_remaining -= waited
                if self.backoff_remaining < 0:
                    self.backoff_remaining = 0.0
                logging.log_info(f"Buoy {str(self.id)[:6]} interrupted during backoff, remaining: {self.backoff_remaining:.2f}s")
                self.state = BuoyState.RECEIVING
                return False

            if sim_time < self.next_try_time:
                return False

            # Attempt to transmit
            beacon = Beacon(
                sender_id=self.id,
                mobile=self.is_mobile,
                position=self.position,
                battery=self.battery,
                neighbors=self.neighbors.copy(),
                timestamp=sim_time
            )
            success = self.channel.broadcast(beacon, sim_time)
            logging.log_info(f"Buoy {str(self.id)[:6]} sent beacon at {sim_time:.2f}s: {'SUCCESS' if success else 'FAIL'}")

            if success and self.metrics:
                latency = sim_time - self.scheduler_decision_time
                self.metrics.record_scheduler_latency(latency)

            # Reset transmission attempt state
            self.want_to_send = False
            self.state = BuoyState.RECEIVING
            return success

        return False

    def receive_beacon(self, sim_time: float):
        beacons = self.channel.receive_all(self.id, self.position, sim_time)
        for beacon in beacons:
            updated = False
            for i, (nid, _, _) in enumerate(self.neighbors):
                if nid == beacon.sender_id:
                    self.neighbors[i] = (nid, sim_time, beacon.position)
                    updated = True
                    break
            if not updated:
                self.neighbors.append((beacon.sender_id, sim_time, beacon.position))

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]} pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"
