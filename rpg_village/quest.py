"""The main quest: Elder Maren asks you to defeat Grimhorn, Warden of the Hollow.

States:  unknown -> active (talk to Elder Maren) -> ready (Grimhorn is dead) -> done (report back, get the reward)
Dialogue and rewards are edited here; main.py wires the Elder's conversation and the HUD tracker."""

TITLE = "The Warden of the Hollow"

OFFER = [
    "Before you go wandering off, traveler... I must ask something of you. It is grave.",
    "Beneath the south road lies the Hollow Below, five floors of stone and shadow. A creature called Grimhorn, the Warden, sits on a throne at its very bottom.",
    "Since he woke, the Hollow has been spilling its monsters closer to our fields every season. Someone must end it.",
    "QUEST: Descend into the Hollow Below, clear the floors, and defeat Grimhorn. Rest at the goddess statue by the gate whenever you are hurt.",
]
REMINDER = [
    "Grimhorn still sits upon his throne, deep in the Hollow Below. The south road ends at the gate.",
    "Clear all five floors, then step to the purple gate on the last one. Rest at the goddess statue if you need strength.",
]
THANKS = [
    "You... you've done it? The Hollow has gone quiet. I can feel it from here!",
    "Grimhorn is no more. Hearthmoor owes you a debt we can never repay.",
    "Please, take these. A blessing from the goddess, and a few potions from our stores.",
    "REWARD: +20 max HP, +20 max MP, 3 Health Potions and 3 Mana Potions.",
]

REWARD = dict(max_hp=20, max_mp=20, health_potion=3, mana_potion=3)


HUD_SECONDS = 10.0          # how long the on-screen quest panel stays after the quest changes


class Quest:
    def __init__(self):
        self.state = "unknown"
        self.hud_t = 0.0        # seconds left for the on-screen quest panel

    def show_hud(self):
        self.hud_t = HUD_SECONDS

    def update(self, game, dt=0.0):
        """Grimhorn falls -> the quest becomes ready to turn in. Also ticks the HUD timer."""
        self.hud_t = max(0.0, self.hud_t - dt)
        if self.state == "active" and game.combat.boss_defeated:
            self.state = "ready"
            self.show_hud()
            game.toast("Quest updated: return to Elder Maren", 5.0)

    def hud_tracker(self):
        """What the on-screen panel shows: the 'talk to the Elder' goal until you do, then
        each update for 10 seconds only. The inventory (key I) always shows the full quest line."""
        if self.state == "unknown" or self.hud_t > 0:
            return self.tracker()
        return None

    def tracker(self):
        """(title, objective) for the HUD, or None while the quest is not running."""
        if self.state == "active":
            return TITLE, "Defeat Grimhorn in the Hollow Below (floor 5, beyond the purple gate)."
        if self.state == "ready":
            return TITLE, "Grimhorn is defeated! Return to Elder Maren in the village."
        if self.state == "done":
            return TITLE, "Complete! Grimhorn is defeated and Hearthmoor is safe again."
        return "Welcome to Hearthmoor", "Talk to Elder Maren in the village plaza."
