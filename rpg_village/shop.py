"""The trade screen. Stand beside a shopkeeper and press T.

BUY tab   potions, food, permanent upgrades and services (a bed at the inn).  Prices include your renown discount.
SELL tab  everything in your pack that has a sell price (monster loot, spare potions).  SHIFT + E sells the whole stack.

What each shop sells, and what unlocks it, is in economy.py (SHOPS, UPGRADES).  This file is only the screen."""
import pygame

import economy as ECO
import story
from inventory import ITEMS, _wrap, draw_coin, draw_icon

PANEL = pygame.Rect(40, 12, 560, 336)
LIST_X, LIST_Y, ROW_H, ROWS_VISIBLE, LIST_W = PANEL.x + 14, PANEL.y + 76, 24, 9, 288
DET_X = PANEL.x + 318
TAB_BUY = pygame.Rect(PANEL.x + 14, PANEL.y + 50, 84, 20)
TAB_SELL = pygame.Rect(PANEL.x + 102, PANEL.y + 50, 84, 20)
ACT_BTN = pygame.Rect(DET_X + 4, PANEL.y + 246, 120, 24)
ROMAN = ["I", "II", "III", "IV", "V"]


def flag_source(flag):
    """Title of the quest that unlocks a story flag (for 'Locked: finish X' hints)."""
    for q in story.QUESTS:
        if flag in q.get("reward", {}).get("flags", []):
            return q["title"]
    return "a quest"


