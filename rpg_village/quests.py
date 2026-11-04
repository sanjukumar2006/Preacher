"""The quest engine.  Rules live here, the quests themselves live in story.py.

LIFE OF A QUEST
    locked     its `requires` quests are not finished yet            (invisible)
    available  the giver has something to ask: a gold "!" floats over their head
    active     accepted; objectives are tracked automatically         (quest log: J)
    ready      every objective is met: a gold "?" floats over the turn-in villager
    done       turned in; rewards paid

WHAT THE GAME TELLS THE ENGINE  (main.py calls these)
    notify(game, "kill", key=, big=, floor=)     a monster died
    notify(game, "place", name=)                 the hero walked into a named place
    notify(game, "spend", amount=)               Crowns were spent in a shop
    notify(game, "floor", level=)                the hero set foot on a dungeon floor
    update(game, dt)                             re-checks objectives a few times a second
    converse(game, npc) -> (lines, after)        what a villager says, and what happens when it ends

`game` is only used through: game.combat (cleared_floors, boss_defeated, inv, max_hp, ...), game.eco, game.npcs,
game.toast(), game.save_game().  That makes the engine easy to test with a stand-in object.
"""
import economy as ECO
import story
from data import NPCS

NPC_NAME = {n["id"]: n["name"] for n in NPCS}
BY_ID = {q["id"]: q for q in story.QUESTS}
MAIN = [q for q in story.QUESTS if q["kind"] == "main"]

HUD_SECONDS = 6.0            # how long the full tracker panel stays open after something changes
CHECK_EVERY = 0.25


