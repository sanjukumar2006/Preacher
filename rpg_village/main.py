
"""Hearthmoor - a tiny open-world village RPG made with pygame.

Title screen: New Game / Controls / Music / Quit, then an optional tutorial.

Controls
  WASD / Arrow keys  move          SHIFT  run
  SPACE              jump (also advances dialogue)
  E / ENTER          talk / interact / continue dialogue
  M  world map       N  skip an hour of time      H  help
  F11  fullscreen    ESC  pause menu (resume / controls / music / tutorial / main menu / quit)

In the dungeon (battle):
  LEFT MOUSE (hold)    attack with the equipped weapon, aimed at the cursor
  RIGHT MOUSE / SCROLL swap between sword and magic
  SPACE                dodge roll (invincible while rolling)

Final boss: clear floor 5, step up to the purple gate and press E - it leads to Grimhorn's throne room.
Beat him and a path opens that teleports you back to the village. Test quickly with:  python main.py --boss-test
"""
import argparse
import math
import os
import random
import sys

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ASSETS = os.path.join(HERE, "assets")

if not os.path.isdir(os.path.join(ASSETS, "tiles")):
    print("Generating assets (first run)...")
    import generate_assets
    generate_assets.main()

from data import NPCS, PLACES
from entities import NPC, Animal, Dialogue, Player
import world as W
from world import FOOT, HOUSES, T, Baked, World
from dungeon import Dungeon
from combat import Combat
import quest as Q
import save as SAVE
from inventory import QUICK_ITEMS, draw_inventory, inv_click, inv_key
import gate
from menus import (MenuList, Tutorial, draw_ask, draw_controls, draw_pause, draw_slots, draw_title_screen, make_motes)

VIEW_W, VIEW_H = 640, 360

TINTS = [
    (0, (10, 14, 50, 150)), (5, (16, 20, 60, 140)), (6.2, (255, 140, 80, 70)), (7.6, (255, 200, 140, 24)),
    (9, (255, 240, 200, 0)), (16, (255, 240, 200, 0)), (17.6, (255, 180, 100, 30)), (19, (230, 90, 90, 70)),
    (20.3, (20, 24, 70, 125)), (22, (10, 14, 50, 150)), (24, (10, 14, 50, 150)),
]


def tint_at(h):
    for (h0, c0), (h1, c1) in zip(TINTS, TINTS[1:]):
        if h0 <= h <= h1:
            k = (h - h0) / (h1 - h0)
            return tuple(int(c0[i] + (c1[i] - c0[i]) * k) for i in range(4))
    return TINTS[0][1]


def load_assets():
    a = {}
    for sub in sorted(os.listdir(ASSETS)):
        d = os.path.join(ASSETS, sub)
        if not os.path.isdir(d) or sub in ("sfx", "rpgmaker"):
            continue
        a[sub] = {}
        for f in os.listdir(d):
            if f.endswith(".png"):
                a[sub][f[:-4]] = pygame.image.load(os.path.join(d, f)).convert_alpha()
    return a


def radial(size, color, power=1.8):
    s = pygame.Surface((size, size))
    c = size / 2
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - c + 0.5, y - c + 0.5) / c
            k = max(0.0, 1 - d) ** power
            s.set_at((x, y), tuple(int(v * k) for v in color))
    return s


