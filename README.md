# Normandy: Frontline

A small, local, real-time WWII squad-action prototype made with Pygame. It uses genre-level inspiration from squad shooters: the player directly controls one soldier while nearby AI squadmates and friendly/enemy soldiers fight around them. This is an original top-down prototype, not a recreation of another game's proprietary maps, art, names, or code.
## Controls

- **WASD** move; **Shift** sprint; **Ctrl** crouch.
- **Mouse** aim; hold **left mouse** to fire; hold **right mouse** to aim more carefully.
- **1** primary; **2** pistol; **3** machete; **4** grenade, then click to throw along the preview arc. Every soldier gets one grenade per spawn; the whole squad resupplies when it respawns. Press **V** with a rifle for a separate bayonet thrust. **R** reload.
- Press **E** beside a bunker gun, field cannon, or machine-gun nest to operate it; press **E** again to leave.
- The **Map Editor** is available from the start screen (**M**). Select missions with **[ / ]**, choose terrain with **1–0** or **Q/E**, rotate the selected asset with **R**, paint with left click, sample tile and rotation with right click, pan with arrows, and save with **S**. Connected wire and trench sections join at tile edges automatically.
- During a battle, **Esc** opens Resume, Start Menu, Options, and Controls. Options let you cycle difficulty and toggle combat effects.
- **F1–F8**, **Tab**, or the squad buttons switch to a living squadmate. Engineers use **B** for sandbags or **N** for barbed wire; **H** heals as a medic.
- Aim in the direction you want the engineer to face before building. Emplacements are placed ahead of the engineer and oriented perpendicular to that facing.
- **Esc** pause. Missions rotate between sector capture, timed holdouts, and demolition targets. Captured sectors remain yours until enemy troops physically contest and retake them.
- Campaign maps unlock in order: win the current operation to open the next one.

Campaign progress, veteran bonus, and aggregate battle stats are saved automatically after each deployment and result. On macOS, save data and rotating event logs are stored in `~/Library/Application Support/NormandyFrontline/` (`savegame.json` and `game.log`). AI grenades are intentionally uncommon: only assault troops and engineers may decide to throw one, once per spawn.

Weapon control matters: moving increases shot spread, aiming reduces it, repeated shots add recoil, hits are confirmed at the reticle, and magazines have limited ammunition. AI grenade use is rare, each troop has one per spawn, and only one AI grenade can be in flight at a time with an eight-second battle-wide AI delay; the player also has a shared three-second throw cooldown. Random events can trigger aircraft strafing runs, heavy artillery barrages, or super-reinforcement waves. The howitzer mount has a limited shell supply; aim within range and fire to call a marked impact. Operable MG nests, bunker guns, field cannons, and howitzers provide fixed defenses. Demolition targets are marked on the map with a health bar and an edge-of-screen indicator. Difficulty and combat-effect settings are saved automatically.

## Project layout

- `main.py` — small application entry point.
- `normandy_tactics/game.py` — event loop, controls, campaign flow.
- `normandy_tactics/battle.py` — player movement, gunplay, AI, reinforcements, objectives.
- `normandy_tactics/actors.py` — soldier, weapon, tracer, and explosion data.
- `normandy_tactics/world.py` — procedural terrain and collision/line-of-sight.
- `normandy_tactics/campaigns.py` — eight selectable mission briefs and tuning.
- `normandy_tactics/renderer.py` — scrolling camera, units, terrain, and HUD.
- `normandy_tactics/settings.py` — shared display and palette settings.

# Notes

This game is currently a work in progress, follow the **Eri License** for notes on 
distributing and copying this game. This game is just for me to practice my skills
and put this on my portfolio because yea. There will **DEFINETLY** be bugs in this
and do **NOT** expect this to be updated like I'm a sweat. Unless people actually 
like this or smthing.
