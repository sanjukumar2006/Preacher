"""Inventory: item catalogue, the pack itself, procedural item icons, and the inventory screen (key I).

Add a new item: put an entry in ITEMS here, its name and prices in economy.py (ITEM_NAMES, PRICES), and pick an
icon style (see draw_icon). Usable items just need hp= / mp=. Monster loot is tuned in economy.py (LOOT)."""
import pygame

import economy as ECO

ITEMS = {
    "health_potion": dict(color=(214, 52, 70), key="1", hp=40, icon="potion",
                          desc="A ruby tonic that knits wounds shut. Restores 40 HP."),
    "mana_potion": dict(color=(64, 120, 238), key="2", mp=40, icon="potion",
                        desc="Bottled starlight. Restores 40 MP, enough for eight fireballs."),
    "greater_health": dict(color=(236, 96, 150), hp=90, icon="potion",
                           desc="A deep rose elixir from Wren's own stills. Restores 90 HP."),
    "greater_mana": dict(color=(120, 90, 240), mp=90, icon="potion",
                         desc="Concentrated starlight. Restores 90 MP."),
    "bread": dict(color=(214, 164, 90), hp=15, icon="bread", desc="A warm loaf from Pip's bakery. Restores 15 HP."),
    "honey_bun": dict(color=(232, 178, 84), hp=30, icon="bun", desc="A sticky honey bun. Restores 30 HP."),
    "hot_stew": dict(color=(190, 110, 70), hp=50, icon="bowl", desc="Rosalind's famous stew. Restores 50 HP."),
    "bone_shard": dict(color=(232, 228, 214), icon="shard", loot=True,
                       desc="Iron-rich bone from the catacombs. Bram prizes it."),
    "ectoplasm": dict(color=(150, 230, 210), icon="wisp", loot=True,
                      desc="Cold, glowing residue. A herbalist's delight."),
    "slime_gel": dict(color=(96, 210, 140), icon="gel", loot=True, desc="Wobbly green gel. Sticky and surprisingly useful."),
    "stone_chip": dict(color=(150, 160, 176), icon="chip", loot=True, desc="A sliver of flint-grade stone."),
    "arcane_dust": dict(color=(200, 140, 255), icon="dust", loot=True, desc="Shimmering dust left behind by spellcasters."),
    "beast_hide": dict(color=(176, 120, 76), icon="hide", loot=True, desc="Thick hide from one of the Hollow's great beasts."),
}
for _k, _d in ITEMS.items():                           # names and prices come from economy.py
    _d["name"] = ECO.ITEM_NAMES[_k]
    _d["buy"], _d["sell"] = ECO.PRICES.get(_k, (None, None))
QUICK_ITEMS = ("health_potion", "mana_potion")       # hotkeys 1 and 2


