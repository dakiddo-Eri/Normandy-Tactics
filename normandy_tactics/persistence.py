"""Persistent campaign progress and rotating local gameplay logs."""

from __future__ import annotations

import json
import logging
import math
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


SAVE_VERSION = 1


def user_data_directory() -> Path:
    """Return the macOS per-user save directory, with an optional override."""
    override = os.environ.get("NORMANDY_FRONTLINE_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Application Support" / "NormandyFrontline"


class SaveStore:
    """Load/save campaign state and write concise rotating event logs."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or user_data_directory()
        self.save_path = self.directory / "savegame.json"
        self.log_path = self.directory / "game.log"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(f"normandy_frontline.{self.directory}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        for existing_handler in self.logger.handlers[:]:
            self.logger.removeHandler(existing_handler)
            existing_handler.close()
        handler = RotatingFileHandler(self.log_path, maxBytes=1_000_000, backupCount=3,
                                      encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)

    def load(self, mission_count: int) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "version": SAVE_VERSION,
            "completed_missions": [],
            "dev_unlock_all": False,
            "veteran_bonus": 0.0,
            "stats": {"attempts": 0, "victories": 0, "defeats": 0, "kills": 0},
            "settings": {"difficulty": "standard", "combat_effects": True},
        }
        try:
            raw = json.loads(self.save_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("save root must be an object")
            completed = raw.get("completed_missions", [])
            if not isinstance(completed, list):
                completed = []
            stats = raw.get("stats", {})
            if not isinstance(stats, dict):
                stats = {}
            defaults["completed_missions"] = sorted({
                index for index in completed
                if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < mission_count
            })
            defaults["dev_unlock_all"] = raw.get("dev_unlock_all", False) is True
            defaults["veteran_bonus"] = max(0.0, min(20.0, float(raw.get("veteran_bonus", 0.0))))
            defaults["stats"] = {
                key: max(0, int(stats.get(key, 0)))
                for key in ("attempts", "victories", "defeats", "kills")
            }
            settings = raw.get("settings", {})
            if isinstance(settings, dict):
                difficulty = settings.get("difficulty", "standard")
                defaults["settings"] = {
                    "difficulty": difficulty if difficulty in {"easy", "standard", "hard"} else "standard",
                    "combat_effects": bool(settings.get("combat_effects", True)),
                }
            self.logger.info("Loaded campaign save (%s completed missions)",
                             len(defaults["completed_missions"]))
        except FileNotFoundError:
            self.logger.info("No campaign save found; starting a new campaign")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            self.logger.exception("Could not load campaign save: %s", error)
        return defaults

    def save(self, data: dict[str, Any]) -> None:
        payload = {"version": SAVE_VERSION, **data}
        temporary = self.save_path.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(self.save_path)
        except OSError:
            self.logger.exception("Could not save campaign progress")

    def log_event(self, message: str, *args: object) -> None:
        self.logger.info(message, *args)

    def load_map_data(
        self, mission_index: int, width: int, height: int,
    ) -> tuple[list[list[str]] | None, list[list[float]] | None]:
        path = self.directory / "maps" / f"mission_{mission_index + 1:02}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("tiles") if isinstance(raw, dict) else None
            if (isinstance(rows, list) and len(rows) == height
                    and all(isinstance(row, list) and len(row) == width
                            and all(isinstance(tile, str) for tile in row) for row in rows)):
                orientations = raw.get("orientations")
                valid_orientations = (
                    isinstance(orientations, list) and len(orientations) == height
                    and all(
                        isinstance(row, list) and len(row) == width
                        and all(isinstance(angle, (int, float)) and not isinstance(angle, bool)
                                and math.isfinite(angle) for angle in row)
                        for row in orientations
                    )
                )
                return rows, orientations if valid_orientations else None
        except FileNotFoundError:
            return None, None
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            self.logger.exception("Could not load custom map %d: %s", mission_index, error)
        return None, None

    def load_map(self, mission_index: int, width: int, height: int) -> list[list[str]] | None:
        """Load only map tiles, retaining compatibility with older callers."""
        tiles, _ = self.load_map_data(mission_index, width, height)
        return tiles

    def save_map(self, mission_index: int, mission_title: str, tiles: list[list[str]],
                 orientations: list[list[float]] | None = None) -> None:
        path = self.directory / "maps" / f"mission_{mission_index + 1:02}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        try:
            payload = {"title": mission_title, "tiles": tiles}
            if orientations is not None:
                payload["orientations"] = orientations
            temporary.write_text(json.dumps(payload,
                                            separators=(",", ":")) + "\n", encoding="utf-8")
            temporary.replace(path)
            self.logger.info("Saved custom map: %s", mission_title)
        except OSError:
            self.logger.exception("Could not save custom map: %s", mission_title)
