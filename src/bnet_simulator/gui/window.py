import pygame
from typing import List
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.utils import config

class Window:
    def __init__(self):
        pygame.init()
        self.surface = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        pygame.display.set_caption("BNet Simulation")
        self.running = True
        self.scale = min(config.WINDOW_WIDTH / config.WORLD_WIDTH, config.WINDOW_HEIGHT / config.WORLD_HEIGHT)
        self.font = pygame.font.SysFont("Arial", 14)

    def poll_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def draw(self, buoys: List[Buoy]):
        self.surface.fill(config.BG_COLOR)

        for buoy in buoys:
            x, y = buoy.position
            screen_x = int(x * self.scale)
            screen_y = int(y * self.scale)
            screen_pos = (screen_x, screen_y)
            color = config.MOBILE_COLOR if buoy.is_mobile else config.FIXED_COLOR
            radius_px = int(config.COMMUNICATION_RANGE * self.scale)
            
            first_digit = str(buoy.id)[:6]  # Get the first digit of the buoy's ID
            text_surface = self.font.render(first_digit, True, (255, 255, 255))  # White text
                
            text_width = text_surface.get_width()
            text_height = text_surface.get_height()
            text_x = screen_x - text_width / 2  # Center text horizontally above the buoy
            text_y = screen_y - config.BUOY_RADIUS - text_height - 5  # 5 pixels above the buoy

            pygame.draw.circle(self.surface, color, screen_pos, config.BUOY_RADIUS)
            pygame.draw.circle(self.surface, (150, 150, 150), screen_pos, radius_px, width=1)
            self.surface.blit(text_surface, (text_x, text_y))

        pygame.display.flip()

    def should_close(self) -> bool:
        return not self.running

    def close(self):
        pygame.quit()