class Inventory:
    COLS, ROWS = 4, 4
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
    """Item icon centred on (cx, cy). s = scale."""
    d = ITEMS[key]
    col = d["color"]
    kind = d.get("icon", "potion")
    light = tuple(min(255, c + 90) for c in col)
    dark = tuple(int(c * 0.55) for c in col)
    outline = (36, 30, 52)

    def r(x, y, w, h, c):
        pygame.draw.rect(v, c, (int(cx + x * s), int(cy + y * s), max(1, int(w * s)), max(1, int(h * s))))

    def disc(x, y, rad, c):
        pygame.draw.circle(v, c, (int(cx + x * s), int(cy + y * s)), max(1, int(rad * s)))

    def poly(pts, c):
        pygame.draw.polygon(v, c, [(int(cx + x * s), int(cy + y * s)) for x, y in pts])

    def ell(x, y, w, h, c):
        pygame.draw.ellipse(v, c, (int(cx + x * s), int(cy + y * s), max(2, int(w * s)), max(2, int(h * s))))

    def line(x0, y0, x1, y1, c, w=1):
        pygame.draw.line(v, c, (cx + x0 * s, cy + y0 * s), (cx + x1 * s, cy + y1 * s), w)

    if kind == "potion":
        r(-3, -13, 6, 4, (150, 108, 66))                    # cork
        r(-4, -9, 8, 5, (200, 215, 230))                    # glass neck
        disc(0, 3, 11, outline)
        disc(0, 3, 10, (205, 220, 235))
        disc(0, 4, 8, dark)
        disc(0, 4, 7, col)
        r(-6, 3, 12, 3, col)
        disc(-3, 1, 2, light)
        if "mp" in d:                                       # little star on the mana potion
            line(2, 3, 2, 8, (235, 245, 255))
            line(-1, 6, 5, 6, (235, 245, 255))
        else:                                               # cross on the health potion
            line(2, 3, 2, 8, (255, 235, 235))
            line(-1, 6, 5, 6, (255, 235, 235))
        if key.startswith("greater"):                       # a golden ring around the neck marks the stronger brew
            r(-5, -5, 10, 2, (240, 200, 90))
    elif kind == "bread":
        ell(-12, -6, 24, 15, outline)
        ell(-11, -5, 22, 13, dark)
        ell(-10, -5, 20, 11, col)
        for x in (-5, 0, 5):
            line(x - 2, -2, x + 1, 3, dark, 2)
        ell(-8, -4, 8, 3, light)
    elif kind == "bun":
        disc(0, 2, 11, outline)
        disc(0, 2, 10, dark)
        disc(0, 1, 9, col)
        disc(-3, -3, 3, light)
        line(-6, 2, 6, 2, (255, 246, 214), 2)
        line(-4, 6, 4, 6, (255, 246, 214), 1)
    elif kind == "bowl":
        poly([(-11, -2), (11, -2), (8, 9), (-8, 9)], outline)
        poly([(-10, -1), (10, -1), (7, 8), (-7, 8)], (214, 196, 168))
        r(-9, -3, 18, 3, col)
        disc(-3, -4, 2, (250, 220, 150))
        disc(3, -5, 2, (240, 160, 90))
        for x in (-4, 1, 6):
            line(x, -8, x + 2, -12, (235, 235, 245))
    elif kind == "shard":
        line(-9, 7, 7, -8, outline, 7)
        line(-9, 7, 7, -8, col, 4)
        disc(-9, 7, 4, col)
        disc(7, -8, 4, col)
        line(-4, 3, 3, -4, light, 1)
    elif kind == "wisp":
        poly([(0, -12), (9, 2), (4, 11), (-4, 11), (-9, 2)], outline)
        poly([(0, -10), (7, 2), (3, 9), (-3, 9), (-7, 2)], col)
        poly([(0, -6), (4, 2), (0, 7), (-4, 2)], light)
        disc(-2, 0, 1, outline)
        disc(2, 0, 1, outline)
    elif kind == "gel":
        ell(-11, -4, 22, 15, outline)
        ell(-10, -5, 20, 14, dark)
        ell(-9, -6, 18, 12, col)
        disc(-4, -3, 2, light)
        disc(-1, 2, 1, outline)
        disc(4, 2, 1, outline)
    elif kind == "chip":
        poly([(-10, 3), (-5, -9), (5, -10), (11, 0), (6, 9), (-5, 9)], outline)
        poly([(-8, 2), (-4, -7), (4, -8), (9, 0), (5, 7), (-4, 7)], col)
        poly([(-4, -7), (4, -8), (0, -1)], light)
    elif kind == "dust":
        pygame.draw.rect(v, outline, (int(cx - 9 * s), int(cy + 2 * s), max(1, int(18 * s)), max(1, int(8 * s))), border_radius=3)
        pygame.draw.rect(v, dark, (int(cx - 8 * s), int(cy + 3 * s), max(1, int(16 * s)), max(1, int(6 * s))), border_radius=3)
        for x, y, rad in ((-6, 0, 2), (0, -4, 3), (6, -1, 2), (-2, 1, 1), (3, -7, 1)):
            disc(x, y, rad, col)
            disc(x, y, max(0.5, rad - 1), (255, 250, 255))
    elif kind == "hide":
        pygame.draw.rect(v, outline, (int(cx - 11 * s), int(cy - 8 * s), max(1, int(22 * s)), max(1, int(17 * s))), border_radius=4)
        pygame.draw.rect(v, col, (int(cx - 10 * s), int(cy - 7 * s), max(1, int(20 * s)), max(1, int(15 * s))), border_radius=4)
        for x in (-6, -2, 2, 6):
            line(x, -5, x, 6, dark, 1)
        disc(-6, -4, 1, light)
    else:                                                    # unknown style: a plain gem
        poly([(0, -10), (9, 0), (0, 10), (-9, 0)], outline)
        poly([(0, -8), (7, 0), (0, 8), (-7, 0)], col)


