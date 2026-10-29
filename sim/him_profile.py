"""What she has come to know about him, from weeks of looking.

The phone digest is a transcript of one look; `user_facts` are one-liners.
Nothing read the digests back over time, so she knew what he did at 10:04
and not what he is like -- when he is at his machine, what he is into this
month, what he does when he is stressed -- which is the model of him the
bible assumes she has ("you know his hours"). `Rhythm` learns the hours;
this learns the rest, once a day (`him_profile.every_hours`), from the last
`him_profile.digests` digests and the facts, into kv `him_profile`.

Read by her own reply (the persona system prompt, beside her beliefs about
him) and by the digest writer, so a look can say "as usual" or "not like
him" instead of narrating every session as news.
"""
import json

import logger
from sim import sight


class HimProfile:
    def __init__(self, config, store, clock, rhythm=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.rhythm = rhythm
        # the count the wait was last logged at: `due()` stays true until a
        # profile is written, so without this the wait is logged every tick
        # (Rena's log, 3,812 lines of it on 2026-09-06)
        self._waited_at = None

    def current(self):
        return self.store.get("him_profile", {}) or {}

    def due(self):
        c = self.config.him_profile
        if not c.enabled:
            return False
        last = float(self.current().get("ts", 0) or 0)
        return self.clock.now_ts() - last >= float(c.every_hours) * 3600

    def maybe(self, llm):
        if self.due():
            try:
                return self.refresh(llm)
            except Exception as e:
                logger.log(f"[him] profile not refreshed: {type(e).__name__}: {e}")
        return None

    def refresh(self, llm):
        c = self.config.him_profile
        digests = self.store.recent_digests(int(c.digests))
        if len(digests) < int(c.min_digests):
            if self._waited_at != len(digests):
                logger.log(f"[him] {len(digests)} digest(s) on file; the profile waits for {c.min_digests}")
                self._waited_at = len(digests)
            return None
        lines = []
        for d in digests:
            when = self.clock.to_user(d["ts"]).strftime("%a %d %H:%M") if hasattr(self.clock, "to_user") else self.clock.hm(d["ts"])
            lines.append(f"[{when} his time] {str(d.get('text', ''))[:700]}")
        facts = self.store.user_facts() or []
        hours = ""
        try:
            hours = self.rhythm.describe() if self.rhythm and hasattr(self.rhythm, "describe") else ""
        except Exception:
            hours = ""
        prev = self.current().get("text", "")
        user = (
            f"TODAY: {self.clock.user_now().strftime('%A %Y-%m-%d')} his time.\n"
            + (f"HIS HOURS, as learned by the machine: {hours}\n" if hours else "")
            + f"WHAT SHE ALREADY HOLDS AS FACT ABOUT HIM:\n{json.dumps(facts[-40:], ensure_ascii=False)}\n\n"
            + (f"HER PREVIOUS PICTURE OF HIM (revise it; do not restart from nothing):\n{prev}\n\n" if prev else "")
            + sight.w(self.config, "him_profile_digests_label", n=len(lines)) + "\n".join(lines)
        )
        messages = [{"role": "system", "content": self.config.prompt_text("him_profile")},
                    {"role": "user", "content": user}]
        data, _raw = llm.call_json("him_profile", messages)
        if not isinstance(data, dict) or not data.get("picture"):
            logger.log("[him] profile call gave nothing usable")
            return None
        rec = {"ts": self.clock.now_ts(), "date": self.clock.date_str(),
               "text": str(data.get("picture", ""))[:1500],
               "hours": str(data.get("hours", ""))[:300],
               "into": [str(x)[:80] for x in (data.get("into_lately") or [])][:8],
               "tells": [str(x)[:120] for x in (data.get("tells") or [])][:8],
               "unsure": [str(x)[:120] for x in (data.get("unsure") or [])][:5],
               "digests": len(lines)}
        self.store.set("him_profile", rec)
        logger.log(f"[him] profile refreshed from {len(lines)} digests: {rec['text'][:120]}")
        return rec

    def prompt_text(self):
        """For her own reply: the picture, as something she holds rather
        than recites."""
        rec = self.current()
        if not rec.get("text"):
            return ""
        from sim.lang import say
        t = say(self.config)
        out = [t(*sight.w2(self.config, "him_profile_head")),
               rec["text"]]
        if rec.get("hours"):
            out.append(t(f"His hours: {rec['hours']}", f"彼の時間帯: {rec['hours']}"))
        if rec.get("into"):
            out.append(t("Into lately: ", "最近はまっているもの: ") + "; ".join(rec["into"]))
        if rec.get("tells"):
            out.append(t("His tells: ", "彼のくせ: ") + "; ".join(rec["tells"]))
        return "\n".join(out)

    def digest_line(self):
        """For the digest writer: what is usual, so a look can say what is not."""
        rec = self.current()
        if not rec.get("text"):
            return ""
        return ("WHAT SHE ALREADY KNOWS OF HIS PATTERNS (say when a session is his usual and when it is not; "
                "do not re-explain the usual): " + rec["text"][:600]
                + (f" Hours: {rec['hours']}" if rec.get("hours") else ""))