class ShopUI:
    def __init__(self):
        self.active = False
        self.shop_id = None
        self.tab = "buy"
        self.sel = 0
        self.scroll = 0
        self.msg, self.msg_t = "", 0.0

    # ------------------------------------------------------------------ opening
    def open(self, g, npc_id):
        """Returns True when the shop opened (False when it is closed for now)."""
        shop = ECO.SHOPS.get(npc_id)
        if not shop:
            return False
        flag = shop["open_flag"]
        if flag and not g.quests.has(flag):
            g.toast(shop["closed"], 4.0)
            return False
        self.active, self.shop_id, self.tab, self.sel, self.scroll = True, npc_id, "buy", 0, 0
        self.msg, self.msg_t = shop["greet"], 4.0
        g.play("blip")
        return True

    def close(self, g):
        self.active = False
        g.play("bye")

    @property
    def shop(self):
        return ECO.SHOPS[self.shop_id]

    # ------------------------------------------------------------------ entries
    def discount(self, g):
        return ECO.renown_discount(g.quests.renown)

    def buy_entries(self, g):
        disc, out = self.discount(g), []
        inv = g.combat.inv
        for ent in self.shop["stock"]:
            kind, key = ent[0], ent[1]
            need = ent[2] if len(ent) > 2 else None
            e = dict(kind=kind, id=key, locked=None, maxed=False, price=0, owned=None, icon=None)
            if kind == "item":
                d = ITEMS[key]
                e.update(name=d["name"], desc=d["desc"], price=ECO.discounted(ECO.buy_price(key), disc),
                         owned=inv.count(key), icon=key)
            elif kind == "upgrade":
                u = ECO.UPGRADES[key]
                nxt = g.eco.next_tier(key)
                if nxt is None:
                    e.update(name=u["name"] + " (max)", desc=u["desc"], maxed=True)
                else:
                    t, td = nxt
                    need = td["need"]
                    e.update(name=f"{u['name']} {ROMAN[t]}", desc=u["desc"], price=ECO.discounted(td["price"], disc),
                             owned=None)
            else:
                svc = ECO.SERVICES[key]
                price = svc["price"] * (ECO.INN_FRIEND_DISCOUNT if g.quests.has("inn_friend") else 1.0)
                e.update(name=svc["name"], desc=svc["desc"], price=ECO.discounted(price, disc))
            if need and not g.quests.has(need):
                e["locked"] = f"Locked: finish '{flag_source(need)}'"
            out.append(e)
        return out

    def sell_entries(self, g):
        counts = {}
        for s in g.combat.inv.slots:
            if s:
                counts[s[0]] = counts.get(s[0], 0) + s[1]
        wanted = set()
        for q in g.quests.active_quests():
            for o in q["objectives"]:
                if o["t"] == "deliver":
                    wanted.add(o["item"])
        out = []
        for key, n in counts.items():
            price = ECO.sell_price(key)
            if price:
                d = ITEMS[key]
                out.append(dict(kind="sell", id=key, name=d["name"], desc=d["desc"], price=price, owned=n, icon=key,
                                locked=None, maxed=False, wanted=key in wanted))
        out.sort(key=lambda e: (not ITEMS[e["id"]].get("loot", False), e["name"]))     # loot first
        return out

    def entries(self, g):
        return self.buy_entries(g) if self.tab == "buy" else self.sell_entries(g)

    # ------------------------------------------------------------------ actions
    def act(self, g, whole_stack=False):
        ents = self.entries(g)
        if not ents:
            return
        self.sel = max(0, min(self.sel, len(ents) - 1))
        e = ents[self.sel]
        if self.tab == "buy":
            self.buy(g, e)
        else:
            self.sell(g, e, whole_stack)

    def say(self, text, secs=2.5):
        self.msg, self.msg_t = text, secs

    def buy(self, g, e):
        if e["maxed"]:
            return self.say("Fully upgraded already.")
        if e["locked"]:
            return self.say(e["locked"])
        if not g.eco.can_afford(e["price"]):
            g.play("land")
            return self.say(f"You need {e['price']} {ECO.CURRENCY}.")
        inv = g.combat.inv
        if e["kind"] == "item":
            if inv.add(e["id"], 1):
                return self.say("Your pack is full!")
            g.eco.spend(e["price"])
            self.say(f"Bought {e['name']}.")
        elif e["kind"] == "upgrade":
            g.eco.spend(e["price"])
            g.eco.upgrades[e["id"]] = g.eco.tier(e["id"]) + 1
            g.apply_upgrade(e["id"])
            self.say(f"{e['name']} complete!")
        else:
            g.eco.spend(e["price"])
            g.use_service(e["id"])
            self.say("You wake feeling brand new." if e["id"] == "rest" else "Done.")
            self.active = False                       # sleeping leaves the shop
        g.quests.notify(g, "spend", amount=e["price"])
        g.play("talk")

    def sell(self, g, e, whole_stack):
        n = e["owned"] if whole_stack else 1
        if n <= 0:
            return
        if not g.combat.inv.remove(e["id"], n):
            return
        g.eco.earn(e["price"] * n)
        g.play("blip")
        self.say(f"Sold {n} {ECO.item_name(e['id'], n)} for {e['price'] * n} {ECO.CURRENCY}.")
        self.sel = max(0, min(self.sel, len(self.sell_entries(g)) - 1))

    # ------------------------------------------------------------------ input
    def set_tab(self, g, tab):
        if tab == "sell" and not self.shop["buys"]:
            return self.say(f"{self.shop['name']} doesn't buy goods.")
        if tab != self.tab:
            self.tab, self.sel, self.scroll = tab, 0, 0
            g.play("blip")

    def key(self, g, k):
        ents = self.entries(g)
        n = len(ents)
        if k in (pygame.K_ESCAPE, pygame.K_t, pygame.K_q):
            self.close(g)
        elif k in (pygame.K_UP, pygame.K_w) and n:
            self.sel = (self.sel - 1) % n
            g.play("blip")
        elif k in (pygame.K_DOWN, pygame.K_s) and n:
            self.sel = (self.sel + 1) % n
            g.play("blip")
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.set_tab(g, "buy")
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.set_tab(g, "sell")
        elif k == pygame.K_TAB:
            self.set_tab(g, "sell" if self.tab == "buy" else "buy")
        elif k in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.act(g, whole_stack=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
        self._scroll_to_sel(len(self.entries(g)))

    def _scroll_to_sel(self, n):
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + ROWS_VISIBLE:
            self.scroll = self.sel - ROWS_VISIBLE + 1
        self.scroll = max(0, min(self.scroll, max(0, n - ROWS_VISIBLE)))

    def click(self, g, pos):
        if TAB_BUY.collidepoint(pos):
            return self.set_tab(g, "buy")
        if TAB_SELL.collidepoint(pos):
            return self.set_tab(g, "sell")
        ents = self.entries(g)
        for i in range(min(ROWS_VISIBLE, len(ents) - self.scroll)):
            if pygame.Rect(LIST_X, LIST_Y + i * ROW_H, LIST_W, ROW_H - 2).collidepoint(pos):
                self.sel = self.scroll + i
                g.play("blip")
                return
        if ACT_BTN.collidepoint(pos):
            self.act(g, whole_stack=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))

    # ------------------------------------------------------------------ drawing
    def update(self, dt):
        self.msg_t = max(0.0, self.msg_t - dt)

    def draw(self, g, v):
        dim = pygame.Surface(v.get_size(), pygame.SRCALPHA)
        dim.fill((8, 6, 10, 195))
        v.blit(dim, (0, 0))
        g.panel(v, PANEL, 245)
        shop, mouse = self.shop, g.mouse_view()
        g.text_shadow(v, g.font_m, shop["name"], (PANEL.x + 16, PANEL.y + 12), (255, 232, 170))
        # purse + renown
        draw_coin(v, PANEL.right - 118, PANEL.y + 21, 1.1)
        g.text_shadow(v, g.font_m, str(g.eco.gold), (PANEL.right - 106, PANEL.y + 14), (255, 226, 150))
        disc = self.discount(g)
        nxt = ECO.next_renown_step(g.quests.renown)
        if disc:
            ren = f"Renown {g.quests.renown}: {int(disc * 100)}% off"
        elif nxt:
            ren = f"Renown {g.quests.renown}  (finish side quests for discounts)"
        else:
            ren = f"Renown {g.quests.renown}"
        g.text_shadow(v, g.font_s, ren, (PANEL.right - 16 - g.font_s.size(ren)[0], PANEL.y + 36), (214, 190, 120))
        # tabs
        for rect, name, tab in ((TAB_BUY, "BUY", "buy"), (TAB_SELL, "SELL", "sell")):
            on = self.tab == tab
            off = tab == "sell" and not shop["buys"]
            pygame.draw.rect(v, (70, 52, 44) if on else (34, 24, 22), rect, border_radius=6)
            pygame.draw.rect(v, (255, 214, 120) if on else ((120, 100, 88) if rect.collidepoint(mouse) else (84, 68, 58)),
                             rect, 2 if on else 1, border_radius=6)
            t = g.font_s.render(name, True, (255, 246, 226) if not off else (110, 100, 96))
            v.blit(t, (rect.centerx - t.get_width() // 2, rect.y + 5))
        ents = self.entries(g)
        self.sel = max(0, min(self.sel, max(0, len(ents) - 1)))
        self._scroll_to_sel(len(ents))
        # list
        lst = pygame.Rect(LIST_X - 4, LIST_Y - 4, LIST_W + 8, ROWS_VISIBLE * ROW_H + 6)
        pygame.draw.rect(v, (26, 18, 18), lst, border_radius=6)
        pygame.draw.rect(v, (96, 76, 64), lst, 1, border_radius=6)
        if not ents:
            txt = ("Nothing for sale." if self.tab == "buy" else
                   "Nothing to sell. Monsters in the Hollow drop loot the shopkeepers will buy.")
            for j, ln in enumerate(_wrap(g.font_s, txt, LIST_W - 20)):
                v.blit(g.font_s.render(ln, True, (160, 150, 140)), (LIST_X + 10, LIST_Y + 10 + j * 13))
        for i in range(min(ROWS_VISIBLE, len(ents) - self.scroll)):
            e = ents[self.scroll + i]
            r = pygame.Rect(LIST_X, LIST_Y + i * ROW_H, LIST_W, ROW_H - 2)
            cur = self.scroll + i == self.sel
            hover = r.collidepoint(mouse)
            pygame.draw.rect(v, (62, 44, 38) if cur else (36, 26, 24), r, border_radius=5)
            pygame.draw.rect(v, (255, 214, 120) if cur else ((170, 140, 100) if hover else (70, 56, 48)), r,
                             2 if cur else 1, border_radius=5)
            grey = bool(e["locked"] or e["maxed"] or (self.tab == "buy" and not g.eco.can_afford(e["price"])))
            if e["icon"]:
                draw_icon(v, e["icon"], r.x + 15, r.centery - 1, 0.62)
            elif e["kind"] == "upgrade":
                pygame.draw.rect(v, (150, 160, 176), (r.x + 7, r.centery - 6, 16, 12), border_radius=3)
                pygame.draw.rect(v, (236, 214, 150), (r.x + 9, r.centery - 4, 12, 8), 1, border_radius=2)
            else:
                pygame.draw.circle(v, (150, 180, 220), (r.x + 15, r.centery), 7)
            name = e["name"] + (f"  x{e['owned']}" if self.tab == "sell" else "")
            col = (150, 142, 134) if grey else (255, 246, 226)
            v.blit(g.font_s.render(name, True, col), (r.x + 32, r.y + 6))
            if e["maxed"]:
                price_txt = "MAX"
            elif e["locked"]:
                price_txt = "LOCKED"
            else:
                price_txt = str(e["price"])
            pc = (255, 226, 150) if not grey else (150, 140, 120)
            pt = g.font_s.render(price_txt, True, pc)
            v.blit(pt, (r.right - pt.get_width() - 24, r.y + 6))
            if not e["maxed"] and not e["locked"]:
                draw_coin(v, r.right - 13, r.centery, 0.8)
        if len(ents) > ROWS_VISIBLE:                                   # scrollbar
            bar_h = max(14, int(lst.h * ROWS_VISIBLE / len(ents)))
            bar_y = lst.y + int((lst.h - bar_h) * self.scroll / max(1, len(ents) - ROWS_VISIBLE))
            pygame.draw.rect(v, (120, 100, 88), (lst.right - 4, bar_y, 3, bar_h), border_radius=2)
        # details
        det = pygame.Rect(DET_X, PANEL.y + 50, PANEL.w - (DET_X - PANEL.x) - 14, 266)
        pygame.draw.rect(v, (30, 22, 20), det, border_radius=6)
        pygame.draw.rect(v, (96, 76, 64), det, 1, border_radius=6)
        if ents:
            e = ents[self.sel]
            if e["icon"]:
                draw_icon(v, e["icon"], det.x + 30, det.y + 34, 1.7)
            g.text_shadow(v, g.font_m, e["name"], (det.x + 64, det.y + 12), (255, 246, 226))
            sub = ""
            if e["owned"] is not None and self.tab == "buy":
                sub = f"You own {e['owned']}"
            elif e["kind"] == "upgrade":
                sub = f"Tier {g.eco.tier(e['id'])}/{len(ECO.UPGRADES[e['id']]['tiers'])} bought"
            g.text_shadow(v, g.font_s, sub, (det.x + 64, det.y + 34), (255, 220, 140))
            for j, ln in enumerate(_wrap(g.font_s, e["desc"], det.w - 20)[:5]):
                v.blit(g.font_s.render(ln, True, (214, 206, 194)), (det.x + 10, det.y + 62 + j * 13))
            y = det.y + 134
            if e["kind"] == "upgrade" and not e["maxed"]:
                u = ECO.UPGRADES[e["id"]]
                t = g.eco.tier(e["id"])
                if u["stat"] == "armor":
                    eff = f"Damage taken -{int(u['tiers'][t]['pct'] * 100)}%"
                else:
                    eff = {"sword": "Sword damage", "magic": "Fireball damage", "hp": "Max HP", "mp": "Max MP"}[u["stat"]]
                    eff += f" +{u['per']}"
                v.blit(g.font_s.render("This tier: " + eff, True, (170, 235, 170)), (det.x + 10, y))
                y += 16
            if self.tab == "sell" and e.get("wanted"):
                v.blit(g.font_s.render("A quest is waiting for this item!", True, (255, 190, 110)), (det.x + 10, y))
                y += 16
            if e["locked"]:
                for j, ln in enumerate(_wrap(g.font_s, e["locked"], det.w - 20)):
                    v.blit(g.font_s.render(ln, True, (255, 150, 130)), (det.x + 10, y + j * 13))
            # price + button
            if not e["maxed"] and not e["locked"]:
                label = "Cost" if self.tab == "buy" else "Sells for"
                draw_coin(v, det.x + 18, det.y + 178, 1.1)
                g.text_shadow(v, g.font_m, f"{e['price']}", (det.x + 30, det.y + 171), (255, 226, 150))
                v.blit(g.font_s.render(label, True, (190, 180, 160)), (det.x + 78, det.y + 176))
            can = not e["maxed"] and not e["locked"] and (self.tab == "sell" or g.eco.can_afford(e["price"]))
            hov = ACT_BTN.collidepoint(mouse)
            pygame.draw.rect(v, (70, 120, 80) if can else (60, 56, 56), ACT_BTN, border_radius=6)
            pygame.draw.rect(v, (190, 235, 190) if (can and hov) else (150, 140, 130), ACT_BTN, 1, border_radius=6)
            word = "BUY  [E]" if self.tab == "buy" else "SELL  [E]"
            if e["kind"] == "service":
                word = "REST  [E]"
            elif e["kind"] == "upgrade":
                word = "UPGRADE  [E]"
            t = g.font_s.render(word, True, (255, 255, 255) if can else (150, 146, 146))
            v.blit(t, (ACT_BTN.centerx - t.get_width() // 2, ACT_BTN.y + 7))
            if self.tab == "sell" and e["owned"] > 1:
                v.blit(g.font_s.render("SHIFT+E: sell all", True, (190, 180, 160)), (ACT_BTN.right + 8, ACT_BTN.y + 7))
        # message + footer
        if self.msg_t > 0 and self.msg:
            for j, ln in enumerate(_wrap(g.font_s, self.msg, det.w - 20)[:3]):
                v.blit(g.font_s.render(ln, True, (255, 236, 190)), (det.x + 10, det.y + 228 + j * 13))
        g.text_shadow(v, g.font_s, "W/S: select    A/D or TAB: buy / sell    E: confirm    T / ESC: leave",
                      (PANEL.x + 16, PANEL.bottom - 18), (200, 190, 170))
