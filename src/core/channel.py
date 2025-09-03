import math
import random
from typing import Tuple
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
        self.collision_beacons = set()  # Track beacons involved in collisions

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
                
                # For ideal channel - ensure processed + lost = potential
                if config.IDEAL_CHANNEL:
                    beacon_key = (beacon.sender_id, beacon.timestamp)
                    if beacon_key not in self.collision_beacons:
                        unprocessed = potential_count - processed_count
                        if unprocessed > 0:
                            # In ideal channel, all unreceived should be marked as received
                            for _ in range(unprocessed):
                                if self.metrics:
                                    self.metrics.log_actually_received(beacon.sender_id)
                                    logging.log_info(f"Ideal channel: marking {unprocessed} unreached as received for {str(beacon.sender_id)[:6]}")
                
                # No need to do anything for non-ideal channel as we've already accounted for all losses

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

        # Track if this beacon has a collision
        beacon_key = (beacon.sender_id, beacon.timestamp)
        
        # Track which receivers will experience collisions
        receivers_with_collisions = set()

        # Check for collisions
        for i, (existing, start, end, _, _) in enumerate(self.active_transmissions):
            if beacon.sender_id == existing.sender_id:
                continue
            
            # Check for time overlap
            time_overlap = (sim_time <= end) and (start <= new_end_time)
            if not time_overlap:
                continue
            
            existing_key = (existing.sender_id, existing.timestamp)
            
            # Direct collision detection (transmitters can hear each other)
            if self.in_range(beacon.position, existing.position):
                logging.log_error(f"Direct collision between {str(beacon.sender_id)[:6]} and {str(existing.sender_id)[:6]}")
                self.collision_beacons.add(beacon_key)
                self.collision_beacons.add(existing_key)
                
                # In case of direct collision, all receivers are affected
                for receiver in receivers_in_range:
                    receivers_with_collisions.add(receiver.id)
                    
            # Check which specific receivers can hear both transmissions
            else:
                for receiver in receivers_in_range:
                    if self.in_range(receiver.position, existing.position):
                        logging.log_error(f"Collision at receiver {str(receiver.id)[:6]} between {str(beacon.sender_id)[:6]} and {str(existing.sender_id)[:6]}")
                        receivers_with_collisions.add(receiver.id)
                        self.collision_beacons.add(beacon_key)
                        self.collision_beacons.add(existing_key)

        # Record transmission with count of affected receivers
        successful_receivers = 0
        self.active_transmissions.append((beacon, sim_time, new_end_time, n_receivers, successful_receivers))
        
        # Schedule transmission end
        self.simulator.schedule_event(
            new_end_time, 
            EventType.TRANSMISSION_END, 
            self,
            {"beacon": beacon}
        )
        
        # Track all receivers who won't get the packet (both collisions and probability-based losses)
        total_lost = 0
        collision_lost = len(receivers_with_collisions)
        probability_lost = 0
        
        # Process each potential receiver
        for receiver in receivers_in_range:
            # Calculate distance and propagation delay
            dx = receiver.position[0] - beacon.position[0]
            dy = receiver.position[1] - beacon.position[1]
            distance = math.hypot(dx, dy)
            propagation_delay = distance / config.SPEED_OF_LIGHT
            reception_time = new_end_time + propagation_delay + 1e-9
            
            # Check if receiver will experience collision
            collision_loss = receiver.id in receivers_with_collisions
            
            # Determine if packet will be received
            will_receive = False
            
            if config.IDEAL_CHANNEL:
                # In ideal channel, only receivers affected by collisions should miss the packet
                will_receive = not collision_loss
            else:
                # In non-ideal channel, consider both probability and collisions
                probability_loss = False
                
                # Only check probability if there's no collision
                if not collision_loss:
                    random_val = random.random()
                    
                    if distance <= config.COMMUNICATION_RANGE_HIGH_PROB:
                        probability_loss = random_val >= config.DELIVERY_PROB_HIGH
                    elif distance <= config.COMMUNICATION_RANGE_MAX:
                        probability_loss = random_val >= config.DELIVERY_PROB_LOW
                    
                    if probability_loss:
                        probability_lost += 1
                
                will_receive = not (collision_loss or probability_loss)
            
            # Schedule reception only if the packet will be received
            if will_receive:
                self.simulator.schedule_event(
                    reception_time,
                    EventType.RECEPTION, 
                    receiver,
                    {"beacon": beacon, "collision_checked": True}
                )
        
        # Count all losses
        total_lost = collision_lost + probability_lost
        
        # Log metrics for collisions and losses
        if self.metrics:
            if collision_lost > 0:
                # Log each collision as a separate event
                for _ in range(collision_lost):
                    self.metrics.log_collision()
            
            # Log all losses (both collision and probability-based)
            if total_lost > 0:
                self.metrics.log_lost(total_lost)
                logging.log_info(f"Lost {total_lost} packets: {collision_lost} from collisions, {probability_lost} from probability")
        
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