import time
import heapq
from typing import List, Dict, Optional
import random
from bnet_simulator.utils.metrics import Metrics
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
    def __init__(self, buoys: List[Buoy], channel: Channel, metrics: Metrics, ramp: bool = False):
        self.buoys = buoys
        self.channel = channel
        self.metrics = metrics
        self.ramp = ramp
        self.all_buoys = buoys.copy()
        self.first_change = True
        self.next_buoy_change = 0
        self.ramp_direction = 1  # 1 for increment, -1 for decrement

        # Start with only 2 buoys active if ramp scenario
        if ramp:
            self.buoys = self.all_buoys[:2]
        else:
            self.buoys = buoys

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
        
        # Schedule first buoy array update at 30 seconds
        self.schedule_event(30.0, EventType.BUOY_ARRAY_UPDATE, self)

    def update_buoy_array(self, event, sim_time: float):
        if self.ramp:
            self._update_buoy_array_ramp(sim_time)
        else:
            self._update_buoy_array_random(sim_time)

    def _update_buoy_array_random(self, sim_time: float):
        active_buoys = self.buoys.copy()
        inactive_buoys = [b for b in self.all_buoys if b not in active_buoys]
        total_buoys = len(self.all_buoys)

        # First change always removes buoys, after that randomize add/remove
        if self.first_change or (random.random() >= 0.5 and len(active_buoys) > max(3, int(total_buoys * 0.2))):
            # REMOVE BUOYS
            min_buoys = max(3, int(total_buoys * 0.2))  # Ensure 20% minimum remain

            if len(active_buoys) > min_buoys:
                # 40-50% removal rate
                remove_percentage = 0.5 if self.first_change else 0.4
                max_to_remove = min(len(active_buoys) - min_buoys, 
                                  max(2, int(total_buoys * remove_percentage)))
                
                num_to_remove = max_to_remove if max_to_remove <= 2 else random.randint(1, max_to_remove)
                buoys_to_remove = random.sample(active_buoys, num_to_remove)
                
                # Remove these buoys
                for buoy in buoys_to_remove:
                    if buoy in self.buoys:  # Safety check
                        self.buoys.remove(buoy)
                        logging.log_info(f"Removed buoy {str(buoy.id)[:6]} at {sim_time:.2f}s")

                # Update channel with new buoy list
                self.channel.set_buoys(self.buoys)
                logging.log_info(f"Removed {num_to_remove} buoys, now {len(self.buoys)} active at {sim_time:.2f}s")

                if self.first_change:
                    logging.log_info("First buoy change: forced major removal operation")
                    self.first_change = False
        elif inactive_buoys:
            # ADD BUOYS
            max_to_add = min(len(inactive_buoys), max(2, int(total_buoys * 0.4)))  # Up to 40% of total
            
            num_to_add = max_to_add if max_to_add <= 2 else random.randint(1, max_to_add)
            buoys_to_add = random.sample(inactive_buoys, num_to_add)
            
            # Add these buoys
            for buoy in buoys_to_add:
                self.buoys.append(buoy)
                # Make sure the buoy knows about this simulator
                buoy.simulator = self
                # Schedule initial events for this buoy
                initial_offset = random.uniform(0, 1.0) 
                self.schedule_event(sim_time + initial_offset, EventType.SCHEDULER_CHECK, buoy)
                self.schedule_event(sim_time + config.NEIGHBOR_TIMEOUT, EventType.NEIGHBOR_CLEANUP, buoy)
                if hasattr(buoy, 'is_mobile') and buoy.is_mobile:
                    self.schedule_event(sim_time + 0.1, EventType.BUOY_MOVEMENT, buoy)
                
                logging.log_info(f"Added buoy {str(buoy.id)[:6]} at {sim_time:.2f}s")
                
            # Update channel with new buoy list
            self.channel.set_buoys(self.buoys)
            logging.log_info(f"Added {num_to_add} buoys, now {len(self.buoys)} active at {sim_time:.2f}s")
            self.first_change = False

        # Schedule next change (every 15-20 seconds)
        next_change_time = sim_time + random.uniform(15, 20)
        self.schedule_event(next_change_time, EventType.BUOY_ARRAY_UPDATE, self)

    def _update_buoy_array_ramp(self, sim_time: float):
        active_buoys = self.buoys.copy()
        inactive_buoys = [b for b in self.all_buoys if b not in active_buoys]
        current_count = len(active_buoys)
        total_buoys = len(self.all_buoys)
        buoys_to_add = total_buoys - 2
        duration = config.SIMULATION_DURATION
        add_interval = duration / (2 * buoys_to_add) if buoys_to_add > 0 else duration  # 2x for up+down

        if self.ramp_direction == 1:  # Incrementing
            if current_count < total_buoys:
                if inactive_buoys:
                    buoy = inactive_buoys[0]
                    self.buoys.append(buoy)
                    buoy.simulator = self
                    initial_offset = random.uniform(0, 1.0)
                    self.schedule_event(sim_time + initial_offset, EventType.SCHEDULER_CHECK, buoy)
                    self.schedule_event(sim_time + config.NEIGHBOR_TIMEOUT, EventType.NEIGHBOR_CLEANUP, buoy)
                self.channel.set_buoys(self.buoys)
                self.schedule_event(sim_time + add_interval, EventType.BUOY_ARRAY_UPDATE, self)
            else:
                # Switch to decrementing
                self.ramp_direction = -1
                self.schedule_event(sim_time + add_interval, EventType.BUOY_ARRAY_UPDATE, self)
        else:  # Decrementing
            if current_count > 2:
                buoy = active_buoys[-1]
                self.buoys.remove(buoy)
                self.channel.set_buoys(self.buoys)
                self.schedule_event(sim_time + add_interval, EventType.BUOY_ARRAY_UPDATE, self)
            # When reaching 2, stop scheduling further changes

    def handle_event(self, event, sim_time: float):
        if event.event_type == EventType.BUOY_ARRAY_UPDATE:
            self.update_buoy_array(event, sim_time)

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
                    # Direct events to the simulator itself if target is self
                    if event.target_obj == self:
                        self.handle_event(event, self.simulated_time)
                    else:
                        event.target_obj.handle_event(event, self.simulated_time)
                except Exception as e:
                    logging.log_error(f"Error handling event {event}: {str(e)}")
                
                if self.ramp and int(self.simulated_time) % 5 == 0 and self.simulated_time > 0:
                    self.metrics.log_timepoint(self.simulated_time, len(self.buoys))

        except KeyboardInterrupt:
            logging.log_info("Simulation interrupted by user.")
            self.running = False
            
        real_time_end = time.time()
        real_duration = real_time_end - real_time_start
        sim_speedup = self.simulated_time / real_duration if real_duration > 0 else float('inf')
        logging.log_info(f"Simulation complete. {self.simulated_time:.2f}s simulated in {real_duration:.2f}s real time (speedup: {sim_speedup:.2f}x)")

    def __repr__(self):
        return f"<Simulator buoys={len(self.buoys)}>"