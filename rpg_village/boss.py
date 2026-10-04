"""GRIMHORN, Warden of the Hollow - the final boss of The Hollow Below.

When every monster on floor 5 has been slain the purple gate opens and leads to Grimhorn's throne room.
He sits on his throne, speaks (dialogue is driven by main.py), then stands and fights.  The room is sealed until
he falls; afterwards a path opens in the east wall and a portal carries the hero back to Hearthmoor.  He is an ``Enemy`` subclass, so the sword, magic bolts, knock-back,
depth sorting and dungeon lighting in combat.py all work on him without special cases.

PHASES (by health)
  1  100% - 66%   spear THRUST (long lane), ground SLAM (circle), bolt FAN
  2   66% - 33%   faster; adds the horn CHARGE (rams along a lane - if he hits a wall he is stunned and takes
                  extra damage) and the SPIRAL barrage; summons two skeletons and a dark mage
  3   33% -  0%   enraged: fastest, 7-bolt fans fired twice, slams also throw a ring of bolts, longer spirals;
                  summons a wraith, a dark mage, a witch and a skeleton
During the fight the hero takes real damage (even while INFINITE_HP is on elsewhere).  If the hero is knocked
out, Grimhorn returns to his throne at full health and the fight restarts.

Every attack is telegraphed with a red danger zone, exactly like the normal monsters.  Tuning numbers are
at the top of this file.
"""
import math
import os
import random

import pygame

from combat import CHEST, Enemy, glow, scale_color
from dungeon import DH, DW, T
from entities import Mover

HERE = os.path.dirname(os.path.abspath(__file__))
SPRITE_PATH = os.path.join(HERE, "assets", "boss", "shaman.png")      # 3 cols x 4 rows: down, left, up, right
COLS, ROWS = 3, 4
ROW_OF = {"down": 0, "left": 1, "up": 2, "right": 3}
VIEW_W, VIEW_H = 640, 360

# --------------------------------------------------------------------------- tuning
BOSS_NAME = "GRIMHORN"
BOSS_TITLE = "Warden of the Hollow"
BOSS_HP = 1150
PHASE_AT = (0.66, 0.33)                 # health fractions where phase 2 / 3 begin
SPEED = (64.0, 76.0, 88.0)              # walking speed per phase (px/s)
PACE = (0.86, 0.74, 0.62)               # wind-up time multiplier per phase (lower = faster attacks)
COOLDOWN = (1.05, 0.82, 0.60)           # pause between attacks per phase
RISE_TIME, ROAR_TIME, STUN_TIME, DYING_TIME = 2.6, 1.6, 1.6, 3.3
STUN_DAMAGE_MUL = 1.5

ATK = {
    "thrust": dict(windup=.72, strike=.18, recover=.55, reach=135, half=14, dmg=30, lunge=250),
    "slam":   dict(windup=.95, strike=.30, recover=.75, radius=88, dmg=34),
    "fan":    dict(windup=.80, strike=.05, recover=.60, dmg=16),
    "charge": dict(windup=.90, dash=.80, recover=.65, speed=340, half=16, dmg=38, length=260),
    "spiral": dict(windup=.85, strike=1.5, recover=.75, dmg=13),
}
RED = (255, 60, 40)
MINIONS = {2: ("skeleton", "skeleton", "dark_mage"), 3: ("wraith", "dark_mage", "witch", "skeleton")}
MINION_LEVEL, MINION_CAP = 4, 5


# --------------------------------------------------------------------------- sprite
_SPR = {}


def _fallback_frames():
    """Plain silhouette used only if assets/boss/shaman.png is missing."""
    s = pygame.Surface((64, 90), pygame.SRCALPHA)
    pygame.draw.rect(s, (96, 40, 44), (18, 36, 28, 46))
    pygame.draw.ellipse(s, (226, 214, 196), (6, 26, 52, 36))
    pygame.draw.circle(s, (150, 110, 100), (32, 24), 11)
    pygame.draw.arc(s, (200, 186, 160), (2, 0, 28, 26), 0.2, 3.0, 3)
    pygame.draw.arc(s, (200, 186, 160), (34, 0, 28, 26), 0.2, 3.0, 3)
    return {d: [s, s, s] for d in ROW_OF}


def _eye_spots(img):
    """Glowing-red head markings of a frame (top third) -> up to two screen-space points."""
    w, h = img.get_size()
    pts = []
    for y in range(int(h * 0.30)):
        for x in range(w):
            c = img.get_at((x, y))
            if c[3] > 200 and c[0] > 190 and c[1] < 95 and c[2] < 95:
                pts.append((x, y))
    if not pts:
        return []
    mx = sum(p[0] for p in pts) / len(pts)
    left = [p for p in pts if p[0] < mx]
    right = [p for p in pts if p[0] >= mx]
    out = []
    for grp in (left, right):
        if len(grp) >= 2:
            out.append((sum(p[0] for p in grp) / len(grp), sum(p[1] for p in grp) / len(grp)))
    return out if len(out) == 2 and abs(out[0][0] - out[1][0]) > 3 else [(sum(p[0] for p in pts) / len(pts),
                                                                          sum(p[1] for p in pts) / len(pts))]


