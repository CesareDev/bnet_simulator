import uuid
import math
import random
from typing import List, Tuple, Set, Dict, Optional
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.core.events import EventType  # Import from new events module
from bnet_simulator.utils import logging, config

class Channel:
    def __init__(self, metrics = None):
        # Format: (beacon, start_time, end_time, potential_receiver_count, processed_count)
        self.active_transmissions = []
        self.metrics = metrics
        self.buoys = []
        self.simulator = None  # Will be set by simulator
        self.seen_attempts = set()  # (receiver_id, sender_id, timestamp)

    def set_buoys(self, buoys):
        self.buoys = buoys

    def handle_event(self, event, sim_time: float):
        """Handle different event types"""
        if event.event_type == EventType.CHANNEL_UPDATE:
            self._handle_channel_update(event, sim_time)
        elif event.event_type == EventType.TRANSMISSION_END:
            self._handle_transmission_end(event, sim_time)
        else:
            logging.log_error(f"Channel received unhandled event: {event.event_type}")

    def _handle_channel_update(self, event, sim_time: float):
        """Handle channel update event"""
        self.update(sim_time)
        
        # Schedule next channel update
        self.simulator.schedule_event(
            sim_time + 1.0, EventType.CHANNEL_UPDATE, self
        )

    def _handle_transmission_end(self, event, sim_time: float):
        """Handle transmission end event"""
        # This is handled by the update method, but we can add specific logic here if needed
        beacon = event.data.get("beacon")
        if beacon:
            logging.log_info(f"Transmission completed for beacon from {str(beacon.sender_id)[:6]}")

    def update(self, sim_time: float):
        """Clean up expired transmissions"""
        expired_indices = []
        
        # Define a grace period to keep packets longer in the system
        grace_period = 1.0  # Keep packets for 1 second after transmission ends
        
        for i, (beacon, start, end, potential_count, processed_count) in enumerate(self.active_transmissions):
            # Only remove packets that are well past their end time
            if end + grace_period <= sim_time:
                expired_indices.append(i)

                # Count receivers that never processed this beacon as lost
                if self.metrics:
                    lost_count = potential_count - processed_count
                    for _ in range(lost_count):
                        self.metrics.log_lost()
                    if lost_count > 0:
                        logging.log_info(f"Beacon from {str(beacon.sender_id)[:6]} expired with {lost_count} unreached receivers")

        # Remove expired transmissions (in reverse order)
        for idx in sorted(expired_indices, reverse=True):
            self.active_transmissions.pop(idx)

    def broadcast(self, beacon: Beacon, sim_time: float) -> bool:
        """Broadcast a beacon to all buoys in range"""
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

        # Schedule the transmission end event
        self.simulator.schedule_event(
            new_end_time, 
            EventType.TRANSMISSION_END, 
            self,
            {"beacon": beacon}
        )
        
        # Schedule reception events for all potential receivers
        for receiver in receivers_in_range:
            # Calculate propagation delay
            dx = receiver.position[0] - beacon.position[0]
            dy = receiver.position[1] - beacon.position[1]
            distance = math.hypot(dx, dy)
            propagation_delay = distance / config.SPEED_OF_LIGHT
            
            # Reception happens after transmission completes plus propagation delay
            reception_time = new_end_time + propagation_delay
            
            # Schedule reception at the receiver
            self.simulator.schedule_event(
                reception_time,
                EventType.RECEPTION, 
                receiver,
                {"beacon": beacon}
            )

        return True

    def is_busy(self, position: Tuple[float, float], sim_time: float) -> bool:
        """Check if the channel is busy at a given position and time"""
        for beacon, start, end, _, _ in self.active_transmissions:
            if start <= sim_time <= end and self.in_range(position, beacon.position):
                return True
        return False

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> bool:
        """Check if two positions are within communication range"""
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        distance = math.hypot(dx, dy)
        if config.IDEAL_CHANNEL:
            return distance <= config.COMMUNICATION_RANGE_HIGH_PROB
        else:
            return distance <= config.COMMUNICATION_RANGE_MAX