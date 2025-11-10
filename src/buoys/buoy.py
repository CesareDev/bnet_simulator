import uuid
import random
import math
from enum import Enum
from typing import Tuple
from protocols.scheduler import BeaconScheduler
from protocols.beacon import Beacon
from core.events import EventType
from config.config_handler import ConfigHandler
from utils import logging

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
        battery: float = None,
        velocity: Tuple[float, float] = (0.0, 0.0),
        metrics = None
    ):
        cfg = ConfigHandler()
        
        self.id = uuid.uuid4()
        self.position = position
        self.is_mobile = is_mobile
        self.battery = battery if battery is not None else cfg.get('buoys', 'default_battery')
        self.velocity = velocity
        self.neighbors = []
        self.scheduler = BeaconScheduler()
        self.channel = channel
        self.state = BuoyState.RECEIVING
        self.metrics = metrics
        self.simulator = None

        self.difs_time = cfg.get('csma', 'difs_time')
        self.slot_time = cfg.get('csma', 'slot_time')
        self.cw = cfg.get('csma', 'cw')
        self.neighbor_timeout = cfg.get('scheduler', 'neighbor_timeout')
        self.world_width = cfg.get('world', 'width')
        self.world_height = cfg.get('world', 'height')
        self.speed_of_light = cfg.get('network', 'speed_of_light')
        self.comm_range_max = cfg.get('network', 'communication_range_max')
        
        self.multihop_mode = cfg.get('simulation', 'multihop_mode')
        self.multihop_limit = cfg.get('simulation', 'multihop_limit')

        self.backoff_time = 0.0
        self.backoff_remaining = 0.0
        self.next_try_time = 0.0
        self.want_to_send = False
        self.scheduler_decision_time = 0.0
        
        # Multihop append mode: store neighbors received from other nodes
        self.received_neighbors = []
        
        # Multihop forwarded mode: track seen beacons to avoid forwarding duplicates
        self.forwarded_beacons = set()
        
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
        # Check if this is a forwarding request
        forward_beacon = event.data.get("forward_beacon")
        
        if forward_beacon:
            # Forward mode: create forwarded beacon
            if self.channel.is_busy(self.position, sim_time):
                self.simulator.schedule_event(
                    sim_time + 0.01, EventType.CHANNEL_SENSE, self, {"forward_beacon": forward_beacon}
                )
            else:
                # Create and broadcast forwarded beacon
                forwarded = self.forward_beacon(forward_beacon, sim_time)
                self.channel.broadcast(forwarded, sim_time)
                logging.log_info(f"Buoy {str(self.id)[:6]} forwarded beacon from {str(forward_beacon.origin_id)[:6]}, hops left: {forwarded.hop_limit}")
        elif self.want_to_send:
            # Normal transmission
            if self.channel.is_busy(self.position, sim_time):
                self.simulator.schedule_event(
                    sim_time + 0.01, EventType.CHANNEL_SENSE, self
                )
            else:
                self.state = BuoyState.WAITING_DIFS
                self.simulator.schedule_event(
                    sim_time + self.difs_time, EventType.DIFS_COMPLETION, self
                )

    def _handle_difs_completion(self, event, sim_time: float):
        if not self.want_to_send or self.state != BuoyState.WAITING_DIFS:
            return
            
        if self.channel.is_busy(self.position, sim_time):
            self.state = BuoyState.RECEIVING
            self.simulator.schedule_event(sim_time, EventType.CHANNEL_SENSE, self)
        else:
            backoff_slots = random.randint(0, self.cw - 1)
            backoff_time = backoff_slots * self.slot_time
            
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
        
        # Clear received neighbors after sending in append mode
        if self.multihop_mode == 'append':
            self.received_neighbors = []
        
        if success and self.metrics:
            latency = sim_time - self.scheduler_decision_time
            self.metrics.record_scheduler_latency(latency)

    def _handle_reception(self, event, sim_time: float):
        beacon = event.data.get("beacon")
        if not beacon:
            return
    
        collision = False
        collision_checked = event.data.get("collision_checked", False)
    
        if not collision_checked:
            COLLISION_WINDOW = 1e-5
            
            for tx_beacon, start, end, _, _ in self.channel.active_transmissions:
                if tx_beacon.sender_id == beacon.sender_id and tx_beacon.timestamp == beacon.timestamp:
                    continue
            
                if sim_time < start:
                    continue
                
                dx = self.position[0] - tx_beacon.position[0]
                dy = self.position[1] - tx_beacon.position[1]
                distance = math.hypot(dx, dy)
            
                if distance > self.comm_range_max:
                    continue
                
                propagation_delay = distance / self.speed_of_light
                arrival_time = end + propagation_delay
            
                if abs(arrival_time - sim_time) < COLLISION_WINDOW:
                    logging.log_error(f"Collision detected at receiver {str(self.id)[:6]} between {str(beacon.sender_id)[:6]} and {str(tx_beacon.sender_id)[:6]}")
                    collision = True
                    break
    
        if collision:
            return
        
        # Update direct neighbors (by sender_id)
        updated = False
        for i, (nid, _, _) in enumerate(self.neighbors):
            if nid == beacon.sender_id:
                self.neighbors[i] = (nid, sim_time, beacon.position)
                updated = True
                break
        if not updated:
            self.neighbors.append((beacon.sender_id, sim_time, beacon.position))
        
        # Extract node IDs from beacon's neighbor list
        neighbor_node_ids = [nid for nid, _, _ in beacon.neighbors]
        
        # Multihop append mode: collect neighbors from received beacon
        if self.multihop_mode == 'append':
            for neighbor_id, neighbor_ts, neighbor_pos in beacon.neighbors:
                if neighbor_id == self.id or neighbor_id == beacon.sender_id:
                    continue
                already_exists = any(nid == neighbor_id for nid, _, _ in self.received_neighbors)
                if not already_exists:
                    self.received_neighbors.append((neighbor_id, neighbor_ts, neighbor_pos))
        
        # Multihop forwarded mode: forward beacon if hop_limit > 0
        if self.multihop_mode == 'forwarded' and beacon.hop_limit > 0:
            beacon_key = (beacon.origin_id, beacon.timestamp)
            if beacon_key not in self.forwarded_beacons:
                self.forwarded_beacons.add(beacon_key)
                self.simulator.schedule_event(
                    sim_time + 0.001,
                    EventType.CHANNEL_SENSE,
                    self,
                    {"forward_beacon": beacon}
                )
        
        key = (self.id, beacon.sender_id, beacon.timestamp)
        if key not in self.channel.seen_attempts:
            self.channel.seen_attempts.add(key)
        
            for i, (tx_beacon, start, end, potential_count, processed_count) in enumerate(self.channel.active_transmissions):
                if tx_beacon.sender_id == beacon.sender_id and tx_beacon.timestamp == beacon.timestamp:
                    self.channel.active_transmissions[i] = (tx_beacon, start, end, potential_count, processed_count + 1)
                    break
        
            if self.metrics:
                # Log direct reception (sender)
                self.metrics.log_received(
                    sender_id=beacon.sender_id,
                    timestamp=beacon.timestamp,
                    receive_time=sim_time,
                    receiver_id=self.id
                )
                
                # Log nodes discovered from beacon's neighbor list
                if neighbor_node_ids:
                    self.metrics.log_nodes_discovered_from_neighbors(
                        receiver_id=self.id,
                        neighbor_ids=neighbor_node_ids
                    )
                
                # Track for delivery ratio
                self.metrics.log_actually_received(beacon.sender_id)

    def _handle_neighbor_cleanup(self, event, sim_time: float):
        self.neighbors = [
            (nid, ts, pos) for nid, ts, pos in self.neighbors
            if sim_time - ts <= self.neighbor_timeout
        ]
        
        # Also cleanup received neighbors in append mode
        if self.multihop_mode == 'append':
            self.received_neighbors = [
                (nid, ts, pos) for nid, ts, pos in self.received_neighbors
                if sim_time - ts <= self.neighbor_timeout
            ]
        
        self.simulator.schedule_event(
            sim_time + self.neighbor_timeout, EventType.NEIGHBOR_CLEANUP, self
        )

    def _handle_buoy_movement(self, event, sim_time: float):
        if not self.is_mobile:
            return
            
        dt = 0.1
        x, y = self.position
        vx, vy = self.velocity
        
        new_x = x + vx * dt
        new_y = y + vy * dt
        
        if new_x < 0 or new_x > self.world_width:
            self.velocity = (-vx, vy)
        if new_y < 0 or new_y > self.world_height:
            self.velocity = (vx, -vy)
            
        vx, vy = self.velocity
        self.position = (x + vx * dt, y + vy * dt)
        
        self.simulator.schedule_event(
            sim_time + dt, EventType.BUOY_MOVEMENT, self
        )
    
    def create_beacon(self, sim_time: float) -> Beacon:
        # Combine direct neighbors with received neighbors in append mode
        all_neighbors = self.neighbors.copy()
        
        if self.multihop_mode == 'append':
            for nid, ts, pos in self.received_neighbors:
                # Check if not already in all_neighbors
                if not any(existing_id == nid for existing_id, _, _ in all_neighbors):
                    all_neighbors.append((nid, ts, pos))
        
        # Forwarded mode fields
        origin_id = None
        hop_limit = 0
        
        if self.multihop_mode == 'forwarded':
            origin_id = self.id
            hop_limit = self.multihop_limit
        
        return Beacon(
            sender_id=self.id,
            mobile=self.is_mobile,
            position=self.position,
            battery=self.battery,
            neighbors=all_neighbors,
            timestamp=sim_time,
            origin_id=origin_id,
            hop_limit=hop_limit
        )
    
    def forward_beacon(self, original_beacon: Beacon, sim_time: float) -> Beacon:
        return Beacon(
            sender_id=self.id,  # Forwarder becomes sender
            mobile=original_beacon.mobile,  # Keep original's mobility status
            position=self.position,  # Use forwarder's position for range calc
            battery=self.battery,  # Forwarder's battery
            neighbors=original_beacon.neighbors,  # Original neighbors
            timestamp=original_beacon.timestamp,  # Keep original timestamp
            origin_id=original_beacon.origin_id,  # Keep origin ID
            hop_limit=original_beacon.hop_limit - 1  # Decrement hop limit
        )