def load_sprite():
    """(frames[dir][0..2], eyes[dir][0..2], portrait) - loaded once."""
    if "s" not in _SPR:
        try:
            sheet = pygame.image.load(SPRITE_PATH).convert_alpha()
            cw, ch = sheet.get_width() // COLS, sheet.get_height() // ROWS
            frames = {d: [sheet.subsurface((c * cw, r * ch, cw, ch)).copy() for c in range(COLS)]
                      for d, r in ROW_OF.items()}
        except Exception:
            frames = _fallback_frames()
        eyes = {d: [_eye_spots(f) for f in fl] for d, fl in frames.items()}
        front = frames["down"][1]
        portrait = pygame.Surface((64, 64))
        portrait.fill((28, 16, 30))
        head = front.subsurface((int(front.get_width() * .2), 0, int(front.get_width() * .6),
                                 int(front.get_height() * .42))).copy()
        k = min(60 / head.get_width(), 60 / head.get_height())
        head = pygame.transform.smoothscale(head, (int(head.get_width() * k), int(head.get_height() * k)))
        portrait.blit(head, ((64 - head.get_width()) // 2, 62 - head.get_height()))
        pygame.draw.rect(portrait, (170, 90, 110), portrait.get_rect(), 2)
        _SPR["s"] = (frames, eyes, portrait)
    return _SPR["s"]


def dir_of(dx, dy):
    if abs(dx) > abs(dy) * 1.15:
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


_FONTS = {}


def font_of(size):
    if size not in _FONTS:
        _FONTS[size] = pygame.font.Font(None, size)
    return _FONTS[size]


def lane_points(ox, oy, ang, length, hw):
    c, s = math.cos(ang), math.sin(ang)
    a, b = (ox - s * hw, oy + c * hw), (ox + s * hw, oy - c * hw)
    return [a, b, (b[0] + c * length, b[1] + s * length), (a[0] + c * length, a[1] + s * length)]


def shadow_text(v, font, text, x, y, color, center=False, sh=(20, 8, 14)):
    img, dark = font.render(text, True, color), font.render(text, True, sh)
    if center:
        x -= img.get_width() // 2
    v.blit(dark, (x + 1, y + 1))
    v.blit(img, (x, y))


# --------------------------------------------------------------------------- the boss
class Boss(Enemy):
    is_boss = True
    chest = 36                         # hit / aim centre above the feet (the sprite is tall)

    def __init__(self, x, y, level):
        Mover.__init__(self, x, y)
        self.FW, self.FH = 30, 12
        self.key, self.kind, self.level = "boss", "boss", level
        self.d = dict(color=(215, 50, 60), reach=40, windup=.8, bolt=150)
        self.big, self.fly = True, False
        self.r = 30
        self.frames = None
        self.max_hp = self.hp = BOSS_HP
        self.dmg = 20
        self.speed = SPEED[0]
        self.cd_base = COOLDOWN[0]
        self.state, self.state_t, self.state_total = "seated", 0.0, RISE_TIME
        self.cd = 1.0
        self.aim = 0.0
        self.t = 0.0
        self.flash = 0.0
        self.hp_show = 0.0
        self.kv, self.kb_t = [0.0, 0.0], 0.0
        self.dead_t = 0.0
        self.stuck_t = 0.0
        self.strafe = random.choice((-1, 1))
        self.strafe_t = random.uniform(1.0, 2.5)
        self.dir = "down"
        # boss specifics
        self.phase = 1
        self.atk = None
        self.last = None
        self.second = False
        self.hit_done = False
        self.summoned = False
        self.immune = True                 # until the rise is over
        self.immune_cd = 0.0
        self.dmg_mul = 1.0
        self.knock_mul = 0.05
        self.face = 1
        self.look = "down"
        self.boom_t = 0.0
        self.roar_fx_t = 0.0
        self.eye_scr = []
        self.reveal = 1.0
        self.spiral_t, self.spiral_a = 0.0, 0.0
        self.frames_by_dir, self.eyes_by_dir, self.portrait = load_sprite()

    # ------------------------------------------------------------------ helpers
    @property
    def pace(self):
        return PACE[self.phase - 1]

    def windup_progress(self):
        if self.state != "windup" or self.state_total <= 0:
            return 0.0
        return max(0.0, min(1.0, 1 - self.state_t / self.state_total))

    def wake(self, cb):                    # no waking up, no alerting neighbours
        pass

    def awaken(self, cb):
        """Called when the throne-room speech ends: he stands, roars and the fight begins."""
        if self.state == "seated":
            self.state, self.state_t = "rise", 0.0
            self.immune = True

    def origin(self):
        return self.x, self.y - CHEST

    def _lane_hit(self, cb, ang, length, hw):
        ox, oy = self.origin()
        p = cb.player
        dx, dy = p.x - ox, (p.y - CHEST) - oy
        c, s = math.cos(ang), math.sin(ang)
        along, perp = dx * c + dy * s, -dx * s + dy * c
        return -10 <= along <= length and abs(perp) <= hw + 8

    # ------------------------------------------------------------------ death
    def die(self, cb):
        self.state, self.state_t = "dying", 0.0
        self.immune = True
        self.boom_t = 0.0
        for e in cb.enemies:               # minions fall with their master
            if e is not self and e.alive:
                e.hp = 0
                e.die(cb)
                cb.burst(e.x, e.y - CHEST, e.d["color"], 14, 140, .5, 2)
        cb.sfx.play("roar")
        cb.toast("GRIMHORN falls!", 3)

    # ------------------------------------------------------------------ update
    def update(self, dt, cb):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        self.immune_cd = max(0.0, self.immune_cd - dt)
        self.stuck_t = max(0.0, self.stuck_t - dt)
        self.cd = max(0.0, self.cd - dt)
        self.moving = False
        s = self.state
        if s == "seated":                  # lounging on the throne, watching the hero
            self.look = "down"
            return
        if s == "dead":
            self.dead_t += dt
            return
        if s == "dying":
            self._dying(dt, cb)
            return
        if s == "rise":
            self._rise(dt, cb)
            return
        p = cb.player
        dx, dy = p.x - self.x, p.y - self.y
        dist = math.hypot(dx, dy) or 0.001
        ux, uy = dx / dist, dy / dist
        self.speed = SPEED[self.phase - 1]
        self.cd_base = COOLDOWN[self.phase - 1]
        if s == "chase":
            self._chase(dt, cb, dist, ux, uy)
        elif s == "windup":
            self._windup(dt, cb, ux, uy)
        elif s == "strike":
            self._strike(dt, cb, ux, uy)
        elif s == "dash":
            self._dash(dt, cb)
        elif s == "recover":
            self.state_t -= dt
            self.face = 1 if ux >= 0 else -1
            if self.state_t <= 0:
                self.state, self.cd = "chase", self.cd_base * random.uniform(0.9, 1.2)
        elif s == "stun":
            self.state_t -= dt
            if self.state_t <= 0:
                self.state, self.dmg_mul, self.cd = "chase", 1.0, 0.6
        elif s == "roar":
            self._roar(dt, cb)

    # ---- intro: he rises from the throne
    def _rise(self, dt, cb):
        self.state_t += dt
        t = self.state_t
        self.look = "down"
        cb.shake(1 + 3 * min(1.0, t / 1.2), 0.1)
        if random.random() < dt * 40:      # dust and sparks shaken loose
            cb.particles.append([self.x + random.uniform(-30, 30), self.y - random.uniform(0, 60),
                                 random.uniform(-14, 14), random.uniform(-60, -20), .6, .6,
                                 random.choice(((200, 60, 70), (150, 70, 200), (90, 80, 90))), 2])
        if 1.0 <= t < 1.0 + dt:            # the roar
            cb.sfx.play("roar")
            cb.shake(7, 0.9)
            cb.burst(self.x, self.y - 40, (220, 70, 80), 30, 200, .6, 3)
        if t >= RISE_TIME:
            self.state, self.immune, self.cd = "chase", False, 0.7

    # ---- chasing / choosing an attack
    def _chase(self, dt, cb, dist, ux, uy):
        self.face = 1 if ux >= 0 else -1
        if self._phase_check(cb):
            return
        p = cb.player
        los = cb.sight(self.x, self.y, p.x, p.y)
        if self.cd <= 0:
            atk = self._pick(dist, los)
            if atk:
                self._begin(cb, atk, ux, uy)
                return
        if dist > 62:
            self.approach(cb, dt)
        else:
            self.circle(cb, dt, ux, uy, 0.4)

    def _pick(self, dist, los):
        ph = self.phase
        w = {}
        if dist < 100:
            w["slam"], w["thrust"] = 3, 3
        elif dist < 175:
            w["thrust"], w["slam"] = 3, 1
        if los and 70 < dist < 300:
            w["fan"] = 2 + (ph >= 3)
        if ph >= 2 and los and 60 < dist < 280:
            w["charge"] = 2 if dist < 100 else 3
        if ph >= 3 and dist < 110:
            w["slam"] = w.get("slam", 0) + 2
        if ph >= 2 and dist > 60:
            w["spiral"] = 2 + (ph >= 3)
        if self.last in w and len(w) > 1:
            w.pop(self.last)               # never the same attack twice in a row
        if not w:
            return None
        return random.choices(list(w), weights=list(w.values()))[0]

    def _begin(self, cb, atk, ux, uy):
        self.atk = self.last = atk
        self.state = "windup"
        self.state_total = self.state_t = ATK[atk]["windup"] * self.pace
        self.aim = math.atan2(uy, ux)
        self.second = False
        cb.sfx.play("charge")

    def _phase_check(self, cb):
        frac = self.hp / self.max_hp
        if self.phase <= len(PHASE_AT) and frac <= PHASE_AT[self.phase - 1]:
            self.phase += 1
            self.state, self.state_t, self.state_total = "roar", ROAR_TIME, ROAR_TIME
            self.immune, self.summoned, self.roar_fx_t = True, False, 0.0
            cb.sfx.play("roar")
            cb.shake(5, 1.2)
            cb.toast("GRIMHORN is enraged!" if self.phase == 3 else "GRIMHORN roars - he calls his servants!", 3)
            return True
        return False

    # ---- attacks
    def _windup(self, dt, cb, ux, uy):
        self.state_t -= dt
        if self.atk != "slam" and self.state_t > 0.3 * self.state_total:
            self.aim = math.atan2(uy, ux)            # tracks you, then commits to a direction
        self.face = 1 if (ux if self.atk == "slam" else math.cos(self.aim)) >= 0 else -1
        if self.state_t <= 0:
            self._fire(cb)

    def _fire(self, cb):
        atk, a = self.atk, ATK[self.atk]
        ox, oy = self.origin()
        if atk == "thrust":
            self.state, self.state_t = "strike", a["strike"]
            cb.sfx.play("swing")
            cb.shake(3, 0.15)
            if self._lane_hit(cb, self.aim, a["reach"], a["half"]):
                cb.hurt_player(a["dmg"], ox, oy)
        elif atk == "slam":
            self.state, self.state_t = "strike", a["strike"]
            cb.sfx.play("slam")
            cb.shake(7, 0.4)
            cb.burst(self.x, self.y - 6, (200, 165, 125), 26, 190, .5, 3)
            if cb.player_in_circle(self.x, self.y - 8, a["radius"]):
                cb.hurt_player(a["dmg"], self.x, self.y - 8)
            if self.phase >= 3:
                off = random.uniform(0, math.pi / 4)
                for i in range(8):
                    cb.spawn_bolt(ox, oy, off + i * math.pi / 4, 130, 12, "enemy", (255, 90, 60), 5, 2.4)
        elif atk == "fan":
            self.state, self.state_t = "strike", (0.5 if self.phase >= 3 else a["strike"])
            self._volley(cb)
        elif atk == "charge":
            self.state, self.state_t = "dash", a["dash"]
            self.hit_done = False
            cb.sfx.play("roar")
        elif atk == "spiral":
            self.state, self.state_t = "strike", a["strike"] * (1.35 if self.phase >= 3 else 1.0)
            self.spiral_t, self.spiral_a = 0.0, random.uniform(0, math.tau)
            cb.sfx.play("roar")
            cb.shake(3, 0.3)

    def _volley(self, cb):
        n = 5 if self.phase < 2 else 7
        spread = math.radians(13)
        ox, oy = self.origin()
        for i in range(n):
            ang = self.aim + (i - (n - 1) / 2) * spread
            cb.spawn_bolt(ox + math.cos(ang) * 14, oy + math.sin(ang) * 14, ang, 150 + 10 * self.phase,
                          ATK["fan"]["dmg"], "enemy", (255, 80, 70), 5, 2.8)
        cb.burst(ox + math.cos(self.aim) * 14, oy + math.sin(self.aim) * 14, (255, 90, 70), 10, 90, .3)
        cb.sfx.play("cast")

    def _strike(self, dt, cb, ux, uy):
        self.state_t -= dt
        if self.atk == "thrust":
            sp = ATK["thrust"]["lunge"] * dt
            self.step(math.cos(self.aim) * sp, math.sin(self.aim) * sp, cb.world, cb.feet_except(self))
        elif self.atk == "spiral":              # a rotating stream of bolts, two arms (three when enraged)
            self.spiral_t -= dt
            if self.spiral_t <= 0:
                self.spiral_t = 0.11 if self.phase < 3 else 0.085
                self.spiral_a += 0.42
                ox, oy = self.origin()
                arms = 2 if self.phase < 3 else 3
                for i in range(arms):
                    ang = self.spiral_a + i * math.tau / arms
                    cb.spawn_bolt(ox + math.cos(ang) * 14, oy + math.sin(ang) * 14, ang, 125,
                                  ATK["spiral"]["dmg"], "enemy", (255, 90, 60), 5, 3.2)
                cb.sfx.play("cast")
        if self.state_t <= 0:
            if self.atk == "fan" and self.phase >= 3 and not self.second:
                self.second = True               # enraged: a second volley, freshly aimed
                self.aim = math.atan2(uy, ux)
                self.state_t = 0.05
                self._volley(cb)
                return
            self.state, self.state_t = "recover", ATK[self.atk]["recover"] * self.pace

    def _dash(self, dt, cb):
        a = ATK["charge"]
        self.state_t -= dt
        sp = a["speed"] * (1 + 0.08 * (self.phase - 2)) * dt
        minions = [o.foot for o in cb.enemies if o is not self and o.alive]
        moved = self.step(math.cos(self.aim) * sp, math.sin(self.aim) * sp, cb.world, minions)
        self.moving = True
        self.anim += dt * 14
        self.face = 1 if math.cos(self.aim) >= 0 else -1
        cb.burst(self.x, self.y - 4, (190, 160, 130), 1, 40, .3)
        if not self.hit_done and cb.player_in_circle(self.x, self.y - CHEST, 26):
            self.hit_done = True
            if cb.hurt_player(a["dmg"], self.x, self.y):
                self.state, self.state_t = "recover", a["recover"] * self.pace
                return
        if not moved:                            # slammed into a wall or pillar: stunned and vulnerable
            self.state, self.state_t = "stun", STUN_TIME
            self.dmg_mul = STUN_DAMAGE_MUL
            cb.shake(8, 0.5)
            cb.sfx.play("slam")
            cb.burst(self.x + math.cos(self.aim) * 18, self.y - 20, (190, 170, 150), 22, 170, .5, 3)
            cb.text("Stunned!", self.x, self.y - 100, (255, 235, 140), 1.1)
        elif self.state_t <= 0:
            self.state, self.state_t = "recover", a["recover"] * self.pace

    # ---- phase change: roar + summon
    def _roar(self, dt, cb):
        self.state_t -= dt
        prog = 1 - self.state_t / self.state_total
        self.roar_fx_t -= dt
        if self.roar_fx_t <= 0:
            self.roar_fx_t = 0.12
            cb.burst(self.x, self.y - 30, (190, 70, 220), 8, 150, .5, 2)
        if prog > 0.45 and not self.summoned:
            self.summoned = True
            self._summon(cb)
        if self.state_t <= 0:
            self.state, self.immune, self.cd = "chase", False, 0.7

    def _summon(self, cb):
        keys = MINIONS.get(self.phase, ())
        room = MINION_CAP - sum(1 for e in cb.enemies if e.alive and not e.is_boss)
        keys = keys[:max(0, room)]
        if not keys:
            return
        p, w = cb.player, cb.world
        cands = [(x, y) for y in range(6, DH - 2) for x in range(2, DW - 2)
                 if w.walkable_tile(x, y) and math.hypot(x * T + 16 - p.x, y * T + 16 - p.y) >= 5 * T
                 and math.hypot(x * T + 16 - self.x, y * T + 16 - self.y) >= 2.5 * T
                 and all(w.walkable_tile(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
        random.shuffle(cands)
        chosen = []
        for c in cands:
            if len(chosen) >= len(keys):
                break
            if all(math.hypot(c[0] - o[0], c[1] - o[1]) >= 3 for o in chosen):
                chosen.append(c)
        for key, (tx, ty) in zip(keys, chosen):
            e = Enemy(key, tx, ty, MINION_LEVEL, cb.getframes)
            e.state = "chase"
            cb.enemies.append(e)
            cb.burst(e.x, e.y - CHEST, e.d["color"], 18, 150, .6, 3)

    # ---- death
    def _dying(self, dt, cb):
        self.state_t += dt
        self.boom_t -= dt
        if self.boom_t <= 0:
            self.boom_t = 0.11
            bx, by = self.x + random.uniform(-24, 24), self.y - random.uniform(8, 80)
            cb.burst(bx, by, random.choice(((255, 90, 60), (255, 200, 90), (200, 80, 220))), 14, 150, .5, 3)
            cb.sfx.play("boom")
            cb.shake(3, 0.2)
        if self.state_t >= DYING_TIME:
            cb.burst(self.x, self.y - 40, (255, 220, 150), 50, 260, .9, 4)
            cb.burst(self.x, self.y - 40, (220, 70, 80), 40, 200, .8, 3)
            cb.sfx.play("die")
            cb.shake(9, 0.7)
            self.state, self.dead_t = "dead", 0.0

    # ------------------------------------------------------------------ drawing
    def draw(self, cb, surf, camx, camy, shadow):
        sx, sy = int(self.x) - camx, int(self.y) - camy
        if not (-90 < sx < VIEW_W + 90 and -130 < sy < VIEW_H + 130):
            self.eye_scr = []
            return
        s, t = self.state, self.t
        p = cb.player
        if s in ("seated", "rise"):
            d = "down"
        elif s in ("windup", "strike", "dash"):
            d = dir_of(math.cos(self.aim), math.sin(self.aim))
        else:
            d = dir_of(p.x - self.x, p.y - self.y)
        idx = (0, 1, 2, 1)[int(self.anim) % 4] if self.moving else 1
        base = self.frames_by_dir[d][idx]
        eyes = self.eyes_by_dir[d][idx]
        w, h = base.get_size()
        sxs = sys_ = 1.0
        ox = oy = 0.0
        lift = -abs(math.sin(self.anim * 0.9)) * 2.5 if self.moving else math.sin(t * 2.2) * 0.8
        tint = None
        k = self.windup_progress()
        if s == "windup":
            sys_, sxs = 1 - .07 * k, 1 + .05 * k
            ox, oy = -math.cos(self.aim) * 4 * k, -math.sin(self.aim) * 3 * k
            if k > .7:
                ox += random.randint(-1, 1)
            tint = (int(k * 3) * 26, 0, 0)
        elif s in ("strike", "dash"):
            sys_ = 1.05
            ox, oy = math.cos(self.aim) * 6, math.sin(self.aim) * 5
            if self.atk == "spiral":
                ox, oy, sys_ = random.randint(-1, 1), 0, 1.04
        elif s == "roar":
            sys_, sxs = 1.06 + .02 * math.sin(t * 30), 0.98
            ox = random.randint(-1, 1)
            tint = (52, 0, 26)
        elif s == "rise":
            sys_ = 1.0 + .05 * math.sin(min(1.0, self.state_t / 1.0) * math.pi)
            tint = (40, 0, 20) if self.state_t > 0.9 else None
        elif s == "stun":
            sys_, sxs = .94, 1.03
            tint = (0, 0, 40) if int(t * 8) % 2 == 0 else None
        elif s == "dying":
            ox, oy = random.randint(-2, 2), random.randint(-1, 1)
            tint = (150, 150, 150) if int(t * 14) % 2 == 0 else (90, 0, 0)
        elif self.phase >= 3 and s != "seated":
            tint = (int(26 + 26 * (1 + math.sin(t * 5)) / 2) // 26 * 26, 0, 0)
        if self.flash > 0:
            tint = (170, 170, 170)
        img = cb.tinted(base, tint) if tint else base
        if (sxs, sys_) != (1.0, 1.0):
            img = pygame.transform.scale(img, (int(w * sxs), int(h * sys_)))
        iw, ih = img.get_size()
        px = int(sx - iw // 2 + ox)
        py = int(sy - ih + 6 + lift + oy)
        if s != "seated":
            sw = pygame.transform.scale(shadow, (56, 20))
            surf.blit(sw, (sx - 28, sy - 12))
        top = 0                                       # rows of the sprite that are cut away
        if s == "dying":                              # dissolves from the top down
            top = int(ih * max(0.0, min(1.0, (self.state_t - 1.2) / 1.9)))
            if top < ih and int(t * 30) % 5 != 0:
                surf.blit(img, (px, py + top), pygame.Rect(0, top, iw, ih - top))
        elif s != "dead":
            surf.blit(img, (px, py))
        # where the eyes ended up on screen (used for the glow in draw_fx)
        self.eye_scr = []
        if s != "dead":
            for ex, ey in eyes:
                gx, gy = px + ex * sxs, py + ey * sys_
                if s == "dying" and ey * sys_ < top:
                    continue
                self.eye_scr.append((int(gx), int(gy)))
        if s == "stun":                               # dizzy stars
            for i in range(3):
                a = t * 5 + i * 2.1
                pygame.draw.circle(surf, (255, 235, 120), (int(sx + math.cos(a) * 18), int(py + 6 + math.sin(a) * 5)), 2)

    def draw_fx(self, cb, fx, S):
        """Additive layer: glowing eyes and attack telegraphs."""
        s, k = self.state, self.windup_progress()
        ox, oy = self.origin()
        if self.eye_scr:
            r = 6 + (3 if self.phase >= 3 else 0) + (8 * k if s == "windup" else 0) + (4 if s == "roar" else 0)
            for ex, ey in self.eye_scr:
                glow(fx, ex, ey, r, (255, 50, 40), 0.95)
        if s == "rise":                               # dark aura as he stands
            fx_x, fx_y = S(self.x, self.y)
            prog = min(1.0, self.state_t / 1.0)
            pygame.draw.ellipse(fx, scale_color((200, 40, 70), .6 * prog), (fx_x - 56, fx_y - 18, 112, 36), 2)
            pygame.draw.ellipse(fx, scale_color((150, 70, 220), .5 * prog), (fx_x - 36, fx_y - 11, 72, 22), 1)
            glow(fx, fx_x, fx_y - 40, 52, (220, 60, 90), .35 * prog)
        elif s == "windup":
            a = ATK[self.atk]
            if self.atk == "thrust":
                self._lane_fx(cb, fx, S, a["reach"], a["half"], k)
            elif self.atk == "charge":
                self._lane_fx(cb, fx, S, a["length"], a["half"], k, clip=True)
            elif self.atk == "slam":
                cx, cy = S(self.x, self.y - 8)
                R = a["radius"]
                pygame.draw.circle(fx, (int(110 * k) + 20, int(14 * k), int(10 * k)), (cx, cy), R)
                pygame.draw.circle(fx, (int(255 * (.4 + .6 * k)), int(60 * k), int(40 * k)), (cx, cy), R, 2)
                pygame.draw.circle(fx, (int(255 * k), int(90 * k), int(60 * k)), (cx, cy), max(2, int(R * k)), 1)
            elif self.atk == "spiral":
                cx, cy = S(ox, oy)
                for i in range(3):
                    rr = int(10 + 38 * ((k * 2 + i / 3) % 1.0))
                    pygame.draw.circle(fx, scale_color((255, 80, 70), .25 + .5 * k), (cx, cy), rr, 1)
                glow(fx, cx, cy, 14 + 12 * k, (255, 70, 60), .3 + .5 * k)
            elif self.atk == "fan":
                n = 5 if self.phase < 2 else 7
                spread = math.radians(13)
                hx, hy = S(ox + math.cos(self.aim) * 14, oy + math.sin(self.aim) * 14)
                glow(fx, hx, hy, 6 + 10 * k, (255, 80, 70), .4 + .6 * k)
                for i in range(n):
                    ang = self.aim + (i - (n - 1) / 2) * spread
                    ex, ey = cb.ray_end(ox, oy, ang, 280)
                    pygame.draw.line(fx, scale_color((255, 80, 70), .22 + .3 * k), (hx, hy), S(ex, ey), 1)
        elif s == "strike":
            kk = max(0.0, self.state_t / max(0.01, ATK[self.atk].get("strike", .2)))
            if self.atk == "thrust":
                pts = [S(*pt) for pt in lane_points(ox, oy, self.aim, ATK["thrust"]["reach"], ATK["thrust"]["half"])]
                pygame.draw.polygon(fx, scale_color((255, 235, 210), .55 * kk), pts)
                pygame.draw.polygon(fx, scale_color((255, 255, 255), kk), pts, 2)
            elif self.atk == "slam":
                cx, cy = S(self.x, self.y - 8)
                R = ATK["slam"]["radius"]
                pygame.draw.circle(fx, scale_color((255, 190, 120), kk), (cx, cy), int(R * (1.25 - .25 * kk)), 3)
                pygame.draw.circle(fx, scale_color((140, 70, 40), .6 * kk), (cx, cy), R)
        elif s == "roar":
            cx, cy = S(self.x, self.y - 26)
            for i in range(3):
                ph = ((self.t * 1.6) + i / 3) % 1.0
                pygame.draw.circle(fx, scale_color((190, 70, 230), 1 - ph), (cx, cy), int(14 + 90 * ph), 2)
            glow(fx, cx, cy, 40, (200, 50, 120), .6)
        elif s == "dash":
            cx, cy = S(self.x, self.y - 20)
            glow(fx, cx, cy, 30, (255, 90, 60), .5)
        elif s == "stun":
            cx, cy = S(self.x, self.y - 60)
            glow(fx, cx, cy, 16, (255, 235, 120), .4 + .2 * math.sin(self.t * 12))

    def _lane_fx(self, cb, fx, S, length, hw, k, clip=False):
        ox, oy = self.origin()
        if clip:                                      # the charge stops at walls - show where
            ex, ey = cb.ray_end(ox, oy, self.aim, length)
            length = min(length, math.hypot(ex - ox, ey - oy))
        pts = [S(*pt) for pt in lane_points(ox, oy, self.aim, length, hw)]
        pygame.draw.polygon(fx, (int(80 * k) + 18, int(10 * k), int(8 * k)), pts)
        pygame.draw.polygon(fx, (int(255 * (.4 + .6 * k)), int(60 * k), int(40 * k)), pts, 1)
        fill = [S(*pt) for pt in lane_points(ox, oy, self.aim, max(2.0, length * k), hw - 2)]
        pygame.draw.polygon(fx, (int(170 * k) + 20, int(26 * k), int(20 * k)), fill)

    # ------------------------------------------------------------------ HUD
    def draw_ui(self, cb, v, font, font_s):
        s, t = self.state, self.state_t
        if s == "seated":
            return
        if s == "rise":                               # cinematic bars + name card
            k = max(0.0, min(1.0, t / 0.5, (RISE_TIME - t) / 0.5))
            bar = int(26 * k)
            pygame.draw.rect(v, (0, 0, 0), (0, 0, VIEW_W, bar))
            pygame.draw.rect(v, (0, 0, 0), (0, VIEW_H - bar, VIEW_W, bar))
            if t > 1.0:
                a = max(0.0, min(1.0, (t - 1.0) / 0.4, (RISE_TIME - t) / 0.4))
                col = lambda c: scale_color(c, a)
                shadow_text(v, font, "- FINAL BOSS -", VIEW_W // 2, 96, col((220, 180, 100)), True)
                shadow_text(v, font_of(60), BOSS_NAME, VIEW_W // 2, 112, col((240, 70, 70)), True)
                shadow_text(v, font_of(26), BOSS_TITLE, VIEW_W // 2, 150, col((232, 212, 224)), True)
        if s == "dead":
            return
        # boss health bar (bottom centre, right of the player panel)
        x, y, wbar, hbar = 252, VIEW_H - 30, 376, 14
        shown = max(0.0, min(1.0, (t - 1.0) / 1.2)) if s == "rise" else 1.0
        frac = max(0.0, self.hp / self.max_hp) * shown
        panel = pygame.Surface((wbar + 12, hbar + 26), pygame.SRCALPHA)
        pygame.draw.rect(panel, (22, 12, 26, 215), panel.get_rect(), border_radius=7)
        pygame.draw.rect(panel, (170, 90, 110, 235), panel.get_rect(), 1, border_radius=7)
        v.blit(panel, (x - 6, y - 20))
        shadow_text(v, font_s, f"{BOSS_NAME}  -  {BOSS_TITLE}", x, y - 16, (240, 205, 215))
        pygame.draw.rect(v, (40, 12, 18), (x, y, wbar, hbar), border_radius=4)
        col = (225, 60, 60) if self.phase == 1 else ((235, 120, 50) if self.phase == 2 else (200, 40, 180))
        if frac > 0:
            pygame.draw.rect(v, col, (x, y, max(2, int(wbar * frac)), hbar), border_radius=4)
            pygame.draw.rect(v, scale_color(col, .55), (x, y + hbar // 2, max(2, int(wbar * frac)), hbar // 2 - 1),
                             border_radius=3)
        for f in PHASE_AT:                            # phase notches
            pygame.draw.line(v, (255, 235, 240), (x + int(wbar * f), y), (x + int(wbar * f), y + hbar - 1), 1)
        pygame.draw.rect(v, (255, 215, 225), (x, y, wbar, hbar), 1, border_radius=4)
        if self.immune and s != "rise":
            shadow_text(v, font_s, "IMMUNE", x + wbar - 40, y - 16, (190, 190, 230))
        elif s == "stun":
            shadow_text(v, font_s, "STUNNED  x1.5 damage", x + wbar - 112, y - 16, (255, 235, 140))


def draw_victory(cb, v, font, font_s):
    """Full-screen overlay once Grimhorn is dead.  E / Enter continues (see Combat.dismiss_victory)."""
    t = cb.victory_t
    dim = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    dim.fill((8, 4, 14, int(min(1.0, t / 1.2) * 190)))
    v.blit(dim, (0, 0))
    for i in range(26):                               # drifting golden motes
        a = i * 2.399
        mx = (VIEW_W * (0.5 + 0.48 * math.sin(a * 3.1)) + math.sin(t * .8 + a) * 14) % VIEW_W
        my = (VIEW_H + 20 - ((t * (14 + (i % 5) * 6) + i * 53) % (VIEW_H + 40)))
        pygame.draw.circle(v, scale_color((255, 215, 120), min(1.0, t / 1.5)), (int(mx), int(my)), 1 + i % 2)
    if t < 0.8:
        return
    a = min(1.0, (t - 0.8) / 0.8)
    c = lambda col: scale_color(col, a)
    shadow_text(v, font_of(84), "VICTORY", VIEW_W // 2, 70, c((255, 218, 120)), True, (70, 36, 20))
    shadow_text(v, font_of(26), "Grimhorn, Warden of the Hollow, is no more.", VIEW_W // 2, 140, c((240, 226, 236)), True)
    shadow_text(v, font_of(22), "The Hollow Below is free - a path home has opened.", VIEW_W // 2, 166,
                c((200, 190, 215)), True)
    m, s = divmod(int(cb.boss_time), 60)
    shadow_text(v, font, f"Foes slain: {cb.kills}      Hits taken: {cb.hits_taken}      Boss fight: {m}:{s:02d}",
                VIEW_W // 2, 214, c((255, 230, 160)), True)
    if t > 1.8 and int(t * 2) % 2 == 0:
        shadow_text(v, font, "Press E to continue", VIEW_W // 2, 280, (255, 255, 255), True)
