"""Shared display, tile, and palette configuration."""

WIDTH = 1280
HEIGHT = 800
MIN_WIDTH = 960
MIN_HEIGHT = 600
TILE = 32
TOP_H = 54
HUD_H = 162
FPS = 60

INK = (17, 24, 25)
PANEL = (27, 37, 37)
PANEL_LIGHT = (43, 55, 51)
PAPER = (232, 224, 199)
MUTED = (155, 162, 147)
GOLD = (224, 178, 91)
GREEN = (111, 153, 94)
RED = (191, 83, 67)
BLUE = (103, 163, 183)
WHITE = (247, 241, 220)
BLACK = (12, 15, 15)

TERRAIN = {
    "water": (59, 104, 119),
    "sand": (191, 168, 119),
    "field": (91, 119, 72),
    "road": (132, 119, 95),
    "hedge": (47, 71, 42),
    "wire": (82, 77, 62),
    "crater": (68, 75, 58),
    "wall": (130, 123, 102),
    "building": (105, 99, 83),
    "trench": (61, 71, 53),
    "rock": (111, 108, 93),
    "obstacle": (101, 94, 77),
    "sandbag": (119, 105, 76),
    "rubble": (90, 83, 68),
}
BLOCKED = {"water", "hedge", "wall", "building", "rock", "obstacle", "sandbag"}
