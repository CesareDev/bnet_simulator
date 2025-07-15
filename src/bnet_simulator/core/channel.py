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
        self.buoys = []
        self.seen_attempts: Set[Tuple[uuid.UUID, uuid.UUID, float]] = set()  # (receiver_id, sender_id, timestamp)

    def set_buoys(self, buoys):
        self.buoys = buoys

    def update(self, sim_time: float):
        self.active_transmissions = [
            (b, start, end) for b, start, end in self.active_transmissions
            if end > sim_time
        ]

    def broadcast(self, beacon: Beacon, sim_time: float) -> bool:
        if self.metrics:
            self.metrics.log_sent()

        # Calculate the new transmission's time interval
        transmission_time = beacon.size_bits() / config.BIT_RATE
        new_end_time = sim_time + transmission_time
        
        # Check for collisions with any overlapping transmission
        for existing, start, end in self.active_transmissions:
            # Skip checking against beacons from the same sender
            if beacon.sender_id == existing.sender_id:
                continue
            
            # Check if there's any time overlap between the transmissions
            # Two intervals [a,b] and [c,d] overlap if: a <= d AND c <= b
            time_overlap = (sim_time <= end) and (start <= new_end_time)
            
            # Check if transmitters are within range of each other
            if time_overlap and self.in_range(beacon.position, existing.position):
                logging.log_error(f"Collision detected while broadcasting from {str(beacon.sender_id)[:6]}")
                if self.metrics:
                    self.metrics.log_collision()
                return False  # Collision

        # No collisions detected, proceed with transmission
        self.active_transmissions.append((beacon, sim_time, new_end_time))
        logging.log_info(f"Broadcasting beacon from {str(beacon.sender_id)[:6]}")

        receivers_in_range = [
            buoy for buoy in self.buoys
            if buoy.id != beacon.sender_id and self.in_range(beacon.position, buoy.position)
        ]
        n_receivers = len(receivers_in_range)
        if self.metrics:
            self.metrics.log_potentially_sent(beacon.sender_id, n_receivers)

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

            key = (receiver_id, beacon.sender_id, beacon.timestamp)
            if key in self.seen_attempts:
                continue  # Already processed this beacon for this receiver

            dx = receiver_position[0] - beacon.position[0]
            dy = receiver_position[1] - beacon.position[1]
            distance = math.hypot(dx, dy)

            # --- Channel behavior switch ---
            if config.IDEAL_CHANNEL:
                # Ideal: only receive if <= 70m, always successful
                if distance > config.COMMUNICATION_RANGE_HIGH_PROB:
                    continue  # Out of range for ideal channel
                propagation_delay = distance / config.SPEED_OF_LIGHT
                arrival_time = end + propagation_delay
                if not (start <= sim_time < arrival_time):
                    continue  # Not yet arrived
                self.seen_attempts.add(key)
                received.append(beacon)            
            else:
                if distance > config.COMMUNICATION_RANGE_MAX:
                    continue # Out of range
                propagation_delay = distance / config.SPEED_OF_LIGHT
                arrival_time = end + propagation_delay
                if not (start <= sim_time < arrival_time):
                    continue # Not yet arrived
                self.seen_attempts.add(key)
                # Realistic: probabilistic delivery and collisions
                if distance <= config.COMMUNICATION_RANGE_HIGH_PROB:
                    if random.random() < config.DELIVERY_PROB_HIGH:
                        received.append(beacon)
                    else:
                        if self.metrics:
                            self.metrics.log_lost()
                elif distance <= config.COMMUNICATION_RANGE_MAX:
                    if random.random() < config.DELIVERY_PROB_LOW:
                        received.append(beacon)
                    else:
                        logging.log_error(f"Packet lost from {str(beacon.sender_id)[:6]} to {str(receiver_id)[:6]}")
                        if self.metrics:
                            self.metrics.log_lost()

        if len(received) <= 1:
            if self.metrics and len(received) == 1:
                self.metrics.log_received(received[0].sender_id, received[0].timestamp, sim_time, receiver_id)
                self.metrics.log_actually_received(received[0].sender_id)
            return received
        else:
            # Collision at receiver — discard all
            logging.log_error(f"Collision detected while receiving at {str(receiver_id)[:6]}")
            if self.metrics:
                # Count collision for each beacon involved
                for _ in received:
                    self.metrics.log_collision()
            return []

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> bool:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        distance = math.hypot(dx, dy)
        if config.IDEAL_CHANNEL:
            return distance <= config.COMMUNICATION_RANGE_HIGH_PROB
        else:
            return distance <= config.COMMUNICATION_RANGE_MAX