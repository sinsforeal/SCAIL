"""One-off repairs of a live save, run at boot, once, for every character.

A repair here is not a migration and not a fixture: it is a fault that
reached the record and has to come out of it, keyed on a flag in the save so
the second boot does nothing. The old text of every row it changes is copied
to `data/retired/<timestamp>_<name>/` first -- superseded material is kept,
never deleted -- and the counts go in the log.
"""
import datetime
import io
import json
import os

import logger
from sim import roster
from sim.thread import TIME_STAMP_HEAD

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _retired(name):
    d = os.path.join(ROOT, "data", "retired",
                     datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + name)
    os.makedirs(d, exist_ok=True)
    return d


def _strip_labels(text):
    """The record's own clock label off a stored message, wherever it starts
    a line -- and nothing else.

    The words stay, including the ones the model wrote as the NEXT record
    entry with a stamp minutes in the future: they were sent, he read them,
    and a save that disagrees with his phone is the worse record. What comes
    out is the furniture: `[Fri 04 Sep 11:49 - read ... - you, to him]` at the
    head of the message that reached him this morning, `[Thu 01:24]` in front
    of the second line of one of hers from 2026-08-30, and the two labels
    inside a single spoken turn of 2026-09-01 that holds three turns' text."""
    s = str(text or "")
    out = TIME_STAMP_HEAD.sub("", s).strip()
    return out if out else s


def strip_stamps_once(app):
    """The record's own label, taken off the messages it reached.

    Her turns in the thread carried the app's label until 2026-09-04 and the
    model copied it; `Persona._clean` stripped it from the answer, and the one
    that got past the cleaner the morning the stamp form gained the date was
    sent and stored with the label in front of it. This takes it off the
    stored rows -- her messages, and her own turns in the exchanges with her
    people, wherever in them the label starts a line -- and asks the hub to
    correct its copy of any message it can still reach. Flagged in the save as
    `stamps_stripped_once`; the second boot returns at once."""
    store = app.store
    try:
        if store.get("stamps_stripped_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the stamp pass did not run: {type(e).__name__}: {e}")
        return
    try:
        msgs, turns = [], []
        with store.lock:
            rows = store.conn.execute(
                "SELECT id, ts, text, tg_id FROM messages WHERE role != 'user' AND text LIKE '%[%'").fetchall()
        for r in rows:
            old = str(r["text"] if hasattr(r, "keys") else r[2])
            new = _strip_labels(old)
            if new != old and new:
                msgs.append({"id": (r["id"] if hasattr(r, "keys") else r[0]),
                             "ts": (r["ts"] if hasattr(r, "keys") else r[1]),
                             "tg_id": (r["tg_id"] if hasattr(r, "keys") else r[3]),
                             "old": old, "new": new})
        chat = store.get("cast_chat", []) or []
        for ex in chat:
            for t in ex.get("turns") or []:
                if not roster.is_self(app.config, str(t.get("who") or "")):
                    continue
                for field in ("ja", "text"):
                    old = str(t.get(field) or "")
                    new = _strip_labels(old)
                    if old and new != old and new:
                        turns.append({"date": ex.get("date"), "hm": t.get("hm"), "field": field,
                                      "old": old, "new": new})
                        t[field] = new
        if not msgs and not turns:
            store.set("stamps_stripped_once", {"ts": app.clock.now_ts(), "messages": 0, "turns": 0})
            return
        d = _retired("stamps")
        name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
        with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"messages": msgs, "turns": turns}, f, ensure_ascii=False, indent=1)
        with store.lock:
            for m in msgs:
                store.conn.execute("UPDATE messages SET text=? WHERE id=?", (m["new"], m["id"]))
            store.conn.commit()
        if turns:
            store.set("cast_chat", chat)
        store.set("stamps_stripped_once", {"ts": app.clock.now_ts(),
                                           "messages": len(msgs), "turns": len(turns), "kept": d})
        logger.log(f"[repair] the record's own label taken off {len(msgs)} message(s) and "
                   f"{len(turns)} turn(s); the old text is in {os.path.relpath(d, ROOT)}")
        # the messenger keeps its own copy of the chat and it is what he reads
        edit = getattr(app.tg, "edit_message", None)
        for m in msgs:
            if not (edit and m.get("tg_id")):
                continue
            try:
                ok = edit(int(m["tg_id"]), m["new"])
                logger.log(f"[repair] message {m['id']} in the messenger: "
                           + ("corrected" if ok else "not corrected (it may be too old to edit)"))
            except Exception as e:
                logger.log(f"[repair] message {m['id']} not corrected in the messenger: {type(e).__name__}")
    except Exception as e:
        logger.log(f"[repair] the stamp pass failed: {type(e).__name__}: {e}")


