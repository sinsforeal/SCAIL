"""Her own config, beside his, touching nothing of Tomoe's.

The bot already supports this: `scail.py --config X --db Y`, and the singleton
lock is keyed to the database path rather than being global, so a second bot
sits beside the live one exactly as a dry run always could. The talkapp hub is
already multi-character -- `h_bot_register` takes a `char` id and keeps a
separate log per persona.

What this writes is the difference between the two: which sheet, which save,
which prompt files, which name. Everything else is the mechanism and is shared.

Secrets are copied across from `config.json` in memory and never printed. Run
it again after a DEFAULTS change and it re-merges without losing the overrides.

    python tools/make_yukarin_config.py
    python scail.py --config config_yukarin.json --db data/yukarin.db --console --no-sensors
"""

import io
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

OUT = "config_yukarin.json"
PORT = "prompts_yukarin"
# her voice, written from the corpus: her bible and her speech guide live here
# rather than at the top of her port directory
VOICE = "voice_replica_in_text"

# Only what is actually about HER. Anything not here is the mechanism and is
# shared with every other character, which is the whole point of keeping this
# file short: the day it gets long, the mechanism has a character baked into it.
OVERRIDES = {
    # ONE entry per section. A second "world" key was added here for the
    # zeitgeist file and Python kept only the last of the two, silently
    # dropping the character_file override -- so her config pointed at the
    # other character's sheet and every existence property reverted with it.
    "world": {
        "character_file": "data/characters/yukarin.json",
        # The shared zeitgeist file carries notes about why a piece of news
        # would matter to the OTHER character -- "She just did the school
        # drill today" reached this one's system prompt at boot. What is going
        # round is not character-specific; the note on why it lands is.
        "zeitgeist_file": "data/zeitgeist_yukarin.json",
        # the only world she has: one flat, written from her own record, with
        # no feed of the present behind it. Deliberately not in
        # `Config.WORLD_KEYS` -- read the note on that table.
        "home_file": "data/flat_yukarin.json",
        # and the one world key a body would otherwise switch back on for
        # her: the weather is the live present, in a city she is not in
        "weather_enabled": False,
    },
    "logging": {"db_path": "data/yukarin.db"},
    # his call. The MiniMax config on this machine names one voice for
    # everything; without this she speaks in the other character's.
    #
    # And his call on how she has a voice at all: no voice notes ("I'd rather
    # it be integrated like this"), a speaker on every line instead, rendered
    # when he taps it and played from the cache every time after. `always`
    # false is what stops the persona writing a [voice] line for every reply.
    "tts": {
        "voice_id": "YOUR_VOICE_ID",
        "always": False,
        "on_demand": True,
    },
    # she starts at zero with nobody, so her relationship is made of what
    # happens rather than of meters somebody wrote down (docs/primitives.md)
    "primitives": {"enabled": True},
    # what she does with what she has seen (sim/stances.py). She is the only
    # character with the quantities behind it.
    "stances": {"enabled": True},
    # Her feeling line. At the shared cap of 5 the named feelings filled it and
    # the cut threw away her mood state, the four gauge levels and "a lot left
    # unsaid today" with unsaid at 98.6.
    #
    # And what her day's ledger says is still to come. She keeps a schedule
    # book -- it is one of her week's own anchors -- and the ledger used to
    # show her the block she was in and nothing after it, so what she was
    # doing later was answered from her own last message about it rather than
    # from her plan.
    "situation_block": {"feel_tags_max": 12, "ledger_rest_of_day": 12},
    # She is told nothing about how long to write: the length draw was fitted
    # to the other character's English and has never been fitted to hers.
    "shape": {"tell_length": False},
    # the stance owns the last line of her prompt, so nothing else bids for it.
    # `compare` is a whole second reply-writing call, logged and never sent,
    # and for her it cannot happen at all: the flag it reads is only set inside
    # the nudge branch and the nudge is off. It said true for three days and
    # advertised a paid draft that has never once run.
    "nudge": {"enabled": False, "compare": False},
    # Her attachment layer, derived from her own sheet. The shipped ids are the
    # other character's, so her strategy selection and her settle were reading
    # nothing at all.
    "attachment": {"belief_pulls": {"kept_in_mind_by_name": 0.5, "say_it_first": 0.35, "pick_the_kind_reason": -0.5, "unrehearsed_is_the_danger": -0.45, "told_off": -0.4, "the_gap_is_the_act": -0.3},
                   "belief_tests": {"protest": {"resolved": {"kept_in_mind_by_name": 6.0, "pick_the_kind_reason": -5.0}, "failed": {"kept_in_mind_by_name": -3.0, "pick_the_kind_reason": 5.0}}, "deactivate": {"resolved": {"kept_in_mind_by_name": 6.0, "the_gap_is_the_act": 3.0}, "failed": {"kept_in_mind_by_name": -4.0, "pick_the_kind_reason": 2.0}}, "rebound": {"the_gap_is_the_act": 5.0, "say_it_first": 3.0}}},
    # Her picture of him holds two beliefs, both about the asymmetry of what
    # each has of the other, and neither is borne out by him turning up when he
    # said he would.
    "expect": {"around_belief": ""},
    # her own record. The paths are ALSO on her sheet (`lore` in
    # data/characters/yukarin.json), which wins at load, so a re-run of this
    # tool cannot switch her memory of her own life off; this is the copy a
    # person reads in the config.
    "lore": {
        "enabled": True,
        "file": "yukarin/persona/records.json",
        "triggers_file": "yukarin/persona/triggers.json",
        "memory_file": "yukarin/persona/records_memories.json",
        "memory_triggers_file": "yukarin/persona/memory_triggers.json",
    },
    # Nothing about posting here any more, and nothing about her body or her
    # world either: `has_account: false` on her sheet switches both off through
    # `Config.REQUIRES`, the way `embodied` and `in_world` switch off the rest.
    # A flag written by hand in a character's config is a decision that has to
    # be repeated for the next character; a property on a sheet is a decision
    # made once about what kind of thing she is.
    "character": {
        "name": "Yukari",
        "program": "resident",
        # she has one language and this chat is no different from anywhere else
        "writes_to_him": "japanese",
        # and the machinery's instructions to her are in it too, where they are
        # addressed to her rather than to itself
        "instruction_language": "japanese",
        "name_ja": "田村ゆかり",
        "reading_ja": "たむら ゆかり",
        "style_prompt": "prompts_yukarin/voice_replica_in_text/style.md",
        "style_ja_prompt": "prompts_yukarin/voice_replica_in_text/style.md",
        "cast_file": "data/cast_yukarin.json",
        "cast_sheets_dir": "prompts_yukarin/cast",
        # what fills the character-shaped holes in the shared mechanism
        # prompts; without this she reads the other character's ward, her
        # classmates and her school day out of files she has in common with her
        "neutral_file": "data/characters/neutral/yukarin.json",
        "voice_rules_file": "data/voice_rules_yukarin.json",
        "beliefs_file": "data/beliefs_yukarin.json",
        "self_beliefs_file": "data/self_beliefs_yukarin.json",
    },
    # ---- the sections a body brings with it that she has not got ----
    #
    # `embodied: true` on her sheet switches six sections ON through
    # `Config.REQUIRES`, and five of them describe a body she does not have.
    # These were set by hand in her config and named in NONE of them, so a
    # re-run of this tool used to give her back a menstrual cycle, hunger, the
    # weather and an allowance -- the exact reversal the sheet's own
    # `_embodied_why` note says has been decided against. The reasons are on
    # the sheet; this is the file that writes them down.
    #
    # forbidden material, and zero records in 1,603 hand-read observations
    "health": {"enabled": False},
    # hunger and thirst: hunger appears once in the whole corpus
    "needs": {"enabled": False},
    # the air she is in, off a live feed of the present she is not in
    "environment": {"enabled": False},
    # an allowance written for a schoolgirl; her pay day is the twentieth
    "money": {"enabled": False},
    # a journey engine reading a place graph that is blanked for a character
    # with no world, so it has nowhere to go and contradicts her own day
    "situation": {"enabled": False},
    # ---- and the rest of what is hers, none of it named here before ----
    # her flat, which is a household of one and the only place she is
    "household": {"enabled": True, "file": "data/household_yukarin.json"},
    # what he is reading in a visual novel, which she can see because she
    # lives on the machine he reads it on
    "eroge": {"enabled": True},
    # what he is watching, and whether she is in it
    "watching": {"enabled": True, "her_seiyuu_name": "Tamura Yukari"},
    # pictures of her from her own episodes, which is her face and not the
    # other character's
    "reactions": {"enabled": False, "character": "tamura_yukari"},
    # reading more of what is on his screen than he would expect
    "vault_snoop": {"enabled": False},
    # Her scene is cut from her plan in code and no model writes it. Her day is
    # written once from her own home file and there is no world round it for a
    # second writer to report on: the block already says where she is, what she
    # is doing and whether she can be reached, and the tick was paying to
    # paraphrase it back 66 to 83 times a day. It was also the only thing in
    # her process free to state a fact her day does not contain, which is what
    # put a recording in her mouth at a time her plan does not hold.
    "director": {"scene_source": "plan"},
}


