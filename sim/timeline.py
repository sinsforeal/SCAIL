import json
from sim import chattext
import logger
from sim import existence
from sim import inflight
from sim import lang
from sim import sight


def _blank(v):
    """Is this field of a compile answer empty? A day that wrote nothing for a
    field and a day that never mentioned it look the same in JSON, and both
    mean "this answer has nothing to say here"."""
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, tuple, dict, set)):
        return not v
    return False


def merge_retry(first, second, asked_about):
    """The stored answer when the compile asked again about ONE field.

    Returns `(merged, from_second)` -- the answer to keep, and the names of
    the fields taken from the second call.

    The retry names the narrative and nothing else, but the role answers with
    the whole JSON, and the second answer is a fresh telling of the day rather
    than an edit of the first: on 2026-09-07 the second character's first
    answer carried fourteen facts about him and the second carried none, and
    the second is what was stored, so a day of facts about him exists nowhere
    in her record. So the retried field comes from the second answer and every
    other field is whichever answer HAS one, with the first preferred when
    both do -- the first answer is the one that was asked the whole question.
    """
    first = first if isinstance(first, dict) else {}
    second = second if isinstance(second, dict) else {}
    merged = dict(first)
    from_second = []
    if asked_about in second:
        merged[asked_about] = second[asked_about]
        from_second.append(asked_about)
    for k, v in second.items():
        if k == asked_about or _blank(v):
            continue
        if _blank(first.get(k)):
            merged[k] = v
            from_second.append(k)
    return merged, from_second


def compile_day(config, llm, store, clock, date_str, *a, **k):
    """The flag round the day (`sim/inflight.py`). The compile is minutes of
    model calls and the one thing a restart cannot pick up where it left
    off; the row it leaves behind is what tells the next process that a
    day was started and never told. `_redo_compile` reruns it only when
    the `days` row is still missing, so a compile killed after the day was
    saved is not paid for twice."""
    with inflight.job(store, "compile", about=date_str, redo={"date": date_str}):
        return _compile_day(config, llm, store, clock, date_str, *a, **k)


