"""Hand-crafted five-level dungeon for Hearthmoor.

Each floor has a deliberate room/corridor layout, a staircase to the next floor, and a
staircase back up. The village entrance is on level 1. Monsters, weapons and all battle
logic live in combat.py; this file only draws the floor and tells combat when a new floor loads.
"""
import math
import pygame

T = 32
DW, DH = 36, 24
FLOOR, WALL, WATER, LAVA, PILLAR = range(5)

FLOOR_NAMES = {1: "Forgotten Catacombs", 2: "Flooded Halls", 3: "Ashen Mines",
               4: "Frozen Vault", 5: "Ancient Sanctum", 6: "Throne of the Warden"}
SEE_RADIUS = 7          # how far (in tiles) the hero's lantern reveals the dungeon map


class DungeonWorld:
    def __init__(self, level=1):
        self.level = level
        self.grid = [[WALL for _ in range(DW)] for _ in range(DH)]
        self.altar = None
        self.throne = None
        self.exit_tile = None
        self.exit_cells = []
        self.exit_open = False
        self._build(level)

    def _set_floor(self, x, y, kind=FLOOR):
        if 0 <= x < DW and 0 <= y < DH:
            self.grid[y][x] = kind

    def room(self, x0, y0, x1, y1, kind=FLOOR):
        x0, y0 = max(1, x0), max(1, y0)
        x1, y1 = min(DW - 2, x1), min(DH - 2, y1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self._set_floor(x, y, kind)

    def corridor_h(self, x0, x1, y, width=2):
        lo, hi = sorted((x0, x1))
        for yy in range(y - width // 2, y + width - width // 2):
            for x in range(lo, hi + 1):
                self._set_floor(x, yy)

    def corridor_v(self, y0, y1, x, width=2):
        lo, hi = sorted((y0, y1))
        for xx in range(x - width // 2, x + width - width // 2):
            for y in range(lo, hi + 1):
                self._set_floor(xx, y)

    def pillar(self, x, y):
        if 1 <= x < DW - 1 and 1 <= y < DH - 1:
            self.grid[y][x] = PILLAR

    def _build(self, level):
        # A deliberate, room-based layout rather than scattered/random tiles.
        if level == 1:
            # Forgotten Catacombs: long nave + six burial chambers.
            self.room(14, 18, 21, 22)
            self.corridor_v(12, 19, 17, 3)
            self.room(11, 10, 23, 14)
            self.corridor_v(5, 11, 17, 3)
            self.room(13, 2, 21, 6)
            self.corridor_h(6, 17, 12, 3)
            self.room(3, 9, 7, 14)
            self.room(27, 9, 33, 14)
            self.corridor_h(7, 17, 11, 2)
            self.corridor_h(17, 27, 12, 2)
            self.room(4, 16, 9, 20)
            self.corridor_h(9, 17, 18, 2)
            self.room(25, 17, 31, 20)
            self.corridor_h(21, 28, 18, 2)
            self.down = (18, 3)
            self.up = (18, 21)
            self._make_crypts()
        elif level == 2:
            # Flooded Halls: symmetrical stone halls around a dry central spine.
            self.room(15, 1, 20, 22)
            self.room(3, 8, 32, 15)
            self.room(4, 3, 10, 7)
            self.room(25, 3, 31, 7)
            self.room(4, 17, 10, 21)
            self.room(25, 17, 31, 21)
            self.corridor_h(10, 15, 5, 2)
            self.corridor_h(20, 25, 5, 2)
            self.corridor_h(10, 15, 19, 2)
            self.corridor_h(20, 25, 19, 2)
            # Water is decorative but blocked, creating dangerous-looking side pools.
            for r in ((5, 9, 10, 11), (25, 9, 30, 11), (5, 13, 10, 14), (25, 13, 30, 14)):
                self.room(*r, WATER)
            self.room(15, 1, 20, 3)
            self.down, self.up = (17, 2), (17, 21)
            for p in ((13, 6), (22, 6), (13, 17), (22, 17)):
                self.pillar(*p)
        elif level == 3:
            # Ashen Mines: a broad central mine with lava fissures and support pillars.
            self.room(3, 3, 32, 20)
            self.room(8, 1, 27, 22)
            # Cut out deep side voids to form mine galleries.
            for y in range(4, 20):
                self.grid[y][3] = WALL
                self.grid[y][32] = WALL
            for r in ((5, 5, 10, 8), (25, 5, 30, 8), (5, 15, 10, 18), (25, 15, 30, 18), (14, 10, 21, 13)):
                self.room(*r, LAVA)
            # Restore corridors through the lava chamber.
            self.corridor_v(8, 15, 12, 2)
            self.corridor_v(8, 15, 23, 2)
            self.corridor_h(10, 25, 11, 2)
            self.corridor_v(3, 8, 17, 3)
            self.down, self.up = (17, 3), (17, 20)
            for p in ((12, 6), (23, 6), (12, 17), (23, 17), (17, 15), (17, 7)):
                self.pillar(*p)
        elif level == 4:
            # Frozen Vault: four chambers connected by a central cross-shaped hall.
            self.room(14, 9, 21, 14)
            self.room(3, 2, 11, 7)
            self.room(24, 2, 32, 7)
            self.room(3, 16, 11, 21)
            self.room(24, 16, 32, 21)
            self.corridor_h(10, 25, 5, 2)
            self.corridor_h(10, 25, 18, 2)
            self.corridor_v(6, 18, 17, 3)
            self.room(15, 10, 20, 13)
            # Ice patches remain walkable-looking but are blocked to force corridor routes.
            self.room(5, 3, 9, 5, WATER)
            self.room(26, 3, 30, 5, WATER)
            self.room(5, 18, 9, 20, WATER)
            self.room(26, 18, 30, 20, WATER)
            self.down, self.up = (17, 3), (17, 18)
            for p in ((13, 8), (22, 8), (13, 15), (22, 15)):
                self.pillar(*p)
        elif level == 6:
            # Throne room of Grimhorn: one great hall, a raised dais, a sealed east wall.
            self.room(8, 6, 27, 21)
            self.room(13, 2, 22, 5)
            self.down = self.up = None
            self.throne = (17, 3)
            for p in ((11, 9), (11, 13), (11, 17), (24, 9), (24, 13), (24, 17)):
                self.pillar(*p)
            self.exit_cells = [(x, y) for x in range(28, 34) for y in range(12, 15)]
            self.exit_tile = (32, 13)
        else:
            # Level 5: Ancient Sanctum. Large final chamber with an altar.
            self.room(12, 2, 23, 6)
            self.room(4, 8, 31, 19)
            self.room(10, 19, 25, 22)
            self.corridor_v(6, 9, 17, 3)
            self.corridor_h(8, 17, 12, 3)
            self.corridor_h(17, 31, 12, 3)
            self.down = None
            self.up = (17, 20)
            for p in ((8, 10), (11, 10), (23, 10), (26, 10), (8, 17), (26, 17),
                      (14, 15), (20, 15), (14, 18), (20, 18)):
                self.pillar(*p)
            self.altar = (17, 4)

        # Hard outer boundary.
        for x in range(DW):
            self.grid[0][x] = WALL
            self.grid[DH - 1][x] = WALL
        for y in range(DH):
            self.grid[y][0] = WALL
            self.grid[y][DW - 1] = WALL

        # Stair tiles are always safe floor.
        if self.up:
            self._set_floor(*self.up)
        if self.down:
            self._set_floor(*self.down)

    def _make_crypts(self):
        # Small blocked pits and columns make the catacombs read as a real burial dungeon.
        for p in ((5, 10), (5, 13), (29, 10), (29, 13), (6, 18), (29, 18),
                  (15, 10), (20, 10), (15, 14), (20, 14)):
            self.pillar(*p)

    def open_exit(self):
        """After the boss falls: the sealed east wall crumbles into a corridor leading to a portal."""
        self.exit_open = True
        for x, y in self.exit_cells:
            self.grid[y][x] = FLOOR

    def inb(self, x, y):
        return 0 <= x < DW and 0 <= y < DH

    def rect_blocked(self, r):
        x0, x1 = int(r.left // T), int((r.right - 1) // T)
        y0, y1 = int(r.top // T), int((r.bottom - 1) // T)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if not self.inb(xx, yy) or self.grid[yy][xx] in (WALL, WATER, LAVA, PILLAR):
                    return True
        return False

    def walkable_tile(self, x, y):
        return self.inb(x, y) and self.grid[y][x] == FLOOR

    def nearest_walkable(self, x, y):
        for r in range(12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and self.walkable_tile(x + dx, y + dy):
                        return x + dx, y + dy
        return self.up or (17, 20)


class Dungeon:
    def __init__(self, assets):
        self.assets = assets
        self.level = 1
        self.max_level = 5          # stairs go 1..5; level 6 is the boss throne room, entered through the purple gate
        self.world = DungeonWorld(1)
        self.t = 0.0
        self.cam = [0.0, 0.0]
        self.on_level = None          # combat.py hooks in here to (re)spawn monsters when a floor loads
        self.explored = {lv: set() for lv in range(1, 7)}     # tiles the hero has seen, per floor (dungeon map)
        self._seen_tile = None
        self._map_worlds = {}
        self._load_tiles()
        self.set_level(1, spawn="entrance")

    def _load_tiles(self):
        a5 = self.assets["Dungeon_A5"]
        # Chosen from the gray/black stone portions of the supplied RPG Maker sheet.
        self.floor_a = a5.subsurface((4 * 32, 13 * 32, 32, 32)).copy()
        self.floor_b = a5.subsurface((5 * 32, 13 * 32, 32, 32)).copy()
        self.floor_c = a5.subsurface((6 * 32, 13 * 32, 32, 32)).copy()
        self.wall = a5.subsurface((4 * 32, 9 * 32, 32, 32)).copy()
        self.wall2 = a5.subsurface((5 * 32, 9 * 32, 32, 32)).copy()
        self.wall3 = a5.subsurface((6 * 32, 9 * 32, 32, 32)).copy()
        self.lava = a5.subsurface((1 * 32, 5 * 32, 32, 32)).copy()
        self.water = a5.subsurface((2 * 32, 6 * 32, 32, 32)).copy()
        self.ornament = a5.subsurface((4 * 32, 14 * 32, 32, 32)).copy()
        self.stairs = a5.subsurface((4 * 32, 15 * 32, 32, 32)).copy()

    def set_level(self, level, spawn="entrance"):
        self.level = max(1, min(6, level))
        self.world = DungeonWorld(self.level)
        self.torches = self._make_torches()
        self.cracks = self._make_details()
        self._seen_tile = None
        self._set_spawn(spawn)
        if self.on_level:
            self.on_level()

    def _set_spawn(self, spawn):
        if spawn == "down" and self.world.up:
            tx, ty = self.world.up
        elif spawn == "up" and self.world.down:
            tx, ty = self.world.down
        elif spawn == "gate":
            tx, ty = (17, 20)
        elif spawn == "entrance":
            tx, ty = (17, 20) if self.level == 1 else (self.world.up or (17, 20))
        else:
            tx, ty = self.world.nearest_walkable(17, 20)
        self.spawn_tile = (tx, ty)

    def player_spawn(self):
        tx, ty = self.spawn_tile
        return tx * T + 16, ty * T + 28

    def _make_torches(self):
        common = {
            1: [(12, 5), (22, 5), (8, 11), (27, 12), (12, 18), (23, 18)],
            2: [(12, 5), (23, 5), (12, 12), (23, 12), (12, 19), (23, 19)],
            3: [(7, 3), (27, 3), (7, 20), (27, 20), (12, 8), (23, 8), (17, 15)],
            4: [(11, 5), (23, 5), (11, 18), (23, 18), (17, 8), (17, 15)],
            5: [(10, 9), (24, 9), (10, 18), (24, 18), (17, 7), (17, 20)],
            6: [(9, 7), (26, 7), (9, 14), (26, 14), (9, 20), (26, 20), (14, 3), (21, 3), (14, 12), (21, 12)],
        }
        return [p for p in common[self.level] if self.world.walkable_tile(*p)]

    def _make_details(self):
        patterns = {
            1: [(10, 7), (24, 7), (3, 15), (32, 15), (13, 16), (22, 16)],
            2: [(4, 7), (31, 7), (4, 16), (31, 16), (13, 8), (22, 8)],
            3: [(4, 4), (31, 4), (4, 19), (31, 19), (14, 6), (20, 17)],
            4: [(12, 7), (22, 7), (12, 16), (22, 16)],
            5: [(6, 8), (29, 8), (6, 19), (29, 19), (12, 16), (22, 16)],
            6: [(9, 10), (26, 11), (13, 16), (22, 19)],
        }
        return [p for p in patterns[self.level] if self.world.walkable_tile(*p)]

    def next_transition(self, player):
        tx, ty = int(player.x // T), int((player.y - 4) // T)
        if self.world.up and abs(tx - self.world.up[0]) <= 1 and abs(ty - self.world.up[1]) <= 1:
            return "up"
        if self.world.down and abs(tx - self.world.down[0]) <= 1 and abs(ty - self.world.down[1]) <= 1:
            return "down"
        return None

    # ------------------------------------------------------------------ dungeon map
    def world_for(self, level):
        """The layout of any floor (used by the map to show floors other than the current one)."""
        if level == self.level:
            return self.world
        if level not in self._map_worlds:
            self._map_worlds[level] = DungeonWorld(level)
        return self._map_worlds[level]

    def reveal(self, player):
        """Mark the tiles around the hero as explored. Walls block the view, so rooms are
        only drawn once you have actually looked into them."""
        px, py = int(player.x // T), int((player.y - 4) // T)
        if (px, py) == self._seen_tile:
            return
        self._seen_tile = (px, py)
        seen = self.explored[self.level]
        g = self.world.grid
        r = SEE_RADIUS
        for ty in range(max(0, py - r), min(DH, py + r + 1)):
            for tx in range(max(0, px - r), min(DW, px + r + 1)):
                if (tx, ty) in seen or math.hypot(tx - px, ty - py) > r + 0.5:
                    continue
                n = max(abs(tx - px), abs(ty - py))
                blocked = False
                for i in range(1, n):                 # walk the line; a wall in between hides the tile
                    sx = px + (tx - px) * i / n
                    sy = py + (ty - py) * i / n
                    if g[int(round(sy))][int(round(sx))] == WALL:
                        blocked = True
                        break
                if not blocked:
                    seen.add((tx, ty))

    def explored_to_save(self):
        return {str(lv): ["".join("1" if (x, y) in tiles else "0" for x in range(DW)) for y in range(DH)]
                for lv, tiles in self.explored.items() if tiles}

    def load_explored(self, data):
        self.explored = {lv: set() for lv in range(1, 7)}
        self._seen_tile = None
        for key, rows in (data or {}).items():
            try:
                lv = int(key)
                for y, row in enumerate(rows[:DH]):
                    for x, ch in enumerate(row[:DW]):
                        if ch == "1":
                            self.explored[lv].add((x, y))
            except (ValueError, KeyError, TypeError):
                continue

    def update(self, dt, player):
        self.t += dt
        self.reveal(player)
        tx = player.x - 320
        ty = player.y - 180
        max_x = max(0, DW * T - 640)
        max_y = max(0, DH * T - 360)
        target_x = max(0, min(max_x, tx))
        target_y = max(0, min(max_y, ty))
        self.cam[0] += (target_x - self.cam[0]) * 0.16
        self.cam[1] += (target_y - self.cam[1]) * 0.16

    def _draw_throne_room(self, surf, camx, camy, combat):
        w = self.world
        # red carpet from the dais to the entrance
        for y in range(4, 22):
            for x in (16, 17, 18):
                if w.grid[y][x] == FLOOR:
                    sx, sy = x * T - camx, y * T - camy
                    pygame.draw.rect(surf, (96, 20, 32) if x == 17 else (70, 14, 26), (sx, sy, T, T))
                    if x == 16 or x == 18:
                        pygame.draw.line(surf, (190, 140, 70), (sx + (0 if x == 16 else 31), sy),
                                         (sx + (0 if x == 16 else 31), sy + 31), 1)
        # dais steps
        for y in range(2, 6):
            for x in range(13, 23):
                if (x, y) in ((16, y), (17, y), (18, y)):
                    continue
                sx, sy = x * T - camx, y * T - camy
                pygame.draw.rect(surf, (52, 40, 62), (sx, sy, T, T))
                pygame.draw.rect(surf, (88, 70, 100), (sx, sy, T, T), 1)
        # the throne (drawn behind the seated boss)
        tx, ty = w.throne
        bx, by = tx * T + 16 - camx, ty * T + 30 - camy
        pygame.draw.rect(surf, (40, 30, 48), (bx - 30, by - 92, 60, 96), border_radius=6)
        pygame.draw.rect(surf, (96, 76, 110), (bx - 30, by - 92, 60, 96), 2, border_radius=6)
        pygame.draw.polygon(surf, (60, 46, 70), [(bx - 30, by - 92), (bx - 18, by - 112), (bx - 6, by - 92)])
        pygame.draw.polygon(surf, (60, 46, 70), [(bx + 30, by - 92), (bx + 18, by - 112), (bx + 6, by - 92)])
        pygame.draw.rect(surf, (110, 22, 36), (bx - 20, by - 80, 40, 60), border_radius=4)
        pygame.draw.rect(surf, (52, 40, 62), (bx - 36, by - 26, 72, 20), border_radius=4)       # seat
        pygame.draw.rect(surf, (96, 76, 110), (bx - 36, by - 26, 72, 20), 1, border_radius=4)
        pygame.draw.rect(surf, (36, 28, 44), (bx - 40, by - 54, 10, 40))                       # arm rests
        pygame.draw.rect(surf, (36, 28, 44), (bx + 30, by - 54, 10, 40))
        pulse = (math.sin(self.t * 3) + 1) / 2
        pygame.draw.circle(surf, (200, 60, 70), (bx, by - 100), 3 + int(pulse * 2))
        # the sealed east wall: a dim rune that wakes up once the path opens
        if not w.exit_open:
            sx, sy = 28 * T - camx, 13 * T - camy
            col = (120 + int(60 * pulse), 40, 150 + int(40 * pulse))
            pygame.draw.circle(surf, col, (sx + 16, sy + 16), 12, 1)
            pygame.draw.line(surf, col, (sx + 6, sy + 16), (sx + 26, sy + 16), 1)
            pygame.draw.line(surf, col, (sx + 16, sy + 6), (sx + 16, sy + 26), 1)

    def _draw_portal(self, surf, camx, camy):
        ex, ey = self.world.exit_tile
        cx, cy = ex * T + 16 - camx, ey * T + 16 - camy
        pulse = (math.sin(self.t * 4) + 1) / 2
        # glowing path along the corridor
        for x in range(28, ex):
            for y in (12, 13, 14):
                a = pygame.Surface((T, T), pygame.SRCALPHA)
                a.fill((150, 90, 230, 28 + int(20 * pulse)))
                surf.blit(a, (x * T - camx, y * T - camy))
        glow = pygame.Surface((140, 140), pygame.SRCALPHA)
        for r in range(66, 6, -6):
            pygame.draw.circle(glow, (160, 100, 245, int(2.2 * (66 - r))), (70, 70), r)
        surf.blit(glow, (cx - 70, cy - 70), special_flags=pygame.BLEND_RGBA_ADD)
        for i in range(3):
            a = self.t * (2.0 + i * .6) + i * 2.1
            rx, ry = 22 - i * 5, 26 - i * 6
            pygame.draw.ellipse(surf, (200 - i * 30, 150, 255), (cx - rx, cy - ry, rx * 2, ry * 2), 2)
            pygame.draw.circle(surf, (255, 240, 255), (int(cx + math.cos(a) * rx), int(cy + math.sin(a) * ry)), 2)
        pygame.draw.circle(surf, (240, 220, 255), (cx, cy), 5 + int(pulse * 3))

    def draw_tile(self, surf, img, sx, sy):
        surf.blit(img, (sx, sy))

    def draw(self, surf, player, shadow, combat=None):
        camx, camy = int(self.cam[0]), int(self.cam[1])
        if combat:
            ox, oy = combat.shake_offset()
            camx, camy = camx + ox, camy + oy
        surf.fill((4, 4, 7))

        # Full, coherent stone floor/wall layout.
        for y in range(DH):
            for x in range(DW):
                sx, sy = x * T - camx, y * T - camy
                if sx < -T or sx >= 640 or sy < -T or sy >= 360:
                    continue
                tile = self.world.grid[y][x]
                if tile == WALL:
                    img = (self.wall2 if (x * 3 + y) % 4 == 0 else self.wall)
                    self.draw_tile(surf, img, sx, sy)
                    # Deep seam along the bottom of wall blocks.
                    pygame.draw.line(surf, (18, 17, 22), (sx, sy + 30), (sx + 31, sy + 30), 2)
                elif tile == WATER:
                    self.draw_tile(surf, self.water, sx, sy)
                elif tile == LAVA:
                    self.draw_tile(surf, self.lava, sx, sy)
                elif tile == PILLAR:
                    self.draw_tile(surf, self.floor_a, sx, sy)
                    self.draw_tile(surf, self.ornament, sx, sy)
                else:
                    img = self.floor_b if (x + y) % 5 == 0 else self.floor_a
                    self.draw_tile(surf, img, sx, sy)

        # Add a darker grout to the whole floor so it reads as underground stone.
        grout = pygame.Surface((640, 360), pygame.SRCALPHA)
        for x in range((-camx) % T, 640, T):
            pygame.draw.line(grout, (8, 8, 12, 45), (x, 0), (x, 360), 1)
        for y in range((-camy) % T, 360, T):
            pygame.draw.line(grout, (8, 8, 12, 45), (0, y), (640, y), 1)
        surf.blit(grout, (0, 0))

        # Staircases / transitions.
        for kind, pos in (("up", self.world.up), ("down", self.world.down)):
            if not pos:
                continue
            x, y = pos
            sx, sy = x * T - camx, y * T - camy
            surf.blit(self.stairs, (sx, sy))
            if kind == "down" and combat and not combat.cleared:  # sealed until every foe on the floor is dead
                pulse = (math.sin(self.t * 5) + 1) / 2
                pygame.draw.rect(surf, (36, 8, 12), (sx + 2, sy + 2, 28, 28), border_radius=5)
                pygame.draw.circle(surf, (170, 40, 50), (sx + 16, sy + 16), 14, 2)
                pygame.draw.circle(surf, (240, 110, 100), (sx + 16, sy + 16), 7 + int(pulse * 3), 1)
                pygame.draw.line(surf, (215, 70, 70), (sx + 8, sy + 8), (sx + 24, sy + 24), 2)
                pygame.draw.line(surf, (215, 70, 70), (sx + 24, sy + 8), (sx + 8, sy + 24), 2)
                continue
            if kind == "up" and combat and combat.boss_lock:      # sealed while the final boss lives
                pulse = (math.sin(self.t * 6) + 1) / 2
                pygame.draw.rect(surf, (30, 10, 44), (sx + 2, sy + 2, 28, 28), border_radius=5)
                pygame.draw.circle(surf, (150, 60, 200), (sx + 16, sy + 16), 14, 2)
                pygame.draw.circle(surf, (225, 130, 255), (sx + 16, sy + 16), 7 + int(pulse * 3), 1)
                pygame.draw.line(surf, (190, 90, 235), (sx + 8, sy + 8), (sx + 24, sy + 24), 2)
                pygame.draw.line(surf, (190, 90, 235), (sx + 24, sy + 8), (sx + 8, sy + 24), 2)
                continue
            # directional marker
            pygame.draw.rect(surf, (8, 7, 12, 170), (sx + 5, sy + 4, 22, 22), border_radius=4)
            if kind == "down":
                pygame.draw.polygon(surf, (210, 190, 225), [(sx + 16, sy + 8), (sx + 8, sy + 18), (sx + 24, sy + 18)])
            else:
                pygame.draw.polygon(surf, (210, 190, 225), [(sx + 8, sy + 14), (sx + 24, sy + 14), (sx + 16, sy + 6)])

        # Level 5 altar: the purple gate to the throne room (pulses and brightens once the floor is clear).
        if self.level == 5 and self.world.altar:
            x, y = self.world.altar
            sx, sy = x * T - camx, y * T - camy
            ready = bool(combat and combat.cleared and not combat.boss_defeated)
            pulse = (math.sin(self.t * 4) + 1) / 2
            surf.blit(self.ornament, (sx, sy))
            pygame.draw.rect(surf, (70, 46, 84), (sx + 8, sy + 6, 16, 20), border_radius=4)
            pygame.draw.circle(surf, (145, 92, 190) if not ready else (190, 120, 245), (sx + 16, sy + 11), 5)
            if ready:
                pygame.draw.circle(surf, (225, 150, 255), (sx + 16, sy + 11), 8 + int(pulse * 4), 1)
                pygame.draw.circle(surf, (170, 90, 230), (sx + 16, sy + 16), 17 + int(pulse * 3), 1)

        # Level 6: throne room dressing (carpet, dais, throne, sealed wall / portal).
        if self.level == 6:
            self._draw_throne_room(surf, camx, camy, combat)

        # Cracks/rubble details.
        for x, y in self.cracks:
            px, py = x * T - camx + 7, y * T - camy + 19
            pygame.draw.line(surf, (42, 39, 48), (px, py), (px + 7, py - 5), 2)
            pygame.draw.line(surf, (42, 39, 48), (px + 7, py - 5), (px + 11, py + 1), 1)

        # Torch flames and local warm light sources.
        for tx, ty in self.torches:
            px, py = tx * T + 16 - camx, ty * T + 10 - camy
            glow = pygame.Surface((112, 112), pygame.SRCALPHA)
            for r in range(50, 4, -5):
                alpha = int(1.7 * max(0, 50 - r))
                pygame.draw.circle(glow, (230, 105, 35, alpha), (56, 56), r)
            surf.blit(glow, (px - 56, py - 56), special_flags=pygame.BLEND_RGBA_ADD)
            flick = int((math.sin(self.t * 9 + tx * 0.7) + 1) * 1.5)
            pygame.draw.rect(surf, (70, 43, 30), (px - 2, py + 5, 4, 9))
            pygame.draw.circle(surf, (245, 134, 45), (px, py + flick), 6)
            pygame.draw.circle(surf, (255, 232, 145), (px, py + flick - 1), 2)

        if self.level == 6 and self.world.exit_open:
            self._draw_portal(surf, camx, camy)

        # Monsters and the player (depth-sorted together by the combat system).
        if combat:
            combat.draw_entities(surf, camx, camy, shadow)
        else:
            player.draw(surf, (camx, camy), shadow)

        # The dungeon is deliberately very dark: visibility comes from torches + player lantern.
        darkness = pygame.Surface((640, 360), pygame.SRCALPHA)
        # Throne room (level 6) is lit up; every other floor stays dark.
        darkness.fill((0, 0, 5, 90 if self.level == 6 else 226))
        px, py = int(player.x - camx), int(player.y - camy - 12)
        pygame.draw.circle(darkness, (0, 0, 0, 0), (px, py), 92)
        pygame.draw.circle(darkness, (0, 0, 0, 38), (px, py), 132)
        for tx, ty in self.torches:
            lx, ly = tx * T + 16 - camx, ty * T + 10 - camy
            pygame.draw.circle(darkness, (0, 0, 0, 40), (lx, ly), 130 if self.level == 6 else 82)
            pygame.draw.circle(darkness, (0, 0, 0, 0), (lx, ly), 80 if self.level == 6 else 48)
        if self.level == 6 and self.world.exit_open:
            ex, ey = self.world.exit_tile
            lx, ly = ex * T + 16 - camx, ey * T + 16 - camy
            pygame.draw.circle(darkness, (0, 0, 0, 60), (lx, ly), 150)
            pygame.draw.circle(darkness, (0, 0, 0, 0), (lx, ly), 80)
        if combat:
            combat.cut_light(darkness, camx, camy)
        surf.blit(darkness, (0, 0))
        if combat:
            combat.draw_fx(surf, camx, camy)      # glowing spells / telegraphs sit above the darkness

        # Subtle vignette on top of the darkness.
        vignette = pygame.Surface((640, 360), pygame.SRCALPHA)
        for i in range(24):
            pygame.draw.rect(vignette, (0, 0, 0, 5), (i, i, 640 - i * 2, 360 - i * 2), 1)
        surf.blit(vignette, (0, 0))