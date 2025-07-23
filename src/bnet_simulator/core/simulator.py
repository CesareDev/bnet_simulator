import time
import heapq
import uuid
from typing import List, Dict, Tuple, Optional, Callable
import random
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.core.channel import Channel
from bnet_simulator.core.events import EventType
from bnet_simulator.utils import logging, config

class Event:
    def __init__(self, time: float, event_type: EventType, target_obj, data: Optional[Dict] = None):
        self.time = time
        self.event_type = event_type
        self.target_obj = target_obj
        self.data = data or {}
    
    def __repr__(self):
        target_id = getattr(self.target_obj, 'id', id(self.target_obj))
        return f"Event({self.time:.2f}, {self.event_type.name}, {str(target_id)[:6]})"

class Simulator:
    def __init__(self, buoys: List[Buoy], channel: Channel):
        self.buoys = buoys
        self.channel = channel
        self.channel.set_buoys(self.buoys)
        self.channel.simulator = self
        self.running = False
        self.simulated_time = 0.0
        
        for buoy in self.buoys:
            buoy.simulator = self
        
        self.event_queue = []
        self.event_counter = 0
        
        self._schedule_initial_events()

    def schedule_event(self, time: float, event_type: EventType, target_obj, data: Optional[Dict] = None) -> None:
        event = Event(time, event_type, target_obj, data)
        epsilon = self.event_counter * 1e-10
        self.event_counter += 1
        heapq.heappush(self.event_queue, (event.time + epsilon, self.event_counter, event))
    
    def _get_next_event(self) -> Optional[Event]:
        if not self.event_queue:
            return None
        _, _, event = heapq.heappop(self.event_queue)
        return event

    def _schedule_initial_events(self):
        for buoy in self.buoys:
            initial_offset = random.uniform(0, 1.0)
            self.schedule_event(initial_offset, EventType.SCHEDULER_CHECK, buoy)
            self.schedule_event(config.NEIGHBOR_TIMEOUT, EventType.NEIGHBOR_CLEANUP, buoy)
            
            if buoy.is_mobile:
                self.schedule_event(0.1, EventType.BUOY_MOVEMENT, buoy)
        
        self.schedule_event(1.0, EventType.CHANNEL_UPDATE, self.channel)

    def start(self):
        self.running = True
        real_time_start = time.time()
        
        try:
            while self.running and self.simulated_time < config.SIMULATION_DURATION:
                event = self._get_next_event()
                if not event:
                    logging.log_info("No more events to process.")
                    break
                
                self.simulated_time = event.time
                
                if event.event_type in [EventType.TRANSMISSION_START, EventType.RECEPTION]:
                    logging.log_info(f"Processing {event}")
                    
                if int(self.simulated_time) % 10 == 0 and self.simulated_time > 0:
                    logging.log_info(f"Time: {self.simulated_time:.2f}s, Event queue size: {len(self.event_queue)}")
                
                try:
                    event.target_obj.handle_event(event, self.simulated_time)
                except Exception as e:
                    logging.log_error(f"Error handling event {event}: {str(e)}")
                    
        except KeyboardInterrupt:
            logging.log_info("Simulation interrupted by user.")
            self.running = False
            
        real_time_end = time.time()
        real_duration = real_time_end - real_time_start
        sim_speedup = self.simulated_time / real_duration if real_duration > 0 else float('inf')
        logging.log_info(f"Simulation complete. {self.simulated_time:.2f}s simulated in {real_duration:.2f}s real time (speedup: {sim_speedup:.2f}x)")

    def __repr__(self):
        return f"<Simulator buoys={len(self.buoys)}>"