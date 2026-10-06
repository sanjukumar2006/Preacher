"""Procedural world: terrain noise, village layout, roads, forests, decor,
collision grid and a baked ground renderer with soft terrain edges."""
import math
import os
import random

import pygame

T = 32
W = H = 96
CX, CY = 48, 48

GRASS, DARK, SAND, WATER, DEEP, PATH, COBBLE, FARM, DOCK = range(9)
PRIO = {DEEP: 0, WATER: 1, SAND: 2, PATH: 3, COBBLE: 3, FARM: 3, DARK: 4, GRASS: 5, DOCK: -1}

# object table: name -> (footprint w, footprint h) in tiles (blocked, bottom-anchored)
FOOT = {
    "tree_oak": (1, 1), "tree_pine": (1, 1), "tree_autumn": (1, 1), "tree_cherry": (1, 1),
    "bush": (1, 1), "bush_berry": (1, 1), "rock_s": (1, 1), "rock_l": (2, 1), "stump": (1, 1),
    "lamp": (1, 1), "barrel": (1, 1), "crate": (1, 1), "hay": (1, 1), "sign": (1, 1),
    "board": (2, 1), "bench": (2, 1), "scarecrow": (1, 1), "anvil": (1, 1), "campfire": (1, 1),
    "fence_h": (1, 1), "fence_v": (1, 1), "well": (2, 1), "stall_red": (3, 2), "stall_blue": (3, 2),
    "shrine": (3, 2), "tent": (3, 2), "goddess": (2, 1),
}

HOUSES = [  # name, x0, y0, width, display name, door text
    ("house_elder", 39, 37, 5, "Elder Maren's House", "Elder Maren's door is shut. (This demo has no interiors yet.)"),
    ("house_bakery", 53, 37, 4, "Pip's Bakery", "The bakery door is closed. A warm smell of bread drifts out."),
    ("house_inn", 28, 39, 6, "The Sleeping Fox Inn", "The inn is full. Muffled singing comes from the loft. Lark, probably."),
    ("house_herb", 17, 40, 4, "Wren's Cottage", "Bundles of dried herbs hang by the window. The door is locked."),
    ("house_shop", 60, 40, 4, "General Store", "A sign says: 'Back after the next caravan.' The teapot whistles inside."),
    ("house_cottage_a", 68, 41, 4, "Tilly's Home", "Someone is humming inside. The door is closed."),
    ("house_smith", 58, 52, 5, "The Forge", "The forge is banked for the day. Warm air leaks from the door."),
    ("house_cottage_b", 37, 52, 4, "Empty Cottage", "Nobody's home. Curtains are drawn."),
    ("house_farm", 26, 52, 5, "Gil's Farmhouse", "The farmhouse door is shut. Muddy boots rest by the step."),
]

for _h in HOUSES:
    FOOT[_h[0]] = (_h[3], 4)


def _smooth(t):
    return t * t * (3 - 2 * t)


class Noise:
    def __init__(self, seed, size=W + 2):
        r = random.Random(seed)
        self.n = size
        self.g = [[r.random() for _ in range(size)] for _ in range(size)]

    def at(self, x, y):
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        fx, fy = _smooth(x - x0), _smooth(y - y0)
        n = self.n
        a = self.g[y0 % n][x0 % n]
        b = self.g[y0 % n][(x0 + 1) % n]
        c = self.g[(y0 + 1) % n][x0 % n]
        d = self.g[(y0 + 1) % n][(x0 + 1) % n]
        return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy

    def fbm(self, x, y, octaves=4):
        v, amp, tot, f = 0.0, 1.0, 0.0, 1.0
        for _ in range(octaves):
            v += self.at(x * f, y * f) * amp
            tot += amp
            amp *= 0.5
            f *= 2.0
        return v / tot