class QuestLog:
    def __init__(self):
        self.state = {}                 # quest id -> "active" | "ready" | "done"
        self.prog = {}                  # quest id -> [progress per objective] (talk / visit / spend)
        self.flags = set()
        self.renown = 0
        self.done_order = []            # finished quest ids, oldest first
        self.tracked = None
        self.hud_t = 0.0
        self.stats = dict(kills=0, big=0, by_key={}, by_floor={}, max_floor=0)
        self._t = 0.0

    # ------------------------------------------------------------------ queries
    def has(self, flag):
        return flag in self.flags

    def requires_ok(self, q, assume_done=()):
        return all(self.state.get(r) == "done" or r in assume_done for r in q["requires"])

    def available(self, npc_id=None, assume_done=()):
        """Quests that could be accepted now, main story first."""
        out = [q for q in story.QUESTS
               if q["id"] not in self.state and q["id"] not in assume_done and self.requires_ok(q, assume_done)
               and (npc_id is None or q["giver"] == npc_id)]
        return sorted(out, key=lambda q: q["kind"] != "main")

    def ready_for(self, npc_id):
        out = [q for q in story.QUESTS if self.state.get(q["id"]) == "ready" and q["turn_in"] == npc_id]
        return sorted(out, key=lambda q: q["kind"] != "main")

    def active_for(self, npc_id):
        out = [q for q in story.QUESTS if self.state.get(q["id"]) == "active"
               and npc_id in (q["giver"], q["turn_in"])]
        return sorted(out, key=lambda q: q["kind"] != "main")

    def talk_targets(self, npc_id):
        """(quest, index, objective) for every unfinished 'talk to this villager' objective that is active."""
        out = []
        for q in story.QUESTS:
            if self.state.get(q["id"]) != "active":
                continue
            for i, o in enumerate(q["objectives"]):
                if o["t"] == "talk" and o["npc"] == npc_id and not self.prog.get(q["id"], [0] * 9)[i]:
                    out.append((q, i, o))
        return out

    def count(self, status):
        return sum(1 for s in self.state.values() if s == status)

    def active_quests(self):
        """Quests shown in the log: ready first, then active; main before side."""
        order = {"ready": 0, "active": 1}
        qs = [q for q in story.QUESTS if self.state.get(q["id"]) in order]
        return sorted(qs, key=lambda q: (q["kind"] != "main", order[self.state[q["id"]]]))

    def done_quests(self):
        return [BY_ID[i] for i in self.done_order if i in BY_ID]

    def chapter(self):
        """(number, name) of the chapter the story is in."""
        for q in MAIN:
            if self.state.get(q["id"]) != "done":
                return q["chapter"], story.CHAPTERS[q["chapter"]]
        return len(story.CHAPTERS), "The End... for now"

    def marker(self, npc_id):
        """What floats over a villager: 'ready' (?), 'offer' (!), 'talk' (a quest wants you to speak to them) or None."""
        if self.ready_for(npc_id):
            return "ready"
        if self.available(npc_id):
            return "offer"
        if self.talk_targets(npc_id):
            return "talk"
        return None

    # ------------------------------------------------------------------ objectives
    def _kills(self, o):
        s = self.stats
        if o.get("of") == "big":
            return s["big"]
        if o.get("floors"):
            return sum(s["by_floor"].get(f, 0) for f in o["floors"])
        if o.get("of"):
            return sum(s["by_key"].get(k, 0) for k in o["of"])
        return s["kills"]

    def obj_state(self, game, q, i):
        """(done, current, needed) for one objective."""
        o = q["objectives"][i]
        t = o["t"]
        p = self.prog.get(q["id"], [0] * len(q["objectives"]))[i]
        c = game.combat
        if t == "kill":
            cur, need = self._kills(o), o["n"]
        elif t == "clear":
            cur, need = int(o["floor"] in c.cleared_floors or c.boss_defeated), 1
        elif t == "boss":
            cur, need = int(c.boss_defeated), 1
        elif t == "deliver":
            cur, need = c.inv.count(o["item"]), o["n"]
        elif t in ("talk", "visit"):
            cur, need = p, 1
        elif t == "spend":
            cur, need = p, o["n"]
        elif t == "reach":
            cur, need = int(self.stats["max_floor"] >= o["floor"]), 1
        elif t == "pay":
            cur, need = game.eco.gold, o["n"]
        elif t == "meet":
            cur, need = sum(1 for n in game.npcs if n.talk_count > 0 and n.id != "elder"), o["n"]
        else:
            cur, need = 0, 1
        cur = min(cur, need)
        return cur >= need, cur, need

    def obj_text(self, game, q, i):
        """Readable objective line with progress, e.g. 'Bring 4 Bone Shards (2/4)'."""
        o = q["objectives"][i]
        done, cur, need = self.obj_state(game, q, i)
        t = o["t"]
        if t == "kill":
            return f"Slay {need} {o.get('label', 'monsters')} ({cur}/{need})"
        if t == "clear":
            return f"Clear floor {o['floor']} of the Hollow Below"
        if t == "boss":
            return "Defeat Grimhorn, Warden of the Hollow"
        if t == "deliver":
            return f"Bring {need} {ECO.item_name(o['item'], need)} ({cur}/{need})"
        if t == "talk":
            return f"Speak with {NPC_NAME.get(o['npc'], o['npc'])}"
        if t == "visit":
            return f"Visit {o['place']}"
        if t == "spend":
            return f"Spend {need} {ECO.CURRENCY} in the village shops ({cur}/{need})"
        if t == "reach":
            return f"Reach floor {o['floor']} of the Hollow Below"
        if t == "pay":
            return f"Pay {need} {ECO.CURRENCY} ({cur}/{need})"
        if t == "meet":
            return f"Greet {need} villagers ({cur}/{need})"
        return t

    def objectives(self, game, q):
        return [(self.obj_text(game, q, i), self.obj_state(game, q, i)[0]) for i in range(len(q["objectives"]))]

    @staticmethod
    def reward_text(q):
        """'REWARD: 40 Crowns, 2 Health Potions, +20 max HP'."""
        r = q.get("reward", {})
        bits = []
        if r.get("gold"):
            bits.append(f"{r['gold']} {ECO.CURRENCY}")
        for k, n in r.get("items", {}).items():
            bits.append(f"{n} {ECO.item_name(k, n)}")
        if r.get("max_hp"):
            bits.append(f"+{r['max_hp']} max HP")
        if r.get("max_mp"):
            bits.append(f"+{r['max_mp']} max MP")
        if r.get("renown"):
            bits.append("village renown")
        if "inn_friend" in r.get("flags", []):
            bits.append("half-price beds")
        if "forge_open" in r.get("flags", []):
            bits.append("Bram's finer forge work")
        if "wren_brews" in r.get("flags", []):
            bits.append("Wren's finer recipes")
        if "tobias_stock" in r.get("flags", []):
            bits.append("greater potions at Tobias's")
        if "caravan" in r.get("flags", []):
            bits.append("Tobias's store opens")
        return "REWARD: " + (", ".join(bits) if bits else "the village's thanks")

    # ------------------------------------------------------------------ events
    def notify(self, game, event, **kw):
        s = self.stats
        if event == "kill":
            s["kills"] += 1
            s["big"] += int(bool(kw.get("big")))
            key, floor = kw.get("key"), kw.get("floor")
            if key:
                s["by_key"][key] = s["by_key"].get(key, 0) + 1
            if floor:
                s["by_floor"][floor] = s["by_floor"].get(floor, 0) + 1
        elif event == "floor":
            s["max_floor"] = max(s["max_floor"], int(kw.get("level", 0)))
        for q in story.QUESTS:
            if self.state.get(q["id"]) not in ("active", "ready"):
                continue
            prog = self.prog.setdefault(q["id"], [0] * len(q["objectives"]))
            for i, o in enumerate(q["objectives"]):
                if event == "talk" and o["t"] == "talk" and o["npc"] == kw.get("npc"):
                    prog[i] = 1
                elif event == "place" and o["t"] == "visit" and o["place"] == kw.get("name"):
                    prog[i] = 1
                elif event == "spend" and o["t"] == "spend":
                    prog[i] = min(o["n"], prog[i] + int(kw.get("amount", 0)))
        self.check(game)

    def update(self, game, dt):
        self.hud_t = max(0.0, self.hud_t - dt)
        self._t -= dt
        if self._t <= 0:
            self._t = CHECK_EVERY
            self.check(game)

    def check(self, game):
        """Move quests between active <-> ready as their objectives are met (or un-met, e.g. items sold)."""
        for q in story.QUESTS:
            st = self.state.get(q["id"])
            if st not in ("active", "ready"):
                continue
            ok = all(self.obj_state(game, q, i)[0] for i in range(len(q["objectives"])))
            if ok and st == "active":
                self.state[q["id"]] = "ready"
                self.hud_t = HUD_SECONDS
                who = NPC_NAME.get(q["turn_in"], q["turn_in"])
                game.toast(f"Quest ready: {q['title']}  -  return to {who}", 5.0)
            elif not ok and st == "ready":
                self.state[q["id"]] = "active"
        self._fix_tracked()

    def _fix_tracked(self):
        if self.tracked and self.state.get(self.tracked) in ("active", "ready"):
            return
        act = self.active_quests()
        self.tracked = act[0]["id"] if act else None

    def track(self, qid):
        if self.state.get(qid) in ("active", "ready"):
            self.tracked = qid
            self.hud_t = HUD_SECONDS

    # ------------------------------------------------------------------ accepting / finishing
    def accept(self, game, qid):
        q = BY_ID[qid]
        if qid in self.state or not self.requires_ok(q):
            return False
        self.state[qid] = "active"
        self.prog[qid] = [0] * len(q["objectives"])
        a = q.get("on_accept", {})
        if a.get("gold"):
            game.eco.earn(a["gold"])
            game.toast(f"Received {a['gold']} {ECO.CURRENCY}", 3.0)
        for k, n in a.get("items", {}).items():
            game.combat.inv.add(k, n)
        if q["kind"] == "main" or not self.tracked or self.state.get(self.tracked) not in ("active", "ready"):
            self.tracked = qid
        self.hud_t = HUD_SECONDS
        if q["kind"] == "main":
            game.toast(f"Chapter {q['chapter']}: {story.CHAPTERS[q['chapter']]}", 5.0)
        else:
            game.toast(f"New quest: {q['title']}  (log: J)", 4.0)
        self.check(game)
        game.save_game(auto=True)
        return True

    def complete(self, game, qid):
        q = BY_ID[qid]
        if self.state.get(qid) != "ready":
            return False
        c, eco = game.combat, game.eco
        for o in q["objectives"]:                       # hand in what was asked for
            if o["t"] == "deliver":
                c.inv.remove(o["item"], o["n"])
            elif o["t"] == "pay":
                eco.spend(o["n"])
        r = q.get("reward", {})
        if r.get("gold"):
            eco.earn(r["gold"])
        for k, n in r.get("items", {}).items():
            left = c.inv.add(k, n)
            if left:
                game.toast("Your pack is full - some rewards were left behind!", 3.0)
        if r.get("max_hp") or r.get("max_mp"):
            c.max_hp += r.get("max_hp", 0)
            c.max_mp += r.get("max_mp", 0)
            c.hp, c.mp = c.max_hp, c.max_mp
        for f in r.get("flags", []):
            self.flags.add(f)
        self.renown += int(r.get("renown", 0))
        self.state[qid] = "done"
        self.done_order.append(qid)
        self.hud_t = HUD_SECONDS
        self._fix_tracked()
        game.toast(f"Quest complete: {q['title']}", 5.0)
        if r.get("renown"):
            old = ECO.renown_discount(self.renown - r["renown"])
            new = ECO.renown_discount(self.renown)
            if new > old:
                game.toast(f"Renown {self.renown}: {int(new * 100)}% off in every shop!", 5.0)
        self.check(game)
        game.save_game(auto=True)
        return True

    # ------------------------------------------------------------------ conversations
    def _objective_summary(self, game, q):
        return f"QUEST: {q['title']}.  " + "  ".join(f"- {t}" for t, _d in self.objectives(game, q))

    def converse(self, game, npc):
        """What `npc` says right now, and a callable to run when the conversation ends.

        Priority: turn in a finished quest  >  intro (first meeting)  >  lines a quest wants this villager to say
        >  a new quest offer (main story first)  >  a reminder of an active quest  >  everyday chatter."""
        nid = npc.id
        first = npc.talk_count == 0
        steps = []                                        # run in order when the dialogue ends
        lines = []
        ready = self.ready_for(nid)
        assume = ()
        if ready:
            q = ready[0]
            lines += list(q["thanks"]) + [self.reward_text(q)]
            steps.append(lambda qid=q["id"]: self.complete(game, qid))
            assume = (q["id"],)
        elif first:
            lines += story.default_lines(npc, self.flags, True)
        if not ready:
            for q, _i, o in self.talk_targets(nid):
                lines += list(o["lines"])
        offers = self.available(nid, assume_done=assume)
        if offers:
            q = offers[0]
            lines += list(q["offer"])
            lines.append(self._objective_summary(game, q))
            steps.append(lambda qid=q["id"]: self.accept(game, qid))
        elif not ready:
            for q in self.active_for(nid):
                lines += list(q["remind"])
                lines.append(self._objective_summary(game, q))
        if not lines:
            lines = story.default_lines(npc, self.flags, False)
        npc.talk_count += 1

        def after():
            self.notify(game, "talk", npc=nid)           # may complete 'speak with X' objectives
            for st in steps:
                st()
        return lines, after

    # ------------------------------------------------------------------ HUD helper
    def tracker(self, game):
        """(title, [(objective text, done)], is_main) for the HUD, or None when there is nothing to show."""
        self._fix_tracked()
        if self.tracked:
            q = BY_ID[self.tracked]
            title = (f"Ch.{q['chapter']}  " if q["kind"] == "main" else "") + q["title"]
            if self.state[self.tracked] == "ready":
                return title, [(f"Return to {NPC_NAME.get(q['turn_in'], q['turn_in'])}", False)], q["kind"] == "main"
            return title, self.objectives(game, q), q["kind"] == "main"
        nxt = self.available()
        main = [q for q in nxt if q["kind"] == "main"]
        if main:
            q = main[0]
            return (f"Ch.{q['chapter']}  {q['title']}",
                    [(f"Talk to {NPC_NAME.get(q['giver'], q['giver'])}", False)], True)
        return None

    # ------------------------------------------------------------------ save / load
    def to_save(self):
        s = self.stats
        return dict(state=dict(self.state), prog={k: list(v) for k, v in self.prog.items()},
                    flags=sorted(self.flags), renown=self.renown, done=list(self.done_order), tracked=self.tracked,
                    stats=dict(kills=s["kills"], big=s["big"], by_key=dict(s["by_key"]),
                               by_floor={str(k): v for k, v in s["by_floor"].items()}, max_floor=s["max_floor"]))

    def from_save(self, d):
        d = d or {}
        self.state = {k: v for k, v in d.get("state", {}).items() if k in BY_ID and v in ("active", "ready", "done")}
        self.prog = {k: [int(x) for x in v] for k, v in d.get("prog", {}).items() if k in BY_ID}
        self.flags = set(d.get("flags", []))
        self.renown = int(d.get("renown", 0))
        self.done_order = [i for i in d.get("done", []) if i in BY_ID]
        self.tracked = d.get("tracked")
        st = d.get("stats", {})
        self.stats = dict(kills=int(st.get("kills", 0)), big=int(st.get("big", 0)),
                          by_key={k: int(v) for k, v in st.get("by_key", {}).items()},
                          by_floor={int(k): int(v) for k, v in st.get("by_floor", {}).items()},
                          max_floor=int(st.get("max_floor", 0)))
        self.hud_t = 0.0
        for q in story.QUESTS:                      # objective list lengths must match the current story data
            if q["id"] in self.state and len(self.prog.get(q["id"], [])) != len(q["objectives"]):
                self.prog[q["id"]] = [0] * len(q["objectives"])
        self._fix_tracked()

    def migrate_old(self, old_state, kills=0):
        """Convert the old single-quest save ('unknown' / 'active' / 'ready' / 'done') to the new chain."""
        self.__init__()
        self.stats["kills"] = int(kills)
        if old_state == "unknown":
            return
        finished = ["m1", "m2"] if old_state == "active" else ["m1", "m2", "m3", "m4"]
        if old_state == "done":
            finished = ["m1", "m2", "m3", "m4", "m5"]
        for qid in finished:
            self.state[qid] = "done"
            self.done_order.append(qid)
            self.flags.update(BY_ID[qid].get("reward", {}).get("flags", []))
        nxt = "m3" if old_state == "active" else ("m5" if old_state == "ready" else None)
        if nxt:
            self.state[nxt] = "active"
            self.prog[nxt] = [0] * len(BY_ID[nxt]["objectives"])
            self.tracked = nxt
        self._fix_tracked()
