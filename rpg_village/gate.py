"""The Hollow Gate: a sunken stone stairwell with a flagstone forecourt, a rune seal,
twin braziers and drifting purple mist.  Everything is drawn with code (no extra art files).

Layout (tile coordinates, 32 px tiles):
    forecourt  : ellipse of dark flagstones around (49, 87)         -> built in world.World.build_gate
    landing    : row 86,   x 47..50   (the hero stands here and presses E)
    pillars    : row 86,   x 46 and x 51 (tall, with braziers on top; they are y-sorted props)
    stairwell  : rows 87..89, x 47..50 (steps vanish into darkness), flanked by walls x 46 / x 51
    back wall  : row 90,   x 46..51
"""
import math
import random

import pygame

from world import COBBLE

T = 32
VIEW_W, VIEW_H = 640, 360

CENTER_X = 49 * T                    # 1568 - middle of the stairwell (px)
PIT = pygame.Rect(47 * T, 87 * T, 4 * T, 3 * T)          # the dark stairwell (px)
STRUCT = pygame.Rect(46 * T, 87 * T, 6 * T, 4 * T)       # walls + stairwell (px), for decor placement
PILLAR_TILES = (46, 51)
PILLAR_BOTTOM = 87 * T                                    # y-sort line of the pillars
FLAME_Y = PILLAR_BOTTOM - 98                              # flame centre (px)

STONE = (88, 84, 100)
STONE_DK = (58, 54, 72)
STONE_LT = (128, 122, 146)


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _radial(size, color, power=1.8):
    s = pygame.Surface((size, size))
    c = size / 2.0
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - c + 0.5, y - c + 0.5) / c
            k = max(0.0, 1 - d) ** power
            s.set_at((x, y), tuple(int(v * k) for v in color))
    return s


# --------------------------------------------------------------------------- ground art
def _stone_blocks(surf, rect, rnd, base=STONE):
    """Brick-pattern stone wall filling `rect`."""
    rows = (rect.h + 15) // 16
    for row in range(rows):
        y = rect.y + row * 16
        h = min(16, rect.bottom - y)
        off = 0 if row % 2 == 0 else 16
        x = rect.x - off
        while x < rect.right:
            x0, x1 = max(x, rect.x), min(x + 32, rect.right)
            if x1 > x0:
                d = rnd.randint(-9, 9)
                col = tuple(max(0, min(255, v + d)) for v in base)
                pygame.draw.rect(surf, col, (x0, y, x1 - x0, h))
                pygame.draw.rect(surf, STONE_DK, (x0, y, x1 - x0, h), 1)
                pygame.draw.line(surf, _shade(col, 1.18), (x0 + 1, y + 1), (x1 - 2, y + 1))
                if rnd.random() < 0.16:                       # moss
                    mx, my = rnd.randint(x0, max(x0, x1 - 6)), y + rnd.randint(0, max(0, h - 5))
                    pygame.draw.ellipse(surf, (74, 112, 66), (mx, my, rnd.randint(4, 8), rnd.randint(3, 5)))
            x += 32


def _skull(surf, x, y):
    pygame.draw.ellipse(surf, (226, 220, 204), (x, y, 11, 9))
    pygame.draw.rect(surf, (226, 220, 204), (x + 2, y + 7, 7, 4))
    pygame.draw.circle(surf, (28, 22, 30), (x + 3, y + 4), 2)
    pygame.draw.circle(surf, (28, 22, 30), (x + 8, y + 4), 2)
    pygame.draw.line(surf, (28, 22, 30), (x + 5, y + 6), (x + 6, y + 6))
    for i in (3, 5, 7):
        pygame.draw.line(surf, (150, 142, 130), (x + i, y + 9), (x + i, y + 10))


def _bone(surf, x, y, ang, ln=11):
    dx, dy = math.cos(ang) * ln / 2, math.sin(ang) * ln / 2
    a, b = (x - dx, y - dy), (x + dx, y + dy)
    pygame.draw.line(surf, (218, 210, 192), a, b, 2)
    for p in (a, b):
        pygame.draw.circle(surf, (230, 222, 205), (int(p[0]), int(p[1])), 2)


