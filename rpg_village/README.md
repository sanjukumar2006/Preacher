# Hearthmoor - a tiny open-world village RPG (pygame)

Walk around a procedurally generated village and the forest around it, talk to 12 villagers,
pet the dogs, read notice boards, find the glowing shrine, and watch day turn to night.

## Run
    pip install pygame
    python main.py            # options: --seed 42   --skip-title   --regen-assets

## Controls
| Key | Action |
|---|---|
| WASD / Arrows | move |
| SHIFT | run |
| SPACE | jump (also advances dialogue) |
| E / Enter | talk, interact, next line |
| B | music on/off |
| M | world map |
| N | skip one hour of time |
| H | toggle help, F11 fullscreen, ESC pause / close dialogue |

## What is in the folder
- `main.py`            game loop, rendering, UI, day/night, minimap
- `world.py`           terrain noise, village layout, roads, forest, decor, collision, baked ground renderer
- `entities.py`        player, villagers (wander AI), animals, dialogue box
- `data.py`            villager names, palettes, dialogue, named places  (edit this to change the story)
- `generate_assets.py` draws every sprite/tile/sound with code into `assets/`
- `assets/`            all generated art already included: tiles/, objects/, characters/, portraits/, animals/, decor/, ui/, sfx/, music/ (Hearth_and_Willow BGM)

## Tweaking
- Different map: `python main.py --seed 12` (village layout stays, wilderness/lakes/forest change).
- New villager: add an entry to `NPCS` in `data.py`, then run `python generate_assets.py`.
- Change art: edit `generate_assets.py` and re-run it (or replace PNGs in `assets/` directly).

## Character art
Characters use the RPG Maker-style sheets in `assets/rpgmaker/` (Actor1-3.png). Which sprite each villager
uses is set in `data.py` (`HERO_SPRITE`, `SPRITES`: sheet name + character number 0-7, left to right, top to bottom).
Swap in any other 384x256 sheet, edit the mapping, run `python generate_assets.py`. Portraits are cropped
automatically. If `assets/rpgmaker/` is deleted, the game falls back to its built-in procedural characters.
(Those sprite sheets stay under their own RPG Maker license terms.)

Notes: the village houses have no interiors in this version (doors are interactable with a hint).
