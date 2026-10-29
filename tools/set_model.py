"""Move a character's roles to one model, all together or not at all.

    python tools/set_model.py --config config_yukarin.json                  # show
    python tools/set_model.py --config config_yukarin.json --model kimi-k3  # every role
    python tools/set_model.py --config config.json --model deepseek-v4-flash --roles persona,diary

A model NAME as the provider's table keys it (`api.providers.<name>.models`),
never a slug. The switch refuses a name the character's provider cannot
resolve, because a name missing from the provider's map falls through to the
host as a literal and the host rejects it. The previous config is copied to
`data/retired/<stamp>_set_model/` first. `/model <name>` in the app pins
every role for one run without touching the file; this makes it permanent.
"""
import argparse
import collections
import datetime
import io
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)


def provider_of(cfg):
    api = cfg.get("api", {})
    provs = api.get("providers") or {}
    name = api.get("provider") or "official"
    return name, (provs.get(name) or {})


def resolvable(cfg, model_name):
    """The slug the character's provider serves `model_name` as, or ""."""
    name, p = provider_of(cfg)
    return (p.get("models") or {}).get(model_name, "")


def show(cfg, path):
    roles = cfg.get("models") or {}
    by = collections.Counter(m.get("model") for m in roles.values())
    name, p = provider_of(cfg)
    print(f"{path}: {len(roles)} role(s), provider {name}")
    for m, n in by.most_common():
        slug = resolvable(cfg, m)
        print(f"  {m:<24} {n:>3} role(s)   {name + '->' + slug if slug else '** NOT RESOLVABLE BY THE PROVIDER **'}")
    print(f"  {name} can serve: {', '.join(sorted((p.get('models') or {})))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config_yukarin.json")
    ap.add_argument("--model", default="", help="model NAME as the provider table keys it, not the slug")
    ap.add_argument("--roles", default="", help="comma-separated; default is every role")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        print(f"[FATAL] no such config: {args.config}")
        return 1
    cfg = json.load(io.open(args.config, encoding="utf-8"))

    if not args.model:
        show(cfg, args.config)
        return 0

    slug = resolvable(cfg, args.model)
    name, _p = provider_of(cfg)
    if not slug:
        print(f"[FATAL] '{args.model}' is not in {name}'s models table.")
        print(f"        Add it to api.providers.{name}.models -- and to the SAME place in")
        print("        config.py:DEFAULTS, or the next backfill reports it as a dead key.")
        show(cfg, args.config)
        return 1

    roles = cfg.get("models") or {}
    want = [r.strip() for r in args.roles.split(",") if r.strip()] if args.roles else list(roles)
    missing = [r for r in want if r not in roles]
    if missing:
        print(f"[FATAL] no such role(s): {', '.join(missing)}")
        return 1

    before = collections.Counter(roles[r].get("model") for r in want)
    if len(before) == 1 and args.model in before:
        print(f"already on {args.model}; nothing to do")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join("data", "retired", f"{stamp}_set_model")
    os.makedirs(out_dir, exist_ok=True)
    shutil.copy(args.config, out_dir)

    for r in want:
        roles[r]["model"] = args.model
    json.dump(cfg, io.open(args.config, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"{args.config}: {len(want)} role(s) -> {args.model}")
    print(f"  was: {', '.join(f'{k} x{v}' for k, v in before.most_common())}")
    print(f"  resolves as: {name}->{slug}")
    print(f"  previous config: {out_dir}")
    print()
    print("Now: python tools/smoke.py, then restart.cmd <character>.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
