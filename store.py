import sqlite3
import json
import os
import threading

# world.db is the single save file. Everything the simulation knows about
# itself lives here; prompts are rebuilt from it every call.


class Store:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        # The scene thread the record is in. `main` is the ordinary thread; a
        # directed scene (`docs/2026-09-17_vn_stage_manager_scope.md`) gets its
        # own id, and messages written while it is active carry it. Kept here
        # rather than in kv so the readers that ask "what is happening now" get
        # the scene she is in without a kv read per call. Inert until something
        # sets it: every existing row is `main`.
        self.active_scene = "main"
        self._init()
        # a restart resumes the scene thread it was in. A save from before scene
        # threads has no key and is on the main thread.
        try:
            self.active_scene = str(self.get("active_scene", "main") or "main")
        except Exception:
            self.active_scene = "main"

    # scene threads
    def scene_threads(self):
        """Every scene thread in this save, the main thread first. A scene is a
        separate transcript, backlog and save that can be returned to
        (`docs/2026-09-17_vn_stage_manager_scope.md`). The list is kv, not a
        table: a scene is a handful of fields and the record itself is already
        partitioned by `messages.scene_id`."""
        threads = self.get("scene_threads", {}) or {}
        out = [{"id": "main", "title": "the main thread", "kind": "main", "created_ts": None}]
        for sid, row in sorted(threads.items(), key=lambda kv: float((kv[1] or {}).get("created_ts") or 0)):
            out.append({"id": str(sid), **(row or {})})
        return out

    def register_scene(self, scene_id, title, kind="directed", created_ts=None):
        """Put a scene in the list. Called when the stage manager starts one; the
        main thread is implicit and never registered."""
        sid = str(scene_id or "").strip()
        if not sid or sid == "main":
            return ""
        threads = self.get("scene_threads", {}) or {}
        threads[sid] = {"title": str(title or ""), "kind": str(kind),
                        "created_ts": float(created_ts or 0)}
        self.set("scene_threads", threads)
        return sid

    def set_active_scene(self, scene_id):
        """Which scene the record is in. Persisted, so a restart returns to it."""
        self.active_scene = str(scene_id or "main")
        self.set("active_scene", self.active_scene)
        return self.active_scene

    def _init(self):
        c = self.conn
        c.executescript("""
        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY, ts REAL, date TEXT, hm TEXT,
            location TEXT, activity TEXT, phone_access TEXT, with_who TEXT,
            sensory TEXT, inner TEXT, share_worthy INTEGER, events TEXT, raw TEXT);
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, ts REAL, date TEXT, kind TEXT, text TEXT, salience INTEGER);
        CREATE TABLE IF NOT EXISTS state_log (
            id INTEGER PRIMARY KEY, ts REAL, date TEXT, gauges TEXT, reasons TEXT);
        CREATE TABLE IF NOT EXISTS schedules (
            date TEXT PRIMARY KEY, ts REAL, blocks TEXT, notes TEXT);
        CREATE TABLE IF NOT EXISTS days (
            date TEXT PRIMARY KEY, ts REAL, narrative TEXT, summary TEXT, user_facts TEXT);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY, ts REAL, date TEXT, role TEXT, text TEXT,
            self_started INTEGER DEFAULT 0, delivered_ts REAL, read_ts REAL, tg_id INTEGER,
            scene_id TEXT DEFAULT 'main');
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY, ts REAL, date TEXT, text TEXT, from_ts REAL, to_ts REAL);
        CREATE TABLE IF NOT EXISTS user_facts (
            id INTEGER PRIMARY KEY, ts REAL, fact TEXT);
        CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY, text TEXT, status TEXT, people TEXT,
            created_ts REAL, updated_ts REAL, created_date TEXT, resolved_date TEXT);

        -- The exact prompt a reply she sent was drawn from: the whole
        -- chat-completion messages array, the model that answered it and the
        -- sampling settings, keyed to the first message row of the burst and
        -- naming all of them (`msg_ids`). A swipe re-runs THIS, never a
        -- prompt rebuilt now: her state has moved since and the question a
        -- swipe asks is what she would have said then.
        CREATE TABLE IF NOT EXISTS reply_prompts (
            msg_id INTEGER PRIMARY KEY, char TEXT, ts REAL, model TEXT,
            messages_json TEXT, params_json TEXT, msg_ids TEXT, text TEXT,
            sat INTEGER DEFAULT 0, reconstructed INTEGER DEFAULT 0);
        -- The answers to one frozen prompt. Number 0 is what she actually
        -- sent; the rest are draws he asked for. Only the one he sits reaches
        -- her record, so the thread never carries a version she did not send.
        CREATE TABLE IF NOT EXISTS swipes (
            msg_id INTEGER, n INTEGER, model TEXT, text TEXT, voice_path TEXT,
            ts REAL, prompt_tokens INTEGER, completion_tokens INTEGER,
            cached_tokens INTEGER, cost REAL, PRIMARY KEY (msg_id, n));
        -- The channel's latest frame by its temporary hub turn id. Delivery
        -- copies the final frame to vn_message_frames under the stable row id.
        CREATE TABLE IF NOT EXISTS vn_frames (
            turn_id INTEGER PRIMARY KEY, frame_json TEXT NOT NULL);
        -- Hub turn ids can repeat after a restart. The store message id is
        -- stable for one line across restarts and timeline replay.
        CREATE TABLE IF NOT EXISTS vn_message_frames (
            msg_id INTEGER PRIMARY KEY, frame_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vn_line_checkpoints (
            msg_id INTEGER PRIMARY KEY, checkpoint_id TEXT NOT NULL);
        """)
        # A save written before the rebuild existed has the table without its
        # last column. Added here rather than at the caller, so every reader
        # of the table gets it and no reader has to ask whether it is there.
        have = {r[1] for r in c.execute("PRAGMA table_info(reply_prompts)")}
        if "reconstructed" not in have:
            c.execute("ALTER TABLE reply_prompts ADD COLUMN reconstructed INTEGER DEFAULT 0")
        # A save written before scene threads existed has messages without the
        # column. Every one of them is the main thread, which is what the
        # default says, so the record reads exactly as it did.
        have = {r[1] for r in c.execute("PRAGMA table_info(messages)")}
        if "scene_id" not in have:
            c.execute("ALTER TABLE messages ADD COLUMN scene_id TEXT DEFAULT 'main'")
        c.commit()

    # kv
    def get(self, key, default=None):
        with self.lock:
            r = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def set(self, key, value):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, json.dumps(value)))
            self.conn.commit()

    def set_vn_frame(self, turn_id, frame):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO vn_frames(turn_id,frame_json) VALUES(?,?)",
                              (int(turn_id), json.dumps(frame, ensure_ascii=False)))
            self.conn.commit()

    def vn_frames(self, turn_ids):
        ids = [int(x) for x in turn_ids if x]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        with self.lock:
            rows = self.conn.execute(
                f"SELECT turn_id,frame_json FROM vn_frames WHERE turn_id IN ({marks})", ids).fetchall()
        return {int(r["turn_id"]): json.loads(r["frame_json"]) for r in rows}

    def set_vn_message_frame(self, msg_id, frame):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO vn_message_frames(msg_id,frame_json) VALUES(?,?)",
                              (int(msg_id), json.dumps(frame, ensure_ascii=False)))
            self.conn.commit()

    def vn_message_frames(self, msg_ids):
        ids = [int(x) for x in msg_ids if x]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        with self.lock:
            rows = self.conn.execute(
                f"SELECT msg_id,frame_json FROM vn_message_frames WHERE msg_id IN ({marks})", ids).fetchall()
        return {int(r["msg_id"]): json.loads(r["frame_json"]) for r in rows}

    def set_vn_line_checkpoint(self, msg_id, checkpoint_id):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO vn_line_checkpoints(msg_id,checkpoint_id) VALUES(?,?)",
                              (int(msg_id), str(checkpoint_id)))
            self.conn.commit()

    def vn_line_checkpoints(self, msg_ids):
        ids = [int(x) for x in msg_ids if x]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        with self.lock:
            rows = self.conn.execute(
                f"SELECT msg_id,checkpoint_id FROM vn_line_checkpoints WHERE msg_id IN ({marks})", ids).fetchall()
        return {int(r["msg_id"]): r["checkpoint_id"] for r in rows}

    # scenes
    def today_count(self, key, date):
        """A per-day counter kept in kv as {date: n}: today's number."""
        counts = self.get(key, {}) or {}
        return int(counts.get(date, 0) or 0)

    def bump_today(self, key, date, n=1):
        """Add `n` to today's count under `key` and drop the days before it.
        Nineteen modules kept this dict by hand, each pruning its own way;
        the shape is the same for all of them: today's count is what a cap
        reads, and yesterday's is nobody's business. Returns the new count."""
        counts = self.get(key, {}) or {}
        counts[date] = int(counts.get(date, 0) or 0) + n
        self.set(key, {k: v for k, v in counts.items() if k >= date})
        return counts[date]
    def add_scene(self, ts, date, hm, scene, raw):
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO scenes(ts,date,hm,location,activity,phone_access,with_who,sensory,inner,share_worthy,events,raw) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts, date, hm, scene.get("location", ""), scene.get("activity", ""), scene.get("phone_access", ""),
                 scene.get("with", ""), scene.get("sensory", ""), scene.get("inner", ""),
                 1 if scene.get("share_worthy") else 0, json.dumps(scene.get("events", []), ensure_ascii=False), raw))
            self.conn.commit()
            return cur.lastrowid

    def recent_scenes(self, n):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM scenes ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def scenes_for_date(self, date):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM scenes WHERE date=? ORDER BY ts", (date,)).fetchall()
        return [dict(r) for r in rows]

    def last_scene(self):
        s = self.recent_scenes(1)
        return s[0] if s else None

    # events
    def add_event(self, ts, date, kind, text, salience=1):
        with self.lock:
            self.conn.execute("INSERT INTO events(ts,date,kind,text,salience) VALUES(?,?,?,?,?)", (ts, date, kind, text, salience))
            self.conn.commit()

    def events_for_date(self, date):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM events WHERE date=? ORDER BY ts", (date,)).fetchall()
        return [dict(r) for r in rows]

    def salient_events(self, min_salience=2, before_ts=None, limit=1200):
        """The events worth remembering, newest first, older than `before_ts`.

        The deliberate search reads these because some things are in no other
        store: the only row in the first character's save that holds the title
        of the anime she met on her timeline on 2026-08-21 is an event, and
        until this existed the retrieval could not reach it however the cue
        was written (`docs/memory.md` §6). Salience is the filter -- a passing
        line about a train is not a thing she would go looking for."""
        with self.lock:
            if before_ts is None:
                rows = self.conn.execute(
                    "SELECT * FROM events WHERE salience>=? ORDER BY ts DESC LIMIT ?",
                    (int(min_salience), int(limit))).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM events WHERE salience>=? AND ts<? ORDER BY ts DESC LIMIT ?",
                    (int(min_salience), float(before_ts), int(limit))).fetchall()
        return [dict(r) for r in rows]

    def recent_events(self, n):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    # state
    def add_state(self, ts, date, gauges, reasons):
        with self.lock:
            self.conn.execute("INSERT INTO state_log(ts,date,gauges,reasons) VALUES(?,?,?,?)",
                              (ts, date, json.dumps(gauges), reasons))
            self.conn.commit()

    def state_for_date(self, date):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM state_log WHERE date=? ORDER BY ts", (date,)).fetchall()
        return [dict(r) for r in rows]

    # schedules
    def save_schedule(self, date, ts, blocks, notes):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO schedules(date,ts,blocks,notes) VALUES(?,?,?,?)",
                              (date, ts, json.dumps(blocks, ensure_ascii=False), notes))
            self.conn.commit()

    def get_schedule(self, date):
        with self.lock:
            r = self.conn.execute("SELECT * FROM schedules WHERE date=?", (date,)).fetchone()
        if not r:
            return None
        return {"date": r["date"], "blocks": json.loads(r["blocks"]), "notes": r["notes"]}

    # days
    def save_day(self, date, ts, narrative, summary, user_facts):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO days(date,ts,narrative,summary,user_facts) VALUES(?,?,?,?,?)",
                              (date, ts, narrative, summary, json.dumps(user_facts, ensure_ascii=False)))
            self.conn.commit()

    def get_day(self, date):
        with self.lock:
            r = self.conn.execute("SELECT * FROM days WHERE date=?", (date,)).fetchone()
        return dict(r) if r else None

    def recent_days(self, n):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM days ORDER BY date DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    # messages
    def add_message(self, ts, date, role, text, self_started=0, delivered_ts=None, read_ts=None, tg_id=None, dedupe=False, scene_id=None):
        """One message into the record. `scene_id` names the scene thread it
        belongs to; omitted, it is the active scene, so a reply written inside
        a directed scene is filed there without every caller passing it."""
        if scene_id is None:
            scene_id = self.active_scene
        with self.lock:
            if tg_id is not None and dedupe:
                # Telegram redelivers an update that was never confirmed, which
                # a restart makes likely, and its ids are unique for good. One
                # message of his must never become two of hers to answer (she
                # said "you sent it twice, baka" on 2026-08-19 after five
                # restarts in an hour). Only a channel whose ids are unique may
                # ask for this: the VN stage counts ids from 1 in every process
                # (`Channel.MSG_ID_UNIQUE`), so the same number is a different
                # line after a restart and the compare would eat it.
                row = self.conn.execute("SELECT id FROM messages WHERE tg_id=?", (tg_id,)).fetchone()
                if row:
                    return row[0]
            cur = self.conn.execute(
                "INSERT INTO messages(ts,date,role,text,self_started,delivered_ts,read_ts,tg_id,scene_id) VALUES(?,?,?,?,?,?,?,?,?)",
                (ts, date, role, text, self_started, delivered_ts, read_ts, tg_id, scene_id))
            self.conn.commit()
            return cur.lastrowid

    def mark_read(self, msg_id, ts):
        with self.lock:
            self.conn.execute("UPDATE messages SET read_ts=? WHERE id=?", (ts, msg_id))
            self.conn.commit()

    def retire_window(self, t0, t1, keep_event_kinds=()):
        """Rows the bot itself wrote inside (t0, t1] -- scenes, events (the
        world's kinds kept: a train delay happened whether or not she was
        written), state_log, self_memories -- so a replay (scail.py --replay)
        can write the stretch again on her clock. Returns the counts."""
        out = {}
        with self.lock:
            out["scenes"] = self.conn.execute("DELETE FROM scenes WHERE ts>? AND ts<=?", (t0, t1)).rowcount
            q = "DELETE FROM events WHERE ts>? AND ts<=?"
            args = [t0, t1]
            if keep_event_kinds:
                q += " AND kind NOT IN (%s)" % ",".join("?" * len(keep_event_kinds))
                args += list(keep_event_kinds)
            out["events"] = self.conn.execute(q, args).rowcount
            out["state_log"] = self.conn.execute("DELETE FROM state_log WHERE ts>? AND ts<=?", (t0, t1)).rowcount
            # A memory written in from her own record is not a row the bot
            # wrote in this window, whatever its stamp says: its stamp is the
            # felt age of a thing that happened years before the save existed
            # (`sim/seed_memories.py`), and for a character whose remembered
            # life ends where her lived record begins those stamps run right up
            # to the window's edge. Deleting one would take a piece of her
            # biography out of her for good, because nothing writes it again
            # until the seed version moves.
            from sim.self_memory import STANDING_SOURCES
            out["self_memories"] = self.conn.execute(
                "DELETE FROM self_memories WHERE ts>? AND ts<=? AND COALESCE(source,'compile') NOT IN (%s)"
                % ",".join("?" * len(STANDING_SOURCES)),
                [t0, t1] + list(STANDING_SOURCES)).rowcount
            self.conn.commit()
        return out

    def gauges_at(self, ts):
        """The last gauge snapshot at or before ts: (its ts, the dict)."""
        with self.lock:
            r = self.conn.execute("SELECT ts, gauges FROM state_log WHERE ts<=? ORDER BY ts DESC LIMIT 1", (ts,)).fetchone()
        if not r:
            return None, None
        g = r[1]
        return r[0], (json.loads(g) if isinstance(g, str) else g)

    def count_window(self, table, t0, t1, where=""):
        with self.lock:
            return self.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE ts>? AND ts<=? {where}", (t0, t1)).fetchone()[0]

    def unread_user_messages(self):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM messages WHERE role='user' AND read_ts IS NULL ORDER BY ts").fetchall()
        return [dict(r) for r in rows]

    def all_messages(self):
        """Every message, oldest first. Used by sim/derive.py to work the
        relationship out of the record rather than being told it."""
        with self.lock:
            rows = self.conn.execute("SELECT ts,date,role,self_started,read_ts FROM messages ORDER BY ts").fetchall()
        return [dict(r) for r in rows]

    def message_by_id(self, mid):
        with self.lock:
            r = self.conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        return dict(r) if r else None

    def message_by_tg_id(self, tg_id):
        """The row behind the channel's own id. The app knows hub ids and the
        record knows its own -- 141 in the store was 1813 on the hub -- so
        anything coming from a screen has to be resolved rather than guessed."""
        with self.lock:
            r = self.conn.execute("SELECT * FROM messages WHERE tg_id=?", (int(tg_id),)).fetchone()
        return dict(r) if r else None

    def update_message(self, mid, text):
        """Her side of the record, corrected by hand. Her history and his
        Telegram diverged in four places on 2026-08-20 and there was no way to
        put either back."""
        with self.lock:
            self.conn.execute("UPDATE messages SET text=? WHERE id=?", (text, mid))
            self.conn.commit()

    def delete_message(self, mid):
        with self.lock:
            self.conn.execute("DELETE FROM messages WHERE id=?", (mid,))
            self.conn.commit()

    def message_span(self):
        """(how many messages there are, the first date, the last date). The
        continuity checker is told this so it knows the conversation it is
        shown is an excerpt of a long record rather than the whole of it."""
        with self.lock:
            r = self.conn.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM messages").fetchone()
        return (r[0] or 0, r[1], r[2]) if r else (0, None, None)

    def recent_messages(self, n, scene_id=None):
        """The newest `n` messages. `scene_id` omitted means the active scene
        (the ordinary main thread unless a directed scene is running), so the
        readers that ask what is happening now see the scene she is in; `"*"`
        means every scene, for the record-level readers that must see the whole
        history. Every row in a save from before scene threads is `main`, so
        the ordinary answer is unchanged."""
        if scene_id is None:
            scene_id = self.active_scene
        with self.lock:
            if scene_id == "*":
                rows = self.conn.execute("SELECT * FROM messages ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM messages WHERE scene_id=? ORDER BY ts DESC LIMIT ?",
                    (scene_id, n)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def messages_since(self, ts):
        """Every message from `ts` on, oldest first. The thread's window is a
        span of time, not a count: a count drops the oldest message every
        time a new one lands, and the recap of that day changes with it."""
        with self.lock:
            rows = self.conn.execute("SELECT * FROM messages WHERE ts >= ? ORDER BY ts", (float(ts),)).fetchall()
        return [dict(r) for r in rows]

    def messages_for_date(self, date):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM messages WHERE date=? ORDER BY ts", (date,)).fetchall()
        return [dict(r) for r in rows]

    def last_message(self, role=None, scene_id=None):
        """The newest message, optionally of one role. Same rule as
        `recent_messages`: omitted `scene_id` is the active scene, `"*"` is
        every scene."""
        if scene_id is None:
            scene_id = self.active_scene
        with self.lock:
            if scene_id == "*":
                if role:
                    r = self.conn.execute("SELECT * FROM messages WHERE role=? ORDER BY ts DESC LIMIT 1", (role,)).fetchone()
                else:
                    r = self.conn.execute("SELECT * FROM messages ORDER BY ts DESC LIMIT 1").fetchone()
            else:
                if role:
                    r = self.conn.execute(
                        "SELECT * FROM messages WHERE role=? AND scene_id=? ORDER BY ts DESC LIMIT 1",
                        (role, scene_id)).fetchone()
                else:
                    r = self.conn.execute(
                        "SELECT * FROM messages WHERE scene_id=? ORDER BY ts DESC LIMIT 1",
                        (scene_id,)).fetchone()
        return dict(r) if r else None

    def unmark_read(self, mid):
        """Put a message of his back in the unread queue: the reply was lost."""
        with self.lock:
            self.conn.execute("UPDATE messages SET read_ts=NULL WHERE id=?", (mid,))
            self.conn.commit()

    def count_self_started(self, date, gap_seconds=0):
        """How many times she opened a conversation today. With gap_seconds set,
        bubbles sent closer together than that are one time she spoke rather than
        several, which is what the caps in impulse actually mean."""
        with self.lock:
            rows = self.conn.execute("SELECT ts FROM messages WHERE date=? AND self_started=1 ORDER BY ts",
                                     (date,)).fetchall()
        if not gap_seconds:
            return len(rows)
        n, last = 0, None
        for r in rows:
            if last is None or (r["ts"] - last) > gap_seconds:
                n += 1
            last = r["ts"]
        return n

    # the prompt a reply was drawn from, and the other answers to it
    def add_reply_prompt(self, msg_id, char, ts, model, messages, params, msg_ids, text,
                         reconstructed=0):
        """Written the moment the first bubble of the reply has a row, never
        held until the burst ends: a stop is `Stop-Process -Force`, and a
        prompt kept in a local is a prompt lost.

        `reconstructed` is 1 when the array was rebuilt afterwards from a copy
        of the save cut back to the moment, rather than kept as the call went
        out. Everything drawn from such a row carries the mark."""
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO reply_prompts(msg_id,char,ts,model,messages_json,"
                "params_json,msg_ids,text,sat,reconstructed) VALUES(?,?,?,?,?,?,?,?,0,?)",
                (msg_id, char, ts, model, json.dumps(messages, ensure_ascii=False),
                 json.dumps(params, ensure_ascii=False),
                 json.dumps(list(msg_ids or [])), text, int(reconstructed or 0)))
            self.conn.commit()
        return msg_id

    def reply_prompt(self, msg_id):
        with self.lock:
            r = self.conn.execute("SELECT * FROM reply_prompts WHERE msg_id=?", (int(msg_id),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["messages"] = json.loads(d.pop("messages_json") or "[]")
        d["params"] = json.loads(d.pop("params_json") or "{}")
        d["msg_ids"] = json.loads(d["msg_ids"] or "[]")
        return d

    def reply_prompt_for(self, msg_id):
        """The frozen prompt whose burst this row belongs to. One reply is one
        prompt and one to three message rows, and he may ask for a swipe on
        any of them."""
        got = self.reply_prompt(msg_id)
        if got:
            return got
        with self.lock:
            rows = self.conn.execute(
                "SELECT msg_id FROM reply_prompts ORDER BY msg_id DESC LIMIT 400").fetchall()
        for r in rows:
            got = self.reply_prompt(r[0])
            if got and int(msg_id) in [int(x) for x in (got.get("msg_ids") or [])]:
                return got
        return None

    def extend_reply_prompt(self, msg_id, extra_id):
        """The next bubble of the same burst got a row."""
        with self.lock:
            r = self.conn.execute("SELECT msg_ids FROM reply_prompts WHERE msg_id=?",
                                  (int(msg_id),)).fetchone()
            if not r:
                return False
            ids = [int(x) for x in json.loads(r[0] or "[]")]
            if int(extra_id) in ids:
                return False
            ids.append(int(extra_id))
            self.conn.execute("UPDATE reply_prompts SET msg_ids=? WHERE msg_id=?",
                              (json.dumps(ids), int(msg_id)))
            self.conn.commit()
        return True

    def reply_prompt_ids(self, n=40):
        with self.lock:
            rows = self.conn.execute(
                "SELECT msg_id FROM reply_prompts ORDER BY msg_id DESC LIMIT ?", (n,)).fetchall()
        return [int(r[0]) for r in rows]

    def add_swipe(self, msg_id, n, model, text, voice_path="", ts=0.0, prompt_tokens=0,
                  completion_tokens=0, cached_tokens=0, cost=0.0):
        """A paid answer, written the moment it exists."""
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO swipes(msg_id,n,model,text,voice_path,ts,prompt_tokens,"
                "completion_tokens,cached_tokens,cost) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (int(msg_id), int(n), model, text, voice_path, ts, int(prompt_tokens or 0),
                 int(completion_tokens or 0), int(cached_tokens or 0), float(cost or 0.0)))
            self.conn.commit()
        return int(n)

    def swipes_for(self, msg_id):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM swipes WHERE msg_id=? ORDER BY n",
                                     (int(msg_id),)).fetchall()
        return [dict(r) for r in rows]

    def next_swipe_n(self, msg_id):
        with self.lock:
            r = self.conn.execute("SELECT MAX(n) FROM swipes WHERE msg_id=?", (int(msg_id),)).fetchone()
        return int((r[0] if r and r[0] is not None else -1)) + 1

    def sit_swipe(self, msg_id, n):
        """Which candidate the conversation continues from. The record of the
        choice; the rewrite of her rows is the caller's."""
        with self.lock:
            self.conn.execute("UPDATE reply_prompts SET sat=? WHERE msg_id=?", (int(n), int(msg_id)))
            self.conn.commit()

    # digests
    def add_digest(self, ts, date, text, from_ts, to_ts):
        with self.lock:
            self.conn.execute("INSERT INTO digests(ts,date,text,from_ts,to_ts) VALUES(?,?,?,?,?)", (ts, date, text, from_ts, to_ts))
            self.conn.commit()

    def recent_digests(self, n):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM digests ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def digests_for_date(self, date):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM digests WHERE date=? ORDER BY ts", (date,)).fetchall()
        return [dict(r) for r in rows]

    # threads
    def add_thread(self, text, ts, date, people=""):
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO threads(text,status,people,created_ts,updated_ts,created_date,resolved_date) VALUES(?,?,?,?,?,?,NULL)",
                (text, "open", people, ts, ts, date))
            self.conn.commit()
            return cur.lastrowid

    def update_thread(self, tid, ts, status=None, text=None, resolved_date=None):
        with self.lock:
            if status is not None:
                self.conn.execute("UPDATE threads SET status=?, updated_ts=? WHERE id=?", (status, ts, tid))
            if text is not None:
                self.conn.execute("UPDATE threads SET text=?, updated_ts=? WHERE id=?", (text, ts, tid))
            if resolved_date is not None:
                self.conn.execute("UPDATE threads SET resolved_date=? WHERE id=?", (resolved_date, tid))
            self.conn.commit()

    def delete_thread(self, tid):
        with self.lock:
            self.conn.execute("DELETE FROM threads WHERE id=?", (tid,))
            self.conn.commit()

    def threads_by_status(self, status, n=100):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM threads WHERE status=? ORDER BY updated_ts DESC LIMIT ?", (status, n)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def all_threads(self, n=200):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM threads ORDER BY updated_ts DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in rows]

    # user facts
    def add_user_fact(self, ts, fact):
        with self.lock:
            self.conn.execute("INSERT INTO user_facts(ts,fact) VALUES(?,?)", (ts, fact))
            self.conn.commit()

    def user_facts(self):
        with self.lock:
            rows = self.conn.execute("SELECT * FROM user_facts ORDER BY ts").fetchall()
        return [r["fact"] for r in rows]

    def replace_user_facts(self, ts, facts):
        with self.lock:
            self.conn.execute("DELETE FROM user_facts")
            for f in facts:
                self.conn.execute("INSERT INTO user_facts(ts,fact) VALUES(?,?)", (ts, f))
            self.conn.commit()