def _compile_day(config, llm, store, clock, date_str, state=None, records=None, diet=None, memory=None,
                 goals=None, self_memory=None, self_model=None, ledger=None, orbit=None, episodes=None):
    schedule = store.get_schedule(date_str)
    scenes = store.scenes_for_date(date_str)
    events = store.events_for_date(date_str)
    states = store.state_for_date(date_str)
    digests = store.digests_for_date(date_str)
    msgs = store.messages_for_date(date_str)
    known = store.user_facts()

    sched_txt = "\n".join(f"{b['start']}-{b['end']} {b['activity']} @ {b['location']}" for b in schedule["blocks"]) if schedule else "(none)"
    # the machine's own record of who was where: it outranks a scene that
    # put somebody on a train they were never on
    ledger_txt = ""
    if ledger:
        try:
            ledger_txt = ledger.day_text(date_str)
        except Exception:
            ledger_txt = ""
    if ledger_txt:
        sched_txt += ("\n\nTHE DAY'S LEDGER (the machine's record; a person marked NOT around was in no scene, "
                      "whatever a scene says -- write the day without them):\n" + ledger_txt)
    scenes_txt = "\n".join(f"[{s['hm']}] {s['location']} / {s['activity']} with {s['with_who']}. {s['sensory']}" for s in scenes) or "(none)"
    events_txt = "\n".join(f"[{clock.hm(e['ts'])}] ({e['kind']} s{e['salience']}) {e['text']}" for e in events) or "(none)"
    state_txt = "\n".join(f"[{clock.hm(s['ts'])}] {s['reasons']}" for s in states if s["reasons"]) or "(none)"
    digest_txt = "\n".join(f"[{clock.hm(d['ts'])}] {d['text']}" for d in digests) or sight.w(config, "timeline_none")
    her = str(getattr(config.character, "name", "her") or "her").upper()
    msg_txt = chattext.lines(msgs, clock, labels=("HIM", her)) or "(no messages exchanged)"
    # her talks with the people around her, verbatim. Before this the compile
    # saw his chat word for word and one gist line per exchange with anyone
    # else, so the day she remembered held everything he said and almost
    # nothing Rena did.
    from sim import talks
    talks_txt = talks.compile_rows(store, date_str)
    # The him-facts have been handed to this call since it was written and the
    # cast facts never were, so the compile could not tell what was new about
    # her own mother and had no way of seeing how little it had ever written.
    cast_known = memory.cast_facts_report() if memory else "(none)"
    # and what she is already carrying of her own. This was the one store the
    # compile wrote into blind: it was handed his facts and the cast's so it
    # would reinforce rather than duplicate, and her own memories were written
    # every night as if the record were empty, so a running theme got a fresh
    # row each time. Her memories of THIS date are left out, because a
    # recompile deletes them a moment later (`forget_day`) and the day would
    # otherwise be told not to write the very things it is about to lose.
    self_known = self_memory.recent_report(exclude_date=date_str) if self_memory else "(none)"
    cast_txt = records.cast_sheet(state.relationships, meters=False) if (records and state) else "(none)"
    arcs_txt = records.arcs_brief() if records else "(none)"
    places_txt = records.places_brief() if records else "(none)"

    user = (
        f"DATE: {date_str}\n\nSCHEDULE:\n{sched_txt}\n\nSCENES:\n{scenes_txt}\n\nEVENTS:\n{events_txt}\n\n"
        f"STATE NOTES:\n{state_txt}\n\n{sight.w(config, 'timeline_label')}\n{digest_txt}\n\nMESSAGES:\n{msg_txt}\n\n"
        f"HER TALKS WITH FRIENDS AND FAMILY TODAY (what was actually said; English is a gloss of the Japanese):\n{talks_txt}\n\n"
        f"CAST SHEET BEFORE TODAY:\n{cast_txt}\n\nPLACES ON RECORD: {places_txt}\n\nACTIVE ARCS:\n{arcs_txt}\n\n"
        f"FACTS ABOUT HIM ALREADY KNOWN:\n{json.dumps(known, ensure_ascii=False)}"
        + f"\n\nWHAT SHE ALREADY KNOWS ABOUT THE PEOPLE AROUND HER (do not write these again):\n{cast_known}"
        + f"\n\nWHAT SHE IS ALREADY CARRYING FROM RECENT DAYS (these memories exist; a day that is one more day of something already there says nothing new about it):\n{self_known}"
        + (f"\n\nWHAT SHE WOKE UP WANTING (settle each one against the record):\n{goals.brief()}" if goals else "")
    )
    messages = [{"role": "system", "content": config.prompt_text("timeline")}, {"role": "user", "content": user}]
    data, raw = llm.call_json("timeline", messages)
    if isinstance(data, dict) and isinstance(data.get("narrative"), list):
        data["narrative"] = "\n\n".join(str(x) for x in data["narrative"])
    # A day's prose can come back as one short paragraph while every other
    # field is full: the instruction asks for two to six paragraphs and the
    # schema is one JSON string, and the model resolves that either by
    # breaking the JSON or by writing almost nothing. 08-27 had the most
    # scenes of any day on record and got 556 characters covering its first
    # two hours. The prompt now says how to do both; this is the check that
    # the answer actually did, because a thin day is silent otherwise -- it
    # parses, it saves, and only the record months later shows the hole.
    c = config.timeline
    span = (f"{len(scenes)} scenes on the record, from {scenes[0].get('hm', '?')} to {scenes[-1].get('hm', '?')}"
            if scenes else f"{len(msgs)} messages on the record")
    for _ in range(getattr(c, "narrative_retries", 1)):
        narr = str((data or {}).get("narrative", "") or "") if isinstance(data, dict) else ""
        if len(narr) >= c.narrative_min_chars or len(scenes) < c.narrative_min_scenes:
            break
        logger.log(f"[timeline] narrative was {len(narr)} chars over {span}; asking again")
        # the language the prose goes out in, said again at the end of the
        # prompt. The system half carries it (`sim/lang.material_line`, this
        # role is one of `language.material_roles`), but the retry's own
        # English paragraph is the last thing the model reads, and the second
        # character's retry came back with an English summary on a character
        # who writes Japanese everywhere.
        ask = (f"The narrative is {len(narr)} characters and covers only part of the day. "
               f"There are {span}. Write the whole day again: two to six paragraphs in ONE "
               "JSON string with \\n\\n between them, following it from the first of them to the last. "
               "Same JSON, every field, nothing invented that the record does not show."
               + lang.material_line(config, "timeline"))
        again = messages + [{"role": "assistant", "content": raw or ""},
                            {"role": "user", "content": ask}]
        data2, raw2 = llm.call_json("timeline", again)
        if isinstance(data2, dict) and isinstance(data2.get("narrative"), list):
            data2["narrative"] = "\n\n".join(str(x) for x in data2["narrative"])
        if isinstance(data2, dict) and len(str(data2.get("narrative", "") or "")) > len(narr):
            data, from_second = merge_retry(data, data2, "narrative")
            kept = sorted(k for k in data if k not in from_second)
            logger.log("[timeline] the retry was asked about the narrative: "
                       + ", ".join(from_second) + " taken from the second answer"
                       + (f"; {len(kept)} field(s) kept from the first ({', '.join(kept)})"
                          if kept else "; the first answer had nothing else to keep"))
            # the answer of record is the merge, so a second round shows the
            # model what is being kept rather than its own emptied answer
            raw = json.dumps(data, ensure_ascii=False)
        else:
            break
    if not isinstance(data, dict) or not str(data.get("narrative", "")).strip():
        # never keep the raw answer as the day she remembers; the row is
        # marked so `/compile <date>` can redo it by hand
        logger.log(f"[timeline] COMPILE FAILED for {date_str}: no usable narrative ({len(raw or '')} chars raw); day marked, recompile with /compile {date_str}")
        store.save_day(date_str, clock.now_ts(), "(compile failed; recompile with /compile " + date_str + ")", "", [])
        return None
    new_facts = []
    for f in (data.get("new_user_facts") or []):
        if isinstance(f, dict):
            text, weight = str(f.get("fact", "")).strip(), f.get("weight", 2)
        else:
            text, weight = str(f).strip(), 2
        if not text:
            continue
        if memory:
            how = memory.add_fact(text, weight, source="day", date=date_str)
            if how == "new":
                new_facts.append(text)
            else:
                logger.log(f"[memory] fact reinforced: {text[:80]}")
        else:
            store.add_user_fact(clock.now_ts(), text)
            new_facts.append(text)
    # what he read in a visual novel today, as one fact about him. The
    # accounts of the day are already written (`sim/eroge.py`, at the moments
    # she answered him); this is the day's total time and the last of them,
    # and the raw lines were never anywhere to be summarised again.
    try:
        from sim.eroge import day_fact
        vn = day_fact(store, date_str)
        if vn and memory:
            memory.add_fact(vn, 2, source="eroge", date=date_str)
    except Exception as e:
        logger.log(f"[eroge] the day's fact was not kept: {type(e).__name__}")
    store.save_day(date_str, clock.now_ts(), data["narrative"], data.get("summary", ""), new_facts)
    # the day as cards: one per conversation, the shape and the exact lines
    # (sim/cards.py); the thread shows them once the day leaves verbatim
    if episodes is not None:
        try:
            episodes.write(date_str)
        except Exception as e:
            logger.log(f"[episodes] not written for {date_str}: {type(e).__name__}: {e}")
    if records and state:
        state.relationships = records.apply_cast(state.relationships, data.get("cast_updates"), data.get("new_people"), date_str)
        state.save()
        records.apply_places(data.get("places"), date_str)
        # the arcs belong to the one section that writes them, and a character
        # who does not keep her own world does not run it: without this the
        # compile went on writing notes onto arcs nothing may open or close
        if config.showrunner.enabled:
            records.apply_arc_notes(data.get("arc_notes"), date_str)
        records.age_threads()
    if diet:
        diet.add_things(data.get("her_things"), date_str)
    # her own life, kept the way her facts about him are kept
    if self_memory:
        # first, anything in the table she cannot read: the mechanisms that
        # write memories build their sentences in English, and for a character
        # who does not write English that has to be put right before she is
        # shown any of it (sim/self_memory.py)
        try:
            self_memory.repair()
        except Exception as e:
            logger.log(f"[self] the language pass over her memories did not run: {type(e).__name__}")
        # a day told again is the same day: the memories THIS call wrote last
        # time go, so they are not carried twice in two wordings. Only its own
        # (`source="day"`); the settlers below write their own memories of the
        # same date and are each guarded against running twice.
        try:
            gone = self_memory.forget_day(date_str, "day")
            if gone:
                logger.log(f"[self] {gone} memory(ies) of {date_str} replaced: the day was told again")
        except Exception as e:
            logger.log(f"[self] the day's old memories were kept: {type(e).__name__}: {e}")
        kept = again = 0
        for m in (data.get("memories") or [])[: config.self_memory.compile_max_per_day]:
            if isinstance(m, dict):
                text, w, feel = m.get("text", ""), m.get("weight", 2), ""
                val = m.get("valence", 0)
            else:
                text, w, feel, val = str(m), 2, "", 0
            if not str(text).strip():
                continue
            # a day that repeats something she already carries reinforces that
            # row rather than sitting beside it (`SelfMemory.add`: last_seen
            # bumped, mentions raised, the higher of the two weights kept), and
            # it is said in the log the way a reinforced fact about him is
            how = self_memory.add(date_str, text, w, feel, val, source="day")
            if how == "new":
                kept += 1
            elif how == "reinforced":
                again += 1
                logger.log(f"[self] a memory she already carries came round again: {str(text)[:80]}")
        if kept or again:
            logger.log(f"[self] {kept} thing(s) she will still be carrying from {date_str}"
                       + (f"; {again} more was another day of something she already carries" if again else ""))
    # the question nothing was asking: did she do what she woke up wanting,
    # and then what it costs her that she did not
    if goals:
        goals.settle(data.get("goals"), date_str, self_model, self_memory)
    # what she learned about the people around her, kept on the same curve
    # as what she learned about him
    if memory:
        kept = 0
        for f in (data.get("new_cast_facts") or [])[:10]:
            if not isinstance(f, dict):
                continue
            if memory.add_cast_fact(f.get("who", ""), f.get("fact", ""), f.get("weight", 2),
                                    source="day", date=date_str) == "new":
                kept += 1
        if kept:
            logger.log(f"[memory] {kept} new thing(s) she knows about people")
    # and the people those people belong to
    if orbit:
        try:
            orbit.update_at_compile(date_str, data.get("new_cast_facts"))
        except Exception as e:
            logger.log(f"[orbit] failed: {type(e).__name__}: {e}")
    claims = [str(x).strip() for x in (data.get("self_claims") or []) if str(x).strip()]
    if claims:
        old = store.get("self_claims", [])
        # a day told again replaces its own claims rather than adding a second
        # wording of them. The list is deduplicated by exact text, so a rerun
        # of the same day wrote the same disclosures in different words and
        # they all counted as new: `/compile 2026-09-03` twice took the record
        # from 86 rows to 96.
        before = {c["text"].lower() for c in old if c.get("date") != date_str}
        already_today = {c["text"].lower() for c in old if c.get("date") == date_str}
        rows = [c for c in old if c.get("date") != date_str]
        told = []
        for t in claims[:8]:
            if t.lower() in before:
                continue
            rows.append({"date": date_str, "text": t[:160]})
            if t.lower() not in already_today:
                told.append(t)
        old = rows
        store.set("self_claims", old[-120:])
        # Each of these is a thing he now holds of her that he did not hold
        # yesterday, which is the one event that closes the gap a diary opens
        # (sim/primitives.py:disclosed). Only the new ones: saying the same
        # thing twice tells him nothing the second time, and the deduplication
        # above already decides which is which. A day told again counts only
        # what its own earlier telling had not, so the meter does not ratchet
        # on a recompile.
        prim = getattr(state, "primitives", None) if state is not None else None
        # A claim is a thing SHE said about herself, to whoever she was
        # talking to. It is his holding it only if there is a chat with him:
        # a character with none had what she told her own oldest friend
        # written up as exposure to a man she has never spoken to.
        if prim is not None and told and existence.has_chat(config):
            try:
                him = state._him_key() or "him"
                for t in told:
                    prim.disclosed(him, t)
            except Exception as e:
                logger.log(f"[primitives] what she told him not counted: {type(e).__name__}: {e}")
    logger.log(f"[timeline] {date_str} compiled ({len(data['narrative'])} chars, {len(new_facts)} new facts)")
    return data


