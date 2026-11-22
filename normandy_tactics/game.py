"""Input handling, campaign flow, and main loop."""

from __future__ import annotations

import math

import pygame

from .battle import Battle
from .campaigns import CAMPAIGNS
from .persistence import SaveStore
from .renderer import Renderer
from .settings import FPS, MIN_HEIGHT, MIN_WIDTH
from .world import World


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("NORMANDY: FRONTLINE")
        self.renderer = Renderer()
        self.screen = self.renderer.screen
        self.clock = pygame.time.Clock()
        self.save_store = SaveStore()
        self.save_data = self.save_store.load(len(CAMPAIGNS))
        self.state = "menu"
        self.battle: Battle | None = None
        self.active_mission = 0
        self.completed_missions: set[int] = set(self.save_data["completed_missions"])
        self.dev_unlock_all = self.save_data["dev_unlock_all"]
        self.veteran_bonus = self.save_data["veteran_bonus"]
        self.settings = self.save_data["settings"]
        self.renderer.combat_effects = self.settings["combat_effects"]
        self.aiming = False
        self.paused = False
        self.pause_page = "pause"
        self.drag_origin: tuple[int, int] | None = None
        self.player_squad_buttons: list[pygame.Rect] = []
        self.suppress_mouse_fire = False
        self.editor_mission_index = 0
        self.editor_world: World | None = None
        self.editor_selected_tile = "field"
        self.editor_orientation = 0.0

    def start_mission(self, index: int) -> None:
        if not 0 <= index < len(CAMPAIGNS) or not self.is_mission_unlocked(index):
            return
        self.active_mission = index
        mission = CAMPAIGNS[index]
        overrides, orientations = self.save_store.load_map_data(index, mission.width, mission.height)
        self.battle = Battle(index, self.veteran_bonus, self.settings["difficulty"], overrides,
                     orientations)
        self.save_data["stats"]["attempts"] += 1
        self.save_store.log_event("Mission started: %s (index %d)", self.battle.mission.title, index)
        self._save_progress()
        self.state = "battle"
        self.paused = False
        self.renderer.camera_x = 0.0
        self.renderer.camera_y = 0.0

    def is_mission_unlocked(self, index: int) -> bool:
        return self.dev_unlock_all or index == 0 or index - 1 in self.completed_missions

    def next_mission(self) -> None:
        if self.battle:
            self.completed_missions.add(self.active_mission)
        next_index = self.active_mission + 1
        if next_index >= len(CAMPAIGNS):
            self.state = "campaign_end"
            return
        self.start_mission(next_index)

    def _save_progress(self) -> None:
        self.save_data["completed_missions"] = sorted(self.completed_missions)
        self.save_data["dev_unlock_all"] = self.dev_unlock_all
        self.save_data["veteran_bonus"] = self.veteran_bonus
        self.save_data["settings"] = dict(self.settings)
        self.save_store.save(self.save_data)

    def _enter_map_editor(self, mission_index: int = 0) -> None:
        self.editor_mission_index = mission_index % len(CAMPAIGNS)
        mission = CAMPAIGNS[self.editor_mission_index]
        overrides, orientations = self.save_store.load_map_data(
            self.editor_mission_index, mission.width, mission.height)
        self.editor_world = World(mission, self.editor_mission_index, overrides, orientations)
        self.editor_selected_tile = "field"
        self.editor_orientation = 0.0
        self.renderer.camera_x = 0.0
        self.renderer.camera_y = 0.0
        self.state = "map_editor"

    def _save_editor_map(self) -> None:
        if self.editor_world:
            self.save_store.save_map(self.editor_mission_index,
                                     CAMPAIGNS[self.editor_mission_index].title,
                                     self.editor_world.tiles,
                                     self.editor_world.tile_orientations)
            self.save_store.log_event("Map edited and saved: %s",
                                      CAMPAIGNS[self.editor_mission_index].title)

    def _record_battle_end(self, won: bool) -> None:
        if not self.battle:
            return
        stats = self.save_data["stats"]
        if won:
            first_clear = self.active_mission not in self.completed_missions
            self.completed_missions.add(self.active_mission)
            stats["victories"] += 1
            stats["kills"] += self.battle.kills
            if first_clear:
                self.veteran_bonus = min(20.0, self.veteran_bonus + self.battle.kills * 0.12 + 3.0)
            self.save_store.log_event("Mission completed: %s; kills=%d; first_clear=%s",
                                      self.battle.mission.title, self.battle.kills, first_clear)
        else:
            stats["defeats"] += 1
            self.save_store.log_event("Mission failed: %s; kills=%d",
                                      self.battle.mission.title, self.battle.kills)
        self._save_progress()

    def _select_squad_button(self, pos: tuple[int, int]) -> bool:
        if not self.battle:
            return False
        for index, rect in enumerate(self.player_squad_buttons):
            if rect.collidepoint(pos):
                self.battle.switch_soldier(index)
                return True
        return False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            self.save_store.log_event("Application closed")
            return False
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(MIN_WIDTH, event.w), max(MIN_HEIGHT, event.h)), pygame.RESIZABLE)
            self.renderer.screen = self.screen
            return True
        if event.type == pygame.KEYDOWN:
            if self.state == "menu":
                if event.key == pygame.K_m:
                    self._enter_map_editor()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_mission(0)
                elif pygame.K_1 <= event.key <= pygame.K_8 and self.is_mission_unlocked(event.key - pygame.K_1):
                    self.start_mission(event.key - pygame.K_1)
            elif self.state == "battle" and self.battle:
                if event.key == pygame.K_ESCAPE:
                    if not self.paused:
                        self.paused = True
                        self.pause_page = "pause"
                    elif self.pause_page == "pause":
                        self.paused = False
                    else:
                        self.pause_page = "pause"
                elif self.paused:
                    if event.key == pygame.K_RETURN and self.pause_page == "pause":
                        self.paused = False
                    elif event.key == pygame.K_ESCAPE:
                        self.pause_page = "pause"
                    return True
                elif event.key == pygame.K_e and not self.paused:
                    self.battle.interact_emplacement()
                elif event.key == pygame.K_r:
                    self.battle.reload()
                elif event.key == pygame.K_g:
                    self.battle.select_inventory_slot(4)
                elif event.key == pygame.K_v:
                    aim = self.renderer.mouse_world(pygame.mouse.get_pos())
                    if not self.battle.bayonet_attack(aim):
                        self.battle.radio_message = "BAYONET THRUST REQUIRES A RIFLE"
                        self.battle.radio_timer = 1.5
                elif event.key in (pygame.K_b, pygame.K_n, pygame.K_h):
                    aim = self.renderer.mouse_world(pygame.mouse.get_pos())
                    player = self.battle.player
                    matching_role = ((event.key in (pygame.K_b, pygame.K_n) and player.role == "engineer")
                                     or (event.key == pygame.K_h and player.role == "medic"))
                    build_type = "wire" if event.key == pygame.K_n else "sandbag"
                    used = self.battle.use_role_ability(player, aim, build_type) if matching_role else False
                    if not used:
                        self.battle.radio_message = (
                            "SELECT AN ENGINEER: B SANDBAGS / N BARBED WIRE" if event.key in (pygame.K_b, pygame.K_n)
                            else "SELECT A MEDIC TO HEAL NEARBY ALLIES WITH H"
                        )
                        self.battle.radio_timer = 1.8
                elif pygame.K_1 <= event.key <= pygame.K_4:
                    self.battle.select_inventory_slot(event.key - pygame.K_0)
                elif pygame.K_F1 <= event.key <= pygame.K_F8:
                    self.battle.switch_soldier(event.key - pygame.K_F1)
                elif pygame.K_5 <= event.key <= pygame.K_8:
                    self.battle.switch_soldier(event.key - pygame.K_1)
                elif event.key == pygame.K_TAB:
                    self.battle.switch_soldier((self.battle.selected_index + 1) % len(self.battle.player_squad))
            elif self.state == "map_editor":
                if event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                    self.editor_world = None
                elif event.key == pygame.K_s:
                    self._save_editor_map()
                elif event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                    direction = -1 if event.key == pygame.K_LEFTBRACKET else 1
                    self._enter_map_editor(self.editor_mission_index + direction)
                elif event.key == pygame.K_q:
                    self.editor_selected_tile = self._cycle_editor_tile(-1)
                elif event.key == pygame.K_e:
                    self.editor_selected_tile = self._cycle_editor_tile(1)
                elif event.key == pygame.K_r:
                    self.editor_orientation = (self.editor_orientation + math.pi / 4) % math.tau
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    palette = Renderer.EDITOR_PALETTE
                    self.editor_selected_tile = palette[event.key - pygame.K_1]
                elif event.key == pygame.K_0:
                    self.editor_selected_tile = Renderer.EDITOR_PALETTE[9]
            elif self.state == "debrief":
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.next_mission()
            elif self.state in {"defeat", "campaign_end"}:
                if event.key == pygame.K_r:
                    self.start_mission(self.active_mission if self.state == "defeat" else 0)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.state == "campaign_end":
                    self.state = "menu"
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.state == "map_editor" and self.editor_world:
                if event.button in (1, 3) and event.pos[1] >= 54 and event.pos[1] < self.screen.get_height() - 70:
                    world_x, world_y = self.renderer.mouse_world(event.pos)
                    tile_x, tile_y = int(world_x), int(world_y)
                    if 0 <= tile_x < self.editor_world.width and 0 <= tile_y < self.editor_world.height:
                        if event.button == 1:
                            self.editor_world.tiles[tile_y][tile_x] = self.editor_selected_tile
                            self.editor_world.tile_health[tile_y][tile_x] = self.editor_world._tile_max_health(
                                self.editor_selected_tile)
                            inferred = self.editor_world.connected_defense_orientation(tile_x, tile_y)
                            self.editor_world.tile_orientations[tile_y][tile_x] = (
                                inferred if self.editor_orientation == 0.0 and inferred is not None
                                else self.editor_orientation
                            )
                        else:
                            self.editor_selected_tile = self.editor_world.tile_at(world_x, world_y)
                            self.editor_orientation = self.editor_world.tile_orientations[tile_y][tile_x]
                return True
            if self.state == "menu":
                if event.button == 1 and self.renderer.map_editor_rect.collidepoint(event.pos):
                    self._enter_map_editor()
                elif event.button == 1 and self.renderer.dev_trigger_rect.collidepoint(event.pos):
                    self.dev_unlock_all = True
                    self._save_progress()
                elif event.button == 1:
                    for index, rect in enumerate(self.renderer.menu_rects):
                        if rect.collidepoint(event.pos) and self.is_mission_unlocked(index):
                            self.start_mission(index)
                            break
            elif self.state == "battle" and self.battle:
                if self.paused:
                    action = next((name for name, rect in self.renderer.pause_action_rects
                                   if rect.collidepoint(event.pos)), None)
                    if action == "resume":
                        self.paused = False
                    elif action == "menu":
                        self._save_progress()
                        self.paused = False
                        self.state = "menu"
                        self.battle = None
                    elif action == "options":
                        self.pause_page = "options"
                    elif action == "controls":
                        self.pause_page = "controls"
                    elif action == "back":
                        self.pause_page = "pause"
                    elif action == "difficulty":
                        values = ("easy", "standard", "hard")
                        current = values.index(self.settings["difficulty"])
                        self.settings["difficulty"] = values[(current + 1) % len(values)]
                        if self.battle:
                            self.battle.player_damage_multiplier = {
                                "easy": 1.18, "standard": 1.12, "hard": 1.05,
                            }[self.settings["difficulty"]]
                            self.battle.incoming_damage_multiplier = {
                                "easy": 0.90, "standard": 1.0, "hard": 1.08,
                            }[self.settings["difficulty"]]
                        self._save_progress()
                    elif action == "effects":
                        self.settings["combat_effects"] = not self.settings["combat_effects"]
                        self.renderer.combat_effects = self.settings["combat_effects"]
                        self._save_progress()
                    return True
                if event.button == 2:
                    self.battle.select_inventory_slot(4)
                    self.battle.throw_grenade(self.renderer.mouse_world(event.pos))
                elif event.button == 1:
                    if self._select_squad_button(event.pos):
                        self.suppress_mouse_fire = True
                        return True
                    for slot, rect in enumerate(self.renderer.inventory_rects, start=1):
                        if rect.collidepoint(event.pos):
                            self.battle.select_inventory_slot(slot)
                            self.suppress_mouse_fire = True
                            return True
                    aim = self.renderer.mouse_world(event.pos)
                    if self.battle.player.inventory_slot == 3:
                        self.battle.melee_attack(aim)
                    elif self.battle.player.inventory_slot == 4:
                        self.battle.throw_grenade(aim)
            elif self.state == "debrief" and self.renderer.continue_rect.collidepoint(event.pos):
                self.next_mission()
            elif self.state in {"defeat", "campaign_end"}:
                if self.state == "defeat":
                    self.start_mission(self.active_mission)
                else:
                    self.state = "menu"
            return True
        return True

    def update(self, dt: float) -> None:
        if self.state == "map_editor":
            keys = pygame.key.get_pressed()
            speed = 450.0 * dt
            self.renderer.camera_x = max(0.0, min(self.renderer.camera_x +
                                       (float(keys[pygame.K_RIGHT]) - float(keys[pygame.K_LEFT])) * speed,
                                       (self.editor_world.width * 32 - self.screen.get_width()) if self.editor_world else 0))
            self.renderer.camera_y = max(0.0, min(self.renderer.camera_y +
                                       (float(keys[pygame.K_DOWN]) - float(keys[pygame.K_UP])) * speed,
                                       (self.editor_world.height * 32 - self.screen.get_height() + 220)
                                       if self.editor_world else 0))
            return
        if self.state != "battle" or not self.battle or self.paused:
            return
        mouse = pygame.mouse.get_pos()
        mouse_buttons = pygame.mouse.get_pressed(3)
        if self.suppress_mouse_fire:
            mouse_buttons = (False, *mouse_buttons[1:])
            self.suppress_mouse_fire = False
        self.aiming = mouse_buttons[2]
        aim = self.renderer.mouse_world(mouse)
        self.battle.update(dt, pygame.key.get_pressed(), mouse_buttons, aim, self.aiming)
        if self.battle.complete:
            self._record_battle_end(won=True)
            self.state = "debrief"
        elif self.battle.defeat:
            self._record_battle_end(won=False)
            self.state = "defeat"

    def draw(self, dt: float) -> None:
        if self.state == "menu":
            self.renderer.draw_title(self.completed_missions, self.dev_unlock_all,
                                     self.save_data["stats"])
        elif self.state == "battle" and self.battle:
            self.renderer.draw_battle(self.battle, dt, pygame.mouse.get_pos(), self.aiming)
            self.player_squad_buttons = self.renderer.squad_rects
            if self.paused:
                self._draw_pause()
        elif self.state == "debrief" and self.battle:
            self.renderer.draw_debrief(self.battle)
        elif self.state == "defeat" and self.battle:
            self.renderer.draw_defeat(self.battle)
        elif self.state == "campaign_end":
            self.screen.fill((17, 24, 25))
            self.renderer._text("THE ROAD TO FRANCE IS OPEN", (self.screen.get_width() // 2, self.screen.get_height() // 2 - 30),
                                44, (224, 178, 91), "center")
            self.renderer._text("Press Enter for the campaign board", (self.screen.get_width() // 2,
                                self.screen.get_height() // 2 + 28), 21, (232, 224, 199), "center")
        elif self.state == "map_editor" and self.editor_world:
            self.renderer.draw_map_editor(self.editor_world, CAMPAIGNS[self.editor_mission_index],
                                           self.editor_selected_tile, self.editor_mission_index,
                                           self.editor_orientation)
        pygame.display.flip()

    def _draw_pause(self) -> None:
        self.renderer.draw_pause_menu(self.pause_page, self.settings)

    def _cycle_editor_tile(self, direction: int) -> str:
        palette = Renderer.EDITOR_PALETTE
        index = palette.index(self.editor_selected_tile) if self.editor_selected_tile in palette else 0
        return palette[(index + direction) % len(palette)]

    def run(self) -> None:
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                running = self.handle_event(event) and running
            self.update(dt)
            self.draw(dt)
        pygame.quit()
