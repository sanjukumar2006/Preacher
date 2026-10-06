"""Inventory: item catalogue, the pack itself, procedural item icons, and the inventory screen (key I).

Add a new item: put an entry in ITEMS (and, if it is usable, give it hp= / mp= and it just works),
then draw an icon for it in draw_icon(). Enemy drops are tuned in combat.py (DROPS)."""
import pygame

ITEMS = {
    "health_potion": dict(name="Health Potion", hp=40, color=(214, 52, 70), key="1",
                          desc="A ruby tonic that knits wounds shut. Restores 40 HP."),
    "mana_potion":   dict(name="Mana Potion", mp=40, color=(64, 120, 238), key="2",
                          desc="Bottled starlight. Restores 40 MP, enough for eight fireballs."),
}
QUICK_ITEMS = ("health_potion", "mana_potion")       # hotkeys 1 and 2


class Inventory:
    COLS, ROWS = 4, 3
    STACK = 20

    def __init__(self):
        self.slots = [None] * (self.COLS * self.ROWS)      # each slot: [item_key, count] or None
        self.sel = 0
        self.add("health_potion", 2)                        # a little starter kit
        self.add("mana_potion", 2)

    def count(self, key):
        return sum(s[1] for s in self.slots if s and s[0] == key)

    def add(self, key, n=1):
        """Returns how many items did NOT fit."""
        for s in self.slots:                                # top up existing stacks first
            if n and s and s[0] == key and s[1] < self.STACK:
                put = min(n, self.STACK - s[1])
                s[1] += put
                n -= put
        for i, s in enumerate(self.slots):
            if n and s is None:
                put = min(n, self.STACK)
                self.slots[i] = [key, put]
                n -= put
        return n

    def remove(self, key, n=1):
        if self.count(key) < n:
            return False
        for i in range(len(self.slots) - 1, -1, -1):        # take from the smallest/last stacks first
            s = self.slots[i]
            if n and s and s[0] == key:
                take = min(n, s[1])
                s[1] -= take
                n -= take
                if s[1] <= 0:
                    self.slots[i] = None
        return True

    def selected(self):
        return self.slots[self.sel]


# --------------------------------------------------------------------------- icons
def draw_icon(v, key, cx, cy, s=1.0):
    """Potion bottle centred on (cx, cy). s = scale."""
    col = ITEMS[key]["color"]
    light = tuple(min(255, c + 90) for c in col)
    dark = tuple(int(c * 0.55) for c in col)

    def r(x, y, w, h, c):
        pygame.draw.rect(v, c, (int(cx + x * s), int(cy + y * s), max(1, int(w * s)), max(1, int(h * s))))
    r(-3, -13, 6, 4, (150, 108, 66))                        # cork
    r(-4, -9, 8, 5, (200, 215, 230))                        # glass neck
    pygame.draw.circle(v, (36, 30, 52), (int(cx), int(cy + 3 * s)), int(11 * s))
    pygame.draw.circle(v, (205, 220, 235), (int(cx), int(cy + 3 * s)), int(10 * s))
    pygame.draw.circle(v, dark, (int(cx), int(cy + 4 * s)), int(8 * s))
    pygame.draw.circle(v, col, (int(cx), int(cy + 4 * s)), int(7 * s))
    r(-6, 3, 12, 3, col)
    pygame.draw.circle(v, light, (int(cx - 3 * s), int(cy + 1 * s)), max(1, int(2 * s)))
    if "mp" in ITEMS[key]:                                  # little star on the mana potion
        pygame.draw.line(v, (235, 245, 255), (cx + 2 * s, cy + 3 * s), (cx + 2 * s, cy + 8 * s), 1)
        pygame.draw.line(v, (235, 245, 255), (cx - 1 * s, cy + 6 * s), (cx + 5 * s, cy + 6 * s), 1)
    else:                                                   # cross on the health potion
        pygame.draw.line(v, (255, 235, 235), (cx + 2 * s, cy + 3 * s), (cx + 2 * s, cy + 8 * s), 1)
        pygame.draw.line(v, (255, 235, 235), (cx - 1 * s, cy + 6 * s), (cx + 5 * s, cy + 6 * s), 1)


