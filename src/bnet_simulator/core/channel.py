import uuid
from typing import List, Tuple, Set
import math
import random
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.utils.metrics import Metrics
from bnet_simulator.utils import logging, config

class Channel:
    def __init__(self, metrics: Metrics = None):
        self.active_transmissions: List[Tuple[Beacon, float, float]] = []
        self.metrics = metrics
        self.seen_attempts: Set[Tuple[uuid.UUID, uuid.UUID, float]] = set()  # (receiver_id, sender_id, timestamp)

    def update(self, sim_time: float):
        self.active_transmissions = [
            (b, start, end) for b, start, end in self.active_transmissions
            if end > sim_time
        ]

    def broadcast(self, beacon: Beacon, sim_time: float) -> bool:
        if self.metrics:
            self.metrics.log_sent()

        for existing, start, end in self.active_transmissions:
            if beacon.sender_id == existing.sender_id:
                continue
            if start <= sim_time <= end and self.in_range(beacon.position, existing.position):
                logging.log_error(f"Collision detected while broadcasting from {str(beacon.sender_id)[:6]}")
                if self.metrics:
                    self.metrics.log_collision()
                return False  # Collision

        self.active_transmissions.append((beacon, sim_time, sim_time + config.TRASMISSION_TIME))
        logging.log_info(f"Broadcasting beacon from {str(beacon.sender_id)[:6]}")
        return True

    def is_busy(self, position: Tuple[float, float], sim_time: float) -> bool:
        for beacon, start, end in self.active_transmissions:
            if start <= sim_time <= end and self.in_range(position, beacon.position):
                return True
        return False

    def receive_all(self, receiver_id: uuid.UUID, receiver_position: Tuple[float, float], sim_time: float) -> List[Beacon]:
        received = []

        for beacon, start, end in self.active_transmissions:
            if beacon.sender_id == receiver_id:
                continue
            if not (start <= sim_time <= end):
                continue

            key = (receiver_id, beacon.sender_id, beacon.timestamp)
            if key in self.seen_attempts:
                continue  # Already processed this beacon for this receiver

            self.seen_attempts.add(key)

            dx = receiver_position[0] - beacon.position[0]
            dy = receiver_position[1] - beacon.position[1]
            distance = math.hypot(dx, dy)

            if distance > config.COMMUNICATION_RANGE_MAX:
                continue  # Out of range

            if distance <= config.COMMUNICATION_RANGE_THRESHOLD:
                received.append(beacon)
                if self.metrics:
                    self.metrics.log_received(beacon.sender_id, beacon.timestamp, sim_time, receiver_id)
            else:
                if random.random() < config.DELIVERY_PROB_OVER_THRESHOLD:
                    received.append(beacon)
                    if self.metrics:
                        self.metrics.log_received(beacon.sender_id, beacon.timestamp, sim_time, receiver_id)
                else:
                    logging.log_error(f"Packet lost from {str(beacon.sender_id)[:6]} to {str(receiver_id)[:6]}")
                    if self.metrics:
                        self.metrics.log_lost()

        if len(received) <= 1:
            return received
        else:
            # Collision at receiver — discard all
            logging.log_error(f"Collision detected while receiving at {str(receiver_id)[:6]}")
            if self.metrics:
                self.metrics.log_collision()
            return []

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> bool:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        return math.hypot(dx, dy) <= config.COMMUNICATION_RANGE_MAX
