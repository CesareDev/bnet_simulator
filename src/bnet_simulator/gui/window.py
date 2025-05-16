import pygame
import re
from typing import List, Tuple
from bnet_simulator.buoys.buoy import Buoy
from bnet_simulator.utils import config

ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class Window:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("BNet Simulation")
        self.surface = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), pygame.RESIZABLE)
        self.running = True
        self.font = pygame.font.SysFont("Arial", 14)

        self.log_lines: List[str, Tuple[int, int, int]] = []
        self.max_log_lines = config.LOG_PANEL_HEIGHT // self.font.get_height()

        self.update_scale()

    def update_scale(self):
        width, height = self.surface.get_size()
        usable_height = height - config.LOG_PANEL_HEIGHT
        self.scale = min(width / config.WORLD_WIDTH, usable_height / config.WORLD_HEIGHT)
        self.margin_x = (width - config.WORLD_WIDTH * self.scale) / 2
        self.margin_y = (usable_height - config.WORLD_HEIGHT * self.scale) / 2

    def poll_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.surface = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                self.update_scale()

    def add_log(self, text: str):
        # Parse log level from text and store as (color, message)
        if "] [INFO]" in text:
            color = (100, 255, 100)
        elif "] [DEBUG]" in text:
            color = (100, 100, 255)
        elif "] [WARNING]" in text:
            color = (255, 200, 100)
        elif "] [ERROR]" in text:
            color = (255, 100, 100)
        elif "] [CRITICAL]" in text:
            color = (255, 100, 255)
        else:
            color = (220, 220, 220)

        clean_text = ANSI_ESCAPE.sub('', text)
        self.log_lines.append((clean_text, color))
        if len(self.log_lines) > self.max_log_lines:
            self.log_lines.pop(0)

    def draw_log_panel(self):
        width, height = self.surface.get_size()
        panel_rect = pygame.Rect(0, height - config.LOG_PANEL_HEIGHT, width, config.LOG_PANEL_HEIGHT)
        pygame.draw.rect(self.surface, (30, 30, 30), panel_rect)

        for i, (line, color) in enumerate(self.log_lines[-self.max_log_lines:]):
            rendered = self.font.render(line, True, color)
            self.surface.blit(rendered, (10, height - config.LOG_PANEL_HEIGHT + i * self.font.get_height()))

    def draw(self, buoys: List[Buoy]):
        self.surface.fill(config.BG_COLOR)

        for buoy in buoys:
            x, y = buoy.position
            screen_x = int(x * self.scale + self.margin_x)
            screen_y = int(y * self.scale + self.margin_y)
            screen_pos = (screen_x, screen_y)
            color = config.MOBILE_COLOR if buoy.is_mobile else config.FIXED_COLOR
            radius_px = int(config.COMMUNICATION_RANGE * self.scale)

            # Draw communication radius
            pygame.draw.circle(self.surface, (150, 150, 150), screen_pos, radius_px, width=1)
            pygame.draw.circle(self.surface, color, screen_pos, config.BUOY_RADIUS)

            # Draw ID label
            first_digit = str(buoy.id)[:6]
            text_surface = self.font.render(first_digit, True, (255, 255, 255))
            text_width = text_surface.get_width()
            text_height = text_surface.get_height()
            text_x = screen_x - text_width / 2
            text_y = screen_y - config.BUOY_RADIUS - text_height - 5
            self.surface.blit(text_surface, (text_x, text_y))

            # Draw neighbor table
            neighbors = buoy.neighbors[:config.MAX_NEIGHBORS_DISPLAYED]
            if neighbors:
                box_width = 60
                box_height = 15 * len(neighbors) + 5
                table_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
                table_surface.fill((0, 0, 0, 120))  # Semi-transparent

                for i, (nid, _) in enumerate(neighbors):
                    label = self.font.render(str(nid)[:6], True, (255, 255, 255))
                    table_surface.blit(label, (5, 5 + i * 15))

                self.surface.blit(table_surface, (screen_x + config.BUOY_RADIUS + 10, screen_y - box_height // 2))

        self.draw_log_panel()
        pygame.display.flip()

    def should_close(self) -> bool:
        return not self.running

    def close(self):
        pygame.quit()