def share_recaps_once(app):
    """Every page this character's save holds about the world, copied into the
    machine's one store.

    Until 2026-09-04 the cache of what an episode contains was a table in each
    character's own save, so both bots watching his media player fetched,
    digested and judged the same episode separately. The store is now the
    machine's (`machine/retrievals.py`) and the table is her record of what she
    was told. This carries what each save already holds across, so the pages
    fetched before the change are not fetched again: the first character's
    rows and the second's end up in one place, and where both hold a row for
    one thing the later fetch wins. Flagged in the save as `recaps_shared_once`;
    the second boot returns at once."""
    store = app.store
    shared = getattr(app, "retrievals", None)
    if shared is None:
        return
    try:
        if store.get("recaps_shared_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the shared-recaps pass did not run: {type(e).__name__}: {e}")
        return
    try:
        from sim.recap import Recap
        with store.lock:
            have = [r[1] for r in store.conn.execute("PRAGMA table_info(recaps)")]
            if not have:
                store.set("recaps_shared_once", {"ts": app.clock.now_ts(), "rows": 0})
                return
            cols = [c for c in ("title", "ja", "kind", "ep", "text", "source", "fetched_at",
                                "judged", "confidence", "candidates", "reason", "anchor",
                                "scenes", "archive") if c in have]
            rows = store.conn.execute(
                f"SELECT {','.join(cols)} FROM recaps ORDER BY id").fetchall()
        n = 0
        for r in rows:
            d = dict(zip(cols, r))
            key = str(d.get("ja") or d.get("title") or "").strip()
            text = str(d.get("text") or "")
            if not key or not text:
                continue
            ep = int(d.get("ep") or 0)
            kind = Recap._pool_kind(d.get("kind"), ep)
            judged = int(d.get("judged") or 0)
            conf = str(d.get("confidence") or "") or ("judged" if judged else "provisional")
            meta = {"title": d.get("title") or "", "ja": d.get("ja") or "", "kind": kind,
                    "ep": ep, "confidence": conf, "reason": str(d.get("reason") or "")[:400],
                    "anchor": str(d.get("anchor") or "")[:300],
                    "archive": str(d.get("archive") or "")[:200]}
            for j in ("candidates", "scenes"):
                v = d.get(j)
                if isinstance(v, str) and v:
                    try:
                        v = json.loads(v)
                    except ValueError:
                        v = []
                meta[j] = list(v or [])
            got = shared.put_if_newer(Recap.SHARED_POOL, Recap._shared_key(kind, key, ep),
                                      text[:4000], source=str(d.get("source") or ""),
                                      meta=meta, judged=judged,
                                      fetched_at=float(d.get("fetched_at") or 0))
            if got is not None:
                n += 1
        store.set("recaps_shared_once", {"ts": app.clock.now_ts(),
                                         "read": len(rows), "copied": n})
        logger.log(f"[repair] {n} of {len(rows)} page(s) about the world copied from her save "
                   f"into the machine's store; it now holds {shared.total()}")
    except Exception as e:
        logger.log(f"[repair] the shared-recaps pass failed: {type(e).__name__}: {e}")


# The one row of the first character's save that the recall role invented,
# quoted so the pass is keyed on its content and cannot take anything else.
# Written 2026-09-06 19:39 her time on the cue below, at clarity `hazy`,
# against the role's own instruction "Never invent a memory to please him":
# no excerpt it was given mentions the title, and the exchange it describes
# never happened (the trace is
# `data/retired/20260906_1831_yanineko_check/REPORT.md` §1).
INVENTED_RECALL = {
    "cue": "The smoking cat anime, i don't think ive even seen that one",
    "memory_starts": "The smoking cat anime... that's the one you said you'd watch with me ages ago",
}


