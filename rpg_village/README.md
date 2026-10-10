# Hearthmoor - a tiny open-world village RPG (pygame)

Walk around a procedurally generated village and the forest around it, talk to 12 villagers,
pet the dogs, read notice boards, find the glowing shrine, and watch day turn to night.

## Run
    pip install pygame
    python main.py            # options: --seed 42   --skip-title   --regen-assets   --boss-test

## Title screen, menus and tutorial
- The title screen has **New Game / Controls / Music / Quit** (plus **Continue** once a game is running). Use W/S or the arrow keys + ENTER, or the mouse.
- **New Game** asks *"Would you like a tutorial?"* (Y / N). The tutorial teaches movement, running, jumping, talking, the map, handy keys and the dungeon controls. ENTER continues the read-only steps, **TAB** skips it.
- **ESC** opens the pause menu: Resume, Controls, Music, Replay Tutorial, Main Menu, Quit Game (it also works inside the dungeon now).

## The Hollow Gate
The dungeon entrance at the end of the south road is now a sunken stone stairwell with a flagstone forecourt, rune seal, braziers, mist, bones and a warning sign (art: `gate.py`, layout: `World.build_gate`). It is marked on the minimap and on the big map (M) as **The Hollow Below**.

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
| I | open / close the inventory |
| 1 / 2 | drink a Health / Mana potion (village and dungeon) |
| **Dungeon only** | |
| Left mouse (hold) | attack with the equipped weapon, aimed at the cursor |
| Right mouse / mouse wheel | swap sword <-> magic |
| SPACE | dodge roll (invincible while rolling) |

## What is in the folder
- `main.py`            game loop, rendering, UI, day/night, minimap, menu flow
- `menus.py`           title screen, main/pause menus, controls page, interactive tutorial
- `gate.py`            dungeon gate art + animated braziers / glow / mist
- `world.py`           terrain noise, village layout, roads, forest, decor, collision, baked ground renderer
- `entities.py`        player, villagers (wander AI), animals, dialogue box
- `combat.py`          battle system: weapons, dodge roll, monster AI, projectiles, effects, combat HUD
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

## Dungeon update
- The far southern road now leads to **The Hollow Below**, a dark underground dungeon.
- The dungeon is now **5 hand-crafted floors**, with connected rooms, corridors, pillars, stone walls, staircases and themed hazards.
- Floor 1 is the catacombs; deeper floors become flooded, volcanic, frozen and finally an ancient sanctum.
- Press **E** at the staircase to descend or climb. On Floor 1, the upper staircase returns to Hearthmoor.
- The supplied RPG Maker dungeon tiles are used for the stonework, stairs, water and lava, and the supplied monster sheets are used as decorative idle monsters.
- The dungeon is intentionally very dark. Torches and the player's local light create the main visibility.
- Entering the dungeon switches background music to `assets/music/dark.mp3`; returning to the village restores `hearth_and_willow.mp3`.

## Battle update
Every monster in the dungeon is now hostile. All the code is in `combat.py` (tuning numbers are at the top of the file).

**You**
- **Sword** - short range arc swing, hits everything in front of the cursor, knocks monsters back. You move slower while swinging.
- **Magic** - fires a glowing bolt toward the cursor. Safe range, lower damage.
- **Dodge roll** (SPACE) - rolls in the direction you are moving (or away from the cursor if standing still). You cannot be hurt while rolling and can roll through monsters. Short cooldown, shown in the HUD.
- Health is **infinite** for now (`INFINITE_HP = True` in `combat.py`). Hits still knock you back, flash you red and count in "Hits taken" so you can practise dodging. Set it to `False` to make damage real.

**Monsters**
- **Melee** (skeletons, wraiths, slimes, gargoyles, ogres, brutes, drakes, wyrms): chase you around walls, then wind up - a red danger zone shows where the hit will land - then swing. Step out of the zone or roll.
- **Mages** (dark / fire / ice mages, witches, imps): keep their distance, charge a spell with a visible aim line, then fire slow bolts (some fire a 3-bolt fan). Sidestep or roll through them.
- Monsters flinch when hit (heavy ones - ogres, brutes, dragons - do not), wake their neighbours, and fade out when slain.
- Each floor has its own mix and gets a bit tougher (more monsters, more HP and damage). Monsters respawn when you re-enter a floor.

