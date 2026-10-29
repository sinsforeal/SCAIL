"""Her first words through the real stack.

Not a stand-in. This boots the App with her config, so the prompt is the one
`persona.system_for('him')` assembles -- her bible, her style, her beliefs, her
self-beliefs, her roster, her primitives -- and calls the persona role the way
the loop calls it. Everything the earlier generation test could not reach.

A scratch database, console mode, no sensors: it never touches her save or his.

    python tools/her_first_word.py "こんばんは。今日は疲れてる?"
"""

import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def main():
    cue = sys.argv[1] if len(sys.argv) > 1 else "こんばんは。今日は疲れてる?"
    tmp = os.path.join(tempfile.gettempdir(), "her_first_word.db")
    for suffix in ("", "-wal", "-shm", ".lock"):
        try:
            os.remove(tmp + suffix)
        except OSError:
            pass

    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--console", "--no-sensors", "--config", "config_yukarin.json", "--db", tmp]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    app = scail.App(args)

    # his message, on the record, so nothing she says about it is invented
    app.store.add_message(app.clock.now_ts(), app.clock.date_str(), "user", cue)
    unread = app.store.unread_user_messages()

    scene = {"location": "his machine", "activity": "he is typing to her",
             "with": "alone", "phone_access": "free", "setting": "indoors",
             "sensory": "the window he has had open for forty minutes, and now this",
             "inner": "", "events": [], "share_worthy": False, "share_hint": "",
             "next_tick_minutes": 20}

    print("\n--- what she is given (the him part of her situation)")
    sit = app.persona._situation(scene, "", unread, "")
    for ln in sit.split("\n"):
        if any(k in ln for k in ("STANDS WITH HER", "unread", "he ")):
            print("   ", ln[:150])

    print("\n--- calling the persona role through the real stack")
    bubbles, voice = app.persona.generate(scene, "", unread)
    print("\n" + "=" * 66)
    for b in (bubbles or []):
        print(b)
    if voice:
        print("[voice] %s" % voice)
    print("=" * 66)

    p = app.primitives
    key = app.state._him_key() or "him"
    print("\nafter one message:")
    print("   attention_his %.0f  predictability_hers %.0f  reciprocity %.0f"
          % (p.get(key, "attention_his"), p.get(key, "predictability_hers"), p.get(key, "reciprocity")))
    print("   affection %d (%s)" % (round(app.state.gauges["affection"]), app.state.affection_band()))
    print("\nNever-observed space: a level 2-3 inference until he has read it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
