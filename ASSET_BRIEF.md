# Normandy: Breakout — art asset brief

The game currently runs entirely on generated Pygame/vector art, so it is playable without image files. Use this brief to commission or generate a consistent art pack; save the finished images in `data/assets/`. The current renderer does not automatically load these images yet.

## Shared art direction

Use a restrained, hand-painted WWII field-manual look: readable top-down silhouettes, dusty olive drab, khaki, weathered timber, muted French greens, smoke-grey shadows, and small ochre highlights. Keep the camera strictly top-down (not isometric), lighting consistent, and details bold enough to read at game scale. Avoid legible text, logos, flags, gore, or modern equipment. Transparent PNG for units and interface portraits; tileable PNG for ground. Create at 2× target resolution where practical, then downscale cleanly.

## Ready-to-use image-generation briefs

1. **`data/assets/tiles/terrain_atlas.png` — terrain atlas**  
   “Create a seamless top-down 2D terrain tile atlas for a sober WWII Normandy tactics game. Arrange distinct square tiles on a transparent 6-column grid, each tile 96×96: beach sand, shallow Atlantic water, grass field, muddy road, dense bocage hedge, tangled barbed wire, shell crater, low stone wall, bomb-damaged stone building, shallow trench, grey limestone rocks, and concrete anti-tank hedgehog. No labels, no perspective, clean tile edges, muted historically grounded palette.”

2. **`data/assets/units/allied_squads.png` — Allied infantry**  
   “Top-down 2D game sprite sheet, transparent background, four compact US Army infantry squad silhouettes in June 1944 Normandy: rifle squad, assault squad, scout team, and Browning .30-cal machine-gun crew. Olive drab M1 helmets and field uniforms, webbing, rifles, prone/standing-ready poses, readable at 48×48 pixels, each squad centered in its own 96×96 cell, consistent overhead view, no text or insignia.”

3. **`data/assets/units/specialists.png` — specialists**  
   “Transparent top-down 2D sprite sheet with four Normandy 1944 US Army specialist teams in separate 96×96 cells: combat engineers carrying Bangalore torpedo and cutters, two-person mortar team with compact mortar, medic with clearly visible armband and medical satchel, and radio operator with field radio and antenna. Olive drab and khaki clothing, non-graphic, silhouettes readable at 48×48, no text or logos.”

4. **`data/assets/units/armor.png` — armor and guns**  
   “Transparent top-down 2D vehicle sprite sheet for a 1944 Normandy tactics game: M4 Sherman tank, German Panzer IV tank, German Pak 40 anti-tank gun, and coastal artillery piece. Strict 90-degree overhead view, accurate broad silhouettes and muted weathering, each isolated in a 128×128 cell, no crew close-ups, no text, no insignia.”

5. **`data/assets/units/enemy_infantry.png` — enemy teams**  
   “Transparent top-down 2D game sprite sheet of three generic German WWII Normandy enemy silhouettes: rifle patrol, machine-gun/bunker crew, and sniper. Historically grounded 1944 field-grey uniforms and helmets, non-graphic, readable at 48×48, distinct poses, one unit per 96×96 cell, no flags, no text.”

6. **`data/assets/portraits/commanders.png` — radio portraits**  
   “A cohesive set of four square painted WWII radio-portrait headshots for a respectful historical strategy game: weathered US platoon captain in helmet, young US tank commander, young US radio operator, and French Resistance guide in civilian field clothes. Head-and-shoulders, subdued olive/khaki palette, expressive but natural faces, soft field-light, simple dark background, one portrait per 256×256 panel, no text, no emblems.”

7. **`data/assets/units/resistance.png` — allied NPCs**  
   “Transparent top-down 2D sprites for two French Resistance guides in June 1944 civilian field clothes with practical coats, berets, and discreet equipment; and a US airborne pathfinder with period-correct uniform and equipment. Three separate 96×96 cells, overhead camera, friendly readable silhouettes, no weapons firing, no text or insignia.”

8. **`data/assets/props/beach_obstacles.png` — beach props**  
   “Top-down transparent prop sheet for a Normandy beach map: Czech hedgehogs, wooden stakes, tangled wire coils, a landing craft fragment, sandbags, and small shell craters. Separate 96×96 cells, muted weathered materials, clean silhouettes, no people, no text.”

9. **`data/assets/props/town_bocage.png` — map props**  
   “Top-down transparent prop sheet for rural Normandy 1944: stone farmhouse fragments, low bocage gaps, wooden farm gate, roadside signpost with blank sign, rubble pile, church bell tower footprint, bridge barricade, and field telephone pole. Separate 96×96 cells, no readable lettering, no perspective.”

10. **`data/assets/effects/combat_effects.png` — effects**  
    “Transparent 2D effects sprite sheet for a restrained WWII tactics game: small muzzle flash, mortar impact dust plume, smoke grenade cloud, artillery impact dust ring, and subtle selection ring. Each effect centered in a separate 128×128 cell, no gore, no text, muted colors with clear alpha.”

11. **`data/assets/ui/icons.png` — UI icons**  
    “A clean transparent icon atlas for a WWII tactics game, simple cream-and-ochre line icons on transparent background: move boot/arrow, rifle fire, engineer cutters, mortar shell, medic cross, radio signal, objective flag, unit strength, and end-turn clock. Consistent stroke weight, each icon in a 64×64 square, no words, no flags.”

12. **`data/assets/ui/paper_map.png` — campaign screen**  
    “A weathered, subdued 1944 Normandy campaign-map background viewed straight down, abstract coast, fields, hedgerow lines, roads, and small town blocks, broad low-contrast shapes with empty readable space in the center for interface text, no labels, no symbols, no text, 1920×1080.”

## Suggested animation follow-up

If commissioning animated units, request four-direction idle/walk/fire/hit rows with 6–8 frames per action, transparent backgrounds, consistent foot/track pivot, and separate rows per unit type. Keep the gameplay collision footprint centered and unchanged across frames. The current prototype uses single-frame vector drawings and does not require animation assets.
