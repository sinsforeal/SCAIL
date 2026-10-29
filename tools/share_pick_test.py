"""What the account does with a post she has just sent him, proved on a COPY
of the save with the judge and the browser stubbed out. Nothing is sent and
nothing real is written: the X store is redirected to a temporary directory.

    python tools/share_pick_test.py

What it shows, in order: a share whose judge says repost queues a like and a
repost; a share whose judge says like only queues the like and nothing else;
a judge that says neither queues nothing; an unreadable answer and an empty
taste both fall back to the old probability and say so in the log; and the
same pick runs on the scenery path, where a photograph she passed off as her
own came out of a real post.
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

from tools.dbcopy import copy_db as _copy_save  # noqa: E402

LOG = []
POST = {"id": "2100000000000000001", "author": "kesentm",
        "text": "夜の環七、信号が全部青だった", "url": "https://x.com/kesentm/status/2100000000000000001",
        "ts": 0}


def queued(store, kind):
    return [r for r in (store.get("x_action_queue") or []) if r.get("kind") == kind]


def main():
    tmpdb = os.path.join(tempfile.gettempdir(), "scail_share_pick_test.db")
    _copy_save("data/world.db", tmpdb)
    print(f"[test] copied data/world.db -> {tmpdb} (sqlite backup of a live save)")

    import logger
    logger.setup = lambda out_dir: None
    logger.finish = lambda: None
    logger.log_llm = lambda *a, **k: None
    logger.write_artifact = lambda *a, **k: None

    def cap(m, to_console=True):
        LOG.append(str(m))
    logger.log = cap

    # the account's own files go to a scratch directory: this test never
    # appends a row to the real action log
    xdir = os.path.join(tempfile.gettempdir(), "scail_share_pick_x")
    os.makedirs(xdir, exist_ok=True)
    for f in os.listdir(xdir):
        os.remove(os.path.join(xdir, f))
    from sensors import x_monitor as xm
    xm._paths = lambda config: {
        "feed": os.path.join(xdir, "feed.jsonl"), "seen": os.path.join(xdir, "seen.json"),
        "sessions": os.path.join(xdir, "sessions.json"), "actions": os.path.join(xdir, "actions.jsonl"),
        "likes": os.path.join(xdir, "likes.jsonl"), "likes_seen": os.path.join(xdir, "likes_seen.json"),
        "following": os.path.join(xdir, "following.json"), "followers": os.path.join(xdir, "followers.json"),
        "accounts": os.path.join(xdir, "accounts.json"), "status": os.path.join(xdir, "status.json"),
        "follow_changes": os.path.join(xdir, "follow_changes.jsonl"),
        "trends": os.path.join(xdir, "trends.json"),
    }

    import scail
    argv = sys.argv
    sys.argv = ["scail.py", "--config", "config.json", "--console", "--no-sensors", "--db", tmpdb]
    try:
        args = scail.parse_args()
    finally:
        sys.argv = argv
    app = scail.App(args)
    soc, cur, store = app.social, app.social.curation, app.store
    c = app.config.social
    print(f"[test] the pick is {'on' if app.config.curation.share_pick else 'off'}; "
          f"the fallback rolls {c.repost_shared_p:.2f} (link) / "
          f"{app.config.scenery.repost_sent_p:.2f} (photo); "
          f"reposts capped at {app.config.curation.max_reposts_per_day} a day")
    assert cur.llm is not None, "the account has no judge to put a share to"
    # a queue is only written when the account may act; nothing here reaches a
    # browser, and the test is about the verdict, not about whether he has
    # switched the account's hand off tonight
    app.config.sensor_view.x_actions_enabled = True

    # her taste has to have something in it, or the pick refuses by design
    store.set("x_taste", {POST["author"]: {"like": 3, "meh": 0, "dislike": 0}})
    verdicts = []

    def judge(answer):
        def fake_json(role, messages, max_tokens=None):
            assert role == "x_repost_judge", f"unexpected role {role}"
            verdicts.append(messages)
            return answer, ""
        app.llm.call_json = fake_json

    def one_share(label, answer, sid_suffix):
        """A fresh share, start to finish, through Social.resolve_share."""
        LOG.clear()
        store.set("x_action_queue", [])
        store.set("x_action_counts", {})
        store.set("x_shared", {})
        item = dict(POST, id=POST["id"][:-1] + sid_suffix, ts=app.clock.now_ts())
        item["url"] = f"https://x.com/{item['author']}/status/{item['id']}"
        store.set("x_shareable", [item])
        judge(answer)
        soc.resolve_share(item["id"])
        likes, reposts = queued(store, "like"), queued(store, "repost")
        print(f"\n{label}")
        for m in LOG:
            print("   log:", m)
        print(f"   queued: {len(likes)} like, {len(reposts)} repost")
        return likes, reposts

    # ---- 1. she wants it on her own timeline
    likes, reposts = one_share("1. THE JUDGE SAYS REPOST",
                               {"verdict": "repost", "why": "her kind of picture, she would have found it"}, "1")
    assert len(likes) == 1 and len(reposts) == 1, "a repost verdict did not queue both"
    assert any("her pick: repost" in m for m in LOG), "the log does not say it was her pick"
    user = verdicts[-1][1]["content"]
    print("   what the judge was given, first lines:")
    for line in user.splitlines()[:6]:
        print("     |", line[:100])
    assert "HOW IT REACHED HIM" in user and "sent him the link" in user, \
        "the judge was not told she had just sent it to him"
    assert "HER REACTIONS TO @kesentm" in user, "the judge was not given her taste"
    sheet = app.config.prompt_text("persona")
    jsys = verdicts[-1][0]["content"]
    print(f"   judge system prompt: {len(jsys)} chars, character sheet in it: {sheet[:200] in jsys}")
    assert sheet[:200] not in jsys, "the judge was handed her character sheet"

    # ---- 2. between the two of them and nowhere else
    likes, reposts = one_share("2. THE JUDGE SAYS LIKE ONLY",
                               {"verdict": "like", "why": "she sent it to him, not to everyone"}, "2")
    assert len(likes) == 1 and not reposts, "a like-only verdict still reposted"
    assert any("her pick: like only" in m for m in LOG)

    # ---- 3. neither
    likes, reposts = one_share("3. THE JUDGE SAYS NEITHER",
                               {"verdict": "none", "why": "she sent it to complain about it"}, "3")
    assert not likes and not reposts, "a 'neither' verdict still acted"
    assert any("her pick: neither" in m for m in LOG)

    # ---- 4. the judge cannot be read: the old roll, and the log says so
    likes, reposts = one_share("4. THE JUDGE ANSWERS SOMETHING CODE CANNOT READ", None, "4")
    rolled = [m for m in LOG if "no pick available" in m]
    print(f"   fallback line: {rolled[0] if rolled else '(none)'}")
    assert rolled, "an unreadable judge answer did not fall back to the roll"
    assert len(likes) == 1, "the fallback did not like it"

    # ---- 5. nothing of hers to judge with: the same fallback. Her declared
    # sheet is blanked the way it is for a character with no account, and her
    # reactions to the author are cleared, so there is no ground for a pick
    store.set("x_taste", {})
    store.set("x_verdicts", {})
    sheet_file = app.config.world.taste_file
    app.config.world.taste_file = ""
    try:
        likes, reposts = one_share("5. HER TASTE HAS NOTHING ON THE ACCOUNT",
                                   {"verdict": "repost", "why": "should never be asked"}, "5")
    finally:
        app.config.world.taste_file = sheet_file
    rolled = [m for m in LOG if "no pick available" in m]
    print(f"   fallback line: {rolled[0] if rolled else '(none)'}")
    assert rolled and "taste" in rolled[0], "an empty taste did not fall back to the roll"

    # ---- 6. the scenery path goes through the same pick
    LOG.clear()
    store.set("x_taste", {"tokyo_scene": {"like": 4, "meh": 0, "dislike": 0}})
    store.set("x_action_queue", [])
    store.set("x_action_counts", {})
    judge({"verdict": "repost", "why": "she would have this on her page anyway"})
    app.scenery.curation.act_on_shared(
        {"author": "tokyo_scene", "text": "夕方の商店街",
         "url": "https://x.com/tokyo_scene/status/2100000000000000009"},
        sent_as="she sent him the photograph out of this post as one of her own",
        like_on=bool(app.config.scenery.like_sent), repost_on=bool(app.config.scenery.repost_sent),
        roll_p=float(app.config.scenery.repost_sent_p), why="the post her photo came from")
    print("\n6. THE SCENERY PATH (A PHOTOGRAPH SHE PASSED OFF AS HER OWN)")
    for m in LOG:
        print("   log:", m)
    print(f"   queued: {len(queued(store, 'like'))} like, {len(queued(store, 'repost'))} repost")
    assert queued(store, "repost"), "the scenery path did not reach the pick"
    assert "as one of her own" in verdicts[-1][1]["content"], \
        "the judge was not told the photograph was passed off as hers"

    # ---- 7. nothing claims a repost the browser has not done
    q = queued(store, "repost")
    done = [a for a in xm.her_actions(app.config.sensor_view, "repost_done")]
    print("\n7. NOTHING SAYS IT WAS REPOSTED YET")
    print(f"   on the queue: {[(r['kind'], r['target']) for r in q]}")
    print(f"   rows saying the browser did it: {len(done)}")
    assert q and not done, "a repost was recorded before the browser confirmed it"

    print("\n[test] all clear")


if __name__ == "__main__":
    main()
