"""Moving things in the world: the hero, villagers, animals, plus the dialogue box."""
import math
import random

import pygame

T = 32
DIRS = ("down", "left", "right", "up")
VEC = {"down": (0, 1), "left": (-1, 0), "right": (1, 0), "up": (0, -1)}
CELL_W, CELL_H = 36, 52


class Mover:
    FW, FH = 12, 8

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)   # foot-centre in pixels
        self.dir = "down"
        self.anim = 0.0
        self.moving = False

    @property
    def foot(self):
        return pygame.Rect(int(self.x - self.FW / 2), int(self.y - self.FH), self.FW, self.FH)

    def rect_at(self, x, y):
        return pygame.Rect(int(x - self.FW / 2), int(y - self.FH), self.FW, self.FH)

    def step(self, dx, dy, world, others=()):
        """Move with axis-separated collision. Returns True if it moved."""
        moved = False
        for ax in (0, 1):
            nx = self.x + (dx if ax == 0 else 0)
            ny = self.y + (dy if ax == 1 else 0)
            if (nx, ny) == (self.x, self.y):
                continue
            r = self.rect_at(nx, ny)
            if world.rect_blocked(r):
                continue
            cur = self.foot
            if any(r.colliderect(o) and not cur.colliderect(o) for o in others):
                continue
            self.x, self.y = nx, ny
            moved = True
        return moved