class World:
    def __init__(self, seed=7):
        self.seed = seed
        self.rng = random.Random(seed)
        self.terrain = [[GRASS] * W for _ in range(H)]
        self.blocked = [[False] * W for _ in range(H)]
        self.occupied = [[False] * W for _ in range(H)]   # no decor / props here
        self.props = []        # dict(kind, tx, ty)
        self.decor = []        # dict(kind, x, y) in pixels (baked, non-blocking)
        self.interact = []     # dict(rect, text, name)
        self.lamps = []        # pixel positions
        self.chimneys = []     # pixel positions
        self.doors = []
        self.tile_variant = [[0] * W for _ in range(H)]
        self._tree_at = {}
        self.generate()

    # ------------------------------------------------------------- terrain
    def generate(self):
        ne = Noise(self.seed)
        nf = Noise(self.seed + 1)
        nm = Noise(self.seed + 2)
        self.nf, self.nm = nf, nm
        rng = self.rng
        elev = [[0.0] * W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                e = ne.fbm(x / 14.0, y / 14.0, 4)
                e = (e - 0.5) * 1.3 + 0.66
                # village clearing pushes terrain up to flat grass
                d = math.hypot(x - CX, (y - CY) * 1.0)
                clear = 1.0 - _smooth(max(0.0, min(1.0, (d - 22) / 9.0)))
                e = e * (1 - clear) + 0.62 * clear
                elev[y][x] = e
        self.elev = elev
        t = self.terrain
        for y in range(H):
            for x in range(W):
                e = elev[y][x]
                if e < 0.30:
                    t[y][x] = DEEP
                elif e < 0.37:
                    t[y][x] = WATER
                elif e < 0.41:
                    t[y][x] = SAND
                else:
                    f = nf.fbm(x / 9.0, y / 9.0, 3)
                    d = math.hypot(x - CX, y - CY)
                    t[y][x] = DARK if (f > 0.56 and d > 30) else GRASS
        # hand-placed lakes with organic, noise-warped shores and a wide sand beach
        nl = Noise(self.seed + 9)
        for (lx, ly, rx, ry) in ((80, 17, 11, 8), (69, 66, 5.6, 4.4), (13, 82, 10, 8), (18, 14, 7, 5),
                                 (89, 62, 5, 9), (62, 86, 9, 5), (10, 52, 4, 7)):
            for y in range(max(0, int(ly - ry * 1.6)), min(H, int(ly + ry * 1.6) + 1)):
                for x in range(max(0, int(lx - rx * 1.6)), min(W, int(lx + rx * 1.6) + 1)):
                    dd = math.hypot((x - lx) / rx, (y - ly) / ry) + (nl.fbm(x / 3.5, y / 3.5, 2) - 0.5) * 0.55
                    if dd < 1.0:
                        t[y][x] = DEEP if dd < 0.55 else WATER
                    elif dd < 1.32 and t[y][x] in (GRASS, DARK):
                        t[y][x] = SAND
        # sand ring around the village pond & ensure shallow border around deep
        for y in range(1, H - 1):
            for x in range(1, W - 1):
                if t[y][x] == DEEP:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if t[y + dy][x + dx] in (SAND, GRASS, DARK):
                            t[y][x] = WATER
                            break
        self.tile_variant = [[rng.randrange(4) for _ in range(W)] for _ in range(H)]
        self.build_village()
        self.build_forest()
        self.scatter_decor()
        self.finish()

    # --------------------------------------------------------------- utils
    def inb(self, x, y):
        return 0 <= x < W and 0 <= y < H

    def set_t(self, x, y, v, force=False):
        if self.inb(x, y):
            if force or self.terrain[y][x] not in (COBBLE, DOCK, FARM):
                self.terrain[y][x] = v

    def free(self, x, y):
        return (self.inb(x, y) and not self.occupied[y][x]
                and self.terrain[y][x] in (GRASS, DARK, SAND, PATH, COBBLE))

    def place(self, kind, tx, ty, block=True, force=False):
        fw, fh = FOOT[kind]
        for yy in range(ty, ty + fh):
            for xx in range(tx, tx + fw):
                if not self.inb(xx, yy):
                    return False
                if not force and (self.occupied[yy][xx] or self.terrain[yy][xx] in (WATER, DEEP, DOCK)):
                    return False
        for yy in range(ty, ty + fh):
            for xx in range(tx, tx + fw):
                self.occupied[yy][xx] = True
                if block:
                    self.blocked[yy][xx] = True
        self.props.append(dict(kind=kind, tx=tx, ty=ty))
        if kind.startswith('tree'):
            self._tree_at[(tx, ty)] = True
        return True

    def paint_disk(self, cx, cy, r, v):
        for yy in range(int(cy - r - 1), int(cy + r + 2)):
            for xx in range(int(cx - r - 1), int(cx + r + 2)):
                if self.inb(xx, yy) and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r + 0.3:
                    if self.terrain[yy][xx] in (WATER, DEEP) and v != DOCK:
                        continue
                    if self.terrain[yy][xx] in (COBBLE, FARM, DOCK) and v == PATH:
                        continue
                    self.terrain[yy][xx] = v

    def road(self, pts, width):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
            for i in range(n + 1):
                tt = i / n
                self.paint_disk(x0 + (x1 - x0) * tt, y0 + (y1 - y0) * tt, width / 2.0, PATH)

    # ------------------------------------------------------------- village
    def build_village(self):
        rng = self.rng
        # main roads with gentle wiggle further out
        def wig(d):
            return math.sin(d * 0.28) * min(2.2, max(0.0, (d - 10) / 8.0))
        north = [(CX + 0.5 + wig(d) * 0.6, CY - d) for d in range(0, 33)]
        south = [(CX + 0.5 + wig(d + 3), CY + d) for d in range(0, 31)]
        west = [(CX - d, CY + 0.5 + wig(d + 1)) for d in range(0, 33)]
        east = [(CX + d, CY + 0.5 + wig(d + 5)) for d in range(0, 24)]
        for pts in (north, south, west, east):
            self.road(pts[:16], 3)
            self.road(pts[15:], 2)
        self.north_end = north[-1]
        self.road([(CX + 23, CY + 0.5 + wig(28)), (73, 44), (76, 40), (78.5, 37.5)], 2)   # trail to camp
        # south lane + the road to the dungeon at the far southern edge
        self.road([(24, 60.5), (62, 60.5)], 2)
        self.road([(61.5, 60.5), (61.5, 66.5)], 2)
        self.road([(48.5, 60.0), (48.5, 88.5)], 2.5)
        # (the stone stairwell at the end of this road is built by build_gate() below)
        # plaza
        for y in range(H):
            for x in range(W):
                if ((x - CX + 0.5) / 7.2) ** 2 + ((y - CY + 0.5) / 5.2) ** 2 <= 1.0:
                    self.terrain[y][x] = COBBLE
        # houses
        for (name, x0, y0, w, label, text) in HOUSES:
            for yy in range(y0, y0 + 4):
                for xx in range(x0 - 0, x0 + w):
                    self.terrain[yy][xx] = GRASS if self.terrain[yy][xx] != PATH else self.terrain[yy][xx]
            self.place(name, x0, y0, force=True)
            door_cx = (x0 + w / 2.0) * T
            by = (y0 + 4) * T
            self.interact.append(dict(rect=pygame.Rect(int(door_cx - 22), by - 14, 44, 30),
                                      text=[text], name=label))
            self.chimneys.append((x0 * T + w * T - 34, y0 * T - 16 + 8))
            # door path: runs south until it meets a road / plaza / lane
            sx = x0 + w // 2 - 1
            for yy in range(y0 + 4, 63):
                hit = yy > y0 + 4 and self.terrain[yy][sx] in (PATH, COBBLE)
                for xx in (sx, sx + 1):
                    self.set_t(xx, yy, PATH)
                if hit:
                    break
            # shrubs next to the door
            for bx in (x0 - 1, x0 + w):
                if rng.random() < 0.9:
                    self.place(rng.choice(("bush", "bush_berry")), bx, y0 + 3, force=False)
            # flowers along the wall base
            for fx in range(x0, x0 + w):
                if (fx not in (sx, sx + 1)) and rng.random() < 0.8:
                    self.add_decor(rng.choice(("flower_red", "flower_yellow", "flower_white", "flower_pink", "flower_blue")),
                                   fx * T + rng.randint(2, 14), (y0 + 4) * T + rng.randint(6, 20))
        # plaza furniture
        self.place("well", 47, 48)
        self.interact.append(dict(rect=pygame.Rect(46 * T, 48 * T - 6, 4 * T, 52), name="Village Well",
                                  text=["An old stone well. The water is cold and clear.",
                                        "Your reflection looks back: a traveler with a hopeful face."]))
        self.place("stall_red", 51, 44)
        self.place("stall_blue", 43, 44)
        self.interact.append(dict(rect=pygame.Rect(51 * T, 46 * T - 6, 96, 44), name="Fruit & Bread Stall",
                                  text=["Apples, rolls and honey cakes are piled high. The stall owner seems to be nearby."]))
        self.interact.append(dict(rect=pygame.Rect(43 * T, 46 * T - 6, 96, 44), name="Vegetable Stall",
                                  text=["Crates of cabbages, carrots and pumpkins from Gil's farm."]))
        self.place("board", 44, 52)
        self.interact.append(dict(rect=pygame.Rect(44 * T - 6, 53 * T - 6, 76, 40), name="Notice Board",
                                  text=["HARVEST FESTIVAL: coming soon! Bring pumpkins.",
                                        "LOST: one brown hen named Duchess. Reward: eggs.",
                                        "WANTED: someone to teach Lark a second song."]))
        self.place("bench", 51, 52)
        self.place("bench", 44, 41)
        for lx, ly in ((46, 43), (50, 43), (46, 53), (50, 53), (46, 34), (50, 34), (46, 26), (50, 26),
                       (36, 46), (36, 50), (58, 46), (58, 50), (68, 46), (28, 46), (50, 58), (46, 58)):
            if self.place("lamp", lx, ly):
                self.lamps.append((lx * T + 16, ly * T - 10))
        # signposts
        for sx2, sy2, txt in ((46, 46, ["North: Whispering Shrine", "East: Hunter's Camp", "South: Gil's Farm & Reedwater Pond", "West: Wren's Cottage"]),
                              (49, 30, ["Whispering Shrine ahead.", "Please keep the humming to a minimum."]),
                              (24, 50, ["Westwood Trail: beyond lies the Whisperwood."]),
                              (74, 49, ["East Trail: Hunter's Camp. Knock before entering the tent."])):
            if self.place("sign", sx2, sy2):
                self.interact.append(dict(rect=pygame.Rect(sx2 * T - 8, sy2 * T - 6, 48, 44), name="Signpost", text=txt))
        # farm
        for yy in range(63, 73):
            for xx in range(23, 36):
                self.terrain[yy][xx] = FARM
                self.occupied[yy][xx] = True
        for xx in range(22, 37):
            for yy in (62, 73):
                if not (yy == 62 and xx in (28, 29)):
                    self.place("fence_h", xx, yy)
                else:
                    self.terrain[yy][xx] = PATH
        for yy in range(63, 73):
            for xx in (22, 36):
                self.place("fence_v", xx, yy)
        crops = ["crop_wheat", "crop_wheat", "crop_cabbage", "crop_carrot", "crop_pumpkin"]
        for yy in range(63, 73):
            for xx in range(23, 36):
                if xx in (28, 29) and yy in range(63, 66):
                    continue
                k = crops[((xx - 23) // 3 + (yy - 63) // 5 * 2) % len(crops)]
                if (xx, yy) in ((29, 67),):
                    continue
                self.add_decor(k, xx * T, yy * T)
        self.place("scarecrow", 29, 67)
        self.interact.append(dict(rect=pygame.Rect(28 * T, 67 * T - 6, 64, 40), name="Scarecrow",
                                  text=["The scarecrow stares back. You swear it just tilted its head."]))
        self.place("hay", 34, 64)
        self.place("hay", 24, 71)
        self.place("barrel", 35, 71)
        self.place("crate", 37, 62)
        self.place("barrel", 37, 63)
        # smithy yard
        self.place("anvil", 56, 56)
        self.interact.append(dict(rect=pygame.Rect(55 * T, 56 * T - 6, 64, 40), name="Anvil",
                                  text=["A heavy anvil, scarred by a thousand hammer-strikes. Still warm."]))
        self.place("barrel", 63, 54)
        self.place("barrel", 64, 54)
        self.place("crate", 63, 55)
        # inn & shop clutter
        self.place("barrel", 34, 42)
        self.place("barrel", 27, 42)
        self.place("crate", 64, 43)
        self.place("barrel", 65, 43)
        self.place("bench", 35, 44)
        # pond + dock
        for xx in range(62, 68):
            self.terrain[66][xx] = DOCK
        # shrine & camp clearings
        self.paint_disk(48, 14, 6, GRASS)
        self.paint_disk(78, 35, 5, GRASS)
        lx, ly = self.north_end
        self.road([(lx, ly), (48.5, 19), (48.5, 16.5)], 2)
        self.road([(76, 40), (78.5, 37.5), (78.5, 36.5)], 2)
        self.place("shrine", 47, 14)
        self.interact.append(dict(rect=pygame.Rect(46 * T, 15 * T - 4, 5 * T, 60), name="Whispering Shrine",
                                  text=["An ancient shrine hums softly. The orb glows teal, pulsing like a slow heartbeat.",
                                        "Runes are carved around the arch. You can't read them, but they feel friendly."]))
        self.place("lamp", 46, 16)
        self.lamps.append((46 * T + 16, 16 * T - 10))
        self.place("lamp", 50, 16)
        self.lamps.append((50 * T + 16, 16 * T - 10))
        self.place("tent", 75, 32)
        self.interact.append(dict(rect=pygame.Rect(75 * T, 34 * T - 4, 96, 40), name="Hunter's Tent",
                                  text=["A canvas tent patched many times over. A fur blanket is rolled up inside."]))
        self.place("campfire", 79, 35, block=True)
        self.interact.append(dict(rect=pygame.Rect(78 * T - 6, 35 * T - 4, 44, 44), name="Campfire",
                                  text=["The campfire crackles. It smells of pine and woodsmoke."]))
        self.place("stump", 81, 35)
        self.place("stump", 77, 38)
        self.place("barrel", 74, 36)
        # cherry trees around the village
        for (tx, ty) in ((34, 49), (41, 58), (55, 58), (65, 50), (52, 34), (43, 34), (71, 58), (31, 57),
                         (38, 46), (59, 47), (22, 46), (56, 49), (66, 44), (24, 58), (44, 56)):
            self.place("tree_cherry", tx, ty)
        for (tx, ty) in ((24, 44), (35, 36), (33, 58), (63, 36), (70, 52), (66, 56)):
            self.place(rng.choice(("tree_oak", "tree_oak", "tree_autumn")), tx, ty)
        self.build_gate()

    # ---------------------------------------------------------------- gate
    def build_gate(self):
        """The Hollow Gate at the end of the south road: flagstone forecourt, sunken stairwell,
        two braziers and some clutter.  Art is painted by gate.py; this only sets up the map data."""
        # props first (place() refuses occupied tiles), then claim the whole forecourt
        self.place("sign", 45, 85)
        self.interact.append(dict(rect=pygame.Rect(45 * T - 8, 85 * T - 6, 48, 44), name="Warning Sign",
                                  text=["DANGER: THE HOLLOW BELOW.",
                                        "Five floors of stone, shadow and teeth. Those who descend rarely climb back up.",
                                        "Bring a sword. Bring courage. Bring a very good reason."]))
        for kind, tx, ty in (("barrel", 44, 88), ("crate", 44, 89), ("barrel", 52, 89), ("crate", 52, 88),
                             ("rock_l", 43, 92), ("rock_s", 53, 91), ("bush", 44, 84), ("bush_berry", 52, 83)):
            self.place(kind, tx, ty)
        # flagstone forecourt (rounded) - the road runs straight into it
        for y in range(81, 95):
            for x in range(42, 56):
                e = ((x + 0.5 - 49.0) / 4.3) ** 2 + ((y + 0.5 - 87.0) / 5.3) ** 2
                if e <= 1.0 and self.terrain[y][x] not in (WATER, DEEP, DOCK):
                    self.terrain[y][x] = COBBLE
                    self.occupied[y][x] = True
        # stairwell (x 47..50) + side walls (46, 51) + back wall (row 90) are solid
        for y in range(87, 91):
            for x in range(46, 52):
                self.blocked[y][x] = True
                self.occupied[y][x] = True
        # the two brazier pillars on row 86
        for x in (46, 51):
            self.blocked[86][x] = True
            self.occupied[86][x] = True
        for x in (47, 48, 49, 50):
            self.occupied[86][x] = True
        # brazier light for the night pass
        for x in (46, 51):
            self.lamps.append((x * T + 16, 87 * T - 98))
        # Goddess statue west of the forecourt: a small flagstone plaza joined to the gate courtyard.
        for y in range(84, 88):
            for x in range(40, 45):
                if ((x + 0.5 - 42.5) / 2.9) ** 2 + ((y + 0.5 - 85.8) / 2.3) ** 2 <= 1.0 \
                        and not self.occupied[y][x] and self.terrain[y][x] not in (WATER, DEEP, DOCK):
                    self.terrain[y][x] = COBBLE
                    self.occupied[y][x] = True
        for x in (43, 44):                                   # little walkway into the forecourt
            self.terrain[86][x] = COBBLE
            self.occupied[86][x] = True
        self.place("goddess", 41, 84, force=True)
        self.goddess = (41, 84)                              # tile of the statue's left foot (used by main.py)
        self.interact.append(dict(rect=pygame.Rect(40 * T, 82 * T, 4 * T, 5 * T), id="goddess",
                                  name="Goddess Statue", text=[]))
        # E prompt: anywhere on the landing / just in front of it
        self.interact.append(dict(rect=pygame.Rect(46 * T, 85 * T, 6 * T, 4 * T), id="dungeon", name="The Hollow Below",
                                  text=["A stone stairwell sinks into the dark."]))

    # -------------------------------------------------------------- forest
    def build_forest(self):
        rng = self.rng
        nf = self.nf
        pine_noise = Noise(self.seed + 5)
        for y in range(H):
            for x in range(W):
                if self.terrain[y][x] not in (GRASS, DARK) or self.occupied[y][x]:
                    continue
                d = math.hypot(x - CX, y - CY)
                edge = min(x, y, W - 1 - x, H - 1 - y)
                f = nf.fbm(x / 8.0, y / 8.0, 3)
                if edge <= 2:
                    dens = 1.0
                else:
                    dens = max(0.0, (f - 0.38) * 2.2) * min(1.0, max(0.0, (d - 26) / 6.0))
                    if edge < 8:
                        dens = max(dens, 0.55 + (8 - edge) * 0.05)
                if rng.random() < dens:
                    if self.tree_near(x, y):
                        continue
                    pn = pine_noise.fbm(x / 10.0, y / 10.0, 2)
                    if self.terrain[y][x] == DARK or pn > 0.55:
                        kind = "tree_pine" if rng.random() < 0.75 else "tree_oak"
                    else:
                        kind = rng.choice(("tree_oak", "tree_oak", "tree_oak", "tree_autumn", "tree_pine"))
                    self.place(kind, x, y)
        # bushes, rocks, stumps scattered
        for y in range(3, H - 3):
            for x in range(3, W - 3):
                if not self.free(x, y) or self.terrain[y][x] in (PATH, COBBLE):
                    continue
                d = math.hypot(x - CX, y - CY)
                r = rng.random()
                if d > 14:
                    if r < 0.012:
                        self.place("bush_berry" if rng.random() < 0.3 else "bush", x, y)
                    elif r < 0.018:
                        self.place("rock_s", x, y)
                    elif r < 0.020 and x + 1 < W:
                        self.place("rock_l", x, y)
                    elif r < 0.023:
                        self.place("stump", x, y)
                elif d > 8 and r < 0.004:
                    self.place("bush", x, y)

    def tree_near(self, x, y):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                xx, yy = x + dx, y + dy
                if (dx or dy) and self.inb(xx, yy) and self._tree_at.get((xx, yy)):
                    return True
        return False

    # ------------------------------------------------------------- scatter
    def add_decor(self, kind, x, y):
        self.decor.append(dict(kind=kind, x=int(x), y=int(y)))

    def scatter_decor(self):
        rng = self.rng
        nm = self.nm
        for y in range(H):
            for x in range(W):
                t = self.terrain[y][x]
                if self.occupied[y][x]:
                    continue
                d = math.hypot(x - CX, y - CY)
                px_, py_ = x * T, y * T
                if t in (GRASS, DARK):
                    m = nm.fbm(x / 5.0, y / 5.0, 2)
                    if rng.random() < 0.20:
                        self.add_decor(f"tuft_{rng.randrange(3)}", px_ + rng.randint(0, 16), py_ + rng.randint(4, 20))
                    # flower meadows
                    meadow = m > 0.56
                    pf = 0.28 if meadow else (0.05 if d < 26 else 0.015)
                    if t == GRASS and rng.random() < pf:
                        col = ("red", "yellow", "white", "blue", "pink", "purple")[int(nm.fbm(x / 3.0 + 9, y / 3.0, 2) * 6) % 6] \
                            if meadow else rng.choice(("red", "yellow", "white", "blue", "pink", "purple"))
                        self.add_decor(f"flower_{col}", px_ + rng.randint(0, 14), py_ + rng.randint(2, 16))
                    if t == DARK and rng.random() < 0.035:
                        self.add_decor("mushroom", px_ + rng.randint(2, 16), py_ + rng.randint(6, 18))
                elif t == SAND and rng.random() < 0.05:
                    self.add_decor("pebbles", px_ + rng.randint(2, 18), py_ + rng.randint(6, 20))
                elif t == PATH and rng.random() < 0.04:
                    self.add_decor("pebbles", px_ + rng.randint(2, 18), py_ + rng.randint(6, 20))

    def finish(self):
        # block water and the outer rim
        for y in range(H):
            for x in range(W):
                if self.terrain[y][x] in (WATER, DEEP):
                    self.blocked[y][x] = True
                if x < 1 or y < 1 or x >= W - 1 or y >= H - 1:
                    self.blocked[y][x] = True

    # ---------------------------------------------------------- collision
    def rect_blocked(self, r):
        x0, x1 = int(r.left // T), int((r.right - 1) // T)
        y0, y1 = int(r.top // T), int((r.bottom - 1) // T)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if not self.inb(xx, yy) or self.blocked[yy][xx]:
                    return True
        return False

    def nearest_walkable(self, x, y):
        for r in range(0, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and self.walkable_tile(x + dx, y + dy):
                        return x + dx, y + dy
        return x, y

    def walkable_tile(self, x, y):
        return self.inb(x, y) and not self.blocked[y][x]


# ---------------------------------------------------------------- baking
class Baked:
    """Pre-renders the static ground (with soft edges) into one big surface."""

    def __init__(self, world, assets):
        self.w = world
        self.a = assets
        self.ground = pygame.Surface((W * T, H * T)).convert()
        self.shore = {}   # (tx,ty) -> list of surfaces drawn over animated water
        self.water_tiles = []
        self.bake()

    def tex(self, t, x, y):
        a = self.a
        v = self.w.tile_variant[y][x]
        if t == GRASS:
            return a["tiles"][f"grass_{v}"]
        if t == DARK:
            return a["tiles"][f"dark_{v % 3}"]
        if t == SAND:
            return a["tiles"][f"sand_{v % 2}"]
        if t == PATH:
            return a["tiles"][f"dirt_{v % 3}"]
        if t == COBBLE:
            return a["tiles"][f"cobble_{(v + x + y) % 2}"]
        if t == FARM:
            return a["tiles"][f"farm_{v % 2}"]
        if t == DOCK:
            return a["tiles"][f"dock_{v % 2}"]
        if t == WATER:
            return a["tiles"]["water_0_0"]
        return a["tiles"]["deep_0_0"]

    def strip(self, tex, side, rnd, line):
        s = pygame.Surface((T, T), pygame.SRCALPHA)
        d = rnd.randint(5, 8)
        for i in range(T):
            d = max(3, min(10, d + rnd.choice((-1, 0, 0, 1))))
            if side == "N":
                s.blit(tex, (i, 0), (i, 0, 1, d))
                if line and d < T:
                    s.set_at((i, d), line)
            elif side == "S":
                s.blit(tex, (i, T - d), (i, T - d, 1, d))
                if line:
                    s.set_at((i, T - d - 1), line)
            elif side == "W":
                s.blit(tex, (0, i), (0, i, d, 1))
                if line:
                    s.set_at((d, i), line)
            else:
                s.blit(tex, (T - d, i), (T - d, i, d, 1))
                if line:
                    s.set_at((T - d - 1, i), line)
        return s

    def bake(self):
        w = self.w
        g = self.ground
        t = w.terrain
        for y in range(H):
            for x in range(W):
                g.blit(self.tex(t[y][x], x, y), (x * T, y * T))
                if t[y][x] in (WATER, DEEP):
                    self.water_tiles.append((x, y))
        lines = {GRASS: (66, 118, 52, 255), DARK: (46, 96, 46, 255), SAND: None, PATH: (150, 116, 80, 255)}
        for y in range(H):
            for x in range(W):
                tt = t[y][x]
                if tt == DOCK:
                    continue
                for side, dx, dy in (("N", 0, -1), ("S", 0, 1), ("W", -1, 0), ("E", 1, 0)):
                    nx, ny = x + dx, y + dy
                    if not w.inb(nx, ny):
                        continue
                    nt = t[ny][nx]
                    if PRIO[nt] > PRIO[tt] and PRIO[nt] >= 0 and not (nt == DARK and tt == PATH):
                        rnd = random.Random(x * 7919 + y * 104729 + dx * 3 + dy * 5)
                        if tt in (WATER, DEEP):
                            line = (250, 252, 255, 200) if nt == SAND else ((140, 200, 236, 255) if nt == WATER else None)
                        else:
                            line = lines.get(nt)
                        st = self.strip(self.tex(nt, nx, ny), side, rnd, line)
                        if tt in (WATER, DEEP):
                            self.shore.setdefault((x, y), []).append(st)
                        else:
                            g.blit(st, (x * T, y * T))
        # decor baked on top
        for d in w.decor:
            img = self.a["decor"][d["kind"]]
            if d["kind"].startswith("crop"):
                g.blit(img, (d["x"], d["y"]))
            else:
                g.blit(img, (d["x"], d["y"]))
        # soft vignette dirt under doors etc not needed
