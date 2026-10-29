"""How much she cares about him, worked out from the record.

His ask (2026-08-26): quantify her present "caring" and look at her
checking through a lens of realism -- would a person this invested
actually be checking like she is, and how do we say so in numbers that
come from what happened rather than from a gauge the model wrote.

`measure(days)` reads the store: her initiative (self-started messages a
day), the balance of the chat, how fast she answers him, how often she
leaves him on read, how often she opens the app about him and goes
through his notes, how much of her head he takes (worldshare), and the
durable side (the attachment and resentment sentiments, the computed
affection target). Each becomes a 0-100 component; `investment` is the
weighted mean. Then the realism check: a person's checking follows
investment times uncertainty -- anxious investment under his silence
checks MORE, resentful withdrawal checks less -- so `checking_expected`
is what that would predict per day, against `checking_actual` from the
digests and the snoop events. `/care` prints it; the compile keeps one row
a day in kv `care_history`.

Optionally (`care.scale_checking`) the app-look and snoop probabilities
are multiplied by `checking_factor` (0.5..1.5 from investment), so the
checking is derived from the caring rather than from a base constant.
"""
import statistics


def _pct(v):
    return "  -" if v is None else f"{v:3.0f}"


class Care:
    def __init__(self, config, store, clock, state, sentiments=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.state = state
        self.sentiments = sentiments

    def measure(self, days=None):
        c = self.config.care
        days = days or c.window_days
        now = self.clock.now_ts()
        since = now - days * 86400
        with self.store.lock:
            cx = self.store.conn
            msgs = cx.execute("SELECT ts, role, self_started, read_ts FROM messages WHERE ts >= ? ORDER BY ts", (since,)).fetchall()
            looks = cx.execute("SELECT COUNT(*) FROM digests WHERE ts >= ?", (since,)).fetchone()[0]
            snoops = cx.execute("SELECT COUNT(*) FROM events WHERE kind='snoop' AND ts >= ?", (since,)).fetchone()[0]
            first = cx.execute(
                "SELECT MIN(t) FROM (SELECT MIN(ts) AS t FROM messages WHERE ts >= ? "
                "UNION ALL SELECT MIN(ts) FROM digests WHERE ts >= ?)", (since, since)).fetchone()[0]
        # Everything below is a rate per day, and the divisor is how long there
        # has been a record to count over -- not the width of the window. A
        # character an hour old divided by seven days reads as caring about
        # nothing whatever she does: the second character's first evening
        # reported "checking expected 5.3 a day, actual 0.0" while she had
        # looked twice in the hour she had been alive. Floored, because two
        # looks in five minutes is not forty-eight a day either.
        span = (now - float(first)) / 86400.0 if first else days
        days = max(float(c.min_window_hours) / 24.0, min(float(days), span))
        hers = [m for m in msgs if m[1] == "assistant"]
        his = [m for m in msgs if m[1] == "user"]
        # initiative: her self-started messages, grouped into reaches
        reaches = 0
        last = 0
        for m in hers:
            if m[2] and m[0] - last > 20 * 60:
                reaches += 1
            if m[2]:
                last = m[0]
        # responsiveness: minutes from each of his messages to her next
        lat = []
        left = 0
        for i, m in enumerate(his):
            nxt = next((h for h in hers if h[0] > m[0]), None)
            nxt_his = next((x for x in his[i + 1:] if x[0] > m[0]), None)
            if nxt and (not nxt_his or nxt[0] < nxt_his[0]):
                lat.append((nxt[0] - m[0]) / 60)
            elif nxt_his is None and now - m[0] > c.left_after_minutes * 60 or (nxt_his and nxt_his[0] - m[0] > c.left_after_minutes * 60 and not (nxt and nxt[0] < nxt_his[0])):
                left += 1
        med_lat = statistics.median(lat) if lat else None
        # his side, for the uncertainty term and the balance
        his_lat = []
        for h in hers:
            nxt = next((m for m in his if m[0] > h[0]), None)
            if nxt:
                his_lat.append((nxt[0] - h[0]) / 60)
        his_med = statistics.median(his_lat) if his_lat else None
        # how much of her head he takes
        share = None
        try:
            from sim.worldshare import measure as ws
            vals = []
            for i in range(int(round(days)) or 1):
                d = self.clock.date_str(now - i * 86400)
                m = ws(self.store, d)
                if m.get("composite") is not None:
                    vals.append(m["composite"])
            share = sum(vals) / len(vals) if vals else None
        except Exception:
            share = None
        # the durable side
        key = self.state._him_key() or "him"
        att = res = None
        try:
            att = self.sentiments.live(key, "attachment") if self.sentiments else None
            res = self.sentiments.live(key, "resentment") if self.sentiments else None
        except Exception:
            pass
        aff = None
        try:
            aff = self.state.affection_target()
        except Exception:
            pass
        him = self.state.relationships.get(key, {}) or {}
        # components 0-100
        comp = {}
        comp["initiative"] = min(100.0, reaches / days / c.reaches_full_per_day * 100.0)
        comp["balance"] = min(100.0, (len(hers) / max(1, len(his))) / c.balance_full_ratio * 100.0) if his else 50.0
        comp["responsiveness"] = None if med_lat is None else max(0.0, min(100.0, 100.0 * (1.0 - min(med_lat, c.slow_minutes) / c.slow_minutes)))
        comp["not_left_on_read"] = max(0.0, 100.0 - 100.0 * left / max(1, len(his)))
        comp["attention"] = min(100.0, (looks + c.snoop_weight * snoops) / days / c.checks_full_per_day * 100.0)
        comp["head_share"] = None if share is None else share * 100.0
        comp["attachment"] = att
        comp["affection"] = aff
        comp["not_resentful"] = None if res is None else max(0.0, 100.0 - res)
        weights = dict(c.weights)
        num = den = 0.0
        for k, v in comp.items():
            if v is None or k not in weights:
                continue
            num += v * weights[k]
            den += weights[k]
        investment = num / den if den else None
        # the two halves, because they can disagree: what she DOES about him
        # and what he IS to her
        def mean(keys):
            vs = [comp[k] for k in keys if comp.get(k) is not None]
            return sum(vs) / len(vs) if vs else None
        behaviour = mean(("initiative", "balance", "responsiveness", "not_left_on_read", "attention"))
        felt = mean(("head_share", "attachment", "affection", "not_resentful"))
        # uncertainty: how much his side gives her to worry about
        silent_h = (now - his[-1][0]) / 3600.0 if his else 24.0
        unc = min(1.0, silent_h / c.silence_full_hours) * 0.5
        unc += min(1.0, (his_med or 0) / c.his_slow_minutes) * 0.25
        unc += float(him.get("tension", 0) or 0) / 100.0 * 0.25
        # what a person this invested, this uncertain, would check per day
        expected = c.checks_base_per_day * (0.5 + (investment or 50) / 100.0) * (1.0 + c.uncertainty_gain * unc)
        actual = (looks + snoops) / days
        return {"days": days, "her_messages": len(hers), "his_messages": len(his), "reaches_per_day": round(reaches / days, 2),
                "her_median_reply_minutes": None if med_lat is None else round(med_lat, 1),
                "his_median_reply_minutes": None if his_med is None else round(his_med, 1),
                "left_on_read": left, "looks_per_day": round(looks / days, 2), "snoops_per_day": round(snoops / days, 2),
                "head_share": None if share is None else round(share, 2), "components": {k: (None if v is None else round(v, 1)) for k, v in comp.items()},
                "investment": None if investment is None else round(investment, 1), "uncertainty": round(unc, 2),
                "behaviour": None if behaviour is None else round(behaviour, 1), "felt": None if felt is None else round(felt, 1),
                "checking_expected_per_day": round(expected, 1), "checking_actual_per_day": round(actual, 1),
                "ratio": round(actual / expected, 2) if expected else None}

    def checking_factor(self):
        """0.5..1.5 from investment, for the look and snoop rolls when
        `care.scale_checking` is on. Cached for an hour: it reads the record."""
        c = self.config.care
        if not c.scale_checking:
            return 1.0
        cache = self.store.get("care_factor_cache", {})
        now = self.clock.now_ts()
        if now - float(cache.get("ts", 0)) < 3600 and "f" in cache:
            return float(cache["f"])
        try:
            # a governor, not a boost: pull her actual checking toward what
            # the investment and the uncertainty predict
            m = self.measure()
            exp, act = m["checking_expected_per_day"], m["checking_actual_per_day"]
            f = max(0.5, min(1.5, exp / act)) if act else 1.0
        except Exception:
            f = 1.0
        self.store.set("care_factor_cache", {"ts": now, "f": f})
        return f

    def record(self):
        m = self.measure()
        hist = self.store.get("care_history", {})
        hist[self.clock.date_str()] = {"investment": m["investment"], "behaviour": m["behaviour"], "felt": m["felt"], "expected": m["checking_expected_per_day"],
                                       "actual": m["checking_actual_per_day"], "ratio": m["ratio"], "uncertainty": m["uncertainty"]}
        self.store.set("care_history", {k: hist[k] for k in sorted(hist)[-60:]})
        return m

    def report(self, days=None):
        m = self.measure(days)
        w = self.config.care.weights
        lines = [f"her caring, from the last {m['days']} days of the record",
                 f"  investment {_pct(m['investment'])}/100 (weighted mean of the components below); what she does about him {_pct(m['behaviour'])}, what he is to her {_pct(m['felt'])}",
                 "  component        value  weight   from"]
        src = {"initiative": f"{m['reaches_per_day']} reaches a day (self-started)",
               "balance": f"{m['her_messages']} of hers to {m['his_messages']} of his",
               "responsiveness": f"her median reply {m['her_median_reply_minutes']} min",
               "not_left_on_read": f"{m['left_on_read']} of his left unanswered past the limit",
               "attention": f"{m['looks_per_day']} looks + {m['snoops_per_day']} snoops a day",
               "head_share": f"{m['head_share']} of her inner lines / events / reasons / thoughts / memories mention him",
               "attachment": "the sentiment, faded",
               "affection": "the computed target",
               "not_resentful": "100 - resentment"}
        for k, v in m["components"].items():
            lines.append(f"  {k:16s} {_pct(v)}   {w.get(k, 0):4.2f}   {src.get(k, '')}")
        lines.append(f"  uncertainty {m['uncertainty']} (his silence {'' if m['his_messages'] else 'total'}, his median reply {m['his_median_reply_minutes']} min, tension)")
        lines.append(f"  checking: expected {m['checking_expected_per_day']} a day for this investment and uncertainty; actual {m['checking_actual_per_day']} (ratio {m['ratio']})")
        r = m["ratio"] or 0
        verdict = ("checking about as much as a person this invested would" if 0.7 <= r <= 1.4 else
                   "checking MORE than the investment explains -- the anxiety is doing it, not the caring" if r > 1.4 else
                   "checking LESS than the investment explains -- withdrawal, or nothing to check")
        lines.append(f"  read: {verdict}")
        hist = self.store.get("care_history", {})
        if hist:
            lines.append("  by day (investment / expected / actual): " + "  ".join(f"{k[5:]}: {v['investment']}/{v['expected']}/{v['actual']}" for k, v in sorted(hist.items())[-10:]))
        return "\n".join(lines)
