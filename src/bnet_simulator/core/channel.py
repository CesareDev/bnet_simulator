import uuid
import math
import random
from typing import List, Tuple, Set, Dict, Optional
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.core.events import EventType
from bnet_simulator.utils import logging, config

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
        grace_period = 2.0
        
        for i, (beacon, _, end, potential_count, processed_count) in enumerate(self.active_transmissions):
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

        # PART 1: Check for direct transmitter-to-transmitter collisions
        collision_indexes = []
        for i, (existing, start, end, _, _) in enumerate(self.active_transmissions):
            if beacon.sender_id == existing.sender_id:
                continue
            
            # Check for time overlap first - required for any type of collision
            time_overlap = (sim_time <= end) and (start <= new_end_time)
            if not time_overlap:
                continue
            
            # Direct collision detection (transmitters can hear each other)
            if self.in_range(beacon.position, existing.position):
                logging.log_error(f"Direct collision between {str(beacon.sender_id)[:6]} and {str(existing.sender_id)[:6]}")
                collision_indexes.append(i)
                if self.metrics:
                    self.metrics.log_collision()
                continue  # Skip to next transmission
                
            # PART 2: NEW RECEIVER-SIDE COLLISION DETECTION
            # Check if any receivers can hear both this new beacon and an existing transmission
            for receiver in receivers_in_range:
                # Check if this receiver can also hear the existing transmission
                if self.in_range(receiver.position, existing.position):
                    # This receiver would hear both transmissions - it's a collision
                    logging.log_error(f"Receiver collision at {str(receiver.id)[:6]} between {str(beacon.sender_id)[:6]} and {str(existing.sender_id)[:6]}")
                    if i not in collision_indexes:
                        collision_indexes.append(i)
                    if self.metrics:
                        self.metrics.log_collision()
                    break  # Found at least one common receiver, no need to check more for this existing transmission

        # Handle collisions if any were detected
        if collision_indexes:
            # Calculate total potential receivers affected by collision
            total_collision_losses = n_receivers  # Start with current beacon's receivers
            
            for idx in sorted(collision_indexes, reverse=True):
                removed_beacon, start, end, potential_count, processed_count = self.active_transmissions[idx]
                # Add remaining potential receivers from this transmission
                remaining_receivers = potential_count - processed_count
                total_collision_losses += remaining_receivers
                
                logging.log_error(f"Removed collided transmission from {str(removed_beacon.sender_id)[:6]} with {remaining_receivers} unreached receivers")
                self.active_transmissions.pop(idx)

            if self.metrics:
                # Log the collision event
                self.metrics.log_collision()
                # Log lost packets for all affected receivers
                self.metrics.log_lost(total_collision_losses)
                logging.log_info(f"Collision resulted in {total_collision_losses} lost packet opportunities")
            
            return False

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
            reception_time = new_end_time + propagation_delay
            
            # Determine if packet will be received
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
            
            # Schedule reception or mark as processed
            if will_receive:
                self.simulator.schedule_event(
                    reception_time,
                    EventType.RECEPTION, 
                    receiver,
                    {"beacon": beacon}
                )
            
            # Update processed count regardless of reception success
            for i, (tx_beacon, start, end, potential_count, processed_count) in enumerate(self.active_transmissions):
                if tx_beacon.sender_id == beacon.sender_id and tx_beacon.timestamp == beacon.timestamp:
                    self.active_transmissions[i] = (tx_beacon, start, end, potential_count, processed_count + 1)
                    break

        return True

    def is_busy(self, position: Tuple[float, float], sim_time: float) -> bool:
        for beacon, start, end, _, _ in self.active_transmissions:
            if start <= sim_time <= end:
                # Check if this node can detect the transmitter
                # The key change: A node might not sense a transmission that's happening
                # if it's from a transmitter outside its detection range
                sender_position = beacon.position
                
                # Calculate distance to the transmitter
                dx = position[0] - sender_position[0]
                dy = position[1] - sender_position[1]
                distance = math.hypot(dx, dy)
                
                # Node can only sense transmissions from nodes it can hear
                detection_range = config.COMMUNICATION_RANGE_HIGH_PROB
                if distance <= detection_range:
                    return True
                
        # Channel appears free to this node, even if there are ongoing transmissions
        # that it cannot detect (hidden terminals)
        return False

    def in_range(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> bool:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        distance = math.hypot(dx, dy)
        if config.IDEAL_CHANNEL:
            return distance <= config.COMMUNICATION_RANGE_HIGH_PROB
        else:
            return distance <= config.COMMUNICATION_RANGE_MAX