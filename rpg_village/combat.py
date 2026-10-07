"""Real-time battle system for The Hollow Below.

PLAYER
  Left mouse (hold)        attack with the equipped weapon, aimed at the cursor
  Right mouse / scroll     swap between SWORD and MAGIC
  SPACE                    dodge roll (brief invincibility, short cooldown)

ENEMIES  (every dungeon monster is hostile)
  melee  - chase you, wind up (red danger zone appears), then swing. Dodge or step away.
  mage   - keep their distance, charge (aim line appears), then fire slow bolts. Dodge or roll through.

Player health is infinite for now: set INFINITE_HP = False to turn damage on.

FINAL BOSS  (boss.py)
  Clear every monster on floor 5 and GRIMHORN, Warden of the Hollow, rises from the floor. The stairs stay sealed
  until he is dead; then a victory screen is shown.
"""
import array
import math
import random
from collections import deque

import pygame

from dungeon import DH, DW, FLOOR, LAVA, PILLAR, T, WALL, WATER
from entities import DIRS, Mover
from inventory import ITEMS, Inventory

# --------------------------------------------------------------------------- tuning
INFINITE_HP = False          # <- flip to False later to make enemy hits actually hurt
PLAYER_MAX_HP = 100
MAX_MP = 100                # mana pool
FIREBALL_COST = 5           # mana per fireball
MANA_ON_KILL = 6            # mana regained for every enemy you defeat...
MANA_ON_KILL_BIG = 10       # ...and for the big ones (ogres, brutes, drakes, wyrms)
MANA_ON_BOSS = 25
# chance that a slain monster drops a potion straight into your pack (checked once per item)
DROPS = dict(health_potion=0.12, mana_potion=0.12)
BOSS_DROPS = dict(health_potion=3, mana_potion=3)
FIRE = (255, 140, 50)       # fireball colour
CHEST = 14                  # px between a character's feet and its chest (hit / aim centre)

SWORD = dict(damage=14, cooldown=0.36, duration=0.20, reach=46, arc=135.0, knock=260.0, lunge=95.0)
MAGIC = dict(damage=9, cooldown=0.42, duration=0.16, speed=300.0, radius=5, knock=120.0, life=1.15)
ROLL = dict(duration=0.30, speed=240.0, iframes=0.36, cooldown=0.70)

BLOCKING = (WALL, WATER, LAVA, PILLAR)     # stops walking
SIGHT_BLOCK = (WALL, PILLAR)               # stops vision and projectiles
NEIGH8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))
VIEW_W, VIEW_H = 640, 360

# --------------------------------------------------------------------------- monster catalogue
# sheet/char: which RPG-Maker style character (0-7, left->right, top->bottom) on Monster1/Monster2.
MONSTERS = {
    # ---- melee
    "skeleton": dict(sheet="Monster1", char=1, kind="melee", hp=34, speed=54, dmg=9, reach=30,
                     windup=.50, recover=.55, cd=.8, lunge=70, color=(225, 225, 235)),
    "wraith":   dict(sheet="Monster1", char=0, kind="melee", hp=26, speed=64, dmg=8, reach=28,
                     windup=.42, recover=.50, cd=.7, lunge=90, color=(205, 70, 70), fly=True),
    "ogre":     dict(sheet="Monster1", char=2, kind="melee", hp=70, speed=36, dmg=18, reach=38,
                     windup=.80, recover=.85, cd=1.1, lunge=45, color=(215, 160, 110), big=True),
    "gargoyle": dict(sheet="Monster1", char=3, kind="melee", hp=30, speed=78, dmg=9, reach=28,
                     windup=.38, recover=.45, cd=.6, lunge=130, color=(80, 190, 190), fly=True),
    "brute":    dict(sheet="Monster1", char=7, kind="melee", hp=64, speed=44, dmg=16, reach=36,
                     windup=.70, recover=.80, cd=1.0, lunge=50, color=(225, 170, 70), big=True),
    "slime":    dict(sheet="Monster2", char=2, kind="melee", hp=22, speed=42, dmg=6, reach=24,
                     windup=.45, recover=.50, cd=.8, lunge=60, color=(110, 170, 255)),
    "slime_g":  dict(sheet="Monster2", char=6, kind="melee", hp=26, speed=46, dmg=7, reach=24,
                     windup=.45, recover=.50, cd=.8, lunge=60, color=(90, 225, 150)),
    "drake":    dict(sheet="Monster2", char=1, kind="melee", hp=58, speed=50, dmg=14, reach=34,
                     windup=.60, recover=.70, cd=.9, lunge=80, color=(130, 210, 80), big=True),
    "wyrm":     dict(sheet="Monster2", char=5, kind="melee", hp=78, speed=44, dmg=18, reach=36,
                     windup=.70, recover=.80, cd=1.0, lunge=70, color=(240, 110, 80), big=True),
    # ---- mages (ranged)
    "dark_mage": dict(sheet="Monster1", char=6, kind="mage", hp=22, speed=46, dmg=8, windup=.75,
                      cd=2.4, bolt=140, color=(175, 95, 255)),
    "fire_mage": dict(sheet="Monster1", char=4, kind="mage", hp=24, speed=44, dmg=9, windup=.75,
                      cd=2.2, bolt=150, color=(255, 145, 45), fly=True),
    "ice_mage":  dict(sheet="Monster1", char=5, kind="mage", hp=22, speed=44, dmg=8, windup=.75,
                      cd=2.3, bolt=160, color=(130, 225, 255)),
    "witch":     dict(sheet="Monster2", char=3, kind="mage", hp=20, speed=52, dmg=7, windup=.80,
                      cd=2.8, bolt=130, fan=3, spread=16, color=(255, 115, 205), fly=True),
    "imp_mage":  dict(sheet="Monster2", char=7, kind="mage", hp=24, speed=50, dmg=7, windup=.80,
                      cd=2.7, bolt=135, fan=3, spread=16, color=(130, 255, 150)),
}

# (melee pool, mage pool) for each floor
FLOOR_POOLS = {
    1: (("skeleton", "wraith"), ("dark_mage",)),
    2: (("slime", "slime_g", "skeleton"), ("ice_mage",)),
    3: (("gargoyle", "ogre", "wraith"), ("fire_mage",)),
    4: (("gargoyle", "brute", "skeleton"), ("ice_mage", "witch")),
    5: (("drake", "wyrm", "ogre", "brute"), ("dark_mage", "imp_mage", "witch")),
}

DIR_ROW = {"down": 0, "left": 1, "right": 2, "up": 3}


# --------------------------------------------------------------------------- small helpers
def dir_from_vec(vx, vy):
    if abs(vx) >= abs(vy):
        return "right" if vx > 0 else "left"
    return "down" if vy > 0 else "up"


def ang_diff(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def scale_color(c, k):
    k = max(0.0, min(1.0, k))
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))


def glow(fx, x, y, r, color, k=1.0):
    """Stepped additive glow (drawn on the black fx layer)."""
    for rr, kk in ((r, .22), (r * .62, .5), (r * .3, 1.0)):
        if rr >= 1:
            pygame.draw.circle(fx, scale_color(color, kk * k), (int(x), int(y)), int(rr))


def draw_infinity(surf, cx, cy, a, color):
    pts = []
    for i in range(28):
        t = i / 28 * 2 * math.pi
        d = 1 + math.sin(t) ** 2
        pts.append((cx + a * math.cos(t) / d, cy + a * math.sin(t) * math.cos(t) / d))
    pygame.draw.lines(surf, color, True, pts, 2)


