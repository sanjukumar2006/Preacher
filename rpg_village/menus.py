"""Title screen, main / pause menus, controls page and the interactive tutorial for Hearthmoor."""
import math
import random

import pygame

VIEW_W, VIEW_H = 640, 360
GOLD = (255, 226, 150)
CREAM = (255, 246, 226)
DIM = (200, 188, 168)
SHADOW = (40, 24, 20)


def wrap(font, text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------------------ menu list
class MenuList:
    """A vertical list of buttons. entries = [(key, label_or_callable)]."""

    def __init__(self, entries, top, gap=29, width=230):
        self.entries = entries
        self.top, self.gap, self.width = top, gap, width
        self.sel = 0

    def label(self, i):
        lab = self.entries[i][1]
        return lab() if callable(lab) else lab

    def key(self):
        return self.entries[self.sel][0]

    def move(self, d):
        self.sel = (self.sel + d) % len(self.entries)

    def rect(self, i):
        return pygame.Rect((VIEW_W - self.width) // 2, self.top + i * self.gap, self.width, self.gap - 5)

    def hover(self, pos):
        for i in range(len(self.entries)):
            if self.rect(i).collidepoint(pos):
                self.sel = i
                return True
        return False

    def draw(self, g, v, t):
        for i in range(len(self.entries)):
            r = self.rect(i)
            on = i == self.sel
            s = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(s, (66, 38, 30, 225) if on else (32, 22, 26, 165), s.get_rect(), border_radius=9)
            pygame.draw.rect(s, (255, 214, 120, 255) if on else (150, 120, 90, 150), s.get_rect(),
                             2 if on else 1, border_radius=9)
            v.blit(s, r.topleft)
            col = (255, 242, 196) if on else (204, 190, 166)
            g.text_shadow(v, g.font_m, self.label(i), (r.centerx, r.centery - g.font_m.get_height() // 2 + 1),
                          col, SHADOW, True)
            if on:
                b = int(math.sin(t * 7) * 2)
                cy = r.centery
                pygame.draw.polygon(v, GOLD, [(r.x + 9 + b, cy - 5), (r.x + 9 + b, cy + 5), (r.x + 17 + b, cy)])
                pygame.draw.polygon(v, GOLD, [(r.right - 9 - b, cy - 5), (r.right - 9 - b, cy + 5), (r.right - 17 - b, cy)])


# ------------------------------------------------------------------------------ title scene
_VIG = None


def _vignette():
    global _VIG
    if _VIG is None:
        s = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        for y in range(VIEW_H):
            top = max(0.0, 1 - y / 130.0)
            bot = max(0.0, 1 - (VIEW_H - 1 - y) / 110.0)
            a = int(190 * max(top, bot) ** 1.4 + 75)
            s.fill((12, 8, 26, min(255, a)), (0, y, VIEW_W, 1))
        _VIG = s
    return _VIG


def make_motes(n=34):
    rnd = random.Random(11)
    motes = []
    for _ in range(n):
        r = rnd.choice((1, 2, 2, 3))
        img = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(img, (255, 226, 140, 255), (r + 1, r + 1), r)
        motes.append(dict(x=rnd.uniform(0, VIEW_W), y=rnd.uniform(0, VIEW_H), rise=rnd.uniform(6, 20),
                          sw=rnd.uniform(8, 26), sp=rnd.uniform(0.4, 1.3), ph=rnd.uniform(0, 6.28), img=img))
    return motes


def _logo(g, v, text, cx, y):
    f = g.font_b
    base = f.render(text, True, (255, 222, 140))
    hi = f.render(text, True, (255, 248, 214))
    mid = f.render(text, True, (96, 46, 30))
    outl = f.render(text, True, (28, 14, 22))
    x = cx - base.get_width() // 2
    for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3), (0, -2), (-2, 0), (2, 0)):
        v.blit(outl, (x + dx, y + dy))
    v.blit(mid, (x + 1, y + 3))
    v.blit(base, (x, y))
    v.blit(hi, (x, y), (0, 0, base.get_width(), base.get_height() // 3))


def _ornament(v, cx, y, half=130):
    c = (214, 178, 120)
    pygame.draw.line(v, c, (cx - half, y), (cx - 14, y))
    pygame.draw.line(v, c, (cx + 14, y), (cx + half, y))
    pygame.draw.polygon(v, GOLD, [(cx, y - 5), (cx + 7, y), (cx, y + 5), (cx - 7, y)])
    pygame.draw.polygon(v, (70, 38, 24), [(cx, y - 5), (cx + 7, y), (cx, y + 5), (cx - 7, y)], 1)
    for sx in (-1, 1):
        pygame.draw.circle(v, c, (cx + sx * (half + 4), y), 2)


def _dim(v, alpha):
    d = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    d.fill((14, 10, 24, alpha))
    v.blit(d, (0, 0))


def draw_motes(g, v):
    for m in g.motes:
        x = (m["x"] + math.sin(g.t * m["sp"] + m["ph"]) * m["sw"]) % VIEW_W
        y = (m["y"] - g.t * m["rise"]) % VIEW_H
        m["img"].set_alpha(int(70 + 150 * (0.5 + 0.5 * math.sin(g.t * 2.0 * m["sp"] + m["ph"]))))
        v.blit(m["img"], (x, y))


def draw_title_screen(g, v):
    """Main menu screen (logo + buttons) drawn over the live village."""
    v.blit(_vignette(), (0, 0))
    draw_motes(g, v)
    cx = VIEW_W // 2
    bob = math.sin(g.t * 1.6) * 3
    _logo(g, v, "HEARTHMOOR", cx, 34 + bob)
    _ornament(v, cx, 106)
    g.text_shadow(v, g.font_m, "A tiny open-world village adventure", (cx, 116), CREAM, SHADOW, True)
    g.menu_main.draw(g, v, g.t)
    hint = "W / S or UP / DOWN: choose     ENTER: confirm     Mouse works too"
    g.text_shadow(v, g.font_s, hint, (cx, VIEW_H - 22), DIM, SHADOW, True)
    g.text_shadow(v, g.font_s, "v1.1", (VIEW_W - 30, VIEW_H - 22), (150, 140, 128), SHADOW, True)


def draw_ask(g, v):
    """'Would you like a tutorial?' prompt."""
    _dim(v, 150)
    v.blit(_vignette(), (0, 0))
    draw_motes(g, v)
    rect = pygame.Rect(130, 82, 380, 178)
    g.panel(v, rect, 230)
    cx = VIEW_W // 2
    g.text_shadow(v, g.font_m, "Would you like a tutorial?", (cx, rect.y + 14), GOLD, SHADOW, True)
    g.text_shadow(v, g.font_s, "A quick walkthrough of the basic controls.", (cx, rect.y + 40), CREAM, SHADOW, True)
    g.menu_ask.draw(g, v, g.t)
    g.text_shadow(v, g.font_s, "Y: yes     N: no     ESC: back", (cx, rect.bottom - 18), DIM, SHADOW, True)


CONTROLS_VILLAGE = [("WASD / Arrows", "Move"), ("SHIFT", "Run (hold)"), ("SPACE", "Jump"),
                    ("E / ENTER", "Talk / interact"), ("M", "World map"), ("N", "Skip an hour"),
                    ("I", "Inventory"), ("1 / 2", "Health / mana potion"),
                    ("B / H", "Music / help bar"), ("F11 / ESC", "Fullscreen / pause")]
CONTROLS_DUNGEON = [("Left mouse", "Attack (hold)"), ("Right mouse / wheel", "Swap sword / fireball"),
                    ("SPACE", "Dodge roll"), ("E", "Stairs / purple gate"),
                    ("M", "Dungeon map"), ("I", "Inventory"), ("1 / 2", "Drink potions")]


def draw_controls(g, v):
    _dim(v, 175)
    rect = pygame.Rect(34, 28, 572, 304)
    g.panel(v, rect, 240)
    cx = VIEW_W // 2
    g.text_shadow(v, g.font_m, "CONTROLS", (cx, rect.y + 12), GOLD, SHADOW, True)
    _ornament(v, cx, rect.y + 36, 90)
    x0, y0 = rect.x + 20, rect.y + 52
    g.text_shadow(v, g.font, "VILLAGE", (x0, y0), (190, 230, 180), SHADOW)
    for i, (k, d) in enumerate(CONTROLS_VILLAGE):
        y = y0 + 22 + i * 20
        g.text_shadow(v, g.font, k, (x0, y), GOLD, SHADOW)
        g.text_shadow(v, g.font, d, (x0 + 112, y), CREAM, SHADOW)
    x1 = rect.x + 306
    g.text_shadow(v, g.font, "DUNGEON  (The Hollow Below)", (x1, y0), (214, 184, 246), SHADOW)
    for i, (k, d) in enumerate(CONTROLS_DUNGEON):
        y = y0 + 22 + i * 20
        g.text_shadow(v, g.font, k, (x1, y), GOLD, SHADOW)
        g.text_shadow(v, g.font, d, (x1 + 132, y), CREAM, SHADOW)
    tips = ["Fireballs cost 5 MP. Slay every foe to unseal the stairs; clear all 5 floors to open the purple gate. "
            "The goddess statue in the north sanctuary heals you."]
    ty = y0 + 22 + len(CONTROLS_DUNGEON) * 20 + 10
    for tip in tips:
        for ln in wrap(g.font_s, tip, 250):
            g.text_shadow(v, g.font_s, ln, (x1, ty), DIM, SHADOW)
            ty += 14
        ty += 4
    g.text_shadow(v, g.font_s, "F5: quick save (current slot)   -   F9: load latest   -   ESC or ENTER: back", (cx, rect.bottom - 20), DIM, SHADOW, True)


def draw_pause(g, v):
    _dim(v, 175)
    cx = VIEW_W // 2
    g.text_shadow(v, g.font_b, "PAUSED", (cx, 28), GOLD, (70, 36, 24), True)
    _ornament(v, cx, 96, 100)
    g.menu_pause.draw(g, v, g.t)
    g.text_shadow(v, g.font_s, "ESC: resume", (cx, VIEW_H - 22), DIM, SHADOW, True)


def _hour_text(t):
    try:
        h = int(float(t)) % 24
        m = int((float(t) - int(float(t))) * 60)
        return "%02d:%02d" % (h, m)
    except (TypeError, ValueError):
        return "--:--"


def draw_slots(g, v):
    """Save / load slot list (5 manual slots, plus the autosave when loading)."""
    import time as _time
    import save as SAVE
    _dim(v, 185)
    cx = VIEW_W // 2
    saving = g.slot_mode == "save"
    g.text_shadow(v, g.font_b, "SAVE GAME" if saving else "LOAD GAME", (cx, 12), GOLD, (70, 36, 24), True)
    _ornament(v, cx, 52, 110)
    for i, sid in enumerate(g.slot_ids):
        r = g.slot_row_rect(i)
        on = i == g.slot_sel
        info = g.slot_info.get(sid)
        s = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (66, 38, 30, 230) if on else (32, 22, 26, 175), s.get_rect(), border_radius=8)
        pygame.draw.rect(s, (255, 214, 120, 255) if on else (150, 120, 90, 150), s.get_rect(), 2 if on else 1,
                         border_radius=8)
        v.blit(s, r.topleft)
        name = "Autosave" if sid == SAVE.AUTO else "Slot %d" % sid
        g.text_shadow(v, g.font_m, name, (r.x + 12, r.y + 4), GOLD if on else (220, 200, 160), SHADOW)
        if info is None:
            g.text_shadow(v, g.font, "- empty -", (r.x + 112, r.y + 10), DIM, SHADOW)
        elif info.get("broken"):
            g.text_shadow(v, g.font, "unreadable save file", (r.x + 112, r.y + 10), (230, 140, 120), SHADOW)
        else:
            place = info["meta"].get("place") or ("The Hollow Below" if info.get("scene") == "dungeon"
                                                  else "Hearthmoor Village")
            g.text_shadow(v, g.font, place, (r.x + 112, r.y + 4), CREAM, SHADOW)
            stats = "HP %s/%s   Kills %s   %s%s" % (info.get("hp"), info.get("max_hp"), info.get("kills"),
                                                  _hour_text(info.get("time")),
                                                  "   Boss slain" if info.get("boss") else "")
            g.text_shadow(v, g.font_s, stats, (r.x + 112, r.y + 21), DIM, SHADOW)
            ts = _time.strftime("%d %b %Y  %H:%M", _time.localtime(info.get("saved_at", 0)))
            g.text_shadow(v, g.font_s, ts, (r.right - 12 - g.font_s.size(ts)[0], r.y + 21), (170, 160, 140), SHADOW)
        if on and g.slot_confirm and g.slot_confirm[1] == sid:
            msg = "ENTER again: overwrite" if g.slot_confirm[0] == "overwrite" else "DEL again: delete"
            g.text_shadow(v, g.font_s, msg, (r.right - 12 - g.font_s.size(msg)[0], r.y + 5), (255, 170, 130), SHADOW)
    hint = "W/S: choose   ENTER: %s   DEL: delete   ESC: back" % ("save" if saving else "load")
    g.text_shadow(v, g.font_s, hint, (cx, VIEW_H - 22), DIM, SHADOW, True)


# ------------------------------------------------------------------------------ tutorial
def _pointer(g, v, wx, wy, label):
    """Bouncing arrow over a world position, or an edge-of-screen arrow when it is off-screen."""
    cam = g.cam
    sx, sy = wx - cam[0], wy - cam[1]
    bob = math.sin(g.t * 6) * 3
    if 18 <= sx <= VIEW_W - 18 and 40 <= sy <= VIEW_H - 18:
        tri = [(sx - 8, sy - 20 + bob), (sx + 8, sy - 20 + bob), (sx, sy - 6 + bob)]
        pygame.draw.polygon(v, (40, 24, 20), [(sx - 10, sy - 22 + bob), (sx + 10, sy - 22 + bob), (sx, sy - 3 + bob)])
        pygame.draw.polygon(v, GOLD, tri)
        g.text_shadow(v, g.font_s, label, (sx, sy - 36 + bob), CREAM, SHADOW, True)
    else:
        a = math.atan2(sy - VIEW_H / 2, sx - VIEW_W / 2)
        dx, dy = math.cos(a), math.sin(a)
        k = min((VIEW_W / 2 - 26) / max(abs(dx), 1e-6), (VIEW_H / 2 - 26) / max(abs(dy), 1e-6))
        px, py = VIEW_W / 2 + dx * k, VIEW_H / 2 + dy * k
        tip = (px + dx * 13, py + dy * 13)
        b1 = (px - dx * 7 - dy * 9, py - dy * 7 + dx * 9)
        b2 = (px - dx * 7 + dy * 9, py - dy * 7 - dx * 9)
        pygame.draw.polygon(v, (40, 24, 20), [(tip[0] + dx * 2, tip[1] + dy * 2), (b1[0] - dy * 2, b1[1] + dx * 2),
                                              (b2[0] + dy * 2, b2[1] - dx * 2)])
        pygame.draw.polygon(v, GOLD, [tip, b1, b2])


class Tutorial:
    STEPS = [
        dict(id="welcome", title="Welcome to Hearthmoor!", info=True,
             text="Let's learn the basics. It only takes a minute."),
        dict(id="move", title="Moving", bar=True, goal="Walk around a little...",
             text="Use W A S D or the ARROW KEYS to walk in any direction."),
        dict(id="run", title="Running", bar=True, goal="Run for a moment...",
             text="Hold SHIFT while you move to run."),
        dict(id="jump", title="Jumping", goal="Press SPACE to jump.",
             text="Press SPACE to jump over the cobbles and show off."),
        dict(id="talk", title="Talking and interacting", goal="Talk to Elder Maren (follow the arrow).",
             text="Walk up to a villager, animal, sign or door. When the E bubble appears above it, "
                  "press E or ENTER. Keep pressing E to read on."),
        dict(id="map", title="The world map", goal="Press M to open the map, then M again to close it.",
             text="Press M to see the village, the Whisperwood and the Hollow Gate marked on the map."),
        dict(id="misc", title="Handy keys", info=True,
             text="N skips an hour of time.  B turns the music on or off.  H shows the help bar.  "
                  "F11 is fullscreen.  ESC opens the pause menu."),
        dict(id="dungeon", title="The Hollow Below", info=True, point="gate",
             text="Far to the south, past the farm road, a stone stairwell leads down into the dungeon. "
                  "Stand on the landing in front of it and press E to descend."),
        dict(id="combat", title="Fighting", info=True,
             text="In the dungeon: hold LEFT MOUSE to attack toward your cursor, RIGHT MOUSE or the "
                  "WHEEL to swap sword and fireball, and SPACE to dodge roll. Rolling makes you invincible."),
        dict(id="mana", title="Mana, Items & the Goddess", info=True,
             text="Fireballs cost 5 MP; kills restore a little. Press I for your inventory, 1 / 2 to drink "
                  "potions. The goddess statue in the north sanctuary (behind the Whispering Shrine) restores HP and MP."),
        dict(id="done", title="You're ready!", info=True,
             text="Good luck, traveler. You can replay this tutorial from the pause menu any time."),
    ]

    def __init__(self):
        self.active = False
        self.i = 0
        self.prog = 0.0
        self.done_t = 0.0
        self.flags = {}

    @property
    def cur(self):
        return self.STEPS[self.i]

    def start(self):
        self.active = True
        self.i = 0
        self.prog = 0.0
        self.done_t = 0.0
        self.flags = {}

    def on_info(self):
        return self.active and self.cur.get("info", False)

    def skip(self, g):
        self.active = False
        g.toast("Tutorial skipped. Press H any time for the help bar.", 3.0)

    def next(self, g):
        """Advance to the next step (or finish)."""
        self.i += 1
        self.prog = 0.0
        self.done_t = 0.0
        self.flags = {}
        if self.i >= len(self.STEPS):
            self.active = False
            g.toast("Tutorial complete - enjoy Hearthmoor!", 4.0)

    def _complete(self, g):
        if self.done_t <= 0:
            self.prog = 1.0
            self.done_t = 0.9
            g.play("blip")

    def notify(self, g, event):
        if not self.active or self.done_t > 0:
            return
        sid = self.cur["id"]
        if sid == "jump" and event == "jump":
            self._complete(g)
        elif sid == "talk" and event == "interact":
            self._complete(g)
        elif sid == "map":
            if event == "map_open":
                self.flags["open"] = True
            elif event == "map_close" and self.flags.get("open"):
                self._complete(g)

    def update(self, dt, g):
        if not self.active:
            return
        if self.done_t > 0:
            self.done_t -= dt
            if self.done_t <= 0:
                self.next(g)
            return
        sid = self.cur["id"]
        p = g.player
        if sid == "move" and p.moving:
            self.prog += dt / 1.3
        elif sid == "run" and p.moving and p.running:
            self.prog += dt / 1.0
        if self.cur.get("bar") and self.prog >= 1.0:
            self._complete(g)

    def draw(self, g, v):
        if not self.active or g.scene != "village" or g.dialogue.active or g.show_map:
            return
        s = self.cur
        target = None
        if s["id"] == "talk" and self.done_t <= 0:
            for n in g.npcs:
                if n.id == "elder":
                    target = (n.x, n.y - 44, "Elder Maren")
        elif s.get("point") == "gate":
            target = (49 * 32, 85 * 32, "The Hollow Below")
        if target:
            _pointer(g, v, *target)
        w = 318
        body = wrap(g.font, s["text"], w - 22)
        h = 10 + 18 + 6 + len(body) * 15 + 8 + 18 + 6
        rect = pygame.Rect(8, VIEW_H - h - 8, w, h)
        g.panel(v, rect, 225)
        if not s.get("info") and self.done_t <= 0:       # pulsing border while waiting for the player
            a = int(90 + 80 * (0.5 + 0.5 * math.sin(g.t * 5)))
            b = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(b, (255, 226, 150, a), b.get_rect(), 2, border_radius=8)
            v.blit(b, rect.topleft)
        g.text_shadow(v, g.font, s["title"], (rect.x + 11, rect.y + 9), GOLD, SHADOW)
        num = f"{self.i + 1}/{len(self.STEPS)}"
        g.text_shadow(v, g.font_s, num, (rect.right - 11 - g.font_s.size(num)[0], rect.y + 11), DIM, SHADOW)
        y = rect.y + 10 + 18 + 6
        for ln in body:
            g.text_shadow(v, g.font, ln, (rect.x + 11, y), CREAM, SHADOW)
            y += 15
        fy = rect.bottom - 24
        if self.done_t > 0:
            g.text_shadow(v, g.font, "Nice!", (rect.x + 11, fy), (170, 236, 150), SHADOW)
        elif s.get("info"):
            g.text_shadow(v, g.font_s, "ENTER: continue        TAB: skip tutorial", (rect.x + 11, fy + 3), (200, 230, 190), SHADOW)
        else:
            goal = s.get("goal", "")
            g.text_shadow(v, g.font_s, goal, (rect.x + 11, fy - 1), (200, 230, 190), SHADOW)
            if s.get("bar"):
                pygame.draw.rect(v, (30, 20, 18), (rect.x + 11, fy + 12, w - 22, 5), border_radius=3)
                pygame.draw.rect(v, GOLD, (rect.x + 11, fy + 12, int((w - 22) * min(1.0, self.prog)), 5), border_radius=3)
            else:
                g.text_shadow(v, g.font_s, "TAB: skip tutorial", (rect.x + 11, fy + 12), (160, 150, 136), SHADOW)
