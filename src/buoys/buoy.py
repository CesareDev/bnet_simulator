import uuid
import random
import math
from enum import Enum
from typing import Tuple
from protocols.scheduler import BeaconScheduler
from protocols.beacon import Beacon
from core.events import EventType
from utils import config, logging

class BuoyState(Enum):
    SLEEPING = 0
    RECEIVING = 1
    WAITING_DIFS = 2
    BACKOFF = 3

class Buoy:
    def __init__(
        self,
        channel,
        position: Tuple[float, float] = (0.0, 0.0),
        is_mobile: bool = False,
        battery: float = 100.0,
        velocity: Tuple[float, float] = (0.0, 0.0),
        metrics = None
    ):
        self.id = uuid.uuid4()
        self.position = position
        self.is_mobile = is_mobile
        self.battery = battery
        self.velocity = velocity
        self.neighbors = []
        self.scheduler = BeaconScheduler()
        self.channel = channel
        self.state = BuoyState.RECEIVING
        self.metrics = metrics
        self.simulator = None

        # CSMA/CA state
        self.backoff_time = 0.0
        self.backoff_remaining = 0.0
        self.next_try_time = 0.0
        self.want_to_send = False
        self.scheduler_decision_time = 0.0
        
    def handle_event(self, event, sim_time: float):
        handlers = {
            EventType.SCHEDULER_CHECK: self._handle_scheduler_check,
            EventType.CHANNEL_SENSE: self._handle_channel_sense,
            EventType.DIFS_COMPLETION: self._handle_difs_completion,
            EventType.BACKOFF_COMPLETION: self._handle_backoff_completion,
            EventType.TRANSMISSION_START: self._handle_transmission_start,
            EventType.RECEPTION: self._handle_reception,
            EventType.NEIGHBOR_CLEANUP: self._handle_neighbor_cleanup,
            EventType.BUOY_MOVEMENT: self._handle_buoy_movement
        }
        
        handler = handlers.get(event.event_type)
        if handler:
            handler(event, sim_time)
        else:
            logging.log_error(f"Buoy {str(self.id)[:6]} received unhandled event: {event.event_type}")

    def _handle_scheduler_check(self, event, sim_time: float):
        should_send = self.scheduler.should_send(
            self.battery, self.velocity, self.neighbors, sim_time
        )
        
        if should_send:
            self.want_to_send = True
            self.scheduler_decision_time = sim_time
            self.simulator.schedule_event(
                sim_time, EventType.CHANNEL_SENSE, self
            )
        
        next_check_interval = self.scheduler.get_next_check_interval()
        self.simulator.schedule_event(
            sim_time + next_check_interval, EventType.SCHEDULER_CHECK, self
        )

    def _handle_channel_sense(self, event, sim_time: float):
        if not self.want_to_send:
            return
            
        if self.channel.is_busy(self.position, sim_time):
            # Small delay (10ms) before retrying channel sense to avoid immediate busy-wait and allow event queue to advance
            self.simulator.schedule_event(
                sim_time + 0.01, EventType.CHANNEL_SENSE, self
            )
        else:
            self.state = BuoyState.WAITING_DIFS
            self.simulator.schedule_event(
                sim_time + config.DIFS_TIME, EventType.DIFS_COMPLETION, self
            )

    def _handle_difs_completion(self, event, sim_time: float):
        if not self.want_to_send or self.state != BuoyState.WAITING_DIFS:
            return
            
        if self.channel.is_busy(self.position, sim_time):
            self.state = BuoyState.RECEIVING
            self.simulator.schedule_event(
                sim_time, EventType.CHANNEL_SENSE, self
            )
        else:
            backoff_time = random.uniform(config.BACKOFF_TIME_MIN, config.BACKOFF_TIME_MAX)
            self.backoff_time = backoff_time
            self.backoff_remaining = backoff_time
            self.state = BuoyState.BACKOFF
            
            self.simulator.schedule_event(
                sim_time + backoff_time, 
                EventType.BACKOFF_COMPLETION, 
                self,
                {"backoff_start_time": sim_time}
            )

    def _handle_backoff_completion(self, event, sim_time: float):
        if not self.want_to_send or self.state != BuoyState.BACKOFF:
            return
            
        if self.channel.is_busy(self.position, sim_time):
            backoff_start = event.data.get("backoff_start_time", sim_time - self.backoff_time)
            waited = sim_time - backoff_start
            self.backoff_remaining = max(0, self.backoff_time - waited)
            self.state = BuoyState.RECEIVING
            
            self.simulator.schedule_event(
                sim_time, EventType.CHANNEL_SENSE, self
            )
        else:
            self.simulator.schedule_event(
                sim_time, EventType.TRANSMISSION_START, self
            )

    def _handle_transmission_start(self, event, sim_time: float):
        if not self.want_to_send:
            return
        
        beacon = self.create_beacon(sim_time)
        success = self.channel.broadcast(beacon, sim_time)
        
        self.want_to_send = False
        self.state = BuoyState.RECEIVING
        
        if success and self.metrics:
            latency = sim_time - self.scheduler_decision_time
            self.metrics.record_scheduler_latency(latency)

    def _handle_reception(self, event, sim_time: float):
        beacon = event.data.get("beacon")
        if not beacon:
            return
    
        # Skip collision check if already done at channel level
        collision = False
        collision_checked = event.data.get("collision_checked", False)
    
        if not collision_checked:
            # Define a collision window (10 microseconds)
            COLLISION_WINDOW = 1e-5
            
            # Check for collision with other transmissions at this receiver
            for tx_beacon, start, end, _, _ in self.channel.active_transmissions:
                # Skip the beacon we're currently processing
                if tx_beacon.sender_id == beacon.sender_id and tx_beacon.timestamp == beacon.timestamp:
                    continue
            
                # Only consider transmissions that have started
                if sim_time < start:
                    continue
                
                # Calculate when this transmission's wavefront reached this receiver
                dx = self.position[0] - tx_beacon.position[0]
                dy = self.position[1] - tx_beacon.position[1]
                distance = math.hypot(dx, dy)
            
                # Only consider transmissions within reception range
                if distance > config.COMMUNICATION_RANGE_MAX:
                    continue
                
                propagation_delay = distance / config.SPEED_OF_LIGHT
                arrival_time = end + propagation_delay
            
                # If another transmission arrives within the collision window, mark as collision
                if abs(arrival_time - sim_time) < COLLISION_WINDOW:
                    logging.log_error(f"Collision detected at receiver {str(self.id)[:6]} between {str(beacon.sender_id)[:6]} and {str(tx_beacon.sender_id)[:6]}")
                    collision = True
                    break
    
        # If collision detected, don't process (already counted as lost in channel.py)
        if collision:
            return
    
        # No collision - process the reception normally
        updated = False
        for i, (nid, _, _) in enumerate(self.neighbors):
            if nid == beacon.sender_id:
                self.neighbors[i] = (nid, sim_time, beacon.position)
                updated = True
                break
        if not updated:
            self.neighbors.append((beacon.sender_id, sim_time, beacon.position))
    
        key = (self.id, beacon.sender_id, beacon.timestamp)
        if key not in self.channel.seen_attempts:
            self.channel.seen_attempts.add(key)
        
            # Update successful reception count in active_transmissions
            for i, (tx_beacon, start, end, potential_count, processed_count) in enumerate(self.channel.active_transmissions):
                if tx_beacon.sender_id == beacon.sender_id and tx_beacon.timestamp == beacon.timestamp:
                    self.channel.active_transmissions[i] = (tx_beacon, start, end, potential_count, processed_count + 1)
                    break
        
            # Log successful reception
            if self.metrics:
                self.metrics.log_received(beacon.sender_id, beacon.timestamp, sim_time, self.id)
                self.metrics.log_actually_received(beacon.sender_id)

    def _handle_neighbor_cleanup(self, event, sim_time: float):
        self.neighbors = [
            (nid, ts, pos) for nid, ts, pos in self.neighbors
            if sim_time - ts <= config.NEIGHBOR_TIMEOUT
        ]
        
        self.simulator.schedule_event(
            sim_time + config.NEIGHBOR_TIMEOUT, EventType.NEIGHBOR_CLEANUP, self
        )

    def _handle_buoy_movement(self, event, sim_time: float):
        if not self.is_mobile:
            return
            
        dt = 0.1
        x, y = self.position
        vx, vy = self.velocity
        
        new_x = x + vx * dt
        new_y = y + vy * dt
        
        world_width = config.WORLD_WIDTH
        world_height = config.WORLD_HEIGHT
        
        if new_x < 0 or new_x > world_width:
            self.velocity = (-vx, vy)
        if new_y < 0 or new_y > world_height:
            self.velocity = (vx, -vy)
            
        vx, vy = self.velocity
        self.position = (x + vx * dt, y + vy * dt)
        
        self.simulator.schedule_event(
            sim_time + dt, EventType.BUOY_MOVEMENT, self
        )
    
    def create_beacon(self, sim_time: float) -> Beacon:
        return Beacon(
            sender_id=self.id,
            mobile=self.is_mobile,
            position=self.position,
            battery=self.battery,
            neighbors=self.neighbors.copy(),
            timestamp=sim_time
        )

    def __repr__(self):
        return f"<Buoy id={str(self.id)[:6]} pos={self.position} vel={self.velocity} bat={self.battery:.1f}% mob={self.is_mobile}>"
    
    # CSMA/CA Transmission Cycle Example:
#
# Step                | Time (s) | State        | Action
# --------------------|----------|--------------|----------------------------------------
# Scheduler Check     | 0.00     | RECEIVING    | Decide to send, schedule channel sense
# Channel Sense       | 0.00     | WAITING_DIFS | Channel free, schedule DIFS
# DIFS Completion     | 0.05     | BACKOFF      | Channel free, random backoff, schedule backoff completion
# Backoff Completion  | 0.17     | RECEIVING    | Channel free, schedule transmission start
# Transmission Start  | 0.17     | RECEIVING    | Send beacon, record scheduler latency
#
# If the channel is busy at any step, the buoy retries sensing after a short delay.