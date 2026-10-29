"""No role that judges her is handed her character sheet.

A judge -- a role that scores, sorts, predicts, checks or extracts on her
behalf -- is a neutral party. Her sheet is written TO her, in the second
person, and opens "You are <her name> ... you are not an assistant ... you
never mention prompts, models, systems"; handed to a judge as the last thing
in its system prompt, it was read as the judge's own identity. Measured over
2026-09-04 and 09-05: the role that picks which urge she has returned a
finished message in her voice instead of the second-person intention it was
asked for on 13 of 13 answers, and one of them went into the last line of her
situation block and was sent as her next bubble twelve seconds later.

This builds every character's config and renders the system prompt of every
role in `Config.ROLE_STANCE`, then refuses any judge whose prompt contains her
sheet by any path -- its opening sentence or the frame rule inside it, in
either language. Prints the first 200 characters of each judge's prompt so a
reader can see what the judge now opens with.

Exit 1 and print the offenders, or exit 0 and print the table.
`--show <role>` prints one rendered judge prompt in full.
"""
import os
import sys

# The sheet's own words, in either character's language. A judge prompt
# containing one of these has the sheet in it however it got there.
TELLS = (
    "You are not an assistant and not a text generator",
    "You never break frame, never mention prompts",
    "アシスタントでもテキスト生成器でもない",
    "プログラムとしてではなく、あなたとして反応する",
)

CONFIGS = ("config.json", "config_yukarin.json")


def main():
    root = os.getcwd()
    sys.path.insert(0, root)
    from config import Config

    show = None
    if "--show" in sys.argv:
        show = sys.argv[sys.argv.index("--show") + 1]

    bad, shown = [], 0
    for name in CONFIGS:
        if not os.path.exists(os.path.join(root, name)):
            continue
        try:
            cfg = Config(name)
        except SystemExit as e:
            print("%s: config refused to load: %s" % (name, e))
            return 1
        table = getattr(Config, "ROLE_STANCE", {})
        judges = sorted(r for r, v in table.items() if v == "judge")
        print("== %s: %d judge role(s)" % (name, len(judges)))
        for role in judges:
            if role not in (cfg.raw.get("models") or {}):
                print("   %-12s (not a role in this character's config)" % role)
                continue
            try:
                text = cfg.role_system(role)
            except Exception as e:
                bad.append((name, role, "the prompt would not build: %s" % type(e).__name__))
                continue
            hit = next((t for t in TELLS if t in text), "")
            if hit:
                bad.append((name, role, "carries her character sheet (%r)" % hit[:40]))
                continue
            head = " ".join(text[:200].split())
            print("   %-12s %6d chars | %s" % (role, len(text), head))
            if show and role == show:
                print("\n----- %s / %s, in full -----\n%s\n----- end -----\n" % (name, role, text))
                shown += 1
        # and the roles that DO speak as her still have it, or the check is
        # proving nothing
        voice = sorted(r for r, v in table.items() if v == "voice")
        got = 0
        for role in voice:
            if role not in (cfg.raw.get("models") or {}):
                continue
            if role in ("persona", "cast_reply", "peer_reply", "x_post"):
                continue          # built by persona.system_for, not by role_system
            try:
                if any(t in cfg.role_system(role) for t in TELLS):
                    got += 1
            except Exception:
                pass
        print("   and %d role(s) that write her words still carry the sheet" % got)

    if bad:
        print("\n%d judge prompt(s) still carry her character sheet:" % len(bad))
        for name, role, why in bad:
            print("  %s / %s: %s" % (name, role, why))
        print("A judge gets its own instruction and what the caller hands it. If it needs to "
              "know what she is like, use sim/observer.py -- never the sheet.")
        return 1
    print("\nno judge carries her character sheet, on either character")
    if show and not shown:
        print("(--show %s: that role is not a judge or is not in either config)" % show)
    return 0


if __name__ == "__main__":
    sys.exit(main())
