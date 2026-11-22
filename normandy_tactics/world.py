"""Procedural tile maps and collision queries."""

from __future__ import annotations

import math
import random
import heapq
import itertools

from .campaigns import Mission
from .settings import BLOCKED


class World:
    def __init__(self, mission: Mission, seed: int = 0,
                 tile_overrides: list[list[str]] | None = None,
                 orientation_overrides: list[list[float]] | None = None) -> None:
        self.mission = mission
        self.width = mission.width
        self.height = mission.height
        self.rng = random.Random(2400 + seed)
        self.tiles = [["field" for _ in range(self.width)] for _ in range(self.height)]
        self._build()
        valid_tiles = {"water", "sand", "field", "road", "hedge", "wire", "crater",
                       "wall", "building", "trench", "rock", "obstacle", "sandbag", "rubble"}
        if tile_overrides and len(tile_overrides) == self.height:
            for y, row in enumerate(tile_overrides):
                if len(row) != self.width:
                    continue
                for x, tile in enumerate(row):
                    if tile in valid_tiles:
                        self.tiles[y][x] = tile
        self.tile_orientations = [[0.0 for _ in range(self.width)] for _ in range(self.height)]
        if orientation_overrides and len(orientation_overrides) == self.height:
            for y, row in enumerate(orientation_overrides):
                if len(row) != self.width:
                    continue
                for x, orientation in enumerate(row):
                    if isinstance(orientation, (int, float)) and math.isfinite(orientation):
                        self.tile_orientations[y][x] = float(orientation) % math.tau
        else:
            self._align_connected_defenses()
        self.elevation = [[0 for _ in range(self.width)] for _ in range(self.height)]
        if self.mission.terrain == "beach":
            for tile_y in range(self.height):
                for tile_x in range(self.width):
                    if tile_x >= int(self.width * 0.39):
                        self.elevation[tile_y][tile_x] = 1
                    if tile_x >= int(self.width * 0.53):
                        self.elevation[tile_y][tile_x] = 2
        self.tile_health = [[self._tile_max_health(tile) for tile in row] for row in self.tiles]

    def _align_connected_defenses(self) -> None:
        """Give connected wire, trench, and sandbag runs a shared direction."""
        for y in range(self.height):
            for x in range(self.width):
                orientation = self.connected_defense_orientation(x, y)
                if orientation is not None:
                    self.tile_orientations[y][x] = orientation

    def connected_defense_orientation(self, tile_x: int, tile_y: int) -> float | None:
        """Infer a line direction from adjacent wire, trench, or sandbag tiles."""
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return None
        linked_defenses = {"wire", "trench", "sandbag"}
        if self.tiles[tile_y][tile_x] not in linked_defenses:
            return None
        neighbors = [
            (nx - tile_x, ny - tile_y)
            for nx, ny in ((tile_x - 1, tile_y), (tile_x + 1, tile_y),
                           (tile_x, tile_y - 1), (tile_x, tile_y + 1))
            if 0 <= nx < self.width and 0 <= ny < self.height
            and self.tiles[ny][nx] in linked_defenses
        ]
        if not neighbors:
            return None
        cos_sum = sum(math.cos(2 * math.atan2(dy, dx)) for dx, dy in neighbors)
        sin_sum = sum(math.sin(2 * math.atan2(dy, dx)) for dx, dy in neighbors)
        if abs(cos_sum) + abs(sin_sum) <= 1e-8:
            return None
        orientation = (0.5 * math.atan2(sin_sum, cos_sum)) % math.pi
        return 0.0 if math.isclose(orientation, math.pi, abs_tol=1e-8) else orientation

    def defense_connections(self, tile_x: int, tile_y: int) -> tuple[bool, bool, bool, bool]:
        """Return north/east/south/west links for continuous defensive lines."""
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return False, False, False, False
        tile = self.tiles[tile_y][tile_x]
        linked_tiles = {"wire", "trench"} if tile in {"wire", "trench"} else {"sandbag"}
        return tuple(
            0 <= nx < self.width and 0 <= ny < self.height
            and self.tiles[ny][nx] in linked_tiles
            for nx, ny in ((tile_x, tile_y - 1), (tile_x + 1, tile_y),
                           (tile_x, tile_y + 1), (tile_x - 1, tile_y))
        )

    @staticmethod
    def _tile_max_health(tile: str) -> float:
        return {"field": 260.0, "road": 220.0, "sand": 180.0, "wire": 24.0,
                "hedge": 70.0, "sandbag": 90.0, "obstacle": 100.0, "rock": 160.0,
                "wall": 180.0, "building": 240.0, "trench": 110.0,
                "crater": 70.0}.get(tile, 0.0)

    def _build(self) -> None:
        theme = self.mission.terrain
        if theme == "beach":
            shoreline_end = int(self.width * 0.20)
            road_x = int(self.width * 0.27)
            for y in range(self.height):
                for x in range(self.width):
                    self.tiles[y][x] = "water" if x < 3 else "sand" if x < shoreline_end else "field"
            for y in range(2, self.height - 2, 4):
                for x in range(4, shoreline_end, 3):
                    self.tiles[y + (x % 3)][x] = "obstacle"
            for y in range(self.height):
                self.tiles[y][road_x] = "road"
            bunker_x = int(self.width * 0.52)
            bunker_y = self.height // 2 - 7
            for x in (bunker_x, bunker_x + 1):
                for y in range(bunker_y, bunker_y + 4):
                    self.tiles[y][x] = "building"
            for x, y in ((10, 5), (11, 5), (10, 20), (11, 20), (18, 12), (21, 22)):
                self.tiles[y][x] = "crater"
        elif theme == "bocage":
            for x in range(6, self.width - 3, 7):
                gap = self.rng.randrange(3, self.height - 3)
                for y in range(1, self.height - 1):
                    if abs(y - gap) > 1:
                        self.tiles[y][x] = "hedge"
            for y in range(5, self.height - 3, 8):
                gap = self.rng.randrange(5, self.width - 5)
                for x in range(3, self.width - 2):
                    if abs(x - gap) > 2:
                        self.tiles[y][x] = "hedge"
            for y in range(self.height):
                self.tiles[y][self.width // 2] = "road"
            for x in range(self.width):
                self.tiles[self.height // 2][x] = "road"
        elif theme == "town":
            for y in range(self.height):
                for x in range(self.width):
                    if x % 10 in (4, 5) or y % 9 in (3, 4):
                        self.tiles[y][x] = "road"
                    elif self.rng.random() < 0.30:
                        self.tiles[y][x] = "building"
            for y in range(self.height):
                for x in (4, 5, self.width // 2, self.width // 2 + 1):
                    self.tiles[y][x] = "road"
            for x in range(self.width):
                for y in (3, 4, self.height // 2):
                    self.tiles[y][x] = "road"
        elif theme == "river":
            river_x = self.width // 2
            for y in range(self.height):
                for x in range(river_x - 2, river_x + 2):
                    self.tiles[y][x] = "water"
            for x in range(river_x - 2, river_x + 2):
                for y in range(self.height // 2 - 1, self.height // 2 + 2):
                    self.tiles[y][x] = "road"
            for y in range(self.height):
                self.tiles[y][river_x - 3] = "road"
                self.tiles[y][river_x + 2] = "road"
        else:  # ridge, scrub, and mixed countryside
            for y in range(3, self.height - 2, 6):
                gap = self.rng.randrange(3, self.width - 3)
                for x in range(3, self.width - 2):
                    if abs(x - gap) > 2:
                        self.tiles[y][x] = "trench"
            for _ in range(self.width * self.height // 25):
                x = self.rng.randrange(4, self.width - 2)
                y = self.rng.randrange(2, self.height - 2)
                if self.tiles[y][x] == "field":
                    self.tiles[y][x] = self.rng.choice(("rock", "crater", "wall"))

        # Place contextual cover while maintaining corridors across the map.
        for _ in range(self.width * self.height // 24):
            x = self.rng.randrange(5, self.width - 2)
            y = self.rng.randrange(1, self.height - 1)
            if self.tiles[y][x] == "field" and x % 8 not in (0, 1):
                self.tiles[y][x] = self.rng.choice(("crater", "trench", "wire"))

        # Objective areas are clear so the capture interaction remains readable.
        ox, oy = self.mission.objective_tile
        for y in range(max(1, oy - 2), min(self.height - 1, oy + 3)):
            for x in range(max(1, ox - 2), min(self.width - 1, ox + 3)):
                if self.tiles[y][x] in BLOCKED:
                    self.tiles[y][x] = "field"

    def tile_at(self, world_x: float, world_y: float) -> str:
        tx, ty = int(world_x), int(world_y)
        if tx < 0 or ty < 0 or tx >= self.width or ty >= self.height:
            return "water"
        return self.tiles[ty][tx]

    def blocked(self, world_x: float, world_y: float, radius: float = 0.22) -> bool:
        checks = ((world_x - radius, world_y - radius), (world_x + radius, world_y - radius),
                  (world_x - radius, world_y + radius), (world_x + radius, world_y + radius))
        return any(self.tile_at(x, y) in BLOCKED for x, y in checks)

    def damage_tile(self, tile_x: int, tile_y: int, damage: float) -> bool:
        """Damage one destructible tile; return True when it was destroyed."""
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return False
        health = self.tile_health[tile_y][tile_x]
        if health <= 0:
            return False
        health -= max(0.0, damage)
        if health > 0:
            self.tile_health[tile_y][tile_x] = health
            return False
        self.tiles[tile_y][tile_x] = "rubble"
        self.tile_health[tile_y][tile_x] = 0.0
        return True

    def _build_emplacement(self, tile_x: int, tile_y: int, tile: str, orientation: float) -> bool:
        """Place an engineer emplacement and store its facing-relative angle."""
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return False
        if self.tiles[tile_y][tile_x] not in {"field", "road", "sand", "crater", "rubble"}:
            return False
        self.tiles[tile_y][tile_x] = tile
        self.tile_health[tile_y][tile_x] = self._tile_max_health(tile)
        self.tile_orientations[tile_y][tile_x] = orientation
        return True

    def build_sandbag(self, tile_x: int, tile_y: int, orientation: float = 0.0) -> bool:
        """Place engineer-built cover on an empty walkable tile."""
        return self._build_emplacement(tile_x, tile_y, "sandbag", orientation)

    def build_wire(self, tile_x: int, tile_y: int, orientation: float = 0.0) -> bool:
        """Place engineer-built wire on an empty walkable tile."""
        return self._build_emplacement(tile_x, tile_y, "wire", orientation)

    def tile_hp(self, tile_x: int, tile_y: int) -> float:
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return 0.0
        return self.tile_health[tile_y][tile_x]

    def tile_damage_ratio(self, tile_x: int, tile_y: int) -> float:
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return 0.0
        maximum = self._tile_max_health(self.tiles[tile_y][tile_x])
        return 0.0 if maximum <= 0 else 1.0 - self.tile_health[tile_y][tile_x] / maximum

    def elevation_at(self, world_x: float, world_y: float) -> int:
        tile_x, tile_y = int(world_x), int(world_y)
        if not (0 <= tile_x < self.width and 0 <= tile_y < self.height):
            return 0
        return self.elevation[tile_y][tile_x]

    def cover_factor(self, world_x: float, world_y: float) -> float:
        """Return the fraction of incoming damage stopped by nearby cover."""
        tile = self.tile_at(world_x, world_y)
        return {"trench": 0.52, "crater": 0.72, "sand": 0.90, "field": 1.0,
            "road": 1.08, "wire": 1.0}.get(tile, 0.85)

    def nearest_open(self, world_x: float, world_y: float, max_radius: int = 8) -> tuple[float, float]:
        """Snap a strategic point or spawn to the closest walkable tile center."""
        origin_x, origin_y = int(world_x), int(world_y)
        candidates = []
        for radius in range(max_radius + 1):
            for ty in range(max(0, origin_y - radius), min(self.height, origin_y + radius + 1)):
                for tx in range(max(0, origin_x - radius), min(self.width, origin_x + radius + 1)):
                    if max(abs(tx - origin_x), abs(ty - origin_y)) > radius:
                        continue
                    if self.tiles[ty][tx] not in BLOCKED and self.tiles[ty][tx] != "wire":
                        candidates.append((math.dist((world_x, world_y), (tx + 0.5, ty + 0.5)), tx, ty))
            if candidates:
                _, x, y = min(candidates)
                return x + 0.5, y + 0.5
        return min(self.width - 1, max(0, origin_x)) + 0.5, min(self.height - 1, max(0, origin_y)) + 0.5

    def route_to_firing_position(
        self,
        start: tuple[float, float],
        target: tuple[float, float],
        weapon_range: float,
    ) -> list[tuple[float, float]]:
        """A* to a reachable, visible firing tile so NPCs route around walls/hedges."""
        start_cell = (int(start[0]), int(start[1]))
        desired_range = min(5.5, max(1.4, weapon_range * 0.48))
        target_x, target_y = target
        radius = min(weapon_range - 0.2, desired_range)
        min_x = max(0, int(target_x - radius - 1))
        max_x = min(self.width - 1, int(target_x + radius + 1))
        min_y = max(0, int(target_y - radius - 1))
        max_y = min(self.height - 1, int(target_y + radius + 1))
        goals: set[tuple[int, int]] = set()
        for ty in range(min_y, max_y + 1):
            for tx in range(min_x, max_x + 1):
                cell = (tx, ty)
                center = (tx + 0.5, ty + 0.5)
                if self.tiles[ty][tx] in BLOCKED or self.tiles[ty][tx] == "wire":
                    continue
                if math.dist(center, target) > radius:
                    continue
                if cell == start_cell and not self.line_clear(start, target):
                    continue
                if self.line_clear(center, target):
                    goals.add(cell)
        if not goals:
            # If cover blocks every immediate firing lane, move to a new tile near the target
            # rather than repeatedly steering into the same hedge or building corner.
            for ty in range(min_y, max_y + 1):
                for tx in range(min_x, max_x + 1):
                    cell = (tx, ty)
                    if cell == start_cell or self.tiles[ty][tx] in BLOCKED:
                        continue
                    if math.dist((tx + 0.5, ty + 0.5), target) <= radius:
                        goals.add(cell)
            if not goals:
                return []

        def heuristic(cell: tuple[int, int]) -> float:
            return max(0.0, math.dist((cell[0] + 0.5, cell[1] + 0.5), target) - radius)

        serial = itertools.count()
        frontier = [(heuristic(start_cell), next(serial), start_cell)]
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_cell: None}
        cost = {start_cell: 0.0}
        destination: tuple[int, int] | None = None
        directions = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                      (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414))
        while frontier:
            _, _, cell = heapq.heappop(frontier)
            if cell in goals:
                destination = cell
                break
            x, y = cell
            for dx, dy, step_cost in directions:
                nx, ny = x + dx, y + dy
                neighbor = (nx, ny)
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if self.tiles[ny][nx] in BLOCKED:
                    continue
                if dx and dy and (self.tiles[y][nx] in BLOCKED or self.tiles[ny][x] in BLOCKED):
                    continue
                terrain_cost = (3.5 if self.tiles[ny][nx] == "wire" else
                                2.2 if self.tiles[ny][nx] == "crater" else
                                0.9 if self.tiles[ny][nx] == "rubble" else 1.0)
                new_cost = cost[cell] + step_cost * terrain_cost
                if new_cost >= cost.get(neighbor, float("inf")):
                    continue
                cost[neighbor] = new_cost
                came_from[neighbor] = cell
                priority = new_cost + heuristic(neighbor)
                heapq.heappush(frontier, (priority, next(serial), neighbor))

        if destination is None:
            return []
        route = []
        cursor = destination
        while cursor != start_cell:
            route.append((cursor[0] + 0.5, cursor[1] + 0.5))
            previous = came_from[cursor]
            if previous is None:
                break
            cursor = previous
        return list(reversed(route))

    def line_clear(self, start: tuple[float, float], end: tuple[float, float]) -> bool:
        dx, dy = end[0] - start[0], end[1] - start[1]
        steps = max(1, math.ceil(max(abs(dx), abs(dy)) * 4))
        for index in range(1, steps):
            t = index / steps
            x, y = start[0] + dx * t, start[1] + dy * t
            if self.tile_at(x, y) in {"hedge", "building", "wall", "rock", "obstacle", "sandbag"}:
                return False
        return True
