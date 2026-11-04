"""The story of Hearthmoor: chapters, quests and how the villagers react as the tale unfolds.

This file is DATA ONLY.  The rules that run it live in quests.py.  To add or change a quest, edit QUESTS below.

THE STORY
  For three hundred years Hearthmoor has slept peacefully above the Hollow Below, a five-floor vault built to hold
  its first Warden, Grimhorn.  The seal that binds him is failing.  A traveler arrives just as the ground starts to
  shake, and the villagers ask for help:  gather supplies, break the rune-stone on every floor, face the Warden,
  and bring the village home to a festival.

CHAPTERS (main quest line, one main quest per chapter)
  1 A Stranger in Hearthmoor      2 Supplies for the Descent     3 Into the Hollow
  4 The Deeper Dark               5 The Warden of the Hollow     6 Hearthmoor Reborn

QUEST FIELDS
  id, title, kind ("main" / "side"), chapter (main only), giver, turn_in (NPC ids from data.py), requires (quest ids
  that must be finished first), summary, offer / remind / thanks (dialogue), objectives, reward, on_accept.

OBJECTIVES  (dict with "t" = type)
  talk    npc               speak to a villager (their `lines` are what they say)
  visit   place             walk into a named place (see PLACES in data.py)
  kill    n, of, floors     slay n monsters  (of = tuple of monster keys, or "big";  floors = tuple of floors)
  clear   floor             clear every monster on a floor of the Hollow Below
  boss                      defeat Grimhorn
  reach   floor             set foot on a floor
  deliver item, n           hand in items (they are taken when you turn the quest in)
  pay     n                 hand over Crowns (taken when you turn the quest in)
  spend   n                 spend Crowns in the village shops after accepting
  meet    n                 greet n different villagers (other than the Elder)

REWARD / ON_ACCEPT  (dict)  gold, items {key: n}, max_hp, max_mp, flags [..], renown (1 for side quests)
FLAGS  are story switches that quests set.  They unlock shop stock and change what villagers say (VARIANTS below).
"""
from data import NPCS

_ELDER = next(n for n in NPCS if n["id"] == "elder")

CHAPTERS = {
    1: "A Stranger in Hearthmoor",
    2: "Supplies for the Descent",
    3: "Into the Hollow",
    4: "The Deeper Dark",
    5: "The Warden of the Hollow",
    6: "Hearthmoor Reborn",
}

