
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
import gate
from menus import (MenuList, Tutorial, draw_ask, draw_controls, draw_pause, draw_title_screen, make_motes)

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
        self.build_menus()
        self.t = 0.0
        self.show_map = False
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
        main += [("new", "New Game"), ("controls", "Controls"), ("music", self.music_label), ("quit", "Quit")]
        sel = self.menu_main.sel if self.menu_main else 0
        self.menu_main = MenuList(main, top=148, width=230)
        self.menu_main.sel = min(sel, len(main) - 1)
        if self.menu_ask is None:
            self.menu_ask = MenuList([("yes", "Yes, show me the basics"), ("no", "No thanks, let's go")],
                                     top=156, width=320)
        if self.menu_pause is None:
            self.menu_pause = MenuList([("resume", "Resume"), ("controls", "Controls"), ("music", self.music_label),
                                        ("tutorial", "Replay Tutorial"), ("title", "Main Menu"),
                                        ("quit", "Quit Game")], top=112, gap=29, width=230)

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

    def menu_key(self, k):
        scr = self.menu_screen
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

    def change_dungeon_level(self, direction):
        if self.scene != "dungeon":
            return
        old = self.dungeon.level
        if direction == "gate":
            self.enter_throne_room()
            return
        if direction == "down" and old < self.dungeon.max_level:
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
        self.combat.boss_tries = 0
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
        if kind == "npc":
            obj.talking = True
            obj.face(self.player.x, self.player.y)
            self.player.dir = {"left": "right", "right": "left", "up": "down", "down": "up"}[obj.dir]
            others_met = all(n.talk_count > 0 for n in self.npcs if n.id != "elder")
            first = obj.talk_count == 0
            lines = obj.lines(others_met)

            def end(n=obj, first=first):
                n.talking = False
                self.play("bye")
                if first:
                    c = self.met_count()
                    if c == len(self.npcs):
                        self.toast("You've met every villager! Visit Elder Maren once more.", 5)
                    else:
                        self.toast(f"Met {n.name}  ({c}/{len(self.npcs)} villagers)")
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

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        keys = pygame.key.get_pressed()
        hide = self.scene == "dungeon" and self.state == "play" and not self.paused
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
        if self.paused or self.show_map:
            return
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
                    label = "Descend"
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
        # day / night light
        r, g, b, a = tint_at(self.time)
        if a > 0:
            self.night.fill((r, g, b, a))
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
            hint = "Floor %d/5  •  E: stairs" % self.dungeon.level if self.dungeon.level < 6 else "Throne Room  •  defeat the Warden"
            self.text_shadow(v, self.font_s, hint, (14, 30), (190, 180, 205))
            if self.banner_t > 0:
                txt = self.font_m.render(self.banner_text, True, (235, 224, 246))
                w = txt.get_width() + 36
                s = pygame.Surface((w, 30), pygame.SRCALPHA)
                pygame.draw.rect(s, (25, 18, 32, 195), s.get_rect(), border_radius=15)
                pygame.draw.rect(s, (148, 122, 168, 230), s.get_rect(), 1, border_radius=15)
                s.blit(txt, (18, 8))
                v.blit(s, ((VIEW_W - w) // 2, 12))
            self.draw_toasts(v)
            self.combat.draw_hud(v, self.font, self.font_s, self.mouse_view())
            self.dialogue.draw(v)
            if self.tele_t > 0:                                  # portal flash
                a = min(255, int(255 * self.tele_t / 1.2))
                flash = pygame.Surface((VIEW_W, VIEW_H))
                flash.fill((235, 215, 255))
                flash.set_alpha(a)
                v.blit(flash, (0, 0))
            return
        # clock / progress
        hh, mm = int(self.time), int((self.time % 1) * 60) // 5 * 5
        self.panel(v, pygame.Rect(6, 6, 118, 36))
        self.text_shadow(v, self.font, f"{hh:02d}:{mm:02d}", (14, 10))
        icon = "Day" if 6.3 < self.time < 19 else "Night"
        self.text_shadow(v, self.font_s, icon, (66, 13), (200, 190, 160))
        self.text_shadow(v, self.font_s, f"Villagers met {self.met_count()}/{len(self.npcs)}", (14, 26), (255, 226, 150))
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
            txt = "WASD move  SHIFT run  SPACE jump  E talk  M map  B music  H help"
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
            self.text_shadow(v, self.font_s, nm, (x + cx, y + cy - 4), center=True)
        for n in self.npcs:
            if n.talk_count > 0:
                pygame.draw.circle(v, (255, 226, 90), (x + int(n.x / T * 3), y + int(n.y / T * 3)), 3)
                pygame.draw.circle(v, (60, 40, 20), (x + int(n.x / T * 3), y + int(n.y / T * 3)), 3, 1)
        px_, py_ = x + int(self.player.x / T * 3), y + int(self.player.y / T * 3)
        pygame.draw.circle(v, (255, 255, 255), (px_, py_), 5)
        pygame.draw.circle(v, (230, 40, 40), (px_, py_), 3)
        self.text_shadow(v, self.font_m, "Hearthmoor & the Whisperwood", (VIEW_W // 2, y - 28), center=True)
        self.text_shadow(v, self.font_s, "Press M to close   -   yellow: villagers you've met   -   purple: dungeon gate",
                         (VIEW_W // 2, y + h + 12), (210, 200, 180), center=True)

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
            elif self.menu_screen == "tutorial_ask":
                draw_ask(self, v)
            else:
                draw_title_screen(self, v)
        else:
            self.draw_ui(v)
            if self.show_map:
                self.draw_map(v)
            if self.paused:
                if self.menu_screen == "controls":
                    draw_controls(self, v)
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
            m = self.current_menu()
            if m and m.hover(self.mouse_view()):
                return self.menu_do(m.key())
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
            if menu_open:
                return self.menu_key(k)
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
                    if not self.dialogue.active and not self.combat.victory_active:
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