class Game:
    def __init__(self, seed=7, skip_title=False, begin_new=False):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        try:
            flags = pygame.SCALED | pygame.RESIZABLE
            self.screen = pygame.display.set_mode((VIEW_W, VIEW_H), flags)
        except pygame.error:
            self.screen = pygame.display.set_mode((VIEW_W * 2, VIEW_H * 2))
        pygame.display.set_caption("Hearthmoor - Village RPG")
        self.view = pygame.Surface((VIEW_W, VIEW_H)).convert()
        self.out = self.screen
        self.clock = pygame.time.Clock()
        self.a = load_assets()
        self.sfx = {}
        try:
            for n in ("blip", "talk", "bye", "jump", "land"):
                self.sfx[n] = pygame.mixer.Sound(os.path.join(ASSETS, "sfx", n + ".wav"))
        except Exception:
            pass
        self.sfx["jump"].set_volume(0.7) if "jump" in self.sfx else None
        self.music_on = True
        self.current_music = None
        self.music_volume = 0.45
        self.play_music("hearth_and_willow.mp3", fade_ms=1500)
        self.font = pygame.font.Font(None, 20)
        self.font_s = pygame.font.Font(None, 16)
        self.font_m = pygame.font.Font(None, 24)
        self.font_b = pygame.font.Font(None, 76)

        print("Generating village terrain...")
        self.world = World(seed)
        self.baked = Baked(self.world, self.a)
        gate.paint_ground(self.baked.ground, self.world)      # dungeon gate art is baked into the ground
        self.gatefx = gate.GateFX()
        self.build_props()
        self.dungeon = Dungeon(self.a["dungeon"])
        self.scene = "village"
        self.village_return_pos = None
        self.shadow = pygame.Surface((22, 9), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow, (0, 0, 0, 70), (0, 0, 22, 9))

        # actors
        hx, hy = self.world.nearest_walkable(48, 51)
        self.player = Player(hx * T + 16, hy * T + 28, self.a["characters"]["hero"])
        self.combat = Combat(self.dungeon, self.player)
        self.combat.toast = self.toast
        self.combat.on_victory = lambda: self.play_music("hearth_and_willow.mp3", fade_ms=2500)
        self.combat.on_boss_intro = self.boss_intro
        self.combat.on_boss_start = lambda: self.play_music("dark.mp3", fade_ms=400)
        self.tele_t = 0.0
        self.mouse_hidden = False
        self.npcs = []
        for d in NPCS:
            self.npcs.append(NPC(d, self.a["characters"][d["id"]], self.a["portraits"][d["id"]], self.world))
        self.animals = []
        ch = [self.a["animals"][f"chicken_{i}"] for i in range(3)]
        for (tx, ty, r) in ((50, 50, 4), (53, 51, 4), (45, 53, 4), (30, 66, 5), (33, 69, 5), (56, 58, 4)):
            self.animals.append(Animal("chicken", tx * T, ty * T, ch, 26, r, self.world))
        dg = [self.a["animals"][f"dog_{i}"] for i in range(2)]
        self.animals.append(Animal("dog", 57 * T, 58 * T, dg, 44, 6, self.world))
        self.animals.append(Animal("dog", 66 * T, 47 * T, dg, 44, 6, self.world))

        self.dialogue = Dialogue(self.font, self.a["ui"]["dialog_box"], self.a["ui"]["name_tag"],
                                 self.a["ui"]["next_arrow"])
        self.combat.on_floor_cleared = lambda: self.save_game(auto=True)
        self.cam = [0.0, 0.0]
        self.center_camera(True)
        self.time = 9.0           # hour of the day
        self.state = "play" if skip_title else "title"
        self.started = bool(skip_title)            # a game is in progress (enables "Continue")
        self.restart = False
        self.menu_screen = "tutorial_ask" if begin_new else "main"
        self.controls_back = "main"
        self.motes = make_motes()
        self.tut = Tutorial()
        self.dungeon_hint = False
        self._last_mouse = None
        self.title_cam = list(self.cam)
        self.menu_main = self.menu_ask = self.menu_pause = None
        self.current_slot = 1                               # slot used by quick save (F5)
        self.slot_mode, self.slot_ids, self.slot_info = "load", [], {}
        self.slot_sel, self.slot_confirm, self.slots_back = 0, None, "main"
        self.build_menus()
        self.t = 0.0
        self.show_map = False
        self.map_floor = 1                          # floor shown on the dungeon map (browse with arrows / A, D)
        self.show_inv = False                       # inventory screen (key I)
        self.quest = Q.Quest()
        self.heal_t = 0.0                           # goddess blessing animation timer
        self.death_t = 0.0                          # > 0 while the death scene plays
        self.holy = [radial(100, (int(70 * k), int(135 * k), int(210 * k)), 1.5) for k in (0.55, 0.75, 1.0)]
        self.paused = False
        self.help_t = 14.0
        self.toasts = []
        self.place_name = ""
        self.banner_t = 0.0
        self.banner_text = ""
        self.target = None
        self.glow = radial(112, (255, 190, 90))
        self.glow_mask = pygame.Surface((112, 112), pygame.SRCALPHA)
        for y in range(112):
            for x in range(112):
                d = math.hypot(x - 55.5, y - 55.5) / 56
                self.glow_mask.set_at((x, y), (0, 0, 0, int(255 * max(0, 1 - d) ** 1.4)))
        self.night = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        self.smoke = []
        self.smoke_t = [random.random() * 2 for _ in HOUSES]
        self.smoke_surf = []
        for r in range(2, 8):
            s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (236, 236, 242, 255), (r + 1, r + 1), r)
            self.smoke_surf.append(s)
        self.make_butterflies()
        self.make_minimaps()
        self.update_place(True)

    # ------------------------------------------------------------ setup
    def build_props(self):
        o = self.a["objects"]
        self.props = []
        self.campfires = []
        for p in self.world.props:
            kind = p["kind"]
            fw, fh = FOOT[kind]
            img = o.get(kind) or o[kind + "_0"]
            cx = (p["tx"] + fw / 2.0) * T
            bottom = (p["ty"] + fh) * T
            x = int(cx - img.get_width() / 2)
            y = int(bottom + 4 - img.get_height())
            item = [bottom, img, x, y, img.get_width(), img.get_height()]
            if kind == "campfire":
                item[1] = None
                self.campfires.append(item)
            self.props.append(item)
        self.props.extend(gate.pillar_props())
        self.props.sort(key=lambda p: p[0])

    def make_butterflies(self):
        rnd = random.Random(5)
        flowers = [d for d in self.world.decor if d["kind"].startswith("flower")
                   and abs(d["x"] / T - 48) < 30 and abs(d["y"] / T - 48) < 30]
        self.butterflies = []
        for _ in range(18):
            f = rnd.choice(flowers)
            self.butterflies.append(dict(cx=f["x"], cy=f["y"] - 10, rx=rnd.randint(14, 40), ry=rnd.randint(8, 22),
                                         sp=rnd.uniform(0.5, 1.2), ph=rnd.uniform(0, 6.28), kind=rnd.randrange(3)))

    def make_minimaps(self):
        cols = {W.GRASS: (98, 164, 72), W.DARK: (58, 118, 56), W.SAND: (232, 212, 156), W.WATER: (70, 150, 214),
                W.DEEP: (46, 112, 184), W.PATH: (184, 148, 102), W.COBBLE: (150, 146, 156),
                W.FARM: (116, 80, 50), W.DOCK: (168, 120, 72)}
        m = pygame.Surface((W.W, W.H))
        for y in range(W.H):
            for x in range(W.W):
                m.set_at((x, y), cols[self.world.terrain[y][x]])
        for p in self.world.props:
            k = p["kind"]
            fw, fh = FOOT[k]
            if k.startswith("tree"):
                c = (36, 92, 48) if k != "tree_cherry" else (226, 130, 170)
            elif k.startswith("house"):
                c = (170, 66, 58)
            elif k in ("stall_red", "stall_blue", "tent", "shrine", "well"):
                c = (230, 200, 90)
            else:
                continue
            m.fill(c, (p["tx"], p["ty"], fw, fh if not k.startswith("house") else 4))
        gx, gy = self.world.goddess
        m.fill((150, 225, 255), (gx, gy - 1, 5, 3))               # goddess statue (sanctuary behind the shrine)
        m.fill((74, 66, 96), (46, 86, 6, 5))                     # the Hollow Gate
        m.fill((150, 80, 230), (47, 87, 4, 3))
        self.mini = m
        self.mini_small = m
        self.mini_big = pygame.transform.scale(m, (W.W * 3, W.H * 3))

    # ------------------------------------------------------------ menus
    def music_label(self):
        return "Music: ON" if self.music_on else "Music: OFF"

    def build_menus(self):
        """(Re)build the button lists. The main menu gains 'Continue' once a game is running."""
        main = []
        if self.started:
            main.append(("continue", "Continue"))
        main.append(("new", "New Game"))
        if SAVE.any_exists():
            main.append(("load", "Load Game"))
        main += [("controls", "Controls"), ("music", self.music_label), ("quit", "Quit")]
        sel = self.menu_main.sel if self.menu_main else 0
        self.menu_main = MenuList(main, top=148, width=230)
        self.menu_main.sel = min(sel, len(main) - 1)
        if self.menu_ask is None:
            self.menu_ask = MenuList([("yes", "Yes, show me the basics"), ("no", "No thanks, let's go")],
                                     top=156, width=320)
        if self.menu_pause is None:
            self.menu_pause = MenuList([("resume", "Resume"), ("save", "Save Game"), ("load", "Load Game"),
                                        ("inventory", "Inventory"), ("controls", "Controls"), ("music", self.music_label),
                                        ("tutorial", "Replay Tutorial"), ("title", "Main Menu"),
                                        ("quit", "Quit Game")], top=104, gap=26, width=230)

    def current_menu(self):
        if self.state == "title":
            return {"main": self.menu_main, "tutorial_ask": self.menu_ask}.get(self.menu_screen)
        if self.paused:
            return self.menu_pause if self.menu_screen == "pause" else None
        return None

    def toggle_music(self):
        self.music_on = not self.music_on
        if self.music_on:
            pygame.mixer.music.set_volume(self.music_volume)
            if not self.paused:
                pygame.mixer.music.unpause()
                if not pygame.mixer.music.get_busy() and self.current_music:
                    self.play_music(self.current_music, fade_ms=600)
        else:
            pygame.mixer.music.pause()
        self.toast("Music on" if self.music_on else "Music off", 1.5)

    def open_pause(self):
        self.paused = True
        self.menu_screen = "pause"
        self.menu_pause.sel = 0
        self.show_map = False
        if self.music_on:
            pygame.mixer.music.pause()

    def resume(self):
        self.paused = False
        if self.music_on:
            pygame.mixer.music.unpause()

    def begin_game(self, tutorial):
        """Leave the title screen and start playing (optionally with the tutorial)."""
        self.state = "play"
        self.started = True
        self.time = 9.0
        self.center_camera(True)
        self.banner_text = self.place_name
        self.banner_t = 3.2
        self.toast("Talk to Elder Maren in the village plaza (press E near him)", 8.0)
        self.build_menus()
        if tutorial:
            self.tut.start()
            self.help_t = 0.0
        else:
            self.tut.active = False
            self.help_t = 14.0

    def menu_do(self, key):
        """Run a menu action. Returns False when the game should quit."""
        self.play("blip")
        if key == "continue":
            self.state = "play"
        elif key == "new":
            if self.started:                      # a fresh world: restart the whole game object
                self.restart = True
                return False
            self.menu_screen = "tutorial_ask"
            self.menu_ask.sel = 0
        elif key == "save":
            self.open_slots("save")
        elif key == "load":
            self.open_slots("load")
        elif key == "controls":
            self.controls_back = self.menu_screen
            self.menu_screen = "controls"
        elif key == "music":
            self.toggle_music()
        elif key == "quit":
            return False
        elif key in ("yes", "no"):
            self.begin_game(key == "yes")
        elif key == "resume":
            self.resume()
        elif key == "inventory":
            self.resume()
            self.show_inv = True
        elif key == "tutorial":
            if self.scene != "village":
                self.toast("Return to the village to replay the tutorial.", 3.0)
            else:
                self.resume()
                self.tut.start()
                self.help_t = 0.0
        elif key == "title":
            self.resume()
            self.state = "title"
            self.menu_screen = "main"
            self.build_menus()
            self.menu_main.sel = 0
        return True

    # ------------------------------------------------------------ save slots screen
    def open_slots(self, mode):
        """Show the slot list. mode = 'save' or 'load'."""
        self.slots_back = self.menu_screen
        self.slot_mode = mode
        self.slot_ids = SAVE.slot_ids(include_auto=(mode == "load"))
        self.slot_info = {sid: SAVE.info(sid) for sid in self.slot_ids}
        self.slot_confirm = None
        cur = self.current_slot if self.current_slot in self.slot_ids else self.slot_ids[0]
        self.slot_sel = self.slot_ids.index(cur)
        self.menu_screen = "slots"

    def slot_row_rect(self, i):
        return pygame.Rect(70, 62 + i * 41, 500, 37)

    def slots_close(self):
        self.menu_screen = self.slots_back
        self.slot_confirm = None

    def slots_activate(self):
        sid = self.slot_ids[self.slot_sel]
        info = self.slot_info.get(sid)
        if self.slot_mode == "save":
            if info and self.slot_confirm != ("overwrite", sid):
                self.slot_confirm = ("overwrite", sid)
                self.toast("Press ENTER again to overwrite slot %s" % sid, 2.0)
                return
            if self.scene == "dungeon" and self.dungeon.level == 6 and not self.combat.boss_defeated:
                self.toast("Saves in the throne room return you to floor 5.", 3.0)
            if self.save_game(slot=sid):
                self.slots_close()
                self.resume()
        else:
            if not info:
                self.toast("That slot is empty.", 1.8)
                return
            if self.load_game(sid):
                self.paused = False

    def slots_delete(self):
        sid = self.slot_ids[self.slot_sel]
        if sid == SAVE.AUTO or not self.slot_info.get(sid):
            return
        if self.slot_confirm != ("delete", sid):
            self.slot_confirm = ("delete", sid)
            self.toast("Press DEL again to delete slot %s" % sid, 2.0)
            return
        SAVE.delete(sid)
        self.slot_info[sid] = None
        self.slot_confirm = None
        if self.current_slot == sid:
            self.current_slot = 1
        self.build_menus()
        self.toast("Slot %s deleted" % sid, 1.8)

    def slots_key(self, k):
        n = len(self.slot_ids)
        if k in (pygame.K_UP, pygame.K_w):
            self.slot_sel = (self.slot_sel - 1) % n
            self.slot_confirm = None
            self.play("blip")
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.slot_sel = (self.slot_sel + 1) % n
            self.slot_confirm = None
            self.play("blip")
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e):
            self.slots_activate()
        elif k in (pygame.K_DELETE, pygame.K_x):
            self.slots_delete()
        elif k in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.slots_close()
            self.play("blip")
        elif pygame.K_1 <= k <= pygame.K_9 and (k - pygame.K_0) in self.slot_ids:
            self.slot_sel = self.slot_ids.index(k - pygame.K_0)
            self.slot_confirm = None
        return True

    def slots_mouse(self, pos):
        for i in range(len(self.slot_ids)):
            if self.slot_row_rect(i).collidepoint(pos):
                if self.slot_sel != i:
                    self.slot_confirm = None
                self.slot_sel = i
                self.slots_activate()
                return
        if pygame.Rect(0, VIEW_H - 40, VIEW_W, 40).collidepoint(pos):
            self.slots_close()

    def menu_key(self, k):
        scr = self.menu_screen
        if scr == "slots":
            return self.slots_key(k)
        if scr == "controls":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e,
                     pygame.K_BACKSPACE):
                self.menu_screen = self.controls_back
                self.play("blip")
            return True
        menu = self.current_menu()
        if menu is None:
            return True
        if k in (pygame.K_UP, pygame.K_w):
            menu.move(-1)
            self.play("blip")
        elif k in (pygame.K_DOWN, pygame.K_s):
            menu.move(1)
            self.play("blip")
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e):
            return self.menu_do(menu.key())
        elif k == pygame.K_ESCAPE:
            if scr == "pause":
                self.resume()
            elif scr == "tutorial_ask":
                self.menu_screen = "main"
            elif scr == "main" and self.started:
                self.state = "play"
        elif scr == "tutorial_ask" and k == pygame.K_y:
            return self.menu_do("yes")
        elif scr == "tutorial_ask" and k == pygame.K_n:
            return self.menu_do("no")
        elif scr == "pause" and k == pygame.K_q:
            return False
        return True

    # ----------------------------------------------------------- helpers
    def center_camera(self, snap=False):
        tx = self.player.x - VIEW_W / 2
        ty = self.player.y - 26 - VIEW_H / 2
        tx = max(0, min(W.W * T - VIEW_W, tx))
        ty = max(0, min(W.H * T - VIEW_H, ty))
        if snap:
            self.cam = [tx, ty]
        else:
            self.cam[0] += (tx - self.cam[0]) * 0.14
            self.cam[1] += (ty - self.cam[1]) * 0.14

    def play_music(self, filename, fade_ms=800):
        """Switch background music while respecting the B/music toggle."""
        path = os.path.join(ASSETS, "music", filename)
        if not os.path.isfile(path):
            print("Music not available:", path)
            self.current_music = None
            return False
        try:
            pygame.mixer.music.load(path)
            self.current_music = filename
            pygame.mixer.music.set_volume(self.music_volume if self.music_on else 0.0)
            if self.music_on:
                pygame.mixer.music.play(-1, fade_ms=fade_ms)
            else:
                pygame.mixer.music.pause()
            return True
        except Exception as ex:
            print("Music not available:", ex)
            self.current_music = None
            return False

    def enter_dungeon(self):
        if self.scene == "dungeon":
            return
        # Remember a safe spot outside the gate so returning does not immediately re-trigger it.
        self.village_return_pos = (48 * T + 16, 84 * T + 24)
        self.scene = "dungeon"
        self.combat.dungeon_active = True
        self.show_map = False
        self.dialogue.active = False
        self.dungeon.set_level(1, spawn="entrance")
        sx, sy = self.dungeon.player_spawn()
        self.player.x, self.player.y = sx, sy
        self.player.dir = "up"
        self.player.z = self.player.vz = 0.0
        self.dungeon.cam = [max(0, self.player.x - VIEW_W / 2), max(0, self.player.y - VIEW_H / 2)]
        self.banner_text = "The Hollow Below — Floor 1"
        self.banner_t = 3.2
        self.play_music("dark.mp3", fade_ms=1200)
        if not self.dungeon_hint:
            self.dungeon_hint = True
            self.toast("LEFT CLICK attack   RIGHT CLICK swap weapon   SPACE dodge roll", 6.0)

    def exit_dungeon(self):
        if self.scene != "dungeon":
            return
        self.scene = "village"
        self.combat.dungeon_active = False
        self.dungeon.set_level(1, spawn="entrance")
        if self.village_return_pos:
            # Put the hero just outside the entrance, rather than inside the trigger again.
            self.player.x, self.player.y = self.village_return_pos
        else:
            self.player.x, self.player.y = 48 * T + 16, 88 * T + 24
        self.player.dir = "down"
        self.player.z = self.player.vz = 0.0
        self.center_camera(True)
        self.banner_text = "Hearthmoor Village"
        self.banner_t = 3.2
        self.play_music("hearth_and_willow.mp3", fade_ms=1200)
        self.save_game(auto=True)

    def change_dungeon_level(self, direction):
        if self.scene != "dungeon":
            return
        old = self.dungeon.level
        if direction == "gate":
            self.enter_throne_room()
            return
        if direction == "down" and old < self.dungeon.max_level:
            if not self.combat.cleared:
                self.toast("The stairs are sealed. Slay every monster on this floor first (%d left)."
                           % self.combat.alive_count(), 3.0)
                return
            new = old + 1
            self.dungeon.set_level(new, spawn="down")
            self.player.x, self.player.y = self.dungeon.player_spawn()
            self.player.dir = "up"
            self.player.z = self.player.vz = 0.0
            self.banner_text = f"The Hollow Below — Floor {new}"
            self.banner_t = 2.8
            self.toast(f"Descended to floor {new}/5", 2.2)
        elif direction == "up":
            if old == 1:
                self.exit_dungeon()
                return
            new = old - 1
            self.dungeon.set_level(new, spawn="up")
            self.player.x, self.player.y = self.dungeon.player_spawn()
            self.player.dir = "down"
            self.player.z = self.player.vz = 0.0
            self.banner_text = f"The Hollow Below — Floor {new}"
            self.banner_t = 2.8
            self.toast(f"Returned to floor {new}/5", 2.2)
        self.dungeon.cam = [max(0, self.player.x - VIEW_W / 2), max(0, self.player.y - VIEW_H / 2)]

    def boss_intro(self):
        """Grimhorn speaks from his throne, then stands up and the fight starts."""
        from boss import BOSS_NAME, BOSS_TITLE, load_sprite
        portrait = load_sprite()[2]
        if self.combat.boss_tries == 0:
            lines = [
                "Hmmm... so the stones did not lie. Another little light crawls down into my hall.",
                "For a thousand winters I have kept the Hollow Below. Every hero who passed the Sanctum became bones at my feet.",
                "You cut through my servants. Impressive - for a village rat. Hearthmoor will sing of you... if anyone is left to sing.",
                "Come, then. Let me see if your blade is as sharp as your pride. RISE - AND DIE!",
            ]
        else:
            lines = ["Back already? Good. I was just getting comfortable.", "Again, then. And this time, do try to last."]
        self.dialogue.start(BOSS_NAME, BOSS_TITLE, lines, portrait, on_end=self.combat.start_boss_fight)

    def enter_throne_room(self):
        """The purple gate on floor 5 -> Grimhorn's throne room."""
        if not self.combat.cleared:
            self.toast("The gate is sealed. Slay every monster on this floor first.", 3.0)
            return
        if self.combat.boss_defeated:
            self.toast("The gate is dormant. The Warden is gone.", 3.0)
            return
        missing = [f for f in range(1, 5) if f not in self.combat.cleared_floors]
        if missing:
            self.toast("The gate rejects you. Floor %s still %s monsters. Clear every floor first."
                       % (", ".join(map(str, missing)), "has" if len(missing) == 1 else "have"), 4.0)
            return
        self.dungeon.set_level(6, spawn="gate")
        self.player.x, self.player.y = self.dungeon.player_spawn()
        self.player.dir = "up"
        self.player.z = self.player.vz = 0.0
        self.dungeon.cam = [max(0, self.player.x - VIEW_W / 2), max(0, self.player.y - VIEW_H / 2)]
        self.banner_text = "The Throne of the Warden"
        self.banner_t = 3.2
        self.toast("The gate swallows you. A great hall opens in the dark...", 3.5)

    def debug_boss(self):
        """--boss-test: drop the hero into floor 5 with the floor already cleared and wake the boss."""
        self.state = "play"
        self.enter_dungeon()
        self.dungeon.set_level(5, spawn="down")
        self.combat.cleared = True
        self.combat.cleared_floors.update(range(1, 6))
        self.enter_throne_room()

    def mouse_view(self):
        """Mouse position in the 640x360 game view (also correct when the window is scaled)."""
        mx, my = pygame.mouse.get_pos()
        sw, sh = self.screen.get_size()
        return mx * VIEW_W / sw, my * VIEW_H / sh

    def play(self, name):
        s = self.sfx.get(name)
        if s:
            s.play()

    def toast(self, text, dur=3.5):
        self.toasts.append([text, dur])

    def met_count(self):
        return sum(1 for n in self.npcs if n.talk_count > 0)

    def update_place(self, first=False):
        if self.scene == "dungeon":
            name = f"The Hollow Below — Floor {self.dungeon.level}/5"
            if name != self.place_name:
                self.place_name = name
                self.banner_text = name
                self.banner_t = 3.2
            return
        tx, ty = self.player.x / T, self.player.y / T
        name = None
        for nm, (x0, y0, x1, y1) in PLACES:
            if x0 <= tx <= x1 and y0 <= ty <= y1:
                name = nm
                break
        if name is None:
            d = math.hypot(tx - 48, ty - 48)
            name = "Hearthmoor Village" if d < 24 else "Whisperwood Forest"
        if name != self.place_name:
            self.place_name = name
            self.banner_text = name
            self.banner_t = 3.2

    def find_target(self):
        if self.scene == "dungeon":
            transition = self.dungeon.next_transition(self.player)
            if transition and not self.combat.boss_lock:
                pos = self.dungeon.world.up if transition == "up" else self.dungeon.world.down
                return ("dungeon_transition", (transition, pos))
            w = self.dungeon.world
            if self.dungeon.level == 5 and w.altar:                    # the purple gate
                ax, ay = w.altar
                if math.hypot(self.player.x - (ax * T + 16), (self.player.y - 4) - (ay * T + 16)) < 54:
                    return ("dungeon_transition", ("gate", w.altar))
            return None
        px, py = self.player.x, self.player.y
        best, bd = None, 1e9
        for n in self.npcs:
            d = math.hypot(n.x - px, (n.y - py) * 1.0)
            if d < 44 and d < bd:
                best, bd = ("npc", n), d
        if best:
            return best
        for a in self.animals:
            d = math.hypot(a.x - px, a.y - py)
            if d < 30 and d < bd:
                best, bd = ("animal", a), d
        if best:
            return best
        for it in self.world.interact:
            r = it["rect"].inflate(10, 10)
            if r.collidepoint(px, py - 4):
                d = math.hypot(r.centerx - px, r.centery - py)
                if d < bd:
                    best, bd = ("obj", it), d
        return best

    def interact(self):
        tgt = self.target
        if not tgt:
            return
        kind, obj = tgt
        self.play("talk")
        self.tut.notify(self, "interact")
        if kind == "dungeon_transition":
            self.change_dungeon_level(obj[0])
            return
        if kind == "obj" and obj.get("id") == "dungeon":
            self.enter_dungeon()
            return
        if kind == "obj" and obj.get("id") == "goddess":
            self.pray()
            return
        if kind == "npc":
            obj.talking = True
            obj.face(self.player.x, self.player.y)
            self.player.dir = {"left": "right", "right": "left", "up": "down", "down": "up"}[obj.dir]
            others_met = False
            first = obj.talk_count == 0
            after = None
            if obj.id == "elder" and self.combat.boss_defeated and self.quest.state != "done":
                lines = list(Q.THANKS)                     # Grimhorn is dead: report back and get the reward
                obj.talk_count += 1 if first else 0
                after = self.finish_quest
            elif obj.id == "elder" and self.quest.state == "active":
                lines = list(Q.REMINDER)
            elif obj.id == "elder" and self.quest.state == "unknown":
                lines = obj.lines(others_met) + Q.OFFER     # first request: go and defeat the boss
                after = self.start_quest
            else:
                lines = obj.lines(others_met)

            def end(n=obj, first=first, after=after):
                n.talking = False
                self.play("bye")
                if after:
                    after()
            self.dialogue.start(obj.name, obj.role, lines, obj.portrait, end)
        elif kind == "animal":
            if obj.kind == "chicken":
                line = random.choice(["Bwak! Bwak!", "The chicken eyes you suspiciously, then goes back to pecking.",
                                      "Cluck. (It seems to be saying: this is MY plaza.)"])
            else:
                line = random.choice(["Woof! The dog wags its tail so hard its whole body wiggles.",
                                      "The dog sniffs your boots and approves."])
            obj.state = "idle"
            self.dialogue.start("", "", [line], None)
        else:
            self.dialogue.start(obj["name"], "", obj["text"], None)

    def start_quest(self):
        self.quest.state = "active"
        self.quest.show_hud()
        self.toast("New quest: " + Q.TITLE + "  (see Inventory: I)", 5.0)
        self.save_game(auto=True)

    def finish_quest(self):
        c = self.combat
        self.quest.state = "done"
        self.quest.show_hud()
        c.max_hp += Q.REWARD["max_hp"]
        c.max_mp += Q.REWARD["max_mp"]
        c.hp, c.mp = c.max_hp, c.max_mp
        c.inv.add("health_potion", Q.REWARD["health_potion"])
        c.inv.add("mana_potion", Q.REWARD["mana_potion"])
        self.play("talk")
        self.toast("Quest complete: " + Q.TITLE, 6.0)
        self.save_game(auto=True)


    # ------------------------------------------------------------ save / load / death
    def collect_save(self):
        c = self.combat
        lvl = self.dungeon.level
        scene = self.scene
        spawn = None
        if scene == "dungeon":
            if lvl == 6:                                   # throne room: after the fight you go home, before it you wait on floor 5
                if c.boss_defeated:
                    scene = "village"
                else:
                    lvl = 5
            spawn = "entrance" if lvl == 1 else "down"
        if scene == "village" and self.scene == "dungeon":
            px, py = self.village_return_pos or (48 * T + 16, 84 * T + 24)
            pdir = "down"
        elif scene == "village":
            px, py, pdir = self.player.x, self.player.y, self.player.dir
        else:
            px = py = 0
            pdir = "up"
        return dict(
            scene=scene, level=lvl, spawn=spawn, x=px, y=py, dir=pdir, time=self.time,
            quest=self.quest.state,
            hp=c.hp, mp=c.mp, max_hp=c.max_hp, max_mp=c.max_mp, weapon=c.weapon, kills=c.kills,
            boss_defeated=c.boss_defeated, boss_tries=c.boss_tries,
            cleared_floors=sorted(c.cleared_floors),
            dungeon_explored=self.dungeon.explored_to_save(),
            inv=[list(s) if s else None for s in c.inv.slots], inv_sel=c.inv.sel,
            talk={n.id: n.talk_count for n in self.npcs},
            dungeon_hint=self.dungeon_hint,
            meta=dict(place=("The Hollow Below - Floor %d" % lvl) if scene == "dungeon" else "Hearthmoor Village"),
        )

    def save_game(self, auto=False, slot=None):
        """Write a save slot. auto=True is the quiet autosave (floor cleared, quest changes, ...) and goes to
        the autosave slot; otherwise slot defaults to the slot you last used."""
        if not self.started or self.state != "play" or self.death_t > 0 or self.combat.dying:
            return False
        if slot is None:
            slot = SAVE.AUTO if auto else self.current_slot
        try:
            SAVE.write(self.collect_save(), slot)
        except OSError as ex:
            print("Save failed:", ex)
            self.toast("Could not save the game!", 3.0)
            return False
        if slot != SAVE.AUTO:
            self.current_slot = slot
        label = "(auto)" if slot == SAVE.AUTO else "to slot %s" % slot
        self.toast("Game saved " + label, 1.8 if auto else 2.5)
        if not auto:
            self.play("blip")
        self.build_menus()
        return True

    def load_game(self, slot=None):
        if slot is None:                                   # quick load: the most recent save
            slot = SAVE.latest()
        data = SAVE.read(slot) if slot is not None else None
        if not data:
            self.toast("No saved game found.", 2.5)
            return False
        try:
            self.apply_save(data)
        except Exception as ex:                            # a broken / hand-edited file must never crash the game
            print("Load failed:", ex)
            self.toast("The save file could not be loaded.", 3.0)
            return False
        if slot != SAVE.AUTO:
            self.current_slot = slot
        return True

    def apply_save(self, d):
        c = self.combat
        self.state = "play"
        self.started = True
        self.paused = False
        self.show_inv = self.show_map = False
        self.dialogue.active = False
        self.tut.active = False
        self.tele_t = self.death_t = 0.0
        self.help_t = 0.0
        self.toasts = []
        self.time = float(d.get("time", 9.0))
        self.quest.state = d.get("quest", "unknown")
        self.quest.hud_t = 0.0
        self.dungeon_hint = bool(d.get("dungeon_hint", False))
        for n in self.npcs:
            n.talk_count = int(d.get("talk", {}).get(n.id, 0))
            n.talking = False
        c.max_hp, c.max_mp = int(d["max_hp"]), int(d["max_mp"])
        c.weapon = d.get("weapon", "sword")
        c.kills = int(d.get("kills", 0))
        c.boss_defeated = bool(d.get("boss_defeated", False))
        c.boss_tries = int(d.get("boss_tries", 0))
        c.cleared_floors = set(int(f) for f in d.get("cleared_floors", []))
        self.dungeon.load_explored(d.get("dungeon_explored"))
        self.map_floor = 1
        c.victory = c.victory_done = False
        c.dying = False
        for i in range(len(c.inv.slots)):
            s = d["inv"][i] if i < len(d["inv"]) else None
            c.inv.slots[i] = [s[0], int(s[1])] if s else None
        c.inv.sel = int(d.get("inv_sel", 0))
        if d.get("scene") == "dungeon":
            self.village_return_pos = (48 * T + 16, 84 * T + 24)
            self.scene = "dungeon"
            c.dungeon_active = True
            self.dungeon.set_level(int(d["level"]), spawn=d.get("spawn") or "entrance")
            self.player.x, self.player.y = self.dungeon.player_spawn()
            self.player.dir = "up"
            self.dungeon.cam = [max(0, self.player.x - VIEW_W / 2), max(0, self.player.y - VIEW_H / 2)]
            self.banner_text = "The Hollow Below — Floor %d" % self.dungeon.level
            self.play_music("dark.mp3", fade_ms=800)
        else:
            self.scene = "village"
            c.dungeon_active = False
            self.dungeon.set_level(1, spawn="entrance")
            self.player.x, self.player.y = float(d["x"]), float(d["y"])
            self.player.dir = d.get("dir", "down")
            self.center_camera(True)
            self.banner_text = "Hearthmoor Village"
            self.play_music("hearth_and_willow.mp3", fade_ms=800)
        c.hp, c.mp = min(int(d["hp"]), c.max_hp), min(int(d["mp"]), c.max_mp)
        self.player.z = self.player.vz = 0.0
        self.banner_t = 3.2
        self.update_place(True)
        self.build_menus()
        if self.music_on:
            pygame.mixer.music.unpause()
        self.toast("Game loaded", 2.5)

    def respawn_at_goddess(self):
        """The hero fell. He wakes before the goddess statue in her sanctuary; cleared floors stay cleared."""
        c = self.combat
        if self.scene == "dungeon" and self.dungeon.level == 6 and not c.boss_defeated:
            c.boss_tries += 1                              # Grimhorn remembers you
        self.scene = "village"
        c.dungeon_active = False
        c.dying = False
        self.dungeon.set_level(1, spawn="entrance")        # reloads floor 1 (cleared floors stay empty)
        c.hp, c.mp = c.max_hp, c.max_mp
        gx, gy = self.world.goddess
        self.player.x, self.player.y = (gx + 2) * T + 16, (gy + 3) * T + 24      # on the flagstones, just in front of the statue
        self.player.dir = "up"
        self.player.z = self.player.vz = 0.0
        self.tele_t = 0.0
        self.death_t = 0.0
        self.heal_t = 2.2
        self.dialogue.active = False
        self.center_camera(True)
        self.banner_text = "Hearthmoor Village"
        self.banner_t = 3.2
        self.play_music("hearth_and_willow.mp3", fade_ms=1500)
        self.toast("You awaken before the goddess statue...", 4.5)
        self.save_game(auto=True)

    def draw_death(self, v):
        t = self.death_t
        a = max(0, min(255, int(255 * t / 1.2)))
        veil = pygame.Surface((VIEW_W, VIEW_H))
        veil.fill((10, 0, 4))
        veil.set_alpha(a)
        v.blit(veil, (0, 0))
        if t > 0.9:
            k = min(1.0, (t - 0.9) / 0.8)
            col = (int(200 * k), int(30 * k), int(40 * k))
            self.text_shadow(v, self.font_b, "YOU DIED", (VIEW_W // 2, VIEW_H // 2 - 22), col, (0, 0, 0), True)
            sub = (int(190 * k), int(180 * k), int(170 * k))
            self.text_shadow(v, self.font, "The goddess calls you back...", (VIEW_W // 2, VIEW_H // 2 + 12), sub, (0, 0, 0), True)

    def draw_quest(self, v, x, y):
        """Quest tracker panel (top-left, under the other panels)."""
        t = self.quest.hud_tracker()
        if not t:
            return
        title, obj = t
        words, lines, cur = obj.split(), [], ""
        for w in words:
            tt = (cur + " " + w).strip()
            if self.font_s.size(tt)[0] <= 186:
                cur = tt
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        done = self.quest.state == "done"
        ready = self.quest.state == "ready"
        h = 22 + len(lines) * 12
        self.panel(v, pygame.Rect(x, y, 204, h), 200)
        col = (170, 235, 170) if (done or ready) else (255, 226, 150)
        self.text_shadow(v, self.font_s, "QUEST: " + title, (x + 8, y + 5), col)
        for i, ln in enumerate(lines):
            self.text_shadow(v, self.font_s, ln, (x + 8, y + 19 + i * 12), (236, 228, 214))

    def pray(self):
        """Goddess statue in the sanctuary behind the Whispering Shrine: refills HP and MP (as often as you like)."""
        c = self.combat
        if c.restore_all():
            self.heal_t = 2.2
            lines = ["You kneel before the goddess and close your eyes.",
                     "Warm light pours from the orb in her hands. Your wounds close and your mind grows clear.",
                     "HP and MP fully restored."]
            self.toast("The goddess restores your HP and MP", 3.0)
        else:
            self.heal_t = 1.0
            lines = ["The goddess smiles down at you. You are already in perfect health.",
                     "Her blessing will be waiting whenever you return from the dark."]
        self.dialogue.start("Goddess Statue", "", lines, None)

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        keys = pygame.key.get_pressed()
        hide = self.scene == "dungeon" and self.state == "play" and not self.paused and not self.show_inv and not self.show_map
        if hide != self.mouse_hidden:                   # the dungeon draws its own crosshair
            self.mouse_hidden = hide
            pygame.mouse.set_visible(not hide)
        if self.state == "title" or self.paused:        # menus: highlight the button under the mouse
            mp = pygame.mouse.get_pos()
            if mp != self._last_mouse:
                self._last_mouse = mp
                m = self.current_menu()
                if m:
                    m.hover(self.mouse_view())
                elif self.menu_screen == "slots":
                    for i in range(len(self.slot_ids)):
                        if self.slot_row_rect(i).collidepoint(self.mouse_view()) and self.slot_sel != i:
                            self.slot_sel, self.slot_confirm = i, None
        if self.state == "title":
            # slow camera drift over the village while the time of day rolls on
            self.time = (self.time + dt / 5.0) % 24.0
            bx, by = self.title_cam
            self.cam = [max(0, min(W.W * T - VIEW_W, bx + math.sin(self.t * 0.2) * 70)),
                        max(0, min(W.H * T - VIEW_H, by + math.cos(self.t * 0.15) * 34))]
            for n in self.npcs:
                n.update(dt, self.world, [self.player.foot])
            for a in self.animals:
                a.update(dt, self.world)
            return
        if self.paused or self.show_map or self.show_inv:
            return
        self.heal_t = max(0.0, self.heal_t - dt)
        self.quest.update(self, dt)
        talking = self.dialogue.active
        if self.music_on:
            want = 0.22 if talking else ((0.44 if self.combat.boss_lock else 0.32) if self.scene == "dungeon" else 0.45)
            cur = pygame.mixer.music.get_volume()
            pygame.mixer.music.set_volume(cur + max(-0.01, min(0.01, want - cur)))
        if self.scene == "dungeon" and self.dialogue.active:           # throne-room speech: the world holds still
            self.dialogue.update(dt, self.sfx.get("blip"))
            self.player.moving = False
            self.player.anim = 0
            self.target = None
            self.dungeon.update(dt, self.player)
            return
        if self.scene == "dungeon" and (self.combat.dying or self.death_t > 0):
            self.death_t += dt                                      # death scene: the world freezes, screen fades out
            if self.death_t >= 3.2:
                self.respawn_at_goddess()
            for t in self.toasts:
                t[1] -= dt
            self.toasts = [t for t in self.toasts if t[1] > 0]
            return
        if self.scene == "dungeon":
            mx, my = self.mouse_view()
            cam = self.dungeon.cam
            aim = (mx + int(cam[0]), my + int(cam[1]))            # cursor in dungeon world coordinates
            self.combat.update(dt, keys, aim, pygame.mouse.get_pressed()[0])
            self.target = self.find_target()
            self.dungeon.update(dt, self.player)
            w = self.dungeon.world
            if self.dungeon.level == 6 and w.exit_open and self.tele_t == 0:
                ex, ey = w.exit_tile
                if math.hypot(self.player.x - (ex * T + 16), (self.player.y - 4) - (ey * T + 16)) < 30:
                    self.tele_t = 0.001
                    self.toast("The portal pulls you away...", 2.0)
            if self.tele_t > 0:
                self.tele_t += dt
                if self.tele_t >= 1.3:
                    self.tele_t = 0.0
                    self.exit_dungeon()
                    self.toast("You step out into the sunlight. Hearthmoor is safe at last!", 5.0)
                    return
            self.update_place()
            self.banner_t = max(0, self.banner_t - dt)
            self.help_t = max(0, self.help_t - dt)
            for t in self.toasts:
                t[1] -= dt
            self.toasts = [t for t in self.toasts if t[1] > 0]
            return
        self.dialogue.update(dt, self.sfx.get("blip"))
        npc_rects = [n.foot for n in self.npcs]
        if not talking:
            self.player.update(dt, keys, self.world, npc_rects)
            if self.player.just_landed:
                self.play("land")
            self.target = self.find_target()
        else:
            self.player.moving = False
            self.player.anim = 0
            self.target = None
        for n in self.npcs:
            others = [m.foot for m in self.npcs if m is not n] + [self.player.foot]
            n.update(dt, self.world, others)
        for a in self.animals:
            a.update(dt, self.world)
        self.time = (self.time + dt / 22.0) % 24.0    # one in-game hour ~ 22 s
        self.tut.update(dt, self)
        self.center_camera()
        self.update_place()
        self.banner_t = max(0, self.banner_t - dt)
        self.help_t = max(0, self.help_t - dt)
        for t in self.toasts:
            t[1] -= dt
        self.toasts = [t for t in self.toasts if t[1] > 0]
        # smoke
        cam = self.cam
        for i, (nm, *_rest) in enumerate(HOUSES):
            if nm in ("house_cottage_b", "house_shop"):
                continue
            cx, cy = self.world.chimneys[i]
            if cam[0] - 40 < cx < cam[0] + VIEW_W + 40 and cam[1] - 60 < cy < cam[1] + VIEW_H + 60:
                self.smoke_t[i] -= dt
                if self.smoke_t[i] <= 0:
                    self.smoke_t[i] = random.uniform(0.7, 1.3)
                    self.smoke.append([cx + random.uniform(-1, 1), cy - 2, 0.0, random.uniform(-4, 4)])
        for s in self.smoke:
            s[2] += dt
            s[1] -= 14 * dt
            s[0] += (5 + s[3]) * dt
        self.smoke = [s for s in self.smoke if s[2] < 3.6]

    # -------------------------------------------------------------- draw
    def draw_world(self, v):
        if self.scene == "dungeon":
            self.dungeon.draw(v, self.player, self.shadow, self.combat)
            self.combat.draw_overlay(v, self.font_s)
            if self.target and not self.dialogue.active:
                bob = math.sin(self.t * 5) * 2
                direction, pos = self.target[1]
                if direction == "gate":
                    label = ("Enter the Purple Gate" if self.combat.cleared and not self.combat.boss_defeated
                             else ("Dormant gate" if self.combat.boss_defeated else "Sealed - slay all foes"))
                elif direction == "down":
                    label = ("Descend" if self.combat.cleared
                             else "Sealed - %d foes left" % self.combat.alive_count())
                elif self.dungeon.level == 1:
                    label = "Return to Hearthmoor"
                else:
                    label = "Go Up"
                lw = self.font_s.size(label)[0]
                pad = pygame.Surface((lw + 10, 14), pygame.SRCALPHA)
                pygame.draw.rect(pad, (16, 13, 22, 205), pad.get_rect(), border_radius=5)
                pad.blit(self.font_s.render(label, True, (235, 225, 245)), (5, 2))
                tx = pos[0] * T + 16 - self.dungeon.cam[0]
                ty = pos[1] * T - self.dungeon.cam[1] - 12
                v.blit(pad, (tx - pad.get_width() // 2, ty - 18 + bob))
                v.blit(self.a["ui"]["key_e"], (tx - 10, ty + bob))
            return
        cam = (int(self.cam[0]), int(self.cam[1]))
        v.blit(self.baked.ground, (0, 0), (cam[0], cam[1], VIEW_W, VIEW_H))
        # animated water + shore foam
        f = int(self.t * 3) % 4
        tw = self.a["tiles"]
        t0x, t0y = cam[0] // T, cam[1] // T
        for ty in range(t0y, t0y + VIEW_H // T + 2):
            for tx in range(t0x, t0x + VIEW_W // T + 2):
                if not (0 <= tx < W.W and 0 <= ty < W.H):
                    continue
                tt = self.world.terrain[ty][tx]
                if tt == W.WATER or tt == W.DEEP:
                    var = (tx * 3 + ty * 5) % 2
                    img = tw[f"{'water' if tt == W.WATER else 'deep'}_{var}_{(f + tx + ty) % 4}"]
                    v.blit(img, (tx * T - cam[0], ty * T - cam[1]))
                    for st in self.baked.shore.get((tx, ty), ()):
                        v.blit(st, (tx * T - cam[0], ty * T - cam[1]))
        # y-sorted objects & actors
        view = pygame.Rect(cam[0] - 40, cam[1] - 40, VIEW_W + 80, VIEW_H + 120)
        items = []
        for p in self.props:
            if p[2] < view.right and p[2] + p[4] > view.left and p[3] < view.bottom and p[3] + p[5] > view.top:
                items.append((p[0], 0, p))
        items.append((self.player.y, 1, self.player))
        for n in self.npcs:
            if view.collidepoint(n.x, n.y):
                items.append((n.y, 1, n))
        for a in self.animals:
            if view.collidepoint(a.x, a.y):
                items.append((a.y, 1, a))
        items.sort(key=lambda i: i[0])
        self.gatefx.draw_ground(v, cam, self.t)               # glow, rune seal and mist at the Hollow Gate
        cf = int(self.t * 6) % 2
        for _, kind, o in items:
            if kind == 0:
                img = o[1] if o[1] is not None else self.a["objects"][f"campfire_{cf}"]
                v.blit(img, (o[2] - cam[0], o[3] - cam[1]))
            else:
                o.draw(v, cam, self.shadow)
        self.gatefx.draw_flames(v, cam, self.t)
        # chimney smoke
        for s in self.smoke:
            k = s[2] / 3.6
            idx = min(len(self.smoke_surf) - 1, int(k * len(self.smoke_surf)))
            img = self.smoke_surf[idx]
            img.set_alpha(int(150 * (1 - k)))
            v.blit(img, (s[0] - cam[0] - img.get_width() // 2, s[1] - cam[1] - img.get_height() // 2))
        # butterflies (daytime only)
        h = self.time
        if 6.5 < h < 19.5:
            for b in self.butterflies:
                tt = self.t * b["sp"] + b["ph"]
                bx = b["cx"] + math.sin(tt) * b["rx"]
                by = b["cy"] + math.sin(tt * 1.7) * b["ry"]
                fr = int(self.t * 8 + b["ph"]) % 2
                img = self.a["animals"][f"butterfly_{b['kind']}_{fr}"]
                if cam[0] - 10 < bx < cam[0] + VIEW_W and cam[1] - 10 < by < cam[1] + VIEW_H:
                    v.blit(img, (bx - cam[0], by - cam[1]))
        # prompt above the interaction target
        if self.target and not self.dialogue.active:
            kind, obj = self.target
            if kind == "npc":
                tx, ty = obj.x - cam[0], obj.y - cam[1] - 46
                label = obj.name
            elif kind == "animal":
                tx, ty = obj.x - cam[0], obj.y - cam[1] - 34
                label = "Pet" if obj.kind == "dog" else "Chicken"
            else:
                tx, ty = obj["rect"].centerx - cam[0], obj["rect"].top - cam[1] - 14
                label = obj["name"]
            bob = math.sin(self.t * 5) * 2
            key = self.a["ui"]["key_e"]
            lw = self.font_s.size(label)[0]
            pad = pygame.Surface((lw + 10, 14), pygame.SRCALPHA)
            pygame.draw.rect(pad, (30, 20, 20, 170), pad.get_rect(), border_radius=5)
            pad.blit(self.font_s.render(label, True, (255, 246, 226)), (5, 2))
            v.blit(pad, (tx - pad.get_width() // 2, ty - 18 + bob))
            v.blit(key, (tx - 10, ty + bob))
        orb = self.statue_orb(cam)
        # day / night light
        r, g, b, a = tint_at(self.time)
        if a > 0:
            self.night.fill((r, g, b, a))
            if -60 < orb[0] < VIEW_W + 60 and -60 < orb[1] < VIEW_H + 60:      # the statue lights its own corner
                self.night.blit(self.glow_mask, (orb[0] - 56, orb[1] - 56), special_flags=pygame.BLEND_RGBA_SUB)
            if self.time > 17.5 or self.time < 6.3:
                for lx, ly in self.world.lamps:
                    sx, sy = lx - cam[0], ly - cam[1]
                    if -60 < sx < VIEW_W + 60 and -60 < sy < VIEW_H + 60:
                        self.night.blit(self.glow_mask, (sx - 56, sy - 56), special_flags=pygame.BLEND_RGBA_SUB)
                for f_ in self.campfires:
                    sx, sy = f_[2] - cam[0] + 16, f_[3] - cam[1] + 14
                    if -60 < sx < VIEW_W + 60 and -60 < sy < VIEW_H + 60:
                        self.night.blit(self.glow_mask, (sx - 56, sy - 56), special_flags=pygame.BLEND_RGBA_SUB)
            v.blit(self.night, (0, 0))
            if self.time > 17.5 or self.time < 6.3:
                for lx, ly in self.world.lamps:
                    sx, sy = lx - cam[0], ly - cam[1]
                    if -60 < sx < VIEW_W + 60 and -60 < sy < VIEW_H + 60:
                        v.blit(self.glow, (sx - 56, sy - 56), special_flags=pygame.BLEND_RGB_ADD)
                for f_ in self.campfires:
                    sx, sy = f_[2] - cam[0] + 16, f_[3] - cam[1] + 14
                    if -60 < sx < VIEW_W + 60 and -60 < sy < VIEW_H + 60:
                        v.blit(self.glow, (sx - 56, sy - 56), special_flags=pygame.BLEND_RGB_ADD)
        self.draw_statue_fx(v, cam, orb)
        self.draw_heal_fx(v, cam)

    def statue_orb(self, cam):
        """Screen position of the glowing orb in the goddess's hands."""
        gx, gy = self.world.goddess
        return int((gx + 2.5) * T - cam[0]), int((gy + 2) * T + 4 - 198 + 43 - cam[1])    # sprite is 198px tall, orb 43px from its top

    def draw_statue_fx(self, v, cam, orb):
        ox, oy = orb
        if not (-60 < ox < VIEW_W + 60 and -80 < oy < VIEW_H + 80):
            return
        pulse = 0.5 + 0.5 * math.sin(self.t * 2.2)
        img = self.holy[min(2, int(pulse * 3))]
        v.blit(img, (ox - img.get_width() // 2, oy - img.get_height() // 2), special_flags=pygame.BLEND_RGB_ADD)
        for i in range(7):                                   # motes of light drifting up around her
            k = (self.t * 0.28 + i / 7.0) % 1.0
            px = ox + math.sin(self.t * 0.9 + i * 2.1) * (10 + 12 * k)
            py = oy + 30 - k * 78
            a = math.sin(k * math.pi)
            c = (int(150 * a), int(210 * a), int(255 * a))
            v.fill(c, (int(px), int(py), 2, 2), special_flags=pygame.BLEND_RGB_ADD)

    def draw_heal_fx(self, v, cam):
        """Beam of light and rising sparkles on the hero after praying."""
        if self.heal_t <= 0:
            return
        k = self.heal_t / 2.2
        px, py = int(self.player.x - cam[0]), int(self.player.y - cam[1])
        a = max(0.0, min(1.0, k * 1.6))
        beam = pygame.Surface((26, 70), pygame.SRCALPHA)
        for yy in range(70):
            w = 6 + int(10 * (yy / 70))
            pygame.draw.rect(beam, (190, 230, 255, int(110 * a * (1 - yy / 80))), (13 - w // 2, yy, w, 1))
        v.blit(beam, (px - 13, py - 70))
        for i in range(14):
            ph = (i / 14.0 + (1 - k) * 1.6) % 1.0
            sx = px + math.sin(i * 1.7 + self.t * 3) * 12
            sy = py - 4 - ph * 46
            c = (int(200 * a), int(240 * a), int(255 * a))
            v.fill(c, (int(sx), int(sy), 2, 2), special_flags=pygame.BLEND_RGB_ADD)

    def text_shadow(self, v, font, text, pos, color=(255, 246, 226), sh=(40, 24, 20), center=False):
        img = font.render(text, True, color)
        s = font.render(text, True, sh)
        x, y = pos
        if center:
            x -= img.get_width() // 2
        v.blit(s, (x + 1, y + 1))
        v.blit(img, (x, y))

    def panel(self, v, rect, alpha=170):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (40, 26, 22, alpha), s.get_rect(), border_radius=8)
        pygame.draw.rect(s, (214, 178, 120, 220), s.get_rect(), 1, border_radius=8)
        v.blit(s, rect.topleft)

    def draw_toasts(self, v):
        for i, (t, d) in enumerate(self.toasts[-3:]):
            img = self.font.render(t, True, (255, 246, 226))
            w = img.get_width() + 20
            s = pygame.Surface((w, 24), pygame.SRCALPHA)
            pygame.draw.rect(s, (60, 100, 70, 200), s.get_rect(), border_radius=8)
            pygame.draw.rect(s, (190, 230, 180, 230), s.get_rect(), 1, border_radius=8)
            s.blit(img, (10, 5))
            s.set_alpha(int(255 * min(1, d / 0.6)))
            v.blit(s, ((VIEW_W - w) // 2, 52 + i * 28))

    def draw_ui(self, v):
        if self.scene == "dungeon":
            self.panel(v, pygame.Rect(6, 6, 210, 46), 220)
            self.text_shadow(v, self.font_m, "THE HOLLOW BELOW", (14, 10), (220, 204, 238), (25, 18, 30))
            hint = "Floor %d/5  •  E: stairs  •  M: map" % self.dungeon.level if self.dungeon.level < 6 else "Throne Room  •  defeat the Warden"
            self.text_shadow(v, self.font_s, hint, (14, 30), (190, 180, 205))
            if self.banner_t > 0:
                txt = self.font_m.render(self.banner_text, True, (235, 224, 246))
                w = txt.get_width() + 36
                s = pygame.Surface((w, 30), pygame.SRCALPHA)
                pygame.draw.rect(s, (25, 18, 32, 195), s.get_rect(), border_radius=15)
                pygame.draw.rect(s, (148, 122, 168, 230), s.get_rect(), 1, border_radius=15)
                s.blit(txt, (18, 8))
                v.blit(s, ((VIEW_W - w) // 2, 12))
            self.draw_quest(v, 6, 56)
            self.draw_toasts(v)
            self.combat.draw_hud(v, self.font, self.font_s, self.mouse_view())
            self.dialogue.draw(v)
            if self.tele_t > 0:                                  # portal flash
                a = min(255, int(255 * self.tele_t / 1.2))
                flash = pygame.Surface((VIEW_W, VIEW_H))
                flash.fill((235, 215, 255))
                flash.set_alpha(a)
                v.blit(flash, (0, 0))
            if self.death_t > 0:
                self.draw_death(v)
            return
        # clock / progress
        hh, mm = int(self.time), int((self.time % 1) * 60) // 5 * 5
        self.panel(v, pygame.Rect(6, 6, 118, 36))
        self.text_shadow(v, self.font, f"{hh:02d}:{mm:02d}", (14, 10))
        icon = "Day" if 6.3 < self.time < 19 else "Night"
        self.text_shadow(v, self.font_s, icon, (66, 13), (200, 190, 160))
        # hero vitals (HP / MP)
        c = self.combat
        self.panel(v, pygame.Rect(6, 46, 118, 36))
        for i, (lab, cur, mx, fill, back) in enumerate((("HP", c.hp, c.max_hp, (190, 44, 60), (52, 20, 26)),
                                                        ("MP", c.mp, c.max_mp, (60, 110, 235), (18, 24, 56)))):
            by = 51 + i * 14
            self.text_shadow(v, self.font_s, lab, (12, by), (255, 246, 226))
            bar = pygame.Rect(30, by + 1, 88, 10)
            pygame.draw.rect(v, back, bar, border_radius=3)
            pygame.draw.rect(v, fill, (bar.x, bar.y, int(bar.w * cur / mx), bar.h), border_radius=3)
            pygame.draw.rect(v, (235, 225, 215), bar, 1, border_radius=3)
            t = self.font_s.render(f"{cur}/{mx}", True, (255, 255, 255))
            v.blit(t, (bar.centerx - t.get_width() // 2, bar.y - 1))
        self.draw_quest(v, 6, 86)
        # minimap
        mm_rect = pygame.Rect(VIEW_W - 108, 6, 102, 102)
        self.panel(v, mm_rect, 200)
        v.blit(self.mini, (VIEW_W - 105, 9))
        pxx = VIEW_W - 105 + int(self.player.x / T)
        pyy = 9 + int(self.player.y / T)
        if int(self.t * 3) % 2 == 0:
            pygame.draw.rect(v, (255, 255, 255), (pxx - 2, pyy - 2, 5, 5))
        pygame.draw.rect(v, (230, 40, 40), (pxx - 1, pyy - 1, 3, 3))
        # location banner
        if self.banner_t > 0:
            a = min(1.0, self.banner_t / 0.6, (3.2 - self.banner_t) / 0.4 + 0.01)
            txt = self.font_m.render(self.banner_text, True, (255, 246, 226))
            w = txt.get_width() + 36
            s = pygame.Surface((w, 30), pygame.SRCALPHA)
            pygame.draw.rect(s, (40, 26, 22, 180), s.get_rect(), border_radius=15)
            pygame.draw.rect(s, (214, 178, 120, 230), s.get_rect(), 1, border_radius=15)
            s.blit(txt, (18, 8))
            s.set_alpha(int(255 * max(0, min(1, a))))
            v.blit(s, ((VIEW_W - w) // 2, 12))
        self.draw_toasts(v)
        self.tut.draw(self, v)
        self.dialogue.draw(v)
        if self.help_t > 0 and not self.dialogue.active:
            a = min(1.0, self.help_t / 2)
            txt = "WASD move  SHIFT run  SPACE jump  E talk  M map  I inventory  B music  H help"
            img = self.font_s.render(txt, True, (255, 246, 226))
            s = pygame.Surface((img.get_width() + 18, 20), pygame.SRCALPHA)
            pygame.draw.rect(s, (40, 26, 22, 170), s.get_rect(), border_radius=8)
            s.blit(img, (9, 4))
            s.set_alpha(int(255 * a))
            v.blit(s, (8, VIEW_H - 28))

    def draw_map(self, v):
        v.fill((0, 0, 0), special_flags=pygame.BLEND_RGB_MULT) if False else None
        dim = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        dim.fill((10, 8, 8, 190))
        v.blit(dim, (0, 0))
        w, h = self.mini_big.get_size()
        x, y = (VIEW_W - w) // 2, (VIEW_H - h) // 2 + 6
        self.panel(v, pygame.Rect(x - 8, y - 8, w + 16, h + 16), 240)
        v.blit(self.mini_big, (x, y))
        for nm, (x0, y0, x1, y1) in PLACES:
            cx, cy = (x0 + x1) / 2 * 3, (y0 + y1) / 2 * 3
            if nm == "The Hollow Gate":
                self.draw_gate_marker(v, x + 49 * 3, y + 87 * 3)
                continue
            self.text_shadow(v, self.font_s, nm, (x + cx, y + cy - (18 if nm == "Goddess Sanctuary" else 4)), center=True)
        for n in self.npcs:
            if n.talk_count > 0:
                pygame.draw.circle(v, (255, 226, 90), (x + int(n.x / T * 3), y + int(n.y / T * 3)), 3)
                pygame.draw.circle(v, (60, 40, 20), (x + int(n.x / T * 3), y + int(n.y / T * 3)), 3, 1)
        px_, py_ = x + int(self.player.x / T * 3), y + int(self.player.y / T * 3)
        pygame.draw.circle(v, (255, 255, 255), (px_, py_), 5)
        pygame.draw.circle(v, (230, 40, 40), (px_, py_), 3)
        self.text_shadow(v, self.font_m, "Hearthmoor & the Whisperwood", (VIEW_W // 2, y - 28), center=True)
        self.text_shadow(v, self.font_s, "Press M to close   -   yellow: villagers   -   purple: dungeon gate   -   light blue: goddess statue (north sanctuary)",
                         (VIEW_W // 2, y + h + 12), (210, 200, 180), center=True)

    # ------------------------------------------------------------ dungeon map
    def dungeon_map_floors(self):
        """Floors the map can show: every explored floor, plus the one the hero is standing on."""
        d = self.dungeon
        return [f for f in range(1, 7) if d.explored[f] or f == d.level]

    def browse_dungeon_map(self, step):
        floors = self.dungeon_map_floors()
        if self.map_floor not in floors:
            self.map_floor = floors[0]
        i = floors.index(self.map_floor) + step
        if 0 <= i < len(floors):
            self.map_floor = floors[i]
            self.play("blip")

    def draw_dungeon_map(self, v):
        from dungeon import DW, DH, WALL, WATER, LAVA, PILLAR, FLOOR_NAMES
        d, c = self.dungeon, self.combat
        floors = self.dungeon_map_floors()
        if self.map_floor not in floors:
            self.map_floor = d.level
        lv = self.map_floor
        world = d.world_for(lv)
        seen = d.explored[lv]
        dim = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        dim.fill((6, 4, 10, 215))
        v.blit(dim, (0, 0))

        sc = 11                                              # pixels per tile
        mw, mh = DW * sc, DH * sc
        mx, my = (VIEW_W - mw) // 2, 52
        pygame.draw.rect(v, (12, 9, 18), (mx - 8, my - 8, mw + 16, mh + 16), border_radius=8)
        pygame.draw.rect(v, (148, 122, 168), (mx - 8, my - 8, mw + 16, mh + 16), 1, border_radius=8)

        # title + floor name
        title = "THE HOLLOW BELOW" if lv < 6 else "THE WARDEN'S HALL"
        self.text_shadow(v, self.font_m, title, (VIEW_W // 2, 6), (226, 210, 244), (25, 18, 30), True)
        self.text_shadow(v, self.font_s,
                         ("Floor %d/5 - %s" % (lv, FLOOR_NAMES[lv])) if lv < 6 else FLOOR_NAMES[6],
                         (VIEW_W // 2, 22), (190, 180, 205), (25, 18, 30), True)

        # floor tabs down the left side
        tx0, ty0 = mx - 8 - 40, my
        for i, f in enumerate(range(1, 7)):
            if f == 6 and f not in floors:
                continue
            r = pygame.Rect(tx0, ty0 + i * 30, 32, 26)
            have = f in floors
            cleared = f in c.cleared_floors or (f == 6 and c.boss_defeated)
            fill = (58, 44, 76) if f == lv else ((26, 20, 34) if have else (16, 12, 22))
            pygame.draw.rect(v, fill, r, border_radius=5)
            pygame.draw.rect(v, (226, 196, 255) if f == self.map_floor else (86, 72, 104), r, 2 if f == self.map_floor else 1,
                             border_radius=5)
            lab = self.font_m.render("T" if f == 6 else str(f), True, (235, 224, 246) if have else (84, 76, 96))
            v.blit(lab, (r.x + 8, r.y + 5))
            if cleared:
                pygame.draw.circle(v, (120, 230, 130), (r.right - 6, r.y + 6), 3)
            if f == d.level:
                pygame.draw.circle(v, (255, 120, 120), (r.x + 5, r.bottom - 6), 2)

        # the map itself
        for y in range(DH):
            for x in range(DW):
                if (x, y) not in seen:
                    continue
                t = world.grid[y][x]
                rect = (mx + x * sc, my + y * sc, sc, sc)
                if t == WALL:
                    pygame.draw.rect(v, (44, 38, 58), rect)
                elif t == WATER:
                    pygame.draw.rect(v, (46, 88, 150), rect)
                elif t == LAVA:
                    pygame.draw.rect(v, (206, 92, 30), rect)
                elif t == PILLAR:
                    pygame.draw.rect(v, (78, 72, 92), rect)
                    pygame.draw.rect(v, (132, 124, 150), (rect[0] + 3, rect[1] + 3, sc - 6, sc - 6))
                else:
                    pygame.draw.rect(v, (86, 82, 108) if (x + y) % 2 else (80, 76, 102), rect)
        # bright edge where a walkable tile meets a wall, so rooms read clearly
        for y in range(1, DH - 1):
            for x in range(1, DW - 1):
                if (x, y) in seen and world.grid[y][x] == WALL:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if (x + dx, y + dy) in seen and world.grid[y + dy][x + dx] not in (WALL,):
                            px, py = mx + x * sc, my + y * sc
                            if dx == 1:
                                pygame.draw.line(v, (170, 150, 200), (px + sc - 1, py), (px + sc - 1, py + sc - 1))
                            elif dx == -1:
                                pygame.draw.line(v, (170, 150, 200), (px, py), (px, py + sc - 1))
                            elif dy == 1:
                                pygame.draw.line(v, (170, 150, 200), (px, py + sc - 1), (px + sc - 1, py + sc - 1))
                            else:
                                pygame.draw.line(v, (170, 150, 200), (px, py), (px + sc - 1, py))

        pulse = 0.5 + 0.5 * math.sin(self.t * 4)
        floor_clear = (lv in c.cleared_floors) or (lv == d.level and c.cleared)

        def marker(tile, kind):
            x, y = tile
            if (x, y) not in seen:
                return
            cx, cy = mx + x * sc + sc // 2, my + y * sc + sc // 2
            if kind == "up":
                pygame.draw.polygon(v, (230, 220, 245), [(cx, cy - 4), (cx - 4, cy + 3), (cx + 4, cy + 3)])
            elif kind == "down":
                col = (120, 230, 130) if floor_clear else (235, 80, 80)
                pygame.draw.polygon(v, col, [(cx, cy + 4), (cx - 4, cy - 3), (cx + 4, cy - 3)])
                pygame.draw.polygon(v, (20, 14, 24), [(cx, cy + 4), (cx - 4, cy - 3), (cx + 4, cy - 3)], 1)
            elif kind == "altar":
                pts = [(cx, cy - 5), (cx + 5, cy), (cx, cy + 5), (cx - 5, cy)]
                pygame.draw.polygon(v, (170 + int(60 * pulse), 100, 240), pts)
                pygame.draw.polygon(v, (240, 220, 255), pts, 1)
            elif kind == "throne":
                pygame.draw.rect(v, (200, 60, 70), (cx - 4, cy - 4, 8, 8))
                pygame.draw.rect(v, (255, 210, 120), (cx - 4, cy - 4, 8, 8), 1)

        if world.up:
            marker(world.up, "up")
        if world.down:
            marker(world.down, "down")
        if world.altar:
            marker(world.altar, "altar")
        if world.throne:
            marker(world.throne, "throne")

        # the hero
        if lv == d.level:
            px_, py_ = mx + int(self.player.x / T * sc), my + int((self.player.y - 4) / T * sc)
            pygame.draw.circle(v, (255, 255, 255), (px_, py_), 5 + int(pulse * 2), 1)
            pygame.draw.circle(v, (230, 40, 40), (px_, py_), 3)

        # status lines + legend
        if lv < 6:
            if lv == d.level and not c.cleared:
                st, col = "Foes left on this floor: %d" % c.alive_count(), (235, 190, 150)
            elif floor_clear:
                st, col = "Floor cleared", (150, 235, 160)
            else:
                st, col = "Not cleared - monsters still lurk here", (235, 190, 150)
        else:
            st, col = ("The Warden has fallen" if c.boss_defeated else "Defeat the Warden"), (235, 190, 150)
        done = len([f for f in range(1, 6) if f in c.cleared_floors])
        self.text_shadow(v, self.font_s, "%s     -     floors cleared: %d/5" % (st, done),
                         (VIEW_W // 2, my + mh + 12), col, (25, 18, 30), True)
        self.text_shadow(v, self.font_s,
                         "A / D or arrows: switch floor   -   M / Esc: close   -   red stairs: sealed   green stairs: open",
                         (VIEW_W // 2, my + mh + 26), (170, 160, 188), (25, 18, 30), True)

    def draw_gate_marker(self, v, mx, my):
        """Pulsing purple marker + label for the Hollow Gate on the big map."""
        pulse = 0.5 + 0.5 * math.sin(self.t * 3.5)
        r = 6 + int(pulse * 3)
        halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (170, 96, 240, int(60 + 80 * pulse)), (r * 2, r * 2), r * 2)
        v.blit(halo, (mx - r * 2, my - r * 2))
        pts = [(mx, my - r), (mx + r, my), (mx, my + r), (mx - r, my)]
        pygame.draw.polygon(v, (40, 18, 70), pts)
        pygame.draw.polygon(v, (196, 140, 255), pts, 2)
        pygame.draw.rect(v, (240, 220, 255), (mx - 1, my - 3, 3, 6))                 # tiny stairwell glyph
        self.text_shadow(v, self.font_s, "The Hollow Below", (mx, my + r + 4), (226, 196, 255), (30, 14, 40), True)
        self.text_shadow(v, self.font_s, "dungeon gate", (mx, my + r + 16), (176, 150, 206), (30, 14, 40), True)

    def draw(self):
        v = self.view
        self.draw_world(v)
        if self.state == "title":
            if self.menu_screen == "controls":
                draw_controls(self, v)
            elif self.menu_screen == "slots":
                draw_slots(self, v)
            elif self.menu_screen == "tutorial_ask":
                draw_ask(self, v)
            else:
                draw_title_screen(self, v)
        else:
            self.draw_ui(v)
            if self.show_map:
                self.draw_dungeon_map(v) if self.scene == "dungeon" else self.draw_map(v)
            if self.show_inv:
                draw_inventory(self, v)
            if self.paused:
                if self.menu_screen == "controls":
                    draw_controls(self, v)
                elif self.menu_screen == "slots":
                    draw_slots(self, v)
                else:
                    draw_pause(self, v)
        self.screen.blit(v, (0, 0)) if self.screen.get_size() == v.get_size() else \
            self.screen.blit(pygame.transform.scale(v, self.screen.get_size()), (0, 0))
        pygame.display.flip()

    # -------------------------------------------------------------- loop
    def handle(self, e):
        if e.type == pygame.QUIT:
            return False
        menu_open = self.state == "title" or self.paused
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and menu_open:
            if self.menu_screen == "controls":
                self.menu_screen = self.controls_back
                self.play("blip")
                return True
            if self.menu_screen == "slots":
                self.slots_mouse(self.mouse_view())
                return True
            m = self.current_menu()
            if m and m.hover(self.mouse_view()):
                return self.menu_do(m.key())
            return True
        if self.show_inv and self.state == "play" and not self.paused:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                inv_click(self, self.mouse_view())
            if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL):
                return True
        if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL):
            # attack is read as "left button held" in update(); right click / scroll swaps weapon
            if self.state == "play" and not self.paused and self.scene == "dungeon":
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                    self.combat.swap_weapon()
                elif e.type == pygame.MOUSEWHEEL and e.y:
                    self.combat.swap_weapon(scroll=True)
            return True
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            if k == pygame.K_F5 and self.state == "play" and not self.paused:
                self.save_game()                                # quick save
                return True
            if k == pygame.K_F9 and not self.paused:
                self.load_game()                                # quick load
                return True
            if menu_open:
                return self.menu_key(k)
            if self.show_inv:                                  # inventory screen swallows the keyboard
                if k in (pygame.K_ESCAPE, pygame.K_i, pygame.K_TAB):
                    self.show_inv = False
                else:
                    inv_key(self, k)
                return True
            # tutorial: TAB skips it, ENTER / E continues on the "read this" steps
            if self.tut.active and self.scene == "village":
                if k == pygame.K_TAB:
                    self.tut.skip(self)
                    return True
                if (k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e) and self.tut.on_info()
                        and not self.dialogue.active and not self.show_map):
                    self.tut.next(self)
                    self.play("blip")
                    return True
            if k == pygame.K_ESCAPE:
                if self.scene == "dungeon":
                    # not while Grimhorn is speaking or the victory screen is up
                    if self.show_map:
                        self.show_map = False
                    elif not self.dialogue.active and not self.combat.victory_active:
                        self.open_pause()
                elif self.show_map:
                    self.show_map = False
                    self.tut.notify(self, "map_close")
                elif self.dialogue.active:
                    self.dialogue.active = False
                    for n in self.npcs:
                        n.talking = False
                else:
                    self.open_pause()
            elif k == pygame.K_b:
                self.toggle_music()
            elif k == pygame.K_i and not self.dialogue.active and not self.show_map and not self.combat.victory_active:
                self.show_inv = True
                self.play("blip")
            elif k in (pygame.K_1, pygame.K_2) and not self.dialogue.active and not self.show_map \
                    and not self.combat.victory_active:
                self.combat.use_item(QUICK_ITEMS[0 if k == pygame.K_1 else 1])
            elif k == pygame.K_SPACE and not self.show_map:
                if self.dialogue.active:
                    self.dialogue.advance()
                elif self.scene == "dungeon":
                    self.combat.dodge(pygame.key.get_pressed())
                elif self.player.jump():
                    self.play("jump")
                    self.tut.notify(self, "jump")
            elif k == pygame.K_m:
                if self.scene == "village":
                    self.show_map = not self.show_map
                    self.tut.notify(self, "map_open" if self.show_map else "map_close")
                elif (self.scene == "dungeon" and not self.dialogue.active and not self.combat.victory_active
                      and not self.combat.dying and self.death_t <= 0 and not self.show_inv):
                    self.show_map = not self.show_map
                    self.map_floor = self.dungeon.level
                    self.play("blip")
            elif (k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d)
                  and self.show_map and self.scene == "dungeon"):
                self.browse_dungeon_map(-1 if k in (pygame.K_LEFT, pygame.K_a) else 1)
            elif k == pygame.K_h:
                self.help_t = 0 if self.help_t > 0 else 12
            elif k == pygame.K_n and not self.dialogue.active and self.scene == "village":
                self.time = (self.time + 1) % 24
                self.toast("Time passes...", 1.5)
            elif k in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER) and not self.show_map:
                if self.scene == "dungeon" and self.combat.victory_active:
                    self.combat.dismiss_victory()
                elif self.dialogue.active:
                    self.dialogue.advance()
                else:
                    self.interact()
        return True

    def run(self, frames=None):
        """Main loop. Returns "restart" if the player chose New Game mid-session, else "quit"."""
        running = True
        n = 0
        while running:
            dt = min(0.05, self.clock.tick(60) / 1000.0)
            for e in pygame.event.get():
                if not self.handle(e):
                    running = False
            self.update(dt)
            self.draw()
            n += 1
            if frames and n >= frames:
                break
        pygame.mouse.set_visible(True)
        return "restart" if self.restart else "quit"


def main():
    ap = argparse.ArgumentParser(description="Hearthmoor village RPG")
    ap.add_argument("--seed", type=int, default=7, help="terrain seed (default 7)")
    ap.add_argument("--skip-title", action="store_true")
    ap.add_argument("--regen-assets", action="store_true", help="re-create all art before starting")
    ap.add_argument("--boss-test", action="store_true", help="start on floor 5 and fight the final boss immediately")
    args = ap.parse_args()
    if args.regen_assets:
        import generate_assets
        generate_assets.main()
    begin_new = False
    while True:
        game = Game(seed=args.seed, skip_title=args.skip_title or args.boss_test, begin_new=begin_new)
        if args.boss_test and not begin_new:
            game.debug_boss()
        if game.run() != "restart":
            break
        begin_new = True
        args.skip_title = args.boss_test = False
    pygame.quit()


if __name__ == "__main__":
    main()
