"""Read her world from each cast member's chair.

Every call the cast layer makes is built from a different seat: Rena's turn is
her sheet, her day, her edges and what she can see of the chat; Tomoe's reply
is her whole interior; a beat is one person reaching for her. Nothing has ever
LOOKED at those prompts side by side, and a prompt is where a contradiction
hides: the same fact stated twice with two values, an English gloss in a
Japanese-only field, a name that is one girl in the labels and another in the
transcript.

This builds the real prompts against a COPY of the save, with the model stubbed
out, and prints them -- so a person can read what Rena actually reads. It also
runs the cheap mechanical checks that a reader would otherwise have to do by
eye:

  names     every name in the prompt resolves through the roster, and the
            person's own name is not among the people they are told about
  clock     her time and his are labelled where they appear
  language  the ja fields are Japanese and the English gloss is not in them
  size      the sections, so a prompt that has quietly doubled is visible

    python tools/context_audit.py                  # all three friends
    python tools/context_audit.py --who Rena-chan
    python tools/context_audit.py --full           # the whole prompt, verbatim
"""
import argparse
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import roster

CAP = 2600          # how much of a prompt to print in the summary view


def build_app(src="data/world.db"):
    tmp = os.path.join(tempfile.gettempdir(), "scail_context_audit.db")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(src + suffix):
            shutil.copy(src + suffix, tmp + suffix)
    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--console", "--no-sensors", "--db", tmp]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    return scail.App(args)


class Captured(Exception):
    """The prompt is the point; the answer is not wanted."""

    def __init__(self, messages):
        self.messages = messages


def capture(app, fn):
    """Run something that makes one model call and keep the messages."""
    got = {}

    def fake_json(role, messages, **kw):
        got["role"] = role
        got["messages"] = messages
        raise Captured(messages)

    def fake_call(role, messages, **kw):
        got["role"] = role
        got["messages"] = messages
        raise Captured(messages)

    real_json, real_call = app.llm.call_json, app.llm.call
    app.llm.call_json, app.llm.call = fake_json, fake_call
    try:
        fn()
    except Captured:
        pass
    except Exception as e:                      # a real fault in the builder
        got["error"] = f"{type(e).__name__}: {e}"
    finally:
        app.llm.call_json, app.llm.call = real_json, real_call
    return got


def sections(text):
    """(label, chars) for the ALL-CAPS headings a prompt is built from."""
    out, cur, n = [], "(head)", 0
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z '/()-]{4,70}:)", line)
        if m:
            if n:
                out.append((cur, n))
            cur, n = m.group(1).rstrip(":"), 0
        n += len(line) + 1
    if n:
        out.append((cur, n))
    return out


def checks(app, who, text):
    """The mechanical half: what a careful reader would check by eye."""
    cfg = app.config
    out = []
    me = roster.record_name(cfg, who)
    # 1. every SPEAKER LABEL resolves to somebody. Only the labels: a check
    # that flags every noun in the prompt cries wolf and gets ignored, which
    # this one did on its first run (丘公園, 断定, 句読点).
    labels = set(re.findall(r"(?m)^\s*(?:- [0-9-]{10} [0-9:]{5} \([a-z_]+\): )?([^\s:：/]{2,12})[:：] ", text))
    labels |= set(re.findall(r"/ ([^\s:：/]{2,12})[:：] ", text))
    unknown = sorted(n for n in labels
                     if not roster.role_of(cfg, n) and not n.isupper() and not n.isascii())
    # 2. is this person listed among the people they are told about
    self_in_others = ""
    for line in text.splitlines():
        if line.startswith("ALSO READING THE GROUP CHAT") and me in line:
            self_in_others = line[:90]
    # 3. a clock without a label
    unlabelled = [l for l in text.splitlines()
                  if re.match(r"^TIME:", l) and "her time" not in l]
    # 4. the English gloss leaking into the Japanese record
    gloss = [l for l in text.splitlines()
             if l.startswith("  ") and re.search(r"[぀-ヿ]", l) and re.search(r"\b(is|the|she|her)\b", l)]
    out.append(("names that resolve to nobody", ", ".join(unknown[:6]) or "none"))
    out.append(("this person listed among 'also reading'", self_in_others or "no"))
    out.append(("an unlabelled clock", unlabelled[0][:60] if unlabelled else "none"))
    out.append(("a line mixing her Japanese with English prose", str(len(gloss))))
    return out


def show(app, label, got, full=False):
    print("\n" + "=" * 78)
    print(f"{label}   (role {got.get('role', '?')})")
    print("=" * 78)
    if got.get("error"):
        print("  BUILDER FAILED:", got["error"])
        return
    msgs = got.get("messages") or []
    for m in msgs:
        body = m.get("content", "")
        print(f"\n----- {m.get('role')} ({len(body):,} chars) -----")
        if m.get("role") == "system" and not full:
            print(body[:700] + ("\n  ...[trimmed]" if len(body) > 700 else ""))
        else:
            print(body if full else body[:CAP] + ("\n  ...[trimmed]" if len(body) > CAP else ""))
    usr = next((m["content"] for m in msgs if m.get("role") == "user"), "")
    if usr:
        print("\n  sections of the user block:")
        for name, n in sections(usr):
            print(f"    {name[:56]:<58}{n:>7} chars")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", default="", help="one speaker instead of all three")
    ap.add_argument("--full", action="store_true", help="print the prompts whole")
    a = ap.parse_args()

    app = build_app()
    ex = app.exchange
    scene = app.director.current or {}
    people = [a.who] if a.who else ["Rena-chan", "Hinako", "Aya"]

    # a chat in flight, so the prompt is built the way a live one is
    her = roster.record_name(app.config, "Tomoe")
    turns = [{"who": roster.record_name(app.config, people[0]), "ja": "明日の集合、13時でいい？", "hm": "21:40"},
             {"who": her, "ja": "うん、それでいいよ", "hm": "21:42"}]

    print("CONTEXT AUDIT")
    print(f"her clock {app.clock.hm()} on {app.clock.date_str()}; his {app.clock.user_now():%H:%M}")
    print(f"scene: {scene.get('location', '?')} / {scene.get('activity', '?')} "
          f"(with {scene.get('with_who', '-')}, phone {scene.get('phone_access', '?')})")

    for who in people:
        nm = roster.record_name(app.config, who)
        got = capture(app, lambda: ex._one_speaker(nm, "group", turns))
        show(app, f"{nm} — her seat in the GROUP", got, a.full)
        usr = next((m["content"] for m in (got.get("messages") or []) if m.get("role") == "user"), "")
        if usr:
            print("\n  what a careful reader would check:")
            for k, v in checks(app, nm, usr):
                print(f"    {k:<48} {v}")

    got = capture(app, lambda: ex._her_turns(roster.record_name(app.config, people[0]), "group", turns, scene))
    show(app, f"{her} — her own seat, answering them", got, a.full)

    beat = {"time": app.clock.hm(), "who": roster.record_name(app.config, people[0]), "kind": "group",
            "text": "she is asking about tomorrow", "salience": 2}
    got = capture(app, lambda: app.cast._speak_beat(beat, app.clock.date_str()))
    show(app, f"{roster.record_name(app.config, people[0])} — reaching for her (a beat)", got, a.full)


if __name__ == "__main__":
    main()
