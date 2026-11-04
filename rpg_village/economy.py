"""The Hearthmoor economy: currency, income, prices, shops and permanent upgrades.

Everything here is plain Python (no pygame) so the numbers are easy to tune and to test.

CURRENCY   Crowns.  You earn them from monster bounties, first-time floor-clear bonuses, selling loot and
           finishing quests.  You spend them in the village shops (press T next to a shopkeeper), on
           permanent upgrades, and at the inn.  Dying costs a small slice of your purse.

TUNING     Every number you might want to change is a constant at the top of this file or in the SHOPS /
           UPGRADES tables below.  Item prices live in PRICES (buy, sell).  Quest rewards live in story.py.
"""
import random

CURRENCY = "Crowns"
CURRENCY_SHORT = "Cr"

# --------------------------------------------------------------------------- income
# Base bounty paid per monster.  Deeper floors pay more: x (1 + FLOOR_BOUNTY_STEP * (floor - 1)).
MONSTER_BOUNTY = {
    "slime": 5, "slime_g": 6, "skeleton": 7, "wraith": 7, "gargoyle": 9,
    "dark_mage": 10, "ice_mage": 10, "fire_mage": 11, "imp_mage": 11, "witch": 12,
    "ogre": 18, "brute": 18, "drake": 20, "wyrm": 26,
}
FLOOR_BOUNTY_STEP = 0.20
BOUNTY_SPREAD = 0.25          # +/- random variation on every bounty
BOSS_BOUNTY = 250             # Grimhorn
FLOOR_CLEAR_BONUS = 20        # per floor number, paid once: floor 3 pays 60
DEATH_PENALTY_PCT = 0.10      # share of your purse lost when you fall in the dungeon...
DEATH_PENALTY_MAX = 40        # ...but never more than this

# Monster loot: monster key -> [(item, chance), ...].  Loot is sold to shopkeepers or handed in for quests.
LOOT = {
    "skeleton": [("bone_shard", 0.60)],
    "wraith": [("ectoplasm", 0.50), ("bone_shard", 0.30)],
    "slime": [("slime_gel", 0.60)], "slime_g": [("slime_gel", 0.60)],
    "gargoyle": [("stone_chip", 0.60)],
    "dark_mage": [("arcane_dust", 0.40), ("ectoplasm", 0.25)],
    "ice_mage": [("arcane_dust", 0.40)], "fire_mage": [("arcane_dust", 0.40)],
    "imp_mage": [("arcane_dust", 0.40)],
    "witch": [("arcane_dust", 0.40), ("ectoplasm", 0.25)],
    "ogre": [("beast_hide", 0.60), ("stone_chip", 0.30)], "brute": [("beast_hide", 0.60), ("stone_chip", 0.30)],
    "drake": [("beast_hide", 0.65)], "wyrm": [("beast_hide", 0.70)],
}
# Monsters never come back once a floor is cleared, so loot is finite.  To keep quest items reachable,
# every loot item has a "pity timer": after this many eligible kills with no drop, the next one drops.
PITY_KILLS = 3

# --------------------------------------------------------------------------- prices
# item key -> (buy price, sell price).  buy None = never sold in shops.  sell None = cannot be sold.
PRICES = {
    "health_potion":  (25, 10),
    "mana_potion":    (25, 10),
    "greater_health": (70, 28),
    "greater_mana":   (70, 28),
    "bread":          (6, 2),
    "honey_bun":      (14, 5),
    "hot_stew":       (18, 7),
    "bone_shard":     (None, 5),
    "ectoplasm":      (None, 7),
    "slime_gel":      (None, 4),
    "stone_chip":     (None, 6),
    "arcane_dust":    (None, 9),
    "beast_hide":     (None, 16),
}

