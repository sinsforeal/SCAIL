"""Which set of instructions a character is addressed in, as an arm that can
be swapped and compared rather than a decision baked into the code.

Every wording lives in the source twice, side by side, and `character.
instructions` picks which one is rendered. Named the way the prompt sets are
named, because they are the same kind of thing -- approaches to be compared,
not a migration with a winner already chosen:

  as_they_run_today   The control, and the default. What her prompt is TODAY,
                      preserved byte for byte: English scaffolding and section
                      headers around Japanese identity sections, with finished
                      Japanese prose injected mid-block by other roles. It is
                      not "the English version" of anything -- it is a
                      mixture -- and its whole value is that every measurement
                      taken so far was taken under it. Nothing in here tidies
                      it. Where a tidier way of deciding something would change
                      one rendered byte, this arm keeps the untidy way and says
                      why at the call site.
  in_english          A clean, consistent English-instruction arm. TODAY IT
                      RENDERS THE SAME BYTES AS `as_they_run_today`: the
                      scaffolding was already English, and nothing was invented
                      to fill the slot. It exists as a name a bench result can
                      carry, and as the place a genuinely tidied English arm
                      would go if anyone builds one.
  in_her_language     The instructions in the language the character lives in.
                      Japanese, for the second character.

`character.instructions` may also say `auto`, which is the default and is
what an unset value means: her own language when she declares one this
switch can render, and the control when she does not. A character who says
she lives in Japanese is instructed in Japanese without anybody switching
her on, and the boot line and `/lang` both name the arm and where it came
from, so which one is in force is never invisible.

**It is a variable to be benched.** The arms must differ in the instructions
and in nothing else, so `set_override` flips it inside one process
(`tools/voicelab.py --instructions`) and the environment variable
`SCAIL_INSTRUCTIONS` flips it for a whole run -- neither touching a config file
and neither needing a restart.

**And it is a switch he throws.** `/lang ja|en|auto` writes kv
`instructions_override` on her save and sets it here; the boot reads that kv
back, so the arm moves between two replies and survives a restart without a
config edit, and `auto` forgets it and lets her config decide again. Which
language `in_her_language` renders is hers to declare
(`character.instruction_language`): a character whose instructions are
English has no second arm and the command says so. How far the arm reaches
beyond her own prompt -- the roles that write the material she reads -- is
the `language` section and `material_line` below.

What is covered is decided by AUDIENCE, not by file. A line she is meant to
read as herself is in her instruction language: her situation block, the
section headers above it, the closing instruction that says what to write and
how. What the machine says to itself has no audience and stays English: the
state role is gauge arithmetic with nobody being spoken to, a JSON field name
is a key, a log line is for a developer.

**Every translated string goes behind this switch.** The first character is on
`as_they_run_today` and shares every line of the code these strings live in, so
a Japanese line that is not selected here would reach her too.

    from sim.lang import say
    t = say(config)
    t("today so far: ", "今日ここまで: ")
"""

import os

# Set for the length of a process, above the config and below nothing. `None`
# means "whatever the character's config says".
_OVERRIDE = [None]

# The arm he asked for in the chat (`/lang`, kv `instructions_override` on her
# save), read at boot and set again by the command, so the next prompt is
# built in the arm he just chose and the choice survives a restart. Below the
# process override and below the environment on purpose: a harness has to be
# able to hold an arm still while it builds both, and a launcher that names an
# arm for a whole run is naming it for every call in that run.
_SAVED = [None]

TODAY, ENGLISH, HERS = "as_they_run_today", "in_english", "in_her_language"
ARMS = (TODAY, ENGLISH, HERS)

# Not an arm: what a config says when it wants the arm decided from what
# the character declares she lives in. `arm()` resolves it, and an unset
# value means the same thing.
AUTO = "auto"

# What an older or shorter spelling means. `japanese` and `english` are what a
# person types at a command line; the arm names are what a result carries.
_ALIASES = {"japanese": HERS, "ja": HERS, "hers": HERS, "her": HERS,
            "english": ENGLISH, "en": ENGLISH,
            "current": TODAY, "today": TODAY}