## Final boss update - GRIMHORN, Warden of the Hollow
Clear every monster on **floor 5**: the purple altar becomes a glowing **gate**. Stand next to it and press **E** to enter
**Grimhorn's throne room**. He sits on his throne and speaks; when the speech ends he stands and the fight begins.
The boss fight uses **real damage** (even while `INFINITE_HP` is on); if you are knocked out, you restart at the hall entrance
and Grimhorn returns to his throne at full health. When he falls, the east wall crumbles into a glowing path that ends in a
**portal** - walk into it to be teleported back outside to Hearthmoor.

Code is in `boss.py` (tuning numbers at the top). Sprite: `assets/boss/shaman.png`, sliced from `shaman_source.png` by
`tools/make_shaman_sheet.py` (rows: down, left, up, right; 3 walk frames each).

Quick test: `python main.py --boss-test` (jumps straight to the throne room).

| Phase | Health | New behaviour |
|---|---|---|
| 1 | 100-66% | spear **thrust** (long red lane), ground **slam** (red circle), 5-bolt **fan** |
| 2 | 66-33% | faster; **horn charge** (if he hits a wall he is stunned and takes x1.5 damage); summons 2 skeletons |
| 3 | 33-0%  | enraged: fastest, 7-bolt fans fired twice, slams throw a ring of 8 bolts; summons a wraith, dark mage and witch |

He is immune while rising, roaring (phase changes) and dying. Beating him shows a victory screen (press **E**), plays the village
music and unseals the stairs. He does not return once defeated. `INFINITE_HP` in `combat.py` still applies - set it to `False`
for a real fight.

## Mana, inventory and the goddess statue
- **Mana pool of 100 MP** (blue bar under HP, shown in the village and the dungeon). The magic weapon is now a **fireball**:
  every cast costs **5 MP**; with less than 5 MP it fizzles ("Not enough mana!"). **Every enemy you defeat restores mana**
  (6 MP, 10 MP for big monsters, 25 MP for Grimhorn). Tuning: `MAX_MP`, `FIREBALL_COST`, `MANA_ON_KILL*` at the top of `combat.py`.
- **Inventory (press I)**: 12 slots, stacks of 20. You start with 2 Health Potions (+40 HP) and 2 Mana Potions (+40 MP).
  Select with arrows / WASD / mouse, then E / Enter or the USE button. **1** and **2** quick-drink from anywhere.
  Monsters drop potions straight into your pack (12% each per kill, `DROPS` in `combat.py`); Grimhorn drops 3 of each.
  New items: add an entry to `ITEMS` in `inventory.py` (+ an icon in `draw_icon`).
- **Goddess statue**: a glowing statue stands on its own little flagstone plaza just west of the dungeon gate courtyard
  (light-blue mark on the minimap and map). Stand in front of it and press **E** to fully restore HP and MP - as often as you like.
  Art: `assets/objects/goddess.png` (regenerate with `python tools/make_goddess.py`), placed in `World.build_gate`.

## Clear every floor + the dungeon map
- **The stairs down are sealed until every monster on the floor is dead.** Sealed stairs show a red rune, the prompt reads
  "Sealed - N foes left", and the top-right counter shows the foes remaining. Cleared floors stay cleared (saved).
- The **purple gate** on floor 5 only opens once *all five* floors have been cleared; otherwise it tells you which floors still have monsters.
- **Press M in the dungeon** to open the dungeon map. It fills in as your lantern reveals rooms (walls block the view) and is saved with your game.
  It marks the stairs (red = sealed, green = open), the altar, your position and the foes left. **A / D or the arrow keys** switch between explored
  floors; tabs on the left show which floors are cleared (green dot) and where you are. M or Esc closes it; the game is paused while it is open.
  Code: `Dungeon.reveal` / `explored_to_save` in `dungeon.py`, `Game.draw_dungeon_map` in `main.py`, `SEE_RADIUS` to change how far you see.

## Main quest - The Warden of the Hollow
- Talk to **Elder Maren** in the village plaza: after her usual greeting she asks you to descend into the Hollow Below and defeat **Grimhorn**.
  The quest tracker appears at the top-left (village and dungeon) and in a box on the inventory screen. Talking to her again repeats the hint.
- When Grimhorn falls the tracker says "return to Elder Maren". Report back for the reward: **+20 max HP, +20 max MP, 3 Health + 3 Mana Potions**
  (and a full heal). Text and rewards are edited in `quest.py`.
- If you beat Grimhorn before ever accepting the quest, Elder Maren still thanks you and pays the reward.
