"""What a second character still shares with the first, subsystem by subsystem.

Three things reach a character: the switches that decide which subsystems run
for her, the files those subsystems read, and the prompts they are written in.
This reports all three against one config, so "is she isolated" is a table
somebody can read rather than a boot to sit through.

The rule it enforces is narrow and worth stating: **a path shared between two
characters must belong to the machine, not to a person.** His telemetry, his
anime history, the API keys and the model prompts are the machine and are
shared on purpose. A household, a place graph, a school calendar and a cast are
a person, and sharing one means the second character is reading the first one's
life. `Config.WORLD_KEYS` blanks those; anything else shared and person-shaped
is reported here and fails.

    python tools/isolation.py                          # the second character
    python tools/isolation.py --config config.json     # the first, as a control
    python tools/isolation.py --against config.json    # what she shares with whom
"""

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

PATHY = re.compile(r"(^|/)(data|prompts|logs|secerts|talkapp|characters)[/.]|\.(json|md|txt|db|log|jsonl)$")

# One directory per character, holding everything that is that person and
# nothing that is not (`docs/bundle.md`). It is the only prefix in the project
# that can be stated as a rule rather than as a list: everything under
# `characters/<key>/` is hers, so a path of hers anywhere else has to argue for
# itself, and a path under somebody else's bundle needs no argument at all --
# it is the fault this whole check exists to find, in one line.
BUNDLE_ROOT = "characters/"

# Shared on purpose, because it is the machine and not a person: his PC's own
# telemetry, his anime history, the credentials, and the directories every run
# writes into. A new entry here is a claim that a file belongs to the machine,
# and it should be arguable in one sentence.
MACHINE = (
    "api.", "sensors.", "vision.key_path", "logging.backup_dir",
    "logging.dry_run_out_dir", "tts.cache_dir", "world.weather_cache_path",
    "talkapp.",
    # the voice vendor's key, model and command-line tool. The file also names
    # a default voice, and that part IS a person -- so it is not enough to call
    # this machinery and move on: `_effective_voice` below checks that no two
    # characters come out of it sounding the same.
    "tts.minimax_config_path", "tts.minimax_script_path",
    # the second vendor's credential, beside the provider's key one line up
    # (`api.` covers `openrouter_key_file`): one key for the machine, the same
    # for every character, and no person's record anywhere in it. The
    # classifier it buys is code's half of the split (`typesafe.py`,
    # `docs/system-one.md`), and which uses a character turns on is hers.
    "typesafe.key_file",
    # his media player's own history of every file he has opened. The same
    # claim as his telemetry and his anime list: it is a record of what the
    # machine did, and both characters watching the same machine is the
    # premise rather than a leak.
    "watching.player_history_path", "watching.now_playing_path",
    # the same player's record of what it FINISHED -- the end position and the
    # unpaused seconds of every play -- and the plain-text timeline of those
    # plays he reads himself (machine/plays.py). Both are the machine's for
    # the same reason the history is: they say what the machine did, and every
    # character watching one player is the premise. Whichever process gets
    # there first writes a row and the open's own epoch stops it being written
    # twice, so sharing the file is what makes one record possible at all.
    "watching.player_plays_path", "watching.plays_timeline_path",
    # every page, subtitle file, transcript and verdict fetched about an
    # episode, kept on disk under the show and the episode number. It is a
    # cache of public pages about television programmes with nobody's life in
    # it, and one download serving both characters is the point; what each of
    # them made of an episode is in her own save, not here.
    "recap.archive_dir",
    # And the readable view of it: one page per episode with the account, the
    # scenes in order and the sources it was merged from, plus an index over
    # all of them (`machine/episode_reports.py`). The same claim as the
    # archive it is written from -- an episode of a television programme is
    # the same episode whoever watched it, so one copy serves the machine.
    # Nothing a character made of an episode is in there; that is in her save.
    "recap.episodes_report_dir",
    # ...and where each episode's own dialogue came from, one line per attempt
    # that resolved, append-only. The same claim again, and the reason it is one
    # file rather than one per character: a subtitle file found once is found
    # for the machine, and the answer to "where did that transcript come from"
    # does not change with who is asking. Each save catches up its own rows
    # into it and the de-duplication makes three writers one record.
    "recap.transcripts_report",
    # The clone of a public subtitle archive: an archive of television with
    # nobody's life in it, cloned once for the machine and refreshed on the
    # machine's own clock, never on a character's thread. Reading it costs no
    # network, which is why it is on disk at all.
    "recap.subtitles_local_mirror",
    # His own transcriber, and the episode it is pointed at: his install and
    # his file, a tool of the machine's like the media player itself.
    "recap.whisper_exe",
    # What was fetched about the world, kept once for the whole machine
    # (machine/retrievals.py): an episode's page and the verdict on it, a page
    # condensed by a role that names nobody, a web search, a game's database
    # card. Nothing a character made of any of it is in there -- that is in her
    # own save -- and one fetch serving both is the point. The `sensors.`
    # prefix above already covers the key; it is written out here so the claim
    # sits beside the other machine-owned stores rather than being inherited.
    "sensors.retrievals_db",
    # The per-play dossiers and the store behind them (`machine/dossier.py`).
    # The same claim as the media player's own history one line above: it is a
    # record of what the MACHINE did with a television programme -- which file
    # was played, what the list says about it, who is in it -- written once by
    # the mirror daemon for a machine with three characters on it. Nothing a
    # character made of a play is in there; that is in her own save.
    "dossier.",
    # The koikano visual-novel corpus and the VN channel's own run directory.
    # The corpus (sprites, faces, voice and the C4 expression tables) is the
    # game's extracted assets, read in place by the VN stage and belonging to
    # no character; `vn.out_dir` is one more directory under `data/` that a run
    # writes into. Neither carries a person's record, so neither is a leak when
    # more than one character shares it.
    "vn.character_dir", "vn.inventory", "vn.labels", "vn.out_dir",
    # and the staging pass's two art directories, the same corpus read the
    # same way: backgrounds and the emotion overlays the face can carry.
    "vn.bg_dir", "vn.emotion_dir",
)