# A gauge of hers that the mechanism's default describes wrongly, patched
# rather than replaced (see the note beside the loop that applies it).
GAUGES = {
    "belonging": {"baseline": 0, "tags": []},
}


def main(argv=None):
    """`--out <path>` writes somewhere else and touches nothing of hers, which
    is how a regeneration is checked against her live config before it is
    allowed to replace it (`diff` of the two must be empty). `--fresh` ignores
    her existing config and writes what this tool would produce for a
    character who has none, which is what says how much of her file is written
    down here and how much only exists in the file."""
    from config import Config, DEFAULTS, _merge

    argv = list(sys.argv[1:] if argv is None else argv)
    out = OUT
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    fresh = "--fresh" in argv

    # A duplicate key in the OVERRIDES literal is silent in Python and the
    # last one wins, which once cost the character_file override and pointed
    # her at the other character's sheet. The literal cannot be checked after
    # the fact, so check the result instead.
    for sect, kv in OVERRIDES.items():
        assert isinstance(kv, dict) and kv, "empty override section: %s" % sect

    # The mechanism, with her own file over it. It used to be the mechanism
    # alone -- "start from DEFAULTS, not from his config, so nothing he tuned
    # for the other character comes across and everything deliberate about her
    # is written down here". The second half of that turned out not to be true:
    # 86 keys of her live file differed from what this tool writes, from which
    # model writes in her voice and where her own bible is, to eleven sections
    # switched off by hand, so a re-run would have quietly undone four days of
    # decisions. Her file goes under DEFAULTS the same way `config.json` does
    # at every boot (`Config.__init__`), so a new key still arrives with its
    # default and nothing of hers is lost; `--fresh` says what is left if her
    # file is gone.
    merged = json.loads(json.dumps(DEFAULTS))
    if not fresh and os.path.exists(OUT):
        merged = _merge(merged, json.load(open(OUT, encoding="utf-8")))

    # the secrets are the exception -- they belong to the machine, not to a
    # character, and are read across without being looked at
    if os.path.exists("config.json"):
        live = json.load(open("config.json", encoding="utf-8"))
        for sect, keys in (("api", ("api_key", "base_url", "provider", "providers")),
                           ("talkapp", ("token", "port", "enabled", "boot_wait_seconds")),
                           # the voice vendor's key and script live on the
                           # machine, not with a character. Without these two
                           # she has a voice id and no way to reach the
                           # endpoint that speaks it, which fails silently at
                           # the moment he taps a line.
                           ("tts", ("minimax_script_path", "minimax_config_path")),
                           ("sensors", None), ("sensor_view", None), ("vision", None),
                           ("odpt", None), ("weather", None)):
            if sect not in live:
                continue
            if keys is None:
                merged[sect] = json.loads(json.dumps(live[sect]))
            else:
                for k in keys:
                    if k in live.get(sect, {}):
                        merged.setdefault(sect, {})[k] = live[sect][k]
        # her chat is her own: a second Telegram bot would need its own token,
        # and until there is one she is app-only
        merged.setdefault("telegram", {})["bot_token"] = ""
        merged["telegram"]["chat_id"] = ""

    for sect, kv in OVERRIDES.items():
        merged.setdefault(sect, {}).update(kv)

    # What her SHEET says, copied into the file a person opens. The sheet wins
    # at load either way (`config.py:_apply_character`), so none of this
    # changes what runs -- but the existence block in the generated file was
    # the untouched default, which said she is in a world, has an account and
    # sees him through an app: the opposite of what she is, in the first file
    # anybody reads. Taken from the sheet rather than typed here, so there is
    # one place to change it.
    sheet = {}
    _sheet_path = OVERRIDES["world"]["character_file"]
    if os.path.exists(_sheet_path):
        sheet = json.load(open(_sheet_path, encoding="utf-8"))
    for k in ("embodied", "in_world", "sees_him", "has_account"):
        if k in (sheet.get("existence") or {}):
            merged["character"].setdefault("existence", {})[k] = sheet["existence"][k]
    if str(sheet.get("mal_person_id", "") or "").strip():
        merged["character"]["mal_person_id"] = str(sheet["mal_person_id"]).strip()
    # and the machinery her sheet says she has not got, which is a section's
    # own `enabled` flag or one of the named switches for a thing that has no
    # section (the continuity check on her drafts lives under `delivery`)
    for name in sheet.get("mechanisms_absent") or {}:
        if str(name).startswith("_"):
            continue
        sect, key = Config.NAMED_SWITCHES.get(name, (name, "enabled"))
        if isinstance(merged.get(sect), dict) and key in merged[sect]:
            merged[sect][key] = False

    # One gauge, not a section: `update` on "state" would replace the whole
    # gauge spec. She has no peers, so there is nobody who could leave her out
    # and nothing for `Sentiments.belonging` to read -- it returned its own
    # floor forever, which cleared the tag threshold of 22 and put "on the
    # outside of them lately" permanently into a line that holds a handful of
    # feelings. A floor is not a feeling.
    for name, spec in GAUGES.items():
        if name in merged.get("state", {}).get("gauges", {}):
            merged["state"]["gauges"][name].update(spec)

    # every ported prompt is pointed at; every unported one is left pointing at
    # the other character's file, so it fails loudly rather than quietly
    # speaking in her voice with somebody else's words
    ported = missing = 0
    for role, spec in merged.get("models", {}).items():
        if not isinstance(spec, dict) or not spec.get("prompt"):
            continue
        rel = os.path.relpath(spec["prompt"], "prompts").replace(os.sep, "/")
        # a prompt that is not under `prompts/` belongs to a program, not to
        # the shared set, and there is nothing to port: the relative path
        # climbs out and the join produced `prompts_yukarin/../tomoe/prompts/
        # x.txt`, which reads as a port, resolves to the same file and made
        # this tool's output differ from its own input in 22 places
        if rel.startswith(".."):
            missing += 1
            continue
        # her own copy of a shared prompt, under her port directory or in the
        # voice replica beside it -- which is where her BIBLE is, so without
        # the second candidate a regenerated config handed the role that
        # writes her words the first character's bible
        mine = next((p for p in (os.path.join(PORT, rel).replace(os.sep, "/"),
                                 os.path.join(PORT, VOICE, rel).replace(os.sep, "/"))
                     if os.path.exists(p)), "")
        if mine:
            spec["prompt"] = mine
            ported += 1
        else:
            missing += 1

    if out == OUT and os.path.exists(OUT):
        ts = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs("data/retired/%s_config_yukarin" % ts, exist_ok=True)
        shutil.copy(OUT, "data/retired/%s_config_yukarin/%s" % (ts, OUT))

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, ensure_ascii=False)
    print("wrote %s" % out)
    print("  %d roles point at her prompts, %d still point at the other character's" % (ported, missing))

    cfg = Config(path=out)
    ex = cfg.character.existence
    print("  loads as %s: embodied=%s in_world=%s sees_him=%s, %d gauges"
          % (cfg.character.name, ex.embodied, ex.in_world, ex.sees_him, len(cfg.state.gauges)))
    print("  save %s, lock %s.lock -- her own, beside his" % (cfg.logging.db_path, cfg.logging.db_path))
    for k in ("cast_file", "beliefs_file", "self_beliefs_file", "voice_rules_file"):
        p = getattr(cfg.character, k)
        print("  %-18s %s%s" % (k, p, "" if os.path.exists(p) else "   -- does not exist yet"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