def drop_invented_recall_once(app):
    """The invented memory, out of the record it should never have entered.

    Keyed on the row's own content rather than on its position, so a save that
    does not hold it is untouched and a re-run does nothing. What comes out is
    copied to `data/retired/<timestamp>_invented_recall/` first. Flagged in
    the save as `invented_recall_dropped_once`."""
    store = app.store
    try:
        if store.get("invented_recall_dropped_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the invented-recall pass did not run: {type(e).__name__}: {e}")
        return
    try:
        rows = list(store.get("recalls", []) or [])
        keep, gone = [], []
        for r in rows:
            if (str(r.get("cue") or "").strip() == INVENTED_RECALL["cue"]
                    and str(r.get("memory") or "").startswith(INVENTED_RECALL["memory_starts"])):
                gone.append(r)
            else:
                keep.append(r)
        if gone:
            d = _retired("invented_recall")
            name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
            with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(gone, f, ensure_ascii=False, indent=1)
            store.set("recalls", keep)
        store.set("invented_recall_dropped_once",
                  {"ts": app.clock.now_ts(), "dropped": len(gone), "kept": len(keep)})
        if gone:
            logger.log(f"[repair] {len(gone)} invented memory of an exchange that never happened "
                       f"taken out of what she remembers on cue; {len(keep)} left, and the old "
                       f"row is in {os.path.relpath(d, ROOT)}")
    except Exception as e:
        logger.log(f"[repair] the invented-recall pass failed: {type(e).__name__}: {e}")


# the openings of the habit facts `sim/anime_sense.py` writes from his
# anime history; a blind character's save is searched for these by text
HABIT_FACT_STARTS = (
    "His anime history:", "His favorite seiyuu", "The seiyuu he has clearly taken to",
    "His favorite anime characters", "His all-time favorite anime",
    "Behaviour and taste differ for him", "He watches anime mostly",
    "By hours watched his anime", "He is not a binger", "He scores anime",
)

# what the phone look and the profile wrote about him, keyed in kv
HIS_KV = ("him_profile", "phone_account", "phone_last_live", "phone_last_fingerprint",
          "phone_last_active_wall", "anime_habits_date")


def retire_his_digests_once(app):
    """A character whose sheet says she cannot see him holds nothing of his
    machine.

    Until 2026-09-07 `sees_him: none` was read by the pick and the persona
    only, so Rena's process digested his screen six times and wrote nine
    habit facts from his anime history. The sections are off by the existence
    table now; this takes what they wrote out of her save -- every digest, the
    kv the look and the profile keep, and the facts whose text is one of the
    habit templates -- into `data/retired/<timestamp>_his_digests/` first.
    Nothing happens on a character who sees him. Flagged in the save as
    `his_digests_retired_once`."""
    store = app.store
    try:
        ex = app.config.character.existence
        if str(getattr(ex, "sees_him", "digest") or "digest").lower() != "none":
            return
        if store.get("his_digests_retired_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the his-digests pass did not run: {type(e).__name__}: {e}")
        return
    try:
        with store.lock:
            digests = [dict(r) for r in store.conn.execute("SELECT * FROM digests ORDER BY ts").fetchall()]
            facts = [dict(r) for r in store.conn.execute("SELECT * FROM user_facts ORDER BY ts").fetchall()
                     if str(r["fact"] or "").startswith(HABIT_FACT_STARTS)]
        kv = {k: store.get(k) for k in HIS_KV if store.get(k) is not None}
        if digests or facts or kv:
            d = _retired("his_digests")
            name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
            with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
                json.dump({"digests": digests, "user_facts": facts, "kv": kv}, f, ensure_ascii=False, indent=1)
            with store.lock:
                store.conn.execute("DELETE FROM digests")
                for r in facts:
                    store.conn.execute("DELETE FROM user_facts WHERE id=?", (r["id"],))
                for k in kv:
                    store.conn.execute("DELETE FROM kv WHERE key=?", (k,))
                store.conn.commit()
        store.set("his_digests_retired_once",
                  {"ts": app.clock.now_ts(), "digests": len(digests), "facts": len(facts), "kv": sorted(kv)})
        if digests or facts or kv:
            logger.log(f"[repair] she cannot see him, and her save held {len(digests)} digest(s) of his "
                       f"machine, {len(facts)} habit fact(s) from his anime history and {len(kv)} kv "
                       f"row(s) of the look; all of it is out, in "
                       f"{os.path.relpath(d, ROOT)}")
    except Exception as e:
        logger.log(f"[repair] the his-digests pass failed: {type(e).__name__}: {e}")


