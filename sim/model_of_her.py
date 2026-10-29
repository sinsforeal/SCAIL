import logger
from sim.model_of_him import ModelOfHim

# What she has decided about herself.
#
# The same object and the same machine as her picture of him, pointed inward.
# `self_claims` are things she has told him and must stay consistent with, and
# `self_memories` are things that happened to her; neither of them can be
# wrong. This is the third thing: propositions she is using to know what she
# is, which the days can disagree with.
#
# The seeds are in data/self_beliefs.json and every one of them is derived from
# her own sheet. Their `evidence` is high where she watches herself do it every
# day (she reads the air, the mask has never yet failed) and low where she has
# never actually tested it -- "if the act slipped they would work out what you
# are" is what most of her life is arranged around, and she has 8 out of 100 to
# go on. That is the one worth watching.
#
# What strains these is not a discovery about him, it is a day that did not go
# her way (sim/goals.py). A goal anchors to one of these, and failing charges
# it: what she keeps carrying and what she quietly stops wanting comes out of
# how much is riding on the thing the goal was holding up. Nothing anywhere
# says she is stubborn.


class ModelOfHer(ModelOfHim):
    KEY = "self_beliefs"
    SEED_ATTR = "self_beliefs_file"
    LOG = "self"
    REVISE_ROLE = "revise_self"
    WHAT = "what she has decided about herself"
    REVISE_HEADER = "WHAT SHE HAS BELIEVED ABOUT HERSELF"
    # there is no history of hers to settle against: the seeds already say what
    # four months in Tokyo have made of her, which is what the file is for
    SETTLE_ON_SEED = False
    BRIEF_SETTLED = " [not in question for her; only something she cannot argue with touches it]"
    BRIEF_EMPTY = "- (she has decided nothing about herself yet)"
    # she is not reconsidering it, she is holding it together
    PROMPT_STRAINED = (" (lately the days have not been agreeing with this and you have been finding reasons; you have not let go of it)",
                       "（最近の毎日がこれと噛み合わなくて、あなたはそのたびに理由を見つけている。手放してはいない）")
    PROMPT_REVISED = (" (you used to think this about yourself more simply than you do now)",
                      "（自分についてこれを、前はいまよりも単純に思っていた）")
    PROMPT_HEAD = ("## What you have decided about yourself (never said out loud, most of it never tested, "
                   "and you would rather not have it read back to you)",
                   "## 自分について自分で決めたこと（口に出したことはなく、ほとんど確かめてもいない。"
                   "読み上げられるのは、あまり嬉しくない）")

    def _graduate(self, b, rows):
        """Past arguing with. It does not become a `user_fact` -- that store is
        things she knows about him -- it stays here marked known, which is what
        stops it soaking up further confirmations while leaving it breakable.
        A thing about yourself you have stopped questioning is still a thing
        that can be taken off you in an afternoon."""
        b["state"] = "known"
        b["known_on"] = self.clock.date_str()
        self.save(rows)
        self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "belief",
                             f"(she would not say it like this) she has stopped treating this as a question about herself: {b['text']}",
                             self.config.beliefs.event_salience)
        logger.log(f"[{self.LOG}] {b['id']} is not in question any more: {b['text'][:70]}")

    def _revised_event(self, b, row):
        return (f"(she would not put it this way) she does not think this about herself any more: "
                f"{b['text']}. {row['text']}")

    def anchor_brief(self):
        """For the morning call: what a want could be riding on, with how much
        rests on each. The same shape as the kinds list in the ick call, and for
        the same reason -- the model is shown the ids and copies one back, because
        word overlap cannot tell that "get through the festival without anyone
        looking at me" is holding up "being on your own is embarrassing"."""
        out = []
        for b in self.beliefs():
            if b.get("state") == "let_go":
                continue
            out.append(f"- {b['id']}: {b['text']} (she has {b.get('invested', 50)} of 100 riding on this)")
        return "\n".join(out) or "- (nothing)"