# --------------------------------------------------------------------------- permanent upgrades
# Each upgrade has tiers bought in order.  `need` is a story flag that must be set before that tier is for sale
# (flags come from finishing quests - see story.py).  `stat` says how the effect is applied:
#   sword / magic / armor are recalculated from the tier,  hp / mp are applied once when bought.
UPGRADES = {
    "sword": dict(name="Sword Sharpening", stat="sword", per=4,
                  desc="Bram hones your blade. +4 sword damage per tier.",
                  tiers=[dict(price=100, need=None), dict(price=220, need="forge_open"),
                         dict(price=380, need="forge_open")]),
    "armor": dict(name="Hearth Mail", stat="armor", per=0.0,
                  desc="Bram riveting plates over your tunic. Reduces damage taken.",
                  tiers=[dict(price=90, need=None, pct=0.10), dict(price=200, need="forge_open", pct=0.18),
                         dict(price=340, need="forge_open", pct=0.25)]),
    "magic": dict(name="Fireball Focus", stat="magic", per=6,
                  desc="Wren binds ember-sage into your focus. +6 fireball damage per tier.",
                  tiers=[dict(price=120, need=None), dict(price=240, need="wren_brews")]),
    "vitality": dict(name="Vitality Tonic", stat="hp", per=10,
                     desc="A bitter tonic. Permanently raises max HP by 10.",
                     tiers=[dict(price=80, need=None), dict(price=160, need=None), dict(price=260, need="wren_brews")]),
    "arcane": dict(name="Arcane Draught", stat="mp", per=10,
                   desc="Liquid starlight. Permanently raises max MP by 10.",
                   tiers=[dict(price=80, need=None), dict(price=160, need="wren_brews")]),
}

# --------------------------------------------------------------------------- services
SERVICES = {
    "rest": dict(name="Rent a Bed", price=14, desc="Sleep until morning. Fully restores HP and MP."),
}
INN_FRIEND_DISCOUNT = 0.5     # Rosalind halves the room price once you have settled Lark's tab

# --------------------------------------------------------------------------- shops
# open_flag: shop opens when this story flag is set (None = always open).   buys: shop also buys your loot.
# stock entries:  ("item", key[, flag])   ("upgrade", id)   ("service", id)
SHOPS = {
    "tobias": dict(name="Tobias's General Store", open_flag="caravan", buys=True,
                   closed="Sorry, friend - the shelves are bare until the caravan arrives!",
                   greet="Step right up! The caravan came through and I have actual goods!",
                   stock=[("item", "health_potion"), ("item", "mana_potion"), ("item", "bread"),
                          ("item", "greater_health", "tobias_stock"), ("item", "greater_mana", "tobias_stock")]),
    "pip": dict(name="Pip's Bakery", open_flag=None, buys=False,
                closed="", greet="Fresh bread! Hot out of the oven! ...Well, warm.",
                stock=[("item", "bread"), ("item", "honey_bun")]),
    "bram": dict(name="Bram's Smithy", open_flag=None, buys=True,
                 closed="", greet="Mind the sparks. What can the forge do for you?",
                 stock=[("upgrade", "sword"), ("upgrade", "armor")]),
    "wren": dict(name="Sage Wren's Remedies", open_flag=None, buys=True,
                 closed="", greet="Come in, dear. Mind the foxglove.",
                 stock=[("upgrade", "vitality"), ("upgrade", "arcane"), ("upgrade", "magic"),
                        ("item", "greater_health"), ("item", "greater_mana")]),
    "rosalind": dict(name="The Sleeping Fox Inn", open_flag=None, buys=False,
                     closed="", greet="Welcome to the Sleeping Fox! Stew, or a bed?",
                     stock=[("item", "hot_stew"), ("service", "rest")]),
}

# Village renown: every finished side quest adds 1.  Renown gives a discount in every shop.
RENOWN_DISCOUNTS = [(8, 0.20), (6, 0.15), (4, 0.10), (2, 0.05)]       # (renown needed, discount)


def renown_discount(renown):
    for need, pct in RENOWN_DISCOUNTS:
        if renown >= need:
            return pct
    return 0.0


def next_renown_step(renown):
    """(renown needed, discount) of the next reward, or None when maxed."""
    for need, pct in reversed(RENOWN_DISCOUNTS):
        if renown < need:
            return need, pct
    return None


def discounted(price, discount):
    return max(1, int(round(price * (1.0 - discount))))


def buy_price(item):
    return PRICES.get(item, (None, None))[0]


def sell_price(item):
    return PRICES.get(item, (None, None))[1]


def floor_bonus(level):
    return FLOOR_CLEAR_BONUS * int(level)