def retire_his_reflections_once(app):
    """What a blind character THOUGHT about his machine, out of her save.

    The digests are gone (`retire_his_digests_once`), but on 2026-09-07 her
    reflect role had already written two private thoughts quoting his notes
    by name, kept in kv `reflections` (about: him) and mirrored as `reflect`
    events, and the psychological primitives had counted his screen as her
    watching him. Once, for a character whose sheet answers `sees_him: none`;
    what comes out is copied to `data/retired/<timestamp>_his_reflections/`.
    Flagged `his_reflections_retired_once`."""
    store = app.store
    try:
        ex = app.config.character.existence
        if str(getattr(ex, "sees_him", "digest") or "digest").lower() != "none":
            return
        if store.get("his_reflections_retired_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the his-reflections pass did not run: {type(e).__name__}: {e}")
        return
    try:
        refl = list(store.get("reflections", []) or [])
        gone = [r for r in refl if str(r.get("about") or "").lower() == "him"]
        keep = [r for r in refl if str(r.get("about") or "").lower() != "him"]
        heads = [str(r.get("thought") or "")[:40] for r in gone if r.get("thought")]
        with store.lock:
            evs = [dict(r) for r in store.conn.execute(
                "SELECT * FROM events WHERE kind='reflect' ORDER BY ts").fetchall()]
        evs = [e for e in evs if any(h and h in str(e.get("text") or "") for h in heads)]
        prim = store.get("primitives", {}) or {}
        him = dict(prim.get("him") or {})
        touched = bool(him.get("_log")) or any(float(v or 0) for k, v in him.items() if k != "_log" and not isinstance(v, (list, dict)))
        if gone or evs or touched:
            d = _retired("his_reflections")
            name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
            with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
                json.dump({"reflections": gone, "events": evs, "primitives_him": him}, f, ensure_ascii=False, indent=1)
            if gone:
                store.set("reflections", keep)
            if evs:
                with store.lock:
                    for e in evs:
                        store.conn.execute("DELETE FROM events WHERE id=?", (e["id"],))
                    store.conn.commit()
            if touched:
                prim["him"] = {k: (0.0 if isinstance(v, float) else ([] if isinstance(v, list) else v))
                               for k, v in him.items()}
                store.set("primitives", prim)
        store.set("his_reflections_retired_once",
                  {"ts": app.clock.now_ts(), "reflections": len(gone), "events": len(evs), "primitives": touched})
        if gone or evs or touched:
            logger.log(f"[repair] she cannot see him, and her save held {len(gone)} thought(s) about his "
                       f"machine, {len(evs)} reflect event(s) of them and the primitives' count of her "
                       f"watching him; all of it is out, in {os.path.relpath(d, ROOT)}")
    except Exception as e:
        logger.log(f"[repair] the his-reflections pass failed: {type(e).__name__}: {e}")


# Everything the two earlier passes left behind, keyed in kv. Each of these is
# a row about a man the character's own sheet says she has no chat with and no
# window on: how his mood read this tick, when his machine first went active,
# how much of her day was about him, what she predicted he would do, the score
# of how much she is investing in him, the meters derived for him, and the
# three rows the app on her phone kept about looking. The sections that write
# them are all switched off by the existence table now, so nothing puts them
# back.
NO_HIM_KV = ("his_mood", "his_first_active", "him_share", "foresight", "care_history",
             "relationship_derived", "phone_use", "phone_last_look_ts", "phone_debt_done",
             "phone_last_consumed_id", "phone_last_active_wall")


