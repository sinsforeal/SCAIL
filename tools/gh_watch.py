"""Watch our PRs and issues on outside repos; file a scail tracker issue for every new reply.

The User 10-27 16:11: "create a tracked issue if he replies on github again so it doesn't go unseen for so long."
Covers every issue or PR authored by ME in each repo of REPOS: issue comments, PR review comments, reviews,
and state changes (closed, merged, reopened). Anything not written by ME becomes one tracker issue, owner scail.
State: var/gh_watch.json (seen ids, last state per item). First run (no state file) only records, files nothing.
Run: pythonw tools/gh_watch.py (scheduled task SCAIL_gh_watch, every 15 min); `--dry` prints instead of filing.
"""
import json
import os
import subprocess
import sys
from datetime import datetime

ME = "owner"
REPOS = ["flamingrickpat/private-machine"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "var", "gh_watch.json")
LOG = os.path.join(ROOT, "logs", "gh_watch.log")
# t.cmd's own target, called direct: through cmd.exe a "&" or "|" in his comment would break or inject
TRACKER = [r"F:\REPS2\Meta_Orchestrator\.venv\Scripts\python.exe", r"F:\REPS2\Meta_Orchestrator\tools\tracker\t.py"]
NO_WINDOW = 0x08000000


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def gh(path):
    r = subprocess.run(["gh", "api", "--paginate", path], capture_output=True, text=True, encoding="utf-8",
                       creationflags=NO_WINDOW, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip()[:300]}")
    out = r.stdout.strip()
    if not out:
        return []
    # --paginate concatenates JSON arrays as "][": join them into one list
    return json.loads(out.replace("]\n[", ",").replace("][", ","))


def events(repo):
    """Yield (key, item_number, title, kind, author, url, body_or_state) for every reply and state on our items."""
    items = gh(f"search/issues?q=repo:{repo}+author:{ME}&per_page=100")
    if isinstance(items, dict):
        items = items.get("items", [])
    elif items and isinstance(items[0], dict) and "items" in items[0]:
        items = [i for page in items for i in page["items"]]
    for it in items:
        n, title, is_pr = it["number"], it["title"], "pull_request" in it
        for c in gh(f"repos/{repo}/issues/{n}/comments?per_page=100"):
            yield (f"ic{c['id']}", n, title, "comment", c["user"]["login"], c["html_url"], c.get("body") or "")
        if is_pr:
            for c in gh(f"repos/{repo}/pulls/{n}/comments?per_page=100"):
                yield (f"rc{c['id']}", n, title, "review comment", c["user"]["login"], c["html_url"], c.get("body") or "")
            for c in gh(f"repos/{repo}/pulls/{n}/reviews?per_page=100"):
                yield (f"rv{c['id']}", n, title, f"review {c.get('state', '').lower()}", c["user"]["login"],
                       c["html_url"], c.get("body") or "")
            pr = gh(f"repos/{repo}/pulls/{n}")
            state = "merged" if pr.get("merged_at") else pr.get("state")
        else:
            state = it.get("state")
        yield (f"st{n}", n, title, "state", "", it["html_url"], state)


def file_issue(repo, n, title, kind, author, url, text, dry):
    short = " ".join(text.split())[:300]
    t = f"GitHub {repo}#{n}: {author or 'state'} {kind}: {short[:90]}"
    desc = f"{url}\nOn: {title}\n{author} ({kind}): {short}\nAnswer him on GitHub, then close with the reply link."
    if dry:
        print("WOULD FILE:", t, "|", desc)
        return
    r = subprocess.run(TRACKER + ["new", t, "--owner", "scail", "--trigger", "reply now (the User 10-27 16:11)",
                        "--label", "tree:scail", "--ref", url, "-d", desc], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW, timeout=120)
    log(f"filed rc={r.returncode} {t} :: {(r.stdout or r.stderr).strip()[-200:]}")
    if r.returncode != 0:
        raise RuntimeError(f"tracker new failed rc {r.returncode}")


def main():
    dry = "--dry" in sys.argv
    first = not os.path.exists(STATE)
    st = {"seen": [], "state": {}} if first else json.load(open(STATE, encoding="utf-8"))
    seen = set(st["seen"])
    for repo in REPOS:
        for key, n, title, kind, author, url, body in events(repo):
            if kind == "state":
                sk = f"{repo}#{n}"
                old = st["state"].get(sk)
                if old != body:
                    if old is not None and not first:
                        file_issue(repo, n, title, "state", "", url, f"{old} -> {body}", dry)
                    st["state"][sk] = body
                continue
            sk = f"{repo}:{key}"
            if sk in seen:
                continue
            if author != ME and not first:
                file_issue(repo, n, title, kind, author, url, body, dry)
            seen.add(sk)
    st["seen"] = sorted(seen)
    if not dry:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
        os.replace(tmp, STATE)
    log(f"ok first={first} seen={len(seen)} items={len(st['state'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # logged; the next run tries again
        log(f"error {e!r}")
        sys.exit(1)
