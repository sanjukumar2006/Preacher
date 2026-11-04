"""The quest log (key J): every quest you have taken, organised.

Left   MAIN STORY, SIDE QUESTS and COMPLETED, each as a list.  Gold ! = ready to turn in, a star marks the tracked quest.
Right  the selected quest: who gave it, what it is about, each objective with progress, and the reward.

W / S select    T track the selected quest on the HUD    J / ESC close"""
import re

import pygame

import economy as ECO
import quests as QU
from inventory import _wrap

PANEL = pygame.Rect(48, 14, 544, 332)
LIST_X, LIST_Y, LIST_W, ROW_H, ROWS = PANEL.x + 12, PANEL.y + 54, 196, 17, 15
DET_X = PANEL.x + 220


def rows(g):
    """Flat list of ('hdr', text) and ('q', quest, status) rows for the left column."""
    ql = g.quests
    act = ql.active_quests()
    out = []
    main = [q for q in act if q["kind"] == "main"]
    side = [q for q in act if q["kind"] == "side"]
    out.append(("hdr", "MAIN STORY"))
    out += [("q", q, ql.state[q["id"]]) for q in main] or [("none", "No main quest yet.")]
    out.append(("hdr", "SIDE QUESTS"))
    out += [("q", q, ql.state[q["id"]]) for q in side] or [("none", "Villagers will ask for help.")]
    done = ql.done_quests()
    out.append(("hdr", f"COMPLETED ({len(done)})"))
    out += [("q", q, "done") for q in reversed(done)]
    return out


def selectable(rs):
    return [i for i, r in enumerate(rs) if r[0] == "q"]