def retire_him_residue_once(app):
    """The last of him out of the save of a character who has neither a chat
    with him nor sight of him.

    The digests went (`retire_his_digests_once`) and the thoughts about them
    went (`retire_his_reflections_once`), and what was left was the arithmetic
    around them: eleven kv rows, a sentiment row on him at all zeros, the
    questions she opened about what she had seen on his screen, and a flag on
    a title in her watchlist saying he watches it. None of it was being written
    any more and all of it was still there, and two of the questions were open
    -- a question is a thing she is carrying, not a record of one.

    A watchlist row is not deleted: the title is hers, she chose it and wrote
    why. The claim that it is HIS comes off it and the old row is kept.

    Once, for a character whose sheet answers `sees_him: none` or
    `with_him: none`; what comes out is copied to
    `data/retired/<timestamp>_him_residue/`. Flagged
    `him_residue_retired_once`."""
    store = app.store
    try:
        ex = app.config.character.existence
        blind = str(getattr(ex, "sees_him", "digest") or "digest").lower() == "none"
        alone = str(getattr(ex, "with_him", "chat") or "chat").lower() == "none"
        if not (blind or alone):
            return
        if store.get("him_residue_retired_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the him-residue pass did not run: {type(e).__name__}: {e}")
        return
    try:
        kv = {k: store.get(k) for k in NO_HIM_KV if store.get(k) is not None}
        sent = store.get("sentiments", {}) or {}
        him_sent = {k: sent[k] for k in list(sent) if str(k).lower() == "him"}
        qs = list(store.get("questions", []) or [])
        watch = list(store.get("watchlist", []) or [])
        flagged = [dict(w) for w in watch if isinstance(w, dict) and w.get("his")]
        if not (kv or him_sent or qs or flagged):
            store.set("him_residue_retired_once", {"ts": app.clock.now_ts(), "kv": [], "questions": 0})
            return
        d = _retired("him_residue")
        name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
        with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"kv": kv, "sentiments_him": him_sent, "questions": qs,
                       "watchlist_flagged_his": flagged}, f, ensure_ascii=False, indent=1)
        if kv:
            with store.lock:
                for k in kv:
                    store.conn.execute("DELETE FROM kv WHERE key=?", (k,))
                store.conn.commit()
        if him_sent:
            store.set("sentiments", {k: v for k, v in sent.items() if str(k).lower() != "him"})
        if qs:
            # every question in the file is about him: the section that writes
            # them (`wonder`) is the relationship's and is off for her
            store.set("questions", [])
        if flagged:
            store.set("watchlist", [{k: v for k, v in w.items() if k != "his"}
                                    if isinstance(w, dict) else w for w in watch])
        store.set("him_residue_retired_once",
                  {"ts": app.clock.now_ts(), "kv": sorted(kv), "sentiments_him": bool(him_sent),
                   "questions": len(qs), "watchlist_unflagged": len(flagged)})
        logger.log(f"[repair] nothing of him is hers to hold, and her save held {len(kv)} kv row(s) "
                   f"about him, {len(qs)} open question(s) about him, {len(him_sent)} sentiment row "
                   f"on him and {len(flagged)} watchlist title(s) flagged as his; all of it is out, "
                   f"in {os.path.relpath(d, ROOT)}")
    except Exception as e:
        logger.log(f"[repair] the him-residue pass failed: {type(e).__name__}: {e}")


def retire_his_mood_once(app):
    """The row saying what mood HE is in, out of the save of a character whose
    sheet says she has no chat with him.

    `retire_him_residue_once` took this row out once and flagged the save, and
    the section that writes it was still on: the state role asked her every
    tick what he sounded like, and on 2026-09-08 at 06:51 it answered with a
    null line, which `str()` turned into the four-letter word "None" and the
    guard let through. The section is assigned to `with_him` now
    (`Config.REQUIRES`) and the guard reads a null as nothing, so this is the
    one row that was written in between.

    Once, keyed `his_mood_retired_once`; what comes out is copied to
    `data/retired/<timestamp>_his_mood/`."""
    store = app.store
    try:
        ex = app.config.character.existence
        if str(getattr(ex, "with_him", "chat") or "chat").lower() != "none":
            return
        if store.get("his_mood_retired_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the his-mood pass did not run: {type(e).__name__}: {e}")
        return
    try:
        row = store.get("his_mood")
        if row is None:
            store.set("his_mood_retired_once", {"ts": app.clock.now_ts(), "row": None})
            return
        d = _retired("his_mood")
        name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
        with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"his_mood": row}, f, ensure_ascii=False, indent=1)
        with store.lock:
            store.conn.execute("DELETE FROM kv WHERE key=?", ("his_mood",))
            store.conn.commit()
        store.set("his_mood_retired_once", {"ts": app.clock.now_ts(), "row": row})
        logger.log(f"[repair] she has no chat with him, and her save held a row saying what mood he "
                   f"was in ({str(row)[:80]}); it is out, in {os.path.relpath(d, ROOT)}")
    except Exception as e:
        logger.log(f"[repair] the his-mood pass failed: {type(e).__name__}: {e}")


