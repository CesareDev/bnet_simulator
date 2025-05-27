import pygame
from typing import List
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.utils import config

class Window:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("BNet Simulation")
        self.surface = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), pygame.RESIZABLE)
        self.running = True
        self.scale = min(config.WINDOW_WIDTH / config.WORLD_WIDTH, config.WINDOW_HEIGHT / config.WORLD_HEIGHT)
        self.font = pygame.font.SysFont("Arial", 14)
        self.margin_x = (config.WINDOW_WIDTH - config.WORLD_WIDTH * self.scale) / 2
        self.margin_y = (config.WINDOW_HEIGHT - config.WORLD_HEIGHT * self.scale) / 2
        self.dragging = False
        self.last_mouse_pos = None
        self.zoom_factor = 1.1
        self.min_scale = 0.1
        self.max_scale = 10.0


    def poll_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    self.dragging = True
                    self.last_mouse_pos = pygame.mouse.get_pos()

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging = False
                    self.last_mouse_pos = None

            elif event.type == pygame.MOUSEMOTION:
                if self.dragging and self.last_mouse_pos is not None:
                    current_mouse_pos = pygame.mouse.get_pos()
                    dx = current_mouse_pos[0] - self.last_mouse_pos[0]
                    dy = current_mouse_pos[1] - self.last_mouse_pos[1]
                    self.margin_x += dx
                    self.margin_y += dy
                    self.last_mouse_pos = current_mouse_pos

            elif event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                world_x = (mouse_x - self.margin_x) / self.scale
                world_y = (mouse_y - self.margin_y) / self.scale
                if event.y > 0:
                    new_scale = min(self.scale * self.zoom_factor, self.max_scale)
                else:
                    new_scale = max(self.scale / self.zoom_factor, self.min_scale)
                self.margin_x = mouse_x - world_x * new_scale
                self.margin_y = mouse_y - world_y * new_scale
                self.scale = new_scale

    def draw(self, buoys: List[Buoy]):
        self.surface.fill(config.BG_COLOR)

        for buoy in buoys:
            x, y = buoy.position
            screen_x = int(x * self.scale + self.margin_x)
            screen_y = int(y * self.scale + self.margin_y)
            screen_pos = (screen_x, screen_y)
            color = config.MOBILE_COLOR if buoy.is_mobile else config.FIXED_COLOR
            radius_px = int(buoy.range * self.scale)
            
            first_digit = str(buoy.id)[:6]  # Get the first digit of the buoy's ID
            text_surface = self.font.render(first_digit, True, (255, 255, 255))  # White text
                
            text_width = text_surface.get_width()
            text_height = text_surface.get_height()
            text_x = screen_x - text_width / 2  # Center text horizontally above the buoy
            text_y = screen_y - config.BUOY_RADIUS - text_height - 5  # 5 pixels above the buoy

            neighbors = buoy.neighbors[:config.MAX_NEIGHBORS_DISPLAYED]
            if len(neighbors) > 0:
                box_width = 60
                box_height = 15 * len(neighbors) + 5
                table_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
                table_surface.fill((0, 0, 0, 120))  # RGBA: semi-transparent black

                for i, (nid, _) in enumerate(neighbors):
                    label = self.font.render(str(nid)[:6], True, (255, 255, 255))
                    table_surface.blit(label, (5, 5 + i * 15))
                
                self.surface.blit(table_surface, (screen_x + config.BUOY_RADIUS + 10, screen_y - box_height // 2))

            pygame.draw.circle(self.surface, color, screen_pos, config.BUOY_RADIUS)
            pygame.draw.circle(self.surface, (150, 150, 150), screen_pos, radius_px, width=1)
            self.surface.blit(text_surface, (text_x, text_y))

        pygame.display.flip()

    def should_close(self) -> bool:
        return not self.running

    def close(self):
        pygame.quit()
