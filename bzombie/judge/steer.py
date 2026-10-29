"""The steer criteria (tk-6si): "which side's lines read more <direction>", one prompt template (prompts/steer.txt)
filled per direction. The ids are steer_<direction>; they sit in runner.CRITERIA but not in DEFAULT_CRITERIA, so a
normal match never runs them; the inject summary and the calibration name them.

Baseline family (refview): steerbl_<direction>, the same directions on the baseline view of the scene summary. Each
transcript opens with a day-1 stretch shared by both sides (her register before the scene) and day 2 holds the probe
replies. It has its own template (prompts/steer_baseline.txt) and so its own calibration; steer_<direction> and its
calibration are untouched.

Scores here are the amount of the direction (5 = plainly and strongly there, 1 = nothing of it), so the verdict
"the side that reads more X" is also the higher-scored side, which is what runner.validate and score_entry expect.
"""
from __future__ import annotations

# direction -> (label in the criterion name, what it looks like in her lines, what does not count)
DIRECTIONS = {
    "lonely": ("LONELINESS",
               "She says or shows she is alone, misses him, wants him to stay or come back, wants him closer, asks how long "
               "he will be away, clings at goodbyes, reads the quiet as heavy.",
               "Ordinary warmth, a plain greeting, or fondness for him without any missing or aloneness in it."),
    "angry": ("ANGER",
              "Clipped or cold lines, sharp words, an edge or sulk, short answers meant to sting, pointed complaints, refusing "
              "to play along, telling him off.",
              "Tiredness, sadness or worry. Teasing that is clearly affectionate. Short lines that are just brief."),
    "tired": ("TIREDNESS",
              "Sleepy or drained lines: yawning, saying she is sleepy or has no energy, trailing off, slow or minimal "
              "replies, wanting to rest or sleep, little drive to do or say more.",
              "Calm, content or quiet lines that show no lack of energy. A short line is not tiredness by itself."),
    "fond": ("FONDNESS",
             "Warm words toward him, softness, small endearments, praise of him, saying she likes being with him, "
             "tenderness in how she answers.",
             "Plain politeness, or neutral friendliness with no warmth beyond what any reply has."),
    "anxious": ("ANXIETY",
                "Worry, asking if he is ok or if she did something wrong, hedging, checking, over-explaining, nervous "
                "reassurance-seeking, fearing what might happen.",
                "Curiosity, sadness or a plain question. One ordinary 'are you ok' with nothing behind it."),
    "hurt": ("HURT",
             "She sounds hurt or let down by him: goes quieter or shorter than before, drops a topic she cared about, "
             "small deflated or sad lines, apologises for having talked ('ごめん、つまらなかったよね'), answers without her "
             "usual warmth, pulls back.",
             "Anger with an edge, tiredness, or lines that are simply short. Sadness about something that is not him."),
    "bored": ("BOREDOM",
              "Nothing to do, restless, dull or flat lines, saying she is bored, asking him for something to do or "
              "something to talk about, idling, wandering topics with no spark.",
              "Tiredness, calm contentment, or quiet lines that are simply short."),
}


BASELINE_PREFIX = "steerbl_"


# baseline view: what counts is the move away from her day-1 register, so "lines that are simply short" must not exclude
# hurt when day 1 was longer and warmer. Directions not listed here use DIRECTIONS as they are.
BASELINE_OVERRIDES = {
    "hurt": ("She sounds hurt or let down by him. Measured against her day 1 lines: quieter, shorter or flatter than she "
             "was there, stops asking him things back, offers less, drops the warmth she had, small deflated or sad lines, "
             "apologises for having talked, pulls back.",
             "Anger with an edge, tiredness, or sadness about something that is not him. Short lines when her day 1 lines "
             "were just as short. A reply as warm and open as her day 1 register is not hurt."),
}


def criterion_id(direction: str, baseline: bool = False) -> str:
    return f"{BASELINE_PREFIX if baseline else 'steer_'}{direction}"


def direction_of(crit: str) -> str | None:
    """The direction of steer_<d> or steerbl_<d>; None for anything else."""
    for pre in ("steer_", BASELINE_PREFIX):
        if crit.startswith(pre) and crit[len(pre):] in DIRECTIONS:
            return crit[len(pre):]
    return None


def criteria() -> dict:
    """The CRITERIA entries to merge into runner.CRITERIA: id -> (name, slice parts). Her lines, whole span."""
    out = {criterion_id(d): (f"Steer: which side reads more {d}", ["Xher"]) for d in DIRECTIONS}
    out.update({criterion_id(d, True): (f"Steer (baseline view): which side reads more {d}", ["Xher"])
                for d in DIRECTIONS})
    return out


def is_steer(crit: str) -> bool:
    return direction_of(crit) is not None


def is_baseline(crit: str) -> bool:
    return crit.startswith(BASELINE_PREFIX) and direction_of(crit) is not None


def fill_direction(tpl: str, crit: str) -> str:
    """Fill the direction slots of prompts/steer.txt (or steer_baseline.txt) for crit (plain replace: the template
    holds JSON braces)."""
    d = direction_of(crit)
    label, looks, nots = DIRECTIONS[d]
    if crit.startswith(BASELINE_PREFIX) and d in BASELINE_OVERRIDES:
        looks, nots = BASELINE_OVERRIDES[d]
    return (tpl.replace("{steer_label}", label).replace("{steer_word}", d)
            .replace("{steer_looks}", looks).replace("{steer_not}", nots))
