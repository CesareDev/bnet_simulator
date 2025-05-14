import pygame
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.utils.config import (
    WINDOW_SIZE,
    BUOY_RADIUS,
    BG_COLOR,
    MOBILE_COLOR,
    FIXED_COLOR,
)

class Window:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("BNet Simulation")

    def draw(self, buoys: list[Buoy]):
        self.screen.fill(BG_COLOR)
        for buoy in buoys:
            color = MOBILE_COLOR if buoy.is_mobile else FIXED_COLOR
            x, y = buoy.position
            # Scale to fit the screen (simple normalization)
            px = int(x * 5) + 100
            py = int(y * 5) + 100
            pygame.draw.circle(self.screen, color, (px, py), BUOY_RADIUS)
        pygame.display.flip()

    def quit(self):
        pygame.quit()
