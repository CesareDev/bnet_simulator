from bnet_simulator.buoys.buoy import Buoy

class Vessel(Buoy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_vessel = True
        
    def send_beacon(self, dt: float, sim_time: float) -> bool:
        # Skip beacon sending completely
        return False