def _norm(value):
    v = str(value or "").strip().lower()
    return v if v in ARMS else _ALIASES.get(v, "")


def named(value):
    """The arm a person typed, or "" for a word that names none. Public
    because the ops command has to be able to say "that is not an arm"
    before it writes anything to her save."""
    return _norm(value)


def set_override(value):
    """Force an arm for this process, or clear it with None.

    For a harness that builds the same character's prompt both ways in one run:
    the arms must differ in the instructions and in nothing else, and a config
    edit between them would put the file's mtime and whatever else was saved
    with it into the comparison."""
    _OVERRIDE[0] = _norm(value) or None
    return _OVERRIDE[0]


def override():
    return _OVERRIDE[0]


def set_saved(value):
    """The arm saved on her save, or None to forget it. `App` reads kv
    `instructions_override` at boot and `/lang` writes it and calls this, so
    which arm is in force is one question with one answer rather than a kv
    that some call sites remember to read."""
    _SAVED[0] = _norm(value) or None
    return _SAVED[0]


def saved():
    return _SAVED[0]


def arm(config=None):
    """Which arm is being rendered: the process override, else the
    environment, else the arm saved by `/lang`, else her config.

    A config that says `auto`, or says nothing, is decided from what she
    declares she lives in: her own language when this switch has a second
    one to render for her, and the control when it has not. A character who
    says she lives in Japanese should not have to be switched on by hand,
    and three of the four were not."""
    named_arm = (_OVERRIDE[0]
                 or _norm(os.environ.get("SCAIL_INSTRUCTIONS"))
                 or _SAVED[0]
                 or _norm(getattr(getattr(config, "character", None), "instructions", "")))
    if named_arm:
        return named_arm
    return HERS if switchable(config) else TODAY


def source(config=None):
    """Where the arm in force came from, for a status line. A switch whose
    provenance cannot be seen is one that gets flipped twice."""
    if _OVERRIDE[0]:
        return "set for this process"
    if _norm(os.environ.get("SCAIL_INSTRUCTIONS")):
        return "SCAIL_INSTRUCTIONS, for this run"
    if _SAVED[0]:
        return "/lang, saved on her save"
    if _norm(getattr(getattr(config, "character", None), "instructions", "")):
        return "her config"
    said = str(getattr(getattr(config, "character", None), "instructions", "") or "").strip().lower()
    return (f"her config says {said or '(nothing)'}, and she lives in "
            f"{instruction_language(config)}")


def instruction_language(config=None):
    """Which language `in_her_language` renders for THIS character.

    Off her config (`character.instruction_language`), and never inferred
    from `writes_to_him`: the first character is bilingual, her chat with him
    is the one room her English lives in, and every measurement taken on her
    was taken with her instructions in English. So hers is English,
    `in_her_language` renders the same bytes as `in_english` for her, and the
    ops command has something true to say instead of switching her."""
    v = str(getattr(getattr(config, "character", None), "instruction_language", "") or "").strip().lower()
    return v or "english"


def switchable(config=None):
    """Is there another language to switch this character into?

    Every wording behind the switch lives in the source as an English and
    Japanese pair -- `say()` here, the gauge and feeling glosses below, the
    words tables each program registers -- so "her language" can be Japanese
    and nothing else today. A character whose instruction language is English
    is not half covered; she has no second arm at all."""
    return instruction_language(config).startswith("ja")


def language_name(config=None):
    """Her instruction language the way a role prompt should name it."""
    v = instruction_language(config)
    return {"ja": "Japanese", "japanese": "Japanese",
            "en": "English", "english": "English"}.get(v, v.capitalize())


def reads_ja(config=None):
    """Is this character being instructed in her own language right now?

    Both halves of the question: the arm has to be `in_her_language` AND her
    instruction language has to be one this switch can render. Without the
    second half, setting the arm on a character whose instructions are
    English rendered Japanese at her."""
    return arm(config) == HERS and switchable(config)