def compile_week(config, llm, store, clock, date_str, state=None):
    """Sunday: a first-person paragraph of how the week felt, from the day
    summaries, her diary and the gauge trend. Memory, not mutation: the
    bible is never touched."""
    import datetime
    days = store.recent_days(7)
    days_txt = "\n".join(f"{d['date']}: {d['summary'] or d['narrative'][:300]}" for d in days) or "(no days)"
    diary = [e for e in store.get("diary", []) if e["date"] >= (datetime.date.fromisoformat(date_str) - datetime.timedelta(days=7)).isoformat()]
    diary_txt = "\n\n".join(f"{e['date']}: {e['text'][:600]}" for e in diary) or "(she did not write this week)"
    gauges = state.gauge_line() if state else ""
    user = (f"WEEK ENDING {date_str}.\n\nTHE DAYS:\n{days_txt}\n\nHER DIARY THIS WEEK:\n{diary_txt}\n\nHOW SHE FEELS TONIGHT: {gauges}")
    system = config.role_system("weekly")
    text = llm.call("weekly", [{"role": "system", "content": system}, {"role": "user", "content": user}]).strip()
    if not text:
        return None
    wk = store.get("weekly_self", [])
    wk.append({"week_ending": date_str, "ts": clock.now_ts(), "text": text[:1500]})
    store.set("weekly_self", wk[-26:])
    logger.log(f"[weekly] {date_str}: {text[:160]}")
    return text