# Shared because the mechanism prompts carry no person: `tools/neutral_gate.py`
# proves every character-shaped span in them is a `[[TOKEN]]` filled from the
# character's own file, and that filling them for the character they were
# written around reproduces the originals byte for byte.
NEUTRAL = ("models.", "vision.prompt_")

# Shared because it is the WORLD's, and only when both characters are in the
# same world (`world_shared.id`, `docs/shared-world.md` §1). A world is one
# clock, one calendar, one set of people and one set of places; two characters
# in it reading two rosters or two maps is the fault, not the safeguard. Before
# a promoted character existed there was no such category and every one of
# these read as the first character's, which is what `docs/promotion.md` lists
# as the third thing a promoted character still lacked.
#
# The test is the world id and not the key alone: a character with no world has
# these BLANKED by `Config.WORLD_KEYS`, so if one of them is still on her
# loaded config and she is not in the other character's world, it is a leak and
# is reported as one.
WORLD = (
    "character.cast_file", "character.cast_sheets_dir",
    "cast.mechanisms_dir", "cast.types_file",
    "world.places_file", "world.school_calendar_file",
    "world.holidays_file", "world.local_events_file", "world.shared_dir",
    # `world.geography_file` is NOT here and must not be added back. A map
    # holds one person's flat, her station, her walk to it and her line's
    # notes, and two characters in one world sharing one map means the second
    # is handed the first one's address under the heading HER MAP. The school
    # and the ward's public places ARE the same places, and are copied into
    # each character's own map with a line on each saying so.
)

# What is still a PERSON inside a file the world owns. Sharing the file is
# right; the block named here is one character's and the other one reads it,
# and saying so is the whole value of listing it rather than calling the file
# clean.
WORLD_STILL_A_PERSON = {
    "character.cast_file": "a peer's `note` and `stance` are that peer's inside AND the first "
                           "character's reading of them; a second reader of this file gets both",
}

# Keys whose VALUE is a person, written as a bare name rather than as a path.
# `PATHY` above never sees these, because they have no directory and no
# extension -- which is how the second character came to be configured to
# publish frames of the FIRST character's face as her own mood, with the
# checker reporting her isolated.
PERSON_KEYS = ("reactions.character",)


def _dig(d, dotted):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, str) else None


