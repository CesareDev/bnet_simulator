import uuid
from typing import List, Tuple, Set
import math
import random
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.utils.metrics import Metrics
from bnet_simulator.utils import logging, config

class Channel:
    def __init__(self, metrics: Metrics = None):
        # Format: (beacon, start_time, end_time, potential_receiver_count, processed_count)
        self.active_transmissions: List[Tuple[Beacon, float, float, int, int]] = []
        self.metrics = metrics
        self.buoys = []
        self.seen_attempts: Set[Tuple[uuid.UUID, uuid.UUID, float]] = set()  # (receiver_id, sender_id, timestamp)

    def set_buoys(self, buoys):
        self.buoys = buoys

    def update(self, sim_time: float):
        expired_indices = []
        for i, (beacon, start, end, potential_count, processed_count) in enumerate(self.active_transmissions):
            if end <= sim_time:  # Transmission has finished
                expired_indices.append(i)

                # Count receivers that never processed this beacon as lost
                if self.metrics:
                    # Calculate how many receivers never got it
                    lost_count = potential_count - processed_count
                    for _ in range(lost_count):
                        self.metrics.log_lost()
                    if lost_count > 0:
                        logging.log_info(f"Beacon from {str(beacon.sender_id)[:6]} expired with {lost_count} unreached receivers")

        # Remove expired transmissions (in reverse order)
        for idx in sorted(expired_indices, reverse=True):
            self.active_transmissions.pop(idx)

    def broadcast(self, beacon: Beacon, sim_time: float) -> bool:
        if self.metrics:
            self.metrics.log_sent()

        # Calculate the new transmission's time interval
        transmission_time = beacon.size_bits() / config.BIT_RATE
        new_end_time = sim_time + transmission_time

        # Find potential receivers BEFORE collision detection
        receivers_in_range = [
            buoy for buoy in self.buoys
            if buoy.id != beacon.sender_id and self.in_range(beacon.position, buoy.position)
        ]
        n_receivers = len(receivers_in_range)
        if self.metrics:
            self.metrics.log_potentially_sent(beacon.sender_id, n_receivers)

        # Check for collisions with any overlapping transmission
        collision_indexes = []  # Track which transmissions collide

        for i, (existing, start, end, _, _) in enumerate(self.active_transmissions):
            # Skip checking against beacons from the same sender
            if beacon.sender_id == existing.sender_id:
                continue
            
            # Check if there's any time overlap between the transmissions
            # Two intervals [a,b] and [c,d] overlap if: a <= d AND c <= b
            time_overlap = (sim_time <= end) and (start <= new_end_time)

            # Check if transmitters are within range of each other
            if time_overlap and self.in_range(beacon.position, existing.position):
                logging.log_error(f"Collision detected between {str(beacon.sender_id)[:6]} and {str(existing.sender_id)[:6]}")
                collision_indexes.append(i)
                if self.metrics:
                    self.metrics.log_collision()

        # If there were collisions, remove the collided transmissions
        if collision_indexes:
            # Remove in reverse order to avoid index shifting problems
            for idx in sorted(collision_indexes, reverse=True):
                removed_beacon, _, _, _, _ = self.active_transmissions.pop(idx)
                logging.log_error(f"Removed collided transmission from {str(removed_beacon.sender_id)[:6]}")

            # Count collision for current beacon too
            if self.metrics:
                self.metrics.log_collision()

            return False  # The new beacon also failed due to collision

        # No collisions detected, proceed with transmission
        # Add with potential receivers count and 0 processed count
        self.active_transmissions.append((beacon, sim_time, new_end_time, n_receivers, 0))
        logging.log_info(f"Broadcasting beacon from {str(beacon.sender_id)[:6]}")

        return True

    def is_busy(self, position: Tuple[float, float], sim_time: float) -> bool:
        for beacon, start, end, _, _ in self.active_transmissions:
            if start <= sim_time <= end and self.in_range(position, beacon.position):
                return True
        return False

    def receive_all(self, receiver_id: uuid.UUID, receiver_position: Tuple[float, float], sim_time: float) -> List[Beacon]:
        received = []
        
        for i, (beacon, start, end, potential_count, processed_count) in enumerate(self.active_transmissions):
            # Skip if sender is the same as receiver
            if beacon.sender_id == receiver_id:
                continue

            # Check if already processed by this receiver
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
                    
                # Mark as processed
                self.seen_attempts.add(key)
                # Increment processed count
                self.active_transmissions[i] = (beacon, start, end, potential_count, processed_count + 1)
                
                received.append(beacon)            
            else:
                if distance > config.COMMUNICATION_RANGE_MAX:
                    continue # Out of range
                    
                propagation_delay = distance / config.SPEED_OF_LIGHT
                arrival_time = end + propagation_delay
                if not (start <= sim_time < arrival_time):
                    continue # Not yet arrived
                    
                # Mark as processed regardless of outcome
                self.seen_attempts.add(key)
                
                # Increment processed count regardless of outcome
                self.active_transmissions[i] = (beacon, start, end, potential_count, processed_count + 1)
                
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