def key_pages_by_id_once(app):
    """Pages filed under a title two works share, re-filed under the work.

    Until 2026-09-04 a page about an episode was named by its Japanese title
    and the episode number, in the machine's store and in her save alike.
    MyAnimeList gives the 2006 one-episode Example Show OVA and the 2007
    television run the identical Japanese title, so both hashed to
    `anime|エグザンプル|ep1`, and the television series' first episode was
    served as the OVA's to both characters -- with the right id on the row
    she kept, which is why nothing downstream caught it.

    Two passes, both keyed in the save so the second boot does nothing:

    * her own `recaps` table gets the work's id written onto every row whose
      title his list resolves without ambiguity, so a reader that knows which
      edition it wants can no longer be handed the other one;
    * the machine's store keeps every row it can, and moves ONLY the rows
      whose title is carried by more than one entry of his list -- the
      collisions, which is the whole of the fault. A row under a title only
      one work has is still read by a caller with no id (her own watchlist
      carries none), so nothing that was paid for is paid for twice.

    Nothing is deleted: the old key's row is written under the new key and
    then dropped, and the whole of what moved is copied to
    `data/retired/<timestamp>_page_keys/` first."""
    store = app.store
    kb = getattr(app, "anime_kb", None)
    shared = getattr(app, "retrievals", None)
    try:
        if store.get("pages_keyed_by_id_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the page-key pass did not run: {type(e).__name__}: {e}")
        return
    try:
        from sim.recap import Recap

        def resolve(title):
            """(aid, media type) when his list holds exactly one entry of that
            name; (None, "") when it holds none or more than one."""
            if kb is None or not str(title or "").strip():
                return None, ""
            try:
                cands = kb.resolve_candidates(title)
            except Exception:
                return None, ""
            if len(cands) != 1:
                return None, ""
            return int(cands[0]["aid"]), str(cands[0].get("type") or "")

        # ---- her own rows: the id written on, nothing moved
        local, ambiguous = [], []
        with store.lock:
            have = [r[1] for r in store.conn.execute("PRAGMA table_info(recaps)")]
            rows = (store.conn.execute("SELECT id, title, ja, kind, ep, aid FROM recaps").fetchall()
                    if "aid" in have else [])
        for r in rows:
            rid, title, ja, kind, ep = (r[0], r[1] or "", r[2] or "", r[3] or "", int(r[4] or 0))
            if r[5] or Recap._pool_kind(kind, ep) != "anime" or ep < 1:
                continue
            aid, mt = resolve(title)
            if not aid:
                ambiguous.append((rid, title, ja, ep))
                continue
            local.append({"id": rid, "title": title, "ja": ja, "ep": ep, "aid": aid, "type": mt})
        if local:
            with store.lock:
                for row in local:
                    store.conn.execute("UPDATE recaps SET aid=? WHERE id=?", (row["aid"], row["id"]))
                store.conn.commit()

        # ---- the machine's rows: only a colliding title moves
        moved, kept = [], 0
        if shared is not None:
            try:
                with shared.lock:
                    srows = [dict(x) for x in shared.con.execute(
                        "SELECT * FROM retrievals WHERE kind=?", (Recap.SHARED_POOL,)).fetchall()]
            except Exception as e:
                logger.log(f"[repair] the machine's store was not read: {type(e).__name__}")
                srows = []
            for row in srows:
                key = str(row.get("key") or "")
                try:
                    meta = json.loads(row.get("meta") or "{}")
                except ValueError:
                    meta = {}
                ep = int(meta.get("ep") or 0)
                if not key.startswith("anime|") or ep < 1 or meta.get("aid"):
                    kept += 1
                    continue
                title = str(meta.get("title") or "")
                try:
                    cands = kb.resolve_candidates(title) if kb is not None else []
                except Exception:
                    cands = []
                if len(cands) < 2:
                    # one work of that name, or none this mirror can place: the
                    # key still names it, and a reader with an id checks that
                    # it does before using the row (`Recap._resolves_to`)
                    kept += 1
                    continue
                aid, mt = int(cands[0]["aid"]), str(cands[0].get("type") or "")
                new = Recap._shared_key(meta.get("kind") or "anime", meta.get("ja") or title,
                                        ep, aid, mt or "any")
                if new == key:
                    kept += 1
                    continue
                shared.put_if_newer(Recap.SHARED_POOL, new, row.get("text") or "",
                                    source=row.get("source") or "",
                                    meta=dict(meta, aid=aid, media_type=mt or "any"),
                                    judged=int(row.get("judged") or 0),
                                    fetched_at=float(row.get("fetched_at") or 0),
                                    by=row.get("by") or "")
                shared.drop(Recap.SHARED_POOL, key)
                moved.append({"from": key, "to": new, "title": title, "ep": ep,
                              "aid": aid, "text": (row.get("text") or "")[:4000],
                              "candidates": [c["aid"] for c in cands]})
        if local or moved:
            d = _retired("page_keys")
            name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
            with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
                json.dump({"her_rows_given_an_id": local,
                           "her_rows_left_without_one": ambiguous,
                           "moved_in_the_machine_store": moved}, f,
                          ensure_ascii=False, indent=1)
        store.set("pages_keyed_by_id_once",
                  {"ts": app.clock.now_ts(), "hers": len(local), "hers_unresolved": len(ambiguous),
                   "moved": len(moved), "kept": kept})
        logger.log(f"[repair] page keys: {len(local)} of her own row(s) now name the work's id, "
                   f"{len(ambiguous)} could not be placed on his list; "
                   f"{len(moved)} row(s) in the machine's store re-filed under an id because "
                   f"their title belongs to more than one work, {kept} left as they are"
                   + ("".join(f"; {m['from']} -> {m['to']}" for m in moved) if moved else ""))
    except Exception as e:
        logger.log(f"[repair] the page-key pass failed: {type(e).__name__}: {e}")