def draw_questlog(g, v):
    ql, rs = g.quests, rows(g)
    sel_rows = selectable(rs)
    mouse = g.mouse_view()
    dim = pygame.Surface(v.get_size(), pygame.SRCALPHA)
    dim.fill((8, 6, 10, 195))
    v.blit(dim, (0, 0))
    g.panel(v, PANEL, 245)
    g.text_shadow(v, g.font_m, "QUEST LOG", (PANEL.x + 16, PANEL.y + 12), (255, 232, 170))
    num, name = ql.chapter()
    sub = f"Chapter {num}: {name}"
    g.text_shadow(v, g.font_s, sub, (PANEL.x + 130, PANEL.y + 17), (200, 190, 170))
    ren = f"Renown {ql.renown}"
    d = ECO.renown_discount(ql.renown)
    if d:
        ren += f"  ({int(d * 100)}% off)"
    g.text_shadow(v, g.font_s, ren, (PANEL.right - 16 - g.font_s.size(ren)[0], PANEL.y + 17), (214, 190, 120))
    g.ql_sel = max(0, min(getattr(g, "ql_sel", 0), max(0, len(sel_rows) - 1)))
    cur_row = sel_rows[g.ql_sel] if sel_rows else None

    # ---- list column (scrolls to keep the selected quest visible)
    lst = pygame.Rect(LIST_X - 4, LIST_Y - 4, LIST_W + 8, ROWS * ROW_H + 8)
    pygame.draw.rect(v, (26, 18, 18), lst, border_radius=6)
    pygame.draw.rect(v, (96, 76, 64), lst, 1, border_radius=6)
    top = getattr(g, "ql_top", 0)
    if cur_row is not None:
        if cur_row < top:
            top = max(0, cur_row - 1)
        elif cur_row >= top + ROWS:
            top = cur_row - ROWS + 1
    top = max(0, min(top, max(0, len(rs) - ROWS)))
    g.ql_top = top
    g.ql_rects = []
    for i in range(top, min(len(rs), top + ROWS)):
        r = rs[i]
        y = LIST_Y + (i - top) * ROW_H
        if r[0] == "hdr":
            v.blit(g.font_s.render(r[1], True, (214, 190, 140)), (LIST_X + 4, y + 3))
            pygame.draw.line(v, (96, 76, 64), (LIST_X + 4, y + ROW_H - 2), (LIST_X + LIST_W - 4, y + ROW_H - 2))
        elif r[0] == "none":
            v.blit(g.font_s.render(r[1], True, (130, 122, 114)), (LIST_X + 10, y + 3))
        else:
            q, st = r[1], r[2]
            rect = pygame.Rect(LIST_X, y, LIST_W, ROW_H - 1)
            g.ql_rects.append((rect, sel_rows.index(i)))
            cur = i == cur_row
            if cur:
                pygame.draw.rect(v, (62, 44, 38), rect, border_radius=4)
                pygame.draw.rect(v, (255, 214, 120), rect, 1, border_radius=4)
            elif rect.collidepoint(mouse):
                pygame.draw.rect(v, (46, 34, 30), rect, border_radius=4)
            col = (150, 142, 134) if st == "done" else ((170, 235, 170) if st == "ready" else (255, 246, 226))
            mark = "!" if st == "ready" else ("*" if ql.tracked == q["id"] else " ")
            v.blit(g.font_s.render(mark, True, (255, 214, 90)), (rect.x + 5, rect.y + 3))
            title = q["title"]
            while g.font_s.size(title)[0] > LIST_W - 26 and len(title) > 4:
                title = title[:-2]
            v.blit(g.font_s.render(title, True, col), (rect.x + 16, rect.y + 3))

    # ---- detail column
    det = pygame.Rect(DET_X, PANEL.y + 50, PANEL.w - (DET_X - PANEL.x) - 12, 270)
    pygame.draw.rect(v, (30, 22, 20), det, border_radius=6)
    pygame.draw.rect(v, (96, 76, 64), det, 1, border_radius=6)
    if cur_row is None:
        for j, ln in enumerate(_wrap(g.font_s, "You have no quests yet. Talk to Elder Maren in the village plaza.", det.w - 24)):
            v.blit(g.font_s.render(ln, True, (190, 180, 160)), (det.x + 12, det.y + 14 + j * 13))
    else:
        q, st = rs[cur_row][1], rs[cur_row][2]
        g.text_shadow(v, g.font_m, q["title"], (det.x + 12, det.y + 10), (255, 246, 226))
        kind = f"Main story - Chapter {q['chapter']}" if q["kind"] == "main" else "Side quest"
        g.text_shadow(v, g.font_s, kind, (det.x + 12, det.y + 30), (255, 220, 140))
        who = QU.NPC_NAME.get(q["giver"], q["giver"])
        turn = QU.NPC_NAME.get(q["turn_in"], q["turn_in"])
        y = det.y + 46
        v.blit(g.font_s.render(f"Given by {who}" + (f"   -   hand in to {turn}" if turn != who else ""), True,
                               (190, 180, 160)), (det.x + 12, y))
        y += 18
        for ln in _wrap(g.font_s, q["summary"], det.w - 24):
            v.blit(g.font_s.render(ln, True, (214, 206, 194)), (det.x + 12, y))
            y += 13
        y += 8
        v.blit(g.font_s.render("OBJECTIVES", True, (214, 190, 140)), (det.x + 12, y))
        y += 16
        if st == "done":
            for t in range(len(q["objectives"])):
                text = re.sub(r"\s*\(\d+/\d+\)$", "", ql.obj_text(g, q, t))      # no stale 0/4 after items were handed in
                _check(v, det.x + 12, y, True)
                v.blit(g.font_s.render(text, True, (150, 142, 134)), (det.x + 30, y))
                y += 15
        else:
            for text, done in ql.objectives(g, q):
                _check(v, det.x + 12, y, done)
                lines = _wrap(g.font_s, text, det.w - 44)
                for j, ln in enumerate(lines):
                    v.blit(g.font_s.render(ln, True, (150, 142, 134) if done else (236, 228, 214)), (det.x + 30, y + j * 13))
                y += 15 + (len(lines) - 1) * 13
            if st == "ready":
                y += 4
                v.blit(g.font_s.render(f"Ready! Return to {turn}.", True, (170, 235, 170)), (det.x + 12, y))
                y += 16
        y += 8
        v.blit(g.font_s.render("REWARD", True, (214, 190, 140)), (det.x + 12, y))
        y += 16
        rt = ql.reward_text(q).replace("REWARD: ", "")
        for ln in _wrap(g.font_s, rt, det.w - 24):
            v.blit(g.font_s.render(ln, True, (255, 226, 150) if st != "done" else (150, 142, 134)), (det.x + 12, y))
            y += 13
        if st in ("active", "ready"):
            tracked = ql.tracked == q["id"]
            label = "Tracked on HUD" if tracked else "T: track this quest"
            v.blit(g.font_s.render(label, True, (170, 235, 170) if tracked else (200, 190, 170)),
                   (det.x + 12, det.bottom - 18))
        else:
            v.blit(g.font_s.render("Completed", True, (150, 142, 134)), (det.x + 12, det.bottom - 18))
    g.text_shadow(v, g.font_s, "W/S: select    T: track    J / ESC: close", (PANEL.x + 16, PANEL.bottom - 16),
                  (200, 190, 170))


def _check(v, x, y, done):
    pygame.draw.rect(v, (26, 18, 18), (x, y + 1, 10, 10), border_radius=2)
    pygame.draw.rect(v, (170, 235, 170) if done else (150, 130, 110), (x, y + 1, 10, 10), 1, border_radius=2)
    if done:
        pygame.draw.line(v, (170, 235, 170), (x + 2, y + 6), (x + 4, y + 9), 2)
        pygame.draw.line(v, (170, 235, 170), (x + 4, y + 9), (x + 9, y + 2), 2)


def questlog_key(g, k):
    """Returns True if the key was used."""
    rs = rows(g)
    sel = selectable(rs)
    n = len(sel)
    if k in (pygame.K_UP, pygame.K_w) and n:
        g.ql_sel = (getattr(g, "ql_sel", 0) - 1) % n
    elif k in (pygame.K_DOWN, pygame.K_s) and n:
        g.ql_sel = (getattr(g, "ql_sel", 0) + 1) % n
    elif k == pygame.K_t and n:
        r = rs[sel[min(getattr(g, "ql_sel", 0), n - 1)]]
        if r[2] in ("active", "ready"):
            g.quests.track(r[1]["id"])
            g.toast(f"Tracking: {r[1]['title']}", 2.0)
    else:
        return False
    g.play("blip")
    return True


def questlog_click(g, pos):
    for rect, idx in getattr(g, "ql_rects", []):
        if rect.collidepoint(pos):
            g.ql_sel = idx
            g.play("blip")
            return
