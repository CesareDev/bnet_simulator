import time
from typing import List
import random
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.core.channel import Channel
from bnet_simulator.gui.window import Window
from bnet_simulator.utils.metrics import Metrics
from bnet_simulator.utils import logging, config

class Simulator:
    def __init__(self, buoys: List[Buoy], channel: Channel):
        self.buoys = buoys
        self.channel = channel
        self.channel.buoys = self.buoys
        self.running = False
        self.simulated_time = 0.0
        self.window = Window() if not config.HEADLESS else None
        
        # Store all original buoys for dynamic network changes
        self.all_buoys = buoys.copy()
        
        # Variables for network topology changes
        self.next_buoy_change = random.uniform(5, 15)
        self.first_change = True

    def start(self):
        self.running = True
        previous_time = time.time()
        dt = 1.0 / config.TARGET_FPS
        delta_real = dt
        
        try:
            while self.running and self.simulated_time < config.SIMULATION_DURATION:
                if not config.HEADLESS and self.window.should_close():
                    break

                if not config.HEADLESS:
                    self.window.poll_input()

                start_time = time.time()
                delta_real = start_time - previous_time
                previous_time = start_time
                self.simulated_time += delta_real

                self.update(delta_real)

                if not config.HEADLESS:
                    self.window.draw(self.buoys)

                elapsed_time = time.time() - start_time
                sleep_time = dt - elapsed_time
                if sleep_time > 0.0:
                    time.sleep(sleep_time)

            if not config.HEADLESS:
                self.window.close()
        except KeyboardInterrupt:
            logging.log_info("Simulation interrupted by user.")
            self.running = False

    def update(self, dt: float):
        self.update_buoy_array(dt)
        self.channel.update(self.simulated_time)

        # Shuffle for randomized processing order
        random.shuffle(self.buoys)

        for buoy in self.buoys:
            buoy.update_position(dt)
            buoy.send_beacon(dt, self.simulated_time)
            buoy.receive_beacon(self.simulated_time)
            buoy.cleanup_neighbors(self.simulated_time)

    def update_buoy_array(self, dt: float):
        self.next_buoy_change -= dt

        if self.next_buoy_change <= 0:
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
                    for buoy in buoys_to_remove:
                        if buoy in self.buoys:  # Safety check
                            self.buoys.remove(buoy)

                    logging.log_info(f"Removed {num_to_remove} buoys, now {len(self.buoys)} active")

                    if self.first_change:
                        logging.log_info("First buoy change: forced major removal operation")
                        self.first_change = False
            elif inactive_buoys:
                # ADD BUOYS
                max_to_add = min(len(inactive_buoys), max(2, int(total_buoys * 0.4)))  # Up to 40% of total
                
                num_to_add = max_to_add if max_to_add <= 2 else random.randint(1, max_to_add)

                buoys_to_add = random.sample(inactive_buoys, num_to_add)
                for buoy in buoys_to_add:
                    self.buoys.append(buoy)

                logging.log_info(f"Added {num_to_add} buoys, now {len(self.buoys)} active")
                self.first_change = False

            # Schedule next change (every 15-20 seconds)
            self.next_buoy_change = random.uniform(15, 20)

    def is_outside_world(self, buoy: Buoy) -> bool:
        x, y = buoy.position
        margin = config.COMMUNICATION_RANGE_MAX
        can_remove = x < -margin or x > config.WORLD_WIDTH + margin or y < -margin or y > config.WORLD_HEIGHT + margin
        if can_remove:
            logging.log_info(f"Removing buoy {str(buoy.id)[:6]} because it is outside world bounds")
        return can_remove

    def __repr__(self):
        return f"<Simulator buoys={self.buoys}>"