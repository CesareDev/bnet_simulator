import uuid
import math
import random
from typing import List, Tuple, Set, Dict, Optional
from protocols.beacon import Beacon
from core.events import EventType
from utils import logging, config

class Channel:
    def __init__(self, metrics = None):
        self.active_transmissions = []
        self.metrics = metrics
        self.buoys = []
        self.simulator = None
        self.seen_attempts = set()

    def set_buoys(self, buoys):
        self.buoys = buoys

    def handle_event(self, event, sim_time: float):
        if event.event_type == EventType.CHANNEL_UPDATE:
            self._handle_channel_update(event, sim_time)
        elif event.event_type == EventType.TRANSMISSION_END:
            self._handle_transmission_end(event, sim_time)
        else:
            logging.log_error(f"Channel received unhandled event: {event.event_type}")

    def _handle_channel_update(self, event, sim_time: float):
        self.update(sim_time)
        self.simulator.schedule_event(
            sim_time + 1.0, EventType.CHANNEL_UPDATE, self
        )

    def _handle_transmission_end(self, event, sim_time: float):
        beacon = event.data.get("beacon")
        if beacon:
            logging.log_info(f"Transmission completed for beacon from {str(beacon.sender_id)[:6]}")

    def update(self, sim_time: float):
        expired_indices = []
        # Use max propagation delay for grace period
        max_delay = config.COMMUNICATION_RANGE_MAX / config.SPEED_OF_LIGHT
        grace_period = max_delay + 1e-6  # Small epsilon to account for floating point errors
        
        for i, (beacon, start, end, potential_count, processed_count) in enumerate(self.active_transmissions):
            if end + grace_period <= sim_time:
                expired_indices.append(i)
                if self.metrics:
                    lost_count = potential_count - processed_count
                    if lost_count > 0:
                        self.metrics.log_lost(lost_count)
                        logging.log_info(f"Beacon from {str(beacon.sender_id)[:6]} expired with {lost_count} unreached receivers")

        for idx in sorted(expired_indices, reverse=True):
            self.active_transmissions.pop(idx)

    def broadcast(self, beacon: Beacon, sim_time: float) -> bool:
        logging.log_info(f"Broadcasting from {str(beacon.sender_id)[:6]} at {sim_time:.2f}s")
        
        if self.metrics:
            self.metrics.log_sent()

        transmission_time = beacon.size_bits() / config.BIT_RATE
        new_end_time = sim_time + transmission_time

        receivers_in_range = [
            buoy for buoy in self.buoys
            if buoy.id != beacon.sender_id and self.in_range(beacon.position, buoy.position)
        ]
        n_receivers = len(receivers_in_range)
        
        if self.metrics:
            self.metrics.log_potentially_sent(beacon.sender_id, n_receivers)

        # Only log collisions, do NOT remove transmissions
        for i, (existing, start, end, _, _) in enumerate(self.active_transmissions):
            if beacon.sender_id == existing.sender_id:
                continue
            
            # Check for time overlap
            time_overlap = (sim_time <= end) and (start <= new_end_time)
            if not time_overlap:
                continue
            
            # Direct collision detection (transmitters can hear each other)
            if self.in_range(beacon.position, existing.position):
                logging.log_error(f"Direct collision between {str(beacon.sender_id)[:6]} and {str(existing.sender_id)[:6]}")
                if self.metrics:
                    self.metrics.log_collision()
                
            # Check if any receivers can hear both transmissions
            for receiver in receivers_in_range:
                if self.in_range(receiver.position, existing.position):
                    logging.log_error(f"Potential receiver collision at {str(receiver.id)[:6]} between {str(beacon.sender_id)[:6]} and {str(existing.sender_id)[:6]}")
                    if self.metrics:
                        self.metrics.log_collision()
                    break

        # Record transmission
        successful_receivers = 0
        self.active_transmissions.append((beacon, sim_time, new_end_time, n_receivers, successful_receivers))
        
        # Schedule transmission end
        self.simulator.schedule_event(
            new_end_time, 
            EventType.TRANSMISSION_END, 
            self,
            {"beacon": beacon}
        )
        
        # Process each potential receiver
        for receiver in receivers_in_range:
            dx = receiver.position[0] - beacon.position[0]
            dy = receiver.position[1] - beacon.position[1]
            distance = math.hypot(dx, dy)
            propagation_delay = distance / config.SPEED_OF_LIGHT
            # Add a tiny epsilon to ensure consistent event ordering
            reception_time = new_end_time + propagation_delay + 1e-9
            
            # Determine if packet will be received based on distance probability
            will_receive = False
            
            if config.IDEAL_CHANNEL:
                will_receive = True
            else:
                random_val = random.random()
                if distance <= config.COMMUNICATION_RANGE_HIGH_PROB:
                    will_receive = random_val < config.DELIVERY_PROB_HIGH
                    if not will_receive and self.metrics:
                        self.metrics.log_lost(1)
                elif distance <= config.COMMUNICATION_RANGE_MAX:
                    will_receive = random_val < config.DELIVERY_PROB_LOW
                    if not will_receive and self.metrics:
                        self.metrics.log_lost(1)
            
            # Schedule reception for this receiver
            if will_receive:
                self.simulator.schedule_event(
                    reception_time,
                    EventType.RECEPTION, 
                    receiver,
                    {"beacon": beacon}
                )
            
            # Update processed count
            for i, (tx_beacon, start, end, potential_count, processed_count) in enumerate(self.active_transmissions):
                if tx_beacon.sender_id == beacon.sender_id and tx_beacon.timestamp == beacon.timestamp:
                    self.active_transmissions[i] = (tx_beacon, start, end, potential_count, processed_count + 1)
                    break

        return True

    def is_busy(self, position: Tuple[float, float], sim_time: float) -> bool:
        for beacon, start, end, _, _ in self.active_transmissions:
            if start <= sim_time <= end:
                sender_position = beacon.position
                
                # Calculate distance to the transmitter
                dx = position[0] - sender_position[0]
                dy = position[1] - sender_position[1]
                distance = math.hypot(dx, dy)
                
                # Calculate how far the signal wavefront has traveled
                wavefront_radius = config.SPEED_OF_LIGHT * (sim_time - start)
                
                # Node can sense transmission only if:
                # 1. It's within the detection range (carrier sense)
                # 2. The wavefront has reached this position
                detection_range = config.COMMUNICATION_RANGE_HIGH_PROB
                if distance <= wavefront_radius and distance <= detection_range:
                    return True
                
        return False

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> bool:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        distance = math.hypot(dx, dy)
        # Always use COMMUNICATION_RANGE_MAX as maximum range
        return distance <= config.COMMUNICATION_RANGE_MAX