def can_be_synthesised(cfg):
    """Is there any route from this character to the renderer?

    Three, and a character with none of them never makes a sound whatever her
    identifier says: `tts.always` speaks a line of hers unprompted,
    `tts.on_demand` speaks one he taps, and `tts.aside_from_persona` lets her
    write a spoken aside of her own. All three sit under `tts.enabled`."""
    t = getattr(cfg, "tts", None)
    if t is None or not getattr(t, "enabled", False):
        return False
    return any(bool(getattr(t, name, False))
               for name in ("always", "on_demand", "aside_from_persona"))


def would_fall_back_to(cfg):
    """The identifier the shared vendor file would hand her, or ""."""
    p = getattr(cfg.tts, "minimax_config_path", "")
    if p and os.path.exists(p):
        try:
            mc = json.load(io.open(p, encoding="utf-8"))
            return str(((mc.get("voice_setting") or {}).get("voice_id") or ""))
        except (OSError, ValueError):
            pass
    return ""


def effective_voice(cfg):
    """The voice she will actually be synthesised in.

    Her own `tts.voice_id` if she has one, otherwise whatever the shared
    MiniMax config names -- and that fallback is the trap, because the shared
    file's default is one character's voice. A second character whose id was
    never set, or was cleared, would speak in it and nothing downstream would
    notice: the audio renders, the cache stores it, the app plays it.

    A character with no route to the renderer at all is the other case, and it
    is not a collision: the first character's identifier is empty and every
    switch that could speak a line of hers is off, so reporting the shared
    default as HER voice made her clash with whoever is given that identifier
    on purpose. She has none; what she would fall back to is named anyway,
    because turning one of those switches on would make the clash real."""
    own = str(getattr(cfg.tts, "voice_id", "") or "").strip()
    if own:
        return own, "her own tts.voice_id"
    if not can_be_synthesised(cfg):
        back = would_fall_back_to(cfg)
        return "", ("she is never synthesised; the shared default she would fall back to is "
                    + back if back else "she is never synthesised")
    back = would_fall_back_to(cfg)
    if back:
        return back, "the shared default"
    return "", "nothing set"


def key_of(config_path):
    """The operator's key for the character this config file belongs to.

    Read off the register rather than guessed from the file name: the first
    character's config is `config.json` and her key is not `config`."""
    try:
        from tools import registry
    except ImportError:
        import registry
    want = os.path.basename(str(config_path or "")).lower()
    for r in registry.characters():
        if os.path.basename(r["config"]).lower() == want:
            return r["key"]
    return ""


def bundle_owner(value, keys):
    """Whose bundle this path is under, or "" for a path that is under none."""
    p = str(value or "").replace("\\", "/")
    if not p.startswith(BUNDLE_ROOT):
        return ""
    rest = p[len(BUNDLE_ROOT):].split("/")[0]
    return rest if rest in keys else ""


def _world_of(cfg):
    """The id of the world this loaded config is in, or "" for no world.

    Read off the LOADED config for the same reason the file table is: a
    character with no world has the section forced off at load
    (`Config.REQUIRES`), so her file may still name a world and she has no
    path to one."""
    ws = (cfg or {}).get("world_shared") or {}
    return str(ws.get("id") or "") if ws.get("enabled") else ""


