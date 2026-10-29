import datetime
import logger

# Her allowance. A balance in yen (kv money) that mom tops up on the
# allowance day, that the director spends from when a scene has her buy
# something (`spent` in the scene JSON: yen and what on), and that cannot go
# below zero: a girl with 300 yen left does not buy the 700 yen parfait, and
# the director is told so before it writes the scene. Low money is a fact
# she lives with (a "broke" tag, a line in her situation, a line to the
# schedule model so the plan stays home more), not a mood the model is
# told to have.


class Money:
    def __init__(self, config, store, clock):
        self.config = config
        self.store = store
        self.clock = clock
        m = store.get("money")
        if not m:
            # Only for somebody who has money modelled. Every other method here
            # checks the flag and this one did not, so constructing the object
            # -- which happens for everybody -- wrote a starting balance into
            # the save of a character whose money section is switched off. Hers
            # held 2,800 yen of the first character's allowance, put there by
            # nothing anyone chose, and `line()` would have read it out.
            if not getattr(config.money, "enabled", False):
                self.m = {"balance": 0, "last_allowance": "", "log": []}
                return
            # the start balance is what is left of this month's allowance
            m = {"balance": config.money.start_balance_yen, "last_allowance": clock.now().strftime("%Y-%m"), "log": []}
            store.set("money", m)
        self.m = m

    def save(self):
        self.m["log"] = self.m["log"][-self.config.money.log_keep:]
        self.store.set("money", self.m)

    # ---------------- the month ----------------

    def ensure_allowance(self):
        """On the allowance day (or the first day she is around after it) mom hands it over. Returns the event text or ''."""
        c = self.config.money
        if not c.enabled:
            return ""
        today = self.clock.now().date()
        key = today.strftime("%Y-%m")
        if self.m.get("last_allowance") == key or today.day < c.allowance_day:
            return ""
        self.m["balance"] = int(self.m.get("balance", 0)) + c.allowance_yen
        self.m["last_allowance"] = key
        self.m["log"].append({"date": today.isoformat(), "hm": self.clock.hm(), "yen": c.allowance_yen, "on": "allowance from mom"})
        self.save()
        text = f"allowance day: mom hands over this month's {c.allowance_yen} yen"
        self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "life", text, 2)
        logger.log(f"[money] {text}; balance {self.m['balance']}")
        return text

    def days_to_allowance(self):
        c = self.config.money
        today = self.clock.now().date()
        if today.day < c.allowance_day:
            return c.allowance_day - today.day
        nxt = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=c.allowance_day)
        return (nxt - today).days

    # ---------------- spending ----------------

    def spend(self, spent):
        """Apply the director's `spent` {yen, on}; clamps to the balance. Returns the amount actually spent."""
        c = self.config.money
        if not c.enabled or not isinstance(spent, dict):
            return 0
        try:
            yen = int(spent.get("yen", 0) or 0)
        except (TypeError, ValueError):
            return 0
        if yen <= 0:
            return 0
        on = str(spent.get("on", "") or "something")[:80]
        # The director runs every `tick_minutes` and is not shown what the last
        # scene bought, so it re-narrates the purchase it just made: the same
        # grape ice and melon bun went into the log at 13:00 and again at 13:20
        # on 2026-08-20, and her balance paid for both. One purchase, once.
        mins = int(getattr(c, "duplicate_minutes", 45) or 45)
        today = self.clock.date_str()
        now_m = int(self.clock.hm()[:2]) * 60 + int(self.clock.hm()[3:5])
        for e in reversed(self.m.get("log", [])[-6:]):
            if e.get("date") != today or e.get("on") != on or e.get("yen") != -yen:
                continue
            hm = str(e.get("hm") or "00:00")
            if now_m - (int(hm[:2]) * 60 + int(hm[3:5])) <= mins:
                logger.log(f"[money] the same {on} for {yen} is already in the log at {hm}; not spent twice")
                return 0
        bal = int(self.m.get("balance", 0))
        if yen > bal:
            logger.log(f"[money] scene spent {yen} on {on} but she has {bal}; clamped")
            yen = bal
        self.m["balance"] = bal - yen
        self.m["log"].append({"date": self.clock.date_str(), "hm": self.clock.hm(), "yen": -yen, "on": on})
        self.save()
        logger.log(f"[money] -{yen} {on}; balance {self.m['balance']}")
        return yen

    def spent_today(self):
        d = self.clock.date_str()
        return -sum(e["yen"] for e in self.m.get("log", []) if e.get("date") == d and e.get("yen", 0) < 0)

    # ---------------- put aside ----------------
    # money a promise has claimed (sim/commitments.py). Not a hard block:
    # the director is told what is put aside, and a girl can still blow the
    # gift money on a parfait -- which is then the record the promise is
    # settled against.

    def reserve(self, gid, yen):
        """Put aside up to `yen` for a commitment; returns what could be."""
        amount = max(0, min(int(yen), self.available()))
        self.m.setdefault("reserved", {})[gid] = amount
        self.save()
        return amount

    def release(self, gid):
        if self.m.get("reserved", {}).pop(gid, None) is not None:
            self.save()

    def reserved(self):
        return sum(int(v) for v in self.m.get("reserved", {}).values())

    def available(self):
        return max(0, self.balance() - self.reserved())

    # ---------------- how it feels ----------------

    def balance(self):
        return int(self.m.get("balance", 0))

    def broke(self):
        c = self.config.money
        return self.balance() < c.allowance_yen * c.broke_ratio

    def tags(self):
        if not self.config.money.enabled:
            return []
        if self.balance() <= 0:
            return ["no money left this month"]
        if self.broke():
            return ["nearly broke this month"]
        return []

    def line(self):
        """For the director and the schedule model."""
        c = self.config.money
        if not c.enabled:
            return ""
        d = self.days_to_allowance()
        s = f"MONEY: {self.balance()} yen left; allowance {c.allowance_yen} yen on the {c.allowance_day}st ({d} day{'s' if d != 1 else ''} away)"
        st = self.spent_today()
        if st:
            s += f"; spent today {st} yen"
        # what she has ALREADY bought, so the scene does not buy it again --
        # and so the third grape ice in a week reads as the tic it is
        bought = [f"{e.get('hm')} {e.get('on')}" for e in self.m.get("log", [])
                  if e.get("date") == self.clock.date_str() and int(e.get("yen", 0) or 0) < 0]
        if bought:
            s += "; already bought today: " + ", ".join(bought[-4:])
        if self.reserved():
            s += f"; {self.reserved()} yen of it put aside for promises, {self.available()} actually free"
        if self.broke():
            s += ". She is nearly out: no parfait, no gacha, the cheap konbini tier, borrowing is embarrassing"
        return s

    def bought_line(self, date_str=None):
        """What the money record says she bought on a date, for the ledger
        -- every reader of the day, hers and theirs. The plan wrote 'she
        buys a used paperback for 100 yen' into a block and a friend's turn
        read it as done; the record had no purchase, and she told the
        group and her father about a book she never bought."""
        if not self.config.money.enabled:
            return ""
        date_str = date_str or self.clock.date_str()
        bought = [f"{e.get('hm')} {e.get('on')} ({abs(int(e.get('yen', 0) or 0))} yen)" for e in self.m.get("log", [])
                  if e.get("date") == date_str and int(e.get("yen", 0) or 0) < 0]
        if bought:
            return "bought today, the money record (a purchase the plan or a scene mentions and this line does not never happened): " + ", ".join(bought[-8:])
        return "bought nothing today (the money record; a purchase the plan or a scene mentions never happened)"

    def persona_line(self):
        if not self.config.money.enabled:
            return ""
        d = self.days_to_allowance()
        b = self.balance()
        if b <= 0:
            return f"money: you are out until allowance day ({d} days)"
        put = f", {self.reserved()} of it put aside for things you promised" if self.reserved() else ""
        if self.broke():
            return f"money: about {b} yen left for {d} more days, which is nothing{put}"
        return f"money: about {b} yen left until the {self.config.money.allowance_day}st ({d} days){put}"

    def brief(self):
        log = self.m.get("log", [])[-12:]
        return f"balance {self.balance()} yen; next allowance in {self.days_to_allowance()} day(s)\n" + "\n".join(
            f"{e['date']} {e.get('hm', '')} {e['yen']:+d} {e['on']}" for e in log)
