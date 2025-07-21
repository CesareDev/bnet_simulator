import time
import heapq
import uuid
from typing import List, Dict, Tuple, Optional, Callable
import random
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.core.channel import Channel
from bnet_simulator.core.events import EventType  # Import from new events module
from bnet_simulator.utils import logging, config

class Event:
    def __init__(self, time: float, event_type: EventType, target_obj, data: Optional[Dict] = None):
        self.time = time
        self.event_type = event_type
        self.target_obj = target_obj  # Object that will handle this event
        self.data = data or {}
    
    def __repr__(self):
        target_id = getattr(self.target_obj, 'id', id(self.target_obj))
        return f"Event({self.time:.2f}, {self.event_type.name}, {str(target_id)[:6]})"

class Simulator:
    def __init__(self, buoys: List[Buoy], channel: Channel):
        self.buoys = buoys
        self.channel = channel
        self.channel.set_buoys(self.buoys)
        self.channel.simulator = self  # Allow channel to schedule events
        self.running = False
        self.simulated_time = 0.0
        
        # Set simulator reference in all buoys
        for buoy in self.buoys:
            buoy.simulator = self  # Allow buoys to schedule events
        
        # Event queue (priority queue for events)
        self.event_queue = []
        self.event_counter = 0  # Used to ensure FIFO for same-time events
        
        # Schedule initial events
        self._schedule_initial_events()

    def schedule_event(self, time: float, event_type: EventType, target_obj, data: Optional[Dict] = None) -> None:
        """Schedule a new event to be processed"""
        event = Event(time, event_type, target_obj, data)
        epsilon = self.event_counter * 1e-10  # Small value to maintain FIFO for same-time events
        self.event_counter += 1
        heapq.heappush(self.event_queue, (event.time + epsilon, self.event_counter, event))
    
    def _get_next_event(self) -> Optional[Event]:
        """Get the next event from the queue"""
        if not self.event_queue:
            return None
        _, _, event = heapq.heappop(self.event_queue)
        return event

    def _schedule_initial_events(self):
        """Schedule the initial events to start the simulation"""
        # Schedule initial events for each buoy
        for buoy in self.buoys:
            # Initial scheduler check with random offset to prevent synchronization
            initial_offset = random.uniform(0, 1.0)
            self.schedule_event(initial_offset, EventType.SCHEDULER_CHECK, buoy)
            
            # Initial neighbor cleanup
            self.schedule_event(config.NEIGHBOR_TIMEOUT, EventType.NEIGHBOR_CLEANUP, buoy)
            
            # Schedule movement updates for mobile buoys
            if buoy.is_mobile:
                self.schedule_event(0.1, EventType.BUOY_MOVEMENT, buoy)
        
        # Schedule first channel update
        self.schedule_event(1.0, EventType.CHANNEL_UPDATE, self.channel)

    def start(self):
        """Start the simulation with event-driven approach"""
        self.running = True
        real_time_start = time.time()
        
        try:
            # Main event loop
            while self.running and self.simulated_time < config.SIMULATION_DURATION:
                # Get next event
                event = self._get_next_event()
                if not event:
                    logging.log_info("No more events to process.")
                    break
                
                # Update simulation time to event time
                self.simulated_time = event.time
                
                # Dispatch the event to the target object
                if hasattr(event.target_obj, 'handle_event'):
                    event.target_obj.handle_event(event, self.simulated_time)
                else:
                    logging.log_error(f"Target object has no handle_event method: {event.target_obj}")
                
        except KeyboardInterrupt:
            logging.log_info("Simulation interrupted by user.")
            self.running = False
            
        # Report simulation performance
        real_time_end = time.time()
        real_duration = real_time_end - real_time_start
        sim_speedup = self.simulated_time / real_duration if real_duration > 0 else float('inf')
        logging.log_info(f"Simulation complete. {self.simulated_time:.2f}s simulated in {real_duration:.2f}s real time (speedup: {sim_speedup:.2f}x)")

    def __repr__(self):
        return f"<Simulator buoys={len(self.buoys)}>"