def paths(d, pre=""):
    out = {}
    for k, v in d.items():
        p = pre + k
        if isinstance(v, dict):
            out.update(paths(v, p + "."))
        elif isinstance(v, str) and v and PATHY.search(v):
            out[p] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--against", default="config.json")
    args = ap.parse_args()

    from config import Config
    cfg = Config(path=args.config)
    ex = cfg.character.existence
    # the LOADED config, not the file on disk: the master switch blanks a path
    # at load, so the file still names the other character's household and the
    # running character has no way to reach it. What she can actually read is
    # the honest question, and it is the one a subsystem asks.
    mine = cfg.raw
    theirs = Config(path=args.against).raw if args.against != args.config else {}

    print("\n  %s -- what she shares with %s" % (cfg.character.name, os.path.basename(args.against)))
    print("  existence: " + ", ".join("%s=%s" % (k, getattr(ex, k))
                                      for k in ("embodied", "in_world", "sees_him", "has_account")))

    # 1. the master switch
    lacks = [p for p in ("embodied", "in_world", "has_account") if not getattr(ex, p, True)]
    # and whether the world she is in is hers to keep. The same two keys
    # `Config._existence_implies` reads: one writer per world, so a character
    # in a world somebody else keeps runs none of the sections that write it,
    # and a character with no world is not an owner either.
    _ws = getattr(cfg, "world_shared", None)
    if not getattr(ex, "in_world", True) or (getattr(_ws, "enabled", False)
                                             and not getattr(_ws, "owner", False)):
        lacks.append("world_owner")
    off = sorted(s for s, need in Config.REQUIRES.items() if need in lacks)
    on = sorted(s for s, need in Config.REQUIRES.items() if need not in lacks)
    print("\n  THE MASTER SWITCH (Config.REQUIRES, %d subsystems, all assigned)" % len(Config.REQUIRES))
    for prop in ("embodied", "in_world", "has_account", "world_owner"):
        secs = sorted(s for s, n in Config.REQUIRES.items() if n == prop)
        mark = "OFF for her" if prop in lacks else "on"
        print("    needs %-12s %-11s %s" % (prop, mark, ", ".join(secs)))
    print("    needs %-12s %-11s %d subsystems: the mind, the relationship, the machine"
          % ("nothing", "on", sum(1 for n in Config.REQUIRES.values() if n is None)))
    print("    -> %d run for her, %d do not" % (len(on), len(off)))

    blanked = sorted(k for k, need in Config.WORLD_KEYS.items() if need in lacks)
    if blanked:
        print("    and no path to: " + ", ".join(blanked))

    # 2. the files
    A, B = paths(mine), paths(theirs)
    # One world, or two. `_world_of` reads the loaded config, so a character
    # whose world was switched off at load answers "" and shares nothing as the
    # world's however her file is written.
    my_world, their_world = _world_of(mine), _world_of(theirs)
    one_world = bool(my_world) and my_world == their_world
    shared_machine, shared_neutral, shared_world, shared_person, own = [], [], [], [], []
    for k in sorted(A):
        if k not in B or A[k] != B[k]:
            own.append((k, A[k]))
        elif k.startswith(MACHINE):
            shared_machine.append((k, A[k]))
        elif k.startswith(NEUTRAL):
            shared_neutral.append((k, A[k]))
        elif one_world and k in WORLD:
            shared_world.append((k, A[k]))
        else:
            shared_person.append((k, A[k]))

    print("\n  FILES")
    print("    %3d hers alone" % len(own))
    print("    %3d shared, the machine (his telemetry, his history, the keys, the run dirs)"
          % len(shared_machine))
    print("    %3d shared, mechanism prompts with the person taken out (tools/neutral_gate.py)"
          % len(shared_neutral))
    if one_world:
        print("    %3d shared, the world both of them are in (%s)" % (len(shared_world), my_world))
    print("    %3d shared and person-shaped" % len(shared_person))

    if shared_world:
        print("\n  SHARED BECAUSE IT IS THE WORLD'S -- one clock, one calendar, one roster, one map:")
        for k, v in shared_world:
            note = WORLD_STILL_A_PERSON.get(k)
            print("      %-40s %s" % (k, v))
            if note:
                print("      %-40s   still a person inside it: %s" % ("", note))

    if shared_person:
        print("\n  SHARED AND PERSON-SHAPED -- each of these is the other character's:")
        for k, v in shared_person:
            print("      %-40s %s" % (k, v))

    # 2b. the bundle. One prefix that is hers, so the question "is this file
    #     hers" stops being a list of exceptions and becomes a prefix test. A
    #     path under ANOTHER character's bundle is the fault this check exists
    #     for and is failed on; a person-shaped path of hers outside her own
    #     bundle is reported, because the world's and the machine's are
    #     legitimately outside it and a household is not.
    try:
        from tools import registry as _reg
    except ImportError:
        import registry as _reg
    all_keys = {r["key"] for r in _reg.characters()}
    my_key = key_of(args.config)
    in_bundle = [(k, v) for k, v in A.items() if bundle_owner(v, all_keys) == my_key and my_key]
    trespass = [(k, v, bundle_owner(v, all_keys)) for k, v in A.items()
                if bundle_owner(v, all_keys) and bundle_owner(v, all_keys) != my_key]
    world_ok = set(WORLD) | {"logging.db_path"}
    # her prompt directory is hers and is generated FROM her bundle
    # (`tools/new_character.py compose`), so a path into it is a path into her
    # bundle one copy later; `prompts/` is the library's own.
    mine_pre = ["prompts/"]
    if my_key:
        _b = json.load(io.open(os.path.join("characters", my_key, "bundle.json"), encoding="utf-8")) \
            if os.path.exists(os.path.join("characters", my_key, "bundle.json")) else {}
        if _b.get("prompts_generated") and _b.get("prompts_dir"):
            mine_pre.append(_b["prompts_dir"].replace("\\", "/") + "/")
    outside = [(k, v) for k, v in own
               if not bundle_owner(v, all_keys) and not k.startswith(MACHINE)
               and not k.startswith(NEUTRAL) and k not in world_ok
               and not str(v).replace("\\", "/").startswith(tuple(mine_pre))]
    print("\n  HER BUNDLE (characters/%s/, everything that is this person)" % (my_key or "?"))
    if not my_key:
        print("      this config is not in the register, so there is no bundle to test against")
    else:
        print("    %3d of her paths are in it" % len(in_bundle))
        print("    %3d person-shaped path(s) of hers are outside it" % len(outside))
        for k, v in outside:
            print("      %-40s %s" % (k, v))
        for k, v, who in trespass:
            print("      UNDER %s'S BUNDLE: %-24s %s" % (who.upper(), k, v))

    # 3. prompts a role of hers still reads from the shared set while the
    #    subsystem is switched off is fine; while it is ON it is worth seeing
    roles = mine.get("models") or {}
    shared_live = []
    for role, spec in sorted(roles.items()):
        p = (spec or {}).get("prompt") or ""
        if p.replace("\\", "/").startswith("prompts/"):
            shared_live.append(role)
    print("\n  ROLES: %d point at her own prompts, %d at the shared neutral ones"
          % (len(roles) - len(shared_live), len(shared_live)))

    # the voice is a shared file with a per-character override, so the path
    # test cannot see it: two characters can point at one config and still
    # sound different, or point at one config and sound identical
    same_voice = False
    if theirs:
        v, how = effective_voice(cfg)
        ov, ohow = effective_voice(Config(path=args.against))
        print("\n  VOICE: %s (%s)" % (v or "none", how))
        print("         %-8s %s (%s)" % (os.path.basename(args.against) + ":", ov or "none", ohow))
        same_voice = bool(v) and v == ov
        if same_voice:
            print("         BOTH THE SAME: she would be synthesised in the other character's voice")

    # A person named by a bare key rather than by a path. The file classifier
    # above cannot see these: it only inspects values that LOOK like paths, and
    # `koga_tomoe` has no directory and no extension, so a second character
    # configured to publish the first one's face read as isolated. Each of
    # these keys names a person and is built into a path in code.
    same_key = []
    if theirs:
        for key in PERSON_KEYS:
            mine_v, theirs_v = _dig(mine, key), _dig(theirs, key)
            if mine_v and mine_v == theirs_v:
                same_key.append((key, mine_v))
        print("\n  A PERSON NAMED BY A KEY (built into a path in code, so the file test is blind)")
        for key in PERSON_KEYS:
            v = _dig(mine, key)
            print("    %-24s %s" % (key, v if v else "not set"))
        if same_key:
            print("    BOTH THE SAME: " + ", ".join("%s=%s" % kv for kv in same_key))

    if shared_person or same_voice or same_key or trespass:
        why = []
        if trespass:
            why.append("%d path(s) under another character's bundle: %s"
                       % (len(trespass), ", ".join(k for k, _, _ in trespass)))
        if shared_person:
            why.append("%d person-shaped path(s) shared" % len(shared_person))
        if same_voice:
            why.append("one voice between two characters")
        if same_key:
            why.append("%d key(s) naming the other character: %s"
                       % (len(same_key), ", ".join(k for k, _ in same_key)))
        print("\n  NOT ISOLATED: %s.\n" % ", ".join(why))
        return 1
    tail = (", a prompt with no person in it, or the world they are both in (%s)" % my_world
            if shared_world else " or a prompt with no person in it")
    print("\n  Isolated: everything shared is the machine%s.\n" % tail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