def material_line(config, role):
    """The one line a role that writes WHAT SHE READS is given while she is
    being instructed in her own language, or "".

    The arm covers everything the prompt builder writes: her section
    headers, her situation block, the closing instruction. It cannot cover
    the SENTENCES under those headers, because other roles wrote those --
    the facts about him, the notes she read, what she has decided about
    herself, what she thinks of him. Flipping the arm and nothing else
    leaves her reading her own language over English prose, which is what
    the coverage audit found (`data/retired/20260904_lang_switch/REPORT.md`).

    So the roles named in `language.material_roles` are told, in one line,
    which language their prose goes out in. The line is addressed to a
    mechanism and stays English: nobody is being spoken to in it. Nothing
    already in the record is touched -- a fact written in English stays as it
    was written and ages out through the forgetting curve like any other."""
    if not reads_ja(config):
        return ""
    lc = getattr(config, "language", None)
    if not (lc is not None and getattr(lc, "enabled", True)):
        return ""
    if role not in set(getattr(lc, "material_roles", ()) or ()):
        return ""
    return (
        "\n\nLANGUAGE OF WHAT YOU WRITE HERE: she reads it inside her own prompt, so every "
        f"sentence of prose you write goes out in {language_name(config)}, the asides in "
        "brackets included. What is not prose does not move: field names, keys, tags, and any "
        "value this prompt lists as a fixed choice stay exactly as spelled here, because code "
        "reads those and cannot find a translated one. Anything you quote from the record is "
        "quoted as it was written, never translated.")


def status(config=None):
    """One line for a boot log and a status command: the arm, where it came
    from, her instruction language, and how far the arm reaches."""
    out = (f"instructions: {arm(config)} ({source(config)})"
           f" | her instruction language: {instruction_language(config)}")
    if not switchable(config):
        return out + " -- there is no other arm to switch her to"
    lc = getattr(config, "language", None)
    roles = sorted(set(getattr(lc, "material_roles", ()) or ())) if lc is not None else []
    on = lc is not None and getattr(lc, "enabled", True)
    if reads_ja(config):
        if on and roles:
            return out + f" | {len(roles)} role(s) told to write her material in {language_name(config)}"
        return out + " | the material roles are told nothing (language.enabled is off)"
    return out + f" | /lang ja moves it, and {len(roles)} material role(s) with it"


def control(config=None):
    """Is this the frozen control -- the prompt exactly as it renders today?

    Read at the two places where deciding something a tidier way would change
    a rendered byte. The control keeps the untidy way; every other arm gets the
    tidy one."""
    return arm(config) == TODAY


def say(config=None):
    """`t(english, japanese)` -- the one wording this character is addressed in.

    A call rather than a lookup table so the two wordings sit side by side in
    the source: a translation nobody can see next to its original is one that
    drifts the first time either is edited."""
    return pick(reads_ja(config))


def pick(ja):
    """`t(english, japanese)` for a caller that already knows which language
    the line is going out in. Ten modules wrote this closure by hand."""
    def t(en, jp):
        return jp if ja else en

    return t


# A gauge's name where SHE reads it. Only the ones that reach a line she is
# addressed in -- the state role keeps the keys, because the keys are what it
# writes back and a translated key is a key the code cannot find.
GAUGE_JA = {
    "anger": "怒り",
    "sadness": "悲しさ",
    "shame": "恥ずかしさ",
    "guilt": "うしろめたさ",
    "pride": "誇らしさ",
    "longing": "会いたさ",
    "belonging": "居場所のなさ",
    "stress": "しんどさ",
    "relief": "安心",
    "unwell": "体調",
    "fatigue": "疲れ",
    "affection": "好き",
    "awkwardness": "きまずさ",
    "surprise": "驚き",
    "anxiety": "不安",
    "loneliness": "さみしさ",
    "boredom": "退屈",
    "validation_craving": "かまってほしさ",
    "energy": "元気",
    "curiosity": "気になる度",
    "jealousy": "やきもち",
    "unsaid": "言えていないこと",
    "physical_comfort": "体の楽さ",
    "mood": "機嫌",
}


def gauge_ja(key):
    """Her word for a gauge, or the key when nothing has been written for it --
    a missing gloss shows as the key rather than as a hole."""
    return GAUGE_JA.get(str(key), str(key))