def paint_ground(ground, world):
    """Paint the gate onto the pre-baked village ground surface (done once at start-up)."""
    rnd = random.Random(1234)
    t = world.terrain

    # 1) darken + age the forecourt flagstones
    for ty in range(81, 95):
        for tx in range(42, 56):
            if not (0 < tx < len(t[0]) - 1 and 0 < ty < len(t) - 1) or t[ty][tx] != COBBLE:
                continue
            inner = all(t[ty + dy][tx + dx] == COBBLE for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            a = 125 if inner else 60
            s = pygame.Surface((T, T), pygame.SRCALPHA)
            s.fill((44, 36, 72, a))
            pygame.draw.line(s, (22, 16, 38, min(255, a + 70)), (0, 0), (T - 1, 0))
            pygame.draw.line(s, (22, 16, 38, min(255, a + 70)), (0, 0), (0, T - 1))
            if rnd.random() < 0.55:
                pygame.draw.line(s, (22, 16, 38, min(255, a + 50)), (0, 16), (T - 1, 16))
                vx = rnd.randint(8, 24)
                y0, y1 = (0, 16) if rnd.random() < 0.5 else (16, T - 1)
                pygame.draw.line(s, (22, 16, 38, min(255, a + 50)), (vx, y0), (vx, y1))
            pygame.draw.line(s, (150, 140, 180, a // 2), (1, 1), (T - 3, 1))
            if inner and rnd.random() < 0.28:
                pts, px, py = [], rnd.randint(4, 26), rnd.randint(4, 26)
                for _ in range(4):
                    pts.append((px, py))
                    px = max(1, min(T - 2, px + rnd.randint(-7, 7)))
                    py = max(1, min(T - 2, py + rnd.randint(-7, 7)))
                pygame.draw.lines(s, (14, 10, 24, 210), False, pts, 1)
            if rnd.random() < 0.22:
                for _ in range(4):
                    pygame.draw.circle(s, (72, 112, 68, 170), (rnd.randint(2, 29), rnd.randint(2, 29)), rnd.randint(1, 3))
            ground.blit(s, (tx * T, ty * T))

    # 2) carved landing slab in front of the stairs
    lx, ly = 47 * T, 86 * T
    for i in range(4):
        r = pygame.Rect(lx + i * T, ly, T, T)
        pygame.draw.rect(ground, _shade(STONE, 1.05 + 0.04 * (i % 2)), r)
        pygame.draw.line(ground, STONE_LT, r.topleft, (r.right - 1, r.top))
        pygame.draw.line(ground, STONE_DK, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))
        pygame.draw.line(ground, STONE_DK, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))

    # 3) rune seal around the stairwell mouth (the lower half is hidden by the stairwell itself)
    ring = pygame.Surface((140, 140), pygame.SRCALPHA)
    c = (70, 70)
    pygame.draw.circle(ring, (118, 78, 190, 235), c, 62, 2)
    pygame.draw.circle(ring, (86, 56, 150, 200), c, 53, 1)
    for i in range(36):
        a = i * math.tau / 36
        r0, r1 = (53, 62) if i % 3 == 0 else (56, 60)
        pygame.draw.line(ring, (100, 66, 168, 210), (c[0] + math.cos(a) * r0, c[1] + math.sin(a) * r0),
                         (c[0] + math.cos(a) * r1, c[1] + math.sin(a) * r1))
    for i in range(8):                                        # eight glyph diamonds
        a = i * math.tau / 8 + 0.2
        gx, gy = c[0] + math.cos(a) * 44, c[1] + math.sin(a) * 44
        pygame.draw.polygon(ring, (150, 104, 226, 235), [(gx, gy - 5), (gx + 4, gy), (gx, gy + 5), (gx - 4, gy)], 1)
        pygame.draw.circle(ring, (170, 124, 240, 235), (int(gx), int(gy)), 1)
    ground.blit(ring, (CENTER_X - 70, 87 * T - 70))

    # 4) the stairwell: eight steps sinking into black, with soft shading on the sides and bottom
    pit = pygame.Surface((PIT.w, PIT.h), pygame.SRCALPHA)
    for i in range(8):
        k = i / 7.0
        tread = tuple(int(a + (b - a) * (k ** 0.75)) for a, b in zip((120, 114, 134), (10, 7, 16)))
        pygame.draw.rect(pit, tread, (0, i * 12, PIT.w, 8))
        pygame.draw.rect(pit, _shade(tread, 0.5), (0, i * 12 + 8, PIT.w, 4))
        pygame.draw.line(pit, _shade(tread, 1.25), (0, i * 12), (PIT.w - 1, i * 12))
    shade = pygame.Surface((PIT.w, PIT.h), pygame.SRCALPHA)
    for y in range(PIT.h):
        for x in range(PIT.w):
            side = max(0.0, 1 - x / 16.0, 1 - (PIT.w - 1 - x) / 16.0)
            a = 150 * (y / (PIT.h - 1.0)) ** 2 + 130 * side
            shade.set_at((x, y), (0, 0, 8, min(235, int(a))))
    pit.blit(shade, (0, 0))
    pygame.draw.line(pit, (168, 160, 184), (0, 0), (PIT.w - 1, 0), 2)         # worn top lip
    ground.blit(pit, PIT.topleft)

    # 5) walls: left, right, back + the plinths under the pillars
    _stone_blocks(ground, pygame.Rect(46 * T, 87 * T, T, 3 * T), rnd)
    _stone_blocks(ground, pygame.Rect(51 * T, 87 * T, T, 3 * T), rnd)
    _stone_blocks(ground, pygame.Rect(46 * T, 90 * T, 6 * T, T), rnd, _shade(STONE, 0.92))
    pygame.draw.line(ground, STONE_LT, (46 * T, 90 * T), (52 * T - 1, 90 * T), 3)
    for px in (46 * T + T - 3, 51 * T):                                         # inner edge shadow
        pygame.draw.line(ground, (30, 26, 42), (px, 87 * T), (px, 90 * T), 3)
    for tx in PILLAR_TILES:
        _stone_blocks(ground, pygame.Rect(tx * T, 86 * T, T, T), rnd, _shade(STONE, 0.9))
        pygame.draw.rect(ground, STONE_LT, (tx * T, 86 * T, T, T), 1)
    shadow = pygame.Surface((6 * T + 20, 14), pygame.SRCALPHA)                  # wall shadow on the forecourt
    pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
    ground.blit(shadow, (46 * T - 10, 91 * T - 4))

    # 6) scorch marks, rubble, bones
    for tx in PILLAR_TILES:
        sc = pygame.Surface((54, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(sc, (0, 0, 0, 85), sc.get_rect())
        ground.blit(sc, (tx * T + 16 - 27, 87 * T - 8))
    for _ in range(26):
        x, y = rnd.randint(43 * T, 55 * T), rnd.randint(82 * T, 93 * T)
        tx, ty = x // T, y // T
        if STRUCT.inflate(8, 8).collidepoint(x, y) or not (0 <= ty < len(t) and 0 <= tx < len(t[0])) \
                or t[ty][tx] != COBBLE:
            continue
        w, h = rnd.randint(3, 7), rnd.randint(2, 4)
        pygame.draw.ellipse(ground, (30, 26, 40), (x - 1, y + 1, w + 2, h + 1))
        pygame.draw.ellipse(ground, (104, 98, 118), (x, y, w, h))
    for (sx, sy) in ((45 * T + 6, 88 * T + 2), (52 * T + 10, 89 * T - 6)):
        if t[sy // T][sx // T] == COBBLE:
            _skull(ground, sx, sy)
    for (bx, by, a) in ((45 * T + 22, 88 * T + 14, 0.5), (45 * T + 8, 89 * T + 6, -0.4),
                        (52 * T + 4, 88 * T + 18, 1.1), (52 * T + 20, 90 * T + 4, 0.1),
                        (47 * T + 10, 91 * T + 14, 0.8)):
        if t[by // T][bx // T] == COBBLE:
            _bone(ground, bx, by, a)


def make_pillar():
    """A tall carved pillar with a brazier bowl on top (flame is drawn live by GateFX)."""
    w, h = 36, 104
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, _shade(STONE, 0.82), (0, 88, w, 16))                    # plinth
    pygame.draw.rect(s, STONE_DK, (0, 88, w, 16), 1)
    pygame.draw.line(s, STONE_LT, (1, 89), (w - 2, 89))
    pygame.draw.rect(s, STONE, (6, 20, 24, 70))                                 # shaft
    pygame.draw.rect(s, _shade(STONE, 1.25), (6, 20, 5, 70))
    pygame.draw.rect(s, _shade(STONE, 0.7), (25, 20, 5, 70))
    for y in range(34, 88, 18):
        pygame.draw.line(s, STONE_DK, (6, y), (29, y))
    pygame.draw.polygon(s, (170, 122, 240), [(18, 44), (23, 52), (18, 60), (13, 52)], 1)      # carved rune
    pygame.draw.circle(s, (206, 164, 255), (18, 52), 1)
    pygame.draw.line(s, (150, 104, 226), (18, 60), (18, 74))
    pygame.draw.rect(s, _shade(STONE, 1.1), (2, 12, 32, 10))                    # capital
    pygame.draw.rect(s, STONE_DK, (2, 12, 32, 10), 1)
    pygame.draw.line(s, STONE_LT, (3, 13), (32, 13))
    pygame.draw.polygon(s, (52, 48, 62), [(3, 4), (33, 4), (28, 13), (8, 13)])  # brazier bowl
    pygame.draw.polygon(s, (30, 26, 38), [(3, 4), (33, 4), (28, 13), (8, 13)], 1)
    pygame.draw.ellipse(s, (232, 118, 44), (7, 1, 22, 6))                       # glowing coals
    pygame.draw.ellipse(s, (255, 190, 90), (12, 2, 12, 3))
    return s


def pillar_props():
    """Props for Game.props:  [sort_y, image, x, y, w, h]."""
    img = make_pillar()
    out = []
    for tx in PILLAR_TILES:
        x = tx * T + 16 - img.get_width() // 2
        y = PILLAR_BOTTOM + 4 - img.get_height()
        out.append([PILLAR_BOTTOM, img, x, y, img.get_width(), img.get_height()])
    return out


def flame_positions():
    return [(tx * T + 16, FLAME_Y) for tx in PILLAR_TILES]


# --------------------------------------------------------------------------- live effects
class GateFX:
    def __init__(self):
        base = _radial(128, (150, 70, 230), 1.7)
        self.pit_glow = []
        for k in (0.40, 0.58, 0.78, 1.0):
            g = base.copy()
            g.fill((int(255 * k),) * 3, special_flags=pygame.BLEND_RGB_MULT)
            self.pit_glow.append(g)
        fg = _radial(56, (255, 150, 60), 1.6)
        fg.fill((95, 95, 95), special_flags=pygame.BLEND_RGB_MULT)
        self.flame_glow = fg
        self.mist = []
        for r in (4, 5, 6, 7, 9):
            m = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(m, (196, 150, 255, 255), (r + 1, r + 1), r)
            self.mist.append(m)
        self.ring = pygame.Surface((140, 72), pygame.SRCALPHA)        # only the half above the stairwell
        c = (70, 70)
        pygame.draw.circle(self.ring, (200, 150, 255, 255), c, 62, 2)
        for i in range(8):
            a = i * math.tau / 8 + 0.2
            gx, gy = c[0] + math.cos(a) * 44, c[1] + math.sin(a) * 44
            pygame.draw.polygon(self.ring, (225, 190, 255, 255),
                                [(gx, gy - 5), (gx + 4, gy), (gx, gy + 5), (gx - 4, gy)], 1)

    @staticmethod
    def _near(cam, x, y, pad=160):
        return cam[0] - pad < x < cam[0] + VIEW_W + pad and cam[1] - pad < y < cam[1] + VIEW_H + pad

    def draw_ground(self, v, cam, t):
        """Glow, rune shimmer and mist - drawn on the ground, below the y-sorted sprites."""
        if not self._near(cam, CENTER_X, 88 * T):
            return
        pulse = 0.5 + 0.5 * math.sin(t * 2.2)
        g = self.pit_glow[min(3, int(pulse * 3.99))]
        v.blit(g, (CENTER_X - 64 - cam[0], 88 * T + 8 - 64 - cam[1]), special_flags=pygame.BLEND_RGB_ADD)
        self.ring.set_alpha(int(60 + 150 * pulse))
        v.blit(self.ring, (CENTER_X - 70 - cam[0], 87 * T - 70 - cam[1]))
        for i in range(8):                                         # mist curling up out of the dark
            k = (t * 0.32 + i / 8.0) % 1.0
            x = 47 * T + 10 + i * 15 + math.sin(t * 1.2 + i * 1.7) * 7
            y = 87 * T + 20 - k * 78
            m = self.mist[i % len(self.mist)]
            m.set_alpha(int(105 * math.sin(k * math.pi)))
            v.blit(m, (x - cam[0], y - cam[1]))

    def draw_flames(self, v, cam, t):
        """Brazier flames - drawn after the pillars so they sit on top of them."""
        for n, (fx, fy) in enumerate(flame_positions()):
            if not self._near(cam, fx, fy, 60):
                continue
            sx, sy = fx - cam[0], fy - cam[1]
            v.blit(self.flame_glow, (sx - 28, sy - 34), special_flags=pygame.BLEND_RGB_ADD)
            h = 13 + 3 * math.sin(t * 13 + n * 2) + 2 * math.sin(t * 7.3 + n)
            sway = math.sin(t * 9 + n * 3) * 1.8
            pygame.draw.polygon(v, (255, 138, 38), [(sx - 7, sy), (sx - 4, sy - h * 0.55), (sx + sway, sy - h),
                                                    (sx + 4, sy - h * 0.55), (sx + 7, sy)])
            pygame.draw.polygon(v, (255, 214, 96), [(sx - 4, sy), (sx - 2, sy - h * 0.4), (sx + sway * 0.6, sy - h * 0.72),
                                                    (sx + 2, sy - h * 0.4), (sx + 4, sy)])
            pygame.draw.circle(v, (255, 248, 200), (int(sx), int(sy - 1)), 2)
            for j in range(3):                                      # rising sparks
                k = (t * 0.9 + j / 3.0 + n * 0.37) % 1.0
                px, py = int(sx + math.sin(t * 5 + j * 2 + n) * 6), int(sy - 6 - k * 26)
                if 0 <= px < VIEW_W and 0 <= py < VIEW_H:
                    v.set_at((px, py), (255, int(200 - 90 * k), 80))
