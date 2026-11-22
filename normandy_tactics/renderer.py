"""Top-down action-shooter renderer with scrolling camera and readable combat HUD."""

from __future__ import annotations

import math

import pygame

from .actors import Soldier, WEAPONS
from .battle import PLAYER_NAMES, Battle
from .campaigns import CAMPAIGNS
from .settings import BLUE, GOLD, GREEN, HEIGHT, HUD_H, INK, MUTED, PAPER, PANEL, PANEL_LIGHT, RED, TERRAIN, TILE, TOP_H, WHITE, WIDTH


class Renderer:
    EDITOR_PALETTE = ("field", "road", "sand", "trench", "crater", "wire", "hedge",
                      "building", "water", "rubble")

    def __init__(self) -> None:
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("NORMANDY: FRONTLINE")
        self.font = pygame.font.Font(None, 23)
        self.small = pygame.font.Font(None, 18)
        self.big = pygame.font.Font(None, 72)
        self.font_cache: dict[int, pygame.font.Font] = {}
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.menu_rects: list[pygame.Rect] = []
        self.inventory_rects: list[pygame.Rect] = []
        self.squad_rects: list[pygame.Rect] = []
        self._active_battle: Battle | None = None
        self.dev_trigger_rect = pygame.Rect(0, 0, 0, 0)
        self.menu_rifle_cache: tuple[tuple[int, int], pygame.Surface, pygame.Rect] | None = None
        self.continue_rect = pygame.Rect(0, 0, 0, 0)
        self.map_editor_rect = pygame.Rect(0, 0, 0, 0)
        self.pause_action_rects: list[tuple[str, pygame.Rect]] = []
        self.combat_effects = True
        self.mouse_screen = (WIDTH // 2, HEIGHT // 2)
        screen_w, screen_h = self.screen.get_size()
        initial_scale = max(0.65, min(1.0, screen_w / WIDTH, screen_h / HEIGHT))
        self._draw_menu_rifle(screen_w, screen_h, initial_scale)

    def _text(self, value: str, pos: tuple[int, int], size: int = 20, color: tuple[int, int, int] = PAPER,
              anchor: str = "topleft", font: pygame.font.Font | None = None) -> pygame.Rect:
        if font is None:
            size = max(10, size)
            font = self.font_cache.get(size)
            if font is None:
                font = pygame.font.Font(None, size)
                self.font_cache[size] = font
        surface = font.render(value, True, color)
        rect = surface.get_rect()
        setattr(rect, anchor, pos)
        self.screen.blit(surface, rect)
        return rect

    def _fit_text(self, value: str, max_width: int, size: int) -> str:
        """Trim UI labels to their allocated width before drawing them."""
        font = self.font_cache.get(size)
        if font is None:
            font = pygame.font.Font(None, size)
            self.font_cache[size] = font
        if font.size(value)[0] <= max_width:
            return value
        suffix = "…"
        while value and font.size(value + suffix)[0] > max_width:
            value = value[:-1]
        return value.rstrip() + suffix

    def _update_camera(self, battle: Battle, dt: float) -> None:
        w, h = self.screen.get_size()
        view_h = h - TOP_H - HUD_H
        target_x, target_y = ((battle.active_emplacement.x, battle.active_emplacement.y)
                      if battle.active_emplacement else (battle.player.x, battle.player.y))
        desired_x = target_x * TILE - w / 2
        desired_y = target_y * TILE - (TOP_H + view_h / 2)
        self.camera_x += (desired_x - self.camera_x) * min(1.0, dt * 5.2)
        self.camera_y += (desired_y - self.camera_y) * min(1.0, dt * 5.2)
        self.camera_x = max(0.0, min(self.camera_x, battle.world.width * TILE - w))
        self.camera_y = max(0.0, min(self.camera_y, battle.world.height * TILE - view_h))

    def mouse_world(self, mouse: tuple[int, int]) -> tuple[float, float]:
        return ((mouse[0] + self.camera_x) / TILE, (mouse[1] - TOP_H + self.camera_y) / TILE)

    def _draw_menu_rifle(self, width: int, height: int, scale: float) -> None:
        size = (width, height)
        if self.menu_rifle_cache and self.menu_rifle_cache[0] == size:
            layer, trigger = self.menu_rifle_cache[1:]
            self.screen.blit(layer, (0, 0))
            self.dev_trigger_rect = trigger.copy()
            return
        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        center_y = int(height * 0.80)
        thick = max(4, round(8 * scale))
        tone = (179, 167, 130, 105)
        stock_left, stock_right = int(width * 0.08), int(width * 0.30)
        receiver_left, receiver_right = int(width * 0.30), int(width * 0.52)
        muzzle_x = int(width * 0.92)

        pygame.draw.polygon(layer, tone, [
            (stock_left, center_y - thick), (stock_right, center_y - thick // 2),
            (stock_right, center_y + thick // 2), (stock_left, center_y + thick),
        ])
        pygame.draw.rect(layer, tone, (receiver_left, center_y - thick, receiver_right - receiver_left,
                                       thick * 2), border_radius=thick // 2)
        pygame.draw.line(layer, tone, (receiver_right - 2, center_y), (muzzle_x, center_y), thick)
        pygame.draw.rect(layer, (143, 137, 108, 105),
                         (int(width * 0.53), center_y - thick // 2, int(width * 0.16), thick * 2),
                         border_radius=thick // 2)
        pygame.draw.line(layer, tone, (int(width * 0.84), center_y - thick),
                         (int(width * 0.84), center_y + thick), max(2, round(3 * scale)))
        pygame.draw.polygon(layer, tone, [
            (int(width * 0.38), center_y + thick), (int(width * 0.47), center_y + thick),
            (int(width * 0.45), center_y + round(29 * scale)),
            (int(width * 0.39), center_y + round(29 * scale)),
        ])
        trigger_x = int(width * 0.475)
        trigger_y = center_y + round(8 * scale)
        trigger_size = max(12, round(22 * scale))
        pygame.draw.arc(layer, (199, 183, 142, 115),
                        pygame.Rect(trigger_x - trigger_size // 2, trigger_y - trigger_size // 2,
                                    trigger_size, trigger_size), 0, math.pi, max(2, round(2 * scale)))
        pygame.draw.line(layer, (199, 183, 142, 115),
                         (trigger_x, trigger_y), (trigger_x + round(3 * scale), trigger_y + round(7 * scale)),
                         max(2, round(2 * scale)))
        self.dev_trigger_rect = pygame.Rect(trigger_x - round(11 * scale), trigger_y - round(5 * scale),
                                           round(22 * scale), round(20 * scale))
        self.menu_rifle_cache = (size, layer, self.dev_trigger_rect.copy())
        self.screen.blit(layer, (0, 0))

    def draw_title(self, completed_missions: set[int] | None = None, dev_unlock_all: bool = False,
                   campaign_stats: dict[str, int] | None = None) -> None:
        w, h = self.screen.get_size()
        completed = completed_missions or set()
        scale = max(0.65, min(1.0, w / WIDTH, h / HEIGHT))
        px = lambda value: max(1, round(value * scale))
        self.screen.fill(INK)
        pygame.draw.rect(self.screen, (47, 66, 56), (0, h // 2, w, h // 2))
        for x in range(0, w, px(44)):
            pygame.draw.line(self.screen, (57, 78, 64), (x, h // 2), (x - px(120), h), 1)
        self._draw_menu_rifle(w, h, scale)
        self._text("NORMANDY", (w // 2, px(94)), px(74), PAPER, "midtop")
        self._text("FRONTLINE", (w // 2, px(163)), px(38), GOLD, "midtop")
        self._text("A real-time squad action campaign • June 1944", (w // 2, px(208)), px(23), MUTED, "midtop")
        self._text("YOU are the rifleman. Your squad fights beside you.", (w // 2, px(247)), px(22), PAPER, "midtop")
        self._text("WASD MOVE   /   MOUSE AIM + FIRE   /   SHIFT SPRINT   /   R RELOAD",
                   (w // 2, px(282)), px(18), GOLD, "midtop")
        self._text("Campaign modes: capture • holdout • demolition", 
                   (w // 2, px(309)), px(16), MUTED, "midtop")
        self.menu_rects = []
        start_y = px(335)
        for i, mission in enumerate(CAMPAIGNS):
            col, row = i // 4, i % 4
            rect = pygame.Rect(w // 2 - px(390) + col * px(395), start_y + row * px(64),
                               px(375), px(52))
            unlocked = dev_unlock_all or i == 0 or i - 1 in completed
            finished = i in completed
            fill = PANEL_LIGHT if unlocked else (31, 37, 35)
            border = GOLD if finished else GREEN if unlocked else (67, 69, 61)
            pygame.draw.rect(self.screen, fill, rect, border_radius=px(5))
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=px(5))
            title_color = PAPER if unlocked else (112, 116, 105)
            self._text(self._fit_text(f"{i + 1:02}  {mission.title}", rect.width - px(25), px(19)),
                       (rect.x + px(14), rect.y + px(5)), px(19), title_color)
            status = "CLEARED" if finished else "READY" if unlocked else "LOCKED"
            status_size = px(13)
            status_width = pygame.font.Font(None, status_size).size(status)[0]
            location_width = rect.width - px(30) - status_width - px(14)
            location = self._fit_text(f"{mission.location} · {mission.mode.upper()}", location_width, px(14))
            self._text(location, (rect.x + px(15), rect.y + px(30)), px(14),
                       MUTED if unlocked else (91, 94, 86))
            status_color = GOLD if finished else GREEN if unlocked else (126, 111, 92)
            self._text(status, (rect.right - px(12), rect.y + px(30)), status_size, status_color, "topright")
            self.menu_rects.append(rect)
        stats = campaign_stats or {"victories": len(completed), "attempts": 0, "kills": 0}
        footer = (f"AUTO-SAVED  •  {len(completed)}/{len(CAMPAIGNS)} CLEARED  •  "
              f"{stats.get('victories', 0)} VICTORIES  •  CLICK A FRONT")
        self._text(self._fit_text(footer, w - px(210), px(14)),
               (px(18), h - px(22)), px(14), MUTED, "bottomleft")
        self.map_editor_rect = pygame.Rect(w - px(174), h - px(50), px(156), px(36))
        pygame.draw.rect(self.screen, PANEL_LIGHT, self.map_editor_rect, border_radius=4)
        pygame.draw.rect(self.screen, GOLD, self.map_editor_rect, 1, border_radius=4)
        self._text("MAP EDITOR [M]", self.map_editor_rect.center, px(14), GOLD, "center")

    def _draw_tile(self, tx: int, ty: int, tile: str, rect: pygame.Rect,
                   damage_ratio: float = 0.0, elevation: int = 0, orientation: float = 0.0,
                   connections: tuple[bool, bool, bool, bool] = (False, False, False, False)) -> None:
        color = TERRAIN[tile]
        if elevation and tile in {"field", "sand", "road"}:
            lift = 9 * elevation
            color = tuple(min(255, channel + lift) for channel in color)
        pygame.draw.rect(self.screen, color, rect)
        if elevation:
            ledge = (65, 66, 54) if elevation == 1 else (48, 53, 48)
            pygame.draw.line(self.screen, ledge, rect.topleft, rect.topright, 2)
        seed = (tx * 92821 + ty * 68917) & 0xFFFF
        if tile in {"field", "sand"}:
            accent = tuple(min(255, component + 14) for component in color)
            for i in range(3):
                dot = (rect.x + 4 + ((seed >> (i * 3)) & 23), rect.y + 4 + ((seed >> (i * 4 + 2)) & 23))
                pygame.draw.circle(self.screen, accent, dot, 1)
        elif tile == "water":
            pygame.draw.arc(self.screen, (92, 134, 144), rect.inflate(-7, -16), 0.2, 2.8, 1)
        elif tile == "hedge":
            pygame.draw.ellipse(self.screen, (36, 57, 34), rect.inflate(-3, -5))
            dx, dy = math.cos(orientation), math.sin(orientation)
            pygame.draw.line(self.screen, (74, 94, 55),
                             (round(rect.centerx - dx * 8), round(rect.centery - dy * 8)),
                             (round(rect.centerx + dx * 8), round(rect.centery + dy * 8)), 4)
            pygame.draw.circle(self.screen, (89, 105, 61),
                               (round(rect.centerx - dx * 5), round(rect.centery - dy * 5)), 4)
        elif tile == "wire":
            dx, dy = math.cos(orientation), math.sin(orientation)
            center = rect.center
            start = (round(center[0] - dx * 12), round(center[1] - dy * 12))
            end = (round(center[0] + dx * 12), round(center[1] + dy * 12))
            pygame.draw.line(self.screen, (43, 42, 37), start, end, 2)
            for connected, edge in zip(connections, (rect.midtop, rect.midright, rect.midbottom, rect.midleft)):
                if connected:
                    pygame.draw.line(self.screen, (43, 42, 37), center, edge, 2)
            for offset in (-8, 0, 8):
                x, y = center[0] + dx * offset, center[1] + dy * offset
                pygame.draw.line(self.screen, (180, 157, 114),
                                 (round(x - dy * 4), round(y + dx * 4)),
                                 (round(x + dy * 4), round(y - dx * 4)), 1)
        elif tile in {"building", "wall"}:
            pygame.draw.rect(self.screen, (72, 70, 61), rect.inflate(-4, -4), border_radius=2)
            if tile == "building":
                pygame.draw.rect(self.screen, (172, 151, 119), (rect.x + 9, rect.y + 8, 7, 6))
                dx, dy = math.cos(orientation), math.sin(orientation)
                pygame.draw.line(self.screen, (57, 55, 48),
                                 (round(rect.centerx - dx * 12), round(rect.centery - dy * 12)),
                                 (round(rect.centerx + dx * 12), round(rect.centery + dy * 12)), 2)
            else:
                dx, dy = math.cos(orientation), math.sin(orientation)
                pygame.draw.line(self.screen, (112, 106, 91),
                                 (round(rect.centerx - dx * 11), round(rect.centery - dy * 11)),
                                 (round(rect.centerx + dx * 11), round(rect.centery + dy * 11)), 2)
        elif tile == "obstacle":
            for angle in (orientation + math.pi / 4, orientation - math.pi / 4):
                dx, dy = math.cos(angle) * 13, math.sin(angle) * 13
                pygame.draw.line(self.screen, (70, 67, 59),
                                 (round(rect.centerx - dx), round(rect.centery - dy)),
                                 (round(rect.centerx + dx), round(rect.centery + dy)), 4)
        elif tile == "crater":
            pygame.draw.ellipse(self.screen, (53, 61, 46), rect.inflate(-7, -9))
            dx, dy = math.cos(orientation) * 8, math.sin(orientation) * 8
            pygame.draw.line(self.screen, (133, 127, 95),
                             (round(rect.centerx - dx), round(rect.centery - dy)),
                             (round(rect.centerx + dx), round(rect.centery + dy)), 2)
        elif tile == "trench":
            dx, dy = math.cos(orientation) * 12, math.sin(orientation) * 12
            center = rect.center
            pygame.draw.line(self.screen, (39, 49, 37),
                             (round(center[0] - dx), round(center[1] - dy)),
                             (round(center[0] + dx), round(center[1] + dy)), 7)
            for connected, edge in zip(connections, (rect.midtop, rect.midright, rect.midbottom, rect.midleft)):
                if connected:
                    pygame.draw.line(self.screen, (39, 49, 37), center, edge, 7)
        elif tile == "rock":
            dx, dy = math.cos(orientation), math.sin(orientation)
            pygame.draw.polygon(self.screen, (78, 80, 72), [
                (round(rect.centerx - dx * 10 + dy * 8), round(rect.centery - dy * 10 - dx * 8)),
                (round(rect.centerx + dx * 12), round(rect.centery + dy * 12)),
                (round(rect.centerx - dx * 10 - dy * 8), round(rect.centery - dy * 10 + dx * 8)),
            ])
        elif tile == "sandbag":
            dx, dy = math.cos(orientation), math.sin(orientation)
            for row in range(2):
                offset = row * 6 - 3
                center_x = rect.centerx - dy * offset
                center_y = rect.centery + dx * offset
                start = (round(center_x - dx * 12), round(center_y - dy * 12))
                end = (round(center_x + dx * 12), round(center_y + dy * 12))
                pygame.draw.line(self.screen, (154, 134, 91), start, end, 7)
                pygame.draw.line(self.screen, (93, 82, 61),
                                 (round(start[0] + dy * 3), round(start[1] - dx * 3)),
                                 (round(end[0] + dy * 3), round(end[1] - dx * 3)), 1)
        elif tile == "rubble":
            dx, dy = math.cos(orientation), math.sin(orientation)
            rubble_points = ((-12, 9), (-7, -4), (0, 10), (7, -8), (12, 8))
            pygame.draw.polygon(self.screen, (116, 105, 79), [
                (round(rect.centerx + px * dx - py * dy),
                 round(rect.centery + px * dy + py * dx))
                for px, py in rubble_points
            ])
        if damage_ratio > 0.18:
            crack_color = (43, 42, 35)
            crack_count = 1 + int(damage_ratio * 3)
            for crack in range(crack_count):
                offset = 5 + ((tx * 13 + ty * 7 + crack * 11) % max(8, TILE - 10))
                pygame.draw.line(self.screen, crack_color,
                                 (rect.left + offset, rect.top + 3),
                                 (rect.left + max(3, offset - 5), rect.centery), 1)
                pygame.draw.line(self.screen, crack_color,
                                 (rect.left + max(3, offset - 5), rect.centery),
                                 (rect.left + offset + 2, rect.bottom - 3), 1)

    def _draw_soldier(self, soldier: Soldier) -> None:
        view_bottom = self.screen.get_height() - HUD_H
        px = int(soldier.x * TILE - self.camera_x)
        elevation = self._active_battle.world.elevation_at(soldier.x, soldier.y) if self._active_battle else 0
        py = int(TOP_H + soldier.y * TILE - self.camera_y - elevation * 5)
        if px < -16 or py < TOP_H - 16 or px > self.screen.get_width() + 16 or py > view_bottom + 16:
            return
        if soldier.role == "tank":
            self._draw_tank(soldier, px, py)
            return
        player = soldier.player
        color = RED if soldier.faction == "german" else GREEN if soldier.faction == "us" else BLUE
        if soldier.damage_flash > 0:
            color = WHITE
        radius = 8 if player else 5
        pygame.draw.ellipse(self.screen, (19, 24, 21), (px - radius, py - radius // 2, radius * 2, radius * 2))
        pygame.draw.circle(self.screen, color, (px, py), radius)
        pygame.draw.circle(self.screen, (194, 179, 139), (px, py - 2), 3 if player else 2)
        angle = math.atan2(self.mouse_screen[1] - py, self.mouse_screen[0] - px) if player else 0
        if not player and soldier.target and soldier.target.alive:
            angle = math.atan2(soldier.target.y - soldier.y, soldier.target.x - soldier.x)
        aim_end = (int(px + math.cos(angle) * (radius + 7)), int(py + math.sin(angle) * (radius + 7)))
        pygame.draw.line(self.screen, (35, 38, 31), (px, py), aim_end, 3 if player else 2)
        if player:
            pygame.draw.circle(self.screen, GOLD, (px, py), radius + 4, 1)
            hpw = int(32 * soldier.hp / soldier.max_hp)
            pygame.draw.rect(self.screen, (53, 43, 36), (px - 16, py - 17, 32, 3))
            pygame.draw.rect(self.screen, GREEN if soldier.hp > 35 else RED, (px - 16, py - 17, hpw, 3))
        elif soldier.role in {"engineer", "medic", "support", "mortar"}:
            role_color = GOLD if soldier.role in {"engineer", "mortar"} else BLUE if soldier.role == "medic" else PAPER
            role_tag = {"engineer": "E", "medic": "M", "support": "S", "mortar": "T"}[soldier.role]
            badge = pygame.Rect(px + 4, py - radius - 7, 12, 12)
            pygame.draw.rect(self.screen, (23, 29, 27), badge, border_radius=3)
            self._text(role_tag, badge.center, 10, role_color, "center")

    def _draw_tank(self, tank: Soldier, px: int, py: int) -> None:
        body = pygame.Rect(px - 22, py - 13, 44, 26)
        faction_color = (100, 111, 77) if tank.faction == "us" else (123, 92, 70)
        track_color = (37, 39, 34)
        pygame.draw.rect(self.screen, track_color, body.inflate(6, 4), border_radius=6)
        for offset in (-8, 0, 8):
            pygame.draw.circle(self.screen, (91, 91, 75), (px + offset, py - 14), 3)
            pygame.draw.circle(self.screen, (91, 91, 75), (px + offset, py + 14), 3)
        pygame.draw.rect(self.screen, faction_color, body, border_radius=4)
        pygame.draw.rect(self.screen, (147, 139, 107), (px - 8, py - 9, 17, 18), border_radius=4)
        angle = math.atan2(tank.target.y - tank.y, tank.target.x - tank.x) if tank.target else 0.0
        barrel = (int(px + math.cos(angle) * 29), int(py + math.sin(angle) * 29))
        pygame.draw.line(self.screen, (53, 57, 48), (px, py), barrel, 5)
        health_width = max(0, int(38 * tank.hp / tank.max_hp))
        pygame.draw.rect(self.screen, (40, 35, 29), (px - 19, py - 21, 38, 3))
        pygame.draw.rect(self.screen, RED if tank.faction == "german" else GREEN,
                         (px - 19, py - 21, health_width, 3))

    def _draw_emplacement(self, gun, battle: Battle) -> None:
        px = int(gun.x * TILE - self.camera_x)
        py = int(TOP_H + gun.y * TILE - self.camera_y)
        if gun.kind == "bunker":
            pygame.draw.rect(self.screen, (50, 53, 47), (px - 19, py - 14, 38, 28), border_radius=4)
            pygame.draw.rect(self.screen, (113, 108, 87), (px - 14, py - 9, 28, 18), 2)
        elif gun.kind == "mg_nest":
            pygame.draw.circle(self.screen, (93, 82, 61), (px, py), 16, 5)
            pygame.draw.circle(self.screen, (48, 53, 46), (px, py), 8)
        elif gun.kind == "artillery":
            pygame.draw.circle(self.screen, (72, 69, 57), (px, py), 13)
            pygame.draw.circle(self.screen, (135, 125, 99), (px, py), 8, 2)
            self._text(f"{gun.ammo}", (px, py + 18), 12, GOLD, "midtop")
        else:
            pygame.draw.circle(self.screen, (61, 64, 54), (px, py), 10)
        barrel = (int(px + math.cos(gun.facing) * 25), int(py + math.sin(gun.facing) * 25))
        pygame.draw.line(self.screen, (35, 39, 34), (px, py), barrel, 5 if gun.kind == "cannon" else 3)
        pygame.draw.circle(self.screen, GOLD, (px, py), 3)
        if math.hypot(battle.player.x - gun.x, battle.player.y - gun.y) <= 3.2 and not battle.active_emplacement:
            self._text("E  MOUNT", (px, py - 24), 13, GOLD, "midbottom")

    def draw_battle(self, battle: Battle, dt: float, mouse: tuple[int, int], aiming: bool = False) -> None:
        self._active_battle = battle
        self.mouse_screen = mouse
        self._update_camera(battle, dt)
        w, h = self.screen.get_size()
        view_h = h - TOP_H - HUD_H
        view = pygame.Rect(0, TOP_H, w, view_h)
        self.screen.fill(INK)
        self.screen.set_clip(view)
        start_x = max(0, int(self.camera_x // TILE))
        start_y = max(0, int(self.camera_y // TILE))
        end_x = min(battle.world.width, int((self.camera_x + w) // TILE) + 2)
        end_y = min(battle.world.height, int((self.camera_y + view_h) // TILE) + 2)
        for ty in range(start_y, end_y):
            for tx in range(start_x, end_x):
                rect = pygame.Rect(int(tx * TILE - self.camera_x), int(TOP_H + ty * TILE - self.camera_y), TILE, TILE)
                self._draw_tile(tx, ty, battle.world.tiles[ty][tx], rect,
                                battle.world.tile_damage_ratio(tx, ty),
                                battle.world.elevation[ty][tx],
                                battle.world.tile_orientations[ty][tx],
                                battle.world.defense_connections(tx, ty))
                if tx > 0 and battle.world.elevation[ty][tx] > battle.world.elevation[ty][tx - 1]:
                    pygame.draw.rect(self.screen, (47, 48, 40),
                                     (rect.left, rect.top, 7, rect.height))
        artillery_x = int(battle.artillery_position[0] * TILE - self.camera_x)
        artillery_y = int(TOP_H + battle.artillery_position[1] * TILE - self.camera_y)
        pygame.draw.circle(self.screen, (47, 49, 42), (artillery_x, artillery_y), 13)
        pygame.draw.circle(self.screen, (130, 124, 101), (artillery_x - 8, artillery_y + 5), 5, 2)
        pygame.draw.circle(self.screen, (130, 124, 101), (artillery_x + 8, artillery_y + 5), 5, 2)
        pygame.draw.line(self.screen, (149, 139, 111), (artillery_x, artillery_y),
                         (artillery_x + 25, artillery_y - 10), 6)
        for strike in battle.artillery_strikes:
            center = (int(strike.x * TILE - self.camera_x),
                      int(TOP_H + strike.y * TILE - self.camera_y))
            radius = round(strike.radius * TILE)
            pygame.draw.circle(self.screen, RED, center, radius, 2)
            pygame.draw.line(self.screen, RED, (center[0] - 9, center[1]), (center[0] + 9, center[1]), 2)
            pygame.draw.line(self.screen, RED, (center[0], center[1] - 9), (center[0], center[1] + 9), 2)
            self._text(f"{strike.fuse:.1f}", (center[0], center[1] - 16), 14, PAPER, "midbottom")
        if battle.mission.mode == "destroy":
            target_x, target_y = battle.mission.objective_tile
            center = (int((target_x + 0.5) * TILE - self.camera_x),
                      int(TOP_H + (target_y + 0.5) * TILE - self.camera_y))
            if not view.collidepoint(center):
                origin = (w // 2, TOP_H + view_h // 2)
                vector_x, vector_y = center[0] - origin[0], center[1] - origin[1]
                scale = min((w * 0.46) / max(1, abs(vector_x)),
                        (view_h * 0.44) / max(1, abs(vector_y)))
                edge = (int(origin[0] + vector_x * scale), int(origin[1] + vector_y * scale))
                angle = math.atan2(vector_y, vector_x)
                tip = (int(edge[0] + math.cos(angle) * 13), int(edge[1] + math.sin(angle) * 13))
                left = (int(edge[0] + math.cos(angle + 2.5) * 11),
                    int(edge[1] + math.sin(angle + 2.5) * 11))
                right = (int(edge[0] + math.cos(angle - 2.5) * 11),
                     int(edge[1] + math.sin(angle - 2.5) * 11))
                pygame.draw.polygon(self.screen, RED, (tip, left, right))
                self._text("TARGET", edge, 12, GOLD, "center")
                pygame.draw.circle(self.screen, RED, center, 26, 3)
                pygame.draw.line(self.screen, RED, (center[0] - 34, center[1]),
                         (center[0] + 34, center[1]), 2)
                pygame.draw.line(self.screen, RED, (center[0], center[1] - 34),
                         (center[0], center[1] + 34), 2)
                pygame.draw.rect(self.screen, (66, 58, 46), (center[0] - 19, center[1] - 15, 38, 30), border_radius=3)
                pygame.draw.rect(self.screen, GOLD, (center[0] - 19, center[1] - 15, 38, 30), 2, border_radius=3)
                bar = pygame.Rect(center[0] - 25, center[1] - 40, 50, 5)
                pygame.draw.rect(self.screen, (36, 31, 28), bar)
                pygame.draw.rect(self.screen, RED, (bar.x, bar.y,
                         int(bar.width * battle.objective_health / battle.objective_max_health), bar.height))
                self._text("DESTROY TARGET", (center[0], center[1] - 44), 13, GOLD, "midbottom")
        if battle.player.inventory_slot == 4 and battle.grenades > 0:
            start, end = battle.grenade_preview(self.mouse_world(mouse))
            previous = None
            for step in range(13):
                progress = step / 12
                point = (start[0] + (end[0] - start[0]) * progress,
                         start[1] + (end[1] - start[1]) * progress)
                screen_point = (int(point[0] * TILE - self.camera_x),
                                int(TOP_H + point[1] * TILE - self.camera_y
                                    - math.sin(progress * math.pi) * 2.1 * TILE))
                if previous is not None:
                    pygame.draw.line(self.screen, (224, 178, 91), previous, screen_point, 2)
                previous = screen_point
        for grenade in battle.thrown_grenades:
            grenade_x, grenade_y = grenade.position
            point = (int(grenade_x * TILE - self.camera_x),
                     int(TOP_H + grenade_y * TILE - self.camera_y - grenade.height * TILE))
            pygame.draw.circle(self.screen, (45, 50, 39), point, 5)
            pygame.draw.circle(self.screen, GOLD, point, 2)
        for shell in battle.mortar_shells:
            shell_x, shell_y = shell.position
            point = (int(shell_x * TILE - self.camera_x),
                     int(TOP_H + shell_y * TILE - self.camera_y - shell.height * TILE))
            ground = (int(shell_x * TILE - self.camera_x),
                      int(TOP_H + shell_y * TILE - self.camera_y))
            pygame.draw.line(self.screen, (73, 67, 55), point, ground, 1)
            pygame.draw.circle(self.screen, (35, 38, 34), point, 6)
            pygame.draw.circle(self.screen, GOLD, point, 3)
        for point in battle.control_points:
            center = (int(point.x * TILE - self.camera_x),
                      int(TOP_H + point.y * TILE - self.camera_y))
            color = BLUE if point.owner == "us" else RED if point.owner == "german" else GOLD
            pygame.draw.circle(self.screen, color, center, 35, 2)
            pygame.draw.circle(self.screen, color, center, 7)
            if abs(point.progress) > 0.01:
                arc_color = BLUE if point.progress > 0 else RED
                pygame.draw.arc(self.screen, arc_color, pygame.Rect(center[0] - 41, center[1] - 41, 82, 82),
                                -math.pi / 2, -math.pi / 2 + math.tau * abs(point.progress), 4)
            pygame.draw.rect(self.screen, (18, 22, 21), (center[0] - 15, center[1] - 13, 30, 25), border_radius=4)
            self._text(point.label, center, 19, color, "center")
            self._text(point.name, (center[0], center[1] - 43), 14, PAPER, "midbottom", self.small)
        if self.combat_effects:
            for effect in battle.explosions:
                px, py = int(effect.x * TILE - self.camera_x), int(TOP_H + effect.y * TILE - self.camera_y)
                radius = int(effect.radius * TILE * (1 - effect.life / 0.8))
                pygame.draw.circle(self.screen, (239, 177, 82), (px, py), max(2, radius), 2)
                pygame.draw.circle(self.screen, (221, 110, 63), (px, py), max(2, radius // 2), 1)
        for gun in battle.emplacements:
            self._draw_emplacement(gun, battle)
        if battle.air_run:
            progress = min(1.0, battle.air_run["elapsed"] / battle.air_run["duration"])
            plane_x = -5.0 + (battle.world.width + 10.0) * progress
            plane_y = battle.air_run["lane_y"]
            plane_center = (int(plane_x * TILE - self.camera_x),
                            int(TOP_H + plane_y * TILE - self.camera_y - 28))
            pygame.draw.line(self.screen, (207, 204, 184),
                             (plane_center[0] - 22, plane_center[1]),
                             (plane_center[0] + 22, plane_center[1]), 5)
            pygame.draw.polygon(self.screen, (157, 162, 151),
                                [(plane_center[0] + 18, plane_center[1]),
                                 (plane_center[0] + 8, plane_center[1] - 8),
                                 (plane_center[0] + 4, plane_center[1] + 8)])
        for soldier in battle.all_soldiers:
            if soldier.alive and not (battle.active_emplacement and soldier.player):
                self._draw_soldier(soldier)
        for tracer in battle.tracers if self.combat_effects else ():
            progress = 1 - tracer.life / tracer.duration
            sx, sy = tracer.start
            ex, ey = tracer.end
            tip = (int((sx + (ex - sx) * progress) * TILE - self.camera_x),
                   int(TOP_H + (sy + (ey - sy) * progress) * TILE - self.camera_y))
            start = (int(sx * TILE - self.camera_x), int(TOP_H + sy * TILE - self.camera_y))
            color = GOLD if tracer.faction != "german" else (235, 105, 78)
            pygame.draw.line(self.screen, color, start, tip, 3 if tracer.heavy else 2)
        self.screen.set_clip(None)

        self._draw_crosshair(mouse, aiming, battle.player.recoil, battle.hit_marker_timer > 0)
        pygame.draw.rect(self.screen, INK, (0, 0, w, TOP_H))
        left_header = self._fit_text(f"NORMANDY / {battle.mission.title}", int(w * 0.29), 20)
        center_header = self._fit_text(
            f"{battle.mission.location} / {battle.mission.mode.upper()}  {int(battle.elapsed // 60):02}:{int(battle.elapsed % 60):02}",
            int(w * 0.41), 16)
        right_header = self._fit_text(f"{sum(s.alive for s in battle.enemies)} HOSTILES", int(w * 0.18), 15)
        self._text(left_header, (14, 17), 20, PAPER)
        self._text(center_header, (int(w * 0.55), 18), 16, MUTED, "midtop")
        self._text(right_header, (w - 14, 18), 15, RED, "topright")
        pygame.draw.line(self.screen, GOLD, (0, TOP_H - 2), (w, TOP_H - 2), 2)

        hud_y = h - HUD_H
        pygame.draw.rect(self.screen, PANEL, (0, hud_y, w, HUD_H))
        pygame.draw.line(self.screen, (84, 99, 80), (0, hud_y), (w, hud_y), 2)
        player = battle.player
        active_weapon = WEAPONS[player.weapon_key] if player.inventory_slot == 1 else \
            WEAPONS[player.secondary_weapon_key] if player.inventory_slot == 2 else None
        item_name = active_weapon.name if active_weapon else \
            "MACHETE" if player.inventory_slot == 3 else "HAND GRENADE"
        heading = (f"MANNING {battle.active_emplacement.name}" if battle.active_emplacement else
               f"{player.name.upper()} / {player.role.upper()} / {item_name}")
        self._text(self._fit_text(heading, w - 190, 20), (18, hud_y + 12), 20,
               GOLD if battle.active_emplacement else PAPER)
        health_status = (f"HP {int(player.hp):03d}%     KILLS {battle.kills:02d}     "
                 f"SQUAD {sum(s.alive for s in battle.player_squad)}/8")
        self._text(self._fit_text(health_status, w - 220, 16), (18, hud_y + 39), 16, MUTED)
        if battle.active_emplacement and battle.active_emplacement.kind == "artillery":
            ammo_text = f"SHELLS {battle.active_emplacement.ammo}"
        elif player.inventory_slot == 1:
            ammo_text = f"{player.ammo:02d} / {player.reserve:03d}"
        elif player.inventory_slot == 2:
            ammo_text = f"{player.secondary_ammo:02d} / {player.secondary_reserve:03d}"
        else:
            ammo_text = f"×{battle.grenades}" if player.inventory_slot == 4 else "READY"
        if player.reload_timer > 0:
            ammo_text += f"  RLD {math.ceil(player.reload_timer)}"
        self._text(self._fit_text(ammo_text, 210, 26), (w - 22, hud_y + 9), 26, GOLD, "topright")
        self._text(f"GRENADE [G]  ×{battle.grenades}", (w - 22, hud_y + 44), 16, MUTED, "topright")
        # Individual squadmates are selectable and remain in the fight as AI.
        self.inventory_rects = []
        inventory_labels = ("1 PRIMARY", "2 PISTOL", "3 MACHETE", "4 GRENADE")
        for slot, label in enumerate(inventory_labels, start=1):
            rect = pygame.Rect(18 + (slot - 1) * 64, hud_y + 66, 61, 27)
            selected = slot == player.inventory_slot
            pygame.draw.rect(self.screen, GOLD if selected else PANEL_LIGHT, rect, border_radius=3)
            self._text(label, rect.center, 11, INK if selected else PAPER, "center")
            self.inventory_rects.append(rect)
        self.squad_rects = []
        for index, soldier in enumerate(battle.player_squad):
            rect = pygame.Rect(286 + index * 78, hud_y + 66, 72, 27)
            color = GOLD if index == battle.selected_index else PANEL_LIGHT if soldier.alive else (57, 47, 43)
            pygame.draw.rect(self.screen, color, rect, border_radius=3)
            fg = INK if index == battle.selected_index else PAPER if soldier.alive else MUTED
            role_tag = {"engineer": "ENG", "medic": "MED", "support": "SUP", "assault": "ASL",
                        "mortar": "MTR"}.get(
                soldier.role, "RFL")
            self._text(f"F{index + 1} {PLAYER_NAMES[index][:3]} {role_tag}", rect.center, 12, fg, "center")
            self.squad_rects.append(rect)
        point_status = "   ".join(
            f"{point.label}:{'US' if point.owner == 'us' else 'GER' if point.owner == 'german' else 'NEUTRAL'}"
            for point in battle.control_points
        )
        score = f"US {int(battle.tickets['us']):03d}   {point_status}   GER {int(battle.tickets['german']):03d}"
        self._text(self._fit_text(score, w - 24, 16), (w // 2, hud_y + 95), 16, GOLD, "midtop")
        if battle.mission.mode == "holdout":
            objective_status = f"HOLD THE {battle.mission.objective}  •  RELIEF IN {int(battle.holdout_remaining)}s"
        elif battle.mission.mode == "destroy":
            objective_status = f"DESTROY {battle.mission.objective}  •  TARGET {int(battle.objective_health)}/{int(battle.objective_max_health)}"
        else:
            objective_status = "CAPTURE AND HOLD SECTORS"
        self._text(self._fit_text(objective_status, w - 40, 13), (w // 2, hud_y + 119), 13, GOLD, "midtop")
        controls = ("MANNING GUN • LMB fire • E leave" if battle.active_emplacement else
                    "WASD move • LMB fire • Shift sprint • Ctrl crouch • RMB aim • R reload • 1–4 gear • E mount • F1–F8 squad • B/N build • H heal")
        self._text(self._fit_text(controls, w - 24, 12),
               (w // 2, h - 6), 12, MUTED, "midbottom")
        if battle.radio_timer > 0:
            banner = pygame.Rect(w // 2 - 330, TOP_H + 12, 660, 34)
            pygame.draw.rect(self.screen, (21, 28, 27), banner, border_radius=3)
            self._text(battle.radio_message[:78], banner.center, 17, GOLD, "center")

    def _draw_crosshair(self, mouse: tuple[int, int], aiming: bool, recoil: float, hit: bool = False) -> None:
        x, y = mouse
        gap = int((8 if aiming else 13) + recoil * 0.35)
        size = 5 if aiming else 7
        color = GOLD if hit else WHITE
        pygame.draw.line(self.screen, color, (x - gap - size, y), (x - gap, y), 2)
        pygame.draw.line(self.screen, color, (x + gap, y), (x + gap + size, y), 2)
        pygame.draw.line(self.screen, color, (x, y - gap - size), (x, y - gap), 2)
        pygame.draw.line(self.screen, color, (x, y + gap), (x, y + gap + size), 2)
        pygame.draw.circle(self.screen, GOLD, (x, y), 3 if hit else 2)

    def _menu_button(self, action: str, label: str, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, PANEL_LIGHT, rect, border_radius=5)
        pygame.draw.rect(self.screen, GOLD, rect, 1, border_radius=5)
        self._text(self._fit_text(label, rect.width - 18, 19), rect.center, 19, PAPER, "center")
        self.pause_action_rects.append((action, rect))

    def draw_pause_menu(self, page: str, settings: dict[str, object]) -> None:
        w, h = self.screen.get_size()
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((5, 8, 8, 205))
        self.screen.blit(shade, (0, 0))
        panel = pygame.Rect(w // 2 - 230, h // 2 - 225, 460, 450)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, panel, 2, border_radius=8)
        self.pause_action_rects = []
        if page == "pause":
            self._text("PAUSED", (w // 2, panel.y + 35), 42, GOLD, "midtop")
            self._menu_button("resume", "RESUME  ·  ENTER", pygame.Rect(panel.x + 55, panel.y + 105, 350, 52))
            self._menu_button("menu", "RETURN TO START MENU", pygame.Rect(panel.x + 55, panel.y + 170, 350, 52))
            self._menu_button("options", "OPTIONS", pygame.Rect(panel.x + 55, panel.y + 235, 350, 52))
            self._menu_button("controls", "CONTROLS", pygame.Rect(panel.x + 55, panel.y + 300, 350, 52))
            self._text("Battle progress is recorded when the mission ends.",
                       (w // 2, panel.bottom - 34), 15, MUTED, "center")
        elif page == "options":
            self._text("OPTIONS", (w // 2, panel.y + 35), 38, GOLD, "midtop")
            difficulty = str(settings.get("difficulty", "standard")).upper()
            effects = "ON" if settings.get("combat_effects", True) else "OFF"
            self._menu_button("difficulty", f"DIFFICULTY: {difficulty}  ·  CLICK TO CYCLE",
                              pygame.Rect(panel.x + 35, panel.y + 110, 390, 58))
            self._menu_button("effects", f"COMBAT EFFECTS: {effects}",
                              pygame.Rect(panel.x + 35, panel.y + 185, 390, 58))
            self._menu_button("back", "BACK TO PAUSE MENU", pygame.Rect(panel.x + 55, panel.y + 315, 350, 52))
            self._text("Options are saved automatically.", (w // 2, panel.bottom - 34), 15, MUTED, "center")
        else:
            self._text("CONTROLS", (w // 2, panel.y + 28), 36, GOLD, "midtop")
            controls = (
                "WASD / arrows — move     Mouse — aim / fire",
                "Right mouse — aim carefully     Shift — sprint",
                "Ctrl / C — crouch     R — reload     G / 4 — grenade",
                "1 primary  ·  2 pistol  ·  3 melee  ·  4 grenade",
                "F1–F8 / Tab — switch squadmate     E — mount / leave gun",
                "B sandbags  ·  N barbed wire  ·  H medic  ·  V bayonet",
                "Esc — pause / resume     Map editor: M from start menu",
                "Editor: 1–0 terrain  ·  left click paint  ·  right click sample  ·  R rotate",
                "Editor: arrows pan  ·  [ / ] mission  ·  S save map",
            )
            for index, line in enumerate(controls):
                self._text(self._fit_text(line, panel.width - 42, 17),
                           (w // 2, panel.y + 92 + index * 31), 17, PAPER, "midtop")
            self._menu_button("back", "BACK", pygame.Rect(panel.x + 55, panel.bottom - 70, 350, 48))

    def draw_map_editor(self, world, mission, selected_tile: str, mission_index: int,
                        editor_orientation: float = 0.0) -> None:
        w, h = self.screen.get_size()
        view_top, view_bottom = TOP_H, h - 70
        view = pygame.Rect(0, view_top, w, view_bottom - view_top)
        self.screen.fill(INK)
        self.screen.set_clip(view)
        start_x = max(0, int(self.camera_x // TILE))
        start_y = max(0, int(self.camera_y // TILE))
        end_x = min(world.width, int((self.camera_x + w) // TILE) + 2)
        end_y = min(world.height, int((self.camera_y + view.height) // TILE) + 2)
        for ty in range(start_y, end_y):
            for tx in range(start_x, end_x):
                rect = pygame.Rect(int(tx * TILE - self.camera_x),
                                   int(view_top + ty * TILE - self.camera_y), TILE, TILE)
                self._draw_tile(tx, ty, world.tiles[ty][tx], rect,
                                world.tile_damage_ratio(tx, ty), world.elevation[ty][tx],
                                world.tile_orientations[ty][tx], world.defense_connections(tx, ty))
                pygame.draw.rect(self.screen, (36, 44, 37), rect, 1)
        target_x, target_y = mission.objective_tile
        marker = (int((target_x + 0.5) * TILE - self.camera_x),
                  int(view_top + (target_y + 0.5) * TILE - self.camera_y))
        pygame.draw.circle(self.screen, GOLD, marker, 12, 3)
        pygame.draw.line(self.screen, GOLD, (marker[0] - 16, marker[1]),
                         (marker[0] + 16, marker[1]), 2)
        pygame.draw.line(self.screen, GOLD, (marker[0], marker[1] - 16),
                         (marker[0], marker[1] + 16), 2)
        self.screen.set_clip(None)
        pygame.draw.rect(self.screen, INK, (0, 0, w, TOP_H))
        self._text(f"MAP EDITOR / {mission.title}  ({mission_index + 1}/{len(CAMPAIGNS)})",
                   (14, 16), 20, GOLD)
        self._text(f"PAINT: {selected_tile.upper()}  ·  ROTATION {round(math.degrees(editor_orientation)) % 360}°",
                   (w - 14, 18), 15, PAPER, "topright")
        pygame.draw.rect(self.screen, PANEL, (0, h - 70, w, 70))
        palette_labels = "   ".join(f"{(i + 1) % 10}:{tile.upper()}" for i, tile in enumerate(self.EDITOR_PALETTE))
        self._text(self._fit_text(palette_labels, w - 24, 13), (w // 2, h - 54), 13, PAPER, "midtop")
        help_text = "LMB paint  ·  RMB sample+angle  ·  R rotate  ·  Arrows pan  ·  [ / ] mission  ·  S save  ·  Esc exit"
        self._text(self._fit_text(help_text, w - 24, 14), (w // 2, h - 26), 14, MUTED, "midtop")

    def draw_debrief(self, battle: Battle) -> None:
        w, h = self.screen.get_size()
        self.screen.fill(INK)
        self._text("FRONTLINE SECURED", (w // 2, h // 2 - 110), 48, GOLD, "center")
        self._text(battle.mission.title, (w // 2, h // 2 - 57), 26, PAPER, "center")
        self._text(self._fit_text(
            f"Confirmed squad kills: {battle.kills}     Survivors: {sum(s.alive for s in battle.player_squad)}/8",
            w - 50, 20), (w // 2, h // 2 - 15), 20, MUTED, "center")
        self.continue_rect = pygame.Rect(w // 2 - 155, h // 2 + 44, 310, 58)
        pygame.draw.rect(self.screen, GOLD, self.continue_rect, border_radius=5)
        label = "CONTINUE CAMPAIGN" if battle.mission_index < len(CAMPAIGNS) - 1 else "CAMPAIGN COMPLETE"
        self._text(label, self.continue_rect.center, 21, INK, "center")

    def draw_defeat(self, battle: Battle) -> None:
        w, h = self.screen.get_size()
        self.screen.fill(INK)
        self._text("FRONTLINE LOST", (w // 2, h // 2 - 70), 48, RED, "center")
        self._text(self._fit_text(
            f"The Allied line has fallen. You eliminated {battle.kills} enemy troops. Press R to retry.",
            w - 50, 21), (w // 2, h // 2), 21, PAPER, "center")