# The feeling wordings a gauge spec and a blend carry (`state.gauges[k].tags`,
# `state.blends[].text`), said in her language.
#
# They live here rather than in the config because a config holds ONE wording
# per feeling and this has to hold two: the English is the other arm of the
# comparison and cannot be overwritten by it. Keyed on the English, so a
# character whose config words a feeling differently keeps her own wording
# rather than being handed somebody else's -- visible in the prompt, and not a
# crash.
FEELING_JA = {
    "angry about something, and holding it in": "何かに腹を立てていて、それを抑えている",
    "irritated under it": "その下でいらいらしている",
    "sad in a way that has gone quiet rather than loud": "悲しさが、声になるほうではなく静かなほうに出ている",
    "a bit down and not saying why": "少し落ちていて、理由は言っていない",
    "mortified about something and wants to not be looked at": "何かが恥ずかしくて、見られたくない",
    "small about something": "何かのことで自分が小さく感じている",
    "quietly pleased about it and would die before saying so": "内心それが嬉しいが、口に出すくらいなら死ぬ",
    "missing him in a way that is taking up room": "彼に会いたい気持ちが、場所を取るくらいある",
    "missing him": "彼に会いたい",
    "solid with the group at the moment": "いまはその輪の中にちゃんといる感じがある",
    "on the outside of them lately, and it is sitting there": "最近その輪の外側にいて、それがずっと居座っている",
    "wound up, running on nothing, everything is a bit much": "張り詰めていて、何もないところで動いていて、いろいろが少し多い",
    "carrying more than is showing": "見えている以上のものを抱えている",
    "relieved, like something braced for did not happen": "身構えていたことが起きなくて、ほっとしている",
    "physically rotten, wants to lie down": "体がひどくて、横になりたい",
    "a bit off physically": "体が少し不調",
    "properly exhausted; the phone is heavy and the replies come out short and misspelt":
        "本格的に疲れきっている。携帯が重くて、返事は短く、打ち間違いが増える",
    "legs heavy from the day, wiped, would rather lie down than type":
        "一日で足が重く、へとへとで、打つより横になりたい",
    "feeling warm and close to him, wants to reach out": "彼にあたたかく近い感じがしていて、こちらから触れたい",
    "soft toward him right now": "いま彼に対してやわらかい",
    "gone off him: cool, short, not interested in being close right now":
        "彼に冷めている。冷たく、短く、いまは近づく気がない",
    "cannot stand him at the moment; everything he says grates, and it is not hidden":
        "いま彼が我慢ならない。何を言われても引っかかるし、それが隠せていない",
    "squirming about something that is not going to be brought up": "持ち出すつもりのない何かのことで、居心地が悪い",
    "caught off guard by something and still recalibrating; a beat of 'wait' before anything else":
        "何かに不意を突かれて、まだ立て直している最中。何を言うより先に「え、待って」が一拍入る",
    # the blends: two feelings up at once that do not cancel
    "wanting him and furious with him at the same time, and neither cancels the other":
        "彼を求めているのと彼に腹を立てているのが同時にあって、どちらも消えない",
    "fond of him and angry with him at once; it comes out as sharpness she then half takes back":
        "彼を好きなのと怒っているのが同時にある。とげとして出て、そのあと半分だけ引っ込める",
    "bittersweet: the thing is over, she is glad, and it still hurts":
        "ほろ苦い。終わったことが嬉しくもあり、それでもまだ痛い",
    "proud of a thing and embarrassed about the same thing": "同じことを誇らしく思いながら、同じことが恥ずかしい",
    "jealous, and ashamed of being jealous": "やきもちを焼いていて、焼いている自分が恥ずかしい",
    "wants to know and is afraid of the answer": "知りたいのに、答えが怖い",
    "surrounded and still lonely: the people there are not the person missing":
        "人に囲まれていてもさみしい。そこにいる人たちは、いない人ではない",
}


def feeling_ja(text):
    """Her wording for a feeling the config states in English, or the config's
    own words when nothing has been written for it."""
    return FEELING_JA.get(str(text).strip(), str(text))