class Player(Mover):
    def __init__(self, x, y, sheet):
        super().__init__(x, y)
        self.sheet = sheet
        self.walk = 92.0
        self.run = 150.0
        self.running = False
        self.footstep_t = 0.0

    def update(self, dt, keys, world, others):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        self.running = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        self.moving = False
        if dx or dy:
            sp = self.run if self.running else self.walk
            n = math.hypot(dx, dy)
            vx, vy = dx / n * sp * dt, dy / n * sp * dt
            if abs(dx) >= abs(dy) and dx:
                self.dir = "right" if dx > 0 else "left"
            elif dy:
                self.dir = "down" if dy > 0 else "up"
            self.moving = self.step(vx, vy, world, others)
        if self.moving:
            self.anim += dt * (11 if self.running else 8)
        else:
            self.anim = 0

    def frame(self):
        return [0, 1, 0, 2][int(self.anim) % 4] if self.moving else 0

    def draw(self, surf, cam, shadow):
        sx, sy = int(self.x - cam[0]), int(self.y - cam[1])
        surf.blit(shadow, (sx - shadow.get_width() // 2, sy - 6))
        row = DIRS.index(self.dir)
        cw, ch = self.sheet.get_width() // 3, self.sheet.get_height() // 4
        surf.blit(self.sheet, (sx - cw // 2, sy - ch + 2), (self.frame() * cw, row * ch, cw, ch))


class NPC(Mover):
    def __init__(self, data, sheet, portrait, world):
        tx, ty = world.nearest_walkable(*data["home"])
        super().__init__(tx * T + 16, ty * T + 28)
        self.d = data
        self.id = data["id"]
        self.name = data["name"]
        self.role = data["role"]
        self.sheet = sheet
        self.portrait = portrait
        self.home = (tx, ty)
        self.radius = data["radius"]
        self.speed = data["speed"]
        self.talk_count = 0
        self.talking = False
        self.said_final = False
        self.state = "idle"
        self.timer = random.uniform(0.5, 3.0)
        self.steps_left = 0.0
        self.dir = random.choice(DIRS)

    def lines(self, others_met):
        d = self.d
        if self.talk_count == 0:
            out = d["intro"]
        elif self.id == "elder" and others_met and not self.said_final:
            self.said_final = True
            out = d["all_met"]
        else:
            ch = d["chatter"]
            out = ch[(self.talk_count - 1) % len(ch)]
        self.talk_count += 1
        return out

    def face(self, tx, ty):
        dx, dy = tx - self.x, ty - self.y
        if abs(dx) > abs(dy):
            self.dir = "right" if dx > 0 else "left"
        else:
            self.dir = "down" if dy > 0 else "up"

    def update(self, dt, world, others):
        if self.talking:
            self.moving = False
            self.anim = 0
            return
        self.moving = False
        if self.state == "idle":
            self.timer -= dt
            if self.timer <= 0:
                for _ in range(6):
                    d = random.choice(DIRS)
                    n = random.randint(1, 3)
                    hx, hy = self.home
                    tx = int(self.x // T) + VEC[d][0] * n
                    ty = int((self.y - 4) // T) + VEC[d][1] * n
                    if max(abs(tx - hx), abs(ty - hy)) <= self.radius and world.walkable_tile(tx, ty):
                        self.dir = d
                        self.steps_left = n * T
                        self.state = "walk"
                        break
                else:
                    self.timer = random.uniform(1.0, 3.0)
        else:
            vx, vy = VEC[self.dir]
            amt = min(self.speed * dt, self.steps_left)
            if self.step(vx * amt, vy * amt, world, others) and self.steps_left > 0:
                self.steps_left -= amt
                self.moving = True
                self.anim += dt * 6
            else:
                self.steps_left = 0
            if self.steps_left <= 0:
                self.state = "idle"
                self.timer = random.uniform(1.5, 5.0)

    def frame(self):
        return [0, 1, 0, 2][int(self.anim) % 4] if self.moving else 0

    def draw(self, surf, cam, shadow):
        sx, sy = int(self.x - cam[0]), int(self.y - cam[1])
        surf.blit(shadow, (sx - shadow.get_width() // 2, sy - 6))
        row = DIRS.index(self.dir)
        cw, ch = self.sheet.get_width() // 3, self.sheet.get_height() // 4
        surf.blit(self.sheet, (sx - cw // 2, sy - ch + 2), (self.frame() * cw, row * ch, cw, ch))


class Animal(Mover):
    FW, FH = 10, 6

    def __init__(self, kind, x, y, frames, speed, radius, world):
        tx, ty = world.nearest_walkable(int(x // T), int(y // T))
        super().__init__(tx * T + 16, ty * T + 24)
        self.kind = kind
        self.frames = frames          # list of Surfaces (facing right)
        self.flip = [pygame.transform.flip(f, True, False) for f in frames]
        self.speed = speed
        self.radius = radius
        self.home = (tx, ty)
        self.state = "idle"
        self.timer = random.uniform(0.3, 2.5)
        self.steps_left = 0
        self.face_left = random.random() < 0.5
        self.peck = False
        self.vec = (0, 0)
        self.talk = 0

    def update(self, dt, world):
        self.moving = False
        if self.state == "idle":
            self.timer -= dt
            if self.kind == "chicken" and random.random() < dt * 2.2:
                self.peck = not self.peck
            if self.timer <= 0:
                for _ in range(6):
                    d = random.choice(DIRS)
                    n = random.randint(1, 3)
                    hx, hy = self.home
                    tx = int(self.x // T) + VEC[d][0] * n
                    ty = int((self.y - 4) // T) + VEC[d][1] * n
                    if max(abs(tx - hx), abs(ty - hy)) <= self.radius and world.walkable_tile(tx, ty):
                        self.vec = VEC[d]
                        if d == "left":
                            self.face_left = True
                        elif d == "right":
                            self.face_left = False
                        self.steps_left = n * T * 0.8
                        self.state = "walk"
                        self.peck = False
                        break
                else:
                    self.timer = 1.0
        else:
            amt = min(self.speed * dt, self.steps_left)
            if self.step(self.vec[0] * amt, self.vec[1] * amt, world):
                self.steps_left -= amt
                self.moving = True
                self.anim += dt * 8
            else:
                self.steps_left = 0
            if self.steps_left <= 0:
                self.state = "idle"
                self.timer = random.uniform(1.0, 4.0)

    def image(self):
        if self.kind == "chicken":
            idx = (int(self.anim) % 2) if self.moving else (2 if self.peck else 0)
        else:
            idx = (int(self.anim) % 2) if self.moving else 0
        return (self.flip if self.face_left else self.frames)[min(idx, len(self.frames) - 1)]

    def draw(self, surf, cam, shadow):
        sx, sy = int(self.x - cam[0]), int(self.y - cam[1])
        sw = pygame.transform.scale(shadow, (shadow.get_width() * 2 // 3, shadow.get_height() * 2 // 3))
        surf.blit(sw, (sx - sw.get_width() // 2, sy - 4))
        img = self.image()
        surf.blit(img, (sx - img.get_width() // 2, sy - img.get_height() + 2))


class Dialogue:
    LINES_PER_PAGE = 3

    def __init__(self, font, box, tag, arrow, portrait_pos=(12, 14)):
        self.font = font
        self.box, self.tag, self.arrow = box, tag, arrow
        self.active = False
        self.speaker = ""
        self.role = ""
        self.portrait = None
        self.pages = []
        self.pi = 0
        self.typed = 0.0
        self.t = 0.0
        self.on_end = None
        self.last_blip = 0

    def wrap(self, text, width):
        words, lines, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.font.size(test)[0] <= width:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def start(self, speaker, role, lines, portrait=None, on_end=None):
        self.active = True
        self.speaker, self.role, self.portrait = speaker, role, portrait
        width = 600 - (88 if portrait else 28) - 14
        self.pages = []
        for ln in lines:
            wrapped = self.wrap(ln, width)
            for i in range(0, len(wrapped), self.LINES_PER_PAGE):
                self.pages.append(wrapped[i:i + self.LINES_PER_PAGE])
        self.pi = 0
        self.typed = 0.0
        self.last_blip = 0
        self.on_end = on_end

    @property
    def full(self):
        return "\n".join(self.pages[self.pi])

    def update(self, dt, sfx=None):
        if not self.active:
            return
        self.t += dt
        n = len(self.full)
        if self.typed < n:
            self.typed = min(n, self.typed + dt * 55)
            idx = int(self.typed)
            if idx - self.last_blip >= 3 and sfx is not None:
                ch = self.full[max(0, idx - 1)]
                if ch not in " \n":
                    sfx.play()
                self.last_blip = idx

    def advance(self):
        n = len(self.full)
        if self.typed < n:
            self.typed = n
            return None
        if self.pi + 1 < len(self.pages):
            self.pi += 1
            self.typed = 0.0
            self.last_blip = 0
            return "page"
        self.active = False
        if self.on_end:
            self.on_end()
        return "end"

    def draw(self, surf):
        if not self.active:
            return
        bw, bh = self.box.get_size()
        x = (surf.get_width() - bw) // 2
        y = surf.get_height() - bh - 8
        surf.blit(self.box, (x, y))
        tx = x + 16
        if self.portrait:
            surf.blit(self.portrait, (x + 12, y + 12))
            tx = x + 94
        # name tag
        label = self.speaker + (f"  -  {self.role}" if self.role else "")
        tw = self.font.size(label)[0] + 20
        tag = pygame.transform.scale(self.tag, (max(90, tw), 22))
        surf.blit(tag, (x + 12, y - 12))
        surf.blit(self.font.render(label, True, (255, 246, 226)), (x + 22, y - 9))
        shown = self.full[:int(self.typed)].split("\n")
        for i, ln in enumerate(shown):
            surf.blit(self.font.render(ln, True, (58, 38, 28)), (tx, y + 16 + i * 20))
        if self.typed >= len(self.full):
            bob = int(math.sin(self.t * 6) * 2)
            surf.blit(self.arrow, (x + bw - 26, y + bh - 20 + bob))
