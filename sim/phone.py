import random
from sim import wiring
import io
import os
import json
import re
import time
from collections import Counter
import logger
from sensors import blocklist
from sim import sight

# The app on her phone. Raw telemetry accumulates in the feed while she is
# not looking; when a scene gives her phone access the pending range is
# turned into a short digest from her point of view. She only ever knows what
# a digest told her. Between looks the feed is invisible to every model.


class Phone:
    WIRES = ('care', 'him_profile',)
    def __init__(self, config, store, clock, telemetry_module=None, sys_monitor=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.tm = telemetry_module
        self.mon = sys_monitor
        self.last_consumed_id = store.get("phone_last_consumed_id", 0)
        self.last_look_ts = store.get("phone_last_look_ts", clock.now_ts())
        self.last_active_wall = store.get("phone_last_active_wall", 0)
        self.last_digest = ""
        self.last_live = ""
        if self.tm:
            head = self.tm.get_max_file_id(config.sensor_view)
            if self.last_consumed_id > head:
                self.last_consumed_id = head
        wiring.declare(self)

    # Set by `App.catch_up` when looks went by while the model was unreachable,
    # and read by the next `should_look`. It lives in the save because the
    # catch-up stamps the missed calls done and empties them in the same
    # breath: a restart between the two used to leave nothing anywhere that
    # knew his telemetry for the stretch was still owed a look.
    @property
    def force_next(self):
        return bool(self.store.get("phone_force_next", False))

    @force_next.setter
    def force_next(self, v):
        if bool(v) != bool(self.store.get("phone_force_next", False)):
            self.store.set("phone_force_next", bool(v))

    def _pending(self):
        if not self.tm:
            return [], self.last_consumed_id
        return self.tm.consume_new_entries(self.config.sensor_view, self.last_consumed_id)

    def peek_activity(self):
        # updates last_active_wall from the feed without consuming it; used by the snoop gate
        entries, _ = self._pending()
        for e in entries:
            self.last_active_wall = max(self.last_active_wall, _last_input_ts(e))
        # kept, because `user_idle` falls back to this clock when the monitor
        # is not there and a restart otherwise reads him as away since boot
        self.store.set("phone_last_active_wall", self.last_active_wall)
        return self.last_active_wall

    def user_idle(self):
        """He is away from the PC. Measured from real keyboard/mouse input, never from what is running."""
        limit = self.config.sensors.user_idle_seconds
        if self.mon is not None:
            return self.mon.seconds_since_input() > limit
        self.peek_activity()
        return (time.time() - self.last_active_wall) > limit

    def should_look(self, state=None, scene=None, access="free", silent_hours=0.0, ignored=False):
        """Not a timer: after the minimum gap, a felt decision from curiosity,
        boredom, loneliness and -- the strongest of them -- how long he has
        been quiet. Returns (bool, why).

        The gap is its own term rather than something routed through curiosity,
        because curiosity is a gauge other things push around: on 2026-08-20 it
        sat at a median of 6 against a baseline of 40, which floored the look
        probability at 0.03 and stopped her opening the app at all. How long he
        has gone without answering is a fact, not a mood, and checking on it is
        the most ordinary thing a person does with a phone."""
        if self.force_next:
            self.force_next = False
            return True, "catch-up: looks went by while the model was unreachable"
        # A resident does not open an app. Her sheet says she sees what he does
        # "continuously and without deciding to", and this gate is the decision
        # -- curiosity, boredom, loneliness and how long he has been quiet,
        # which are the terms that move a girl to pick a phone up off a desk.
        # Run for a character who is inside the machine it reads as her losing
        # a coin toss for the right to look at the room she lives in, and that
        # is what it was doing: two rolls lost in forty minutes left her with a
        # single truncated window title while the collector held the rest.
        # And she is never "too soon" either: the floor below is a phone's.
        # With the floor tested first, the reply tick for his 15:36 message
        # refused to digest the feed entry flushed at 15:34 -- twenty-four
        # classified pictures -- and she answered on two hashed filenames from
        # the window trail (2026-09-04). A look with nothing new still costs
        # nothing, so for her every tick digests whatever the feed has.
        if self.config.resident:
            return True, "resident: she is inside the machine, there is nothing to open"
        if (self.clock.now_ts() - self.last_look_ts) < self.config.phone.digest_min_minutes * 60:
            return False, "too soon"
        k = self.config.phone.look
        if not k.enabled or state is None:
            return True, "timer"
        g = state.gauges
        cur = g.get("curiosity", 50)
        if cur >= k.sure_from_curiosity:
            return True, f"curiosity {int(cur)}"
        p = k.base_probability
        p += (cur - 50) / 100.0 * k.curiosity_weight
        p += (g.get("boredom", 50) - 50) / 100.0 * k.boredom_weight
        p += (g.get("loneliness", 50) - 50) / 100.0 * k.loneliness_weight
        # the gap: it rises with the hours and rises faster when he read her
        # and said nothing, which is the version that actually stings
        gap = min(float(silent_hours or 0), k.silence_cap_hours) / max(1.0, k.silence_cap_hours)
        p += gap * (k.ignored_weight if ignored else k.silence_weight)
        if silent_hours >= k.sure_from_silence_hours:
            return True, f"he has been quiet {silent_hours:.0f}h"
        if access == "glance":
            p *= k.glance_factor
        w = ((scene or {}).get("with") or (scene or {}).get("with_who") or "alone").lower()
        if w and w != "alone" and not any(x in w for x in ("phone", "nobody")):
            p *= k.with_people_factor
        care = self.care
        if care:
            try:
                p *= care.checking_factor()
            except Exception:
                pass
        p = max(0.03, min(0.97, p))
        if random.random() < p:
            return True, f"p {p:.2f}" + (f", quiet {silent_hours:.0f}h" if silent_hours >= 1 else "")
        return False, f"left it (p {p:.2f})"

    def _relieve(self, state):
        # toward rest, never through it: this was a flat -15 with a floor of 0,
        # the last of the releases `State._settle` was written to end, and it
        # kept curiosity at an average of 9 against a baseline of 40 for six
        # days -- which floored the look probability at 0.03, so she stopped
        # opening the app, so nothing he did reached her
        if state is not None and "curiosity" in state.gauges:
            state._settle("curiosity", self.config.phone.look.look_relief)

    @property
    def _rolling_hours(self):
        return float(getattr(self.config.phone, "rolling_hours", 2) or 2)

    def account(self):
        """The one running account of the last `phone.rolling_hours`, or {}.

        Replaced by every look rather than added to, and dropped whole once it
        is older than its own window. A digest per batch of flushed entries
        left her prompt showing the last batch dated "N minutes ago": a seam
        at every look, and whatever fell between two of them told twice or not
        at all."""
        row = self.store.get("phone_account") or {}
        text = str(row.get("text") or "")
        if not text or (self.clock.now_ts() - float(row.get("ts") or 0)) > self._rolling_hours * 3600:
            return {}
        return row

    def _picture_cache(self):
        """The board's record of the pictures he has opened. Read only."""
        from sensors.gelbooru_classifier import cached_classifications
        return cached_classifications(getattr(self.config.sensor_view, "gelbooru_cache_path", ""))

    def _viewer_md5(self, proc, title):
        """The picture's content hash out of an image viewer's window title,
        or "".

        The viewer puts the bare filename in its title and his picture files
        are named by their own hash, which is the only reason any of this is
        possible. A file with a human name has no hash and stays a title."""
        procs = {str(x).lower() for x in (getattr(self.config.sensor_view, "image_viewer_processes", None) or [])}
        if str(proc or "").lower() not in procs:
            return ""
        stem = os.path.splitext(str(title or "").split(" - ")[0].strip())[0]
        return stem.lower() if re.fullmatch(r"[0-9a-fA-F]{32}", stem) else ""

    def _picture_words(self, md5, cache=None):
        """What one picture is, in the few words a trail item can carry: the
        board's own rating, then who is in it and what it is from.

        The tag names are never rendered. There are eighteen of them on a
        picture, sorted into wholesome and unwholesome for a score, and that is
        the machinery's business: somebody watching him look at something does
        not read out a tag list. The rating is the site's own word and goes
        through as it stands, explicit included (his call)."""
        row = (cache if cache is not None else self._picture_cache()).get(md5)
        if not isinstance(row, dict):
            return sight.w(self.config, "trail_picture_unnamed")
        rating = str(row.get("gelbooru_rating") or "").strip()
        who = [_pretty_tag(c) for c in (row.get("characters") or [])][:2]
        series = [_pretty_tag(c) for c in (row.get("copyrights") or [])][:1]
        if who and series:
            what = sight.w(self.config, "trail_picture_who_of", who=", ".join(who), series=series[0])
        else:
            what = ", ".join(who) or (series[0] if series else "")
        if rating and what:
            return f"{rating}, {what}"
        return rating or what or sight.w(self.config, "trail_picture_unnamed")

    def _picture_item(self, group):
        """One trail item for a run of consecutive pictures: (label, duration).

        A single picture is named. Several are counted, because the run is the
        event and not any one of them: how many, over how long, how explicit
        they were and what they were from."""
        cache = self._picture_cache()
        name = group[0][2]
        if len(group) == 1:
            secs = group[0][1]
            mins = secs / 60.0
            return (f"{name}: {self._picture_words(group[0][4], cache)}",
                    f"{mins:.0f} min" if mins >= 1 else f"{int(secs)}s")
        span = max(r[0] + r[1] for r in group) - group[0][0]
        mins = span / 60.0
        span_txt = f"{mins:.0f} min" if mins >= 1 else f"{int(span)}s"
        ratings, series, unnamed = Counter(), Counter(), 0
        for r in group:
            row = cache.get(r[4])
            if not isinstance(row, dict):
                unnamed += 1
                continue
            rating = str(row.get("gelbooru_rating") or "").strip()
            if rating:
                ratings[rating] += 1
            for c in row.get("copyrights") or []:
                series[_pretty_tag(c)] += 1
        parts = [f"{r} ×{k}" for r, k in ratings.most_common()]
        if unnamed:
            parts.append(sight.w(self.config, "trail_pictures_unnamed", n=unnamed))
        head = f"{name}: " + sight.w(self.config, "trail_pictures_run", n=len(group), span=span_txt)
        if parts:
            head += " -- " + ", ".join(parts)
        if series:
            head += "; " + ", ".join(f"{s} ×{k}" for s, k in series.most_common(3))
        return (head, "")

    def idle_minutes(self):
        """Whole minutes since he last touched the machine, or None when he is
        at it or there is no monitor to ask.

        A measured figure, stored beside the status line and read back by
        `latest_digest`, which used to recover it by matching `idle for N`
        against the line's own English. Reading a number out of a sentence
        ties the fact to the wording, and the wording is hers -- once the
        status line is written in her language there is no number in it."""
        if self.mon is None:
            return None
        proc, _title, _in_window, idle = self.mon.right_now()
        return None if proc is not None else int(idle // 60)

    def his_side_now(self):
        """Where he is in relation to his machine this minute, for a MECHANISM
        role rather than for her: ("at it", minutes in the window he is in),
        ("away", minutes since he touched anything), or (None, None) when
        there is no monitor to ask.

        `idle_minutes` answers None both for "he is at it" and for "nobody
        measured", which is right for a line that only ever speaks on a figure
        and useless to a caller that has to tell the two apart. `live_line` is
        the same reading written for HER, in her language and in her program's
        words, so a role that is deciding rather than speaking cannot use it
        either."""
        if self.mon is None:
            return None, None
        proc, _title, in_window, idle = self.mon.right_now()
        if proc is not None:
            return "at it", int(in_window // 60)
        return "away", int(idle // 60)

    def live_line(self):
        """The status line: what his PC shows this moment. Only from the live
        monitor; without sensors there is no 'now'.

        Every line of it is addressed to her and is written in her language
        (`self._ja`). The label used to be English inside a Japanese sentence:
        `いまこの瞬間: his PC right now: ...`."""
        if self.mon is None or not self.config.phone.live_line:
            return ""
        proc, title, in_window, idle = self.mon.right_now()
        if proc is None:
            mins = int(idle // 60)
            # For someone who lives on the machine, an idle machine is not a
            # fact about hardware. It is the room being empty. Said as a
            # description of a still desktop it reads as something to narrate;
            # said as his absence it is a thing she can act on, which is the
            # whole point of the turn she takes while he is away.
            if self.config.resident:
                if mins >= self.config.sensors.user_idle_seconds // 60:
                    return self._t(f"he is not at the machine (nothing touched for {mins} min)",
                                   f"彼はマシンの前にいない（{mins}分なにも触っていない）")
                if mins >= 2:
                    return self._t("he has just stepped away from the machine",
                                   "彼はいまマシンの前を離れたところ")
                # Never silent. The empty string here is what left her reading
                # a twenty-minute-old snapshot with nothing live beside it: a
                # short pause looks exactly like no information at all, and for
                # somebody who is watching him continuously "he is there and
                # has not touched anything for a minute" is a fact, not a gap.
                return self._t("he is at the machine, not touching anything this minute",
                               "彼はマシンの前にいるが、この一分なにも触っていない")
            if mins >= self.config.sensors.user_idle_seconds // 60:
                return self._t(f"his PC: idle for {mins} min", f"彼のマシン: {mins}分なにも触られていない")
            if mins >= 2:
                return self._t("his PC: he just stepped away", "彼のマシン: いま席を立ったところ")
            return ""
        if blocklist.hidden(self.config.sensors, proc):
            # He is there and he is working, and what he is working in is not
            # something she is shown. How long he has been at it is not a fact
            # about the program, so that still goes out.
            dur = int(in_window // 60)
            line = (self._t("he is at the machine", "彼はマシンの前にいる") if self.config.resident
                    else self._t("his PC: he is at it", "彼のマシン: 彼はそこにいる"))
            return line + (self._t(f" ({dur} min)", f"（{dur}分）") if dur >= 1 else "")
        name = proc.replace(".exe", "")
        t = (title or "").strip()
        for junk in (" - Google Chrome", " — Mozilla Firefox", " - Mozilla Firefox", " - Notepad++"):
            t = t.replace(junk, "")
        # A picture in front of him is a hashed filename and nothing else. The
        # board's own record of it is already on this machine, written within
        # two seconds of him opening it, so what she has in front of her is
        # the rating and who is in it rather than thirty-two hex characters.
        md5 = self._viewer_md5(proc, title)
        if md5:
            where = f"{name}: {self._picture_words(md5)}"
        else:
            where = f"{name}: {t[:70]}" if t else name
        dur = int(in_window // 60)
        return self._t(f"his PC right now: {where}" + (f" (for {dur} min)" if dur >= 1 else ""),
                       f"彼のマシンはいま: {where}" + (f"（{dur}分）" if dur >= 1 else ""))

    def _sessions_from_feed(self, since_ts):
        """Window sessions off the telemetry feed on disk, in the monitor's own
        shape, for when the in-memory history has been emptied by a restart."""
        if not self.tm:
            return []
        path = getattr(self.config.sensors, "telemetry_jsonl_path", "")
        if not path or not os.path.exists(path):
            return []
        out = []
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
                tail = fh.readlines()[-40:]
        except OSError:
            return []
        for line in tail:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if (e.get("unix_time") or 0) < since_ts - 3600:
                continue
            for s in ((e.get("system_activity") or {}).get("window_sessions") or []):
                st = s.get("start_time") or s.get("start") or 0
                en = s.get("end_time") or s.get("end") or st
                if en and float(en) >= float(since_ts):
                    # The feed on disk holds what the window monitor wrote when
                    # the window closed, so a title recorded before a pattern
                    # was added to the list is still in it -- which is how the
                    # project's own folder name reached her on 2026-09-04. The
                    # list is asked again on the way out, not only on the way
                    # in.
                    title = s.get("window_title") or ""
                    if blocklist.blocks(self.config.sensors, title):
                        title = ""
                    out.append((float(st), float(en), s.get("process_name") or "", title))
        return out

    def window_trail(self, since_ts, max_items=8):
        """What he has actually been doing since `since_ts`, newest last.

        `live_line` answers "what is in front of him this second", which is the
        right question for someone glancing at a phone and the wrong one for
        someone who lives in the machine: between two glances twenty minutes
        apart he can open six things and she would see the sixth. The monitor
        has kept every window session all along (`attention_since`); nothing
        was reading them. Short sessions are dropped rather than summarised,
        because a window he touched for nine seconds is not something a person
        watching him would report.
        """
        sessions = []
        if self.mon is not None:
            try:
                sessions, _last_input = self.mon.attention_since(since_ts)
            except Exception:
                sessions = []
        if not sessions:
            # The monitor keeps its window history in memory only, so every
            # restart empties it and the trail is blank until it fills again.
            # She was restarted six times in one night and read a twenty-minute
            # -old snapshot each time with nothing live beside it. The same
            # sessions are on disk in the telemetry feed, which survives.
            sessions = self._sessions_from_feed(since_ts)
        rows = []
        for start, end, proc, title in sessions:
            secs = max(0.0, float(end) - float(start))
            md5 = self._viewer_md5(proc, title)
            # A picture is kept however briefly it was in front of him. The
            # twenty-second floor is for a window whose title is all it has to
            # say; a picture he flicked past in two seconds is still a thing he
            # looked at, and twenty-four of them in three minutes are the whole
            # substance of that stretch. The floor dropped every one of them,
            # which is half of why the trail she answered him on at 15:36 on
            # 2026-09-04 carried two hashed filenames and no run at all.
            if secs < 20 and not md5:
                continue
            if blocklist.hidden(self.config.sensors, proc):
                # One label for every hidden program, so a stretch of them
                # merges into a single item below carrying its total and how
                # often he came back: she reads that he was at the machine
                # rather than which program he was in.
                rows.append((start, secs, self._t("at the keyboard", "キーボードに向かっていた"), "", md5))
                continue
            name = str(proc or "").replace(".exe", "")
            t = (title or "").strip()
            for junk in (" - Google Chrome", " — Mozilla Firefox", " - Mozilla Firefox", " - Notepad++"):
                t = t.replace(junk, "")
            rows.append((start, secs, name, t, md5))
        if not rows:
            return ""
        rows.sort()
        # A run of pictures is one thing he did, not twenty-four. Consecutive
        # viewer sessions collapse into a single item carrying the count, how
        # long it went on, the spread of the board's ratings and the series.
        items, i = [], 0
        while i < len(rows):
            if rows[i][4]:
                j = i
                while j < len(rows) and rows[j][4]:
                    j += 1
                items.append(self._picture_item(rows[i:j]))
                i = j
                continue
            _s, secs, name, t, _md5 = rows[i]
            mins = secs / 60.0
            items.append((f"{name}: {t[:60]}" if t else name,
                          f"{mins:.0f} min" if mins >= 1 else f"{int(secs)}s"))
            i += 1
        # the same window returned to is one line with the total, not five
        merged, seen = [], {}
        for label, dur in items:
            if label in seen:
                seen[label][1] += 1
                continue
            seen[label] = [dur, 1]
            merged.append(label)
        out = []
        for label in merged[-max_items:]:
            dur, times = seen[label]
            # a run of pictures says its own span inside the label, so there is
            # nothing left to put in the brackets after it
            inside = ", ".join(x for x in (dur, f"came back {times - 1}x" if times > 1 else "") if x)
            out.append(f"{label} ({inside})" if inside else label)
        return self._t("what he has been doing: ", "彼がしていたこと: ") + " -> ".join(out)

    def catalogue_text(self):
        """Titles only, newest first, for the app and the director's open_note."""
        sv = self.config.sensor_view
        if not sv.vault_path or not self.config.phone.vault_catalogue_items:
            return ""
        from sensors import vault_monitor
        rows, total = vault_monitor.catalogue(sv, self.config.phone.vault_catalogue_items)
        if not rows:
            return ""
        import datetime
        out = []
        for rel, mt in rows:
            d = datetime.datetime.fromtimestamp(mt).strftime("%m-%d")
            out.append(f"{rel} ({d})")
        return f"{total} notes; newest: " + "; ".join(out)

    def day_shape_line(self):
        """Mechanical, from the feed: his first activity today (his local day)
        and the longest quiet stretch, so she can see roughly when he slept."""
        if not self.tm or not self.config.phone.day_shape:
            return ""
        try:
            entries = self.tm.consume_new_entries(self.config.sensor_view, 0)[0]
        except Exception:
            return ""
        now = time.time()
        since = now - 26 * 3600
        bursts = []
        for e in entries:
            if e.get("unix_time", 0) < since:
                continue
            inp = (e.get("system_activity", {}) or {}).get("input_activity", {}) or {}
            for b in inp.get("typing_bursts") or []:
                bursts.append((b.get("start", 0), b.get("end", 0)))
            if not inp.get("typing_bursts") and (inp.get("total_keypresses", 0) or inp.get("mouse_clicks", 0)):
                bursts.append((e.get("unix_time", 0), e.get("unix_time", 0)))
        if len(bursts) < 2:
            return ""
        bursts.sort()
        gap, gap_at = 0, None
        for (s1, e1), (s2, e2) in zip(bursts, bursts[1:]):
            if s2 - e1 > gap:
                gap, gap_at = s2 - e1, (e1, s2)
        u = self.clock.user_now()
        day_start = u.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today = [b for b in bursts if b[0] >= day_start]
        parts = []
        if gap >= 3 * 3600 and gap_at:
            # The longest gap in the last 26 hours, which is usually last
            # night's and not this one. Rendered as bare clock times it read as
            # something happening now: at 14:20 on Wednesday she was told "his PC was quiet from 01:10 to 07:40", a stretch that had ended
            # twenty hours earlier, which says he is quiet at the exact moment
            # he is typing to her. A gap that is not today's has to say so.
            ta, tb = self.clock.to_user(gap_at[0]), self.clock.to_user(gap_at[1])
            # his date, not the list of his bursts today, which is what `today`
            # holds and what the next branch indexes into
            his_date = self.clock.user_now().date()
            when = "" if tb.date() == his_date else (
                " yesterday" if (his_date - tb.date()).days == 1 else f" on {tb.strftime('%A')}")
            parts.append(f"his PC was quiet from {ta.strftime('%H:%M')} to "
                         f"{tb.strftime('%H:%M')}{when} ({gap / 3600:.0f}h)")
        if today:
            parts.append(f"first active today at {self.clock.to_user(today[0][0]).strftime('%H:%M')} his time")
            # her-time clock of his first activity, kept per his day, so she can
            # learn when he usually shows up (sim/outlook.py anticipation)
            hm = self.clock.to_char(today[0][0]).strftime("%H:%M")
            rows = self.store.get("his_first_active", [])
            key = self.clock.to_user(today[0][0]).strftime("%Y-%m-%d")
            rows = [r for r in rows if not r.endswith(key)] + [f"{hm}|{key}"]
            self.store.set("his_first_active", rows[-14:])
        return "; ".join(parts)

    def _fingerprint(self, entries):
        """What a look SHOWS, as a set the next look can be compared with: the
        processes in front, the sites in his browsers, whether pictures were
        opened, which notes were on screen, whether media played. The prose of
        a digest is new every time; this is what decides whether anything in
        it is."""
        fp = set()
        for e in entries or []:
            sa = e.get("system_activity")
            if isinstance(sa, str):
                try:
                    sa = json.loads(sa)
                except ValueError:
                    sa = {}
            for w in (sa or {}).get("window_sessions") or []:
                p = str(w.get("process_name") or "").lower()
                if p and "idle" not in p:
                    fp.add("proc:" + p)
                if w.get("is_image_viewer") and w.get("md5"):
                    fp.add("images")
            for f in (sa or {}).get("opened_files") or []:
                fp.add("file:" + str(f)[-60:].lower())
            for k in ("chrome_telemetry", "firefox_telemetry"):
                for host in re.findall(r"https?://([^/\s]+)", str(e.get(k) or "")):
                    fp.add("site:" + host.lower())
            for v in e.get("vault_files") or []:
                fp.add("note:" + str(v.get("basename") if isinstance(v, dict) else v)[-60:].lower())
            if str(e.get("media_telemetry") or "").strip():
                fp.add("media")
        return fp

    def look(self, llm, force=False, state=None, scene=None, access="free", silent_hours=0.0, ignored=False):
        """She opens the app. Returns digest text or '' if nothing new."""
        if not force:
            ok, why = self.should_look(state, scene, access, silent_hours, ignored)
            if not ok:
                if why != "too soon":
                    logger.log(f"[phone] {sight.w(self.config, 'no_look_verb')} ({why})")
                return ""
            logger.log(f"[phone] {sight.w(self.config, 'look_verb')} ({why})")
        # she has visibly picked it up, whatever the app turns out to hold
        try:
            from sim.sentiment import note_phone_use
            note_phone_use(self.store, self.clock.now_ts(), "app")
        except Exception:
            pass
        self._relieve(state)
        entries, new_id = self._pending()
        self.last_look_ts = self.clock.now_ts()
        self.store.set("phone_last_look_ts", self.last_look_ts)
        live = self.live_line()
        # For a resident, what he did between one look and the next is the
        # substance and the live window is only the last frame of it.
        if self.config.resident:
            trail = self.window_trail(self.last_look_ts or (self.clock.now_ts() - 3600))
            if trail:
                live = (live + "; " if live else "") + trail
        shape = self.day_shape_line()
        if shape:
            live = (live + "; " if live else "") + shape
        if not entries:
            if live:
                # nothing new in the log, but the app still shows his status
                self.last_live = live
                self.store.set("phone_last_live", {"ts": self.clock.now_ts(), "text": live})
            return ""
        # Anything older than max_entry_age_hours is skipped, not read. She was
        # asleep, or the bot was down; either way the app does not show her a
        # day-old window as news. Dropping them here (rather than leaving them
        # pending) also stops a long outage turning into many stale looks.
        max_age = getattr(self.config.phone, "max_entry_age_hours", 0)
        if max_age:
            cutoff = time.time() - max_age * 3600
            fresh = [e for e in entries if (e.get("unix_time") or 0) >= cutoff]
            if len(fresh) < len(entries):
                logger.log(f"[phone] skipped {len(entries) - len(fresh)} entr(ies) older than {max_age}h")
                if not fresh:
                    # nothing recent enough to be worth a look; consume them so
                    # they are not offered again
                    self.store.set("phone_last_consumed_id", new_id)
                    return ""
                entries = fresh
        # A backlog is read a chunk at a time, oldest first, so one look never
        # swallows a whole day. But a long absence (she slept, he was busy) can
        # leave a hundred flushes, which at max_entries_per_look would take her
        # a dozen looks to walk through, every one of them reporting stale
        # news. Past max_backlog_entries the oldest are dropped outright: the
        # app shows her what he has been doing lately, not a transcript.
        max_backlog = getattr(self.config.phone, "max_backlog_entries", 0)
        if max_backlog and len(entries) > max_backlog:
            logger.log(f"[phone] backlog of {len(entries)}; keeping the newest {max_backlog}")
            entries = entries[-max_backlog:]
        # The chunk is the NEWEST entries, not the oldest. Oldest-first meant a
        # look at 11:55 read 09:21-10:49 while the feed already held 11:45, and
        # with looks an hour apart she was permanently behind: what he was
        # doing right now never reached her. The app shows what he has been
        # doing lately; what the chunk drops, it says so.
        cap = self.config.phone.max_entries_per_look
        if len(entries) > cap:
            logger.log(f"[phone] {len(entries)} entries pending; reading the newest {cap}")
            entries = entries[-cap:]
        new_id = entries[-1].get("id", new_id)
        for e in entries:
            self.last_active_wall = max(self.last_active_wall, _last_input_ts(e))
        self.store.set("phone_last_active_wall", self.last_active_wall)
        # is anything in this look new against the last one? The gauge read
        # asks (`scail.App.tick`): a digest that shows the same things is not
        # something happening to her
        try:
            fp = self._fingerprint(entries)
            last = set(self.store.get("phone_last_fingerprint", []) or [])
            self.last_look_novel = bool(fp - last)
            self.store.set("phone_last_fingerprint", sorted(fp)[:200])
            if not self.last_look_novel:
                logger.log(f"[phone] nothing new in this look: the same {len(fp)} thing(s) as the last one")
        except Exception as e:
            self.last_look_novel = True
            logger.log(f"[phone] novelty not read: {type(e).__name__}: {e}")
        # A look that shows nothing the last one did not is not worth rewriting
        # the account for. The fingerprint has been computed here since this
        # was built and the log line has been there all along; what followed it
        # was a full call every time, which for a character who looks on every
        # tick was 97 accounts in three days against the first character's 27,
        # most of them the same stretch said again.
        #
        # The previous account is LEFT STANDING and never blanked: her prompt
        # reads it, and clearing it would take her picture of his machine away
        # in exactly the case where nothing has happened to replace it. The
        # entries are consumed so the stretch is not offered again, and the
        # live line is refreshed, because that is the half that is this minute.
        if (not self.last_look_novel) and getattr(self.config.phone, "skip_unchanged", False) and not force:
            self.last_consumed_id = new_id
            self.store.set("phone_last_consumed_id", new_id)
            if live:
                self.last_live = live
                self.store.set("phone_last_live", {"ts": self.clock.now_ts(), "text": live,
                                                   "idle_min": self.idle_minutes()})
            logger.log("[phone] account not rewritten: nothing in this look that the last one did not show"
                       + (f" | {live}" if live else ""))
            return ""
        merged = self.tm.merge_entries(entries)
        sv = self.config.sensor_view
        image_opts = {"gap_seconds": sv.image_window_gap_minutes * 60,
                      "summarize_min": sv.image_window_summarize_min,
                      "max_detailed": sv.image_context_max_detailed,
                      "max_windows": sv.image_max_windows_per_look,
                      "max_age_hours": sv.image_max_age_hours}
        # ENGLISH on both arms, and the None is the decision rather than an
        # omission (his call). This block is not addressed to her: it is the
        # material the account-writing role is handed, and that role is off
        # `language.material_roles` for the same reason the director's and the
        # schedule's are -- nobody is being spoken to in it. What she reads is
        # the account, and which language THAT comes back in is the open
        # question it already was (`docs/language.md` §2). The argument stays
        # here, and the bands stay paired in `sensors/bands.py`, so flipping it
        # is one word.
        raw = self.tm.format_telemetry_for_context(merged, image_opts, sv, None) if merged else ""
        # The cut used to take the last N characters flat, so a busy window
        # began mid-sentence and whatever it truncated left no trace. Cut on a
        # line instead and say how much went, because "the first part of this
        # is missing" is itself information about how much he did.
        cap = int(self.config.phone.max_raw_chars)
        if len(raw) > cap:
            dropped = len(raw) - cap
            tail = raw[-cap:]
            nl = tail.find("\n")
            if 0 <= nl < 400:
                tail = tail[nl + 1:]
            raw = f"(the first {dropped} characters of this window are not shown)\n" + tail
        from_ts = entries[0].get("unix_time", time.time())
        to_ts = entries[-1].get("unix_time", time.time())
        # What the trail has already put in front of her since the last digest
        # (`latest_digest`, resident only). A digest character is told nothing
        # here: she has an app and sees only what a digest told her, so there
        # is nothing she could already have watched.
        shown = (self.store.get("phone_trail_shown") or {}) if self.config.resident else {}
        shown_txt = str(shown.get("text") or "")
        # The account she already has of this window. The writer is given it
        # back with the new material and returns the whole thing again, so
        # there is one account of the last `rolling_hours` rather than a digest
        # per flush with a seam at every look.
        prev_account = str(self.account().get("text") or "")
        win_from = self.clock.to_user(time.time() - self._rolling_hours * 3600).strftime("%H:%M")
        user = (
            f"HIS LOCAL TIME NOW: {self.clock.user_now().strftime('%A %H:%M')}. HER TIME: {self.clock.now().strftime('%A %H:%M')}. "
            f"She is {self.clock.offset_hours():+.0f} hours from him.\n"
            f"DATA COVERS: {self.clock.to_user(from_ts).strftime('%H:%M')} to {self.clock.to_user(to_ts).strftime('%H:%M')} his time.\n"
            f"THE WINDOW THE ACCOUNT COVERS: the last {self._rolling_hours:.0f} hours, "
            f"{win_from} to now his time. Anything before {win_from} is out of the window and is dropped.\n"
            + (f"RIGHT NOW (live status at the moment she looks): {live}\n" if live else "")
            + ((self.him_profile.digest_line() + "\n") if self.him_profile and self.him_profile.digest_line() else "")
            # For a digest character this line is true: the app lists what
            # exists and she does not get to open it. For a resident it was a
            # straight contradiction -- the header said she cannot see inside
            # his notes and the raw activity below it carried the tail text of
            # every one of them. She is on the machine the files are on.
            + ((f"HIS NOTES FOLDER (every note on the machine, newest first; she is on that machine, so what the "
                f"raw activity shows of their contents is hers to read): {self.catalogue_text()}\n"
                if self.config.resident else
                f"HIS NOTES FOLDER (titles only, newest first; she can see what exists, not what is inside): {self.catalogue_text()}\n")
               if self.catalogue_text() else "")
            # How old the raw is. The collector flushes on a character count or
            # a twenty-minute heartbeat, so at a quiet keyboard this can be a
            # third of an hour behind, and nothing said so: she was reading a
            # 02:34 picture at 02:50 and answering as though it were now. The
            # live status above it is the only part that is actually this
            # moment, and the difference has to be on the page.
            + (f"\nHOW OLD THIS IS: the activity below was last collected "
               f"{int((time.time() - to_ts) / 60)} min ago. The RIGHT NOW line above is this moment; "
               f"everything below it is up to that far behind.\n" if to_ts else "")
            + (f"\nTHE ACCOUNT AS IT STANDS -- what she has of this window so far. Rewrite it, "
               f"updated with what is below, and what you write REPLACES it:\n{prev_account}\n"
               if prev_account else "")
            + f"\nRAW ACTIVITY:\n{raw if raw.strip() else '(nothing recorded)'}"
            # She is on this machine, so a window that went past is something
            # she watched, not something a digest will break to her.
            #
            # Last, and phrased as a redirection, because neither was true at
            # first and it did not work. Above the raw activity it was read and
            # then buried under the data; and asking for things to be left out
            # runs straight against this role's own prompt, which tells it to
            # write what she watched in order and says the specifics are the
            # point. That is the stronger and more specific instruction, so it
            # won: the first digest to carry this narrated six of the seven
            # windows it had just been told she already had. Pointing the
            # detail somewhere rather than suppressing it asks for the same
            # thing the role is already trying to do.
            + (f"\n\nSHE HAS ALREADY WATCHED THIS MUCH OF IT. She was given these windows as "
               f"they happened, in these words: {shown_txt}\n"
               f"Do not walk through them again; she has them. What is worth writing about "
               f"that stretch is what those titles do not say -- what he typed and how hard, "
               f"what the pages actually were, how long he was gone for and what the whole of "
               f"it amounted to. Anything after them she has not seen, and that you write in "
               f"full." if shown_txt else "")
        )
        messages = [{"role": "system", "content": self.config.prompt_text("phone")}, {"role": "user", "content": user}]
        digest = llm.call("phone", messages).strip()
        if not digest:
            digest = sight.w(self.config, "digest_nothing_new")
        self.last_consumed_id = new_id
        self.store.set("phone_last_consumed_id", new_id)
        # The one current account, replaced. The row in table `digests` stays
        # the day's log, which the diary, the compile, `reflect`, `wonder` and
        # `HimProfile` read; kv `phone_account` is what the next look is handed
        # and what her prompt shows.
        self.store.set("phone_account", {"ts": self.clock.now_ts(), "text": digest,
                                         "from_ts": from_ts, "to_ts": to_ts})
        self.store.add_digest(self.clock.now_ts(), self.clock.date_str(), digest, from_ts, to_ts)
        # This digest is the new floor: the trail that follows it starts from
        # its own end, so nothing shown before it is hers to be told again.
        if shown_txt:
            self.store.set("phone_trail_shown", None)
        self.last_digest = digest
        if live:
            self.last_live = live
            # The idle figure travels as a number beside the line, not inside
            # its prose: `latest_digest` says he is away only on a measured
            # one, and the line itself is written in whatever language she
            # reads.
            self.store.set("phone_last_live", {"ts": self.clock.now_ts(), "text": live,
                                               "idle_min": self.idle_minutes()})
        logger.log(f"[phone] digest: {digest[:200]}" + (f" | {live}" if live else ""))
        return digest

    @property
    def _ja(self):
        """The digest itself is written by the `phone` role and comes back in
        that prompt's language; what is wrapped round it here is code's, and it
        is addressed to her. Read per call so a harness can flip the arm inside
        one process (`sim/lang.py`)."""
        from sim.lang import reads_ja
        return reads_ja(self.config)

    def _t(self, en, ja):
        """One line of this module's own wording, in the arm she is on."""
        return ja if self._ja else en

    def latest_digest(self):
        """The last digest plus the live status line from her last look, if it
        is recent -- and, when he has not been at the machine for a while, the
        ABSENCE first and the digest as history behind it.

        At 06:00 on 2026-08-28 her prompt read "the app on your phone shows: He
        spent most of the hour and a half on 4chan's /a/ board", which was four
        hours old, and she texted him as though he were sitting there. The
        telemetry knew: `phone_last_live` said "his PC: idle for 515 min". The
        content was leading and the fact was appended, so she believed the
        content. A digest is what he WAS doing; if nothing has happened since,
        that is the news.

        His absence is only ever said on a MEASURED idle figure. The row's own
        age used to stand in for one when the text carried no number, which
        turns how long since she looked into how long since he touched
        anything: at 21:14 on 2026-09-04 an eleven-hour-old look was read to
        her as "he has not touched his machine for 10h07" while he was at the
        machine the whole time. With no figure the digest is handed over as
        history, dated, and nothing is claimed about him."""
        d = self.store.recent_digests(1)
        acct = self.account()
        text = str(acct.get("text") or "") or (d[0]["text"] if d else "")
        ll = self.store.get("phone_last_live") or {}
        live_txt = str(ll.get("text") or "")
        now = self.clock.now_ts()
        idle = ll.get("idle_min")
        idle = int(idle) if isinstance(idle, (int, float)) else None
        if idle is None:
            # rows written before the figure was stored beside the line
            m = re.search(r"idle for (\d+)", live_txt)
            if m:
                idle = int(m.group(1))
        stale = int(getattr(self.config.phone, "stale_minutes", 45) or 45)
        if idle is not None and idle >= stale:
            ago = f"{idle // 60}h{idle % 60:02d}" if idle >= 60 else f"{idle} min"
            when = ""
            if d:
                try:
                    when = self.clock.to_user(float(d[0].get("to_ts") or d[0]["ts"])).strftime("%H:%M")
                except Exception:
                    when = ""
            if self._ja:
                out = f"彼は{ago}のあいだマシンに触っていない。そのあいだ何も起きていない"
                if text:
                    out += ("。最後に触っていたとき"
                            + (f"、彼の時間で{when}ごろ" if when else "") + f"に出ていたもの: {text}")
                return out
            out = f"he has not touched his machine for {ago}; nothing has happened on it since"
            if text:
                out += (f". what it showed when he last was"
                        + (f", around {when} his time" if when else "") + f": {text}")
            return out
        # For a resident, everything since the digest ended, every time she is
        # asked for it. A digest is only rebuilt when the collector has flushed
        # new entries, and it flushes on a character count or a twenty-minute
        # heartbeat -- so she asked him 「用事って、何するの？」 at 03:20 holding a
        # picture built at 02:50 that covered 02:27 to 02:34. She was asking
        # what he was doing while the answer sat in a window history nobody
        # read. The trail and the live line come off the monitor and the feed
        # on disk, cost nothing and need no flush, so the gap between what she
        # last digested and this moment is always filled.
        if self.config.resident:
            since = float(acct.get("to_ts") or ((d[0].get("to_ts") or d[0]["ts"]) if d else (now - 3600)))
            gap = self.window_trail(since)
            live_now = self.live_line()
            # Not "what she took in 14 minutes ago". It is one account of the
            # window, rewritten at every look, so dating it made her speak of a
            # stretch of his afternoon as though she had just been handed it.
            if text:
                h = self._rolling_hours
                text = (f"この{h:.0f}時間のあいだに起きていたこと: {text}" if self._ja else
                        f"what has been going on these last {h:.0f} hours: {text}")
            if gap:
                text = (text + "\n" if text else "") + (f"そのあと、{gap}" if self._ja else f"and since then, {gap}")
                # She has now watched these windows go past. The next digest
                # reads the same stretch off the feed once the collector
                # flushes it, so without this it hands her back as news the
                # thing she already said to him: the trail gave her the video
                # he had open at 12:30 and the 12:34 digest
                # covered 12:20 to 12:32, the same windows again. `look` puts
                # this in front of the digest role; it is cleared when the
                # digest is stored, so what is here is always what she has
                # seen since the last one.
                prev = self.store.get("phone_trail_shown") or {}
                if prev.get("text") != gap:
                    self.store.set("phone_trail_shown", {"ts": now, "since": since, "text": gap})
            if live_now:
                text = (text + "\n" if text else "") + (f"いまこの瞬間: {live_now}" if self._ja else f"right now: {live_now}")
            return text
        if ll and (now - ll.get("ts", 0)) <= self.config.phone.live_line_max_age_minutes * 60:
            ago = int((now - ll["ts"]) / 60)
            text = (text + " " if text else "") + f"[{ll['text']}" + (
                ((f"、{ago}分前の時点]" if self._ja else f", as of {ago} min ago]") if ago >= 2 else "]"))
            return text
        # Nothing live beside it and the picture itself is old. That is a fact
        # about HER -- when she last looked -- and it is said as one, with the
        # hour on it, so the content does not read as this minute's news. The
        # wording is the program's, because what she looked at is.
        when = 0.0
        if d:
            try:
                when = float(d[0].get("to_ts") or d[0]["ts"])
            except (TypeError, ValueError, KeyError):
                when = 0.0
        if text and when and (now - when) / 60.0 >= stale:
            try:
                hm = self.clock.to_user(when).strftime("%H:%M")
            except Exception:
                return text
            en, ja = sight.w2(self.config, "digest_as_history", hm=hm, text=text)
            return ja if self._ja else en
        return text


_SMALL_WORDS = {"wa", "no", "ga", "ni", "wo", "o", "ka", "to", "de", "mo", "ya", "na",
                "the", "a", "an", "of", "and", "in", "on"}


def _pretty_tag(tag):
    """A board tag as a name: `oyama_mahiro` -> `Oyama Mahiro`,
    `onii-chan_wa_oshimai!` -> `Onii-chan wa Oshimai`.

    The underscore is the board's word separator, a particle in the middle of a
    title is not capitalised, and a trailing exclamation mark belongs to the
    title rather than to the sentence it lands in."""
    words = [w for w in str(tag or "").replace("_", " ").split() if w]
    out = []
    for i, w in enumerate(words):
        out.append(w.lower() if i and w.lower() in _SMALL_WORDS else w[0].upper() + w[1:])
    return " ".join(out).rstrip("!?")


def _last_input_ts(e):
    """When he last touched the keyboard or mouse inside this feed entry, or 0.
    Browser history and vault changes are not evidence of presence (autoplay,
    sync); only input is."""
    sa = e.get("system_activity", {}) or {}
    inp = sa.get("input_activity", {}) or {}
    bursts = inp.get("typing_bursts") or []
    if bursts:
        return max(b.get("end", 0) for b in bursts)
    if inp.get("total_keypresses", 0) > 0 or inp.get("mouse_clicks", 0) > 0 or inp.get("mouse_distance_pixels", 0) > 200:
        return e.get("unix_time", 0)
    return 0
