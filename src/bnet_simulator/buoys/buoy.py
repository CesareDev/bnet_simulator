import uuid
import random
import math
from enum import Enum
from typing import List, Tuple, Dict, Optional
from bnet_simulator.protocols.scheduler import BeaconScheduler
from bnet_simulator.protocols.beacon import Beacon
from bnet_simulator.core.events import EventType  # Import from new events module
from bnet_simulator.utils import config, logging

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
        self.is_boat = False
        self.battery = battery
        self.velocity = velocity
        self.neighbors: List[Tuple[uuid.UUID, float, Tuple[float, float]]] = []
        self.scheduler = BeaconScheduler()
        self.channel = channel
        self.state = BuoyState.RECEIVING
        self.sleep_timer = 0.0
        self.metrics = metrics
        self.simulator = None  # Will be set by simulator

        # Internal transmission state
        self.backoff_time = 0.0
        self.backoff_remaining = 0.0
        self.next_try_time = 0.0
        self.want_to_send = False
        self.scheduler_decision_time = 0.0
        
    def handle_event(self, event, sim_time: float):
        """Handle different event types"""
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
        """Handle scheduler check event"""
        # Check if buoy should send beacon
        should_send = self.scheduler.should_send(
            self.battery, self.velocity, self.neighbors, sim_time
        )
        
        if should_send:
            # Set the want_to_send flag and store decision time
            self.want_to_send = True
            self.scheduler_decision_time = sim_time
            
            # Schedule channel sensing immediately
            self.simulator.schedule_event(
                sim_time, EventType.CHANNEL_SENSE, self
            )
        
        # Schedule next scheduler check
        next_check_interval = 0.5  # Default
        if hasattr(self.scheduler, "get_next_check_interval"):
            next_check_interval = self.scheduler.get_next_check_interval()
            
        self.simulator.schedule_event(
            sim_time + next_check_interval, EventType.SCHEDULER_CHECK, self
        )

    def _handle_channel_sense(self, event, sim_time: float):
        """Handle channel sensing event"""
        if not self.want_to_send:
            return
            
        # Check if channel is busy
        if self.channel.is_busy(self.position, sim_time):
            # Schedule another check after a short delay
            self.simulator.schedule_event(
                sim_time + 0.01, EventType.CHANNEL_SENSE, self
            )
        else:
            # Channel is free, start DIFS wait
            self.state = BuoyState.WAITING_DIFS
            
            # Schedule DIFS completion
            self.simulator.schedule_event(
                sim_time + config.DIFS_TIME, EventType.DIFS_COMPLETION, self
            )

    def _handle_difs_completion(self, event, sim_time: float):
        """Handle DIFS completion event"""
        if not self.want_to_send or self.state != BuoyState.WAITING_DIFS:
            return
            
        # Check if channel is still free
        if self.channel.is_busy(self.position, sim_time):
            # Channel became busy during DIFS, go back to sensing
            self.state = BuoyState.RECEIVING
            self.simulator.schedule_event(
                sim_time, EventType.CHANNEL_SENSE, self
            )
        else:
            # DIFS complete, start backoff
            backoff_time = random.uniform(config.BACKOFF_TIME_MIN, config.BACKOFF_TIME_MAX)
            self.backoff_time = backoff_time
            self.backoff_remaining = backoff_time
            self.state = BuoyState.BACKOFF
            
            # Schedule backoff completion
            self.simulator.schedule_event(
                sim_time + backoff_time, 
                EventType.BACKOFF_COMPLETION, 
                self,
                {"backoff_start_time": sim_time}
            )

    def _handle_backoff_completion(self, event, sim_time: float):
        """Handle backoff completion event"""
        if not self.want_to_send or self.state != BuoyState.BACKOFF:
            return
            
        # Check if channel is still free
        if self.channel.is_busy(self.position, sim_time):
            # Channel became busy during backoff, calculate remaining time
            backoff_start = event.data.get("backoff_start_time", sim_time - self.backoff_time)
            waited = sim_time - backoff_start
            self.backoff_remaining = max(0, self.backoff_time - waited)
            self.state = BuoyState.RECEIVING
            
            # Go back to channel sensing
            self.simulator.schedule_event(
                sim_time, EventType.CHANNEL_SENSE, self
            )
        else:
            # Backoff complete, start transmission
            self.simulator.schedule_event(
                sim_time, EventType.TRANSMISSION_START, self
            )

    def _handle_transmission_start(self, event, sim_time: float):
        """Handle transmission start event"""
        if not self.want_to_send:
            return
        
        # Create beacon
        beacon = self.create_beacon(sim_time)
        
        # Attempt to broadcast
        success = self.channel.broadcast(beacon, sim_time)
        
        # Reset buoy state regardless of success
        self.want_to_send = False
        self.state = BuoyState.RECEIVING
        
        # Record metrics if successful
        if success and self.metrics:
            latency = sim_time - self.scheduler_decision_time
            self.metrics.record_scheduler_latency(latency)

    def _handle_reception(self, event, sim_time: float):
        """Handle reception event"""
        beacon = event.data.get("beacon")
        if not beacon:
            return
            
        # Update neighbor information based on the received beacon
        updated = False
        for i, (nid, _, _) in enumerate(self.neighbors):
            if nid == beacon.sender_id:
                self.neighbors[i] = (nid, sim_time, beacon.position)
                updated = True
                break
        if not updated:
            self.neighbors.append((beacon.sender_id, sim_time, beacon.position))
        
        # Log reception in metrics if available
        if self.metrics:
            self.metrics.log_received(beacon.sender_id, beacon.timestamp, sim_time, self.id)
            self.metrics.log_actually_received(beacon.sender_id)

    def _handle_neighbor_cleanup(self, event, sim_time: float):
        """Handle neighbor cleanup event"""
        # Clean up expired neighbors
        self.neighbors = [
            (nid, ts, pos) for nid, ts, pos in self.neighbors
            if sim_time - ts <= config.NEIGHBOR_TIMEOUT
        ]
        
        # Schedule next cleanup
        self.simulator.schedule_event(
            sim_time + config.NEIGHBOR_TIMEOUT, EventType.NEIGHBOR_CLEANUP, self
        )

    def _handle_buoy_movement(self, event, sim_time: float):
        """Handle buoy movement event"""
        if not self.is_mobile:
            return
            
        # Update position based on velocity
        dt = 0.1  # Small time step for movement
        x, y = self.position
        vx, vy = self.velocity
        
        # Check world boundaries and bounce if needed
        new_x = x + vx * dt
        new_y = y + vy * dt
        
        world_width = config.WORLD_WIDTH
        world_height = config.WORLD_HEIGHT
        
        if new_x < 0 or new_x > world_width:
            self.velocity = (-vx, vy)  # Reverse x velocity
        if new_y < 0 or new_y > world_height:
            self.velocity = (vx, -vy)  # Reverse y velocity
            
        # Apply corrected movement
        vx, vy = self.velocity
        self.position = (x + vx * dt, y + vy * dt)
        
        # Schedule next movement update
        self.simulator.schedule_event(
            sim_time + dt, EventType.BUOY_MOVEMENT, self
        )
    
    def create_beacon(self, sim_time: float) -> Beacon:
        """Create a beacon for transmission"""
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