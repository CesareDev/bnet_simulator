import time
from typing import List
import random
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.core.channel import Channel
from bnet_simulator.gui.window import Window
from bnet_simulator.utils import logging, config

class Simulator:
    def __init__(self, buoys: List[Buoy], channel: Channel):
        self.buoys = buoys
        self.channel = channel
        self.running = False
        self.simulated_time = 0.0
        self.window = Window()

    def start(self):
        self.running = True
        previous_time = time.time()
        dt = 1.0 / config.TARGET_FPS
        delta_real = dt

        while self.running and self.simulated_time < config.SIMULATION_DURATION and not self.window.should_close():

            self.window.poll_input()

            start_time = time.time()
            delta_real = start_time - previous_time
            previous_time = start_time
            self.simulated_time += delta_real
            
            self.update(delta_real)

            self.window.draw(self.buoys)

            elapsed_time = time.time() - start_time
            sleep_time = dt - elapsed_time
            if sleep_time > 0.0:
                time.sleep(sleep_time)

        self.window.close()

    def update(self, dt: float):
        self.channel.update(self.simulated_time)

        # Shuffle buoys for random order
        random.shuffle(self.buoys)

        # Update buoys
        for buoy in self.buoys:
            buoy.update_position(dt)
            buoy.send_beacon(dt, self.simulated_time)
            buoy.receive_beacon(self.simulated_time)
            buoy.cleanup_neighbors(self.simulated_time)

    def log_buoys(self):
        for buoy in self.buoys:
            logging.log_info(buoy)

    def __repr__(self):
        return f"<Simulator buoys={self.buoys}>"