# ============================================================================================ QUESTS
QUESTS = [
    # ------------------------------------------------------------------------------------ MAIN STORY
    dict(id="m1", title="A Stranger in Hearthmoor", kind="main", chapter=1, giver="elder", turn_in="elder",
         requires=[],
         summary="Something stirs beneath the village. Hear out Sir Aldric on the north road.",
         offer=["Before you wander off, traveler, I must ask a favour of you. It is a grave one.",
                "Beneath the south road lies the Hollow Below, five floors of stone and shadow. For three hundred years it slept, and so did we.",
                "Lately the ground trembles at night. The rune on the gate glows red, and things with too many teeth have been seen near Gil's fields.",
                "Sir Aldric keeps the watch ledger on the north road. Hear what he has to say, then come back to me. Take this purse; Hearthmoor pays its debts before they are owed."],
         remind=["Sir Aldric holds the watch ledger, on the north road. Hear him out, then return to me."],
         thanks=["Aldric told you everything, then. Good. Then you know what I am about to ask of you.",
                 "The supply caravan rolled in this morning. Tobias has goods on his shelves again, so spend your purse wisely."],
         objectives=[dict(t="talk", npc="aldric", lines=[
             "So the Elder sent you. Good. Listen closely.",
             "My ledger says the tremors began on the night of the new moon. Every night since, the rune on the gate burns a little brighter.",
             "The Hollow was built to hold something. The old records call it the Warden: Grimhorn. A guardian, once. Now the seal that binds him is failing.",
             "Five floors, five rune-stones. Break the monsters on each floor and the stones quiet. Floor by floor, and not empty-handed.",
             "Tell the Elder I'll hold the road."])],
         on_accept=dict(gold=30),
         reward=dict(gold=40, flags=["caravan"])),

    dict(id="m2", title="Supplies for the Descent", kind="main", chapter=2, giver="elder", turn_in="elder",
         requires=["m1"],
         summary="Do not walk into the dark with bare hands. Buy supplies from the village shops.",
         offer=["Do not walk into the dark with bare hands, traveler.",
                "Potions at Tobias's store, steel at Bram's forge, tonics at Sage Wren's. Stand beside a shopkeeper and press T to trade.",
                "Crowns are earned from the monsters of the Hollow, from loot the shopkeepers will buy, and from helping the village. Spend them well."],
         remind=["Visit the shops, friend. Tobias, Pip, Bram, Wren and Rosalind all have something you will need. Press T beside them."],
         thanks=["Good. A traveler with full pockets is a traveler who comes back.",
                 "Now you are ready. Go down."],
         objectives=[dict(t="spend", n=30)],
         reward=dict(gold=30, items=dict(health_potion=2), flags=["supplied"])),

    dict(id="m3", title="Into the Hollow", kind="main", chapter=3, giver="elder", turn_in="elder",
         requires=["m2"],
         summary="Clear the Catacombs and the Drowned Halls: floors 1 and 2 of the Hollow Below.",
         offer=["The first two floors are the Catacombs and the Drowned Halls. Skeletons, wraiths, slime. Nothing you cannot handle.",
                "The stairs stay sealed until every monster on a floor is dead, so take your time. When you are hurt, the goddess statue behind the Whispering Shrine will heal you."],
         remind=["The south road ends at the gate. Floors one and two first, traveler. Rest at the goddess statue when you need to."],
         thanks=["Two floors quiet already! I can feel the ground settling beneath my feet.",
                 "The rune-stones are breaking the Warden's hold, one by one."],
         objectives=[dict(t="clear", floor=1), dict(t="clear", floor=2)],
         reward=dict(gold=100, flags=["hollow_1"])),

    dict(id="m4", title="The Deeper Dark", kind="main", chapter=4, giver="elder", turn_in="elder",
         requires=["m3"],
         summary="Fire on the third floor, ice on the fourth. Clear floors 3 and 4.",
         offer=["Below the flooded halls the Hollow turns truly hostile. Fire on the third floor, ice on the fourth.",
                "Sage Wren says the plants around the shrine have begun to lean toward the south road. She thinks the goddess herself is stirring.",
                "Stronger steel and stronger tonics will not go amiss."],
         remind=["Floors three and four, traveler. Mind the fire mages, and mind your potions."],
         thanks=["Four stones silent. Wren says the shrine plants are turning back north, as if the goddess breathes easier.",
                 "One floor remains, and the throne beneath it."],
         objectives=[dict(t="clear", floor=3), dict(t="clear", floor=4)],
         reward=dict(gold=150, items=dict(mana_potion=2), flags=["hollow_2"])),

    dict(id="m5", title="The Warden of the Hollow", kind="main", chapter=5, giver="elder", turn_in="elder",
         requires=["m4"],
         summary="Clear the fifth floor, pass the purple gate and defeat Grimhorn, Warden of the Hollow.",
         offer=["One floor remains, and the throne beneath it. Grimhorn guarded this valley before there was a village.",
                "The seal wore thin, and he has forgotten what he was set to guard. I do not hate him, but he must be stopped.",
                "Clear the fifth floor, then step up to the purple gate. Do what you must, and come home."],
         remind=["Grimhorn still sits upon his throne, deep in the Hollow Below. Clear the fifth floor and step to the purple gate."],
         thanks=["You... you've done it? The Hollow has gone quiet. I can feel it from here!",
                 "Grimhorn is no more, and the seal holds again. Hearthmoor owes you a debt we can never repay.",
                 "Please, take these. A blessing from the goddess, and a purse from our stores."],
         objectives=[dict(t="clear", floor=5), dict(t="boss")],
         reward=dict(gold=400, max_hp=20, max_mp=20, items=dict(health_potion=3, mana_potion=3),
                     flags=["hearthmoor_saved"])),

    dict(id="m6", title="Hearthmoor Reborn", kind="main", chapter=6, giver="elder", turn_in="elder",
         requires=["m5"],
         summary="The village wants a festival. Find Lark, who has been muttering about a ballad.",
         offer=["The village wants to celebrate. The Harvest Festival has been put off three seasons, and tonight it will not.",
                "But a festival needs a song, and the only singer we have is Lark. Find the bard and give them something to rhyme with."],
         remind=["Lark is somewhere near the plaza, muttering. Go and listen."],
         thanks=["Lark sang for an hour and nobody threw anything. That is a triumph.",
                 "Hearthmoor will remember you, traveler. Stay as long as you like. Or go and see the wider world, and bring back stories."],
         objectives=[dict(t="talk", npc="lark", lines=[
             "Is it you? The hero in the flesh! Sit. I have finally found the chorus.",
             "'In Hearthmoor's hollow a Warden lay deep, till a stranger came down and he woke from his sleep.'",
             "Hm. 'Deep' and 'sleep'. That's... that works, actually. Tell the Elder I'll sing it at the festival!"])],
         reward=dict(gold=100, flags=["festival"])),

    # ------------------------------------------------------------------------------------ SIDE QUESTS
    dict(id="s_welcome", title="The Welcome Round", kind="side", giver="elder", turn_in="elder",
         requires=["m1"],
         summary="Greet the villagers. Eight hellos will do.",
         offer=["One more thing. Small places run on goodwill, and a stranger who greets everyone is a friend for life.",
                "Say hello to the villagers: Rosalind, Tobias, Bram, Pip, Gil, Odell, Tilly, Aldric, Rook, Wren, Lark. Eight greetings will do."],
         remind=["Keep greeting the folk. Every hello counts."],
         thanks=list(_ELDER["all_met"]),
         objectives=[dict(t="meet", n=8)],
         reward=dict(gold=40, renown=1)),

    dict(id="s_iron", title="Iron for the Forge", kind="side", giver="bram", turn_in="bram",
         requires=["m2"],
         summary="Bram needs old catacomb bone to temper his finest steel.",
         offer=["Mind the sparks. Say, got a minute? Old catacomb bone is packed with iron, believe it or not.",
                "Bring me four bone shards from the skeletons and wraiths below, and I'll open up the forge's finer work for you."],
         remind=["Bone shards, friend. Four of them. The skeletons and wraiths in the Hollow carry them."],
         thanks=["That'll do nicely. Hear that? The forge sings different with proper bone-iron.",
                 "Second and third tier work is open now. Ask, and I'll deliver."],
         objectives=[dict(t="deliver", item="bone_shard", n=4)],
         reward=dict(gold=60, flags=["forge_open"], renown=1)),

    dict(id="s_remedies", title="Remedies for the Brave", kind="side", giver="wren", turn_in="wren",
         requires=["m2"],
         summary="Sage Wren needs ectoplasm for a stronger tonic.",
         offer=["Oh, dear, you are going into the Hollow. I have been wanting to brew something stronger, but I am missing one thing.",
                "Ectoplasm, the ghostly residue wraiths and some mages leave behind. Three portions, and I will unlock my finer recipes for you."],
         remind=["Three portions of ectoplasm, dear. Wraiths, dark mages and witches all leave it behind."],
         thanks=["Marvellous! It shimmers just like the old books said.",
                 "My finest tonics and focus-work are open to you now, and here's a little something for the road."],
         objectives=[dict(t="deliver", item="ectoplasm", n=3)],
         reward=dict(gold=60, items=dict(greater_mana=1), flags=["wren_brews"], renown=1)),

    dict(id="s_rot", title="The Rot in the Roots", kind="side", giver="gil", turn_in="gil",
         requires=["m2"],
         summary="Something is gnawing at Gil's crops from below. Thin the monsters on floors 1 and 2.",
         offer=["Afternoon, friend. Bad news. Something is gnawing at my carrots from underneath. I've found claw marks.",
                "If you thin the creatures out on the first two floors of the Hollow, I reckon my pumpkins will survive. Eight should do it."],
         remind=["Eight creatures from the first two floors of the Hollow, friend. My carrots thank you."],
         thanks=["My pumpkins haven't moved all week! They're thriving!",
                 "Take these, and a bit of coin. You've earned it."],
         objectives=[dict(t="kill", n=8, floors=(1, 2), label="monsters on floors 1-2")],
         reward=dict(gold=70, items=dict(health_potion=2), renown=1)),

    dict(id="s_road", title="Clear the South Road", kind="side", giver="aldric", turn_in="aldric",
         requires=["m1"],
         summary="Sir Aldric wants twelve of the Hollow's creatures cut down.",
         offer=["Traveler. The watch is stretched thin. Every creature you cut down is one less I must stand guard against.",
                "Slay twelve monsters in the Hollow Below and I'll see the village pays you for it."],
         remind=["Twelve monsters, traveler. Keep your guard up."],
         thanks=["Twelve! The ledger will look kind tonight.",
                 "The village is in your debt, and so, a little, is the watch."],
         objectives=[dict(t="kill", n=12, label="monsters in the Hollow Below")],
         reward=dict(gold=60, renown=1)),

    dict(id="s_trophy", title="The Hunter's Trophy", kind="side", giver="rook", turn_in="rook",
         requires=["m3"],
         summary="Rook wants proof that you can bring down the Hollow's great beasts.",
         offer=["...", "The big ones. Ogres, brutes, drakes, wyrms. I've watched them from the gate. Never gone in.",
                "Take down three of them. Then I'll know you're no tourist."],
         remind=["Three of the big ones. Ogres, brutes, drakes, wyrms. Don't die."],
         thanks=["...", "Three. Good. The forest will know your name.", "Take this. And a bit of coin."],
         objectives=[dict(t="kill", n=3, of="big", label="great beasts (ogres, brutes, drakes, wyrms)")],
         reward=dict(gold=140, items=dict(greater_health=1), renown=1)),

    dict(id="s_bait", title="Bait for Gerald", kind="side", giver="odell", turn_in="odell",
         requires=["m1"],
         summary="Old Odell needs bread to tempt a very stubborn carp.",
         offer=["Shh. Gerald the carp is circling. I need bait he can't resist.",
                "Pip's bread. Two loaves. Gerald has taste."],
         remind=["Two loaves of Pip's bread. Quietly, now."],
         thanks=["Ah, there. Gerald's circling. Patience... patience... Got him!",
                 "...And now I let him go. It's the principle of the thing. For your trouble."],
         objectives=[dict(t="deliver", item="bread", n=2)],
         reward=dict(gold=35, renown=1)),

    dict(id="s_map", title="Tilly's Treasure Map", kind="side", giver="tilly", turn_in="tilly",
         requires=["m1"],
         summary="Tilly has a map to a hidden treasure. It marks four places to visit.",
         offer=["Psst. I have a TREASURE MAP. It's not exactly a map. It's a drawing of a goat. But it points to four places!",
                "Reedwater Pond, the Hunter's Camp, Moonlake and Gil's Farm. Go there, then come back and we'll find the treasure!"],
         remind=["The pond, the Hunter's Camp, Moonlake and Gil's Farm! I'm very patient. (I'm not.)"],
         thanks=["You went to ALL of them? Okay okay okay. The treasure is... it's... a piggy bank. Mine. It has coins.",
                 "I'm sharing! Because you're my friend. Don't tell Mama."],
         objectives=[dict(t="visit", place="Reedwater Pond"), dict(t="visit", place="Hunter's Camp"),
                     dict(t="visit", place="Moonlake"), dict(t="visit", place="Gil's Farm")],
         reward=dict(gold=45, renown=1)),

    dict(id="s_tab", title="Settle Lark's Tab", kind="side", giver="rosalind", turn_in="rosalind",
         requires=["m1"],
         summary="Lark has been 'resting his voice' in Rosalind's loft all week. Pay the bard's tab.",
         offer=["Welcome back. Can I trouble you? The bard in my loft has run up a tab as long as his songs.",
                "Forty Crowns clears it. Settle it for him and I'll never forget it. Maybe I'll even give you a discount on beds."],
         remind=["Forty Crowns, dear. The tab is long and the stew was good."],
         thanks=["Paid in full! Lark will never know. Well, he'll know. But he won't complain.",
                 "From now on, a bed at my inn costs you half. Welcome to the family."],
         objectives=[dict(t="pay", n=40)],
         reward=dict(flags=["inn_friend"], renown=1)),

    dict(id="s_verses", title="Verses from the Deep", kind="side", giver="lark", turn_in="lark",
         requires=["m2"],
         summary="Lark wants a firsthand account of the Hollow. Reach the third floor.",
         offer=["Friend! I'm stuck. A ballad needs a setting, and I have only a loft and a lute.",
                "Go down to the third floor of the Hollow and tell me what the dark sounds like. I'll pay for the verses."],
         remind=["The third floor, friend. Tell me how the dark sounds."],
         thanks=["A drip, a whisper, and a distant roar? Perfect! I can use that!",
                 "Here, a few coins for the inspiration."],
         objectives=[dict(t="reach", floor=3)],
         reward=dict(gold=70, flags=["lark_inspired"], renown=1)),

    dict(id="s_flint", title="Lantern Flint", kind="side", giver="tobias", turn_in="tobias",
         requires=["m2"],
         summary="Tobias needs flint-grade stone chips to restock his lanterns.",
         offer=["Between us, the shelves are fuller but the lanterns are failing. They need flint, and flint means stone chips.",
                "Gargoyles and the big brutes shed them. Three stone chips, and I'll stock the good potions."],
         remind=["Three stone chips from the Hollow's gargoyles and big beasts. I'll make it worth your while."],
         thanks=["Flint! Real flint! You are a marvel.",
                 "As promised: Greater potions are on my shelves. And a bit of coin besides."],
         objectives=[dict(t="deliver", item="stone_chip", n=3)],
         reward=dict(gold=80, flags=["tobias_stock"], renown=1)),
]