def draw_coin(v, cx, cy, s=1.0):
    """The Crown: a little gold coin."""
    rad = max(3, int(6 * s))
    pygame.draw.circle(v, (96, 62, 18), (int(cx), int(cy)), rad + 1)
    pygame.draw.circle(v, (240, 190, 60), (int(cx), int(cy)), rad)
    pygame.draw.circle(v, (255, 226, 120), (int(cx), int(cy)), max(1, rad - 2))
    pygame.draw.circle(v, (214, 156, 40), (int(cx), int(cy)), max(1, rad - 3), 1)
    pygame.draw.line(v, (170, 120, 30), (int(cx), int(cy - rad + 3)), (int(cx), int(cy + rad - 3)), 1)


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
    # ---- purse (under the grid)
    py = GRID_Y + Inventory.ROWS * (SLOT + GAP) + 2
    pbox = pygame.Rect(GRID_X, py, Inventory.COLS * (SLOT + GAP) - GAP, 20)
    pygame.draw.rect(v, (30, 22, 20), pbox, border_radius=6)
    pygame.draw.rect(v, (96, 76, 64), pbox, 1, border_radius=6)
    draw_coin(v, pbox.x + 14, pbox.centery, 1.0)
    v.blit(g.font.render(f"{g.eco.gold} {ECO.CURRENCY}", True, (255, 226, 150)), (pbox.x + 28, pbox.y + 4))
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
        extra = f"   Hotkey: {d['key']}" if d.get("key") else ""
        g.text_shadow(v, g.font_s, f"Owned: {s[1]}{extra}", (box.x + 58, box.y + 32), (255, 220, 140))
        if d.get("sell"):
            g.text_shadow(v, g.font_s, f"Sells for {d['sell']} {ECO.CURRENCY_SHORT}" + ("   (loot)" if d.get("loot") else ""),
                          (box.x + 58, box.y + 44), (214, 190, 120))
        for j, ln in enumerate(_wrap(g.font_s, d["desc"], box.w - 20)[:3]):
            v.blit(g.font_s.render(ln, True, (214, 206, 194)), (box.x + 10, box.y + 60 + j * 12))
        can = (("hp" in d and c.hp < c.max_hp) or ("mp" in d and c.mp < c.max_mp))
        hov = USE_BTN.collidepoint(mouse)
        pygame.draw.rect(v, (70, 120, 80) if can else (60, 56, 56), USE_BTN, border_radius=6)
        pygame.draw.rect(v, (190, 235, 190) if (can and hov) else (150, 140, 130), USE_BTN, 1, border_radius=6)
        usable = "hp" in d or "mp" in d
        t = g.font_s.render("USE  [E]" if usable else "TRADE LOOT", True, (255, 255, 255) if can else (150, 146, 146))
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
    arm = int(round(c.armor * 100))
    v.blit(g.font_s.render(f"Sword: {SWORD['damage'] + c.sword_bonus} dmg" + (f"   Armor: -{arm}% dmg" if arm else ""),
                           True, (225, 225, 235)), (dx, hy + 62))
    v.blit(g.font_s.render(f"Fireball: {MAGIC['damage'] + c.magic_bonus} dmg, costs {FIREBALL_COST} MP", True, (255, 175, 110)),
           (dx, hy + 76))
    v.blit(g.font_s.render(f"Renown {g.quests.renown}" + (f"  -  {int(ECO.renown_discount(g.quests.renown) * 100)}% off in shops"
                                                            if g.quests.renown >= 2 else ""), True, (214, 190, 120)),
           (dx, hy + 90))
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