def build_frames(assets):
    """Returns get(sheet, char) -> {dir: [frame0, frame1, frame2]} (32x32 surfaces, cached)."""
    cache = {}

    def get(sheet, char):
        key = (sheet, char)
        if key not in cache:
            img = assets[sheet]
            bx, by = (char % 4) * 96, (char // 4) * 128
            cache[key] = {d: [img.subsurface((bx + c * 32, by + r * 32, 32, 32)).copy() for c in range(3)]
                          for d, r in DIR_ROW.items()}
        return cache[key]
    return get


# --------------------------------------------------------------------------- sound (synthesised, no asset files)
class Sfx:
    def __init__(self):
        self.s = {}
        try:
            init = pygame.mixer.get_init()
            if not init or init[1] != -16:
                return
            self.rate, _fmt, self.ch = init
            self._build()
        except Exception:
            self.s = {}

    def _synth(self, dur, fn, vol):
        n = int(self.rate * dur)
        buf = array.array("h")
        for i in range(n):
            v = max(-1.0, min(1.0, fn(i / self.rate, i / n))) * vol
            smp = int(v * 32767)
            buf.append(smp)
            if self.ch == 2:
                buf.append(smp)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    @staticmethod
    def _noise(k):
        y = [0.0]

        def f():
            y[0] += k * (random.uniform(-1, 1) - y[0])
            return y[0]
        return f

    def _build(self):
        tau = 2 * math.pi
        nz = self._noise
        n1, n2, n3, n4, n5 = nz(.25), nz(.5), nz(.15), nz(.12), nz(.6)
        sn = math.sin
        mk = self._synth
        self.s["swing"] = mk(.16, lambda t, p: n1() * sn(math.pi * p) ** 1.5 * 1.7, .45)
        self.s["hit"] = mk(.14, lambda t, p: (sn(tau * (180 - 120 * p) * t) * .8 + n2() * .6) * (1 - p) ** 2, .6)
        self.s["cast"] = mk(.22, lambda t, p: sn(tau * (350 + 700 * p) * t + 3 * sn(tau * 18 * t)) * .7 * (1 - p) ** 1.4, .35)
        self.s["boom"] = mk(.20, lambda t, p: (n3() * 1.8 + sn(tau * 70 * t) * .6) * (1 - p) ** 2, .5)
        self.s["charge"] = mk(.55, lambda t, p: sn(tau * (180 + 320 * p) * t) * .5 * p * (1 - p * .3), .25)
        self.s["roll"] = mk(.22, lambda t, p: n4() * sn(math.pi * p) * 1.8, .4)
        self.s["hurt"] = mk(.22, lambda t, p: (1 if sn(tau * (240 - 110 * p) * t) > 0 else -1) * .5 * (1 - p), .35)
        self.s["die"] = mk(.38, lambda t, p: (((t * (300 - 220 * p)) % 1) * 2 - 1) * .6 * (1 - p) ** 1.3 + n5() * .25 * (1 - p), .4)
        self.s["roar"] = mk(1.1, lambda t, p: ((((t * (62 + 22 * sn(tau * 5 * t))) % 1) * 2 - 1) * .8 + n3() * .7)
                            * sn(math.pi * p) ** .6, .55)
        self.s["slam"] = mk(.42, lambda t, p: (n3() * 2.2 + sn(tau * (62 - 36 * p) * t) * 1.4) * (1 - p) ** 2.2, .7)

        def win(t, p):
            seq = (392, 494, 587, 784)
            i, lp = min(3, int(p * 4)), (p * 4) % 1
            return sn(tau * seq[i] * t) * .5 * (1 - lp) ** .6 + sn(tau * seq[i] * 2 * t) * .15 * (1 - lp)
        self.s["win"] = mk(1.4, win, .4)
        self.s["swap"] = mk(.08, lambda t, p: sn(tau * (700 if p < .5 else 1000) * t) * .6 * (1 - (p % .5) * 2), .35)

    def play(self, name):
        s = self.s.get(name)
        if s:
            try:
                s.play()
            except Exception:
                pass


# --------------------------------------------------------------------------- projectiles
class Bolt:
    def __init__(self, x, y, ang, speed, dmg, owner, color, radius, life):
        self.x, self.y = x, y            # chest-height world position
        self.vx, self.vy = math.cos(ang) * speed, math.sin(ang) * speed
        self.speed = speed
        self.ang = ang
        self.dmg, self.owner, self.color = dmg, owner, color
        self.radius, self.life = radius, life
        self.dead = False
        self.t = 0.0


# --------------------------------------------------------------------------- enemies
class Enemy(Mover):
    is_boss = False
    chest = CHEST                  # height of the hit / aim centre above the feet (the boss is taller)

    def __init__(self, key, tx, ty, level, getframes):
        super().__init__(tx * T + 16, ty * T + 26)
        d = MONSTERS[key]
        self.key, self.d, self.kind, self.level = key, d, d["kind"], level
        self.big = d.get("big", False)
        self.fly = d.get("fly", False)
        self.FW = 18 if self.big else 12
        self.r = 15 if self.big else 11                  # hit radius around the chest
        self.frames = getframes(d["sheet"], d["char"])
        lv = level - 1
        self.max_hp = int(d["hp"] * (1 + 0.16 * lv))
        self.hp = self.max_hp
        self.dmg = int(round(d["dmg"] * (1 + 0.12 * lv)))
        self.speed = d["speed"] * (1 + 0.04 * lv)
        self.cd_base = d["cd"] * (1 - 0.04 * lv)
        self.state = "idle"        # idle chase windup strike recover stagger dead
        self.state_t = 0.0
        self.cd = random.uniform(0.4, 1.2)
        self.aim = 0.0
        self.t = random.uniform(0, 6)
        self.flash = 0.0
        self.hp_show = 0.0
        self.kv = [0.0, 0.0]
        self.kb_t = 0.0
        self.dead_t = 0.0
        self.stuck_t = 0.0
        self.strafe = random.choice((-1, 1))
        self.strafe_t = random.uniform(1.0, 2.5)
        self.dir = random.choice(DIRS)

    # ---- queries used by the combat manager
    @property
    def alive(self):
        return self.state != "dead"

    def zone(self):
        """Melee danger zone (cx, cy, radius) in world coords."""
        reach = self.d["reach"]
        return (self.x + math.cos(self.aim) * reach * .55,
                self.y - 12 + math.sin(self.aim) * reach * .55,
                reach * .72 + 4)

    def windup_progress(self):
        total = self.d["windup"]
        return max(0.0, min(1.0, 1 - self.state_t / total)) if self.state == "windup" else 0.0

    # ---- behaviour
    def wake(self, cb):
        if self.state == "idle":
            self.state = "chase"
            cb.alert_near(self)

    def die(self, cb):
        self.state, self.dead_t = "dead", 0.0

    def move(self, cb, vx, vy, dt, mul=1.0):
        sp = self.speed * mul * dt
        moved = self.step(vx * sp, vy * sp, cb.world, cb.feet_except(self))
        if moved:
            self.moving = True
            self.anim += dt * 7
        return moved

    def circle(self, cb, dt, ux, uy, mul):
        self.strafe_t -= dt
        if self.strafe_t <= 0:
            self.strafe = -self.strafe
            self.strafe_t = random.uniform(1.0, 2.6)
        if not self.move(cb, -uy * self.strafe, ux * self.strafe, dt, mul):
            self.strafe = -self.strafe

    def approach(self, cb, dt, mul=1.0):
        p = cb.player
        dx, dy = p.x - self.x, p.y - self.y
        d = math.hypot(dx, dy) or 1.0
        direct = self.stuck_t <= 0 and cb.walk_clear(self.x, self.y, p.x, p.y)
        vx, vy = dx / d, dy / d
        if not direct:
            nxt = cb.flow_step(self)
            if nxt is not None:
                ddx, ddy = nxt[0] - self.x, nxt[1] - self.y
                dd = math.hypot(ddx, ddy) or 1.0
                vx, vy = ddx / dd, ddy / dd
        self.dir = dir_from_vec(vx, vy)
        if not self.move(cb, vx, vy, dt, mul) and direct:
            self.stuck_t = 0.6          # straight line is blocked by a corner: use the path map for a bit

    def update(self, dt, cb):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        self.hp_show = max(0.0, self.hp_show - dt)
        self.stuck_t = max(0.0, self.stuck_t - dt)
        self.moving = False
        if self.state == "dead":
            self.dead_t += dt
            return
        p = cb.player
        if self.kb_t > 0:
            self.kb_t -= dt
            self.step(self.kv[0] * dt, self.kv[1] * dt, cb.world, cb.feet_except(self))
            f = 0.01 ** dt
            self.kv[0] *= f
            self.kv[1] *= f
        dx, dy = p.x - self.x, p.y - self.y
        dist = math.hypot(dx, dy) or 0.001
        ux, uy = dx / dist, dy / dist
        s = self.state
        if s == "idle":
            if dist < self.d.get("aggro", 190) and (dist < 64 or cb.sight(self.x, self.y, p.x, p.y)):
                self.wake(cb)
            elif dist < 260:
                self.dir = dir_from_vec(ux, uy)
            return
        if s == "stagger":
            self.state_t -= dt
            if self.state_t <= 0:
                self.state = "chase"
            return
        if self.kind == "melee":
            self._melee(dt, cb, dist, ux, uy)
        else:
            self._mage(dt, cb, dist, ux, uy)

    def _melee(self, dt, cb, dist, ux, uy):
        d, s = self.d, self.state
        if s == "chase":
            self.cd -= dt
            if dist <= d["reach"] + 4:
                self.dir = dir_from_vec(ux, uy)
                if self.cd <= 0:
                    self.state, self.state_t = "windup", d["windup"]
                    self.aim = math.atan2(uy, ux)
                else:
                    self.circle(cb, dt, ux, uy, 0.45)
            else:
                self.approach(cb, dt)
        elif s == "windup":
            self.state_t -= dt
            if self.state_t > d["windup"] * 0.4:          # tracks you early, then commits to a direction
                self.aim = math.atan2(uy, ux)
            self.dir = dir_from_vec(math.cos(self.aim), math.sin(self.aim))
            if self.state_t <= 0:
                self.state, self.state_t = "strike", 0.14
                cx, cy, r = self.zone()
                cb.slash_fx(self.x, self.y - 12, self.aim, d["reach"] + 8, d["color"])
                cb.sfx.play("swing")
                if cb.player_in_circle(cx, cy, r):
                    cb.hurt_player(self.dmg, self.x, self.y)
        elif s == "strike":
            self.state_t -= dt
            self.step(math.cos(self.aim) * d["lunge"] * dt, math.sin(self.aim) * d["lunge"] * dt,
                      cb.world, cb.feet_except(self))
            if self.state_t <= 0:
                self.state, self.state_t = "recover", d["recover"]
        elif s == "recover":
            self.state_t -= dt
            if self.state_t <= 0:
                self.state, self.cd = "chase", self.cd_base

    def _mage(self, dt, cb, dist, ux, uy):
        d, s = self.d, self.state
        if s == "chase":
            self.cd -= dt
            p = cb.player
            los = cb.sight(self.x, self.y, p.x, p.y)
            self.dir = dir_from_vec(ux, uy)
            near, far = d.get("near", 85), d.get("far", 150)
            if dist < near:                                  # too close: back away
                if not self.move(cb, -ux, -uy, dt, 0.95):
                    self.circle(cb, dt, ux, uy, 0.7)
            elif dist > far or not los:
                self.approach(cb, dt)
            else:
                self.circle(cb, dt, ux, uy, 0.5)
            if self.cd <= 0 and los and dist < 250:
                self.state, self.state_t = "windup", d["windup"]
                self.aim = math.atan2(uy, ux)
                cb.sfx.play("charge")
        elif s == "windup":
            self.state_t -= dt
            if self.state_t > 0.22:                          # aim locks 0.22s before firing
                self.aim = math.atan2(uy, ux)
            self.dir = dir_from_vec(math.cos(self.aim), math.sin(self.aim))
            if self.state_t <= 0:
                fan = d.get("fan", 1)
                spread = math.radians(d.get("spread", 15))
                for i in range(fan):
                    cb.enemy_bolt(self, self.aim + (i - (fan - 1) / 2) * spread)
                self.state, self.state_t = "recover", 0.45
                self.cd = self.cd_base * random.uniform(0.9, 1.3)
        elif s == "recover":
            self.state_t -= dt
            if self.state_t <= 0:
                self.state = "chase"


# --------------------------------------------------------------------------- combat manager
class Combat:
    def __init__(self, dungeon, player):
        self.dungeon = dungeon
        self.player = player
        self.toast = lambda text, dur=3.0: None       # main.py plugs its toast function in here
        self.sfx = Sfx()
        self.getframes = build_frames(dungeon.assets)
        cw, ch = player.sheet.get_width() // 3, player.sheet.get_height() // 4
        self.pframes = [[player.sheet.subsurface((c * cw, r * ch, cw, ch)).copy() for c in range(3)]
                        for r in range(4)]
        self.fx = pygame.Surface((VIEW_W, VIEW_H))    # additive glow layer
        self.tint_cache = {}
        self.t = 0.0
        self.weapon = "sword"
        self.max_hp = self.hp = PLAYER_MAX_HP
        self.max_mp = self.mp = MAX_MP
        self.inv = Inventory()
        self.hits_taken = 0
        self.kills = 0
        self.cam_used = (0, 0)
        self.shake_t = self.shake_amp = 0.0
        self.flow = None
        self.flow_tile = None
        self.flow_t = 0.0
        self.boss_defeated = False            # final boss (boss.py)
        self.victory = self.victory_done = False
        self.victory_t = 0.0
        self.boss_time = 0.0
        self.seal_cd = 0.0
        self.on_boss_start = lambda: None     # main.py plugs music changes in here
        self.on_boss_intro = lambda: None     # main.py plugs the throne-room speech in here
        self.intro_started = False
        self.boss_tries = 0
        self.on_victory = lambda: None
        self.on_floor_cleared = lambda: None  # main.py autosaves here
        self.cleared_floors = set()           # floors 1-5 stay cleared for good (monsters do not come back)
        self.dying = False                    # set when HP hits 0; main.py plays the death scene + respawn
        self.reset_player_state()
        self.clear_level_state()
        dungeon.on_level = self.load_level
        self.load_level()

    @property
    def world(self):
        return self.dungeon.world

    dungeon_active = False                      # main.py sets this while the hero is underground

    def reset_player_state(self):
        self.atk_cd = self.atk_t = 0.0
        self.atk_angle = self.aim = 0.0
        self.swing_hit = True
        self.face_t = 0.0
        self.roll_t = self.roll_cd = 0.0
        self.roll_dir = (0.0, 1.0)
        self.ghost_t = 0.0
        self.invuln = self.hurt_flash = 0.0
        self.kv = [0.0, 0.0]
        self.kb_t = 0.0
        self.swap_cd = 0.0
        self.dodge_msg_cd = 0.0
        self.nomana_cd = self.mp_flash = 0.0
        self.player.speed_mul = 1.0
        self.player.face_lock = None

    def clear_level_state(self):
        self.enemies, self.bolts, self.particles = [], [], []
        self.slashes, self.texts, self.ghosts = [], [], []
        self.cleared = False
        self.total = 0
        self.boss = None
        self.boss_time = 0.0

    # ------------------------------------------------------------------ level setup
    def load_level(self):
        d = self.dungeon
        world, level = d.world, d.level
        self.clear_level_state()
        self.reset_player_state()
        self.flow = None
        if level == 6:                                       # throne room: no wandering monsters, just the Warden
            self.total = 0
            self.spawn_throne_boss()
            return
        if level in self.cleared_floors:                     # already cleared: stays empty
            self.total = 0
            self.cleared = True
            return
        melee_pool, mage_pool = FLOOR_POOLS[level]
        rng = random.Random(level * 977 + 13)
        n = 5 + level
        n_mage = max(1, round(n * (0.22 + 0.05 * (level - 1))))
        avoid = [d.spawn_tile] + [p for p in (world.up, world.down) if p]
        cands = [(x, y) for y in range(DH) for x in range(DW) if world.walkable_tile(x, y)
                 and all(math.hypot(x - ax, y - ay) >= 7 for ax, ay in avoid)]
        rng.shuffle(cands)
        chosen = []
        for sep in (4.5, 3.0, 0.0):                         # relax spacing if the floor is cramped
            for c in cands:
                if len(chosen) >= n:
                    break
                if c not in chosen and all(math.hypot(c[0] - o[0], c[1] - o[1]) >= sep for o in chosen):
                    chosen.append(c)
        for i, (tx, ty) in enumerate(chosen):
            key = rng.choice(mage_pool if i < n_mage else melee_pool)
            self.enemies.append(Enemy(key, tx, ty, level, self.getframes))
        self.total = len(self.enemies)

    def alive_count(self):
        return sum(1 for e in self.enemies if e.alive)

    # ------------------------------------------------------------------ geometry helpers
    def feet_except(self, e):
        out = [o.foot for o in self.enemies if o is not e and o.alive]
        out.append(self.player.foot)
        return out

    def _line_clear(self, x0, y0, x1, y1, kinds):
        g = self.world.grid
        n = int(math.hypot(x1 - x0, y1 - y0) // 6) + 1
        for i in range(1, n + 1):
            k = i / n
            tx, ty = int((x0 + (x1 - x0) * k) // T), int((y0 + (y1 - y0) * k - 4) // T)
            if not (0 <= tx < DW and 0 <= ty < DH) or g[ty][tx] in kinds:
                return False
        return True

    def sight(self, x0, y0, x1, y1):
        return self._line_clear(x0, y0, x1, y1, SIGHT_BLOCK)

    def walk_clear(self, x0, y0, x1, y1):
        return self._line_clear(x0, y0, x1, y1, BLOCKING)

    def ray_end(self, x, y, ang, maxlen):
        """Walk a chest-height ray until it hits a wall; returns the last free point."""
        g = self.world.grid
        c, s = math.cos(ang), math.sin(ang)
        d = 0.0
        while d < maxlen:
            nx, ny = x + c * (d + 6), y + s * (d + 6)
            tx, ty = int(nx // T), int((ny + CHEST - 4) // T)
            if not (0 <= tx < DW and 0 <= ty < DH) or g[ty][tx] in SIGHT_BLOCK:
                break
            d += 6
        return x + c * d, y + s * d

    def _rebuild_flow(self):
        """Breadth-first distance map from the player: lets monsters path around walls and pillars."""
        g = self.world.grid
        p = self.player
        tx, ty = int(p.x // T), int((p.y - 4) // T)
        if not self.world.walkable_tile(tx, ty):
            tx, ty = self.world.nearest_walkable(tx, ty)
        INF = 9999
        f = [[INF] * DW for _ in range(DH)]
        f[ty][tx] = 0
        dq = deque([(tx, ty)])
        while dq:
            x, y = dq.popleft()
            nd = f[y][x] + 1
            for dx, dy in NEIGH8[:4]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < DW and 0 <= ny < DH and g[ny][nx] == FLOOR and f[ny][nx] > nd:
                    f[ny][nx] = nd
                    dq.append((nx, ny))
        self.flow, self.flow_tile = f, (tx, ty)

    def flow_step(self, e):
        """Centre of the neighbouring tile that is closest (by path) to the player."""
        f, g = self.flow, self.world.grid
        if f is None:
            return None
        tx, ty = int(e.x // T), int((e.y - 4) // T)
        if not (0 <= tx < DW and 0 <= ty < DH):
            return None
        best, bv = None, f[ty][tx]
        for dx, dy in NEIGH8:
            nx, ny = tx + dx, ty + dy
            if not (0 <= nx < DW and 0 <= ny < DH):
                continue
            if dx and dy and not (g[ty][nx] == FLOOR and g[ny][tx] == FLOOR):
                continue                                     # no cutting wall corners
            if f[ny][nx] < bv:
                best, bv = (nx, ny), f[ny][nx]
        if best is None:
            return None
        return best[0] * T + 16, best[1] * T + 20

    def alert_near(self, e):
        for o in self.enemies:
            if o is not e and o.state == "idle" and math.hypot(o.x - e.x, o.y - e.y) < 150:
                o.state = "chase"

    def player_in_circle(self, cx, cy, r):
        p = self.player
        return math.hypot(p.x - cx, (p.y - CHEST) - cy) <= r + 8

    # ------------------------------------------------------------------ effects
    def burst(self, x, y, color, n, speed, life, size=2):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(.3, 1.0) * speed
            self.particles.append([x, y, math.cos(a) * sp, math.sin(a) * sp,
                                   life * random.uniform(.6, 1.0), life, color, size])

    def text(self, s, x, y, color, life=0.8):
        self.texts.append([s, x, y, life, life, color])

    def slash_fx(self, x, y, ang, radius, color):
        self.slashes.append([x, y, ang, 0.16, 0.16, radius, color])

    def shake(self, amp, dur):
        if amp >= self.shake_amp or self.shake_t <= 0:
            self.shake_amp = amp
        self.shake_t = max(self.shake_t, dur)

    def shake_offset(self):
        if self.shake_t <= 0:
            return 0, 0
        a = max(1, int(round(self.shake_amp * min(1.0, self.shake_t * 6))))
        return random.randint(-a, a), random.randint(-a, a)

    def spawn_bolt(self, x, y, ang, speed, dmg, owner, color, radius, life):
        self.bolts.append(Bolt(x, y, ang, speed, dmg, owner, color, radius, life))

    def enemy_bolt(self, e, ang):
        sp = e.d.get("bolt", 140) * (1 + 0.05 * (e.level - 1))
        self.spawn_bolt(e.x + math.cos(ang) * 10, e.y - CHEST + math.sin(ang) * 10, ang, sp, e.dmg,
                        "enemy", e.d["color"], 5, 2.6)
        self.burst(e.x + math.cos(ang) * 10, e.y - CHEST + math.sin(ang) * 10, e.d["color"], 6, 70, .3)
        self.sfx.play("cast")

    # ------------------------------------------------------------------ damage
    def damage_enemy(self, e, dmg, ang, knock):
        if not e.alive:
            return
        if e.is_boss and e.immune:                         # rising / roaring / dying: nothing gets through
            if e.immune_cd <= 0:
                e.immune_cd = 0.5
                self.text("Immune", e.x, e.y - e.chest - 40, (190, 190, 225), .6)
            self.burst(e.x, e.y - e.chest, (190, 190, 225), 3, 90, .25)
            return
        dmg = max(1, int(round(dmg * getattr(e, "dmg_mul", 1.0))))
        e.hp -= dmg
        e.flash, e.hp_show = 0.12, 2.5
        e.wake(self)
        kn = knock * getattr(e, "knock_mul", 0.35 if e.big else 1.0)
        e.kv = [math.cos(ang) * kn, math.sin(ang) * kn]
        e.kb_t = 0.2
        self.text(str(dmg), e.x, e.y - e.chest - 20, (255, 240, 150))
        self.burst(e.x, e.y - e.chest, e.d["color"], 7, 120, .35)
        self.sfx.play("hit")
        if e.hp <= 0:
            e.die(self)
            self.kills += 1
            self.reward_kill(e)
            self.burst(e.x, e.y - e.chest, e.d["color"], 22, 170, .6, 3)
            self.sfx.play("die")
            self.shake(2, 0.15)
        elif not e.big:
            e.state, e.state_t = "stagger", 0.3          # light monsters flinch and lose their attack
            e.cd = max(e.cd, 0.45)

    def reward_kill(self, e):
        """Defeating a monster refunds a little mana and may drop potions into the pack."""
        p = self.player
        gain = MANA_ON_BOSS if e.is_boss else (MANA_ON_KILL_BIG if e.big else MANA_ON_KILL)
        got = min(gain, self.max_mp - self.mp)
        if got > 0:
            self.mp += got
            self.text(f"+{got} MP", p.x, p.y - 44, (130, 175, 255), 0.9)
        drops = dict(BOSS_DROPS) if e.is_boss else {k: 1 for k, ch in DROPS.items() if random.random() < ch}
        for k, n in drops.items():
            left = self.inv.add(k, n)
            if left < n:
                self.text(f"+{n - left} {ITEMS[k]['name']}", e.x, e.y - e.chest - 34, (255, 235, 150), 1.2)
                self.toast(f"Found {n - left}x {ITEMS[k]['name']}", 2.5)
            if left:
                self.toast("Your pack is full!", 2.0)

    def use_item(self, key):
        """Drink a potion from the pack. Returns True if it was used."""
        d, p = ITEMS[key], self.player
        if self.inv.count(key) <= 0:
            self.toast(f"You have no {d['name']}s.", 2.0)
            return False
        if "hp" in d and self.hp >= self.max_hp:
            self.toast("Your health is already full.", 2.0)
            return False
        if "mp" in d and self.mp >= self.max_mp:
            self.toast("Your mana is already full.", 2.0)
            return False
        self.inv.remove(key)
        if "hp" in d:
            got = min(d["hp"], self.max_hp - self.hp)
            self.hp += got
            msg, col = f"+{got} HP", (120, 235, 130)
        else:
            got = min(d["mp"], self.max_mp - self.mp)
            self.mp += got
            msg, col = f"+{got} MP", (130, 175, 255)
        self.toast(f"Used {d['name']}  {msg}", 2.2)
        self.sfx.play("swap")
        if self.dungeon_active:
            self.text(msg, p.x, p.y - 40, col, 0.9)
            self.burst(p.x, p.y - CHEST, col, 12, 70, .5)
        return True

    def restore_all(self):
        """Goddess statue: full HP and full MP. Returns True if anything was restored."""
        need = self.hp < self.max_hp or self.mp < self.max_mp
        self.hp, self.mp = self.max_hp, self.max_mp
        return need

    def hurt_player(self, dmg, sx, sy):
        """Called when an enemy attack connects. Returns True if the hit landed."""
        p = self.player
        if self.roll_t > 0:
            if self.dodge_msg_cd <= 0:
                self.dodge_msg_cd = 0.4
                self.text("Dodge!", p.x, p.y - 38, (140, 230, 255), 0.7)
            return False
        if self.invuln > 0:
            return False
        self.hits_taken += 1
        if not INFINITE_HP or self.boss_lock:                # the boss fight always uses real damage
            self.hp = max(0, self.hp - dmg)
        self.invuln, self.hurt_flash = 0.55, 0.3
        a = math.atan2(p.y - sy, p.x - sx)
        self.kv = [math.cos(a) * 200, math.sin(a) * 200]
        self.kb_t = 0.16
        self.atk_t = 0.0                                   # hits interrupt your attack
        self.text(f"-{dmg}", p.x, p.y - 38, (255, 90, 90), 0.9)
        self.burst(p.x, p.y - CHEST, (255, 70, 70), 10, 110, .4)
        self.sfx.play("hurt")
        self.shake(3, 0.2)
        if self.hp <= 0 and not self.dying:                # the hero dies: main.py takes over (death scene -> goddess statue)
            self.dying = True
            self.hp = 0
            self.invuln = 999.0
        return True

    # ------------------------------------------------------------------ player actions
    def swap_weapon(self, scroll=False):
        if scroll and self.swap_cd > 0:
            return
        self.swap_cd = 0.22
        self.weapon = "magic" if self.weapon == "sword" else "sword"
        self.atk_t = 0.0
        self.sfx.play("swap")
        p = self.player
        self.text("Sword" if self.weapon == "sword" else "Fireball", p.x, p.y - 40,
                  (255, 230, 150) if self.weapon == "sword" else (255, 170, 90), 0.8)

    def dodge(self, keys):
        if self.roll_cd > 0 or self.roll_t > 0 or self.kb_t > 0:
            return False
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx or dy:
            n = math.hypot(dx, dy)
            self.roll_dir = (dx / n, dy / n)
        else:                                              # no input: roll away from the cursor
            self.roll_dir = (-math.cos(self.aim), -math.sin(self.aim))
        self.roll_t = ROLL["duration"]
        self.roll_cd = ROLL["cooldown"]
        self.invuln = max(self.invuln, ROLL["iframes"])
        self.atk_t = 0.0
        self.ghost_t = 0.0
        self.player.dir = dir_from_vec(*self.roll_dir)
        self.sfx.play("roll")
        return True

    def attack(self):
        p = self.player
        self.face_t = 0.3
        self.atk_angle = self.aim
        if self.weapon == "sword":
            self.atk_cd, self.atk_t, self.swing_hit = SWORD["cooldown"], SWORD["duration"], False
            self.sfx.play("swing")
        else:
            if self.mp < FIREBALL_COST:                    # out of mana: the fizzle
                self.face_t = 0.0
                self.atk_cd = 0.3
                self.mp_flash = 0.6
                if self.nomana_cd <= 0:
                    self.nomana_cd = 0.9
                    self.text("Not enough mana!", p.x, p.y - 40, (130, 165, 255), 0.9)
                    self.sfx.play("swap")
                return
            self.mp -= FIREBALL_COST
            self.atk_cd, self.atk_t = MAGIC["cooldown"], MAGIC["duration"]
            a = self.aim
            bx, by = p.x + math.cos(a) * 14, p.y - CHEST + math.sin(a) * 14
            self.spawn_bolt(bx, by, a, MAGIC["speed"], MAGIC["damage"], "player", FIRE,
                            MAGIC["radius"] + 1, MAGIC["life"])
            self.burst(bx, by, FIRE, 6, 80, .25)
            self.sfx.play("cast")

    def sword_strike(self):
        p = self.player
        cx, cy = p.x, p.y - CHEST
        half = math.radians(SWORD["arc"]) / 2
        for e in self.enemies:
            if not e.alive:
                continue
            dx, dy = e.x - cx, (e.y - e.chest) - cy
            d = math.hypot(dx, dy)
            if d > SWORD["reach"] + e.r:
                continue
            a = math.atan2(dy, dx)
            if d > e.r + 12 and ang_diff(a, self.atk_angle) > half:
                continue
            self.damage_enemy(e, SWORD["damage"], a, SWORD["knock"])

    # ------------------------------------------------------------------ final boss
    @property
    def boss_lock(self):
        """True from the moment the boss rises until he is dead: the stairs are sealed."""
        return self.boss is not None and self.boss.state != "dead"

    @property
    def victory_active(self):
        return self.victory and not self.victory_done

    def spawn_throne_boss(self):
        """Grimhorn sits on his throne (immune) until the hero walks into the hall and the speech ends."""
        from boss import Boss
        tx, ty = self.world.throne
        self.boss = Boss(tx * T + 16, ty * T + 26, self.dungeon.level)
        self.enemies.append(self.boss)
        self.boss_time = 0.0
        self.seal_cd = 3.0
        self.intro_started = False

    def start_boss_fight(self):
        """The speech is over: the Warden stands up."""
        if self.boss is not None:
            self.boss.awaken(self)
            self.on_boss_start()

    def reset_boss_fight(self):
        """Hero knocked out during the boss fight: back to the entrance, Grimhorn back on his throne."""
        self.boss_tries += 1
        d = self.dungeon
        d.set_level(6, spawn="gate")                         # reloads the room (fresh boss) via load_level
        p = self.player
        p.x, p.y = d.player_spawn()
        p.dir = "up"
        d.cam = [max(0, p.x - VIEW_W / 2), max(0, p.y - VIEW_H / 2)]
        self.hp = self.max_hp
        self.toast("You were knocked out... Grimhorn returns to his throne.", 3.5)

    def _win(self):
        self.victory, self.victory_done, self.victory_t = True, False, 0.0
        self.boss_defeated = True
        self.hp = self.max_hp
        self.sfx.play("win")
        self.on_victory()

    def dismiss_victory(self):
        if self.victory_active and self.victory_t > 1.8:
            self.victory_done = True
            self.world.open_exit()
            self.shake(6, 1.2)
            self.sfx.play("boom")
            ex, ey = self.world.exit_tile
            for x, y in self.world.exit_cells[::2]:
                self.burst(x * T + 16, y * T + 16, (170, 150, 190), 10, 120, .7, 3)
            self.toast("The east wall crumbles - a path opens. Follow the light home.", 5.0)
            return True
        return self.victory_active

    def debug_start_boss(self):
        """Used by `main.py --boss-test`: wipe the floor and summon the boss straight away."""
        self.cleared = True
        self.intro_started = True
        self.boss.awaken(self)

    # ------------------------------------------------------------------ update
    def update(self, dt, keys, aim_pt, firing):
        p, world = self.player, self.world
        self.t += dt
        for name in ("atk_cd", "roll_cd", "invuln", "hurt_flash", "swap_cd", "face_t", "dodge_msg_cd", "shake_t", "nomana_cd", "mp_flash"):
            setattr(self, name, max(0.0, getattr(self, name) - dt))
        if self.victory_active:                              # actors freeze while the victory screen is up
            self.victory_t += dt
            self._update_bolts(dt)
            self._update_fx(dt)
            return
        self.aim = math.atan2(aim_pt[1] - (p.y - CHEST), aim_pt[0] - p.x)
        live_feet = [e.foot for e in self.enemies if e.alive]

        if self.roll_t > 0:                                  # ---- dodge roll
            k = self.roll_t / ROLL["duration"]
            sp = ROLL["speed"] * (0.55 + 0.45 * k) * dt
            p.step(self.roll_dir[0] * sp, self.roll_dir[1] * sp, world, [])   # rolls pass through monsters
            self.roll_t = max(0.0, self.roll_t - dt)
            p.moving, p.anim = False, 0
            self.ghost_t -= dt
            if self.ghost_t <= 0:
                self.ghost_t = 0.035
                self.ghosts.append([p.x, p.y, DIRS.index(p.dir), 0.22])
                self.burst(p.x, p.y - 2, (150, 140, 130), 1, 25, .3)
        elif self.kb_t > 0:                                  # ---- hit-stun knockback
            self.kb_t -= dt
            p.step(self.kv[0] * dt, self.kv[1] * dt, world, live_feet)
            f = 0.01 ** dt
            self.kv[0] *= f
            self.kv[1] *= f
            p.moving, p.anim = False, 0
        else:                                                # ---- normal control
            attacking = self.atk_t > 0
            p.speed_mul = (0.5 if self.weapon == "sword" else 0.75) if attacking else 1.0
            p.face_lock = dir_from_vec(math.cos(self.aim), math.sin(self.aim)) if (attacking or self.face_t > 0) else None
            p.update(dt, keys, world, live_feet)
            if firing and self.atk_cd <= 0:
                self.attack()

        if self.atk_t > 0:                                   # ---- weapon animation / sword hit moment
            dur = SWORD["duration"] if self.weapon == "sword" else MAGIC["duration"]
            self.atk_t = max(0.0, self.atk_t - dt)
            if self.weapon == "sword":
                prog = 1 - self.atk_t / dur
                a = self.atk_angle
                lg = SWORD["lunge"] * (1 - prog) * dt
                p.step(math.cos(a) * lg, math.sin(a) * lg, world, live_feet)
                if not self.swing_hit and prog >= 0.3:
                    self.swing_hit = True
                    self.sword_strike()

        # ---- monsters
        self.flow_t -= dt
        tile = (int(p.x // T), int((p.y - 4) // T))
        if self.flow is None or self.flow_t <= 0 or tile != self.flow_tile:
            self._rebuild_flow()
            self.flow_t = 0.25
        for e in self.enemies:
            e.update(dt, self)
        self.enemies = [e for e in self.enemies if not (e.state == "dead" and e.dead_t > 0.6)]
        if self.total and not self.cleared and self.alive_count() == 0:
            self.cleared = True
            if self.dungeon.level < 6:
                self.cleared_floors.add(self.dungeon.level)
                self.on_floor_cleared()
            if self.dungeon.level == 5 and not self.boss_defeated:
                self.toast("Floor cleared! The purple gate hums... step up to it and press E.", 5.0)
            elif self.dungeon.level == 5:
                self.toast("Floor cleared.", 2.5)
            else:
                self.toast("Floor cleared! The stairs are safe.", 3.5)
        if self.boss is not None:
            if self.boss.state not in ("seated", "rise", "dead"):
                self.boss_time += dt
            if self.boss.state == "dead" and not self.victory:
                self._win()
            if (self.boss.state == "seated" and not self.intro_started
                    and p.y < self.boss.y + 8.5 * T):          # the hero walks into the hall: he speaks
                self.intro_started = True
                self.on_boss_intro()
            self.seal_cd = max(0.0, self.seal_cd - dt)
            if self.boss_lock and self.seal_cd <= 0 and self.dungeon.next_transition(p):
                self.seal_cd = 4.0
                self.toast("The stairs are sealed until the Warden falls!", 2.5)

        self._update_bolts(dt)
        self._update_fx(dt)

    def _update_bolts(self, dt):
        p, g = self.player, self.world.grid
        for b in self.bolts:
            n = int(b.speed * dt / 6) + 1
            sub = dt / n
            for _ in range(n):
                b.x += b.vx * sub
                b.y += b.vy * sub
                tx, ty = int(b.x // T), int((b.y + CHEST - 4) // T)
                if not (0 <= tx < DW and 0 <= ty < DH) or g[ty][tx] in SIGHT_BLOCK:
                    b.dead = True
                elif b.owner == "player":
                    for e in self.enemies:
                        if e.alive and math.hypot(e.x - b.x, (e.y - e.chest) - b.y) <= e.r + b.radius:
                            self.damage_enemy(e, b.dmg, b.ang, MAGIC["knock"])
                            b.dead = True
                            break
                elif math.hypot(p.x - b.x, (p.y - CHEST) - b.y) <= 8 + b.radius:
                    if self.roll_t > 0 or self.invuln > 0:
                        if self.roll_t > 0 and self.dodge_msg_cd <= 0:
                            self.dodge_msg_cd = 0.4
                            self.text("Dodge!", p.x, p.y - 38, (140, 230, 255), 0.7)
                    else:
                        self.hurt_player(b.dmg, b.x, b.y)
                        b.dead = True
                if b.dead:
                    self.burst(b.x, b.y, b.color, 9, 110, .35)
                    self.sfx.play("boom")
                    break
            b.t += dt
            b.life -= dt
            if b.life <= 0 and not b.dead:
                b.dead = True
                self.burst(b.x, b.y, b.color, 4, 60, .25)
            if not b.dead and random.random() < dt * 45:
                self.particles.append([b.x, b.y, random.uniform(-12, 12), random.uniform(-12, 12), .25, .25,
                                       b.color, 2])
        self.bolts = [b for b in self.bolts if not b.dead]

    def _update_fx(self, dt):
        for q in self.particles:
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            f = 0.04 ** dt
            q[2] *= f
            q[3] *= f
            q[4] -= dt
        self.particles = [q for q in self.particles if q[4] > 0]
        for s in self.slashes:
            s[3] -= dt
        self.slashes = [s for s in self.slashes if s[3] > 0]
        for t in self.texts:
            t[3] -= dt
            t[2] -= 22 * dt
        self.texts = [t for t in self.texts if t[3] > 0]
        for g in self.ghosts:
            g[3] -= dt
        self.ghosts = [g for g in self.ghosts if g[3] > 0]

    # ------------------------------------------------------------------ drawing: world
    def tinted(self, img, rgb):
        key = (id(img), rgb)
        t = self.tint_cache.get(key)
        if t is None:
            t = img.copy()
            t.fill(rgb, special_flags=pygame.BLEND_RGB_ADD)
            self.tint_cache[key] = t
        return t

    def _sword_pose(self):
        """(blade angle, swing progress or None)."""
        if self.weapon == "sword" and self.atk_t > 0:
            prog = 1 - self.atk_t / SWORD["duration"]
            e = 1 - (1 - prog) ** 2
            half = math.radians(SWORD["arc"]) / 2
            return self.atk_angle - half + 2 * half * e, prog
        return self.aim, None

    def draw_entities(self, surf, camx, camy, shadow):
        """Monsters and the player, depth-sorted by their feet."""
        self.cam_used = (camx, camy)
        items = [(e.y, 0, e) for e in self.enemies]
        items.append((self.player.y, 1, self.player))
        items.sort(key=lambda i: i[0])
        for _, kind, o in items:
            if kind == 0:
                self._draw_enemy(surf, o, camx, camy, shadow)
            else:
                self._draw_player(surf, camx, camy, shadow)

    def _draw_enemy(self, surf, e, camx, camy, shadow):
        sx, sy = int(e.x) - camx, int(e.y) - camy
        if not (-48 < sx < VIEW_W + 48 and -64 < sy < VIEW_H + 64):
            return
        if e.is_boss:
            e.draw(self, surf, camx, camy, shadow)
            return
        fr = e.frames[e.dir]
        if e.moving:
            idx = (0, 1, 2, 1)[int(e.anim) % 4]
        elif e.fly or e.key.startswith("slime"):
            idx = (1, 0, 1, 2)[int(e.t * 4) % 4]
        else:
            idx = 1
        img = fr[idx]
        hover = (4 + int(math.sin(e.t * 3) * 2)) if e.fly else 0
        ox = oy = 0
        if e.state == "windup" and e.kind == "melee":          # rear back, tinting red
            k = e.windup_progress()
            ox, oy = -math.cos(e.aim) * 3 * k, -math.sin(e.aim) * 3 * k
            img = self.tinted(img, (int(k * 3) * 28, 0, 0))
        elif e.state == "strike":
            ox, oy = math.cos(e.aim) * 4, math.sin(e.aim) * 4
        elif e.state == "windup":                              # mage glows in its spell colour
            c = scale_color(e.d["color"], .35 * e.windup_progress())
            img = self.tinted(img, (c[0] // 28 * 28, c[1] // 28 * 28, c[2] // 28 * 28))
        if e.flash > 0:
            img = self.tinted(img, (170, 170, 170))
        if e.state == "dead":
            k = max(0.0, 1 - e.dead_t / 0.55)
            img = img.copy()
            img.set_alpha(int(255 * k))
        sw = shadow if not e.big else pygame.transform.scale(shadow, (30, 12))
        surf.blit(sw, (sx - sw.get_width() // 2, sy - 6))
        surf.blit(img, (int(sx - 16 + ox), int(sy - 30 - hover + oy)))

    def _draw_player(self, surf, camx, camy, shadow):
        p = self.player
        sx, sy = int(p.x) - camx, int(p.y) - camy
        for gx, gy, row, life in self.ghosts:                  # roll afterimages
            gi = self.pframes[row][0].copy()
            gi.set_alpha(int(110 * life / 0.22))
            surf.blit(gi, (int(gx) - camx - 16, int(gy) - camy - 30))
        row = DIRS.index(p.dir)
        surf.blit(shadow, (sx - shadow.get_width() // 2, sy - 6))
        if self.roll_t > 0:
            prog = 1 - self.roll_t / ROLL["duration"]
            spin = -prog * 360 * (1 if self.roll_dir[0] >= 0 else -1)
            rot = pygame.transform.rotate(self.pframes[row][0], spin)
            surf.blit(rot, rot.get_rect(center=(sx, sy - 14)))
        else:
            blink = self.invuln > 0 and int(self.t * 18) % 2 == 0
            if not blink:
                img = self.pframes[row][0 if p.z > 2 else p.frame()]
                if self.hurt_flash > 0:
                    img = self.tinted(img, (150, 20, 20))
                surf.blit(img, (sx - 16, sy - 30 - int(p.z)))
        self._draw_weapon(surf, sx, sy)

    def _draw_weapon(self, surf, sx, sy):
        if self.roll_t > 0:
            return
        cx, cy = sx, sy - CHEST
        if self.weapon == "sword":
            a, prog = self._sword_pose()
            c, s = math.cos(a), math.sin(a)
            length = 30 if prog is not None else 17
            p0, p1 = (cx + c * 6, cy + s * 6), (cx + c * (6 + length), cy + s * (6 + length))
            pygame.draw.line(surf, (30, 30, 44), p0, p1, 5)
            pygame.draw.line(surf, (214, 224, 240), p0, p1, 3)
            gx, gy = cx + c * 8, cy + s * 8
            pygame.draw.line(surf, (230, 190, 90), (gx - s * 4, gy + c * 4), (gx + s * 4, gy - c * 4), 2)
        else:
            c, s = math.cos(self.aim), math.sin(self.aim)
            big = 1.0 + (1.2 if self.atk_t > 0 else 0.15 * math.sin(self.t * 8))
            ox, oy = int(cx + c * 13), int(cy + s * 13 - 2)
            pygame.draw.circle(surf, (50, 90, 190), (ox, oy), int(4 * big) + 1)
            pygame.draw.circle(surf, (140, 205, 255), (ox, oy), int(3 * big))
            pygame.draw.circle(surf, (255, 255, 255), (ox, oy), max(1, int(1.5 * big)))

    def cut_light(self, darkness, camx, camy):
        """Punch light holes in the dungeon darkness for bolts, monsters and spell glow."""
        for b in self.bolts:
            pos = (int(b.x - camx), int(b.y - camy))
            pygame.draw.circle(darkness, (0, 0, 0, 70), pos, 42)
            pygame.draw.circle(darkness, (0, 0, 0, 0), pos, 18)
        p = self.player
        for e in self.enemies:
            if e.alive and (e.state != "idle" or math.hypot(e.x - p.x, e.y - p.y) < 180):
                pos = (int(e.x - camx), int(e.y - e.chest - camy))
                big = 2.2 if e.is_boss else 1.0
                pygame.draw.circle(darkness, (0, 0, 0, 120), pos, int(30 * big))
                pygame.draw.circle(darkness, (0, 0, 0, 70), pos, int(18 * big))
        if self.weapon == "magic":
            a = self.aim
            pos = (int(p.x + math.cos(a) * 13 - camx), int(p.y - CHEST + math.sin(a) * 13 - camy))
            pygame.draw.circle(darkness, (0, 0, 0, 90), pos, 32)
        elif self.atk_t > 0:
            pygame.draw.circle(darkness, (0, 0, 0, 110), (int(p.x - camx), int(p.y - CHEST - camy)), 52)

    def draw_fx(self, surf, camx, camy):
        """Additive glow layer: spell bolts, particles, telegraphs, sword trail."""
        fx = self.fx
        fx.fill((0, 0, 0))
        p = self.player

        def S(x, y):
            return int(x - camx), int(y - camy)

        # sword trail
        if self.weapon == "sword" and self.atk_t > 0:
            cur, prog = self._sword_pose()
            half = math.radians(SWORD["arc"]) / 2
            start = max(self.atk_angle - half, cur - math.radians(85))
            cx, cy = S(p.x, p.y - CHEST)
            R = SWORD["reach"] - 2
            outer = [(cx + math.cos(start + (cur - start) * i / 8) * R, cy + math.sin(start + (cur - start) * i / 8) * R)
                     for i in range(9)]
            inner = [(cx + math.cos(start + (cur - start) * i / 8) * (R - 14), cy + math.sin(start + (cur - start) * i / 8) * (R - 14))
                     for i in range(8, -1, -1)]
            k = 1 - prog * 0.55
            pygame.draw.polygon(fx, scale_color((95, 115, 150), k), outer + inner)
            pygame.draw.lines(fx, scale_color((235, 245, 255), k), False, outer, 3)
        # magic orb in hand
        if self.weapon == "magic" and self.roll_t <= 0:
            a = self.aim
            ox, oy = S(p.x + math.cos(a) * 13, p.y - CHEST + math.sin(a) * 13 - 2)
            glow(fx, ox, oy, 14 if self.atk_t > 0 else 9, FIRE, 0.9 if self.atk_t > 0 else 0.55)
        # monster telegraphs
        for e in self.enemies:
            if e.is_boss:
                if e.state != "dead":
                    e.draw_fx(self, fx, S)
                continue
            if e.state != "windup":
                continue
            k = e.windup_progress()
            if e.kind == "melee":
                zx, zy, zr = e.zone()
                zx, zy = S(zx, zy)
                pygame.draw.circle(fx, (int(110 * k) + 20, int(14 * k), int(10 * k)), (zx, zy), int(zr))
                pygame.draw.circle(fx, (int(255 * (.4 + .6 * k)), int(60 * k), int(40 * k)), (zx, zy), int(zr), 1)
            else:
                hx, hy = S(e.x + math.cos(e.aim) * 10, e.y - CHEST + math.sin(e.aim) * 10)
                glow(fx, hx, hy, 5 + 9 * k, e.d["color"], .35 + .65 * k)
                fan = e.d.get("fan", 1)
                spread = math.radians(e.d.get("spread", 15))
                for i in range(fan):
                    a = e.aim + (i - (fan - 1) / 2) * spread
                    ex, ey = self.ray_end(e.x, e.y - CHEST, a, 260)
                    pygame.draw.line(fx, scale_color(e.d["color"], .22 + .3 * k), (hx, hy), S(ex, ey), 1)
        # enemy melee slashes
        for sx_, sy_, ang, life, mx, R, col in self.slashes:
            k = life / mx
            cx, cy = S(sx_, sy_)
            pts = [(cx + math.cos(ang - 1.0 + 2.0 * i / 8) * R, cy + math.sin(ang - 1.0 + 2.0 * i / 8) * R) for i in range(9)]
            pygame.draw.lines(fx, scale_color(col, k), False, pts, 3)
        # bolts
        for b in self.bolts:
            bx, by = S(b.x, b.y)
            glow(fx, bx, by, b.radius * 2.6, b.color, 1.0)
            pygame.draw.circle(fx, (255, 255, 255), (bx, by), max(1, b.radius // 2))
        # particles
        for x, y, vx, vy, life, mx, col, size in self.particles:
            k = life / mx
            pygame.draw.circle(fx, scale_color(col, k), S(x, y), max(1, int(size * (0.5 + k))))
        surf.blit(fx, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def draw_overlay(self, surf, font):
        """Health bars and floating numbers (drawn on top of everything in the world)."""
        camx, camy = self.cam_used
        for e in self.enemies:
            if e.alive and e.hp_show > 0 and not e.is_boss:
                sx, sy = int(e.x) - camx, int(e.y) - camy - 38 - (5 if e.fly else 0)
                w = 26
                pygame.draw.rect(surf, (18, 8, 12), (sx - w // 2 - 1, sy - 1, w + 2, 5))
                pygame.draw.rect(surf, (210, 46, 56), (sx - w // 2, sy, max(1, int(w * e.hp / e.max_hp)), 3))
        for s, x, y, life, mx, col in self.texts:
            k = min(1.0, life / (mx * 0.5))
            img = font.render(s, True, scale_color(col, k))
            sh = font.render(s, True, (20, 12, 16))
            px, py = int(x - camx - img.get_width() // 2), int(y - camy)
            surf.blit(sh, (px + 1, py + 1))
            surf.blit(img, (px, py))

    # ------------------------------------------------------------------ drawing: HUD
    def _icon(self, v, kind, x, y):
        if kind == "sword":
            pygame.draw.line(v, (60, 60, 80), (x + 8, y + 24), (x + 24, y + 8), 5)
            pygame.draw.line(v, (220, 230, 245), (x + 8, y + 24), (x + 24, y + 8), 3)
            pygame.draw.line(v, (235, 195, 95), (x + 8, y + 17), (x + 15, y + 24), 3)
            pygame.draw.line(v, (140, 90, 50), (x + 6, y + 26), (x + 9, y + 23), 3)
        else:                                                    # fireball
            pygame.draw.polygon(v, (200, 60, 30), [(x + 8, y + 24), (x + 16, y + 4), (x + 22, y + 14), (x + 26, y + 26)])
            pygame.draw.circle(v, (230, 90, 30), (x + 17, y + 19), 9)
            pygame.draw.circle(v, (255, 160, 50), (x + 17, y + 19), 7)
            pygame.draw.circle(v, (255, 230, 120), (x + 17, y + 20), 4)
            pygame.draw.circle(v, (255, 255, 230), (x + 16, y + 19), 2)

    def draw_hud(self, v, font, font_s, mouse):
        # bottom-left panel
        px, py = 6, VIEW_H - 96
        panel = pygame.Surface((232, 90), pygame.SRCALPHA)
        pygame.draw.rect(panel, (22, 16, 30, 215), panel.get_rect(), border_radius=8)
        pygame.draw.rect(panel, (148, 122, 168, 230), panel.get_rect(), 1, border_radius=8)
        v.blit(panel, (px, py))
        x0, y0 = px + 8, py + 7
        v.blit(font_s.render("HP", True, (230, 215, 235)), (x0, y0 + 1))
        bar = pygame.Rect(x0 + 22, y0, 168, 12)
        real = (not INFINITE_HP) or self.boss_lock
        frac = self.hp / self.max_hp if real else 1.0
        pygame.draw.rect(v, (40, 14, 20), bar, border_radius=4)
        pygame.draw.rect(v, (190, 44, 60), (bar.x, bar.y, int(bar.w * frac), bar.h), border_radius=4)
        pygame.draw.rect(v, (255, 210, 220), bar, 1, border_radius=4)
        if not real:
            draw_infinity(v, bar.centerx, bar.centery, 10, (255, 255, 255))
        else:
            t = font_s.render(f"{self.hp}/{self.max_hp}", True, (255, 255, 255))
            v.blit(t, (bar.centerx - t.get_width() // 2, bar.y - 1))
        # mana bar
        v.blit(font_s.render("MP", True, (170, 200, 255)), (x0, y0 + 16))
        mbar = pygame.Rect(x0 + 22, y0 + 15, 168, 12)
        pygame.draw.rect(v, (12, 18, 46), mbar, border_radius=4)
        pygame.draw.rect(v, (60, 110, 235), (mbar.x, mbar.y, int(mbar.w * self.mp / self.max_mp), mbar.h), border_radius=4)
        pygame.draw.rect(v, (255, 90, 90) if self.mp_flash > 0 and int(self.t * 14) % 2 == 0 else (190, 215, 255),
                         mbar, 1, border_radius=4)
        t = font_s.render(f"{self.mp}/{self.max_mp}", True, (255, 255, 255))
        v.blit(t, (mbar.centerx - t.get_width() // 2, mbar.y - 1))
        v.blit(font_s.render(f"Hits taken {self.hits_taken}    Slain {self.kills}", True, (200, 190, 215)), (x0, y0 + 66))
        # weapon slots
        for i, name in enumerate(("sword", "magic")):
            sx, sy = x0 + i * 38, y0 + 31
            active = self.weapon == name
            pygame.draw.rect(v, (58, 46, 78) if active else (30, 24, 40), (sx, sy, 32, 32), border_radius=5)
            self._icon(v, name, sx, sy)
            if active:
                total = SWORD["cooldown"] if name == "sword" else MAGIC["cooldown"]
                h = int(32 * min(1.0, self.atk_cd / total))
                if h > 0:
                    shade = pygame.Surface((32, h), pygame.SRCALPHA)
                    shade.fill((0, 0, 0, 150))
                    v.blit(shade, (sx, sy))
            if name == "magic":
                ok = self.mp >= FIREBALL_COST
                v.blit(font_s.render(str(FIREBALL_COST), True, (150, 190, 255) if ok else (255, 110, 110)),
                       (sx + 23, sy + 19))
            pygame.draw.rect(v, (255, 214, 120) if active else (90, 78, 110), (sx, sy, 32, 32), 2 if active else 1,
                             border_radius=5)
        # dodge meter
        dx0 = x0 + 84
        v.blit(font_s.render("DODGE [SPACE]", True, (200, 190, 215)), (dx0, y0 + 32))
        ready = 1.0 - min(1.0, self.roll_cd / ROLL["cooldown"])
        pygame.draw.rect(v, (30, 24, 40), (dx0, y0 + 46, 100, 7), border_radius=3)
        pygame.draw.rect(v, (120, 220, 255) if ready >= 1 else (90, 120, 150), (dx0, y0 + 46, int(100 * ready), 7),
                         border_radius=3)
        pygame.draw.rect(v, (170, 150, 190), (dx0, y0 + 46, 100, 7), 1, border_radius=3)
        v.blit(font_s.render("LMB attack   RMB/scroll swap", True, (160, 150, 180)), (dx0 - 4, y0 + 56))
        # foes remaining (top-right)
        left = self.alive_count()
        if self.boss_lock:
            label = "BOSS FIGHT" if left <= 1 else f"BOSS FIGHT  +{left - 1} minions"
        else:
            label = f"Foes left: {left}" if left else "Floor clear"
        img = font.render(label, True, (235, 224, 246) if left else (170, 240, 170))
        w = img.get_width() + 18
        box = pygame.Surface((w, 22), pygame.SRCALPHA)
        pygame.draw.rect(box, (22, 16, 30, 215), box.get_rect(), border_radius=7)
        pygame.draw.rect(box, (148, 122, 168, 230), box.get_rect(), 1, border_radius=7)
        box.blit(img, (9, 4))
        v.blit(box, (VIEW_W - w - 6, 6))
        # potion quick-use
        q = [f"[{ITEMS[k]['key']}] {ITEMS[k]['name']} x{self.inv.count(k)}" for k in ("health_potion", "mana_potion")]
        qw = max(font_s.size(t)[0] for t in q) + 16
        qb = pygame.Surface((qw, 32), pygame.SRCALPHA)
        pygame.draw.rect(qb, (22, 16, 30, 200), qb.get_rect(), border_radius=7)
        pygame.draw.rect(qb, (148, 122, 168, 230), qb.get_rect(), 1, border_radius=7)
        for i, t in enumerate(q):
            have = self.inv.count(("health_potion", "mana_potion")[i]) > 0
            qb.blit(font_s.render(t, True, (235, 224, 246) if have else (130, 120, 140)), (8, 3 + i * 14))
        v.blit(qb, (VIEW_W - qw - 6, 32))
        if self.boss is not None:
            self.boss.draw_ui(self, v, font, font_s)
        if self.victory_active:
            from boss import draw_victory
            draw_victory(self, v, font, font_s)
        # crosshair
        mx, my = int(mouse[0]), int(mouse[1])
        col = (255, 230, 150) if self.weapon == "sword" else (255, 170, 90)
        pygame.draw.circle(v, col, (mx, my), 7, 1)
        for ax, ay, bx, by in ((-12, 0, -6, 0), (6, 0, 12, 0), (0, -12, 0, -6), (0, 6, 0, 12)):
            pygame.draw.line(v, col, (mx + ax, my + ay), (mx + bx, my + by), 1)
        pygame.draw.circle(v, col, (mx, my), 1)