# --------------------------------------------------------------------------- screen
PANEL = pygame.Rect(64, 18, 512, 324)
GRID_X, GRID_Y, SLOT, GAP = PANEL.x + 18, PANEL.y + 50, 46, 6
USE_BTN = pygame.Rect(PANEL.x + 262, PANEL.y + 150, 92, 22)


def slot_rect(i):
    c, r = i % Inventory.COLS, i // Inventory.COLS
    return pygame.Rect(GRID_X + c * (SLOT + GAP), GRID_Y + r * (SLOT + GAP), SLOT, SLOT)


def _wrap(font, text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.size(t)[0] <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _bar(v, font_s, rect, frac, fill, back, label):
    pygame.draw.rect(v, back, rect, border_radius=4)
    pygame.draw.rect(v, fill, (rect.x, rect.y, int(rect.w * max(0.0, min(1.0, frac))), rect.h), border_radius=4)
    pygame.draw.rect(v, (235, 225, 215), rect, 1, border_radius=4)
    t = font_s.render(label, True, (255, 255, 255))
    v.blit(t, (rect.centerx - t.get_width() // 2, rect.y))


def draw_inventory(g, v):
    inv, c = g.combat.inv, g.combat
    dim = pygame.Surface(v.get_size(), pygame.SRCALPHA)
    dim.fill((8, 6, 10, 195))
    v.blit(dim, (0, 0))
    g.panel(v, PANEL, 245)
    g.text_shadow(v, g.font_m, "INVENTORY", (PANEL.x + 18, PANEL.y + 14), (255, 232, 170))
    used = sum(1 for s in inv.slots if s)
    g.text_shadow(v, g.font_s, f"{used}/{len(inv.slots)} slots", (PANEL.x + 130, PANEL.y + 19), (200, 190, 170))
    mouse = g.mouse_view()
    # ---- grid
    for i in range(len(inv.slots)):
        r = slot_rect(i)
        hover = r.collidepoint(mouse)
        pygame.draw.rect(v, (58, 42, 36) if i == inv.sel else (34, 24, 22), r, border_radius=6)
        pygame.draw.rect(v, (255, 214, 120) if i == inv.sel else ((200, 170, 120) if hover else (96, 76, 64)),
                         r, 2 if i == inv.sel else 1, border_radius=6)
        s = inv.slots[i]
        if s:
            draw_icon(v, s[0], r.centerx, r.centery - 2, 1.0)
            t = g.font_s.render(str(s[1]), True, (255, 255, 255))
            sh = g.font_s.render(str(s[1]), True, (30, 20, 20))
            v.blit(sh, (r.right - t.get_width() - 3, r.bottom - 14))
            v.blit(t, (r.right - t.get_width() - 4, r.bottom - 15))
        hk = None
        if s:
            hk = ITEMS[s[0]].get("key")
        if hk:
            v.blit(g.font_s.render(hk, True, (255, 220, 140)), (r.x + 4, r.y + 3))
    # ---- details
    dx = PANEL.x + 244
    g.text_shadow(v, g.font, "Selected", (dx, PANEL.y + 16), (214, 190, 150))
    box = pygame.Rect(dx, PANEL.y + 38, 250, 104)
    pygame.draw.rect(v, (30, 22, 20), box, border_radius=6)
    pygame.draw.rect(v, (96, 76, 64), box, 1, border_radius=6)
    s = inv.selected()
    if s:
        d = ITEMS[s[0]]
        draw_icon(v, s[0], box.x + 28, box.y + 32, 1.6)
        g.text_shadow(v, g.font_m, d["name"], (box.x + 58, box.y + 10), (255, 246, 226))
        g.text_shadow(v, g.font_s, f"Owned: {s[1]}   Hotkey: {d['key']}", (box.x + 58, box.y + 32), (255, 220, 140))
        for j, ln in enumerate(_wrap(g.font_s, d["desc"], box.w - 20)[:4]):
            v.blit(g.font_s.render(ln, True, (214, 206, 194)), (box.x + 10, box.y + 56 + j * 13))
        can = (("hp" in d and c.hp < c.max_hp) or ("mp" in d and c.mp < c.max_mp))
        hov = USE_BTN.collidepoint(mouse)
        pygame.draw.rect(v, (70, 120, 80) if can else (60, 56, 56), USE_BTN, border_radius=6)
        pygame.draw.rect(v, (190, 235, 190) if (can and hov) else (150, 140, 130), USE_BTN, 1, border_radius=6)
        t = g.font_s.render("USE  [E]", True, (255, 255, 255) if can else (150, 146, 146))
        v.blit(t, (USE_BTN.centerx - t.get_width() // 2, USE_BTN.y + 5))
    else:
        v.blit(g.font_s.render("Empty slot", True, (150, 140, 130)), (box.x + 10, box.y + 10))
    # ---- hero panel
    hy = PANEL.y + 182
    g.text_shadow(v, g.font, "Hero", (dx, hy), (214, 190, 150))
    _bar(v, g.font_s, pygame.Rect(dx + 28, hy + 22, 190, 13), c.hp / c.max_hp, (190, 44, 60), (40, 14, 20),
         f"{c.hp}/{c.max_hp}")
    _bar(v, g.font_s, pygame.Rect(dx + 28, hy + 40, 190, 13), c.mp / c.max_mp, (60, 110, 230), (14, 20, 48),
         f"{c.mp}/{c.max_mp}")
    v.blit(g.font_s.render("HP", True, (255, 200, 205)), (dx, hy + 23))
    v.blit(g.font_s.render("MP", True, (170, 205, 255)), (dx, hy + 41))
    from combat import SWORD, MAGIC, FIREBALL_COST
    v.blit(g.font_s.render(f"Sword: {SWORD['damage']} dmg", True, (225, 225, 235)), (dx, hy + 62))
    v.blit(g.font_s.render(f"Fireball: {MAGIC['damage']} dmg, costs {FIREBALL_COST} MP", True, (255, 175, 110)),
           (dx, hy + 76))
    # ---- footer
    g.text_shadow(v, g.font_s, "Arrows / WASD / mouse: select    E / Enter / click USE: drink",
                  (PANEL.x + 18, PANEL.bottom - 38), (200, 190, 170))
    g.text_shadow(v, g.font_s, "1: Health Potion    2: Mana Potion    I / ESC: close    Goddess statue refills HP & MP",
                  (PANEL.x + 18, PANEL.bottom - 22), (200, 190, 170))


def inv_key(g, k):
    """Keys while the inventory is open. Returns True if the key was used."""
    inv = g.combat.inv
    n, cols = len(inv.slots), Inventory.COLS
    if k in (pygame.K_LEFT, pygame.K_a):
        inv.sel = (inv.sel - 1) % n
    elif k in (pygame.K_RIGHT, pygame.K_d):
        inv.sel = (inv.sel + 1) % n
    elif k in (pygame.K_UP, pygame.K_w):
        inv.sel = (inv.sel - cols) % n
    elif k in (pygame.K_DOWN, pygame.K_s):
        inv.sel = (inv.sel + cols) % n
    elif k in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
        sl = inv.selected()
        if sl:
            g.combat.use_item(sl[0])
    else:
        return False
    g.play("blip")
    return True


def inv_click(g, pos):
    inv = g.combat.inv
    for i in range(len(inv.slots)):
        if slot_rect(i).collidepoint(pos):
            inv.sel = i
            g.play("blip")
            return
    if USE_BTN.collidepoint(pos):
        sl = inv.selected()
        if sl:
            g.combat.use_item(sl[0])