class Economy:
    """The player's purse and everything bought with it."""

    def __init__(self):
        self.gold = 0
        self.earned = 0
        self.spent = 0
        self.upgrades = {}            # upgrade id -> tiers bought
        self.bonus_floors = set()     # floors whose first-clear bonus was already paid
        self.miss = {}                # loot item -> eligible kills since its last drop (pity timer)
        self.rng = random.Random()

    # ---- purse
    def earn(self, n):
        n = int(n)
        if n > 0:
            self.gold += n
            self.earned += n
        return n

    def can_afford(self, n):
        return self.gold >= int(n)

    def spend(self, n):
        n = int(n)
        if n > self.gold:
            return False
        self.gold -= n
        self.spent += n
        return True

    def death_penalty(self):
        """Take the dungeon-death toll. Returns the amount lost."""
        loss = min(DEATH_PENALTY_MAX, int(self.gold * DEATH_PENALTY_PCT))
        self.gold -= loss
        return loss

    # ---- income rolls
    def bounty(self, monster_key, floor, rng=None):
        base = MONSTER_BOUNTY.get(monster_key)
        if base is None:
            return 0
        rng = rng or self.rng
        mult = 1.0 + FLOOR_BOUNTY_STEP * (max(1, floor) - 1)
        spread = 1.0 + rng.uniform(-BOUNTY_SPREAD, BOUNTY_SPREAD)
        return max(1, int(round(base * mult * spread)))

    def loot(self, monster_key, rng=None):
        """List of item keys dropped by this monster (usually empty or one item)."""
        rng = rng or self.rng
        out = []
        for item, chance in LOOT.get(monster_key, []):
            if rng.random() < chance or self.miss.get(item, 0) >= PITY_KILLS:
                out.append(item)
                self.miss[item] = 0
            else:
                self.miss[item] = self.miss.get(item, 0) + 1
        return out

    # ---- upgrades
    def tier(self, uid):
        return self.upgrades.get(uid, 0)

    def next_tier(self, uid):
        """The next tier dict for sale (with its index), or None when fully upgraded."""
        tiers = UPGRADES[uid]["tiers"]
        t = self.tier(uid)
        return (t, tiers[t]) if t < len(tiers) else None

    def sword_bonus(self):
        return self.tier("sword") * UPGRADES["sword"]["per"]

    def magic_bonus(self):
        return self.tier("magic") * UPGRADES["magic"]["per"]

    def armor_pct(self):
        t = self.tier("armor")
        return UPGRADES["armor"]["tiers"][t - 1]["pct"] if t else 0.0

    # ---- save / load
    def to_save(self):
        return dict(gold=self.gold, earned=self.earned, spent=self.spent,
                    upgrades=dict(self.upgrades), bonus_floors=sorted(self.bonus_floors), miss=dict(self.miss))

    def from_save(self, d):
        d = d or {}
        self.gold = max(0, int(d.get("gold", 0)))
        self.earned = int(d.get("earned", self.gold))
        self.spent = int(d.get("spent", 0))
        self.upgrades = {k: int(v) for k, v in d.get("upgrades", {}).items() if k in UPGRADES}
        self.bonus_floors = set(int(f) for f in d.get("bonus_floors", []))
        self.miss = {k: int(v) for k, v in d.get("miss", {}).items()}


# --------------------------------------------------------------------------- item names (single source of truth)
ITEM_NAMES = {
    "health_potion": "Health Potion", "mana_potion": "Mana Potion",
    "greater_health": "Greater Health Potion", "greater_mana": "Greater Mana Potion",
    "bread": "Bread", "honey_bun": "Honey Bun", "hot_stew": "Hot Stew",
    "bone_shard": "Bone Shard", "ectoplasm": "Ectoplasm", "slime_gel": "Slime Gel",
    "stone_chip": "Stone Chip", "arcane_dust": "Arcane Dust", "beast_hide": "Beast Hide",
}


def item_name(key, n=1):
    """'Bone Shard' / 'Bone Shards'.  (Ectoplasm and Bread are uncountable and stay as they are.)"""
    name = ITEM_NAMES.get(key, key)
    if n == 1 or key in ("ectoplasm", "bread"):
        return name
    return name + "s"