def drop_wrong_editions_once(app):
    """A thing she knows by name whose text is another edition's story.

    Both saves hold `anime:1480` (the 2006 one-episode Example Show OVA) and
    `anime:2604` (the 2007 television run) with byte-identical 269-character
    texts under the shared name エグザンプル, because the page store was keyed
    on the Japanese title alone. The OVA's is the series' first episode and
    is simply false about the work it names: `KnownThings.remove_part` takes
    the part off, and the row goes with it, having no other part.

    General rather than named: any two things she knows about a work whose
    parts are byte-identical are one page filed twice, and the one whose id
    the page does NOT belong to is the wrong one. Flagged in the save as
    `wrong_editions_dropped_once`."""
    store = app.store
    kb = getattr(app, "anime_kb", None)
    try:
        if store.get("wrong_editions_dropped_once"):
            return
    except Exception as e:
        logger.log(f"[repair] the edition pass did not run: {type(e).__name__}: {e}")
        return
    try:
        from sim.known import KnownThings
        known = KnownThings(app.config, store, app.clock)
        rows = [r for r in known._all() if str(r.get("key") or "").startswith("anime:")]
        # the same text under two ids: one of them was fetched for the other
        by_text = {}
        for r in rows:
            for p in r.get("parts") or []:
                by_text.setdefault((str(p.get("label") or ""), str(p.get("text") or "")), []).append(r)
        taken = []
        for (label, _text), holders in by_text.items():
            if len(holders) < 2 or not label:
                continue
            ids = []
            for r in holders:
                try:
                    ids.append((int(str(r["key"]).split(":", 1)[1]), r))
                except (ValueError, IndexError):
                    continue
            if len(ids) < 2:
                continue
            # whose page is it? The row whose source page was fetched for the
            # OTHER work is the one to take the part off. With his mirror
            # here, the entry with more episodes is the one an episode-guide
            # page with a next-episode preview belongs to; without it, nothing
            # is touched, because guessing would delete the true row.
            if kb is None:
                continue
            eps = {}
            for aid, _r in ids:
                try:
                    eps[aid] = int((kb.entry(aid) or {}).get("eps") or 0)
                except Exception:
                    eps[aid] = 0
            keep = max(eps, key=lambda a: eps[a])
            for aid, r in ids:
                if aid == keep or not eps.get(aid):
                    continue
                if eps[aid] >= eps[keep]:
                    continue
                if known.remove_part(r["key"], label):
                    taken.append({"key": r["key"], "label": label, "kept": f"anime:{keep}",
                                  "episodes": eps})
        store.set("wrong_editions_dropped_once",
                  {"ts": app.clock.now_ts(), "taken": len(taken), "rows": len(rows)})
        if taken:
            d = _retired("wrong_editions")
            name = os.path.splitext(os.path.basename(getattr(app.args, "db", "") or "save"))[0]
            with io.open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(taken, f, ensure_ascii=False, indent=1)
            logger.log("[repair] " + "; ".join(
                f"{t['key']} lost its {t['label']}: the same text is {t['kept']}'s, "
                f"which has {t['episodes'].get(int(t['kept'].split(':')[1]))} episode(s)"
                for t in taken))
    except Exception as e:
        logger.log(f"[repair] the edition pass failed: {type(e).__name__}: {e}")
