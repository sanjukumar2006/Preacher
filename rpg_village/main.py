
"""Hearthmoor - a tiny open-world village RPG made with pygame.

Controls
  WASD / Arrow keys  move          SHIFT  run
  E / SPACE / ENTER  talk / interact / continue dialogue
  M  world map       N  skip an hour of time      H  help
  F11  fullscreen    ESC  pause
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
    def __init__(self, seed=7, skip_title=False):
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
            for n in ("blip", "talk", "bye"):
                self.sfx[n] = pygame.mixer.Sound(os.path.join(ASSETS, "sfx", n + ".wav"))
        except Exception:
            pass
        self.font = pygame.font.Font(None, 20)
        self.font_s = pygame.font.Font(None, 16)
        self.font_m = pygame.font.Font(None, 24)
        self.font_b = pygame.font.Font(None, 76)

        print("Generating village terrain...")
        self.world = World(seed)
        self.baked = Baked(self.world, self.a)
        self.build_props()
        self.shadow = pygame.Surface((22, 9), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow, (0, 0, 0, 70), (0, 0, 22, 9))

        # actors
        hx, hy = self.world.nearest_walkable(48, 51)
        self.player = Player(hx * T + 16, hy * T + 28, self.a["characters"]["hero"])
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
        self.mini = m
        self.mini_small = m
        self.mini_big = pygame.transform.scale(m, (W.W * 3, W.H * 3))

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

    def play(self, name):
        s = self.sfx.get(name)
        if s:
            s.play()

    def toast(self, text, dur=3.5):
        self.toasts.append([text, dur])

    def met_count(self):
        return sum(1 for n in self.npcs if n.talk_count > 0)

    def update_place(self, first=False):
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
        if self.state == "title":
            self.cam = [self.cam[0], self.cam[1]]
            for n in self.npcs:
                n.update(dt, self.world, [self.player.foot])
            for a in self.animals:
                a.update(dt, self.world)
            return
        if self.paused or self.show_map:
            return
        talking = self.dialogue.active
        self.dialogue.update(dt, self.sfx.get("blip"))
        npc_rects = [n.foot for n in self.npcs]
        if not talking:
            self.player.update(dt, keys, self.world, npc_rects)
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
        cf = int(self.t * 6) % 2
        for _, kind, o in items:
            if kind == 0:
                img = o[1] if o[1] is not None else self.a["objects"][f"campfire_{cf}"]
                v.blit(img, (o[2] - cam[0], o[3] - cam[1]))
            else:
                o.draw(v, cam, self.shadow)
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

    def draw_ui(self, v):
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
        # toasts
        for i, (t, d) in enumerate(self.toasts[-3:]):
            img = self.font.render(t, True, (255, 246, 226))
            w = img.get_width() + 20
            s = pygame.Surface((w, 24), pygame.SRCALPHA)
            pygame.draw.rect(s, (60, 100, 70, 200), s.get_rect(), border_radius=8)
            pygame.draw.rect(s, (190, 230, 180, 230), s.get_rect(), 1, border_radius=8)
            s.blit(img, (10, 5))
            s.set_alpha(int(255 * min(1, d / 0.6)))
            v.blit(s, ((VIEW_W - w) // 2, 52 + i * 28))
        self.dialogue.draw(v)
        if self.help_t > 0 and not self.dialogue.active:
            a = min(1.0, self.help_t / 2)
            txt = "WASD move   SHIFT run   E talk   M map   N skip time   H help"
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
            self.text_shadow(v, self.font_s, nm, (x + cx, y + cy - 4), center=True)
        for n in self.npcs:
            if n.talk_count > 0:
                pygame.draw.circle(v, (255, 226, 90), (x + int(n.x / T * 3), y + int(n.y / T * 3)), 3)
                pygame.draw.circle(v, (60, 40, 20), (x + int(n.x / T * 3), y + int(n.y / T * 3)), 3, 1)
        px_, py_ = x + int(self.player.x / T * 3), y + int(self.player.y / T * 3)
        pygame.draw.circle(v, (255, 255, 255), (px_, py_), 5)
        pygame.draw.circle(v, (230, 40, 40), (px_, py_), 3)
        self.text_shadow(v, self.font_m, "Hearthmoor & the Whisperwood", (VIEW_W // 2, y - 28), center=True)
        self.text_shadow(v, self.font_s, "Press M to close  -  yellow dots: villagers you've met",
                         (VIEW_W // 2, y + h + 12), (210, 200, 180), center=True)

    def draw_title(self, v):
        dim = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        dim.fill((14, 10, 24, 120))
        v.blit(dim, (0, 0))
        bob = math.sin(self.t * 1.6) * 3
        self.text_shadow(v, self.font_b, "HEARTHMOOR", (VIEW_W // 2, 62 + bob), (255, 226, 150), (70, 36, 24), True)
        self.text_shadow(v, self.font_m, "A tiny open-world village adventure", (VIEW_W // 2, 128), (255, 246, 226), (40, 24, 20), True)
        self.panel(v, pygame.Rect(VIEW_W // 2 - 170, 176, 340, 96), 190)
        lines = ["WASD / Arrows .... move       SHIFT .... run", "E / Space / Enter .... talk & interact",
                 "M .... world map        N .... skip time", "F11 .... fullscreen       ESC .... pause"]
        for i, l in enumerate(lines):
            self.text_shadow(v, self.font, l, (VIEW_W // 2, 186 + i * 20), center=True)
        if int(self.t * 2) % 2 == 0:
            self.text_shadow(v, self.font_m, "Press ENTER to begin", (VIEW_W // 2, 300), (255, 255, 255), (40, 24, 20), True)

    def draw(self):
        v = self.view
        self.draw_world(v)
        if self.state == "title":
            self.draw_title(v)
        else:
            self.draw_ui(v)
            if self.show_map:
                self.draw_map(v)
            if self.paused:
                dim = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
                dim.fill((10, 8, 8, 170))
                v.blit(dim, (0, 0))
                self.text_shadow(v, self.font_b, "PAUSED", (VIEW_W // 2, 120), (255, 226, 150), (70, 36, 24), True)
                self.text_shadow(v, self.font_m, "ESC resume      Q quit", (VIEW_W // 2, 200), center=True)
        self.screen.blit(v, (0, 0)) if self.screen.get_size() == v.get_size() else \
            self.screen.blit(pygame.transform.scale(v, self.screen.get_size()), (0, 0))
        pygame.display.flip()

    # -------------------------------------------------------------- loop
    def handle(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            if self.state == "title":
                if k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e, pygame.K_KP_ENTER):
                    self.state = "play"
                    self.play("talk")
                    self.banner_t = 3.2
                elif k == pygame.K_ESCAPE:
                    return False
                return True
            if self.paused:
                if k == pygame.K_ESCAPE:
                    self.paused = False
                elif k == pygame.K_q:
                    return False
                return True
            if k == pygame.K_ESCAPE:
                if self.show_map:
                    self.show_map = False
                elif self.dialogue.active:
                    self.dialogue.active = False
                    for n in self.npcs:
                        n.talking = False
                else:
                    self.paused = True
            elif k == pygame.K_m:
                self.show_map = not self.show_map
            elif k == pygame.K_h:
                self.help_t = 0 if self.help_t > 0 else 12
            elif k == pygame.K_n and not self.dialogue.active:
                self.time = (self.time + 1) % 24
                self.toast("Time passes...", 1.5)
            elif k in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER) and not self.show_map:
                if self.dialogue.active:
                    self.dialogue.advance()
                else:
                    self.interact()
        return True

    def run(self, frames=None):
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
        pygame.quit()


def main():
    ap = argparse.ArgumentParser(description="Hearthmoor village RPG")
    ap.add_argument("--seed", type=int, default=7, help="terrain seed (default 7)")
    ap.add_argument("--skip-title", action="store_true")
    ap.add_argument("--regen-assets", action="store_true", help="re-create all art before starting")
    args = ap.parse_args()
    if args.regen_assets:
        import generate_assets
        generate_assets.main()
    Game(seed=args.seed, skip_title=args.skip_title).run()


if __name__ == "__main__":
    main()
