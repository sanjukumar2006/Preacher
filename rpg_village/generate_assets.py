#!/usr/bin/env python3
"""Generates every PNG / WAV asset used by the game into ./assets.
Run:  python generate_assets.py
(The game also runs this automatically if the assets folder is missing.)"""
import math
import os
import random
import struct
import wave

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

from data import NPCS, HERO, HERO_SPRITE, SPRITES

pygame.init()
pygame.font.init()

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
T = 32


# ----------------------------------------------------------------- helpers
def S(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def save(surf, sub, name):
    d = os.path.join(ASSETS, sub)
    os.makedirs(d, exist_ok=True)
    pygame.image.save(surf, os.path.join(d, name + ".png"))


def sh(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def R(s, c, x, y, w, h):
    s.fill(c, (x, y, w, h))


def px(s, x, y, c):
    if 0 <= x < s.get_width() and 0 <= y < s.get_height():
        s.set_at((x, y), c)


def shadow(s, cx, cy, w, h, a=70):
    t = S(s.get_width(), s.get_height())
    pygame.draw.ellipse(t, (0, 0, 0, a), (cx - w // 2, cy - h // 2, w, h))
    s.blit(t, (0, 0))


def outline(s, color=(38, 26, 30)):
    """Adds a 1px outline around opaque pixels (returns a surface 2px larger)."""
    w, h = s.get_size()
    out = S(w + 2, h + 2)
    out.blit(s, (1, 1))
    src = out.copy()
    for y in range(h + 2):
        for x in range(w + 2):
            if src.get_at((x, y))[3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w + 2 and 0 <= ny < h + 2 and src.get_at((nx, ny))[3] > 200:
                        out.set_at((x, y), color)
                        break
    return out


def scale(s, k):
    return pygame.transform.scale(s, (s.get_width() * k, s.get_height() * k))


# ------------------------------------------------------------------- tiles
def t_grass(seed, base=(98, 164, 72), dark=(82, 146, 62), light=(120, 184, 88)):
    r = random.Random(seed)
    s = S(T, T)
    s.fill(base)
    for _ in range(46):
        px(s, r.randrange(T), r.randrange(T), r.choice((dark, light)))
    for _ in range(9):
        x, y = r.randrange(T), r.randrange(2, T)
        c = r.choice((light, dark))
        px(s, x, y, c)
        px(s, x, y - 1, c)
        px(s, x + 1, y - 2, sh(c, 1.1))
    return s


def t_dirt(seed):
    r = random.Random(seed)
    s = S(T, T)
    s.fill((184, 148, 102))
    for _ in range(60):
        px(s, r.randrange(T), r.randrange(T), r.choice(((168, 132, 90), (198, 164, 118), (152, 118, 80))))
    for _ in range(4):
        x, y = r.randrange(T - 2), r.randrange(T - 1)
        R(s, (150, 140, 132), x, y, 2, 1)
        R(s, (190, 182, 172), x, y - 1 if y else y, 1, 1)
    return s


def t_cobble(seed):
    r = random.Random(seed)
    s = S(T, T)
    s.fill((96, 90, 98))
    rows = [[10, 12, 10], [8, 12, 12], [12, 10, 10], [10, 10, 12]]
    for ri in range(4):
        x = 0
        for w in rows[(ri + seed) % 4]:
            g = r.randint(146, 176)
            c = (g, g - 4, g + 4)
            R(s, c, x + 1, ri * 8 + 1, w - 1, 6)
            R(s, sh(c, 1.14), x + 1, ri * 8 + 1, w - 1, 1)
            R(s, sh(c, 0.84), x + 1, ri * 8 + 6, w - 1, 1)
            for _ in range(2):
                px(s, x + 1 + r.randrange(w - 1), ri * 8 + 2 + r.randrange(4), sh(c, 0.92))
            x += w
    return s


def t_sand(seed):
    r = random.Random(seed)
    s = S(T, T)
    s.fill((232, 212, 156))
    for _ in range(60):
        px(s, r.randrange(T), r.randrange(T), r.choice(((218, 196, 140), (244, 228, 176), (204, 180, 124))))
    return s


def t_farm(seed):
    s = S(T, T)
    s.fill((120, 84, 52))
    r = random.Random(seed)
    for y in (3, 11, 19, 27):
        R(s, (138, 98, 62), 0, y, T, 2)
        R(s, (88, 58, 36), 0, y + 2, T, 2)
    for _ in range(26):
        px(s, r.randrange(T), r.randrange(T), r.choice(((100, 68, 42), (140, 100, 64))))
    return s


def t_dock(seed):
    s = S(T, T)
    r = random.Random(seed)
    for i in range(4):
        g = r.randint(0, 14)
        c = (168 + g, 120 + g, 72 + g)
        R(s, c, i * 8, 0, 7, T)
        R(s, sh(c, 1.12), i * 8, 0, 7, 1)
        R(s, sh(c, 0.78), i * 8 + 7, 0, 1, T)
        for _ in range(4):
            px(s, i * 8 + r.randrange(1, 6), r.randrange(T), sh(c, 0.85))
        px(s, i * 8 + 2, 2, (70, 50, 36))
        px(s, i * 8 + 2, 29, (70, 50, 36))
    R(s, (96, 66, 42), 0, 0, T, 2)
    R(s, (96, 66, 42), 0, T - 3, T, 3)
    return s


def t_water(base, hi, variant, frame):
    r = random.Random(variant * 100 + 11)
    s = S(T, T)
    s.fill(base)
    for _ in range(5):
        x0, y, ln = r.randrange(T), r.randrange(2, T - 2), r.randint(5, 9)
        x = (x0 + frame * 8) % T
        dy = int(round(math.sin((frame / 4.0) * 2 * math.pi + x0)))
        for xx in (x, x - T):
            R(s, hi, xx, y + dy, ln, 1)
            R(s, sh(base, 0.9), xx + 1, y + dy + 1, ln - 2, 1)
    r2 = random.Random(variant * 31 + frame * 7)
    for _ in range(2):
        px(s, r2.randrange(T), r2.randrange(T), (232, 246, 255))
    return s


def make_tiles():
    for i in range(4):
        save(t_grass(i), "tiles", f"grass_{i}")
    for i in range(3):
        save(t_grass(40 + i, (66, 128, 62), (54, 110, 52), (82, 148, 74)), "tiles", f"dark_{i}")
        save(t_dirt(i), "tiles", f"dirt_{i}")
    for i in range(2):
        save(t_cobble(i), "tiles", f"cobble_{i}")
        save(t_sand(i), "tiles", f"sand_{i}")
        save(t_farm(i), "tiles", f"farm_{i}")
        save(t_dock(i), "tiles", f"dock_{i}")
    for v in range(2):
        for f in range(4):
            save(t_water((70, 150, 214), (150, 212, 244), v, f), "tiles", f"water_{v}_{f}")
            save(t_water((46, 112, 184), (96, 160, 220), v + 2, f), "tiles", f"deep_{v}_{f}")


# ------------------------------------------------------------------- decor
def flower(color, center=(255, 232, 110)):
    s = S(16, 14)
    for (x, y) in ((3, 8), (9, 5), (7, 11)):
        R(s, (60, 130, 56), x, y + 1, 1, 3)
        R(s, color, x - 1, y, 3, 1)
        R(s, color, x, y - 1, 1, 3)
        px(s, x, y, center)
    return s


def make_decor():
    cols = {"red": (220, 70, 70), "yellow": (250, 214, 70), "white": (248, 248, 248),
            "blue": (96, 140, 235), "pink": (244, 140, 190), "purple": (170, 110, 220)}
    for n, c in cols.items():
        save(flower(c, (255, 232, 110) if n != "yellow" else (240, 140, 40)), "decor", f"flower_{n}")
    for i in range(3):
        r = random.Random(i)
        s = S(16, 12)
        for k in range(6):
            x = 2 + k * 2 + r.randint(0, 1)
            h = r.randint(4, 8)
            c = r.choice(((70, 140, 60), (90, 164, 74), (60, 124, 54)))
            R(s, c, x, 11 - h, 1, h)
            px(s, x + 1, 11 - h + 1, sh(c, 1.15))
        save(s, "decor", f"tuft_{i}")
    s = S(14, 12)
    for (x, y, cc) in ((2, 5, (214, 70, 60)), (8, 3, (240, 224, 200))):
        R(s, (240, 232, 216), x + 1, y + 3, 2, 4)
        R(s, cc, x - 1, y, 6, 3)
        R(s, sh(cc, 0.8), x - 1, y + 2, 6, 1)
        px(s, x + 1, y + 1, (255, 255, 255))
    save(s, "decor", "mushroom")
    s = S(12, 8)
    for (x, y, w) in ((1, 4, 4), (6, 2, 3), (7, 5, 3)):
        R(s, (150, 146, 150), x, y, w, 2)
        R(s, (190, 186, 190), x, y, w, 1)
    save(s, "decor", "pebbles")
    # crops (full tile, drawn over farm soil)
    s = S(T, T)
    for x in range(3, 30, 6):
        for y in (4, 14, 24):
            R(s, (214, 178, 70), x, y, 2, 7)
            R(s, (240, 210, 100), x - 1, y - 2, 4, 3)
            px(s, x, y - 3, (250, 230, 130))
            R(s, (90, 150, 60), x + 2, y + 4, 1, 3)
    save(s, "decor", "crop_wheat")
    s = S(T, T)
    for (x, y) in ((4, 4), (18, 4), (4, 17), (18, 17)):
        pygame.draw.circle(s, (86, 160, 70), (x + 5, y + 5), 6)
        pygame.draw.circle(s, (130, 200, 100), (x + 4, y + 4), 4)
        pygame.draw.circle(s, (190, 230, 150), (x + 3, y + 3), 2)
    save(s, "decor", "crop_cabbage")
    s = S(T, T)
    for x in range(4, 30, 8):
        for y in (4, 15, 25):
            R(s, (70, 150, 60), x, y, 1, 4)
            R(s, (90, 176, 70), x + 2, y - 1, 1, 5)
            R(s, (60, 130, 54), x - 2, y, 1, 4)
            R(s, (240, 130, 40), x, y + 4, 3, 2)
    save(s, "decor", "crop_carrot")
    s = S(T, T)
    for (x, y) in ((6, 6), (20, 8), (8, 20), (21, 21)):
        pygame.draw.ellipse(s, (226, 120, 30), (x, y, 10, 8))
        pygame.draw.ellipse(s, (246, 150, 50), (x + 1, y + 1, 5, 5))
        R(s, (60, 130, 50), x + 4, y - 2, 2, 3)
    save(s, "decor", "crop_pumpkin")


# ----------------------------------------------------------------- objects
def blob_tree(pal, trunk, name, cherry=False):
    W, H = 64, 96
    s = S(W, H)
    shadow(s, 32, H - 6, 46, 14)
    base = H - 6
    # trunk
    pygame.draw.polygon(s, trunk, [(26, base), (29, base - 9), (35, base - 9), (38, base)])
    R(s, trunk, 29, 52, 7, base - 61)
    R(s, sh(trunk, 1.25), 29, 52, 2, base - 52)
    R(s, sh(trunk, 0.7), 34, 52, 2, base - 52)
    dark, mid, light = pal
    circ = [(32, 32, 24), (16, 44, 14), (48, 44, 14), (21, 24, 13), (43, 24, 13), (32, 50, 12), (32, 16, 12)]
    can = S(W, H)
    for cx, cy, r in circ:
        pygame.draw.circle(can, sh(dark, 0.55), (cx, cy), r + 1)
    for cx, cy, r in circ:
        pygame.draw.circle(can, dark, (cx, cy), r)
    for cx, cy, r in circ:
        pygame.draw.circle(can, mid, (cx - 2, cy - 3), max(2, r - 4))
    for cx, cy, r in circ:
        if r >= 12:
            pygame.draw.circle(can, light, (cx - 5, cy - 7), max(2, r - 9))
    rnd = random.Random(sum(pal[0]))
    for _ in range(170):
        x, y = rnd.randrange(W), rnd.randrange(H)
        if can.get_at((x, y))[3] > 0 and y < 62:
            c = rnd.choice((sh(light, 1.05), dark, mid))
            R(can, c, x, y, 2, 2)
    if cherry:
        for _ in range(26):
            x, y = rnd.randrange(8, 56), rnd.randrange(8, 56)
            if can.get_at((x, y))[3] > 0:
                R(can, (255, 232, 240), x, y, 2, 2)
    s.blit(can, (0, 0))
    save(outline(s), "objects", name)  # outlined version is 2px bigger
    return


def pine_tree(name="tree_pine"):
    W, H = 64, 96
    s = S(W, H)
    shadow(s, 32, H - 6, 40, 12)
    base = H - 6
    R(s, (96, 66, 42), 29, 68, 7, base - 68)
    R(s, (126, 90, 58), 29, 68, 2, base - 68)
    dk, md, lt = (30, 84, 58), (48, 116, 72), (90, 164, 100)
    tiers = [(8, 30, 12), (22, 46, 17), (36, 60, 22), (50, 74, 27)]
    for top, bot, hw in tiers:
        pts = [(32, top)]
        n = 4
        for i in range(n + 1):
            y = top + (bot - top) * i / n
            x = 32 - hw * i / n
            pts.append((x - (2 if i % 2 else 0), y))
        pts.append((32 - hw - 2, bot + 3))
        pts.append((32 + hw + 2, bot + 3))
        for i in range(n, -1, -1):
            y = top + (bot - top) * i / n
            x = 32 + hw * i / n
            pts.append((x + (2 if i % 2 else 0), y))
        pygame.draw.polygon(s, dk, pts)
        left = [(32, top), (32 - hw - 1, bot + 2), (32, bot + 2)]
        pygame.draw.polygon(s, md, left)
        pygame.draw.polygon(s, lt, [(32, top + 2), (32 - hw * 0.5, top + (bot - top) * 0.6), (32, top + (bot - top) * 0.55)])
    save(outline(s), "objects", name)


def make_trees():
    blob_tree(((48, 112, 56), (68, 142, 70), (116, 186, 96)), (116, 80, 52), "tree_oak")
    blob_tree(((178, 76, 36), (214, 114, 44), (244, 176, 72)), (112, 76, 50), "tree_autumn")
    blob_tree(((206, 108, 148), (236, 146, 182), (255, 206, 224)), (104, 70, 52), "tree_cherry", cherry=True)
    pine_tree()


def make_misc_objects():
    # bush & berry bush
    for name, berries in (("bush", False), ("bush_berry", True)):
        s = S(32, 32)
        shadow(s, 16, 27, 28, 8, 60)
        for cx, cy, r in ((10, 19, 9), (22, 19, 9), (16, 14, 10)):
            pygame.draw.circle(s, (40, 98, 50), (cx, cy), r + 1)
        for cx, cy, r in ((10, 19, 9), (22, 19, 9), (16, 14, 10)):
            pygame.draw.circle(s, (60, 130, 66), (cx, cy), r)
        for cx, cy, r in ((10, 19, 9), (22, 19, 9), (16, 14, 10)):
            pygame.draw.circle(s, (88, 164, 84), (cx - 2, cy - 3), r - 4)
        if berries:
            for (x, y) in ((8, 18), (15, 12), (22, 18), (18, 21), (12, 22)):
                R(s, (220, 50, 70), x, y, 2, 2)
                px(s, x, y, (255, 150, 160))
        save(s, "objects", name)
    # rocks
    s = S(32, 32)
    shadow(s, 16, 27, 24, 7, 60)
    pygame.draw.polygon(s, (60, 58, 66), [(3, 26), (6, 14), (14, 8), (24, 11), (29, 20), (28, 26)])
    pygame.draw.polygon(s, (130, 128, 138), [(5, 25), (8, 15), (14, 10), (23, 12), (27, 20), (26, 25)])
    pygame.draw.polygon(s, (170, 168, 178), [(8, 16), (14, 11), (20, 12), (14, 17)])
    R(s, (100, 98, 108), 6, 23, 20, 2)
    save(s, "objects", "rock_s")
    s = S(64, 48)
    shadow(s, 32, 41, 52, 10, 60)
    pygame.draw.polygon(s, (60, 58, 66), [(4, 40), (8, 22), (20, 8), (38, 6), (54, 16), (60, 32), (58, 40)])
    pygame.draw.polygon(s, (126, 124, 134), [(6, 38), (10, 23), (21, 10), (38, 8), (52, 17), (57, 31), (55, 38)])
    pygame.draw.polygon(s, (168, 166, 176), [(12, 22), (22, 12), (36, 10), (30, 20), (18, 26)])
    pygame.draw.polygon(s, (92, 130, 80), [(36, 8), (52, 17), (46, 20), (38, 14)])
    R(s, (98, 96, 106), 8, 35, 46, 3)
    save(s, "objects", "rock_l")
    # stump
    s = S(32, 32)
    shadow(s, 16, 27, 26, 8, 60)
    R(s, (96, 64, 40), 7, 14, 18, 12)
    pygame.draw.ellipse(s, (96, 64, 40), (7, 22, 18, 7))
    pygame.draw.ellipse(s, (170, 124, 78), (7, 8, 18, 12))
    pygame.draw.ellipse(s, (200, 156, 104), (10, 10, 12, 8), 1)
    pygame.draw.ellipse(s, (150, 106, 66), (13, 12, 6, 4), 1)
    save(outline(s), "objects", "stump")
    # lamp post
    s = S(32, 64)
    shadow(s, 16, 58, 18, 6, 60)
    R(s, (50, 50, 60), 14, 24, 4, 34)
    R(s, (90, 90, 104), 14, 24, 1, 34)
    R(s, (50, 50, 60), 11, 55, 10, 4)
    R(s, (50, 50, 60), 9, 6, 14, 3)
    R(s, (50, 50, 60), 9, 22, 14, 3)
    R(s, (255, 226, 130), 11, 9, 10, 13)
    R(s, (255, 250, 200), 14, 12, 4, 6)
    R(s, (50, 50, 60), 11, 9, 1, 13)
    R(s, (50, 50, 60), 20, 9, 1, 13)
    pygame.draw.polygon(s, (50, 50, 60), [(8, 6), (24, 6), (16, 0)])
    save(s, "objects", "lamp")
    # barrel / crate / hay
    s = S(32, 32)
    shadow(s, 16, 28, 24, 7, 60)
    R(s, (150, 100, 60), 6, 6, 20, 22)
    pygame.draw.ellipse(s, (150, 100, 60), (5, 8, 22, 22))
    pygame.draw.ellipse(s, (150, 100, 60), (5, 2, 22, 10))
    pygame.draw.ellipse(s, (196, 146, 96), (7, 3, 18, 8))
    pygame.draw.ellipse(s, (120, 80, 48), (9, 5, 14, 4), 1)
    for y in (12, 22):
        R(s, (70, 70, 80), 5, y, 22, 2)
    R(s, (186, 134, 84), 9, 11, 2, 16)
    save(outline(s), "objects", "barrel")
    s = S(32, 32)
    shadow(s, 16, 28, 26, 7, 60)
    R(s, (176, 128, 76), 4, 6, 24, 22)
    R(s, (206, 160, 100), 4, 6, 24, 3)
    for (x, y, w, h) in ((4, 6, 3, 22), (25, 6, 3, 22), (4, 6, 24, 3), (4, 25, 24, 3)):
        R(s, (122, 84, 50), x, y, w, h)
    pygame.draw.line(s, (122, 84, 50), (7, 9), (25, 25), 2)
    pygame.draw.line(s, (122, 84, 50), (25, 9), (7, 25), 2)
    save(outline(s), "objects", "crate")
    s = S(32, 32)
    shadow(s, 16, 28, 28, 8, 60)
    pygame.draw.ellipse(s, (212, 176, 70), (3, 6, 26, 22))
    pygame.draw.ellipse(s, (240, 208, 100), (6, 7, 14, 12))
    r = random.Random(3)
    for _ in range(30):
        x, y = r.randrange(6, 26), r.randrange(8, 26)
        pygame.draw.line(s, r.choice(((190, 150, 50), (250, 226, 120))), (x, y), (x + 3, y + 2))
    R(s, (150, 96, 56), 4, 20, 24, 2)
    save(outline(s), "objects", "hay")
    # sign post
    s = S(32, 48)
    shadow(s, 16, 43, 18, 6, 60)
    R(s, (110, 76, 48), 14, 12, 4, 32)
    R(s, (150, 110, 70), 14, 12, 1, 32)
    pygame.draw.polygon(s, (190, 140, 86), [(3, 8), (24, 8), (30, 13), (24, 18), (3, 18)])
    pygame.draw.polygon(s, (110, 76, 48), [(3, 8), (24, 8), (30, 13), (24, 18), (3, 18)], 1)
    R(s, (96, 66, 42), 6, 12, 14, 1)
    R(s, (96, 66, 42), 6, 14, 10, 1)
    save(s, "objects", "sign")
    # notice board
    s = S(64, 64)
    shadow(s, 32, 58, 52, 8, 60)
    R(s, (100, 68, 44), 8, 14, 4, 44)
    R(s, (100, 68, 44), 52, 14, 4, 44)
    R(s, (82, 54, 34), 6, 6, 52, 34)
    R(s, (176, 130, 82), 9, 9, 46, 28)
    for (x, y, w, h, c) in ((12, 12, 11, 13, (246, 240, 220)), (26, 11, 10, 9, (250, 226, 150)),
                            (38, 13, 12, 15, (240, 236, 226)), (27, 22, 9, 12, (200, 224, 240))):
        R(s, c, x, y, w, h)
        for ly in range(y + 3, y + h - 2, 3):
            R(s, (120, 100, 80), x + 2, ly, w - 4, 1)
        R(s, (210, 60, 60), x + w // 2, y, 2, 2)
    pygame.draw.polygon(s, (82, 54, 34), [(4, 6), (60, 6), (56, 1), (8, 1)])
    save(outline(s), "objects", "board")
    # bench
    s = S(64, 32)
    shadow(s, 32, 28, 56, 7, 60)
    R(s, (90, 62, 40), 6, 20, 4, 8)
    R(s, (90, 62, 40), 54, 20, 4, 8)
    R(s, (150, 104, 64), 3, 8, 58, 4)
    R(s, (150, 104, 64), 3, 13, 58, 4)
    R(s, (186, 136, 88), 3, 8, 58, 1)
    R(s, (176, 126, 80), 2, 18, 60, 5)
    R(s, (206, 156, 104), 2, 18, 60, 1)
    R(s, (96, 66, 42), 4, 10, 3, 14)
    R(s, (96, 66, 42), 57, 10, 3, 14)
    save(outline(s), "objects", "bench")
    # scarecrow
    s = S(32, 48)
    shadow(s, 16, 43, 18, 6, 60)
    R(s, (110, 76, 48), 15, 14, 3, 30)
    R(s, (110, 76, 48), 3, 20, 26, 3)
    R(s, (186, 70, 70), 10, 18, 12, 14)
    R(s, (220, 120, 100), 11, 18, 3, 5)
    R(s, (230, 200, 100), 3, 21, 3, 4)
    R(s, (230, 200, 100), 26, 21, 3, 4)
    R(s, (236, 206, 150), 11, 5, 10, 10)
    px(s, 13, 9, (40, 30, 30))
    px(s, 18, 9, (40, 30, 30))
    R(s, (40, 30, 30), 14, 12, 4, 1)
    R(s, (216, 180, 90), 6, 4, 20, 2)
    R(s, (216, 180, 90), 10, 0, 12, 5)
    R(s, (120, 70, 50), 10, 3, 12, 1)
    save(outline(s), "objects", "scarecrow")
    # anvil on stump
    s = S(32, 32)
    shadow(s, 16, 28, 24, 7, 60)
    R(s, (110, 76, 48), 9, 18, 14, 10)
    R(s, (140, 100, 64), 9, 18, 14, 2)
    pygame.draw.polygon(s, (70, 72, 82), [(4, 10), (28, 10), (24, 14), (20, 14), (20, 18), (12, 18), (12, 14), (8, 14)])
    R(s, (150, 152, 164), 5, 10, 22, 2)
    pygame.draw.polygon(s, (70, 72, 82), [(28, 10), (31, 10), (28, 13)])
    save(outline(s), "objects", "anvil")
    # campfire (2 frames)
    for f in range(2):
        s = S(32, 32)
        shadow(s, 16, 26, 28, 9, 60)
        for i in range(8):
            a = i / 8 * math.tau
            pygame.draw.circle(s, (130, 128, 138), (int(16 + 11 * math.cos(a)), int(22 + 5 * math.sin(a))), 3)
            pygame.draw.circle(s, (176, 174, 184), (int(16 + 11 * math.cos(a)) - 1, int(22 + 5 * math.sin(a)) - 1), 1)
        pygame.draw.line(s, (96, 64, 40), (8, 24), (24, 18), 4)
        pygame.draw.line(s, (120, 80, 50), (8, 18), (24, 24), 4)
        h = 12 if f == 0 else 15
        pygame.draw.polygon(s, (236, 90, 30), [(10, 21), (16 - 1, 21 - h - 2), (22, 21)])
        pygame.draw.polygon(s, (250, 170, 40), [(12, 21), (16, 21 - h + 2), (20, 21)])
        pygame.draw.polygon(s, (255, 236, 130), [(14, 21), (16, 21 - h // 2 - 1), (18, 21)])
        save(s, "objects", f"campfire_{f}")


def make_house(name, w, wall, roof, beam=(104, 70, 46), door=(140, 92, 56), shutter=(84, 130, 170),
               sign=None, flowers=((236, 90, 90), (250, 214, 80)), stone=False, chimney=True):
    W, H = w * T, 4 * T + 16
    s = S(W, H)
    shadow(s, W // 2, H - 4, W - 6, 10, 70)
    cx = W // 2
    top, bot = 24, 80  # roof band
    wall_hi = sh(wall, 1.08)
    wall_lo = sh(wall, 0.88)
    # wall
    R(s, wall, 6, 70, W - 12, 60)
    rr = random.Random(w * 13 + sum(wall))
    for _ in range(W):
        px(s, 6 + rr.randrange(W - 12), 80 + rr.randrange(48), rr.choice((wall_hi, wall_lo)))
    if stone:
        for ry in range(80, 128, 8):
            for rx in range(6 + (ry // 8 % 2) * 6, W - 6, 12):
                R(s, sh(wall, 0.8), rx, ry, 1, 8)
            R(s, sh(wall, 0.8), 6, ry + 7, W - 12, 1)
    # timber frame
    R(s, beam, 6, 84, W - 12, 4)
    R(s, beam, 6, 122, W - 12, 5)
    R(s, beam, 6, 80, 6, 50)
    R(s, beam, W - 12, 80, 6, 50)
    R(s, sh(beam, 1.25), 6, 80, 1, 50)
    R(s, sh(beam, 1.25), 6, 84, W - 12, 1)
    # stone foundation
    R(s, (126, 122, 130), 4, 127, W - 8, 13)
    for ry in (127, 134):
        for rx in range(4 + (ry % 2) * 5, W - 4, 11):
            R(s, (96, 92, 100), rx, ry, 1, 7)
        R(s, (96, 92, 100), 4, ry + 6, W - 8, 1)
    R(s, (160, 156, 164), 4, 127, W - 8, 1)
    # windows
    wins = [cx - 40, cx + 40] if W < 176 else [cx - 76, cx - 40, cx + 40, cx + 76]
    if W >= 160 and W < 176:
        wins = [cx - 52, cx + 52]
    for wx in wins:
        x0, y0 = wx - 8, 98
        R(s, shutter, x0 - 6, y0 - 1, 5, 20)
        R(s, shutter, x0 + 17, y0 - 1, 5, 20)
        R(s, sh(shutter, 0.8), x0 - 6, y0 + 3, 5, 1)
        R(s, sh(shutter, 0.8), x0 - 6, y0 + 9, 5, 1)
        R(s, sh(shutter, 0.8), x0 + 17, y0 + 3, 5, 1)
        R(s, sh(shutter, 0.8), x0 + 17, y0 + 9, 5, 1)
        R(s, beam, x0 - 1, y0 - 1, 18, 18)
        R(s, (150, 206, 236), x0 + 1, y0 + 1, 14, 14)
        R(s, (110, 170, 214), x0 + 1, y0 + 9, 14, 6)
        R(s, beam, x0 + 7, y0 + 1, 2, 14)
        R(s, beam, x0 + 1, y0 + 7, 14, 2)
        R(s, (236, 250, 255), x0 + 2, y0 + 2, 2, 2)
        R(s, (110, 74, 48), x0 - 2, y0 + 17, 20, 5)
        R(s, (150, 106, 66), x0 - 2, y0 + 17, 20, 1)
        r = random.Random(wx)
        for fx in range(x0 - 1, x0 + 17, 3):
            R(s, (64, 132, 58), fx, y0 + 14, 2, 4)
            R(s, r.choice(flowers), fx - 1, y0 + 12, 3, 3)
    # door
    dx0 = cx - 12
    R(s, beam, dx0 - 3, 94, 30, 34)
    R(s, door, dx0, 97, 24, 31)
    for i in range(1, 4):
        R(s, sh(door, 0.78), dx0 + i * 6, 97, 1, 31)
    R(s, sh(door, 1.2), dx0, 97, 24, 1)
    R(s, sh(door, 0.65), dx0, 111, 24, 1)
    R(s, (250, 210, 90), dx0 + 18, 113, 3, 3)
    R(s, (170, 166, 174), cx - 16, 126, 32, 5)
    R(s, (200, 196, 204), cx - 16, 126, 32, 1)
    # roof
    for y in range(top, bot):
        t = (y - top) / (bot - top)
        xl = int(round(16 * (1 - t)))
        xr = W - 1 - xl
        rown = (y - top) // 8
        yin = (y - top) % 8
        base = roof if rown % 2 == 0 else sh(roof, 0.93)
        R(s, base, xl, y, xr - xl + 1, 1)
        if yin == 0:
            R(s, sh(roof, 1.18), xl, y, xr - xl + 1, 1)
        if yin == 7:
            R(s, sh(roof, 0.66), xl, y, xr - xl + 1, 1)
        if yin < 7:
            for x in range(xl + 1 + (rown % 2) * 6, xr, 12):
                px(s, x, y, sh(roof, 0.74))
        px(s, xl, y, sh(roof, 0.55))
        px(s, xr, y, sh(roof, 0.55))
    R(s, sh(roof, 1.3), 16, top - 3, W - 32, 4)
    R(s, sh(roof, 0.6), 16, top - 3, W - 32, 1)
    R(s, sh(roof, 0.55), 0, bot - 1, W, 1)
    # eave shadow on the wall
    sw = S(W, 10)
    for i in range(8):
        pygame.draw.line(sw, (0, 0, 0, 70 - i * 9), (6, i), (W - 7, i))
    s.blit(sw, (0, bot))
    # chimney
    if chimney:
        c0 = W - 42
        R(s, (150, 142, 150), c0, 8, 15, 40)
        for ry in range(10, 46, 6):
            R(s, (112, 104, 112), c0, ry, 15, 1)
        R(s, (112, 104, 112), c0 + 7, 10, 1, 6)
        R(s, (112, 104, 112), c0 + 3, 16, 1, 6)
        R(s, (90, 84, 92), c0 - 2, 4, 19, 5)
        R(s, (176, 168, 176), c0 - 2, 4, 19, 1)
        R(s, (40, 36, 42), c0 + 2, 5, 11, 2)
    if sign:
        f = pygame.font.Font(None, 15)
        tw, th = f.size(sign)
        bw = max(34, tw + 10)
        bx, by = cx - bw // 2, 60
        pygame.draw.line(s, (60, 50, 50), (bx + 4, by - 8), (bx + 4, by), 1)
        pygame.draw.line(s, (60, 50, 50), (bx + bw - 5, by - 8), (bx + bw - 5, by), 1)
        R(s, (84, 56, 34), bx - 1, by - 1, bw + 2, 18)
        R(s, (196, 146, 90), bx, by, bw, 16)
        R(s, (220, 176, 120), bx, by, bw, 1)
        t = f.render(sign, False, (70, 40, 22))
        s.blit(t, (cx - tw // 2, by + 8 - th // 2))
    save(outline(s), "objects", name)


def make_houses():
    make_house("house_elder", 5, (238, 224, 192), (82, 110, 168), shutter=(96, 140, 96), chimney=True)
    make_house("house_inn", 6, (240, 214, 176), (180, 66, 58), shutter=(70, 120, 90), sign="INN")
    make_house("house_shop", 4, (214, 226, 200), (86, 150, 88), shutter=(200, 120, 70), sign="SHOP")
    make_house("house_smith", 5, (176, 168, 168), (96, 98, 112), beam=(70, 60, 56), door=(100, 68, 48),
               shutter=(80, 80, 92), sign="FORGE", stone=True, flowers=((220, 90, 40), (250, 180, 60)))
    make_house("house_bakery", 4, (246, 220, 186), (214, 128, 62), shutter=(190, 80, 80), sign="BREAD")
    make_house("house_cottage_a", 4, (236, 208, 188), (130, 84, 150), shutter=(90, 150, 170))
    make_house("house_cottage_b", 4, (216, 226, 236), (170, 76, 66), shutter=(84, 130, 90))
    make_house("house_farm", 5, (232, 214, 170), (150, 104, 66), shutter=(120, 150, 80))
    make_house("house_herb", 4, (222, 232, 206), (96, 120, 160), shutter=(150, 100, 170),
               flowers=((200, 120, 230), (250, 250, 250)))


def make_big_objects():
    # Well
    s = S(64, 80)
    shadow(s, 32, 72, 56, 12, 70)
    R(s, (96, 90, 98), 6, 48, 52, 22)
    pygame.draw.ellipse(s, (96, 90, 98), (6, 58, 52, 14))
    R(s, (150, 146, 156), 6, 46, 52, 18)
    for ry in (46, 54, 62):
        for rx in range(6 + (ry % 16 // 8) * 6, 58, 12):
            R(s, (112, 108, 118), rx, ry, 1, 8)
        R(s, (112, 108, 118), 6, ry + 7, 52, 1)
    pygame.draw.ellipse(s, (170, 166, 176), (6, 36, 52, 22))
    pygame.draw.ellipse(s, (120, 116, 126), (11, 40, 42, 14))
    pygame.draw.ellipse(s, (40, 100, 170), (13, 42, 38, 10))
    pygame.draw.ellipse(s, (110, 180, 230), (19, 44, 14, 3))
    R(s, (110, 76, 48), 8, 14, 5, 42)
    R(s, (110, 76, 48), 51, 14, 5, 42)
    R(s, (146, 104, 66), 8, 14, 1, 42)
    R(s, (110, 76, 48), 8, 18, 48, 5)
    R(s, (146, 104, 66), 8, 18, 48, 1)
    pygame.draw.polygon(s, (170, 70, 58), [(2, 22), (32, 2), (62, 22)])
    pygame.draw.polygon(s, (204, 96, 74), [(6, 20), (32, 5), (32, 20)])
    pygame.draw.line(s, (120, 44, 38), (2, 22), (62, 22), 2)
    R(s, (120, 90, 60), 32, 23, 1, 12)
    R(s, (130, 90, 56), 28, 34, 8, 7)
    R(s, (80, 54, 36), 28, 34, 8, 1)
    save(outline(s), "objects", "well")
    # Stalls
    for name, c1, c2 in (("stall_red", (210, 66, 62), (250, 244, 232)), ("stall_blue", (70, 112, 192), (250, 244, 232))):
        s = S(96, 96)
        shadow(s, 48, 88, 88, 12, 70)
        R(s, (110, 76, 48), 6, 36, 5, 50)
        R(s, (110, 76, 48), 85, 36, 5, 50)
        R(s, (150, 104, 64), 6, 62, 84, 24)
        for x in range(8, 90, 12):
            R(s, (112, 76, 48), x, 62, 1, 24)
        R(s, (190, 140, 88), 4, 58, 88, 6)
        R(s, (214, 168, 112), 4, 58, 88, 1)
        # goods
        r = random.Random(len(name))
        for x in range(12, 82, 11):
            k = r.choice(("apple", "bread", "cab"))
            if k == "apple":
                pygame.draw.circle(s, (210, 50, 50), (x, 55), 5)
                px(s, x - 2, 53, (255, 150, 150))
                R(s, (60, 130, 50), x, 49, 2, 2)
            elif k == "bread":
                pygame.draw.ellipse(s, (200, 140, 70), (x - 6, 50, 13, 8))
                pygame.draw.ellipse(s, (226, 176, 100), (x - 5, 50, 9, 5))
            else:
                pygame.draw.circle(s, (110, 190, 90), (x, 54), 5)
                pygame.draw.circle(s, (160, 220, 130), (x - 1, 53), 3)
        # awning
        for i in range(0, 96, 8):
            col = c1 if (i // 8) % 2 == 0 else c2
            pygame.draw.polygon(s, col, [(i, 10), (i + 8, 10), (i + 8, 34), (i + 4, 40), (i, 34)])
        R(s, sh(c1, 0.7), 0, 8, 96, 3)
        R(s, sh(c1, 1.2), 0, 11, 96, 1)
        pygame.draw.line(s, sh(c1, 0.6), (0, 34), (4, 40))
        save(outline(s), "objects", name)
    # Fences
    s = S(32, 32)
    shadow(s, 16, 27, 32, 5, 50)
    for y in (12, 20):
        R(s, (176, 128, 78), 0, y, 32, 4)
        R(s, (206, 158, 104), 0, y, 32, 1)
        R(s, (120, 84, 50), 0, y + 3, 32, 1)
    R(s, (150, 104, 64), 0, 7, 6, 22)
    R(s, (186, 138, 90), 0, 7, 2, 22)
    R(s, (210, 164, 112), 0, 6, 6, 2)
    save(s, "objects", "fence_h")
    s = S(32, 32)
    shadow(s, 16, 30, 12, 4, 50)
    R(s, (176, 128, 78), 13, 0, 6, 32)
    R(s, (206, 158, 104), 13, 0, 2, 32)
    R(s, (120, 84, 50), 18, 0, 1, 32)
    R(s, (150, 104, 64), 11, 4, 10, 10)
    R(s, (210, 164, 112), 11, 4, 10, 2)
    R(s, (120, 84, 50), 11, 13, 10, 1)
    save(s, "objects", "fence_v")
    # Shrine (3x2 -> 96x96)
    s = S(96, 96)
    shadow(s, 48, 88, 84, 12, 70)
    R(s, (116, 112, 122), 6, 66, 84, 22)
    R(s, (156, 152, 164), 6, 66, 84, 4)
    R(s, (96, 92, 102), 6, 82, 84, 6)
    for pxx in (14, 70):
        R(s, (130, 126, 138), pxx, 18, 14, 50)
        R(s, (168, 164, 176), pxx, 18, 3, 50)
        R(s, (100, 96, 108), pxx + 11, 18, 3, 50)
        R(s, (150, 146, 158), pxx - 3, 12, 20, 8)
        R(s, (100, 96, 108), pxx - 3, 18, 20, 2)
        for (mx, my) in ((pxx + 1, 40), (pxx + 6, 50), (pxx + 2, 58), (pxx + 8, 30)):
            R(s, (70, 130, 70), mx, my, 4, 3)
    R(s, (150, 146, 158), 12, 8, 72, 8)
    R(s, (186, 182, 194), 12, 8, 72, 2)
    R(s, (100, 96, 108), 12, 14, 72, 2)
    for rx in (22, 38, 54, 70):
        R(s, (90, 210, 200), rx, 11, 4, 2)
    # orb
    for rad, a in ((20, 40), (14, 70), (9, 120)):
        t = S(96, 96)
        pygame.draw.circle(t, (110, 240, 224, a), (48, 52), rad)
        s.blit(t, (0, 0))
    pygame.draw.circle(s, (180, 255, 246), (48, 52), 6)
    pygame.draw.circle(s, (255, 255, 255), (46, 50), 2)
    R(s, (130, 126, 138), 38, 58, 20, 10)
    R(s, (168, 164, 176), 38, 58, 20, 2)
    R(s, (90, 210, 200), 44, 62, 8, 2)
    save(outline(s), "objects", "shrine")
    # Tent
    s = S(96, 80)
    shadow(s, 48, 72, 84, 12, 70)
    pygame.draw.polygon(s, (170, 140, 90), [(4, 70), (48, 4), (92, 70)])
    pygame.draw.polygon(s, (206, 176, 120), [(8, 68), (48, 8), (48, 68)])
    pygame.draw.polygon(s, (86, 60, 40), [(36, 70), (48, 34), (60, 70)])
    pygame.draw.polygon(s, (40, 28, 22), [(42, 70), (48, 44), (54, 70)])
    pygame.draw.line(s, (120, 90, 56), (48, 4), (4, 70), 1)
    pygame.draw.line(s, (120, 90, 56), (48, 4), (92, 70), 1)
    R(s, (110, 76, 48), 47, 0, 2, 8)
    for i in range(3):
        pygame.draw.line(s, (150, 124, 80), (48 - 4 - i * 8, 20 + i * 14), (48 - 4 - i * 8 - 3, 30 + i * 14), 1)
    pygame.draw.polygon(s, (80, 130, 76), [(48, 4), (60, 4), (54, 18)])
    save(outline(s), "objects", "tent")


def make_objects():
    make_trees()
    make_misc_objects()
    make_houses()
    make_big_objects()


# -------------------------------------------------------------- characters
def draw_char(p, d, f):
    s = S(16, 24)
    skin = p["skin"]
    hair = p["hair"]
    shirt = p["shirt"]
    pants = p["pants"]
    shoe = p.get("shoe", (64, 44, 34))
    shirt_d, shirt_l = sh(shirt, 0.78), sh(shirt, 1.14)
    skin_d = sh(skin, 0.86)
    hair_d, hair_l = sh(hair, 0.72), sh(hair, 1.22)
    style = p.get("style", "short")
    hat = p.get("hat")
    hatc = p.get("hatc", (120, 90, 60))
    hat_d = sh(hatc, 0.75)
    hat_l = sh(hatc, 1.2)
    robe = p.get("robe", False)
    apron = p.get("apron")
    beard = p.get("beard", False)
    armor = p.get("armor", False)
    scarf = p.get("scarf")
    cape = p.get("cape")
    side = d in ("left", "right")
    back = d == "up"
    eye = (34, 26, 34)
    bob = 0

    # ---- cape (behind the body, visible from back and sides)
    if cape:
        if back:
            R(s, cape, 3, 10, 10, 11)
            R(s, sh(cape, 0.78), 3, 19, 10, 2)
            R(s, sh(cape, 1.15), 4, 10, 2, 9)
        elif side:
            R(s, cape, 3, 10, 3, 10)
            R(s, sh(cape, 0.78), 3, 18, 3, 2)

    # ---- legs
    if not robe:
        if not side:
            lifts = {0: (0, 0), 1: (1, 0), 2: (0, 1)}[f]
            for lx, lift in ((5, lifts[0]), (8, lifts[1])):
                R(s, pants, lx, 17, 3, 5 - lift)
                R(s, sh(pants, 0.8), lx + 2, 17, 1, 5 - lift)
                R(s, shoe, lx - 0, 22 - lift, 3, 2 if not lift else 1)
                px(s, lx, 22 - lift, sh(shoe, 1.3))
        else:
            offs = {0: (0, 0), 1: (-1, 1), 2: (1, -1)}[f]
            for lx, o in ((6 + offs[0], 0), (7 + offs[1], 0)):
                R(s, pants, lx, 17, 3, 5)
                R(s, shoe, lx + (1 if d == "right" else 0), 22, 3, 2)
    else:
        R(s, shirt, 4, 16, 8, 4)
        R(s, shirt_d, 4, 19, 8, 2)
        R(s, shirt, 3, 19, 10, 2)
        R(s, shirt_d, 3, 20, 10, 1)
        o = (-1 if f == 1 else 0, 1 if f == 2 else 0)
        R(s, shoe, 5 + o[0], 22, 2, 2)
        R(s, shoe, 9 + o[1], 22, 2, 2)

    # ---- torso & arms
    swing = {0: 0, 1: 1, 2: -1}[f]
    if not side:
        R(s, shirt, 4, 10, 8, 7)
        R(s, shirt_d, 11, 10, 1, 7)
        R(s, shirt_l, 4, 10, 8, 1)
        if armor:
            R(s, sh(shirt, 1.25), 3, 10, 2, 2)
            R(s, sh(shirt, 1.25), 11, 10, 2, 2)
            R(s, sh(shirt, 0.9), 6, 12, 4, 3)
        if p.get("belt"):
            R(s, (96, 66, 40), 4, 15, 8, 1)
            px(s, 8, 15, (240, 200, 80))
        for ax, sgn in ((2, 1), (12, -1)):
            ay = 11 + (swing * (1 if ax == 2 else -1))
            R(s, shirt_l if ax == 2 else shirt, ax, ay, 2, 4)
            R(s, skin, ax, ay + 4, 2, 2)
        if apron and not back:
            R(s, apron, 5, 12, 6, 6 if robe else 7)
            R(s, sh(apron, 0.85), 5, 17, 6, 1)
            R(s, sh(apron, 0.88), 5, 12, 6, 1)
        if scarf:
            R(s, scarf, 4, 10, 8, 2)
            if not back:
                R(s, scarf, 9, 12, 2, 4)
                R(s, sh(scarf, 0.8), 9, 15, 2, 1)
    else:
        R(s, shirt, 5, 10, 6, 7)
        R(s, shirt_d, 5, 10, 1, 7)
        R(s, shirt_l, 5, 10, 6, 1)
        if armor:
            R(s, sh(shirt, 1.25), 5, 10, 3, 2)
        if p.get("belt"):
            R(s, (96, 66, 40), 5, 15, 6, 1)
        if apron:
            R(s, apron, 9 if d == "right" else 5, 12, 2, 7)
        ax = 6 + swing
        R(s, shirt_l, ax, 11, 3, 4)
        R(s, skin, ax, 15, 3, 2)
        if scarf:
            R(s, scarf, 5, 10, 6, 2)
            R(s, scarf, 5 if d == "right" else 9, 12, 2, 4)

    # ---- head
    def front_face(x0, x1):
        R(s, skin, x0, 3, x1 - x0 + 1, 7)
        px(s, x0, 3, (0, 0, 0, 0))
        px(s, x1, 3, (0, 0, 0, 0))
        px(s, x0, 9, (0, 0, 0, 0))
        px(s, x1, 9, (0, 0, 0, 0))

    if back:
        R(s, hair, 4, 2, 8, 8)
        R(s, hair_d, 4, 8, 8, 2)
        R(s, hair_l, 5, 3, 3, 1)
        for (x, y) in ((4, 2), (11, 2), (4, 9), (11, 9)):
            px(s, x, y, (0, 0, 0, 0))
        if style == "long":
            R(s, hair, 4, 10, 8, 4)
            R(s, hair_d, 4, 13, 8, 1)
        if style == "braid":
            R(s, hair, 7, 9, 2, 6)
            R(s, hair_d, 7, 11, 2, 1)
            R(s, hair_d, 7, 14, 2, 1)
        if style == "bun":
            R(s, hair, 6, 0, 4, 3)
            R(s, hair_l, 6, 0, 2, 1)
        if style == "pigtails":
            R(s, hair, 2, 5, 2, 6)
            R(s, hair, 12, 5, 2, 6)
        if style == "bald":
            R(s, skin, 5, 3, 6, 5)
            R(s, sh(skin, 1.1), 5, 3, 2, 1)
            R(s, hair, 4, 6, 1, 3)
            R(s, hair, 11, 6, 1, 3)
    elif not side:
        front_face(4, 11)
        # hair
        if style != "bald":
            R(s, hair, 4, 2, 8, 2)
            px(s, 4, 2, (0, 0, 0, 0))
            px(s, 11, 2, (0, 0, 0, 0))
            R(s, hair_l, 6, 2, 3, 1)
            R(s, hair, 4, 4, 3, 1)
            R(s, hair, 9, 4, 3, 1)
            R(s, hair, 4, 5, 1, 2)
            R(s, hair, 11, 5, 1, 2)
        else:
            R(s, sh(skin, 1.1), 6, 2, 3, 1)
            R(s, skin, 5, 2, 6, 2)
            R(s, hair, 4, 5, 1, 3)
            R(s, hair, 11, 5, 1, 3)
        if style == "long":
            R(s, hair, 3, 4, 2, 10)
            R(s, hair, 11, 4, 2, 10)
            R(s, hair_d, 3, 13, 2, 1)
            R(s, hair_d, 11, 13, 2, 1)
        if style == "bun":
            R(s, hair, 6, 0, 4, 2)
            R(s, hair_l, 6, 0, 2, 1)
        if style == "braid":
            R(s, hair, 12, 5, 2, 7)
            R(s, hair_d, 12, 8, 2, 1)
            R(s, (200, 70, 70), 12, 12, 2, 1)
        if style == "pigtails":
            R(s, hair, 2, 4, 2, 6)
            R(s, hair, 12, 4, 2, 6)
            R(s, (210, 60, 70), 2, 4, 2, 1)
            R(s, (210, 60, 70), 12, 4, 2, 1)
        # face
        px(s, 6, 6, eye)
        px(s, 9, 6, eye)
        px(s, 6, 5, (0, 0, 0, 0) if False else skin)
        px(s, 5, 7, (244, 150, 140))
        px(s, 10, 7, (244, 150, 140))
        R(s, (176, 90, 84), 7, 8, 2, 1)
        if beard:
            R(s, hair if style != "bald" else hair, 5, 8, 6, 3)
            R(s, hair_l, 5, 8, 6, 1)
            R(s, (176, 90, 84), 7, 8, 2, 1)
            R(s, hair_d, 6, 10, 4, 1)
    else:
        sx = 5
        R(s, skin, sx, 3, 7, 7)
        px(s, 5, 3, (0, 0, 0, 0))
        px(s, 5, 9, (0, 0, 0, 0))
        px(s, 11, 9, (0, 0, 0, 0))
        R(s, eye, 9, 6, 1, 1)
        px(s, 11, 7, skin_d)
        px(s, 10, 8, (176, 90, 84))
        px(s, 9, 7, (244, 150, 140))
        if style != "bald":
            R(s, hair, 5, 2, 7, 2)
            R(s, hair, 4, 3, 4, 7)
            R(s, hair_d, 4, 8, 4, 2)
            R(s, hair, 9, 4, 3, 1)
            R(s, hair_l, 6, 2, 3, 1)
        else:
            R(s, skin, 5, 2, 6, 2)
            R(s, hair, 4, 5, 3, 4)
        if style == "long":
            R(s, hair, 3, 4, 4, 10)
            R(s, hair_d, 3, 13, 4, 1)
        if style == "bun":
            R(s, hair, 3, 0, 4, 3)
        if style == "braid":
            R(s, hair, 3, 5, 2, 8)
            R(s, hair_d, 3, 8, 2, 1)
            R(s, (200, 70, 70), 3, 12, 2, 1)
        if style == "pigtails":
            R(s, hair, 3, 4, 2, 6)
            R(s, (210, 60, 70), 3, 4, 2, 1)
        if beard:
            R(s, hair, 8, 8, 4, 3)
            R(s, hair_l, 8, 8, 4, 1)
            R(s, hair_d, 9, 10, 2, 1)

    # ---- hats
    cap_front = not back
    if hat == "straw":
        R(s, hatc, 2, 3, 12, 2)
        R(s, hat_l, 2, 3, 12, 1)
        R(s, hat_d, 2, 4, 12, 1)
        R(s, hatc, 5, 0, 6, 4)
        R(s, hat_l, 5, 0, 3, 1)
        R(s, (176, 80, 60), 5, 3, 6, 1)
    elif hat == "cap":
        R(s, hatc, 4, 1, 8, 3)
        R(s, hat_l, 5, 1, 4, 1)
        R(s, hat_d, 4, 3, 8, 1)
        if d == "down":
            R(s, hat_d, 4, 4, 8, 1)
        elif d == "right":
            R(s, hat_d, 9, 4, 4, 1)
        elif d == "left":
            R(s, hat_d, 3, 4, 4, 1)
    elif hat == "hood":
        R(s, hatc, 3, 1, 10, 3)
        R(s, hat_l, 5, 1, 4, 1)
        if d == "down":
            R(s, hatc, 3, 4, 2, 6)
            R(s, hatc, 11, 4, 2, 6)
            R(s, hat_d, 3, 9, 10, 1)
        elif back:
            R(s, hatc, 3, 4, 10, 7)
            R(s, hat_d, 3, 10, 10, 1)
        else:
            R(s, hatc, 3 if d == "right" else 6, 4, 7, 6)
    elif hat == "chef":
        R(s, hatc, 3, 0, 10, 3)
        R(s, sh(hatc, 0.9), 3, 2, 10, 1)
        R(s, hatc, 4, 3, 8, 1)
        R(s, sh(hatc, 0.8), 4, 3, 8, 1)
        R(s, (255, 255, 255), 5, 0, 2, 1)
    elif hat == "witch":
        R(s, hatc, 1, 3, 14, 2)
        R(s, hat_l, 1, 3, 14, 1)
        R(s, hat_d, 1, 4, 14, 1)
        R(s, hatc, 5, 1, 6, 2)
        R(s, hatc, 6, 0, 3, 1)
        R(s, hat_d, 5, 2, 6, 1)
        R(s, (250, 210, 80), 7, 2, 2, 1)
    elif hat == "helmet":
        R(s, hatc, 4, 1, 8, 4)
        R(s, hat_l, 5, 1, 4, 1)
        R(s, hat_d, 4, 4, 8, 1)
        px(s, 4, 1, (0, 0, 0, 0))
        px(s, 11, 1, (0, 0, 0, 0))
        R(s, hat_d, 3, 5, 2, 4)
        R(s, hat_d, 11, 5, 2, 4)
        if d == "down":
            R(s, hat_d, 7, 5, 2, 3)
    elif hat == "feather":
        R(s, hatc, 4, 1, 8, 3)
        R(s, hat_l, 5, 1, 4, 1)
        R(s, hat_d, 3, 3, 10, 1)
        R(s, (248, 248, 248), 11, 0, 1, 2)
        R(s, (230, 230, 240), 12, 0, 1, 1)
        R(s, (250, 250, 250), 10, 1, 1, 1)
        R(s, (250, 250, 250), 12, 1, 2, 1)

    if side and d == "left":
        s = pygame.transform.flip(s, True, False)
    return s


def make_characters_rm():
    """Builds character sheets + portraits from the RPG Maker style sheets in assets/rpgmaker.
    Source layout: 12x8 cells of 32px = 4x2 characters, each 3 cols (step, idle, step) x 4 rows
    (down, left, right, up).  Output layout used by the game: col0 = idle, col1/col2 = steps."""
    src = {}
    for n in ("Actor1", "Actor2", "Actor3"):
        p = os.path.join(ASSETS, "rpgmaker", n + ".png")
        if os.path.exists(p):
            src[n] = pygame.image.load(p)
    jobs = [("hero", HERO_SPRITE)] + [(k, v) for k, v in SPRITES.items()]
    for cid, (sheet, idx) in jobs:
        sp = src[sheet]
        bx, by = (idx % 4) * 96, (idx // 4) * 128
        out = S(96, 128)
        order = (1, 0, 2)
        for r in range(4):
            for f in range(3):
                out.blit(sp, (f * 32, r * 32), (bx + order[f] * 32, by + r * 32, 32, 32))
        save(out, "characters", cid)
        if cid != "hero":
            face = out.subsurface((5, 1, 22, 22)).copy()
            por = S(72, 72)
            for y in range(72):
                pygame.draw.line(por, (206 - y // 4, 226 - y // 6, 238 - y // 8), (0, y), (72, y))
            por.blit(scale(face, 3), (3, 3))
            pygame.draw.rect(por, (70, 48, 34), (0, 0, 72, 72), 3)
            pygame.draw.rect(por, (200, 156, 98), (3, 3, 66, 66), 1)
            save(por, "portraits", cid)


def make_characters():
    if os.path.exists(os.path.join(ASSETS, "rpgmaker", "Actor1.png")):
        return make_characters_rm()
    return make_characters_procedural()


def make_characters_procedural():
    cells = [("hero", HERO)] + [(n["id"], n["pal"]) for n in NPCS]
    for cid, pal in cells:
        sheet = S(36 * 3, 52 * 4)
        for ri, d in enumerate(("down", "left", "right", "up")):
            for f in range(3):
                c = draw_char(pal, "right" if d == "left" else d, f)
                if d == "left":
                    c = pygame.transform.flip(c, True, False)
                # draw_char on 'left' draws mirrored art; we flip a right-facing sprite for left
                big = scale(outline(c), 2)
                sheet.blit(big, (f * 36, ri * 52))
        save(sheet, "characters", cid)
        if cid != "hero":
            front = outline(draw_char(pal, "down", 0))
            crop = front.subsurface((1, 1, 16, 16)).copy()
            por = S(72, 72)
            bg = S(72, 72)
            for y in range(72):
                c = (206 - y // 4, 226 - y // 6, 238 - y // 8)
                pygame.draw.line(bg, c, (0, y), (72, y))
            por.blit(bg, (0, 0))
            por.blit(scale(crop, 4), (4, 6))
            pygame.draw.rect(por, (70, 48, 34), (0, 0, 72, 72), 3)
            pygame.draw.rect(por, (200, 156, 98), (3, 3, 66, 66), 1)
            save(por, "portraits", cid)


def make_animals():
    # chicken: 3 frames (stand, walk, peck), drawn 12x12 then x2
    for f in range(3):
        s = S(12, 12)
        R(s, (250, 250, 246), 3, 4, 6, 5)
        R(s, (226, 224, 220), 3, 8, 6, 1)
        R(s, (250, 250, 246), 7, 2 if f != 2 else 5, 3, 3)
        R(s, (220, 50, 50), 8, 1 if f != 2 else 4, 2, 1)
        R(s, (250, 170, 40), 10, 3 if f != 2 else 6, 1, 1)
        px(s, 8, 3 if f != 2 else 6, (30, 30, 30))
        R(s, (230, 226, 220), 2, 4, 2, 3)
        R(s, (240, 190, 50), 4 + (1 if f == 1 else 0), 9, 1, 2)
        R(s, (240, 190, 50), 7 - (1 if f == 1 else 0), 9, 1, 2)
        save(outline(scale(s, 2)), "animals", f"chicken_{f}")
    for f in range(2):
        s = S(16, 11)
        R(s, (150, 98, 56), 3, 3, 9, 4)
        R(s, (176, 120, 72), 3, 3, 9, 1)
        R(s, (150, 98, 56), 11, 1, 4, 4)
        R(s, (110, 70, 40), 14, 1, 2, 2)
        R(s, (110, 70, 40), 11, 0, 1, 2)
        px(s, 13, 2, (20, 20, 20))
        R(s, (246, 230, 210), 12, 4, 3, 1)
        R(s, (110, 70, 40), 2, 2 - f, 2, 2)
        R(s, (150, 98, 56), 4 + f, 7, 2, 3)
        R(s, (150, 98, 56), 9 - f, 7, 2, 3)
        R(s, (110, 70, 40), 4 + f, 9, 2, 1)
        R(s, (110, 70, 40), 9 - f, 9, 2, 1)
        save(outline(scale(s, 2)), "animals", f"dog_{f}")
    for i, c in enumerate(((255, 160, 60), (250, 240, 110), (140, 190, 255))):
        for f in range(2):
            s = S(9, 7)
            y = 0 if f == 0 else 2
            R(s, c, 0, y, 4, 4 - y // 2)
            R(s, c, 5, y, 4, 4 - y // 2)
            R(s, sh(c, 0.8), 1, y + 1, 2, 2)
            R(s, sh(c, 0.8), 6, y + 1, 2, 2)
            R(s, (40, 30, 30), 4, 2, 1, 4)
            save(s, "animals", f"butterfly_{i}_{f}")


# ---------------------------------------------------------------- UI / SFX
def make_ui():
    s = S(612, 96)
    pygame.draw.rect(s, (60, 40, 28), (0, 0, 612, 96), border_radius=10)
    pygame.draw.rect(s, (244, 232, 200), (3, 3, 606, 90), border_radius=8)
    pygame.draw.rect(s, (214, 188, 140), (3, 3, 606, 90), 2, border_radius=8)
    pygame.draw.rect(s, (150, 104, 64), (7, 7, 598, 82), 1, border_radius=6)
    save(s, "ui", "dialog_box")
    s = S(150, 22)
    pygame.draw.rect(s, (60, 40, 28), (0, 0, 150, 22), border_radius=6)
    pygame.draw.rect(s, (176, 100, 70), (2, 2, 146, 18), border_radius=5)
    save(s, "ui", "name_tag")
    s = S(20, 20)
    pygame.draw.circle(s, (60, 40, 28), (10, 10), 10)
    pygame.draw.circle(s, (250, 240, 214), (10, 10), 8)
    f = pygame.font.Font(None, 18)
    t = f.render("E", True, (60, 40, 28))
    s.blit(t, (10 - t.get_width() // 2, 10 - t.get_height() // 2 + 1))
    save(s, "ui", "key_e")
    s = S(12, 8)
    pygame.draw.polygon(s, (150, 80, 50), [(1, 1), (11, 1), (6, 7)])
    pygame.draw.polygon(s, (230, 150, 90), [(2, 1), (10, 1), (6, 5)])
    save(s, "ui", "next_arrow")
    s = S(64, 64)
    for r, a in ((32, 18), (26, 30), (20, 50), (14, 70), (8, 90)):
        t = S(64, 64)
        pygame.draw.circle(t, (255, 214, 120, a), (32, 32), r)
        s.blit(t, (0, 0))
    save(s, "ui", "glow")


def tone(path, notes, vol=0.4):
    rate = 22050
    frames = bytearray()
    for freq, dur in notes:
        n = int(rate * dur)
        for i in range(n):
            env = (1 - i / n) ** 1.5
            v = math.sin(2 * math.pi * freq * i / rate) * 0.7 + math.sin(2 * math.pi * freq * 2 * i / rate) * 0.2
            frames += struct.pack("<h", int(v * env * vol * 32767))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def sweep(path, f0, f1, dur, vol=0.35, noise=0.0):
    rate = 22050
    n = int(rate * dur)
    frames = bytearray()
    ph = 0.0
    rnd = random.Random(1)
    for i in range(n):
        k = i / n
        f = f0 + (f1 - f0) * k
        ph += 2 * math.pi * f / rate
        env = min(1.0, i / 120) * (1 - k) ** 1.2
        v = math.sin(ph) * 0.8 + math.sin(ph * 2) * 0.15 + (rnd.random() * 2 - 1) * noise
        frames += struct.pack("<h", int(max(-1, min(1, v)) * env * vol * 32767))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def make_sfx():
    d = os.path.join(ASSETS, "sfx")
    tone(os.path.join(d, "blip.wav"), [(620, 0.035)], 0.25)
    tone(os.path.join(d, "blip2.wav"), [(520, 0.035)], 0.25)
    tone(os.path.join(d, "talk.wav"), [(660, 0.07), (880, 0.1)], 0.3)
    tone(os.path.join(d, "bye.wav"), [(660, 0.07), (440, 0.12)], 0.3)
    tone(os.path.join(d, "step.wav"), [(110, 0.03)], 0.15)
    sweep(os.path.join(d, "jump.wav"), 330, 760, 0.17, 0.35)
    sweep(os.path.join(d, "land.wav"), 150, 70, 0.07, 0.35, noise=0.25)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    make_tiles()
    make_decor()
    make_objects()
    make_characters()
    make_animals()
    make_ui()
    make_sfx()
    print("Assets written to", ASSETS)


if __name__ == "__main__":
    main()
