"""Real-time first-person-inspired squad combat and AI battle simulation."""

from __future__ import annotations

import math
import random

import pygame

from .actors import ArtilleryStrike, ControlPoint, Explosion, MortarShell, MountedGun, Soldier, ThrownGrenade, Tracer, WEAPONS, Weapon
from .campaigns import CAMPAIGNS, Mission
from .settings import TILE
from .world import World


PLAYER_NAMES = ["Baker", "Cole", "Diaz", "Fox", "Ellis", "Shaw", "Kline", "Reed"]
ENEMY_WEAPONS = ("bolt", "bolt", "mp40", "mg")
ALLY_WEAPONS = ("rifle", "rifle", "smg", "lmg")
PLAYER_ROLES = ("rifleman", "assault", "medic", "engineer", "support", "rifleman", "support", "assault")
ALLY_ROLES = ("assault", "medic", "engineer", "support", "mortar")
ENEMY_ROLES = ("rifleman", "assault", "support", "engineer", "mortar")


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Battle:
    def __init__(self, mission_index: int = 0, veteran_bonus: float = 0.0,
                 difficulty: str = "standard",
                 tile_overrides: list[list[str]] | None = None,
                 orientation_overrides: list[list[float]] | None = None,
                 mission_override: Mission | None = None,
                 emplacement_overrides: list[dict[str, object]] | None = None) -> None:
        self.mission_index = mission_index
        self.mission: Mission = mission_override or CAMPAIGNS[mission_index]
        self.emplacement_overrides = emplacement_overrides
        self.world = World(self.mission, mission_index, tile_overrides, orientation_overrides)
        self.player_damage_multiplier = {"easy": 1.18, "standard": 1.12, "hard": 1.05}.get(
            difficulty, 1.12)
        self.incoming_damage_multiplier = {"easy": 0.90, "standard": 1.0, "hard": 1.08}.get(
            difficulty, 1.0)
        self.random = random.Random(4900 + mission_index)
        self.player_squad: list[Soldier] = []
        self.allies: list[Soldier] = []
        self.enemies: list[Soldier] = []
        self.tracers: list[Tracer] = []
        self.explosions: list[Explosion] = []
        self.artillery_strikes: list[ArtilleryStrike] = []
        self.mortar_shells: list[MortarShell] = []
        self.thrown_grenades: list[ThrownGrenade] = []
        self.control_points: list[ControlPoint] = []
        self.emplacements: list[MountedGun] = []
        self.selected_index = 0
        self.elapsed = 0.0
        self.tickets = {"us": 320.0, "german": 300.0}
        self.reinforcement_clock = 11.0
        self.reinforcement_wave = 0
        self.spawn_serial = 0
        self.player_respawn_timer: float | None = None
        self.grenade_cooldown = 0.0
        self.ai_grenade_cooldown = 0.0
        self.melee_cooldown = 0.0
        self.team_build_count = {"us": 0, "german": 0}
        self.max_team_builds = 6
        self.holdout_overrun_timer = 0.0
        self.holdout_overrun_grace = 20.0
        self.spatial_cell_size = 12.0
        self.spatial_grid: dict[tuple[str, int, int], list[Soldier]] = {}
        self.kills = 0
        self.hit_marker_timer = 0.0
        self.defeat = False
        self.complete = False
        self.radio_message = self.mission.briefing
        self.radio_timer = 7.0
        self.active_emplacement: MountedGun | None = None
        self.holdout_remaining = self.mission.holdout_seconds
        self.objective_health = 600.0
        self.objective_max_health = 600.0
        self.random_event_timer = self.random.uniform(35.0, 55.0)
        self.active_event_message = ""
        self.active_event_timer = 0.0
        self.air_run: dict[str, float] | None = None
        self.air_run_hits: set[Soldier] = set()
        self.ai_grenades_in_flight = 0
        self._spawn(veteran_bonus)
        self._create_control_points()
        self._create_emplacements()
        self.artillery_position = self.world.nearest_open(self.mission.width * 0.82,
                                  self.mission.height * 0.18)
        self.artillery_timer = self.random.uniform(11.0, 15.0)

    @property
    def player(self) -> Soldier:
        return self.player_squad[self.selected_index]

    @property
    def grenades(self) -> int:
        return self.player.grenades_remaining

    @property
    def all_soldiers(self) -> list[Soldier]:
        return self.player_squad + self.allies + self.enemies

    def _rebuild_spatial_grid(self) -> None:
        grid: dict[tuple[str, int, int], list[Soldier]] = {}
        for soldier in self.all_soldiers:
            if not soldier.alive:
                continue
            cell_x = int(soldier.x // self.spatial_cell_size)
            cell_y = int(soldier.y // self.spatial_cell_size)
            grid.setdefault((soldier.faction, cell_x, cell_y), []).append(soldier)
        self.spatial_grid = grid

    def _nearby_friends(self, soldier: Soldier) -> list[Soldier]:
        if not self.spatial_grid:
            return self.all_soldiers
        cell_x = int(soldier.x // self.spatial_cell_size)
        cell_y = int(soldier.y // self.spatial_cell_size)
        return [other for x in range(cell_x - 1, cell_x + 2)
                for y in range(cell_y - 1, cell_y + 2)
                for other in self.spatial_grid.get((soldier.faction, x, y), ())]

    def _spawn(self, veteran_bonus: float) -> None:
        mid = self.mission.height / 2
        for i, name in enumerate(PLAYER_NAMES):
            x, y = self._initial_spawn("us", (i // 4 - 0.5) * 2.4 + (i % 4) * 0.35)
            soldier = Soldier(f"Sgt. {name}" if i == 0 else f"Pvt. {name}", "us", "player",
                              x, y, ("lmg" if i == 6 else "smg" if i == 7 else "rifle"),
                              hp=100 + veteran_bonus, max_hp=100 + veteran_bonus,
                              player=(i == 0), speed=3.0, role=PLAYER_ROLES[i],
                              grenades_remaining=1 if i == 0 else 0)
            if veteran_bonus:
                soldier.reserve += int(veteran_bonus // 2)
            self.player_squad.append(soldier)

        ally_squads = self.mission.ally_count
        for squad in range(ally_squads):
            squad_id = f"Allied team {squad + 1}"
            for i in range(3):
                if self.mission.mode == "holdout":
                    lane_offset = ((squad % 5) - 2) * 1.25 + (i - 1) * 0.48 \
                        + self.random.uniform(-0.3, 0.3)
                else:
                    lane = squad % 3 - 1
                    squad_y = mid + lane * self.mission.height * 0.22
                    lane_offset = squad_y - mid + (i - 1) * 1.2 + self.random.uniform(-0.45, 0.45)
                x, y = self._initial_spawn("us", lane_offset)
                role = ALLY_ROLES[(i + squad) % len(ALLY_ROLES)]
                weapon = "mortar" if role == "mortar" else "lmg" if role == "support" else self.random.choice(ALLY_WEAPONS)
                self.allies.append(Soldier(f"{squad_id} / {role} {i + 1}", "us", squad_id,
                                           x, y, weapon, speed=self.random.uniform(2.0, 2.7), role=role))

        for i in range(self.mission.enemy_count):
            squad_id = f"German section {i // 4 + 1}"
            x, y = self._initial_spawn("german", self.random.uniform(-self.mission.height * 0.42,
                                                                       self.mission.height * 0.42))
            weapon = self.random.choice(ENEMY_WEAPONS)
            role = ENEMY_ROLES[i % len(ENEMY_ROLES)]
            if role == "support":
                weapon = "mg"
            elif role == "engineer":
                weapon = "mp40"
            elif role == "mortar":
                weapon = "mortar"
            self.enemies.append(Soldier(f"{squad_id} / soldier {i % 4 + 1}", "german", squad_id,
                                        x, y, weapon, hp=self.random.uniform(72, 100),
                                        speed=self.random.uniform(1.8, 2.5), role=role))

        self._spawn_tanks()
        # A fresh, random quarter of the autonomous force carries a single grenade.
        # Reinforcement waves call this again for their own newly spawned troops.
        self._issue_ai_grenades(self.allies + self.enemies)

    def _issue_ai_grenades(self, soldiers: list[Soldier]) -> None:
        """Give a random quarter of a new AI group its one lifetime grenade."""
        for faction in ("us", "german"):
            candidates = [soldier for soldier in soldiers
                          if soldier.faction == faction and soldier.alive and not soldier.player
                          and soldier.role != "tank" and not soldier.grenade_used
                          and soldier.grenades_remaining == 0]
            if not candidates:
                continue
            carrier_count = max(1, len(candidates) // 4)
            for soldier in self.random.sample(candidates, carrier_count):
                soldier.grenades_remaining = 1

    def _spawn_tanks(self) -> None:
        for faction in ("us", "german"):
            group = self.allies if faction == "us" else self.enemies
            for index in range(2):
                if self.mission.mode == "holdout" and faction == "us":
                    x, y = self._initial_spawn(faction, (index * 2 - 1) * 2.0)
                else:
                    home_x = self.mission.width * (0.13 if faction == "us" else 0.87)
                    x, y = self._nudge_open(home_x + index * 1.8,
                                            self.mission.height * (0.42 + index * 0.16))
                group.append(Soldier(f"{faction.title()} tank {index + 1}", faction,
                                     f"{faction.title()} armor", x, y, "tank",
                                     hp=330.0, max_hp=330.0, speed=1.05, role="tank"))

    def _create_control_points(self) -> None:
        ox, oy = self.mission.objective_tile
        if self.mission.mode == "holdout":
            px, py = self.world.nearest_open(ox + 0.5, oy + 0.5)
            self.control_points.append(ControlPoint("C", self.mission.objective, px, py,
                                                    owner="us", progress=1.0))
            return
        points = (
            ("A", "WEST APPROACH", self.mission.width * 0.28, self.mission.height * 0.50),
            ("B", "CROSSROADS", self.mission.width * 0.52, self.mission.height * 0.50),
            ("C", self.mission.objective, ox + 0.5, oy + 0.5),
        )
        placed: list[tuple[float, float]] = []
        for label, name, x, y in points:
            px, py = self.world.nearest_open(x, y)
            if any(distance((px, py), old) < 5.0 for old in placed):
                px, py = self.world.nearest_open(px + 5.0, py)
            placed.append((px, py))
            self.control_points.append(ControlPoint(label, name, px, py))

    def _create_emplacements(self) -> None:
        """Place reusable, player-operable defenses along the approach lanes."""
        labels = {"mg_nest": "MACHINE-GUN NEST", "bunker": "BUNKER GUN",
                  "cannon": "FIELD CANNON", "artillery": "HOWITZER"}
        if self.emplacement_overrides is not None:
            for placement in self.emplacement_overrides:
                kind = placement.get("kind")
                x = placement.get("x")
                y = placement.get("y")
                if kind not in labels or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    continue
                if not (0 <= x < self.world.width and 0 <= y < self.world.height):
                    continue
                px, py = self.world.nearest_open(float(x) + 0.5, float(y) + 0.5)
                self.emplacements.append(MountedGun(kind, px, py, labels[kind],
                                                    ammo=8 if kind == "artillery" else 0))
            return
        layouts = (("mg_nest", 0.30, 0.34), ("bunker", 0.52, 0.68),
               ("cannon", 0.72, 0.45), ("artillery", 0.17, 0.78))
        for kind, x_ratio, y_ratio in layouts:
            x, y = self.world.nearest_open(self.mission.width * x_ratio,
                                           self.mission.height * y_ratio)
            self.emplacements.append(MountedGun(kind, x, y, labels[kind],
                                                ammo=8 if kind == "artillery" else 0))

    def interact_emplacement(self) -> bool:
        """Enter the nearest defense with E, or leave the currently mounted gun."""
        if self.active_emplacement:
            self.active_emplacement.operator = None
            self.active_emplacement = None
            self.radio_message = "LEFT EMPLACEMENT"
            self.radio_timer = 1.5
            return True
        nearby = [gun for gun in self.emplacements if gun.operator is None
                  and distance((self.player.x, self.player.y), (gun.x, gun.y)) <= 2.8]
        if not nearby:
            self.radio_message = "MOVE CLOSER TO A BUNKER, CANNON, OR MG NEST — PRESS E"
            self.radio_timer = 2.0
            return False
        self.active_emplacement = min(nearby, key=lambda gun: distance(
            (self.player.x, self.player.y), (gun.x, gun.y)))
        self.active_emplacement.operator = self.player
        self.player.x, self.player.y = self.active_emplacement.x, self.active_emplacement.y
        self.radio_message = f"MANNING {self.active_emplacement.name} — PRESS E TO LEAVE"
        self.radio_timer = 2.0
        return True

    def _mounted_shot(self, aim: tuple[float, float]) -> bool:
        gun = self.active_emplacement
        if not gun or gun.fire_timer > 0:
            return False
        config = {
            "mg_nest": (18.0, 0.075, 24.0, 0.45),
            "bunker": (20.0, 0.11, 34.0, 0.52),
            "cannon": (28.0, 1.65, 155.0, 1.1),
            "artillery": (42.0, 6.5, 170.0, 2.4),
        }
        max_range, cooldown, damage, spread = config[gun.kind]
        dx, dy = aim[0] - gun.x, aim[1] - gun.y
        target_distance = math.hypot(dx, dy)
        if target_distance <= 0.01:
            return False
        if target_distance > max_range:
            self.radio_message = f"OUT OF RANGE — MAX {int(max_range)} TILES"
            self.radio_timer = 1.5
            return False
        gun.facing = math.atan2(dy, dx)
        if gun.kind == "artillery":
            if gun.ammo <= 0:
                self.radio_message = "HOWITZER OUT OF SHELLS"
                self.radio_timer = 1.8
                return False
            impact_x, impact_y = self.world.nearest_open(aim[0], aim[1])
            gun.ammo -= 1
            self.artillery_strikes.append(ArtilleryStrike(
                impact_x, impact_y, fuse=3.0, radius=5.0, damage=170.0, owner=self.player))
            gun.fire_timer = cooldown
            self.radio_message = "HOWITZER SHELL INCOMING — CLEAR THE MARKED AREA"
            self.radio_timer = 3.0
            return True
        direction = (dx / target_distance, dy / target_distance)
        reach = min(max_range, target_distance)
        candidates: list[tuple[float, Soldier]] = []
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            vx, vy = enemy.x - gun.x, enemy.y - gun.y
            projection = vx * direction[0] + vy * direction[1]
            cross_track = abs(vx * direction[1] - vy * direction[0])
            if 0 < projection <= reach and cross_track <= spread \
                    and self.world.line_clear((gun.x, gun.y), (enemy.x, enemy.y)):
                candidates.append((projection, enemy))
        hit = min(candidates, key=lambda item: item[0])[1] if candidates else None
        endpoint = (gun.x + direction[0] * reach, gun.y + direction[1] * reach)
        if hit:
            endpoint = (hit.x, hit.y)
        if gun.kind == "cannon":
            blast_radius = 1.6
            self.explosions.append(Explosion(endpoint[0], endpoint[1], life=0.55, radius=blast_radius))
            self._damage_world(endpoint[0], endpoint[1], blast_radius, 90.0)
            for enemy in self.enemies:
                separation = distance(endpoint, (enemy.x, enemy.y))
                if enemy.alive and separation < blast_radius:
                    splash = 62.0 * (1.0 - separation / blast_radius)
                    self._damage(enemy, splash, self.player)
        elif hit:
            self._damage(hit, damage, self.player)
        if gun.kind == "cannon":
            target_x, target_y = self.mission.objective_tile
            if distance(endpoint, (target_x + 0.5, target_y + 0.5)) <= 1.2:
                self._damage_objective(damage)
        self.tracers.append(Tracer((gun.x, gun.y), endpoint, gun.faction,
                                   life=0.16, duration=0.16, heavy=gun.kind == "cannon"))
        gun.fire_timer = cooldown
        return True

    def _nudge_open(self, x: float, y: float) -> tuple[float, float]:
        occupied = [(soldier.x, soldier.y) for soldier in self.all_soldiers if soldier.alive]
        origin_x, origin_y = int(x), int(y)
        for radius in range(9):
            candidates: list[tuple[float, float, tuple[float, float]]] = []
            for ty in range(max(0, origin_y - radius), min(self.world.height, origin_y + radius + 1)):
                for tx in range(max(0, origin_x - radius), min(self.world.width, origin_x + radius + 1)):
                    if max(abs(tx - origin_x), abs(ty - origin_y)) != radius:
                        continue
                    position = (tx + 0.5, ty + 0.5)
                    if self.world.blocked(*position) or self.world.tile_at(*position) == "wire":
                        continue
                    clearance = min((distance(position, other) for other in occupied), default=99.0)
                    if clearance < 1.05:
                        continue
                    candidates.append((distance((x, y), position), -clearance, position))
            if candidates:
                return min(candidates)[2]
        return self.world.nearest_open(x, y)

    def _home_spawn(self, faction: str, lane_offset: float = 0.0) -> tuple[float, float]:
        """Pick a rear-area spawn, never a recently captured frontline point."""
        home_x = 7.5 if faction == "us" else self.mission.width - 7.5
        if self.mission.terrain == "beach" and faction == "us":
            home_x = 8.5
        home_y = min(self.mission.height - 3.0, max(3.0, self.mission.height * 0.5 + lane_offset))
        return self._nudge_open(home_x, home_y)

    def _initial_spawn(self, faction: str, lane_offset: float = 0.0) -> tuple[float, float]:
        """Deploy defenders at the holdout point only for the opening wave."""
        if self.mission.mode == "holdout" and faction == "us":
            objective_x, objective_y = self.mission.objective_tile
            return self._nudge_open(objective_x + 0.5, objective_y + 0.5 + lane_offset)
        return self._home_spawn(faction, lane_offset)

    def _move(self, soldier: Soldier, dx: float, dy: float, dt: float, speed: float | None = None) -> None:
        length = math.hypot(dx, dy)
        if length:
            dx, dy = dx / length, dy / length
        else:
            dx = dy = 0.0
        if not soldier.player:
            push_x = push_y = 0.0
            for other in self._nearby_friends(soldier):
                if other is soldier or not other.alive or other.faction != soldier.faction:
                    continue
                away_x, away_y = soldier.x - other.x, soldier.y - other.y
                separation = math.hypot(away_x, away_y)
                if separation <= 0.02:
                    seed = sum(ord(character) for character in soldier.name)
                    angle = seed * 0.73
                    push_x += math.cos(angle)
                    push_y += math.sin(angle)
                elif separation < 0.98:
                    strength = (0.98 - separation) / 0.98
                    push_x += away_x / separation * strength
                    push_y += away_y / separation * strength
            dx += push_x * 1.7
            dy += push_y * 1.7
            length = math.hypot(dx, dy)
        if not length:
            return
        dx, dy = dx / length, dy / length
        velocity = speed if speed is not None else soldier.speed
        projected = (soldier.x + dx * velocity * dt, soldier.y + dy * velocity * dt)
        if self.world.tile_at(soldier.x, soldier.y) == "wire" or self.world.tile_at(*projected) == "wire":
            velocity *= 0.42
        nx = soldier.x + dx * velocity * dt
        ny = soldier.y + dy * velocity * dt
        if not self.world.blocked(nx, soldier.y):
            soldier.x = nx
        if not self.world.blocked(soldier.x, ny):
            soldier.y = ny

    def _nearest_hostile(self, soldier: Soldier) -> Soldier | None:
        pool = self.enemies if soldier.faction != "german" else self.player_squad + self.allies
        if self.spatial_grid:
            cell_x = int(soldier.x // self.spatial_cell_size)
            cell_y = int(soldier.y // self.spatial_cell_size)
            faction = "german" if soldier.faction != "german" else "us"
            alive = [other for x in range(cell_x - 2, cell_x + 3)
                     for y in range(cell_y - 2, cell_y + 3)
                     for other in self.spatial_grid.get((faction, x, y), ()) if other.alive]
        else:
            alive = [other for other in pool if other.alive]
        if not alive:
            alive = [other for other in pool if other.alive]

        def threat_score(other: Soldier) -> float:
            separation = distance((soldier.x, soldier.y), (other.x, other.y))
            visible_bonus = 4.5 if self.world.line_clear(
                (soldier.x, soldier.y), (other.x, other.y)) else 0.0
            attacking_bonus = 2.0 if other.target is soldier else 0.0
            engaged_penalty = 1.1 if other.target and other.target.alive \
                and other.target.faction == soldier.faction else 0.0
            wounded_bonus = (100.0 - other.hp) / 70.0
            return separation - visible_bonus - attacking_bonus - wounded_bonus + engaged_penalty

        return min(
            alive,
            key=threat_score,
            default=None,
        )

    def _tactical_offset(self, soldier: Soldier) -> tuple[float, float]:
        identity = f"{soldier.squad_id}/{soldier.name}"
        seed = sum((index + 1) * ord(character) for index, character in enumerate(identity))
        angle = (seed % 6283) / 1000.0
        radius = 0.35 + (seed % 5) * 0.11
        return math.cos(angle) * radius, math.sin(angle) * radius

    def _route_destination(self, soldier: Soldier, route: list[tuple[float, float]]) -> tuple[float, float] | None:
        start = (soldier.x, soldier.y)
        return next((point for point in reversed(route) if self.world.line_clear(start, point)),
                    route[0] if route else None)

    def build_cover(self, soldier: Soldier, aim: tuple[float, float] | None = None,
                    build_type: str = "sandbag") -> bool:
        if soldier.role != "engineer" or soldier.build_charges <= 0 or soldier.role_cooldown > 0 \
            or self.team_build_count.get(soldier.faction, 0) >= self.max_team_builds:
            return False
        if build_type not in {"sandbag", "wire"}:
            return False
        target = aim or (soldier.x + 1.0, soldier.y)
        dx, dy = target[0] - soldier.x, target[1] - soldier.y
        length = max(0.01, math.hypot(dx, dy))
        dx, dy = dx / length, dy / length
        tile_x, tile_y = int(soldier.x + dx * 1.35), int(soldier.y + dy * 1.35)
        center = (tile_x + 0.5, tile_y + 0.5)
        if distance((soldier.x, soldier.y), center) < 0.8:
            return False
        if any(other.alive and distance((other.x, other.y), center) < 0.65 for other in self.all_soldiers):
            return False
        if any(self.world.tile_at(tile_x + ox + 0.5, tile_y + oy + 0.5) == build_type
               for ox in range(-2, 3) for oy in range(-2, 3)):
            return False
        orientation = math.atan2(dy, dx) + math.pi / 2
        build = self.world.build_sandbag if build_type == "sandbag" else self.world.build_wire
        if not build(tile_x, tile_y, orientation):
            return False
        soldier.build_charges -= 1
        soldier.role_cooldown = 30.0
        self.team_build_count[soldier.faction] = self.team_build_count.get(soldier.faction, 0) + 1
        label = "SANDBAG COVER" if build_type == "sandbag" else "BARBED WIRE"
        self.radio_message = f"ENGINEER {soldier.name} BUILT {label}"
        self.radio_timer = 2.0
        return True

    def _heal_nearby(self, medic: Soldier) -> bool:
        if medic.role != "medic" or medic.role_cooldown > 0:
            return False
        candidates = [ally for ally in self.all_soldiers
                      if ally.faction == medic.faction and ally.alive
                      and ally.hp < ally.max_hp - 1 and distance((medic.x, medic.y), (ally.x, ally.y)) <= 2.4]
        if not candidates:
            return False
        patient = min(candidates, key=lambda ally: ally.hp / ally.max_hp)
        patient.hp = min(patient.max_hp, patient.hp + 24.0)
        patient.damage_flash = 0.25
        medic.role_cooldown = 8.0
        if medic.player or medic.squad_id == self.player.squad_id:
            self.radio_message = f"MEDIC {medic.name} PATCHED UP {patient.name}"
            self.radio_timer = 1.8
        return True

    def _damage_world(self, x: float, y: float, radius: float, damage: float) -> None:
        if self.mission.mode == "destroy":
            objective_x, objective_y = self.mission.objective_tile
            separation = distance((x, y), (objective_x + 0.5, objective_y + 0.5))
            if separation <= radius:
                self._damage_objective(damage * (1.0 - separation / (radius + 0.01)))
        min_x, max_x = max(0, int(x - radius)), min(self.world.width - 1, int(x + radius))
        min_y, max_y = max(0, int(y - radius)), min(self.world.height - 1, int(y + radius))
        for tile_y in range(min_y, max_y + 1):
            for tile_x in range(min_x, max_x + 1):
                if self.world.tile_hp(tile_x, tile_y) <= 0:
                    continue
                separation = distance((x, y), (tile_x + 0.5, tile_y + 0.5))
                if separation <= radius:
                    self.world.damage_tile(tile_x, tile_y, damage * (1.0 - separation / (radius + 0.01)))

    def _damage_cover_on_ray(
        self, start: tuple[float, float], end: tuple[float, float], damage: float,
    ) -> tuple[float, float] | None:
        dx, dy = end[0] - start[0], end[1] - start[1]
        steps = max(1, math.ceil(max(abs(dx), abs(dy)) * 8))
        previous_cell = (-1, -1)
        for index in range(1, steps + 1):
            fraction = index / steps
            x, y = start[0] + dx * fraction, start[1] + dy * fraction
            tile_x, tile_y = int(x), int(y)
            if (tile_x, tile_y) == previous_cell:
                continue
            previous_cell = (tile_x, tile_y)
            if self.world.tile_hp(tile_x, tile_y) <= 0:
                continue
            tile = self.world.tile_at(x, y)
            if tile in {"hedge", "building", "wall", "rock", "obstacle", "sandbag", "wire"}:
                self.world.damage_tile(tile_x, tile_y, damage)
                return tile_x + 0.5, tile_y + 0.5
        return None

    def use_role_ability(self, soldier: Soldier, aim: tuple[float, float] | None = None,
                         build_type: str = "sandbag") -> bool:
        if soldier.role == "engineer":
            return self.build_cover(soldier, aim, build_type)
        if soldier.role == "medic":
            return self._heal_nearby(soldier)
        return False

    def select_inventory_slot(self, slot: int) -> None:
        if slot in (1, 2, 3, 4):
            self.player.inventory_slot = slot

    def _active_player_weapon(self) -> tuple[Weapon, int, int]:
        player = self.player
        if player.inventory_slot == 2:
            return (WEAPONS[player.secondary_weapon_key], player.secondary_ammo,
                    player.secondary_reserve)
        return (WEAPONS[player.weapon_key], player.ammo, player.reserve)

    def _set_active_player_ammo(self, ammo: int, reserve: int) -> None:
        player = self.player
        if player.inventory_slot == 2:
            player.secondary_ammo = ammo
            player.secondary_reserve = reserve
        else:
            player.ammo = ammo
            player.reserve = reserve

    def melee_attack(self, aim: tuple[float, float]) -> bool:
        if self.melee_cooldown > 0 or self.player.inventory_slot != 3:
            return False
        return self._melee_strike(aim, bayonet=False)

    def bayonet_attack(self, aim: tuple[float, float]) -> bool:
        if self.melee_cooldown > 0 or self.player.weapon_key != "rifle":
            return False
        return self._melee_strike(aim, bayonet=True)

    def _melee_strike(self, aim: tuple[float, float], bayonet: bool) -> bool:
        player = self.player
        reach = 1.7 if bayonet else 1.45
        dx, dy = aim[0] - player.x, aim[1] - player.y
        aim_length = max(0.01, math.hypot(dx, dy))
        forward_x, forward_y = dx / aim_length, dy / aim_length
        targets = []
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            enemy_x, enemy_y = enemy.x - player.x, enemy.y - player.y
            projection = enemy_x * forward_x + enemy_y * forward_y
            cross_track = abs(enemy_x * forward_y - enemy_y * forward_x)
            if 0 < projection <= reach and cross_track <= 0.62 \
                    and self.world.line_clear((player.x, player.y), (enemy.x, enemy.y)):
                targets.append((projection, enemy))
        if targets:
            _, target = min(targets, key=lambda item: item[0])
            self._damage(target, 92.0 if bayonet else 125.0, player)
            self._tracer(player, target.x, target.y)
        player.recoil = max(0.0, player.recoil - 8.0)
        self.melee_cooldown = 0.65 if bayonet else 0.9
        self.radio_message = "BAYONET THRUST" if bayonet else "MACHETE SWING"
        self.radio_timer = 0.7
        return True

    def grenade_preview(self, aim: tuple[float, float]) -> tuple[tuple[float, float], ...]:
        player = self.player
        dx, dy = aim[0] - player.x, aim[1] - player.y
        length = max(0.01, math.hypot(dx, dy))
        reach = min(9.0, length)
        end = (player.x + dx / length * reach, player.y + dy / length * reach)
        if self.world.blocked(*end, 0.05):
            end = (player.x + dx / length * max(0.0, reach - 0.8),
                   player.y + dy / length * max(0.0, reach - 0.8))
        return (player.x, player.y), end

    def _assigned_control_point(self, soldier: Soldier) -> ControlPoint | None:
        if not self.control_points:
            return None
        side = soldier.faction
        available = [point for point in self.control_points if point.owner != side]
        if not available:
            available = self.control_points
        squad_number = 1
        last_word = soldier.squad_id.split()[-1]
        if last_word.isdigit():
            squad_number = int(last_word)
        elif soldier.squad_id == "player":
            name = soldier.name.rsplit(" ", 1)[-1]
            if name in PLAYER_NAMES:
                squad_number = PLAYER_NAMES.index(name) + 1
        # Stable assignments prevent squads from swapping lanes as they move.
        return available[(squad_number - 1) % len(available)]

    def _ai_emplacement_range(self, gun: MountedGun) -> float:
        return {"mg_nest": 18.0, "bunker": 20.0, "cannon": 28.0, "artillery": 42.0}[gun.kind]

    def _try_ai_emplacement(self, soldier: Soldier, target: Soldier, dt: float) -> bool:
        """Move an AI soldier to a vacant defense when it has a useful target."""
        # Tanks cannot use mounted emplacements
        if soldier.role == "tank":
            return False
        choices = [gun for gun in self.emplacements
                   if gun.operator is None and gun is not self.active_emplacement
                   and distance((gun.x, gun.y), (target.x, target.y)) <= self._ai_emplacement_range(gun)]
        # Filter out guns that are out of ammo (especially artillery)
        choices = [gun for gun in choices if gun.kind != "artillery" or gun.ammo > 0]
        if not choices:
            return False
        gun = min(choices, key=lambda item: distance((soldier.x, soldier.y), (item.x, item.y)))
        gun_distance = distance((soldier.x, soldier.y), (gun.x, gun.y))
        if gun_distance > 1.25:
            if gun_distance > 10.0:
                return False
            self._move(soldier, gun.x - soldier.x, gun.y - soldier.y, dt, soldier.speed * 1.12)
            return True
        gun.operator = soldier
        gun.faction = soldier.faction
        soldier.x, soldier.y = gun.x, gun.y
        return True

    def _ai_emplacement_shot(self, gun: MountedGun, operator: Soldier, target: Soldier) -> None:
        if gun.fire_timer > 0 or not target.alive:
            return
        target_distance = distance((gun.x, gun.y), (target.x, target.y))
        if target_distance > self._ai_emplacement_range(gun):
            return
        gun.facing = math.atan2(target.y - gun.y, target.x - gun.x)
        if gun.kind == "artillery":
            if gun.ammo <= 0:
                gun.operator = None
                return
            impact_x, impact_y = self.world.nearest_open(target.x, target.y)
            gun.ammo -= 1
            gun.fire_timer = 7.0
            self.artillery_strikes.append(ArtilleryStrike(impact_x, impact_y, fuse=2.8,
                                                          radius=3.6, damage=105.0, owner=operator))
            return
        if not self.world.line_clear((gun.x, gun.y), (target.x, target.y)):
            return
        if gun.kind == "cannon":
            blast_radius = 1.6
            self.explosions.append(Explosion(target.x, target.y, life=0.55, radius=blast_radius))
            self._damage_world(target.x, target.y, blast_radius, 75.0)
            for hostile in self.all_soldiers:
                separation = distance((target.x, target.y), (hostile.x, hostile.y))
                if hostile.alive and hostile.faction != operator.faction and separation < blast_radius:
                    self._damage(hostile, 48.0 * (1.0 - separation / blast_radius), operator)
            gun.fire_timer = 2.2
        else:
            damage = 18.0 if gun.kind == "mg_nest" else 25.0
            self._damage(target, damage, operator)
            gun.fire_timer = 0.14 if gun.kind == "mg_nest" else 0.18
        self.tracers.append(Tracer((gun.x, gun.y), (target.x, target.y), operator.faction,
                                   life=0.16, duration=0.16, heavy=gun.kind == "cannon"))

    def _ai(self, soldier: Soldier, dt: float) -> None:
        for strike in self.artillery_strikes:
            away_x, away_y = soldier.x - strike.x, soldier.y - strike.y
            if math.hypot(away_x, away_y) < strike.radius + 1.0:
                self._move(soldier, away_x, away_y, dt, soldier.speed * 1.2)

        soldier.ai_timer -= dt
        soldier.maneuver_timer = max(0.0, soldier.maneuver_timer - dt)
        soldier.path_timer = max(0.0, soldier.path_timer - dt)
        should_rethink = soldier.ai_timer <= 0 or soldier.target is None or not soldier.target.alive
        target_changed = False
        if should_rethink:
            previous_target = soldier.target
            soldier.target = self._nearest_hostile(soldier)
            soldier.ai_timer = self.random.uniform(0.42, 0.72)
            if soldier.target is not previous_target:
                target_changed = True
                soldier.aim_timer = self.random.uniform(0.18, 0.42)
                soldier.path_timer = 0.0
        target = soldier.target
        weapon = WEAPONS[soldier.weapon_key]
        target_distance = distance((soldier.x, soldier.y), (target.x, target.y)) if target else float("inf")
        mounted_gun = next((gun for gun in self.emplacements if gun.operator is soldier), None)
        if mounted_gun:
            if target and target_distance <= self._ai_emplacement_range(mounted_gun):
                self._ai_emplacement_shot(mounted_gun, soldier, target)
                return
            mounted_gun.operator = None
        if target and self._try_ai_emplacement(soldier, target, dt):
            return
        self._heal_nearby(soldier)
        if target and soldier.squad_id != "player" and soldier.role == "assault" \
                and not soldier.grenade_decided and soldier.grenades_remaining > 0 \
                and target_distance <= 2.75 \
                and self.ai_grenades_in_flight < 1 and self.ai_grenade_cooldown <= 0 \
                and self.world.line_clear((soldier.x, soldier.y), (target.x, target.y)) \
                and not any(friend is not soldier and friend.alive
                            and distance((friend.x, friend.y), (target.x, target.y)) <= 2.25
                            for friend in self._nearby_friends(soldier)):
            soldier.grenade_decided = True
            if self.random.random() < 0.01:
                if self._throw_grenade(soldier, (target.x, target.y)):
                    self.ai_grenade_cooldown = 25.0
        if target and soldier.role == "engineer" and target_distance <= 6.0 \
                and soldier.role_cooldown <= 0:
            self.build_cover(soldier, (target.x, target.y))
        can_engage = bool(target and target_distance <= weapon.range_tiles
                          and (soldier.role == "mortar" or self.world.line_clear(
                              (soldier.x, soldier.y), (target.x, target.y))))
        if can_engage and target:
            tile = self.world.tile_at(soldier.x, soldier.y)
            soldier.crouched = soldier.hp < 50 or tile in {"trench", "crater"}
            if soldier.ammo <= 0 and soldier.reload_timer <= 0 and soldier.reserve > 0:
                soldier.reload_timer = weapon.reload_time
                soldier.aim_timer = max(soldier.aim_timer, 0.25)
            elif soldier.fire_timer <= 0 and soldier.reload_timer <= 0 and soldier.aim_timer <= 0:
                if soldier.role == "mortar":
                    self._ai_mortar_shot(soldier, target)
                else:
                    self._ai_shot(soldier, target)
                soldier.ammo -= 1
                fire_delay = weapon.fire_interval * self.random.uniform(4.0, 6.0)
                if soldier.role == "tank":
                    fire_delay = self.random.uniform(3.0, 4.2)
                elif soldier.role == "mortar":
                    fire_delay = self.random.uniform(5.2, 7.0)
                elif soldier.role == "assault":
                    fire_delay *= 0.82
                soldier.fire_timer = max(0.45, fire_delay)
                soldier.aim_timer = self.random.uniform(0.12, 0.3)
            if soldier.role == "mortar":
                soldier.destination = None
                return
            if target_distance <= weapon.range_tiles * 0.85:
                if soldier.maneuver_timer <= 0:
                    soldier.maneuver_side = self.random.choice((-1, 1))
                    soldier.maneuver_timer = self.random.uniform(0.65, 1.35)
                dx = target.x - soldier.x
                dy = target.y - soldier.y
                retreat = -0.5 if target_distance < 2.3 else 0.12 if target_distance > weapon.range_tiles * 0.65 else 0.0
                move_x = -dy * soldier.maneuver_side + dx / max(target_distance, 0.01) * retreat
                move_y = dx * soldier.maneuver_side + dy / max(target_distance, 0.01) * retreat
                soldier.destination = None
                move_factor = 0.72 if soldier.role == "assault" else 0.58
                self._move(soldier, move_x, move_y, dt, soldier.speed * move_factor)
                return

        if target_changed or soldier.path_timer <= 0:
            point = self._assigned_control_point(soldier)
            route: list[tuple[float, float]] = []
            if point and point.owner != soldier.faction \
                    and distance((soldier.x, soldier.y), (point.x, point.y)) > 3.0:
                offset_x, offset_y = self._tactical_offset(soldier)
                route = self.world.route_to_firing_position(
                    (soldier.x, soldier.y), (point.x + offset_x, point.y + offset_y), 1.0)
            if not route and target and not can_engage:
                offset_x, offset_y = self._tactical_offset(soldier)
                route = self.world.route_to_firing_position(
                    (soldier.x, soldier.y), (target.x + offset_x, target.y + offset_y),
                    weapon.range_tiles)
            soldier.destination = self._route_destination(soldier, route)
            soldier.path_timer = self.random.uniform(0.75, 1.15)

        if soldier.destination:
            soldier.crouched = False
            move_x = soldier.destination[0] - soldier.x
            move_y = soldier.destination[1] - soldier.y
            if math.hypot(move_x, move_y) < 0.12:
                soldier.destination = None
                soldier.path_timer = 0.0
            else:
                self._move(soldier, move_x, move_y, dt, soldier.speed * 1.08)

    def _ai_shot(self, shooter: Soldier, target: Soldier) -> None:
        weapon = WEAPONS[shooter.weapon_key]
        if not self.world.line_clear((shooter.x, shooter.y), (target.x, target.y)):
            self._damage_cover_on_ray((shooter.x, shooter.y), (target.x, target.y), weapon.damage * 0.35)
            return
        separation = distance((shooter.x, shooter.y), (target.x, target.y))
        accuracy = max(0.24, min(0.82, 0.78 - 0.48 * separation / weapon.range_tiles))
        accuracy += 0.06 if shooter.crouched else 0.0
        elevation_advantage = self.world.elevation_at(shooter.x, shooter.y) - self.world.elevation_at(target.x, target.y)
        accuracy = min(0.92, accuracy + max(0, elevation_advantage) * 0.08)
        if self.random.random() > accuracy:
            miss_x = target.x + self.random.uniform(-0.65, 0.65)
            miss_y = target.y + self.random.uniform(-0.65, 0.65)
            self._tracer(shooter, miss_x, miss_y)
            return
        target.damage_flash = 0.12
        damage = weapon.damage * self.random.uniform(0.22, 0.38)
        if shooter.role == "tank":
            damage = weapon.damage * self.random.uniform(1.05, 1.35)
            self.explosions.append(Explosion(target.x, target.y, life=0.65, radius=2.2))
            self._damage_world(target.x, target.y, 1.8, 180.0)
            for nearby in self.all_soldiers:
                if nearby is not target and nearby.alive and nearby.faction != shooter.faction:
                    splash_distance = distance((target.x, target.y), (nearby.x, nearby.y))
                    if splash_distance < 1.8:
                        self._damage(nearby, 54.0 * (1.0 - splash_distance / 1.8), shooter)
        if shooter.role == "support":
            damage *= 1.25
        if elevation_advantage > 0:
            damage *= 1.0 + min(0.18, elevation_advantage * 0.06)
        damage *= self.world.cover_factor(target.x, target.y)
        if target.crouched:
            damage *= 0.62
        self._damage(target, damage, shooter)
        self._tracer(shooter, target.x, target.y)

    def _ai_mortar_shot(self, shooter: Soldier, target: Soldier) -> None:
        """Launch an indirect-fire shell toward a hostile's current position."""
        spread = self.random.uniform(-1.6, 1.6)
        angle = self.random.uniform(0.0, math.tau)
        impact = self.world.nearest_open(target.x + math.cos(angle) * spread,
                                         target.y + math.sin(angle) * spread)
        start = (shooter.x, shooter.y)
        duration = min(2.4, max(1.0, distance(start, impact) * 0.075))
        self.mortar_shells.append(MortarShell(start, impact, shooter.faction, owner=shooter,
                                              life=duration, duration=duration))

    def _damage(self, target: Soldier, damage: float, shooter: Soldier | None = None) -> None:
        if shooter and shooter.player:
            damage *= self.player_damage_multiplier
        elif target.faction == "us" and shooter and shooter.faction == "german":
            damage *= self.incoming_damage_multiplier
        if target.role == "tank" and shooter and shooter.weapon_key != "tank":
            damage *= 0.32
        target.hp = max(0.0, target.hp - damage)
        if target.hp <= 0 and target.alive:
            target.alive = False
            lost_side = "german" if target.faction == "german" else "us"
            self.tickets[lost_side] = max(0.0, self.tickets[lost_side] - 1.0)
            if shooter:
                shooter.kills += 1
                if shooter.player or shooter.squad_id == self.player.squad_id:
                    self.kills += 1
        if shooter and shooter.player:
            self.hit_marker_timer = 0.16

    def _damage_objective(self, damage: float) -> None:
        if self.mission.mode != "destroy" or self.objective_health <= 0:
            return
        self.objective_health = max(0.0, self.objective_health - damage)
        self.radio_message = f"{self.mission.objective}: {int(self.objective_health)} STRUCTURE HP"
        self.radio_timer = 1.0

    def _tracer(self, shooter: Soldier, target_x: float, target_y: float) -> None:
        self.tracers.append(Tracer((shooter.x, shooter.y), (target_x, target_y), shooter.faction,
                                   life=0.12, duration=0.12, heavy=shooter.weapon_key in {"lmg", "mg", "tank"}))

    def _player_shot(self, aim: tuple[float, float], aiming: bool, moving: bool) -> bool:
        shooter = self.player
        if shooter.inventory_slot not in (1, 2):
            return False
        weapon, ammo, _ = self._active_player_weapon()
        if shooter.reload_timer > 0:
            return False
        if ammo == 0:
            self.reload()
            return False
        if shooter.fire_timer > 0:
            return False
        shooter.fire_timer = weapon.fire_interval
        if shooter.role == "assault":
            shooter.fire_timer *= 0.82
        self._set_active_player_ammo(ammo - 1, shooter.reserve if shooter.inventory_slot == 1
                                     else shooter.secondary_reserve)
        shooter.recoil = min(36.0, shooter.recoil + (3.4 if aiming else 5.0))
        max_range = weapon.range_tiles
        ax, ay = aim[0] - shooter.x, aim[1] - shooter.y
        target_distance = math.hypot(ax, ay)
        if target_distance == 0:
            return True
        direction = (ax / target_distance, ay / target_distance)
        spread_px = weapon.spread * (0.50 if aiming else 1.0)
        if moving:
            spread_px *= 1.75
        spread_px += shooter.recoil * 0.7
        spread_tiles = spread_px / TILE
        spread_angle = self.random.gauss(0.0, spread_tiles / max(2.0, target_distance) * 0.65)
        shot_angle = math.atan2(direction[1], direction[0]) + spread_angle
        direction = (math.cos(shot_angle), math.sin(shot_angle))
        shot_range = min(max_range, target_distance)
        ray_end = (shooter.x + direction[0] * shot_range,
                   shooter.y + direction[1] * shot_range)
        cover_hit = self._damage_cover_on_ray((shooter.x, shooter.y), ray_end, weapon.damage * 0.7)
        candidates: list[tuple[float, Soldier]] = []
        cover_projection = float("inf")
        if cover_hit:
            cover_projection = ((cover_hit[0] - shooter.x) * direction[0]
                                + (cover_hit[1] - shooter.y) * direction[1])
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            vx, vy = enemy.x - shooter.x, enemy.y - shooter.y
            projection = vx * direction[0] + vy * direction[1]
            if projection < 0 or projection > shot_range:
                continue
            perpendicular = abs(vx * direction[1] - vy * direction[0])
            if projection < cover_projection and perpendicular <= 0.2 \
                    and self.world.line_clear((shooter.x, shooter.y), (enemy.x, enemy.y)):
                candidates.append((projection, enemy))
        hit = min(candidates, key=lambda pair: pair[0])[1] if candidates else None
        objective_hit = False
        if self.mission.mode == "destroy":
            objective_x, objective_y = self.mission.objective_tile
            objective_center = (objective_x + 0.5, objective_y + 0.5)
            vx, vy = objective_center[0] - shooter.x, objective_center[1] - shooter.y
            projection = vx * direction[0] + vy * direction[1]
            cross_track = abs(vx * direction[1] - vy * direction[0])
            nearest_enemy = min((pair[0] for pair in candidates), default=float("inf"))
            objective_hit = (0 < projection <= shot_range and projection < nearest_enemy
                             and cross_track <= 1.0 and self.world.line_clear(
                                 (shooter.x, shooter.y), objective_center))
            if objective_hit:
                self._damage_objective(weapon.damage * 1.12)
                ray_end = objective_center
        if cover_hit:
            ray_end = cover_hit
        if hit and not objective_hit:
            ray_end = (hit.x, hit.y)
            hit.damage_flash = 0.12
            self._damage(hit, weapon.damage, shooter)
        self._tracer(shooter, *ray_end)
        if ammo - 1 == 0:
            self.radio_message = "MAGAZINE EMPTY — reload with R"
            self.radio_timer = 1.8
        return True

    def reload(self) -> None:
        player = self.player
        if player.inventory_slot not in (1, 2):
            return
        weapon, ammo, reserve = self._active_player_weapon()
        if player.reload_timer > 0 or ammo >= weapon.magazine or reserve <= 0:
            return
        player.reload_timer = weapon.reload_time
        player.reloading_slot = player.inventory_slot
        self.radio_message = f"RELOADING {weapon.name}"
        self.radio_timer = 1.0

    def throw_grenade(self, aim: tuple[float, float]) -> bool:
        if self.player.inventory_slot != 4 or self.grenades <= 0 or self.grenade_cooldown > 0:
            return False
        if not self._throw_grenade(self.player, aim):
            return False
        self.grenade_cooldown = 3.0
        return True

    def _throw_grenade(self, soldier: Soldier, aim: tuple[float, float]) -> bool:
        if soldier.grenades_remaining <= 0 or soldier.grenade_used:
            return False
        dx, dy = aim[0] - soldier.x, aim[1] - soldier.y
        length = max(0.01, math.hypot(dx, dy))
        reach = min(9.0, length)
        end = (soldier.x + dx / length * reach, soldier.y + dy / length * reach)
        if self.world.blocked(*end, 0.05):
            reach = max(0.0, reach - 0.8)
            end = (soldier.x + dx / length * reach, soldier.y + dy / length * reach)
        grenade = ThrownGrenade((soldier.x, soldier.y), end, soldier.faction, owner=soldier)
        grenade.duration = 0.48 + distance(grenade.start, end) * 0.055
        grenade.life = grenade.duration
        self.thrown_grenades.append(grenade)
        soldier.grenades_remaining -= 1
        soldier.grenade_used = True
        if not soldier.player:
            self.ai_grenades_in_flight += 1
        return True

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper, mouse_buttons: tuple[bool, ...],
               aim: tuple[float, float], aiming: bool) -> None:
        self._rebuild_spatial_grid()
        self.elapsed += dt
        self.grenade_cooldown = max(0.0, self.grenade_cooldown - dt)
        self.ai_grenade_cooldown = max(0.0, self.ai_grenade_cooldown - dt)
        for gun in self.emplacements:
            gun.fire_timer = max(0.0, gun.fire_timer - dt)
            if gun.operator and not gun.operator.alive:
                gun.operator = None
        self.radio_timer = max(0.0, self.radio_timer - dt)
        self.hit_marker_timer = max(0.0, self.hit_marker_timer - dt)
        active_tracers = []
        for effect in self.tracers:
            effect.life -= dt
            if effect.life > 0:
                active_tracers.append(effect)
        self.tracers = active_tracers
        active_explosions = []
        for effect in self.explosions:
            effect.life -= dt
            if effect.life > 0:
                active_explosions.append(effect)
        self.explosions = active_explosions
        active_grenades: list[ThrownGrenade] = []
        for grenade in self.thrown_grenades:
            grenade.life -= dt
            if grenade.life > 0:
                active_grenades.append(grenade)
                continue
            x, y = grenade.end
            self.explosions.append(Explosion(x, y, life=0.8, radius=grenade.radius))
            self._damage_world(x, y, grenade.radius, 165.0)
            for soldier in self.all_soldiers:
                separation = distance((x, y), (soldier.x, soldier.y))
                if soldier.alive and separation < grenade.radius \
                        and self.world.line_clear((x, y), (soldier.x, soldier.y)):
                    damage = 75.0 * (1.0 - separation / grenade.radius)
                    damage *= self.world.cover_factor(soldier.x, soldier.y)
                    if soldier.crouched:
                        damage *= 0.72
                    self._damage(soldier, damage, grenade.owner)
        self.thrown_grenades = active_grenades
        self.ai_grenades_in_flight = sum(
            grenade.owner is not None and not grenade.owner.player for grenade in self.thrown_grenades)
        active_shells: list[MortarShell] = []
        for shell in self.mortar_shells:
            shell.life -= dt
            if shell.life > 0:
                active_shells.append(shell)
                continue
            x, y = shell.end
            self.explosions.append(Explosion(x, y, life=0.8, radius=shell.radius))
            self._damage_world(x, y, shell.radius, 260.0)
            for soldier in self.all_soldiers:
                separation = distance((x, y), (soldier.x, soldier.y))
                if soldier.alive and separation < shell.radius:
                    damage = shell.damage * (1.0 - separation / shell.radius)
                    damage *= self.world.cover_factor(soldier.x, soldier.y)
                    if soldier.crouched:
                        damage *= 0.72
                    self._damage(soldier, damage, shell.owner)
        self.mortar_shells = active_shells
        self.melee_cooldown = max(0.0, self.melee_cooldown - dt)
        for soldier in self.all_soldiers:
            soldier.fire_timer = max(0.0, soldier.fire_timer - dt)
            soldier.recoil = max(0.0, soldier.recoil - 24 * dt)
            soldier.damage_flash = max(0.0, soldier.damage_flash - dt)
            soldier.aim_timer = max(0.0, soldier.aim_timer - dt)
            soldier.wire_timer = max(0.0, soldier.wire_timer - dt)
            soldier.role_cooldown = max(0.0, soldier.role_cooldown - dt)
            if soldier.alive and self.world.tile_at(soldier.x, soldier.y) == "wire" \
                    and soldier.wire_timer <= 0:
                self._damage(soldier, 4.0)
                soldier.wire_timer = 0.8
            if soldier.reload_timer > 0:
                soldier.reload_timer = max(0.0, soldier.reload_timer - dt)
                if soldier.reload_timer == 0:
                    if soldier.reloading_slot == 2:
                        weapon = WEAPONS[soldier.secondary_weapon_key]
                        loaded = min(weapon.magazine, soldier.secondary_reserve)
                        soldier.secondary_ammo = loaded
                        soldier.secondary_reserve -= loaded
                    else:
                        weapon = WEAPONS[soldier.weapon_key]
                        loaded = min(weapon.magazine, soldier.reserve)
                        soldier.ammo = loaded
                        soldier.reserve -= loaded
            if soldier.hp < 42 and not soldier.player:
                soldier.crouched = True

        player = self.player
        if player.alive:
            if self.active_emplacement:
                player.crouched = False
                if mouse_buttons[0]:
                    self._mounted_shot(aim)
            else:
                player.crouched = bool(keys[pygame.K_LCTRL] or keys[pygame.K_c])
                dx = float(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - float(keys[pygame.K_a] or keys[pygame.K_LEFT])
                dy = float(keys[pygame.K_s] or keys[pygame.K_DOWN]) - float(keys[pygame.K_w] or keys[pygame.K_UP])
                sprinting = bool(keys[pygame.K_LSHIFT]) and not aiming and not player.crouched
                speed = player.speed * (1.55 if sprinting else 0.58 if player.crouched else 0.78 if aiming else 1.0)
                if player.role == "assault":
                    speed *= 1.15
                if dx or dy:
                    self._move(player, dx, dy, dt, speed)
                if mouse_buttons[0]:
                    self._player_shot(aim, aiming, bool(dx or dy or sprinting))
        else:
            if self.active_emplacement:
                self.active_emplacement.operator = None
            self.active_emplacement = None
            next_alive = next((i for i, soldier in enumerate(self.player_squad) if soldier.alive), None)
            if next_alive is not None:
                self.switch_soldier(next_alive)
                self.radio_message = "SOLDIER DOWN — you took control of the next squadmate"
                self.radio_timer = 3.0
            elif self.tickets["us"] <= 0:
                self.defeat = True
            else:
                if self.player_respawn_timer is None:
                    self.player_respawn_timer = 5.0
                self.player_respawn_timer -= dt
                self.radio_message = f"SQUAD WIPED — reinforcement in {max(0, self.player_respawn_timer):.1f}s"
                self.radio_timer = 0.5
                if self.player_respawn_timer <= 0:
                    self._respawn_player()

        for soldier in self.allies + self.enemies + [s for s in self.player_squad if s is not self.player]:
            if soldier.alive:
                self._ai(soldier, dt)
        self._update_artillery(dt)
        self._update_objective(dt)
        self._update_reinforcements(dt)
        self._update_random_events(dt)

    def switch_soldier(self, index: int) -> None:
        if not 0 <= index < len(self.player_squad) or not self.player_squad[index].alive:
            return
        self.active_emplacement = None
        self.player_squad[self.selected_index].player = False
        self.selected_index = index
        self.player_squad[index].player = True
        self.player_squad[index].target = None
        self.player_squad[index].destination = None

    def _update_objective(self, dt: float) -> None:
        for point in self.control_points:
            us_presence = sum(
                soldier.alive and distance((soldier.x, soldier.y), (point.x, point.y)) <= 3.2
                for soldier in self.player_squad + self.allies
            )
            german_presence = sum(
                soldier.alive and distance((soldier.x, soldier.y), (point.x, point.y)) <= 3.2
                for soldier in self.enemies
            )
            pressure = us_presence - german_presence
            old_owner = point.owner
            if pressure:
                point.progress += math.copysign(dt * min(1.6, 0.52 * abs(pressure)) / 8.0, pressure)
                point.progress = max(-1.0, min(1.0, point.progress))
            if point.progress >= 1.0:
                point.owner = "us"
                point.progress = 1.0
            elif point.progress <= -1.0:
                point.owner = "german"
                point.progress = -1.0
            elif not pressure and point.owner == "us":
                point.progress = 1.0
            elif not pressure and point.owner == "german":
                point.progress = -1.0
            if point.owner != old_owner:
                side_name = "ALLIED" if point.owner == "us" else "GERMAN"
                self.radio_message = f"SECTOR {point.label} CAPTURED BY {side_name} FORCES"
                self.radio_timer = 3.0

        if self.mission.mode == "holdout":
            hold_point = self.control_points[-1]
            if hold_point.owner == "us":
                self.holdout_remaining = max(0.0, self.holdout_remaining - dt)
                self.holdout_overrun_timer = 0.0
            elif hold_point.owner == "german":
                self.holdout_overrun_timer += dt
            else:
                self.holdout_overrun_timer = 0.0
            if self.tickets["german"] <= 0:
                self.complete = True
                self.radio_message = "ENEMY FORCE ROUTED — POSITION SECURED"
                self.radio_timer = 8.0
            elif self.holdout_overrun_timer >= self.holdout_overrun_grace or self.tickets["us"] <= 0:
                self.defeat = True
                self.radio_message = "HOLDOUT OVERRUN — THE POSITION HAS FALLEN"
                self.radio_timer = 8.0
            elif self.holdout_remaining <= 0:
                self.complete = True
                self.radio_message = "HOLDOUT COMPLETE — RELIEF FORCES ARRIVED"
                self.radio_timer = 8.0
            return
        if self.mission.mode == "destroy":
            if self.objective_health <= 0:
                self.complete = True
                self.radio_message = "TARGET DESTROYED — OBJECTIVE COMPLETE"
                self.radio_timer = 8.0
            elif self.tickets["german"] <= 0:
                self.complete = True
                self.radio_message = "ENEMY FORCE ROUTED — OBJECTIVE SECURED"
                self.radio_timer = 8.0
            elif self.tickets["us"] <= 0:
                self.defeat = True
                self.radio_message = "ALLIED TICKETS DEPLETED — FRONTLINE LOST"
                self.radio_timer = 8.0
            return

        us_owned = sum(point.owner == "us" for point in self.control_points)
        german_owned = sum(point.owner == "german" for point in self.control_points)
        if self.control_points and us_owned == len(self.control_points):
            self.complete = True
            self.radio_message = "ALL SECTORS SECURED — FRONTLINE WON"
            self.radio_timer = 8.0
            return
        if self.control_points and german_owned == len(self.control_points):
            self.defeat = True
            self.radio_message = "ALL SECTORS OVERRUN — FRONTLINE LOST"
            self.radio_timer = 8.0
            return
        if us_owned > german_owned:
            drain = 0.9 + 0.65 * (us_owned - german_owned - 1)
            self.tickets["german"] = max(0.0, self.tickets["german"] - dt * drain)
        elif german_owned > us_owned:
            drain = 0.9 + 0.65 * (german_owned - us_owned - 1)
            self.tickets["us"] = max(0.0, self.tickets["us"] - dt * drain)
        if self.tickets["german"] <= 0:
            self.complete = True
            self.radio_message = "GERMAN TICKETS DEPLETED — FRONTLINE WON"
            self.radio_timer = 8.0
        elif self.tickets["us"] <= 0:
            self.defeat = True
            self.radio_message = "ALLIED TICKETS DEPLETED — FRONTLINE LOST"
            self.radio_timer = 8.0

    def _update_artillery(self, dt: float) -> None:
        if self.complete or self.defeat:
            return
        self.artillery_timer -= dt
        if self.artillery_timer <= 0 and self.control_points:
            pressure = [
                sum(soldier.alive and distance((soldier.x, soldier.y), (point.x, point.y)) <= 8.0
                    for soldier in self.all_soldiers)
                for point in self.control_points
            ]
            busiest = max(pressure)
            candidates = [point for point, count in zip(self.control_points, pressure) if count == busiest]
            target = self.random.choice(candidates)
            impact_x, impact_y = self.world.nearest_open(
                target.x + self.random.uniform(-1.5, 1.5),
                target.y + self.random.uniform(-1.5, 1.5),
            )
            salvo_size = self.random.choice((2, 2, 3))
            for index in range(salvo_size):
                angle = math.tau * index / salvo_size + self.random.uniform(-0.3, 0.3)
                spread = self.random.uniform(0.8, 2.8)
                shell_x, shell_y = self.world.nearest_open(
                    impact_x + math.cos(angle) * spread,
                    impact_y + math.sin(angle) * spread,
                )
                self.artillery_strikes.append(
                    ArtilleryStrike(shell_x, shell_y, fuse=self.random.uniform(2.7, 3.5)))
            self.artillery_timer = self.random.uniform(15.0, 21.0)
            self.radio_message = "INCOMING ARTILLERY — MOVE TO COVER"
            self.radio_timer = 2.4

        remaining: list[ArtilleryStrike] = []
        for strike in self.artillery_strikes:
            strike.fuse -= dt
            if strike.fuse > 0:
                remaining.append(strike)
                continue
            self.explosions.append(Explosion(strike.x, strike.y, life=0.8, radius=strike.radius))
            self._damage_world(strike.x, strike.y, strike.radius, 390.0)
            for soldier in self.all_soldiers:
                separation = distance((strike.x, strike.y), (soldier.x, soldier.y))
                if soldier.alive and separation < strike.radius:
                    damage = strike.damage * (1.0 - separation / strike.radius)
                    damage *= self.world.cover_factor(soldier.x, soldier.y)
                    if soldier.crouched:
                        damage *= 0.65
                    self._damage(soldier, damage, strike.owner)
            self.radio_message = "ARTILLERY IMPACT"
            self.radio_timer = 1.4
        self.artillery_strikes = remaining

    def _update_reinforcements(self, dt: float) -> None:
        self.reinforcement_clock -= dt
        if self.reinforcement_clock > 0 or self.complete or self.defeat:
            return
        self.reinforcement_clock = 11.0
        self.reinforcement_wave += 1
        self._spawn_reserves("us")
        self._spawn_reserves("german")

    def _spawn_reserves(self, faction: str, maximum: int = 6) -> None:
        if self.tickets[faction] <= 0:
            return
        if faction == "us":
            population = sum(soldier.alive for soldier in self.player_squad + self.allies)
            capacity = 78
            destination_list = self.allies
            faction_label = "us"
        else:
            population = sum(soldier.alive for soldier in self.enemies)
            capacity = 78
            destination_list = self.enemies
            faction_label = "german"
        count = min(maximum, max(0, capacity - population))
        if count <= 0:
            return
        for _ in range(count):
            self.spawn_serial += 1
            x, y = self._home_spawn(faction, self.random.uniform(-5.0, 5.0))
            weapon_pool = ALLY_WEAPONS if faction == "us" else ENEMY_WEAPONS
            role_pool = ALLY_ROLES if faction == "us" else ENEMY_ROLES
            role = role_pool[self.spawn_serial % len(role_pool)]
            weapon = "lmg" if role == "support" and faction == "us" else \
                "mg" if role == "support" else self.random.choice(weapon_pool)
            if role == "mortar":
                weapon = "mortar"
            squad_id = f"{faction_label.title()} reserve {self.spawn_serial}"
            name = f"{squad_id} {role}"
            destination_list.append(Soldier(name, faction, squad_id, x, y, weapon,
                                            hp=90, speed=self.random.uniform(1.9, 2.5), role=role))
        self._issue_ai_grenades(destination_list[-count:])
        self.radio_message = "BOTH SIDES ARE RECEIVING FRONTLINE REINFORCEMENTS"
        self.radio_timer = 2.5

    def _update_random_events(self, dt: float) -> None:
        if self.complete or self.defeat:
            return
        self.active_event_timer = max(0.0, self.active_event_timer - dt)
        self.random_event_timer -= dt
        if self.random_event_timer <= 0:
            event = self.random.choices(("air", "barrage", "reinforcements"),
                                        weights=(0.42, 0.38, 0.20), k=1)[0]
            if event == "air":
                busiest = max(self.control_points,
                              key=lambda point: sum(soldier.alive and
                                  distance((soldier.x, soldier.y), (point.x, point.y)) <= 9
                                  for soldier in self.all_soldiers))
                self.air_run = {"elapsed": 0.0, "duration": 5.5,
                                "lane_y": busiest.y + self.random.uniform(-2.0, 2.0)}
                self.air_run_hits.clear()
                self.active_event_message = "ENEMY AIRCRAFT — STRAFING RUN INBOUND"
            elif event == "barrage":
                target = self.random.choice(self.control_points)
                for index in range(7):
                    angle = math.tau * index / 7 + self.random.uniform(-0.2, 0.2)
                    radius = self.random.uniform(1.0, 5.0)
                    x, y = self.world.nearest_open(target.x + math.cos(angle) * radius,
                                                   target.y + math.sin(angle) * radius)
                    self.artillery_strikes.append(ArtilleryStrike(
                        x, y, fuse=self.random.uniform(3.0, 4.0), radius=4.8, damage=135.0))
                self.active_event_message = "MASSIVE ARTILLERY BARRAGE — TAKE COVER"
            else:
                self._spawn_reserves("us", maximum=12)
                self._spawn_reserves("german", maximum=12)
                self.active_event_message = "SUPER REINFORCEMENTS — BOTH SIDES DEPLOYED"
            self.active_event_timer = 6.0
            self.radio_message = self.active_event_message
            self.radio_timer = 5.0
            self.random_event_timer = self.random.uniform(75.0, 110.0)

        if self.air_run:
            self.air_run["elapsed"] += dt
            progress = min(1.0, self.air_run["elapsed"] / self.air_run["duration"])
            plane_x = -5.0 + (self.world.width + 10.0) * progress
            lane_y = self.air_run["lane_y"]
            for soldier in self.all_soldiers:
                if soldier.alive and soldier not in self.air_run_hits \
                        and abs(soldier.x - plane_x) <= 0.75 and abs(soldier.y - lane_y) <= 1.15:
                    self._damage(soldier, 36.0)
                    self.air_run_hits.add(soldier)
            self.tracers.append(Tracer((plane_x - 0.8, lane_y), (plane_x + 0.8, lane_y),
                                       "german", life=0.07, duration=0.07, heavy=True))
            if progress >= 1.0:
                self.air_run = None
                self.air_run_hits.clear()

    def _respawn_player(self) -> None:
        replacements: list[Soldier] = []
        for index, old in enumerate(self.player_squad):
            x, y = self._home_spawn("us", (index - 3.5) * 0.85)
            replacement = Soldier(old.name, "us", "player", x, y, old.weapon_key,
                                  hp=old.max_hp, max_hp=old.max_hp, player=(index == 0), speed=3.0,
                                  role=old.role, secondary_weapon_key=old.secondary_weapon_key,
                                  secondary_reserve=old.secondary_reserve,
                                  inventory_slot=old.inventory_slot)
            replacement.reserve = old.reserve
            replacement.secondary_reserve = old.secondary_reserve
            replacement.kills = old.kills
            replacement.build_charges = old.build_charges
            replacement.grenades_remaining = 1 if index == 0 else 0
            replacements.append(replacement)
        self.player_squad = replacements
        self.selected_index = 0
        self.player_respawn_timer = None
        self.radio_message = "SQUAD RESTORED AT REAR BASE — BACK TO THE FRONT"
        self.radio_timer = 3.0
