import time
from typing import List
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

        while self.running and self.simulated_time < config.SIMULATION_DURATION:
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

        self.window.quit()

    def update(self, dt: float):
        for buoy in self.buoys:
            buoy.update(dt=dt, sim_time=self.simulated_time)
        self.channel.clear()

    def log_buoys(self):
        for buoy in self.buoys:
            logging.log_info(buoy)

    def __repr__(self):
        return f"<Simulator buoys={self.buoys}>"
