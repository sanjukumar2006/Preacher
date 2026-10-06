"""Draws the goddess statue sprite -> assets/objects/goddess.png (64x96, bottom-anchored like the other objects).
Run:  python tools/make_goddess.py      (replace the PNG with your own art any time)"""
import os
import pygame

W, H = 64, 96
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "objects", "goddess.png")


def outline(img, col=(34, 30, 52)):
    m = pygame.mask.from_surface(img, 40)
    out = pygame.Surface(img.get_size(), pygame.SRCALPHA)
    for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.blit(m.to_surface(setcolor=col + (255,), unsetcolor=(0, 0, 0, 0)), (dx, dy))
    out.blit(img, (0, 0))
    return out


def poly(s, col, pts):
    pygame.draw.polygon(s, col, pts)


def make():
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = 32
    # ---- wings (behind)
    for sgn in (-1, 1):
        def X(x):
            return cx + sgn * x
        poly(s, (214, 224, 244), [(X(5), 36), (X(22), 20), (X(27), 14), (X(26), 28), (X(20), 44), (X(10), 52)])
        poly(s, (244, 248, 255), [(X(7), 36), (X(21), 23), (X(25), 18), (X(24), 30), (X(18), 42), (X(10), 48)])
        for i, (a, b) in enumerate(((27, 30), (22, 40), (16, 48))):
            pygame.draw.line(s, (176, 192, 226), (X(7 + i * 2), 36 + i * 2), (X(a - 4), b - 14), 1)
    # ---- pedestal
    pygame.draw.rect(s, (112, 116, 132), (8, 84, 48, 12))
    pygame.draw.rect(s, (150, 154, 170), (8, 84, 48, 3))
    pygame.draw.rect(s, (96, 100, 116), (12, 76, 40, 9))
    pygame.draw.rect(s, (140, 144, 160), (12, 76, 40, 2))
    pygame.draw.rect(s, (158, 162, 178), (17, 62, 30, 15))
    pygame.draw.rect(s, (196, 200, 214), (17, 62, 30, 2))
    pygame.draw.rect(s, (122, 126, 144), (17, 74, 30, 3))
    # rune on the plinth
    for pts in (((32, 66), (32, 73)), ((29, 68), (35, 68)), ((29, 72), (32, 69)), ((35, 72), (32, 69))):
        pygame.draw.line(s, (120, 200, 255), pts[0], pts[1], 1)
    # moss
    for x, y in ((9, 90), (11, 92), (50, 88), (53, 91), (14, 80), (46, 79)):
        s.set_at((x, y), (98, 150, 90))
        s.set_at((x + 1, y), (84, 132, 78))
    # ---- robe
    poly(s, (160, 174, 212), [(25, 33), (39, 33), (47, 62), (17, 62)])
    poly(s, (236, 240, 250), [(26, 33), (38, 33), (45, 62), (19, 62)])
    poly(s, (206, 216, 238), [(31, 36), (33, 36), (36, 62), (28, 62)])
    for x0, x1 in ((22, 21), (27, 26), (37, 38), (42, 43)):
        pygame.draw.line(s, (178, 192, 224), (x0, 46), (x1, 62), 1)
    # sash + gold hem
    pygame.draw.rect(s, (236, 190, 84), (26, 44, 12, 3))
    pygame.draw.rect(s, (200, 150, 54), (26, 46, 12, 1))
    pygame.draw.rect(s, (236, 190, 84), (19, 60, 26, 2))
    # ---- arms + orb
    poly(s, (226, 232, 246), [(25, 34), (28, 36), (30, 49), (27, 50), (24, 42)])
    poly(s, (226, 232, 246), [(39, 34), (36, 36), (34, 49), (37, 50), (40, 42)])
    pygame.draw.circle(s, (244, 222, 200), (30, 50), 2)
    pygame.draw.circle(s, (244, 222, 200), (34, 50), 2)
    pygame.draw.circle(s, (90, 160, 240), (32, 47), 5)
    pygame.draw.circle(s, (170, 220, 255), (32, 47), 4)
    pygame.draw.circle(s, (255, 255, 255), (31, 46), 2)
    # ---- hair (back), head, hair (front)
    poly(s, (226, 180, 96), [(25, 22), (39, 22), (41, 40), (36, 44), (28, 44), (23, 40)])
    pygame.draw.circle(s, (244, 222, 200), (32, 26), 6)
    poly(s, (240, 200, 116), [(25, 25), (26, 19), (32, 17), (38, 19), (39, 25), (36, 21), (32, 21), (28, 21)])
    pygame.draw.line(s, (60, 50, 80), (30, 27), (30, 27))
    pygame.draw.line(s, (60, 50, 80), (34, 27), (34, 27))
    s.set_at((32, 30), (214, 150, 140))
    # ---- halo
    pygame.draw.ellipse(s, (255, 226, 130), (23, 8, 18, 7), 2)
    pygame.draw.ellipse(s, (255, 248, 200), (25, 9, 14, 5), 1)
    return outline(s)


if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((1, 1))
    img = make()
    pygame.image.save(img, OUT)
    print("wrote", os.path.abspath(OUT))