# ============================================================================================ REACTIONS
# What each villager says as the story moves on.  For every (flag, overrides) pair whose flag is set,
# the overrides replace that villager's `intro` / `chatter` from data.py.  Later entries win.
VARIANTS = {
    "elder": [
        ("hollow_1", dict(chatter=[["Two floors silent. I slept through the night for the first time in weeks."],
                                   ["Every stone you break, the village breathes a little easier."]])),
        ("hearthmoor_saved", dict(chatter=[["The gate rune has gone dark and cold. Hearthmoor is safe because of you."],
                                           ["There is a chair by my fire with your name on it. It is yours whenever you wish."],
                                           ["Three hundred years, and the next three hundred will remember you."]])),
    ],
    "rosalind": [
        ("caravan", dict(chatter=[["The caravan brought flour, salt and a barrel of pickled onions. Tobias bought the onions himself. Nobody knows why."],
                                  ["Stew or a bed, traveler. Press T beside me and take your pick."]])),
        ("hearthmoor_saved", dict(chatter=[["Free stew for the hero! ...Alright, half price. I'm a businesswoman."],
                                           ["Lark's finally moved out of my loft. I almost miss the off-key humming."]])),
    ],
    "tobias": [
        ("caravan", dict(intro=["Step right up! The caravan finally came! Rope, lanterns, honey, potions, and one slightly haunted teapot.",
                                "Press T beside me to trade. Sell me anything the Hollow gives you, too. I'm not picky."],
                         chatter=[["Business is booming. Everyone wants potions now. It turns out monsters are good for sales."],
                                  ["I'll buy your loot, and I won't ask what it was before it was loot."]])),
        ("tobias_stock", dict(chatter=[["Greater potions on the shelf, thanks to you. Stronger medicine for a stronger traveler."]])),
        ("hearthmoor_saved", dict(chatter=[["I'm putting 'As used by the Hero of Hearthmoor' on the label. Don't sue."]])),
    ],
    "bram": [
        ("forge_open", dict(chatter=[["The forge burns hot with proper bone-iron. Ask about the finer work."],
                                     ["Tilly rang my anvil again. I let her. It makes a good sound."]])),
        ("hearthmoor_saved", dict(chatter=[["I swung a hammer sixty years and never thought a sword would keep a village safe. You proved me wrong."]])),
    ],
    "pip": [
        ("caravan", dict(intro=["Fresh bread! Hot out of the oven! The caravan brought flour, so I baked at dawn. Press T to buy a loaf.",
                                "Try a honey bun, too. Don't tell Rosalind they're better than her stew."],
                         chatter=[["Flour! Sacks of it! I'm baking until sunrise."]])),
        ("hearthmoor_saved", dict(chatter=[["I'm baking a cake the size of a cottage for the festival. Mostly butter."]])),
    ],
    "gil": [
        ("hollow_1", dict(chatter=[["The ground's stopped shaking. The carrots can tell. They're sitting up straighter."]])),
        ("hearthmoor_saved", dict(chatter=[["Best harvest in three hundred years, and the weeds are the only ones complaining."]])),
    ],
    "odell": [
        ("hollow_1", dict(chatter=[["Gerald's been calmer lately. The whole pond has. Funny how the water listens."]])),
        ("hearthmoor_saved", dict(chatter=[["Gerald and I watched fireflies over the pond last night. Peace at last."]])),
    ],
    "tilly": [
        ("hollow_1", dict(chatter=[["Mama says you're going into the BIG hole. Can I come? ...No? Fine."]])),
        ("hearthmoor_saved", dict(chatter=[["You're a HERO! I told everyone I knew you first. That's lying, a bit, but still."]])),
    ],
    "aldric": [
        ("hollow_1", dict(chatter=[["The gate rune's gone from red to amber. Keep it up, traveler."]])),
        ("hearthmoor_saved", dict(chatter=[["I wrote it in the ledger: 'Hollow quiet. Hero returned.' Best entry I've ever made."]])),
    ],
    "rook": [
        ("hollow_1", dict(chatter=[["The deer have come back to the lake. Something is quieter in the earth."]])),
        ("hearthmoor_saved", dict(chatter=[["...", "The forest knows your name now."]])),
    ],
    "wren": [
        ("caravan", dict(chatter=[["The caravan brought me two new herbs and one very rude lizard. Press T if you need tonics, dear."]])),
        ("hollow_2", dict(chatter=[["The shrine plants have turned back toward the north. The goddess settles."]])),
        ("hearthmoor_saved", dict(chatter=[["The foxglove is blooming out of season. Everything is, since you came back."]])),
    ],
    "lark": [
        ("lark_inspired", dict(chatter=[["Verse two is shaping up nicely. Mostly because of what you told me about the dark."]])),
        ("hearthmoor_saved", dict(chatter=[["The chorus finally rhymes. Don't ask how long it took."],
                                           ["I'll be singing about you at the festival. Every verse. Brace yourself."]])),
    ],
}


def default_lines(npc, flags, first):
    """The villager's everyday talk: intro on the first meeting, then rotating chatter, shaped by story flags."""
    d = dict(intro=npc.d["intro"], chatter=npc.d["chatter"])
    for flag, over in VARIANTS.get(npc.id, []):
        if flag in flags:
            d.update(over)
    if first:
        return list(d["intro"])
    ch = d["chatter"]
    return list(ch[(npc.talk_count - 1) % len(ch)])
