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
        # Track which neighbor lines have been drawn
        drawn_pairs = set()
        
        for buoy in buoys:
            x, y = buoy.position
            screen_x = int(x * self.scale + self.margin_x)
            screen_y = int(y * self.scale + self.margin_y)
            screen_pos = (screen_x, screen_y)
            color = config.MOBILE_COLOR if buoy.is_mobile else config.FIXED_COLOR
        
            # Draw buoy
            pygame.draw.circle(self.surface, color, screen_pos, config.BUOY_RADIUS)
        
            # Draw max communication range as light circle
            max_range_px = int(config.COMMUNICATION_RANGE_MAX * self.scale)
            pygame.draw.circle(self.surface, (200, 200, 200), screen_pos, max_range_px, width=1)
        
            # Draw buoy ID above the buoy
            buoy_id_str = str(buoy.id)[:6]
            text_surface = self.font.render(buoy_id_str, True, (255, 255, 255))
            text_x = screen_x - text_surface.get_width() / 2
            text_y = screen_y - config.BUOY_RADIUS - text_surface.get_height() - 5
            self.surface.blit(text_surface, (text_x, text_y))
        
            # Draw neighbor table and yellow lines to neighbors
            neighbors = buoy.neighbors[:config.MAX_NEIGHBORS_DISPLAYED]
            if len(neighbors) > 0:
                # Neighbor table
                box_width = 60
                box_height = 15 * len(neighbors) + 5
                table_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
                table_surface.fill((0, 0, 0, 120))  # RGBA: semi-transparent black
        
                for i, (nid, _) in enumerate(neighbors):
                    label = self.font.render(str(nid)[:6], True, (255, 255, 255))
                    table_surface.blit(label, (5, 5 + i * 15))
        
                    # Draw neighbor lines without redundancy
                    if (buoy.id, nid) in drawn_pairs or (nid, buoy.id) in drawn_pairs:
                        continue
                    neighbor = next((b for b in buoys if b.id == nid), None)
                    if neighbor:
                        nx, ny = neighbor.position
                        screen_nx = int(nx * self.scale + self.margin_x)
                        screen_ny = int(ny * self.scale + self.margin_y)
                        pygame.draw.line(self.surface, (255, 255, 0), screen_pos, (screen_nx, screen_ny), width=1)
                        drawn_pairs.add((buoy.id, nid))
        
                self.surface.blit(table_surface, (screen_x + config.BUOY_RADIUS + 10, screen_y - box_height // 2))

        pygame.draw.rect(self.surface, (255, 0, 0), pygame.Rect(self.margin_x, self.margin_y, config.WORLD_WIDTH * self.scale, config.WORLD_HEIGHT * self.scale), width=1)
        pygame.display.flip()

    def should_close(self) -> bool:
        return not self.running

    def close(self):
        pygame.quit()
