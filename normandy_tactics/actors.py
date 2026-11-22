"""Soldier, weapon, and effect data for the real-time battle simulation."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Weapon:
    name: str
    magazine: int
    reserve: int
    damage: float
    fire_interval: float
    spread: float
    reload_time: float
    range_tiles: float
    automatic: bool = False


WEAPONS = {
    "rifle": Weapon("M1 GARAND", 8, 64, 46, 0.34, 13, 1.65, 12),
    "pistol": Weapon("COLT M1911", 7, 42, 34, 0.24, 18, 1.35, 7),
    "smg": Weapon("THOMPSON", 30, 180, 23, 0.105, 25, 2.1, 8, True),
    "lmg": Weapon("BROWNING", 50, 200, 27, 0.12, 31, 3.2, 11, True),
    "bolt": Weapon("KAR 98K", 5, 50, 52, 0.72, 10, 2.0, 14),
    "mg": Weapon("MG 42", 60, 240, 24, 0.095, 27, 12, 12, True),
    "mp40": Weapon("MP 40", 32, 192, 22, 0.13, 27, 2.0, 8, True),
    "tank": Weapon("TANK CANNON", 1, 14, 100, 2.4, 9, 2.0, 18),
    "mortar": Weapon("60 MM MORTAR", 1, 18, 92, 4.8, 0, 3.2, 20),
}


@dataclass(eq=False)
class Soldier:
    name: str
    faction: str
    squad_id: str
    x: float
    y: float
    weapon_key: str
    hp: float = 100.0
    max_hp: float = 100.0
    speed: float = 2.0
    role: str = "rifleman"
    secondary_weapon_key: str = "pistol"
    secondary_ammo: int = 0
    secondary_reserve: int = 0
    inventory_slot: int = 1
    player: bool = False
    alive: bool = True
    ammo: int = 0
    reserve: int = 0
    fire_timer: float = 0.0
    ai_timer: float = 0.0
    reload_timer: float = 0.0
    reloading_slot: int = 1
    recoil: float = 0.0
    aim_timer: float = 0.0
    target: Soldier | None = None
    destination: tuple[float, float] | None = None
    crouched: bool = False
    kills: int = 0
    damage_flash: float = 0.0
    wire_timer: float = 0.0
    role_cooldown: float = 0.0
    maneuver_timer: float = 0.0
    maneuver_side: int = 1
    path_timer: float = 0.0
    build_charges: int = 2
    grenades_remaining: int = 1
    grenade_decided: bool = False

    def __post_init__(self) -> None:
        weapon = WEAPONS[self.weapon_key]
        if self.ammo <= 0:
            self.ammo = weapon.magazine
        if self.reserve <= 0:
            self.reserve = weapon.reserve
        secondary = WEAPONS[self.secondary_weapon_key]
        if self.secondary_ammo <= 0:
            self.secondary_ammo = secondary.magazine
        if self.secondary_reserve <= 0:
            self.secondary_reserve = secondary.reserve


@dataclass
class Tracer:
    start: tuple[float, float]
    end: tuple[float, float]
    faction: str
    life: float = 0.11
    duration: float = 0.11
    heavy: bool = False


@dataclass
class Explosion:
    x: float
    y: float
    life: float = 0.48
    radius: float = 12.0


@dataclass
class ArtilleryStrike:
    x: float
    y: float
    fuse: float = 2.4
    radius: float = 4.2
    damage: float = 94.0
    owner: Soldier | None = None


@dataclass
class MortarShell:
    start: tuple[float, float]
    end: tuple[float, float]
    faction: str
    owner: Soldier | None = None
    life: float = 1.5
    duration: float = 1.5
    radius: float = 3.5
    damage: float = 96.0

    @property
    def progress(self) -> float:
        return max(0.0, min(1.0, 1.0 - self.life / self.duration))

    @property
    def position(self) -> tuple[float, float]:
        progress = self.progress
        return (self.start[0] + (self.end[0] - self.start[0]) * progress,
                self.start[1] + (self.end[1] - self.start[1]) * progress)

    @property
    def height(self) -> float:
        return math.sin(self.progress * math.pi) * 3.0


@dataclass
class ThrownGrenade:
    start: tuple[float, float]
    end: tuple[float, float]
    faction: str
    owner: Soldier | None = None
    life: float = 0.82
    duration: float = 0.82
    radius: float = 4.5

    @property
    def progress(self) -> float:
        return max(0.0, min(1.0, 1.0 - self.life / self.duration))

    @property
    def position(self) -> tuple[float, float]:
        progress = self.progress
        return (self.start[0] + (self.end[0] - self.start[0]) * progress,
                self.start[1] + (self.end[1] - self.start[1]) * progress)

    @property
    def height(self) -> float:
        return math.sin(self.progress * math.pi) * 2.1


@dataclass
class ControlPoint:
    label: str
    name: str
    x: float
    y: float
    owner: str = "neutral"
    progress: float = 0.0


@dataclass
class MountedGun:
    kind: str
    x: float
    y: float
    name: str
    faction: str = "us"
    health: float = 500.0
    max_health: float = 500.0
    fire_timer: float = 0.0
    facing: float = 0.0
    ammo: int = 0
