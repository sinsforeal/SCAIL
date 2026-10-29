import json
from sim.wiring import wire
import os
import re
import sys
import threading
import time
import random
import argparse
import datetime

import logger
from sim import existence
from sim import downtime
from sim import inflight
from sim import sight
from sim import roster
# which language everything addressed to her is written in (the boot line, /lang)
from sim import lang
from sim import repairs
import netwatch
from config import Config
from llm import LLM
from store import Store
from world.clock import WorldClock, hm_to_minutes
from world.weather import Weather
from world.calendar import Calendar
from sim import schedule as sched
from sim.state import State
from sim.phone import Phone
from sim.reconcile import Reconcile
from sim.inbound import InboundSignals
from typesafe import TypeSafe
from sim.director import Director
from sim.impulse import Impulse
from sim import timeline
from sim.receipts import Receipts
from sim.reunion import Reunion
from sim.notes import Notes
from sim.records import Records
from sim.diary import Diary
from embodied.health import Health
from embodied.body import Body
from embodied.money import Money
from sim.memory import Memory
from sim.appraisal import Appraisal
from sim.stress import Stress
from sim.reflect import Reflection
from sim.lookup import Lookup
from sim.commitments import Commitments
from sim.attachment import Attachment
from sim.recall import Recall, moment_cue
from sim.approach import Approach
from sim.rhythm import Rhythm
from sim.withholding import Withholding
from sim.intent import Intent
from sim.outlook import Outlook
from sim.watchlist import Watchlist
from sim.recap import Recap
from machine.retrievals import Retrievals, character_id as retrieval_character_id
from sim.context import ContextView
from sim.model_of_him import ModelOfHim
from sim.coherence import Coherence
from sensors.x_monitor import (load_following as _x_load_following, load_accounts as _x_load_accounts,
                               load_followers as _x_load_followers, follows_back as _x_follows_back,
                               private_accounts as _x_private_accounts)
from sim.model_of_her import ModelOfHer
from sim.spiral import Spirals
from sim.rupture import Ruptures
from sim.sentiment import Sentiments
from sim.ick import Ick
from sim.goals import Goals
from sim.self_memory import SelfMemory
from sensors.x_monitor import his_likes_since as _x_his_likes, his_follows_since as _x_his_follows, her_actions as _x_her_actions
from persona.persona import Persona
from persona.delivery import Delivery
from channels.telegram_bot import TelegramInterface
from sensors.mal_monitor import MalMonitor


def load_program(config):
    """The program that runs this character: `tomoe.app` or `resident.app`,
    named by `character.program` in her config. The runtime never names a
    program in its own text; it asks the config which one she is."""
    import importlib
    name = str(getattr(config.character, "program", "") or "").strip()
    if not name:
        raise SystemExit("[config] character.program is not set: name the package whose app.py runs her")
    try:
        return importlib.import_module(f"{name}.app")
    except ImportError as e:
        raise SystemExit(f"[config] character.program is {name!r} but {name}/app.py cannot be imported: {e}")


# the world-and-account objects a program may build. Every one of them is a
# slot on the App that starts empty; the shared code asks before it touches
# one, and a character whose sheet excludes it has None there for good.
PROGRAM_SLOTS = ("hazards", "trains", "zeitgeist", "cast", "cast_arcs", "social_graph", "showrunner", "snoop",
                 "social", "taste", "diet", "seen_images", "posting", "replies", "events", "compare", "exchange", "orbit",
                 "gossip", "people", "family", "scenery", "cast_psych", "carried", "sight",
                 "own_mechanisms", "eroge", "world_shared", "share_pick")


def parse_args():
    p = argparse.ArgumentParser(description="SCAIL: one resident character on his machine")
    p.add_argument("--config", default="config_momoka.json")
    p.add_argument("--db", help="override logging.db_path (dry runs should not touch the live save file)")
    p.add_argument("--sim", metavar="YYYY-MM-DD HH:MM", help="dry run: start the world clock here (her time) and run accelerated")
    p.add_argument("--speed", type=float, help="sim speed multiplier (default from config)")
    p.add_argument("--hours", type=float, default=0, help="sim: stop after this many simulated hours (0 = run forever)")
    p.add_argument("--console", action="store_true", help="print her messages to console instead of Telegram")
    p.add_argument("--no-sensors", action="store_true", help="do not start the PC sensors")
    p.add_argument("--say", action="append", default=[], metavar="HH:MM|text", help="sim: inject a message from him at her-time HH:MM (repeatable)")
    p.add_argument("--gap", action="store_true",
                   help="with --replay: do not re-live the window; write one temporal-gap event for it "
                        "(the record says nobody wrote her then) and point the director past it")
    p.add_argument("--yes", action="store_true", help="with --replay: proceed past replay.cost_warn_usd")
    p.add_argument("--replay", nargs=2, metavar=("FROM", "TO"),
                   help="re-live a hole in the record on her clock, on the live save: machine-local times "
                        "'YYYY-MM-DD HH:MM[:SS]'. The bot must be stopped. What the bot wrote inside the window "
                        "is retired (backup in data/retired/), the gauges go back to the snapshot at FROM, and the "
                        "loop runs FROM..TO at --speed with sends, X actions, phone looks and sensors off")
    return p.parse_args()


class App:
    def __init__(self, args):
        self.args = args
        self.config = Config(args.config)
        c = self.config
        self.program = load_program(c)
        self.replay = self._replay_setup(args, c) if getattr(args, "replay", None) else None
        if args.sim:
            c.clock.mode = "sim"
            c.clock.sim_start = args.sim
        if args.speed:
            c.clock.sim_speed = args.speed
        if args.console or args.sim:
            c.telegram.console_only = True
        if args.db:
            c.logging.db_path = args.db
        self.sensors_on = c.sensors.enabled and not args.no_sensors and not args.sim and not self.replay

        logger.setup(c.logging.dry_run_out_dir if args.sim else c.logging.out_dir)
        # What this character turned out to be. `Config` works these out before
        # there is a log to put them in and printed them to a console nothing
        # redirects, so no run of the second character had ever recorded which
        # of her subsystems are off. Console-quiet here: they have been printed
        # once already.
        for _line in c.boot_notes:
            logger.log(_line, to_console=False)
        netwatch.configure(c)
        self.clock = WorldClock(c)
        self.store = Store(c.logging.db_path)
        if self.replay and self.replay.get("gap"):
            self.temporal_gap(self.replay["from"], self.replay["to"], "--gap")
            raise SystemExit(0)
        if self.replay:
            self._replay_prepare()
        self.llm = LLM(c, self.store)
        self.weather = Weather(c, self.clock)
        self.calendar = Calendar(c)
        from sensors.vision import Vision
        self.vision = Vision(c, self.store)
        logger.log(f"[vision] {'on, ' + c.vision.model if self.vision.enabled else 'off'}")
        # the channel: the visual novel stage when switched on, TALKAPP when
        # switched on (and not a console dry run), and otherwise the Telegram
        # object, which for a config with neither is only the console dry-run
        # sink. Telegram is not a live channel for a resident character: she
        # runs on the VN stage, and no bot token or chat id is set here. Same
        # surface; the seam the LINE experiment proved.
        if bool((c.raw.get("vn") or {}).get("enabled")):
            from channels.vn_bot import VnInterface
            self.tg = VnInterface(c, self.vision, self.clock, self.store)
        elif c.talkapp.enabled and not c.telegram.console_only:
            from channels.talkapp_bot import TalkappInterface
            self.tg = TalkappInterface(c, self.vision, self.clock, self.store)
        else:
            # No live channel is configured. Telegram here is the console
            # sink, not a channel she talks on; a real Telegram bot would need
            # `telegram.bot_token` and `telegram.chat_id`, and this fork sets
            # neither. Kept explicit so nothing reads this path as "she is on
            # Telegram".
            self.tg = TelegramInterface(c, self.vision, self.clock, self.store)
        ok = self.tg.verify_connection()
        if not ok and c.talkapp.enabled and not args.console:
            # the hub is a separate process and run.cmd does not start it;
            # wait for it rather than die two seconds after boot
            waited = 0
            logger.log(f"[talkapp] hub not up; waiting up to {c.talkapp.boot_wait_seconds}s")
            while not ok and waited < c.talkapp.boot_wait_seconds:
                time.sleep(5)
                waited += 5
                ok = self.tg.verify_connection()
            if ok:
                logger.log(f"[talkapp] hub up after {waited}s")
        if not ok:
            # name the channel that failed rather than Telegram, which is not
            # the channel every config runs on
            logger.log(f"[fatal] channel unreachable ({type(self.tg).__name__})")
            sys.exit(1)
        if c.telegram.flush_queue_on_start:
            self.tg.flush_queue()

        self.tts = None
        if c.tts.enabled:
            from channels.tts_handler import TTSQueue
            self.tts = TTSQueue(c, self.tg)

        self.telemetry_module = None
        self.sys_monitor = None
        self.collector = None
        if self.sensors_on:
            from sensors import telemetry_collector
            self.telemetry_module = telemetry_collector
            if c.sensors.collector_in_process:
                from sensors.system_monitor import SystemMonitor
                self.sys_monitor = SystemMonitor(c.sensor_view)
                if c.sensors.gelbooru_enabled:
                    from sensors.gelbooru_classifier import GelbooruClassifier
                    self.sys_monitor.set_gelbooru_classifier(GelbooruClassifier(c.sensor_view))
                if c.sensors.chrome_scrape_enabled:
                    from sensors.web_scraper import WebScraper
                    self.sys_monitor.set_web_scraper(WebScraper(c.sensor_view, self.llm))
                self.sys_monitor.start()
                self.collector = telemetry_collector.TelemetryCollector(c.sensor_view, system_monitor_instance=self.sys_monitor)
            else:
                # His machine is watched once. The collector is its own process
                # (machine/collector.py, started by talkapp.cmd) and this only
                # reads what it writes: two bots each running the stack copied
                # his browser history twice a minute into one temp file and
                # wrote one feed with two id counters (HISTORY §11, 2026-09-03).
                from machine.monitor_client import RemoteMonitor
                self.sys_monitor = RemoteMonitor(c.sensor_view)
                self.sys_monitor.alive()
            if self.store.get("phone_last_consumed_id") is None:
                # first boot: do not let her digest a backlog from before she existed
                head = telemetry_collector.get_max_file_id(c.sensor_view)
                self.store.set("phone_last_consumed_id", head)
                logger.log(f"[phone] first boot, feed head at {head}")

        # his anime history is his machine's: a character with no sight of
        # him (`sensors` off by the existence table) does not open it
        self.mal = MalMonitor(c.sensor_view) if c.sensors.enabled else None
        for slot in PROGRAM_SLOTS:
            setattr(self, slot, None)
        self.state = State(c, self.store, self.clock)
        # What a feeling about another person is made of, before it has a
        # name (sim/primitives.py, docs/primitives.md). Only for a character
        # whose config asks for it; the first character's relationship is
        # still described by her cast meters and by sim/sentiment.py.
        self.primitives = None
        if getattr(c.primitives, "enabled", False):
            from sim.primitives import Primitives
            self.primitives = Primitives(c, self.store, self.clock)
            wire(self.state, primitives=self.primitives)
            try:
                self.primitives.seed(self.state._him_key() or "him", c.character_sheet)
            except Exception as e:
                logger.log(f"[primitives] could not seed from the sheet: {type(e).__name__}: {e}")
        # the body (embodied/): empty for a character whose config switches
        # each part off, and a character with no world has no map to be on
        self.health = Health(c, self.store, self.clock, self.state, self.weather, self.calendar)
        self.body = Body(c, self.store, self.clock, self.weather)
        # her flat and her week as things with a state (sim/household.py);
        # the director moves them, she meets them as facts
        self.household = None
        if c.household.enabled:
            from sim.household import Household
            self.household = Household(c, self.store, self.clock)
        self.money = Money(c, self.store, self.clock)
        self.memory = Memory(c, self.store, self.clock)
        # her own life, kept the way her facts about him are kept, and what she
        # is actually trying to do with a day
        self.self_memory = SelfMemory(c, self.store, self.clock, self.state, self.llm)
        self.goals = Goals(c, self.store, self.clock, self.state)
        self.records = Records(c, self.store, self.clock)
        # what these people are to her, as against how she feels today.
        # State holds it because longing, the delay and contagion all read it.
        self.sentiments = Sentiments(c, self.store, self.clock, self.state, self.records)
        wire(self.state, sentiments=self.sentiments)
        wire(self.health, sentiments=self.sentiments)
        # what she has decided he is (seeded from data/beliefs.json), and the
        # thing that works out what learning something costs her against it.
        # After Records: the scoring call is shown the girls whose opinion
        # runs her life, and building it any earlier is an AttributeError.
        # Not built at all for a character with no chat with him: the section
        # is off by the existence table, and an object built while its section
        # is off still ran its seed and printed a line about her picture of
        # him under the boot line that had just said the section was off.
        self.model_of_him = (ModelOfHim(c, self.llm, self.store, self.clock, self.memory)
                             if c.beliefs.enabled else None)
        # and what she has decided she is, which is what a day that does not
        # go her way is charged against (sim/goals.py)
        self.model_of_her = ModelOfHer(c, self.llm, self.store, self.clock, self.memory)
        # anxiety as a chain of inference that extends itself, rather than a
        # number that drifts. The gauge stays; it is the propensity now.
        self.spirals = Spirals(c, self.llm, self.store, self.clock, self.state, self.records,
                               self.model_of_her, self.self_memory)
        wire(self.state, spirals=self.spirals)
        # what breaks between them and what mends it. State holds a reference
        # because the decay has to know not to file an open one away.
        self.ruptures = Ruptures(c, self.llm, self.store, self.clock, self.state, self.records,
                                 self.model_of_her, self.self_memory, self.sentiments)
        wire(self.state, ruptures=self.ruptures)
        self.ick = Ick(c, self.llm, self.store, self.clock, self.state, self.model_of_him, self.records)
        # The one thing that reads his machine. A character whose sheet says
        # she sees nothing of him has no app to open, no count of how long he
        # has been quiet and no row in her save saying she looked: what she
        # has not got is absent, not switched off, the way the calendar loads
        # no data at all for a character with no world. Her open fired
        # fifty-one times with `sees_him: none` on her sheet, wrote to her
        # save each time, and logged a line about his silence, because only
        # the ROLE it feeds was off.
        self.phone = (Phone(c, self.store, self.clock, self.telemetry_module, self.sys_monitor)
                      if existence.sees_him(c) else None)
        # the hosted classifier for code's half of the split (`typesafe.py`):
        # built for every character, and off unless her bundle turns a use on
        self.typesafe = TypeSafe(c, self.clock)
        # the gauge appraisal (`sim/appraisal_gauge.py`) needs the client on the
        # state, and `State` was built above before the client existed. Set it
        # here rather than move either build; nothing runs `update_from_llm`
        # before the tick, so a later assignment is safe.
        self.state.typesafe = self.typesafe
        # and the ick and the ruptures, built above the client for the same
        # reason: their judgements move to Jev, so they need the same client
        # the state got
        self.ick.typesafe = self.typesafe
        self.ruptures.typesafe = self.typesafe
        # the inbound fan-out (`docs/system-one.md` item 2): one call per
        # message of his, answering the gate questions the flags guess at
        self.inbound = InboundSignals(c, self.typesafe, self.clock, self.store)
        self.reconcile = Reconcile(self.config, self.store, self.llm, self.clock,
                                   typesafe=self.typesafe)
        self.director = Director(c, self.llm, self.store, self.clock, self.weather, self.calendar, self.state,
                                 self.records, self.phone, self.health, self.body, None, self.money)
        self.receipts = Receipts(c, self.store, self.clock, self.sys_monitor)
        # A visual novel has no away channel: he is at the stage or the story is
        # not happening. This keeps when he was last here, stamped by the
        # channel, and is read once on his next turn (`sim/reunion.py`). It is
        # the read-receipt and inferred-presence model, replaced for a
        # player-driven character.
        self.reunion = Reunion(c, self.store, self.clock)
        # his meters come from the record, not from three numbers in cast.json.
        # Only on a save file that has never had them derived, so a played-in
        # relationship is never overwritten by a recalculation.
        from sim import derive as _derive
        _derive.apply_if_new(c, self.store, self.clock, self.state.relationships)
        self.impulse = Impulse(c, self.store, self.clock, self.receipts, self.spirals, self.sentiments)
        self.notes = Notes(c, self.llm, self.store, self.clock, self.state)
        self.diary = Diary(c, self.llm, self.store, self.clock, self.state, self.records, None)
        # what his messages left her feeling, on a cycle. The state reads it
        # through state.appraisal when it works affection out.
        self.stress = Stress(c, self.store, self.clock, self.state, self.records, self.goals,
                             self.ruptures, self.ick, self.sentiments, self.health, self.money,
                             self.model_of_her, self.spirals)
        wire(self.state, stress=self.stress)
        self.appraisal = Appraisal(c, self.llm, self.store, self.clock, self.state, self.sentiments,
                                   typesafe=self.typesafe)
        wire(self.state, appraisal=self.appraisal)
        self.reflection = Reflection(c, self.llm, self.store, self.clock, self.state, self.phone, None, self.notes, self.receipts)
        wire(self.spirals, sentiments=self.sentiments)
        # her sense of his anime: the weekly shelf check, his habits as facts,
        # and the series / seiyuu cards the lookup hands her (read-only on the
        # episode-history DB the daemon keeps current)
        self.anime_kb = None
        self.anime_sense = None
        if c.anime_sense.enabled:
            from sim.anime_kb import AnimeKB
            from sim.anime_sense import AnimeSense
            _hdb = c.sensor_view.mal_history_db
            if c.anime_sense.kb_enabled:
                self.anime_kb = AnimeKB(c, _hdb, c.sensor_view.mal_client_id)
            self.anime_sense = AnimeSense(c, self.store, self.clock, self.memory, _hdb)
        # Whether a work named near her is checked against her own filmography
        # before she talks about it, and how much of that filmography is here.
        # Said at boot because the failure it exists for is silent: a character
        # whose credits are not mirrored answers "not checked" to everything
        # and says nothing, which looks exactly like the check working.
        from sim import works as _works
        if _works.role_check_on(c):
            _who = self.anime_kb.person_row(_works.her_person_id(c)) if self.anime_kb else None
            if _who:
                import time as _t
                _n_cast = 0
                try:
                    _con = self.anime_kb._ro()
                    if _con is not None:
                        _n_cast = _con.execute(
                            "SELECT COUNT(DISTINCT p.anime_id) FROM person_role p "
                            "JOIN anime_kb k ON k.anime_id=p.anime_id "
                            "WHERE p.person_id=? AND k.cast_fetched_at IS NOT NULL",
                            (int(_works.her_person_id(c)),)).fetchone()[0]
                        _con.close()
                except Exception as _e:
                    logger.log(f"[roles] the second witness could not be counted: {type(_e).__name__}")
                logger.log(f"[roles] the role check is on: person {_who['person_id']} "
                           f"({_who['name']}), {_who['credits']} credit(s) over {_who['works']} "
                           f"work(s), mirrored "
                           f"{_t.strftime('%Y-%m-%d', _t.localtime(_who['fetched_at']))}; "
                           f"{_n_cast} of those works have a mirrored cast, which is the second "
                           f"witness a flat 'you were not in it' needs")
            else:
                logger.log(f"[roles] the role check is on for person "
                           f"{_works.her_person_id(c)}, but nothing of that person is mirrored: "
                           f"every work will answer 'not checked' and she will be told nothing. "
                           f"Run: python tools/mal_history.py seiyuu-mirror")
        elif getattr(c.role_check, "enabled", False):
            logger.log("[roles] the role check is on in the config and her sheet names nobody on "
                       "MyAnimeList, so it is off: nothing reads his mirror and no line about a "
                       "part is ever built")
        self.watchlist = Watchlist(c, self.store, self.clock)
        # What has been fetched about the world, kept once for the whole
        # machine (machine/retrievals.py): the page for an episode and the
        # verdict on it, a page condensed by a role that names nobody, a web
        # search, a game's card. Built here rather than by a program, because
        # it is the machine's: both characters open the same file, and one
        # fetch of an episode serves both. What each of them made of it stays
        # in her own save.
        self.retrievals = Retrievals(
            getattr(c.sensors, "retrievals_db", "data/retrievals.db"),
            by=retrieval_character_id(c),
            stale_seconds=getattr(c.sensors, "retrievals_inflight_stale_seconds", 600),
            wait_seconds=getattr(c.sensors, "retrievals_inflight_wait_seconds", 120),
            log=logger.log)
        # claims this character left behind by being killed mid-fetch
        self.retrievals.sweep_claims()
        self.recap = Recap(c, self.store, self.clock)
        wire(self.recap, retrievals=self.retrievals, anime_kb=self.anime_kb)
        # Which of several candidate works he means, when the deterministic
        # filters leave more than one (sim/resolver.py). Code decides when it
        # is asked and it never runs in a reply path; its answer about the
        # world goes in the machine's shared store, so both characters read
        # one answer and neither pays twice.
        from sim.resolver import Resolver
        self.resolver = Resolver(c, self.store, self.clock, self.anime_kb,
                                 typesafe=self.typesafe)
        wire(self.resolver, llm=self.llm, retrievals=self.retrievals)
        self.lookup = Lookup(c, self.llm, self.store, self.clock, self.mal, self.memory, self.anime_kb, self.recap,
                             typesafe=self.typesafe)
        wire(self.lookup, retrievals=self.retrievals, resolver=self.resolver)
        # what HE watches, noticed as he plays it rather than when he mentions
        # it, and for a character who is in many of the shows on his list, the
        # thing that opens her own record of that work (sim/watching_him.py)
        self.watching = None
        if c.watching.enabled:
            from sim.watching_him import WatchingHim
            self.watching = WatchingHim(c, self.store, self.clock, self.anime_kb,
                                        self.recap, c.sensor_view.mal_history_db)
            wire(self.watching, llm=self.llm)  # for the digest role
            # which of two editions of one franchise he opened, asked in the
            # worker thread and never in the poll
            wire(self.watching, resolver=self.resolver)
        wire(self.director, reflection=self.reflection)
        # what a note of his did to her is written by the private thought,
        # which has her sheet; the record it reads is the row the read just
        # wrote, and four callers would each have to remember it otherwise
        wire(self.notes, reflection=self.reflection)
        # promises with something outside her head on them (sim/commitments.py):
        # made in exchanges, reserved from her money, kept in the schedule,
        # settled at the compile from the record, raised by the person owed
        self.commitments = Commitments(c, self.llm, self.store, self.clock, self.state,
                                       self.money, None, self.self_memory)
        wire(self.director, commitments=self.commitments)
        # one truth about the day (sim/ledger.py): composed from what code
        # owns, read by everyone who writes what happens
        from sim.ledger import Ledger
        self.ledger = Ledger(c, self.store, self.clock, cast=None, commitments=self.commitments,
                             money=self.money, situation=None, calendar=self.calendar)
        wire(self.director, ledger=self.ledger)
        wire(self.commitments, ledger=self.ledger)
        self.recall = Recall(c, self.llm, self.store, self.clock, self.self_memory)
        self.intent = Intent(c, self.llm, self.store, self.clock, self.state, self.receipts, self.reflection,
                             self.phone, typesafe=self.typesafe)
        self.approach = Approach(c, self.llm, self.store, self.clock, self.state, self.ick,
                                 self.sentiments, self.records)
        self.rhythm = Rhythm(c, self.store, self.clock, self.state, self.llm, self.receipts,
                             typesafe=self.typesafe)
        from sim.him_profile import HimProfile
        self.him_profile = HimProfile(c, self.store, self.clock, rhythm=self.rhythm)
        if self.phone:
            wire(self.phone, him_profile=self.him_profile)
        wire(self.state, rhythm=self.rhythm)
        self.withholding = Withholding(c, self.llm, self.store, self.clock, self.state,
                                       self.sentiments, self.ruptures, self.receipts)
        wire(self.state, withholding=self.withholding)
        # where her body is, continuously: the place graph, journeys on the
        # clock with reality on the legs, fatigue. A character with no world
        # has no map and this stays still.
        from embodied.situation import Situation
        self.situation = Situation(c, self.store, self.clock, self.weather, None, self.body, self.state, self.calendar)
        # the map knows what a place costs to reach; the promises need it to
        # know whether she is going to make one (`Commitments.running_late`)
        wire(self.commitments, situation=self.situation)
        # what she expects him to do next, written down and checked
        from sim.care import Care
        self.care = Care(c, self.store, self.clock, self.state, self.sentiments)
        if self.phone:
            wire(self.phone, care=self.care)
        from sim.foresight import Foresight
        self.foresight = Foresight(c, self.llm, self.store, self.clock, self.state, self.rhythm, self.model_of_him, self.ick, self.receipts,
                                   typesafe=self.typesafe)
        from sim.expectations import Expectations
        self.expectations = Expectations(c, self.llm, self.store, self.clock, self.state, self.model_of_him, self.sentiments, self.rhythm, self.receipts,
                                         typesafe=self.typesafe)
        # What is coming, joined from the stores that already hold a dated
        # thing (sim/agenda.py): the calendar, her open promises, what he
        # said he would do, who the day's plan has taken out of it. It
        # decides nothing and writes nothing; it puts them in one order, for
        # the short block in the system half of her prompt and for /agenda.
        from sim.agenda import Agenda
        self.agenda = Agenda(c, self.store, self.clock)
        wire(self.agenda, calendar=self.calendar, commitments=self.commitments,
             expectations=self.expectations, ledger=self.ledger)
        from sim.wonder import Wonder
        self.wonder = Wonder(c, self.llm, self.store, self.clock, self.state, self.model_of_him, self.model_of_her, self.memory, self.sentiments,
                             typesafe=self.typesafe)
        from sim.discharge import Discharge
        self.discharge = Discharge(c, self.store, self.clock, self.state, self.stress)
        # the moments write their own memories (state._moment)
        wire(self.state, self_memory=self.self_memory)
        from sim.reactions import Reactions
        self.reactions = Reactions(c, self.store, self.clock, self.state)
        wire(self.tg, reaction_provider=self.reactions.current)
        wire(self.reactions, sender=self.tg.send_sticker)
        # The three passes the visual-novel stage reads: the staging director
        # (`sim/scene.py`), the 28-label feeling (`sim/emotion.py`) and the
        # draft guard (`sim/quality.py`). Machinery of the mind -- built for
        # every character, off unless her bundle turns the section on, and
        # read by the channel through the wires below.
        from sim.scene import SceneDirector
        self.scene = SceneDirector(c, self.store, self.clock, self.llm,
                                   typesafe=self.typesafe, weather=self.weather)
        from sim.emotion import Emotion
        self.emotion = Emotion(c, self.store, self.clock, self.llm, typesafe=self.typesafe)
        from sim.quality import Quality
        self.quality = Quality(c, self.store, self.clock, self.llm)
        # the out-of-character console behind the director button: it reads the
        # current scene (`self.director`) and the catalogs (`self.scene`) and
        # proposes a scene for his approval. Off unless her bundle turns it on.
        from sim.stage_manager import StageManager
        self.stage_manager = StageManager(c, self.store, self.clock, self.llm,
                                          self.director, self.scene)
        wire(self.tg, scene_provider=self.scene.current, emotion_provider=self.emotion.classify)
        wire(self.tg, present_notice=self.reunion.stamp)
        wire(self.tg, speak_now=self.speak_now)
        wire(self.tg, gauge_nudge=self._touch_gauge_nudge)
        # the director-button console: the channel serves the chat and hands a
        # message to it. It only proposes; approving and writing are later steps.
        wire(self.tg, stage_chat=self.stage_manager.chat,
             stage_history=self.stage_manager.history,
             stage_snapshot=self.stage_manager.status)
        wire(self.intent, wonder=self.wonder, foresight=self.foresight)
        wire(self.withholding, foresight=self.foresight)
        wire(self.impulse, foresight=self.foresight)
        wire(self.impulse, rhythm=self.rhythm)  # his hours gate her reaching out
        self._foresee_refresh_ts = 0.0
        wire(self.state, situation=self.situation)
        wire(self.director, situation=self.situation)
        wire(self.ledger, situation=self.situation)
        self.attachment = Attachment(c, self.store, self.clock, self.state, self.sentiments, self.ruptures,
                                     self.receipts, self.rhythm, self.model_of_her, self.self_memory, self.impulse)
        wire(self.impulse, attachment=self.attachment)
        wire(self.withholding, attachment=self.attachment)
        wire(self.state, attachment=self.attachment)
        wire(self.intent, attachment=self.attachment)
        self.outlook = Outlook(c, self.llm, self.store, self.clock, self.state, self.calendar, self.phone, None, self.records, self.health, self.money, self.model_of_her, self.watchlist, self.recap)
        wire(self.director, outlook=self.outlook)
        self.persona = Persona(c, self.llm, self.store, self.clock, self.state, self.mal, self.receipts, self.notes, self.records, None, self.diary, self.body, None, self.money, self.memory, self.reflection, self.outlook)
        wire(self.persona, ledger=self.ledger, situation=self.situation, foresight=self.foresight)
        wire(self.persona, expectations=self.expectations, wonder=self.wonder)
        wire(self.persona, agenda=self.agenda)
        wire(self.persona, reunion=self.reunion)
        # the staging pass and the draft guard reach her reply (`sim/scene.py`,
        # `sim/quality.py`), and her tokens stream to the VN channel as they
        # are written when one has a sink for them
        wire(self.persona, scene_director=self.scene, quality=self.quality)
        if hasattr(self.tg, "stream_delta"):
            self.persona.stream_sink = self.tg.stream_delta
        # what she DOES with the phone in her hand, decided by her and carried
        # out by code (sim/pick.py). Built for every character; which tools she
        # is offered follows from what kind of thing she is.
        # what she has already said to whom today, across rooms (sim/said_today.py).
        # The mind's: every character keeps one, and every piece of its state is in
        # the save, so a second instance elsewhere in the process is the same thing
        # seen twice.
        from sim.said_today import SaidToday
        self.said_today = SaidToday(c, self.store, self.clock)
        from sim.pick import PhonePick
        self.pick = PhonePick(c, self.llm, self.store, self.clock,
                              live=not (args.sim or self.replay))
        wire(self.pick, state=self.state, persona=self.persona, impulse=self.impulse,
             receipts=self.receipts, phone=self.phone, ledger=self.ledger,
             director=self.director, wonder=self.wonder, outlook=self.outlook,
             said_today=self.said_today)
        # the operator's view for the app, and the command channel that keeps
        # slash commands out of her chat
        from sim.ops import Ops
        self.ops = Ops(self)
        wire(self.tg, ops_provider=self.ops.payload)
        wire(self.tg, voice_model_provider=self.llm.voice_model_report)
        wire(self.tg, voice_model_setter=self.llm.voice_model_cmd)
        wire(self.tg, stage_model_provider=self.llm.stage_model_report)
        wire(self.tg, stage_model_setter=self.llm.stage_model_cmd)
        wire(self.persona, anime_sense=self.anime_sense, watching=self.watching, household=self.household)
        # the continuity editor's own claim about his list, checked against it
        # before the verdict stands (`docs/role-check.md` §4b)
        wire(self.persona, anime_kb=self.anime_kb)
        if self.lookup:
            wire(self.persona, lookup=self.lookup)  # a search she asks for in a draft
        wire(self.director, household=self.household)
        wire(self.impulse, watching=self.watching)
        if self.lookup:
            wire(self.lookup, watching=self.watching)  # the open episode anchors a character name
        # The modules that move a primitive or are gated by one get a handle.
        # This is here rather than beside the construction because every one of
        # them is built after it: the loop that used to do this ran at line 190
        # and named `commitments`, which is built at line 328, so it attached
        # nothing and a kept promise -- the one entry in the ledger she
        # controls -- has never counted. A ledger that can only run against
        # her is not a ledger.
        if self.primitives is not None:
            for obj in (self.commitments, self.ick, self.withholding, self.ruptures, self.impulse):
                if obj is not None:
                    wire(obj, primitives=self.primitives)
        # attention is a budget code allocates (sim/attention.py)
        from sim.attention import Attention
        self.attention = Attention(c, self.store, self.clock)
        # the day read as one story at the compile, flag only
        self.coherence = Coherence(c, self.llm, self.store, self.clock, ledger=self.ledger)
        self.attention.hooks = {"nag": self.anime_sense.charge_shown if self.anime_sense else (lambda: None),
                                "show_him": (lambda: None)}
        wire(self.persona, attention=self.attention)
        # what she happens to know, retrieved when the moment reaches for it
        # (sim/lore.py). Off unless a character has a record of her own.
        self.lore = None
        if c.lore.enabled:
            from sim.lore import Lore
            self.lore = Lore(c, self.store, self.clock)
            wire(self.persona, lore=self.lore)
        # one thread, both rooms, one clock (sim/thread.py)
        from sim.thread import Thread
        self.thread = Thread(c, self.store, self.clock)
        wire(self.persona, thread=self.thread)
        # the two the judges' view of her is built from, the same sources
        # the loop hands `generate`: the scene the director settled and the
        # digest of his machine (`Persona.judge_view`)
        wire(self.persona, director=self.director, phone=self.phone)
        # and the judges read that view. A judge gets what SHE has -- the same
        # situation block and the same carrying block, built at its own call
        # time -- and never her character sheet (`Config.ROLE_STANCE`).
        wire(self.intent, persona=self.persona)
        wire(self.foresight, persona=self.persona)
        wire(self.appraisal, persona=self.persona)
        # her past as cards, and the meaning-search over it (sim/cards.py, sim/embed.py)
        from sim.cards import Cards
        from sim.embed import Embeddings
        self.embed = Embeddings(c, self.store)
        self.episodes = Cards(c, self.llm, self.store, self.clock)
        wire(self.episodes, embed=self.embed)
        wire(self.thread, episodes=self.episodes)
        wire(self.recall, episodes=self.episodes, embed=self.embed, memory=self.memory)
        # a cue he typed in English or romaji reaching a record written in
        # Japanese: his own list is where both spellings of a title are
        # written down (`docs/memory.md` §3)
        wire(self.recall, anime_kb=self.anime_kb)
        # what she knows about him and what she remembers of her own life are
        # searched by meaning as well as by words, off the same vectors
        wire(self.memory, embed=self.embed)
        wire(self.self_memory, embed=self.embed)
        # What she does with what she has seen: one named stance out of a
        # ranked table, pinned into her section and the owner of the slot
        # (sim/stances.py, docs/stances.md).
        self.stances = None
        if getattr(getattr(c, "stances", None), "enabled", False):
            from sim.stances import Stances
            self.stances = Stances(c, self.store, self.clock, self.state)
            wire(self.stances, primitives=self.primitives, ick=self.ick,
                 lore=self.lore, phone=self.phone)
            wire(self.state, stances=self.stances)
            wire(self.persona, stances=self.stances)
        # a second reader of everything she carries, who is not her (sim/nudge.py)
        from sim.nudge import Nudge
        self.nudge = Nudge(c, self.llm, self.store, self.clock)
        wire(self.nudge, state=self.state)
        wire(self.persona, nudge=self.nudge, model_of_him=self.model_of_him, him_profile=self.him_profile)
        wire(self.persona, model_of_her=self.model_of_her, spirals=self.spirals, ruptures=self.ruptures)
        wire(self.persona, sentiments=self.sentiments, ick=self.ick, self_memory=self.self_memory)
        wire(self.persona, goals=self.goals, commitments=self.commitments)
        wire(self.outlook, commitments=self.commitments)
        wire(self.persona, rhythm=self.rhythm, withholding=self.withholding, attachment=self.attachment)
        wire(self.director, attachment=self.attachment, goals=self.goals, spirals=self.spirals)
        wire(self.intent, ruptures=self.ruptures)
        wire(self.reflection, records=self.records, sentiments=self.sentiments, commitments=self.commitments)
        self.ctx = ContextView(c, self.store, self.clock, self.persona, self.memory, self.state, self.director, self.phone)
        self.delivery = Delivery(c, self.clock, self.store, self.tg, self.tts)
        if getattr(self.tg, "save_busy_provider", None) is None and hasattr(self.tg, "save_busy_provider"):
            self.tg.save_busy_provider = lambda: self.delivery.busy() or bool(self.store.unread_user_messages())
        if hasattr(self.tg, "reply_draw_provider"):
            from persona import delivery as _reply_swipes
            self.tg.reply_draw_provider = lambda hub_id: _reply_swipes.swipe(self, hub_id)
            self.tg.reply_sit_provider = lambda hub_id, n: _reply_swipes.sit(self, hub_id, n)
        # the reply's own prompt: a burst that has actually left is filed
        # with the call it came out of, so it can be drawn again later
        wire(self.delivery, persona=self.persona)
        self.busy_since = None
        self.pending_beats = []
        # Another running character, talking to her over the same hub
        # (sim/peers.py, docs/peer-talk.md). Built for every character and
        # idle for one with no contacts, because who her peers are is her own
        # config and nothing about her body, her world or her account decides
        # whether she can have one. Not the path his messages take: none of
        # the relationship with him runs on somebody else's message.
        from sim.peers import Peers
        self.peers = Peers(c, self.llm, self.store, self.clock, self.tg, self.state,
                           self.persona, self.thread, ledger=self.ledger)
        # and now the rest of her: her world, her people, her account, her
        # sight -- whatever the program that runs her says she has
        self.program.build(self)
        # one pass over the save for anything the record's own label reached
        repairs.strip_stamps_once(self)
        # and one pass to hand the machine what she already holds about the world
        repairs.share_recaps_once(self)
        # a page is named by the WORK now, not by a title two works share
        repairs.key_pages_by_id_once(self)
        # and the one thing she knows by name whose text is another edition's
        repairs.drop_wrong_editions_once(self)
        # and the one memory of an exchange that never happened
        repairs.drop_invented_recall_once(self)
        repairs.retire_his_digests_once(self)
        repairs.retire_his_reflections_once(self)
        # and the arithmetic those two left behind
        repairs.retire_him_residue_once(self)
        repairs.retire_his_mood_once(self)
        # a restart must not leave him read and unanswered
        self.recover_lost_reply()

        legacy = self.store.get("open_threads")
        if legacy and not self.store.all_threads(1):
            self.records.sync_threads([str(t) for t in legacy], [])
            logger.log(f"[records] moved {len(legacy)} legacy thread(s) into the threads table")
        self.coasting_block = None
        self.woke = False
        self.schedule = None
        self.today = None
        self.compiled_dates = set(self.store.get("compiled_dates", []))
        self.last_status_wall = 0
        # `reply_plan` is a property over kv `reply_plan`; nothing is set here,
        # because a boot that wrote None over it would be the restart throwing
        # away the decision this keeps
        self.sim_says = self._parse_says(args.say)
        self.sim_end_ts = None
        if args.sim and args.hours > 0:
            self.sim_end_ts = self.clock.now_ts() + args.hours * 3600
        if self.replay:
            self.sim_end_ts = self.replay["to"]

        cast_txt = self.state.relationships
        if self.config.character.existence.in_world:
            logger.log(f"[boot] her time {self.clock.stamp()} | his time {self.clock.user_now().strftime('%Y-%m-%d %H:%M')} | offset {self.clock.offset_hours():+.0f}h | clock {self.clock.mode}")
        else:
            logger.log(f"[boot] one clock, his: {self.clock.stamp()} | she has no world of her own to keep a time in | clock {self.clock.mode}")
        # the arm he last chose in the chat, before anything builds a prompt
        lang.set_saved(self.store.get("instructions_override"))
        logger.log("[boot] " + lang.status(self.config))
        logger.log(f"[boot] weather: {self.weather.describe()}")
        logger.log(f"[boot] calendar: {self.calendar.describe(self.clock.now().date())}")
        logger.log(self.agenda.boot_line())
        _pin = self.llm.voice_pin_line()
        if _pin:
            logger.log(_pin)
        logger.log(self.pick.boot_line())
        # the stop before this run, if the tool that made it left a marker:
        # the stretch nobody was writing her goes on her record as a blank
        # rather than being invented later (`sim/downtime.py`). Never in a
        # replay, which is re-living a hole rather than admitting to one.
        if not self.replay:
            try:
                downtime.on_boot(self)
            except Exception as e:
                logger.log(f"[boot] the stop before this one was not settled: {type(e).__name__}: {e}")
        for _w in self.unwired():
            logger.log(f"[wiring] built and not attached: {_w}")

    def unwired(self):
        """Declared wires still None on something the App holds, where the App
        has the thing to attach: built and never wired, the silent fault the
        declarations exist to catch (sim/wiring.py). A program slot the
        program did not build is not listed: nothing was there to attach."""
        alias = {"graph": "social_graph", "npc": "people", "sleep_source": "sight"}
        out = set()
        for attr, obj in list(vars(self).items()):
            for name in getattr(type(obj), "WIRES", ()):
                if getattr(obj, name, None) is None and getattr(self, alias.get(name, name), None) is not None:
                    out.add(f"{attr}.{name}")
        return sorted(out)

    def _parse_says(self, says):
        out = []
        for s in says:
            if "|" in s:
                hm, text = s.split("|", 1)
                out.append({"hm": hm.strip(), "text": text.strip(), "done": False})
        return out

    # ---------------- day boundary ----------------

    def ensure_day(self):
        d = self.clock.date_str()
        if d == self.today:
            return
        if self.today and self.today not in self.compiled_dates:
            # not while she is mid-conversation: `maybe_compile` closes
            # yesterday in the small hours once the night is actually over
            if self._program_call("exchange_live", default=False):
                logger.log(f"[timeline] {self.today} is not told yet: the chat ran past midnight")
            else:
                self.compile(self.today)
        self.today = d
        s = self.store.get_schedule(d)
        if not s:
            # the shape of a day is the program's: a schoolgirl's timetable,
            # or a flat and a week of her own
            s = self.program.plan_day(self, d)
        self.schedule = s
        self.store.set("health_note_today", self.health.schedule_note(d) if self.config.health.enabled else "")
        self.store.set("money_note_today", self.money.line())
        self._program_call("day_planned", s, d)
        logger.log(f"[day] {d} ({self._program_call('day_line', default='') or 'no calendar'})")
        self.anime_day(d)

    def _program_call(self, name, *a, default=None, **kw):
        """A hook of the program, if she has it. What a program does not
        define is not hers, and the runtime does not miss it."""
        fn = getattr(self.program, name, None)
        if fn is None:
            return default
        return fn(self, *a, **kw)

    def anime_day(self, d):
        """Her weekly look at his anime list, and his watching habits as facts.
        The shelf check becomes today's pending hint; the first free scene with
        her phone picks it up as a share_hint (intent/persona decide the rest)."""
        if not self.anime_sense:
            return
        try:
            if self.anime_sense.habits_due(d):
                self.anime_sense.habits(d)
            if self.anime_sense.shelf_check_due(d):
                hint = self.anime_sense.shelf_check(d)
                if hint:
                    self.store.set("anime_shelf_hint_pending", {"date": d, "hint": hint})
        except Exception as e:
            logger.log(f"[anime] day hook failed: {type(e).__name__}: {e}"[:200])

    def foresee_after(self, bubbles, kind):
        """After her bubbles exist: what she expects of him now. On a thread,
        because the send is already on one and the loop must not wait."""
        try:
            sent = "\n".join(b if isinstance(b, str) else str(b.get("text", b)) for b in (bubbles or []))[:600]
        except Exception:
            sent = ""
        # the weekly shelf hint is done the moment she actually brings his
        # list up, whichever path the message came out of
        try:
            if self.anime_sense and self.store.get("anime_shelf_hint_pending") and self.anime_sense.mentioned(sent):
                self.store.set("anime_shelf_hint_pending", None)
                logger.log("[anime] she brought his list up; the shelf hint is done for the week")
        except Exception:
            pass
        def work():
            try:
                self.foresight.predict(sent, kind)
            except Exception as e:
                logger.log(f"[foresee] failed: {type(e).__name__}: {e}")
        threading.Thread(target=work, daemon=True).start()

    def maybe_foresee_refresh(self):
        """While he is quiet, a fresh reading of what the silence means, a
        few hours apart, so the situation block is not carrying a window
        she gave him yesterday."""
        c = self.config.foresight
        if not c.enabled:
            return
        if self.silent_hours() < c.refresh_silent_from or self.foresight.live():
            return
        if self.clock.now_ts() - self._foresee_refresh_ts < c.refresh_hours * 3600:
            return
        if self.phone_access() == "none" or self.store.unread_user_messages() or self.delivery.busy():
            return
        self._foresee_refresh_ts = self.clock.now_ts()
        self.foresee_after([], "waiting")

    def maybe_shelf_nag(self):
        """A pending weekly shelf hint becomes the scene's share_hint once she is
        free with her phone and nothing else is going on; then the impulse path
        runs and she may or may not say it."""
        p = self.store.get("anime_shelf_hint_pending")
        if not p or p.get("date") != self.clock.date_str():
            if p:
                self.store.set("anime_shelf_hint_pending", None)
            return
        cur = self.director.current
        if not cur or self.phone_access() != "free" or self.store.unread_user_messages() or self.delivery.busy():
            return
        # it used to clear itself when ANY self-started message of hers went
        # out after it was offered -- one goodnight text at 01:27 killed the
        # week's nag (2026-08-29). It now clears only when she actually brings
        # his list up (foresee_after -> anime_sense.mentioned), after riding
        # nag_shows_max prompts, or at her day's end; nag_line also puts it in
        # her reply prompts, so a Saturday spent mid-conversation still sees it.
        if not p.get("offered_ts"):
            p["offered_ts"] = self.clock.now_ts()
            self.store.set("anime_shelf_hint_pending", p)
            logger.log("[anime] shelf hint live for the day (scene share_hint + her prompts)")
        cur["share_worthy"] = True
        cur["share_hint"] = p["hint"]
        self.maybe_impulse(cur, self.latest_digest())

    def maybe_generate_schedule(self):
        if self.schedule and self.schedule.get("notes") == "(skeleton, pending)":
            gen_at = hm_to_minutes(self.config.schedule.generate_at)
            now_m = self.clock.now().hour * 60 + self.clock.now().minute
            if now_m >= gen_at:
                self.store.set("health_note_today", self.health.schedule_note(self.clock.date_str()) if self.config.health.enabled else "")
                self.store.set("money_note_today", self.money.line())
                self._program_call("before_generate")
                self.schedule = self.program.generate(self)
                self._program_call("day_planned", self.schedule, self.clock.date_str())

    def maybe_compile(self):
        """The day is told when her day is actually over, not at a fixed hour.

        `compile()` FLUSHES a live exchange -- a conversation open at the
        compile ends where it stands so the day's record holds it -- and
        23:55 was chosen when the group chat died at nine. Now the chat can
        run to 02:20, so the fixed hour was cutting off the late night it had
        just been given permission to have. It holds while an exchange is
        live and until the night's last light has passed, and a night that
        ran over midnight is closed in the small hours instead."""
        import datetime
        c = self.config.timeline
        now = self.clock.now()
        now_m = now.hour * 60 + now.minute
        d = self.clock.date_str()
        quiet = hm_to_minutes(getattr(c, "compile_quiet_by_hm", "04:00"))
        live = self._program_call("exchange_live", default=False)

        # a night that ran past midnight: yesterday is still waiting to be told
        prev = (now.date() - datetime.timedelta(days=1)).isoformat()
        if prev not in self.compiled_dates and not self.store.get_day(prev):
            if live and now_m < quiet:
                return
            logger.log(f"[timeline] closing {prev} at {self.clock.hm()}: the night ran past midnight")
            self.compile(prev)
            return

        if d in self.compiled_dates:
            return
        if now_m < hm_to_minutes(c.compile_at):
            return
        if getattr(c, "compile_hold_for_chat", True):
            if live:
                if not getattr(self, "_compile_waiting", False):
                    logger.log("[timeline] the compile is waiting: she is still in a conversation")
                    self._compile_waiting = True
                return
            # the group has not turned in yet tonight: hers to say
            if self._program_call("compile_hold", d, now_m, default=None) == "":
                return
        self._compile_waiting = False
        self.compile(d)

    def backup_db(self, tag):
        """A dated copy of the save file under data/backups, kept for backup_keep days."""
        import shutil, glob
        src = self.config.logging.db_path
        if not os.path.exists(src) or src.endswith("dryrun.db"):
            return
        d = self.config.logging.backup_dir
        os.makedirs(d, exist_ok=True)
        # named after the save it copies, not after the word "world". The
        # second character's bot wrote her save over his dated backup on her
        # first day, and the pruning below -- one glob, one keep count -- would
        # have eaten his history a day at a time from there. His file is
        # data/world.db, so his backups keep the name they have always had.
        stem = os.path.splitext(os.path.basename(src))[0] or "world"
        dst = os.path.join(d, f"{stem}-{tag}.db")
        try:
            with self.store.lock:
                self.store.conn.commit()
                shutil.copy2(src, dst)
            old = sorted(glob.glob(os.path.join(d, f"{stem}-*.db")))[:-self.config.logging.backup_keep]
            for f in old:
                os.remove(f)
            logger.log(f"[backup] {dst}")
        except OSError as e:
            logger.log(f"[backup] failed: {e}")

    def compile(self, d):
        self.backup_db(d)
        # a conversation with another character still open is part of the day
        if self.peers is not None:
            try:
                self.peers.flush()
            except Exception as e:
                logger.log(f"[peer] not closed for the compile: {type(e).__name__}: {e}")
        self._program_call("compile", d, "open")
        timeline.compile_day(self.config, self.llm, self.store, self.clock, d, self.state, self.records, self.diet, self.memory,
                             self.goals, self.self_memory, self.model_of_her, ledger=getattr(self, "ledger", None),
                             orbit=getattr(self, "orbit", None), episodes=self.episodes)
        # how much of her day was him, measured from the record, kept per day
        # How much of her day was him: a measurement of a relationship, so
        # a character who has no chat with him has nothing to measure and
        # gains no row about him at the compile.
        try:
            if existence.has_chat(self.config):
                from sim.worldshare import record as _ws_record
                logger.log("[world] " + _ws_record(self.store, self.clock, d))
        except Exception as e:
            logger.log(f"[world] not measured: {type(e).__name__}: {e}")
        self._program_call("compile", d, "told")
        # how much she cares, from the record, one row a day
        try:
            # the section is off by the existence table for a character with
            # no chat with him, and an object built while its section is off
            # still wrote its row a day
            m = self.care.record() if self.config.care.enabled else None
            try:
                self.expectations.learn_habits()
            except Exception as e:
                logger.log(f"[expect] habits not learned: {type(e).__name__}: {e}")
            if m:
                logger.log(f"[care] investment {m['investment']}, checking expected {m['checking_expected_per_day']} / actual {m['checking_actual_per_day']} a day")
        except Exception as e:
            logger.log(f"[care] not measured: {type(e).__name__}: {e}")
        # predictions he never answered are silences now
        try:
            n = self.foresight.settle()
            if n:
                logger.log(f"[foresee] {n} prediction(s) closed unanswered at the compile")
        except Exception as e:
            logger.log(f"[foresee] not settled: {type(e).__name__}: {e}")
        # promises whose day has come, settled from the record -- before the
        # graph update, so the person she let down witnesses it today
        if self.config.commitments.enabled:
            try:
                self.commitments.settle(d)
            except Exception as e:
                logger.log(f"[commit] not settled: {type(e).__name__}: {e}")
        self._program_call("compile", d, "settled")
        # the questions she had about him that the day answered on its own
        try:
            self.wonder.review(d)
        except Exception as e:
            logger.log(f"[wonder] review failed: {type(e).__name__}: {e}")
        # the day read as one story: the seams between its parts, flagged,
        # never rewritten (`/coherence`, `/absurd` SEAMS)
        try:
            self.coherence.review(d)
        except Exception as e:
            logger.log(f"[coherence] review failed: {type(e).__name__}: {e}")
        # a show of her own when the list runs short or a week has passed
        try:
            self.watchlist.pick_own(self.llm, self._program_call("watch_sources", default={}) or {}, kb=self.anime_kb)
        except Exception as e:
            logger.log(f"[watchlist] pick failed: {type(e).__name__}: {e}")
        # what being on her phone with him cost her with them, from the
        # record: her messages that landed while a scene had people in it
        if self.config.sentiment.enabled and existence.has_chat(self.config):
            try:
                self.sentiments.phone_debt(d)
            except Exception as e:
                logger.log(f"[circle] phone debt not settled: {type(e).__name__}: {e}")
        # after the narrative exists, so the chains can be put against it
        if self.config.spiral.enabled:
            try:
                self.spirals.settle(d)
            except Exception as e:
                logger.log(f"[spiral] not settled: {type(e).__name__}: {e}")
        self.compiled_dates.add(d)
        self.store.set("compiled_dates", sorted(self.compiled_dates)[-60:])
        self._program_call("compile", d, "end")
        import datetime as _dt
        if self.config.weekly.enabled and _dt.date.fromisoformat(d).weekday() == self.config.weekly.weekday:
            timeline.compile_week(self.config, self.llm, self.store, self.clock, d, self.state)

    # ---------------- helpers ----------------

    def world_now(self):
        """world_terms plus how much of him she expects at this hour (0.4 at
        an hour he is never about, 1.0 when he usually is, or said he would
        be), which weights the loneliness climb: an hour he is never about
        in is not an hour of being left."""
        w = self.world_terms()
        try:
            u = float(self.rhythm.usual_now())
            w["usual_w"] = 0.4 + 0.6 * max(0.0, min(1.0, u))
        except Exception:
            w["usual_w"] = 1.0
        return w

    def world_terms(self):
        """What the deterministic state terms need to know about right now."""
        w = self.config.state.world
        now = self.clock.now()
        try:
            cur = self.weather.current(now)
            feels = cur.get("feels")
        except Exception:
            feels = None
        blk = sched.block_at(self.schedule["blocks"], now) if self.schedule else {}
        act = ((blk.get("activity") or "") + " " + (blk.get("with") or "") + " " + (blk.get("location") or "")).lower()
        scene = self.director.current or {}
        if self.director.scene_fresh():
            act += " " + ((scene.get("activity") or "") + " " + (scene.get("with") or scene.get("with_who") or "") + " " + (scene.get("location") or "")).lower()
        kind = ""
        # a block with a friend's name in it is social; the names are the roster's
        social_words = list(w.social_keywords) + [str(n).lower() for n in roster.everyone(self.config)]
        if any(k in act for k in social_words):
            kind = "social"
        elif any(k in act for k in w.dull_keywords):
            kind = "dull"
        loc = ((scene.get("location") if self.director.scene_fresh() else None) or blk.get("location") or "").lower()
        indoors = any(k in loc for k in ("home", "room", "kitchen", "school", "class", "cafe", "house", "bath", "bed"))
        asleep = bool(self.director.asleep_block(self.schedule)) if self.schedule else False
        late = (now.hour * 60 + now.minute) >= hm_to_minutes(w.late_from) and not asleep
        days_to_exam = None
        for e in self.calendar.events(now.date(), lookahead_days=w.exam_days):
            if "exam" in e["name"].lower():
                d = 0 if e["when"].startswith("today") else int(e["when"].split()[1]) if e["when"].startswith("in ") else 1
                days_to_exam = d if days_to_exam is None else min(days_to_exam, d)
        st = self.receipts.status() if self.receipts else None
        ignored = st["minutes"] if st and st.get("state") == "read" else 0
        health = self.health.effects() if self.config.health.enabled else {}
        self.state.body_tags = self.health.tags() if self.config.health.enabled else []
        fresh = self.director.scene_fresh()
        env = self.body.setting(scene, blk, fresh) if self.config.environment.enabled else {}
        meal = self.body.meal_kind(scene, blk, fresh) if self.config.needs.enabled else ""
        if meal == "meal" and "hunger" in self.state.gauges and self.state.gauges["hunger"] > self.config.needs.hungry_from * 0.5:
            self.store.set("last_meal_ts", self.clock.now_ts())
        self.state.need_tags = (self.body.hunger_tags(self.state.gauges) if self.config.needs.enabled else []) + self.money.tags()
        if self.config.needs.enabled and env:
            # hours since the last decay, the same span the world terms will use
            self.body.note_exposure(max(0.0, (self.clock.now_ts() - self.state.last_decay_ts) / 3600.0))
        his_pc_active = bool(self.phone and not self.phone.user_idle())
        return {"feels": feels, "indoors": indoors, "asleep": asleep, "late": late, "block_kind": kind,
                "days_to_exam": days_to_exam, "read_ignored_minutes": ignored, "health": health, "his_pc_active": his_pc_active,
                "ambient_feels": env.get("ambient_feels", feels), "setting": env.get("setting", ""), "meal": meal}

    def silent_hours(self):
        last = self.store.last_message("user")
        if not last:
            return 24.0
        return max(0.0, (self.clock.now_ts() - last["ts"]) / 3600.0)

    def phone_access(self):
        # The resident has no phone to be away from: she can answer whenever she
        # is awake, and her sleep is read off his machine (resident/sight.py).
        # The scene's own field is not consulted, because the one sleep scene
        # of the night says "none" for as long as it stands, and his message at
        # nine in the morning from work found it still standing.
        if self.sight:
            return "none" if self.sight.asleep_block() else "free"
        return self.director.phone_access(self.schedule)

    # ---------------- replay: a hole re-lived on her clock ----------------
    # The one-scene catch-up (catch_up, director._hole) writes hours of her
    # day as a scene stamped now, and everything downstream then runs at now
    # with its own "is this due" clock: on 2026-08-31 the anticipation dreaded
    # "tomorrow's" ceremony at 11:44 after the scene had stood her through it,
    # and the state took three hours as one quiet tick. A replay has no such
    # seam: the clock is pinned to the hole and stepped through it, every
    # mechanism fires when it was due from its own logic, every record lands
    # at its real time. Nothing reaches him from inside the hole -- a line
    # written at 09:30 cannot be sent at 11:50 as if it were 09:30 -- so
    # sends, the reply, the impulse, X actions and phone looks are off, and
    # the live loop answers what is unread with the gap honest in the thread.

    def _replay_setup(self, args, c):
        """Before anything opens: the window, the backup, the clock."""
        import shutil

        def parse(s):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return time.mktime(time.strptime(s, fmt))
                except ValueError:
                    pass
            raise SystemExit(f"--replay: bad time {s!r} (machine local, YYYY-MM-DD HH:MM[:SS])")
        t0, t1 = parse(args.replay[0]), parse(args.replay[1])
        if not t0 < t1 <= time.time():
            raise SystemExit("--replay: FROM must be before TO, and TO not in the future")
        # the estimate comes before anything is touched (his rule: an extreme
        # catch-up is reported with its cost, and may be skipped as a gap)
        speed = args.speed or float(c.replay.speed)
        ticks = max(1, int((t1 - t0) / 60 / max(1, c.director.tick_minutes)))
        usd = ticks * float(c.replay.usd_per_tick)
        wall = (t1 - t0) / speed / 60 + ticks * 0.3
        print(f"[replay] estimate for {(t1 - t0) / 60:.0f} min of her time: ~{ticks} ticks, ~{ticks * 3} model calls, "
              f"~${usd:.2f} at replay.usd_per_tick {c.replay.usd_per_tick}, ~{wall:.0f} min of wall time at x{speed:g}")
        if getattr(args, "gap", False):
            return {"from": t0, "to": t1, "gap": True, "usd": usd}
        if usd > float(c.replay.cost_warn_usd) and not getattr(args, "yes", False):
            raise SystemExit(f"[replay] ~${usd:.2f} is over replay.cost_warn_usd ({c.replay.cost_warn_usd}); nothing touched. "
                             f"Run again with --yes to replay anyway, or --gap to write a temporal-gap event for the window instead.")
        db = c.logging.db_path
        dest = os.path.join("data", "retired", time.strftime("%Y%m%d_%H%M%S") + "_replay")
        os.makedirs(dest, exist_ok=True)
        for suf in ("", "-wal", "-shm"):
            if os.path.exists(db + suf):
                shutil.copy2(db + suf, os.path.join(dest, os.path.basename(db) + suf))
        real = WorldClock(c)
        her0 = real.to_char(t0)
        # the sim clock starts on the whole minute (sim_start has no seconds)
        # but the window keeps its seconds: floored, FROM fell 25 s before the
        # last real scene and the first replay swept that scene up with the hole
        c.clock.mode = "sim"
        c.clock.sim_start = her0.strftime("%Y-%m-%d %H:%M")
        c.clock.sim_speed = speed
        c.telegram.console_only = True
        return {"from": t0, "to": t1, "backup": dest, "speed": speed, "usd": usd}

    def temporal_gap(self, t0, t1, why="", note=""):
        """The alternative to covering a hole: say so. One event of kind
        `gap` at the hole's end, the director pointed past it so `_hole`
        never asks for it, the missed rows marked skipped. The compile and
        the coherence read see an honest blank, never a stretch invented at
        the wrong hour.

        `note` is a second sentence in the event, for a hole whose cause is
        known -- the machine was stopped, the account ran out of money. The
        span carries its date at each end when the two ends fall on
        different days of hers, and its length in the unit that fits it: a
        stop of three days used to read `[22:14-08:00] ... (4306 min)`,
        which says a stretch of one evening."""
        her0, her1 = self.clock.to_char(t0), self.clock.to_char(t1)
        fmt = "%m-%d %H:%M" if her0.date() != her1.date() else "%H:%M"
        text = (f"[{her0.strftime(fmt)}-{her1.strftime(fmt)}] the record has nothing for this stretch "
                f"({downtime.length_words(t1 - t0)}): nobody wrote her; she lived it unrecorded")
        if note:
            text += ". " + str(note).strip().rstrip(".")
        self.store.add_event(t1, self.clock.date_str(t1), "gap", text, 1)
        if float(self.store.get("director_last_model_ts", 0) or 0) < t1:
            self.store.set("director_last_model_ts", t1)
        if getattr(self, "director", None) is not None:
            self.director.last_model_ts = max(self.director.last_model_ts, t1)
            self.director.catch_up = False
        rows = list(self.store.get("missed_calls", []) or [])
        if rows:
            old = list(self.store.get("missed_calls_done", []) or [])
            self.store.set("missed_calls_done", (old + [dict(x, skipped=time.time()) for x in rows])[-200:])
            self.store.set("missed_calls", [])
        self.store.set("gaps", (list(self.store.get("gaps", []) or [])
                                + [{"ts": time.time(), "from": t0, "to": t1, "why": why}])[-50:])
        line = (f"[gap] {her0.strftime('%m-%d %H:%M')}-{her1.strftime(fmt)} her time "
                f"({downtime.length_words(t1 - t0)}) written as a temporal gap"
                + (f" ({why})" if why else "") + f"; {len(rows)} missed call(s) marked skipped")
        logger.log(line)
        return line

    def _replay_prepare(self):
        """The store just opened: retire what the bot wrote inside the window,
        put the gauges back, point the director at FROM."""
        r = self.replay
        t0, t1 = r["from"], r["to"]
        hers = self.store.count_window("messages", t0, t1, "AND role='assistant'")
        if hers:
            raise SystemExit(f"[replay] {hers} message(s) of hers sit inside the window; a replay would contradict "
                             f"what he was sent. Nothing touched (backup taken: {r['backup']}).")
        keep = ("trains", "weather", "hazard", "hazards", "seismic", "eew", "warning")
        counts = self.store.retire_window(t0, t1, keep)
        ts_g, gauges = self.store.gauges_at(t0)
        if gauges:
            self.store.set("gauges", gauges)
            self.store.set("gauges_ts", t0)
        self.store.set("director_last_tick_ts", t0)
        self.store.set("director_last_model_ts", t0)
        a = self.store.get("anticipation") or {}
        if t0 < float(a.get("ts") or 0) <= t1:
            self.store.set("anticipation", {})
        dates = {self.clock.date_str(t0), self.clock.date_str(t1)}
        done = self.store.get("anticipation_done", {}) or {}
        self.store.set("anticipation_done", {k: v for k, v in done.items() if k.split(":")[0] not in dates})
        rows = list(self.store.get("missed_calls", []) or [])
        if rows:
            old = list(self.store.get("missed_calls_done", []) or [])
            self.store.set("missed_calls_done", (old + [dict(x, replayed=time.time()) for x in rows])[-200:])
            self.store.set("missed_calls", [])
        fmt = lambda ts: time.strftime("%H:%M", time.localtime(ts))
        logger.log(f"[replay] window {fmt(t0)}-{fmt(t1)} his time = {self.clock.to_char(t0).strftime('%m-%d %H:%M')}-"
                   f"{self.clock.to_char(t1).strftime('%H:%M')} her time ({(t1 - t0) / 60:.0f} min) at x{r['speed']}; "
                   f"backup {r['backup']}; retired {counts}; gauges restored from the snapshot at "
                   f"{fmt(ts_g) if ts_g else 'none'}; {len(rows)} missed call(s) marked replayed; "
                   f"sends, the reply, the impulse, X actions, phone looks and sensors are off")

    def _replay_finish(self):
        r = self.replay
        t0, t1 = r["from"], r["to"]
        self.state.save()
        n_sc = self.store.count_window("scenes", t0, t1)
        n_ev = self.store.count_window("events", t0, t1)
        n_mem = self.store.count_window("self_memories", t0, t1)
        rec = {"ts": time.time(), "from": t0, "to": t1, "scenes": n_sc, "events": n_ev, "memories": n_mem, "backup": r["backup"]}
        self.store.set("replays", (list(self.store.get("replays", []) or []) + [rec])[-50:])
        logger.log(f"[replay] done: {n_sc} scene(s), {n_ev} event(s), {n_mem} memor(ies) written for "
                   f"{self.clock.to_char(t0).strftime('%H:%M')}-{self.clock.to_char(t1).strftime('%H:%M')} her time | "
                   f"{self.state.gauge_line()}")

    def catch_up(self, force_tick=False, covered=False):
        """The model calls that never got an answer (kv `missed_calls`, written
        by LLM.call when every provider failed) are read once a provider is
        back: the director's next scene covers the whole hole in one (the
        schedule blocks that passed, the events that happened in them), the
        next phone look is forced so his telemetry for the stretch is
        digested and the X queue runs, and the rows move to
        `missed_calls_done`. `/catchup` runs it by hand and forces the tick."""
        rows = list(self.store.get("missed_calls", []) or [])
        if not rows:
            return "nothing missed"
        from collections import Counter
        roles = Counter(r.get("role", "?") for r in rows)
        t0, t1 = min(r["ts"] for r in rows), max(r["ts"] for r in rows)
        span = f"{self.clock.to_char(t0).strftime('%H:%M')}-{self.clock.to_char(t1).strftime('%H:%M')} her time"
        if not covered:
            self.director.catch_up = True
        if "phone" in roles or "director" in roles:
            if self.phone:
                self.phone.force_next = True
        done = list(self.store.get("missed_calls_done", []) or []) + [dict(r, caught=time.time()) for r in rows]
        self.store.set("missed_calls_done", done[-200:])
        self.store.set("missed_calls", [])
        if force_tick:
            self.director.last_tick_ts = 0
        line = (f"[catchup] {len(rows)} call(s) went unanswered {span} ({', '.join(f'{k} x{v}' for k, v in roles.most_common())}): "
                + ("this scene covered the hole" if covered else "the next scene covers the hole")
                + "; the next phone look is forced" + ("; tick forced" if force_tick else ""))
        logger.log(line)
        return line

    # when the collector last failed to answer a request, so a machine with
    # no collector running says so once an hour instead of once a reply
    _flush_ask_quiet_until = 0.0

    def request_flush(self, wait_seconds=None):
        """Ask the machine's collector to write what it is holding, now.

        The collector buffers what it sees and writes the feed on a character
        count or on its heartbeat, so anything he did inside the current
        window was invisible to a reply built during it: he opened twenty-four
        pictures four minutes before a message and the tags were still in the
        buffer (2026-09-04). Touching the request file makes it write on its
        next pass, a few seconds.

        Both characters ask, because the collector and the feed belong to the
        machine and to neither of them. What each does with a new entry is her
        own: one digests it at once, the other when she next opens the app,
        and this never forces a look.

        Returns True when something new reached the feed. Nothing here fails a
        reply: with no collector running the file simply stays and the wait
        runs out.
        """
        if not self.sensors_on or self.replay or not self.phone or existence.is_resident(self.config):
            return False
        sv = self.config.sensors
        path = sv.telemetry_flush_request_path
        if not path:
            return False
        wait = float(sv.telemetry_flush_wait_seconds if wait_seconds is None else wait_seconds)
        # the feed's own newest id, not the id she last consumed: what is
        # being waited for is the collector answering, and entries she has
        # not read yet would otherwise count as an answer
        head_before = self.telemetry_module.get_max_file_id(sv)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except OSError as e:
            logger.log(f"[phone] could not ask the machine for what it has: {type(e).__name__}: {e}")
            return False
        served = False
        deadline = time.time() + max(0.0, wait)
        while time.time() < deadline:
            time.sleep(0.5)
            if self.telemetry_module.get_max_file_id(sv) > head_before:
                return True
            if not os.path.exists(path):
                # it answered and had nothing to write, which is an answer
                served = True
                break
        if not served and time.time() >= self._flush_ask_quiet_until:
            self._flush_ask_quiet_until = time.time() + 3600
            logger.log(f"[phone] asked the machine for what it has; nothing came in {wait:g} s")
        return False

    def latest_digest(self):
        """What her last look at his machine turned up, or "" for a
        character with no window on it -- `self.phone` is None then, not an
        app that answers nothing (`sim/existence.py`)."""
        return (self.phone.latest_digest() if self.phone else "") or ""

    def look_at_phone(self, force=False):
        if self.replay or not self.phone or existence.is_resident(self.config):
            # a replay leaves his telemetry to the live loop's next look, a
            # character with no window on his machine has no app to open, and a
            # resident has no phone either: his machine is already in front of
            # her and the app's account write is what sat between his message
            # and her reply (2026-09-17 14:57). She just replies.
            return ""
        access = self.phone_access()
        if access == "none":
            return ""
        # how long he has been quiet, and whether he read her and said
        # nothing -- the two facts that make a person check their phone
        # status() is None when she has never said anything, which is every
        # tick of a character's first day and was never reachable on a save
        # that already had a history
        rec = (self.receipts.status() if self.receipts else None) or {}
        ignored = bool(rec.get('state') in ('read', 'around'))
        before = self.phone.last_look_ts
        d = self.phone.look(self.llm, force=force, state=self.state, scene=self.director.current,
                            access=access, silent_hours=self.silent_hours(), ignored=ignored)
        if self.phone.last_look_ts != before:
            # She has actually looked, whatever it turned out to hold. A
            # program whose character learns what he is doing only when she
            # goes and fetches it hangs on this everything that has to arrive
            # at that moment and not before -- an episode he played while she
            # was elsewhere, which the watching stage has already read up on.
            self._program_call("after_phone_look", d)
        if d:
            self.assess_learned(d, source="digest", gate="digest")
            try:
                self.wonder.seed(sight.w(self.config, "wonder_seed"))
            except Exception:
                pass
        return d

    # ---------------- inbound ----------------

    def poll_inbound(self):
        new = []
        started_lookup = False
        for text, tg_id in self.tg.get_new_messages():
            new.append((text, tg_id))
        for s in self.sim_says:
            if not s["done"] and self.clock.hm() >= s["hm"]:
                s["done"] = True
                new.append((s["text"], None))
                logger.log(f"[sim] injected his message at {s['hm']}: {s['text']}")
        # lines he tapped to hear her say. Rendered on the voice worker rather
        # than here, so a two-second synthesis never stalls the loop, and the
        # audio is posted back attached to the bubble it belongs to. Nothing is
        # spoken unless he asks: she has no voice notes, by her own config.
        if self.tts and getattr(self.config.tts, "on_demand", False):
            try:
                for row in self.tg.speak_requests():
                    mid, line = int(row.get("id", 0) or 0), str(row.get("text", "") or "")
                    if not mid or not line.strip():
                        continue
                    logger.log(f"[TTS] he asked to hear: {line[:60]}")
                    self.tts.speak_on_demand(
                        line, lambda path, _id=mid: self.tg.send_voice(path, attach_to=_id))
            except Exception as e:
                logger.log(f"[TTS] speak request failed: {type(e).__name__}: {e}")
        # the stage's own controls (`view/index.html`): the voice toggle, the
        # draft guard, and a background picked by hand. The channel saves
        # manual stage choices so a restart resumes them. Read on every pass
        # so a new choice reaches the next turn.
        try:
            if hasattr(self.tg, "quality_on"):
                self.quality.enabled = bool(self.tg.quality_on())
            if hasattr(self.tg, "voice_auto"):
                self._vn_voice_auto = bool(self.tg.voice_auto())
            if hasattr(self.tg, "take_scene_request"):
                req = self.tg.take_scene_request()
                if req:
                    self.scene.request = req
        except Exception as e:
            logger.log(f"[vn] controls not read: {type(e).__name__}: {e}")
        # The director console's approved proposal, or its clear. Applied here on
        # the loop thread, never on the HTTP thread: writing a scene is the one
        # writer's and opening it is a model call.
        try:
            if hasattr(self.tg, "take_director_request"):
                req = self.tg.take_director_request()
                if req:
                    self.apply_director_scene(req)
            if hasattr(self.tg, "take_director_clear"):
                if self.tg.take_director_clear():
                    self.clear_director_scene()
        except Exception as e:
            logger.log(f"[director] the console's proposal was not applied: {type(e).__name__}: {e}")
        # an outfit he picked by hand: her sprite is already changed, and this
        # lets her notice it (a turn, so the loop thread, not the HTTP thread)
        try:
            if hasattr(self.tg, "take_outfit_request"):
                req = self.tg.take_outfit_request()
                if req:
                    self.react_to_outfit(req.get("costume"))
        except Exception as e:
            logger.log(f"[director] the outfit notice was not made: {type(e).__name__}: {e}")
        # A hand-picked background changes immediately; she notices the place
        # on the loop thread, where a model turn may safely run.
        try:
            if hasattr(self.tg, "take_scene_notice_request"):
                req = self.tg.take_scene_notice_request()
                if req:
                    self.react_to_scene(req.get("bg"))
        except Exception as e:
            logger.log(f"[director] the place notice was not made: {type(e).__name__}: {e}")
        # commands from the app's ops view: run, answer into the ops log
        try:
            for text in self.tg.get_ops_commands():
                logger.log(f"[ops] {text[:80]}")
                out = self.run_command(text.strip()) if text.strip().startswith("/") else "commands start with /"
                self.tg.post_ops_result(text, out)
        except Exception as e:
            logger.log(f"[ops] command failed: {type(e).__name__}: {e}")
        for text, tg_id in new:
            if text.strip().startswith("/"):
                self.handle_command(text.strip())
                continue
            ts = self.clock.now_ts()
            # a channel whose ids repeat after a restart (the VN stage) does not
            # get the Telegram redelivery dedupe; `Channel.MSG_ID_UNIQUE` is the
            # channel's answer, not the store's rule
            self.store.add_message(ts, self.clock.date_str(ts), "user", text, tg_id=tg_id,
                                   dedupe=bool(getattr(self.tg, "MSG_ID_UNIQUE", False)))
            logger.log(f"[him] {text[:200]}")
            # what his message is, as one fan-out (`docs/system-one.md` item 2).
            # The gates read it and every answer is kept for calibration; a
            # classifier that cannot answer changes nothing.
            try:
                self.inbound.read(text)
            except Exception as e:
                logger.log(f"[inbound] not read: {type(e).__name__}: {e}")
            self.reply_plan = None
            # his message is the evidence, and the tempo reads it off the
            # record. But if he actually SAID something about when he is
            # around, that is worth more than an inference and she should have
            # it before the reply is planned.
            try:
                self.rhythm.hear(text)
            except Exception as e:
                logger.log(f"[rhythm] not heard: {type(e).__name__}: {e}")
            self._program_call("on_his_message", text)
            try:
                self.attachment.his_message(text)
            except Exception as e:
                logger.log(f"[attach] not counted: {type(e).__name__}: {e}")
            # what the message is worth in the primitives. `effort` is how much
            # of himself it cost him, read from the message and not from how
            # kind it was: for a character who has none of him, a long
            # throwaway is worth less than a short thing he gave away. And
            # predictability moves only if he answered what she actually
            # asked, because that is the one that was callable in advance.
            if self.primitives:
                try:
                    # the same measure her side uses: he writes to her in
                    # Japanese, and a word count on text with no spaces read
                    # his messages as three or four words each
                    from sim.primitives import effort_units
                    effort = max(0.0, min(1.0, effort_units(text) / 40.0))
                    answered = bool(self.store.get("wonder_seed", {}) or {})
                    key = self.state._him_key() or "him"
                    self.primitives.note_from_him(key, effort, answered)
                    # An unrehearsed contact from somebody who can hurt her is
                    # the thing her second driver is about, and until now
                    # nothing made her feel it: she met a stranger at three in
                    # the morning composed, three generations running. The
                    # gauges move; what it looks like is the register's job.
                    pc = self.config.primitives
                    fright = self.primitives.unrehearsed(key)
                    if fright >= pc.fright_from:
                        over = fright - pc.fright_from
                        self.state._nudge("anxiety", over * pc.fright_anxiety)
                        self.state._nudge("stress", over * pc.fright_stress)
                        logger.log("[primitives] unrehearsed contact %.0f: anxiety +%.1f, stress +%.1f"
                                   % (fright, over * pc.fright_anxiety, over * pc.fright_stress))
                except Exception as e:
                    logger.log(f"[primitives] his message not counted: {type(e).__name__}: {e}")
            try:
                self.foresight.outcome(text)
            except Exception as e:
                logger.log(f"[foresee] outcome not written: {type(e).__name__}: {e}")
            # anything in it he could be held to, and anything it settles
            try:
                self.expectations.hear(text)
                self.expectations.tick()
            except Exception as e:
                logger.log(f"[expect] not heard: {type(e).__name__}: {e}")
            # and what she was half braced for, against the read of him
            self._guarded("foresee", self.foresight.score_risks)
            # a question she asked him: what his answer does to her picture
            try:
                self.wonder.on_his_message(text)
            except Exception as e:
                logger.log(f"[wonder] answer not judged: {type(e).__name__}: {e}")
            # and if she was holding out, this is the message that might undo it
            try:
                self.withholding.broken_by(text)
            except Exception as e:
                logger.log(f"[withhold] break not checked: {type(e).__name__}: {e}")
            # He said something. She feels better and nothing has been settled;
            # the chain is suspended and the same seed can go again tomorrow.
            # and it is his answer that decides whether the thing between
            # them is mended, tried at and missed, or made worse
            if self.config.rupture.enabled:
                try:
                    self.rupture_settled(self.ruptures.settle("his_message"))
                except Exception as e:
                    logger.log(f"[rupture] not settled: {type(e).__name__}: {e}")
            if self.config.spiral.enabled:
                try:
                    self.spirals.suspend_for_him()
                except Exception as e:
                    logger.log(f"[spiral] not suspended: {type(e).__name__}")
            # if he named a thing, she quietly looks it up while the message waits
            if self.lookup and not started_lookup and self.lookup.start(text, ts):
                started_lookup = True
                logger.log("[lookup] she is looking something up")
            if self.recall and self.recall.start(text, extra=self._recall_extra()):
                logger.log("[recall] something in it points at the past")

    def _recall_extra(self):
        """The rest of the moment as a cue for recall: her own last line and
        where she is. His message stays the trigger; this only widens what
        the record is searched for. One owner (`sim/recall.py:moment_cue`),
        shared with the persona's recall of a faded fact."""
        return moment_cue(self.store, (self.director.current if self.director else None))

    def _cmd_episodes(self, arg, cmd, text):
        """`/episodes` -- her past as cards: how many, and the last few, each
        with what it fed. `/episodes <date>` writes (or rewrites) that day's
        cards now; `/episodes backfill` writes the missing days the thread
        shows; `/episodes fed [date]` is what each card of that day left in
        her record; `/episodes relink [days]` attaches the conversation the
        memories and facts of the days already carded came out of."""
        a = (arg or "").strip()
        if a == "backfill":
            n = self._backfill_cards()
            return f"{n} day(s) written\n" + self.episodes.report()
        if a.split()[:1] == ["fed"]:
            return self.episodes.fed_report((a.split() + [""])[1] or None)
        if a.split()[:1] == ["relink"]:
            try:
                days = int((a.split() + ["14"])[1])
            except ValueError:
                days = 14
            rows, seen = self.episodes.relink(days)
            return (f"{rows} row(s) over {seen} carded day(s) now name the conversation they came from\n"
                    + self.episodes.fed_report())
        if a:
            n = self.episodes.write(a)
            return f"{a}: {n} card(s)\n" + self.episodes.fed_report(a)
        return self.episodes.report()

    def _cmd_inflight(self, arg, cmd, text):
        """`/inflight` -- the paid or stateful background jobs this process
        believes are running (kv `in_flight`). A row still here after a
        restart is a job the dead process was in the middle of; the boot read
        settles those by kind (`sim/inflight.py`)."""
        return inflight.report(self.store)

    def _backfill_cards(self):
        """Cards for the days the thread shows past its verbatim window and
        does not have cards for. Once after boot, in a thread, and after a
        compile. Bounded: at most eight days a call."""
        try:
            now = self.clock.now_ts()
            cutoff, _verbatim_from = self.thread._window(now)
            # every day of the thread, not only the days already past the
            # verbatim window: while the whole thread fits the history budget
            # the verbatim window reaches the cutoff and that range is empty
            return self.episodes.backfill(cutoff, now)
        except Exception as e:
            logger.log(f"[episodes] backfill failed: {type(e).__name__}: {e}")
            return 0

    def _backfill_vectors(self):
        """Vectors for the facts and the memories that have none. Once after
        boot, in the background: the persona asks for meaning on the loop
        thread and is answered from what is stored, never by loading the
        model or encoding a pool, so the first encode of a save's whole
        record has to happen off that thread. Everything written after this
        is embedded by whoever wrote it (`Memory.add_fact`,
        `SelfMemory.add`)."""
        if not self.config.embed.enabled:
            return 0
        n = 0
        try:
            n += len(self.embed.vectors("fact", [(r["rid"], r["fact"]) for r in self.memory.rows()]))
            n += len(self.embed.vectors("selfmem", [(r["rid"], self.self_memory.embed_text(r))
                                                    for r in self.self_memory.rows()]))
            # the machinery's own record of her days, which the deliberate
            # search reads now (`docs/memory.md` §6). Written here rather than
            # on the loop thread: a save with a year of them is thousands of
            # rows and the first encode of the pool would be paid for by his
            # next reply.
            _sal, _scan = self.recall.events_wanted(self.config)
            if _sal:
                n += len(self.embed.vectors(
                    "event", [(r["id"], str(r.get("text") or ""))
                              for r in self.store.salient_events(min_salience=_sal, limit=_scan)]))
            logger.log(f"[embed] {n} row(s) of what she knows and what she remembers can be reached by meaning")
        except Exception as e:
            logger.log(f"[embed] backfill failed: {type(e).__name__}: {e}")
        return n

    def _backfill_context(self):
        """What her past needs written before the retrieval can reach it,
        after boot and off the loop thread: first the jobs a killed process
        left in flight, then the cards for the days the thread already shows,
        then the vectors of what she knows and what she remembers.

        The in-flight read comes first and belongs here rather than in the
        constructor: it may rerun a compile, which is minutes of model calls,
        and it must run before this process has started a job of its own so
        that every row it finds is a dead process's (`sim/inflight.py`)."""
        try:
            inflight.resolve(self)
        except Exception as e:
            logger.log(f"[boot] the jobs left in flight were not settled: {type(e).__name__}: {e}")
        self._backfill_cards()
        self._backfill_vectors()

    def handle_command(self, text):
        out = self.run_command(text)
        self.tg.send_message(out)

    def run_command(self, text):
        """A slash command's output as text. Telegram sends it into the chat;
        the TALKAPP ops view shows it in its own log, never in her chat."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        try:
            return self._run_command(cmd, arg, text)
        except AttributeError as e:
            # a command that reaches for a world, a cast or an account she has
            # not got: every such slot is None on her App, and this is the
            # honest answer rather than a traceback in the ops log
            if "'NoneType'" in str(e):
                return f"{cmd}: not part of this character ({self.config.character.name} has no such thing)"
            raise

    def _run_command(self, cmd, arg, text):
        """One table (`COMMANDS`): the method, the program slots its body
        touches, whether it needs an argument. A command whose slot this
        character has not got is answered as such rather than run into a
        None, and `/help` does not list it for her."""
        entry = self.COMMANDS.get(cmd)
        if entry is None:
            out = "unknown command"
        else:
            method, needs, needs_arg = entry
            missing = [s for s in needs if getattr(self, s, None) is None]
            if missing:
                out = f"{cmd}: not part of this character ({self.config.character.name} has no {', '.join(missing)})"
            elif needs_arg and not arg:
                out = self.help_text(cmd)
            else:
                out = getattr(self, method)(arg, cmd, text)
        try:
            self.ops.note(text, out)
        except Exception:
            pass
        return out

    def command_available(self, cmd):
        """False when the command needs a program slot this character has not got."""
        entry = self.COMMANDS.get(cmd)
        return entry is None or all(getattr(self, s, None) is not None for s in entry[1])

    # command -> (method, the program slots the body touches, needs an argument).
    # The slots are read off the method bodies; `tools/smoke.py` fails if a
    # method touches a slot its row does not name.
    COMMANDS = {
        "/day": ("_cmd_day", (), False),
        "/agenda": ("_cmd_agenda", (), False),
        "/peers": ("_cmd_peers", (), False),
        "/episodes": ("_cmd_episodes", (), False),
        "/inflight": ("_cmd_inflight", (), False),
        "/scene": ("_cmd_scene", (), False),
        "/state": ("_cmd_state", (), False),
        "/schedule": ("_cmd_schedule", (), False),
        "/tick": ("_cmd_tick", (), False),
        "/idle": ("_cmd_idle", (), False),
        "/reply": ("_cmd_reply", (), False),
        "/selfstart": ("_cmd_selfstart", (), False),
        "/look": ("_cmd_look", (), False),
        "/digest": ("_cmd_digest", (), False),
        "/snoop": ("_cmd_snoop", ('snoop',), False),
        "/compile": ("_cmd_compile", (), False),
        "/impulse": ("_cmd_impulse", (), False),
        "/pick": ("_cmd_pick", (), False),
        "/time": ("_cmd_time", (), False),
        "/read": ("_cmd_read", (), True),
        "/notes": ("_cmd_notes", (), False),
        "/x": ("_cmd_x", ('posting', 'replies', 'social', 'taste'), False),
        "/memory": ("_cmd_memory", (), False),
        "/beliefs": ("_cmd_beliefs", (), False),
        "/self": ("_cmd_beliefs", (), False),
        "/graph": ("_cmd_graph", ('social_graph',), False),
        "/gauges": ("_cmd_gauges", (), False),
        "/hazards": ("_cmd_hazards", ('hazards',), False),
        "/trains": ("_cmd_trains", ('trains',), False),
        "/rhythm": ("_cmd_rhythm", (), False),
        "/withhold": ("_cmd_withhold", (), False),
        "/approach": ("_cmd_approach", (), False),
        "/sentiment": ("_cmd_sentiment", (), False),
        "/rupture": ("_cmd_rupture", (), False),
        "/compare": ("_cmd_compare", ('compare',), False),
        "/spiral": ("_cmd_spiral", (), False),
        "/ick": ("_cmd_ick", (), False),
        "/goals": ("_cmd_goals", (), False),
        "/commit": ("_cmd_commit", (), False),
        "/attach": ("_cmd_attach", (), False),
        "/where": ("_cmd_where", (), False),
        "/family": ("_cmd_family", ('family',), False),
        "/care": ("_cmd_care", (), False),
        "/reaction": ("_cmd_reaction", (), False),
        "/kb": ("_cmd_kb", (), False),
        "/watch": ("_cmd_watch", (), False),
        "/scenery": ("_cmd_scenery", ('scenery', 'social'), False),
        "/discharge": ("_cmd_discharge", (), False),
        "/wonder": ("_cmd_wonder", (), False),
        "/expect": ("_cmd_expect", (), False),
        "/foresee": ("_cmd_foresee", (), False),
        "/world": ("_cmd_world", (), False),
        "/japan": ("_cmd_japan", ('zeitgeist',), False),
        "/npc": ("_cmd_npc", ('people',), False),
        "/lives": ("_cmd_lives", ('cast',), False),
        "/remember": ("_cmd_remember", (), False),
        "/context": ("_cmd_context", (), False),
        "/reflect": ("_cmd_reflect", (), False),
        "/chat": ("_cmd_chat", ('exchange',), False),
        "/recalls": ("_cmd_recalls", (), False),
        "/morning": ("_cmd_morning", (), False),
        "/claims": ("_cmd_claims", (), False),
        "/intents": ("_cmd_intents", (), False),
        "/lookups": ("_cmd_lookups", (), False),
        "/known": ("_cmd_known", (), False),
        "/watching": ("_cmd_watching", (), False),
        "/money": ("_cmd_money", (), False),
        "/gossip": ("_cmd_gossip", ('gossip',), False),
        "/orbit": ("_cmd_orbit", ('orbit',), False),
        "/bonds": ("_cmd_bonds", ('cast_psych',), False),
        "/missed": ("_cmd_missed", (), False),
        "/catchup": ("_cmd_catchup", (), False),
        "/gap": ("_cmd_gap", (), False),
        "/provider": ("_cmd_provider", (), False),
        "/model": ("_cmd_model", (), False),
        "/voicemodel": ("_cmd_voicemodel", (), False),
        "/lang": ("_cmd_lang", (), False),
        "/swipe": ("_cmd_swipe", (), False),
        "/sit": ("_cmd_sit", (), True),
        "/speed": ("_cmd_speed", (), False),
        "/attention": ("_cmd_attention", (), False),
        "/coherence": ("_cmd_coherence", (), False),
        "/nudge": ("_cmd_nudge", (), False),
        "/nudgeab": ("_cmd_nudgeab", (), False),
        "/thread": ("_cmd_thread", (), False),
        "/stats": ("_cmd_stats", (), False),
        "/ledger": ("_cmd_ledger", (), False),
        "/diet": ("_cmd_diet", ('diet',), False),
        "/health": ("_cmd_health", (), False),
        "/beats": ("_cmd_beats", ('cast',), False),
        "/diary": ("_cmd_diary", (), False),
        "/week": ("_cmd_week", (), False),
        "/threads": ("_cmd_threads", (), False),
        "/arcs": ("_cmd_arcs", (), False),
        "/cast": ("_cmd_cast", (), False),
        "/places": ("_cmd_places", (), False),
        "/showrun": ("_cmd_showrun", ('showrunner',), False),
        "/castarcs": ("_cmd_castarcs", ('cast_arcs',), False),
        "/receipt": ("_cmd_receipt", (), False),
        "/voice": ("_cmd_voice", (), False),
        "/derive": ("_cmd_derive", (), False),
        "/vision": ("_cmd_vision", (), False),
        "/say": ("_cmd_say", (), True),
        "/send": ("_cmd_send", (), True),
        "/anime": ("_cmd_anime", (), False),
        "/help": ("_cmd_help", (), False),
        "/set": ("_cmd_set", (), False),
        "/sweep": ("_cmd_sweep", (), False),
        "/absurd": ("_cmd_absurd", (), False),
        "/headless": ("_cmd_headless", (), False),
        "/voicecheck": ("_cmd_voicecheck", (), False),
        "/ops": ("_cmd_ops", (), False),
    }

    def _cmd_peers(self, arg, cmd, text):
        """Who she can write to, what she has sent today, and the conversation
        in flight. `tick` runs one pass of it now; `flush` closes what is open
        the way the compile does."""
        if self.peers is None:
            return "peer talk is not built for this character"
        a = str(arg or "").strip().lower()
        if a == "tick":
            self.peers.tick(self.director.current)
            return self.peers.report()
        if a == "flush":
            self.peers.flush()
            return "closed what was open\n" + self.peers.report()
        return self.peers.report()

    def _cmd_day(self, arg, cmd, text):
        out = ""
        d = arg or self.clock.date_str()
        day = self.store.get_day(d)
        if day:
            out = f"{d}\n\n{day['narrative']}"
        else:
            scenes = self.store.scenes_for_date(d)
            if scenes:
                out = f"{d} (not compiled yet)\n" + "\n".join(f"{s['hm']} {s['location']}: {s['activity']}" for s in scenes)
            else:
                out = f"nothing on record for {d}"
        return out

    def _cmd_agenda(self, arg, cmd, text):
        """What is coming, joined: the calendar, her promises, what he said
        he would do, who the day's plan has taken out of the day, and what
        today has settled. A number is how many days ahead."""
        a = str(arg or "").strip()
        return self.agenda.report(max(0, min(60, int(a))) if a.isdigit() else None)

    def _cmd_scene(self, arg, cmd, text):
        out = ""
        s = self.director.current
        out = f"{s['hm']} {s['location']} / {s['activity']} (with {s.get('with', s.get('with_who'))}, phone {s['phone_access']})\n{s.get('sensory', '')}" if s else "no scene yet"
        return out

    def _cmd_state(self, arg, cmd, text):
        out = ""
        out = f"{self.state.gauge_line()}\n\n{self.state.relationships_brief()}\n\nthreads: {self.store.get('open_threads', [])}"
        return out

    def _cmd_schedule(self, arg, cmd, text):
        out = ""
        if arg == "regen":
            # redraw the wake and rebuild today's plan. The wake is cached
            # in kv `wake_days` on purpose (one morning, one number), so a
            # fix to how it is drawn only reaches today if the cached one
            # goes first.
            d = self.clock.date_str()
            days = self.store.get("wake_days", {}) or {}
            had = days.pop(d, None)
            self.store.set("wake_days", days)
            self.schedule = self.program.generate(self)
            self._program_call("day_planned", self.schedule, d)
            now = (self.store.get("wake_days", {}) or {}).get(d, {})
            out = (f"wake was {(had or {}).get('hm', '?')} -> {now.get('hm', '?')}"
                   f" ({', '.join(now.get('why', [])[:3])})\n" + sched.describe(self.schedule))
        else:
            out = sched.describe(self.schedule) if self.schedule else "no schedule"
        return out

    def _cmd_tick(self, arg, cmd, text):
        out = ""
        self.tick(force=True)
        out = "ticked"
        return out

    def _cmd_look(self, arg, cmd, text):
        out = ""
        out = self.look_at_phone(force=True) or sight.w(self.config, "ops_nothing_new")
        return out

    def _cmd_digest(self, arg, cmd, text):
        out = ""
        # read-only on purpose. /look is the other one and it is not the
        # same question: that makes her look, which eats the pending feed,
        # writes a new digest and moves her gauges. This shows what she is
        # holding now, and how far behind the log she has fallen.
        want = int(arg) if arg.strip().isdigit() else 1
        rows = self.store.recent_digests(max(1, min(10, want)))
        if not rows:
            out = sight.w(self.config, "ops_never_looked")
        else:
            parts = []
            for d in reversed(rows):
                his = self.clock.to_user(d["ts"]).strftime("%Y-%m-%d %H:%M:%S")
                parts.append(f"[{his} his time / {self.clock.hm(d['ts'])} her {d['date']}]\n{d['text']}")
            behind, newest = self.feed_backlog()
            if behind:
                parts.append(f"({behind} log entr{'y' if behind == 1 else 'ies'} since, unread"
                             + (f"; newest {newest}" if newest else "") + ")")
            else:
                parts.append("(nothing new in the log since)")
            out = "\n\n".join(parts)
        return out

    def _cmd_snoop(self, arg, cmd, text):
        # through the program's hook, which is where everything but the
        # record lives: what the look costs her, what it does to her
        # picture of him, her own reaction to it and the scene tick. Calling
        # the object direct wrote a record and moved nothing.
        missing = object()
        r = self._program_call("maybe_snoop", forced=True, default=missing)
        if r is missing:
            return "she has no way of going through his things"
        return r["text"] if r else "nothing new in his notes or his downloads"

    def _cmd_compile(self, arg, cmd, text):
        out = ""
        d = arg.strip() if arg and arg.strip() else self.clock.date_str()
        self.compile(d)
        out = f"compiled {d}"
        return out

    def _cmd_idle(self, arg, cmd, text):
        out = ""
        # The loop's own ordinary pass, run now rather than when the director
        # is next due: a change can be exercised in seconds instead of waiting
        # out her clock. It is the same method the loop calls, so nothing here
        # is a shorter path than the real one.
        if not self.schedule:
            # the loop draws the day before its first tick, and everything
            # below reads the block she is in
            out = "she has no plan for today yet; nothing forced"
        else:
            logger.log("[ops] forced: one ordinary loop tick")
            scene = self.ordinary_tick()
            if not scene:
                out = "the tick wrote no scene; the log says why"
            else:
                out = (f"{scene.get('hm', '')} {scene.get('location', '')} / {scene.get('activity', '')}"
                       f" (with {scene.get('with', scene.get('with_who', ''))},"
                       f" phone {scene.get('phone_access', '')})\n"
                       f"{scene.get('sensory', '')}\n\n{self.state.gauge_line()}")
        return out

    def _cmd_reply(self, arg, cmd, text):
        out = ""
        # His message answered NOW instead of when her plan says. Only the
        # waiting is skipped: the plan is set due and `maybe_reply` runs the
        # real path from there -- her gauges read off his words, the
        # situation, the editor, her delivery queue. `again` puts his newest
        # message back in the unread queue, so one she has already answered
        # can be answered a second time.
        again = arg.strip().lower().startswith("again")
        access = self.phone_access()
        if self.replay:
            out = "she is re-living a hole; nothing is answered from inside one"
        elif not self.schedule:
            out = "she has no plan for today yet; nothing forced"
        elif self.delivery.busy():
            out = "she is in the middle of sending something; nothing forced"
        elif access == "none":
            out = "she has no phone in this block (asleep, or it is away); nothing forced"
        else:
            if again:
                m = self.store.last_message("user")
                if m:
                    self.store.unmark_read(m["id"])
            unread = self.store.unread_user_messages()
            if not unread:
                out = ("he has never written to her; there is nothing to answer" if again
                       else "nothing of his is unread (/reply again answers his newest message anyway)")
            else:
                before = (self.store.last_message("assistant") or {}).get("id", 0)
                logger.log(f"[ops] forced: her reply to {len(unread)} of his, due now")
                self.reply_plan = {"mode": access, "presence": self.rhythm.presence(),
                                   "due_ts": self.clock.now_ts() - 1}
                self.maybe_reply()
                after = (self.store.last_message("assistant") or {}).get("id", 0)
                if self.delivery.busy() or after != before:
                    out = f"answering {len(unread)} of his now: {unread[-1]['text'][:60]}"
                else:
                    out = ("the reply path ran and nothing went out: she is holding it back, "
                           "or nothing came back from the model. The log says which")
        return out

    def _cmd_selfstart(self, arg, cmd, text):
        out = ""
        # She writes first, now, through the door a discharge uses: the
        # impulse gate and her resolve do not get a vote, and everything after
        # that -- what she means by it, the situation, the editor, the
        # delivery -- is the path a real opener of hers takes. The argument is
        # the reason she is handed, and stands in for what the gate would have
        # found her.
        scene = self.director.current
        if self.replay:
            out = "she is re-living a hole; she does not write out of one"
        elif not self.schedule:
            out = "she has no plan for today yet; nothing forced"
        elif self.delivery.busy():
            out = "she is in the middle of sending something; nothing forced"
        elif self.store.unread_user_messages():
            out = "something of his is unread: she answers that before she starts anything (/reply)"
        elif self.phone_access() == "none":
            out = "she has no phone in this block (asleep, or it is away); nothing forced"
        elif not scene:
            out = "there is no scene yet; /idle or /tick first"
        else:
            hint = arg.strip() or "she has decided to write to him now, off her own bat"
            logger.log(f"[ops] forced: she writes first ({hint[:70]})")
            before = (self.store.last_message("assistant") or {}).get("id", 0)
            self.maybe_impulse(scene, self.latest_digest(), force_hint=hint)
            after = (self.store.last_message("assistant") or {}).get("id", 0)
            out = (f"she is writing first: {hint[:80]}"
                   if (self.delivery.busy() or after != before)
                   else "she went through it and sent nothing; the log says why")
        return out

    def _cmd_impulse(self, arg, cmd, text):
        out = ""
        ok, why = self.impulse.check(self.state, self.director.current, self.silent_hours()) if not self.replay else (False, "replay")
        out = f"{ok}: {why}\n\n{self.impulse.initiative.report()}"
        return out

    def _cmd_pick(self, arg, cmd, text):
        return self.pick.report(arg)

    def _cmd_time(self, arg, cmd, text):
        out = ""
        out = self.clock.both()
        return out

    def _cmd_read(self, arg, cmd, text):
        out = ""
        r = self.notes.read(arg, ("he asked her to read it", "彼に読んでと言われて"), self.director.current)
        out = f"{r['basename']}: {r['takeaway']}\n(salience {r['salience']}) gist: {r['gist']}" if r else f"no vault file matching '{arg}'"
        return out

    def _cmd_notes(self, arg, cmd, text):
        out = ""
        out = self.notes.index_text(50) or "she has not read any of his notes yet"
        return out

    def _cmd_x(self, arg, cmd, text):
        out = ""
        if arg == "likes":
            items = self._x_his_likes_recent()
            out = "\n".join(f"@{i.get('author', '')}: {(i.get('text', '') or '(image)')[:100]}" for i in items) or "no likes of his recorded since the baseline"
        elif arg == "follows":
            items = _x_his_follows(self.config.sensor_view, time.time() - 30 * 86400)
            out = "\n".join(f"@{i.get('handle', '')} ({i.get('name', '')}) {i.get('bio', '')[:80]}" for i in items) or "no new follows of his recorded since the baseline"
        elif arg == "followers":
            # who follows the account, what that protects, and what she
            # was stopped from doing because of it
            fol = _x_load_followers(self.config.sensor_view) or {}
            accs = fol.get("accounts") or {}
            following = {h.lower() for h in ((_x_load_following(self.config.sensor_view) or {}).get("accounts") or {})}
            mutual = _x_follows_back(self.config.sensor_view) & following
            private = _x_private_accounts(self.config.sensor_view)
            new = sorted((v for v in accs.values() if not v.get("baseline")), key=lambda v: -float(v.get("since", 0)))
            refused = [x for x in _x_her_actions(self.config.sensor_view) if x.get("kind") == "unfollow_refused"]
            backs = [x for x in _x_her_actions(self.config.sensor_view) if x.get("follow_back")]
            out = (f"{len(accs)} follower(s) known (fetched {self.clock.hm(fol.get('fetched', 0)) if fol.get('fetched') else 'never'}); "
                   f"{len(mutual)} mutual, {len(private)} private -- none of those can be unfollowed" + chr(10)
                   + "SINCE THE BASELINE: " + (", ".join("@" + str(v.get("handle")) for v in new[:15]) or "(nobody new)") + chr(10)
                   + f"FOLLOWED BACK ({len(backs)}): " + (", ".join("@" + str(x.get("target")) for x in backs[-10:]) or "(none)") + chr(10)
                   + f"UNFOLLOWS REFUSED AT THE PROFILE ({len(refused)}): "
                   + (chr(10).join(f"@{x.get('target')} :: {x.get('why', '')}" for x in refused[-8:]) or "(none)"))
        elif arg == "taste":
            out = self.social.taste_brief() or "no reactions yet"
        elif arg.startswith("taste "):
            what = arg[6:].strip()
            out = self.social.taste_history(None if what == "all" else what)
        elif arg.startswith("following"):
            # the follow list itself: who the account follows, each with
            # the card's kind, her verdict and her likes. Filters: hers /
            # keep / drop / leave / unjudged / all (default: the summary
            # and the ones that are in any way hers)
            what = (arg.split(None, 1)[1].strip().lower() if " " in arg else "")
            fol = (_x_load_following(self.config.sensor_view) or {}).get("accounts", {}) or {}
            cards = _x_load_accounts(self.config.sensor_view) or {}
            verd = self.taste.verdicts()
            taste = self.store.get("x_taste", {}) or {}
            lows = {h.lower(): h for h in fol}

            def row(h):
                lc = next((k for k in cards if k.lower() == h.lower()), "")
                card = cards.get(lc) or {}
                v = verd.get(h) or verd.get(next((k for k in verd if k.lower() == h.lower()), ""), {})
                t = taste.get(h) or taste.get(next((k for k in taste if k.lower() == h.lower()), ""), {})
                hers = (fol.get(h) or {}).get("added_by") == "her"
                bits = [f"@{h}", f"[{card.get('kind', '?')}]", (v.get("verdict") or "unjudged")]
                if hers:
                    bits.append("HERS")
                if t.get("like") or t.get("dislike"):
                    bits.append(f"{t.get('like', 0)}+/{t.get('dislike', 0)}-")
                if v.get("why"):
                    bits.append("-- " + str(v["why"])[:60])
                return " ".join(bits)

            names = sorted(lows.values(), key=str.lower)
            if what in ("hers", "keep", "drop", "leave", "unjudged"):
                if what == "hers":
                    names = [h for h in names if (fol.get(h) or {}).get("added_by") == "her"]
                elif what == "unjudged":
                    names = [h for h in names if not (verd.get(h) or verd.get(next((k for k in verd if k.lower() == h.lower()), ""), {}))]
                else:
                    names = [h for h in names if (verd.get(h) or verd.get(next((k for k in verd if k.lower() == h.lower()), ""), {})).get("verdict") == what]
                out = f"{len(names)} account(s) ({what})" + chr(10) + chr(10).join(row(h) for h in names)
            elif what == "all":
                out = f"{len(names)} followed" + chr(10) + chr(10).join(row(h) for h in names)
            else:
                counts = {}
                for h in names:
                    v = (verd.get(h) or verd.get(next((k for k in verd if k.lower() == h.lower()), ""), {})).get("verdict") or "unjudged"
                    counts[v] = counts.get(v, 0) + 1
                hers = [h for h in names if (fol.get(h) or {}).get("added_by") == "her"]
                liked = [h for h in names if (taste.get(h) or {}).get("like", 0) > 0]
                out = (f"{len(names)} followed: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
                       + f"; hers {len(hers)}" + chr(10)
                       + "HERS:" + chr(10) + (chr(10).join(row(h) for h in hers) or "(none)") + chr(10)
                       + f"WITH LIKES ({len(liked)}):" + chr(10) + chr(10).join(row(h) for h in liked)
                       + chr(10) + "(/x following keep|leave|drop|hers|unjudged|all for the rest)")
        elif arg == "unfollowed":
            # every unfollow ever, with the judge's why: the total record
            acts = [x for x in _x_her_actions(self.config.sensor_view) if x.get("kind") == "unfollow_done"]
            verd = self.taste.verdicts()
            rows = []
            for x in acts:
                h = str(x.get("target", ""))
                v = verd.get(h) or verd.get(next((k for k in verd if k.lower() == h.lower()), ""), {})
                rows.append(f"{datetime.datetime.fromtimestamp(float(x.get('at', 0))).strftime('%m-%d %H:%M')} @{h} :: {v.get('why', '') or x.get('why', '')}")
            out = f"{len(acts)} unfollowed in all" + chr(10) + (chr(10).join(rows) or "none yet")
        elif arg == "sheet":
            out = self.taste.sheet_text() or "no taste sheet (data/taste.json)"
        elif arg == "drift":
            out = self.taste.report()
        elif arg == "judge":
            n = self.taste.judge(limit=60)
            out = f"judged {n} account(s)\n" + self.taste.report()
        elif arg == "japan":
            out = "\n".join(f"{j['date']}: {j['text']}" for j in self.store.get("x_japan", [])[-20:]) or "nothing noted yet"
        elif arg == "status":
            hl = "headless" if getattr(self.config.sensor_view, "x_headless", True) else "windowed"
            try:
                gate = self.posting.why_not(self.director.current or {})
            except Exception as e:
                gate = f"gate unreadable: {type(e).__name__}"
            try:
                answering = self.replies.status() if self.replies else "no replying built"
            except Exception as e:
                answering = f"the reply gate unreadable: {type(e).__name__}"
            out = (f"last look {self.clock.hm(self.social.last_look_ts) if self.social.last_look_ts else 'never'}; "
                   f"{hl}; busy {self.social.busy()}; last error: {self.social.error or 'none'}" + chr(10)
                   + gate + chr(10) + answering + chr(10) + (self.social.recent_line() or "(nothing recent)"))
        elif arg == "post":
            txt = self.posting.write(self.director.current or {}, reason="he asked")
            out = f"she would post: {txt}" if txt else "she opened the composer and closed it (see log)"
        elif arg == "actions":
            q = self.store.get("x_action_queue", [])
            recent = [x for x in _x_her_actions(self.config.sensor_view) if not x.get("kind", "").endswith("_done")][-15:]
            on = "ON" if self.config.sensor_view.x_actions_enabled else "OFF (dry run, logged only)"
            posting = "ON" if self.config.sensor_view.x_posting_enabled else "OFF"
            rows = [f"{'dry ' if x.get('dry_run') else ''}{x['kind']} {str(x.get('target'))[:60]} :: {x.get('why', '')[:60]}" for x in recent]
            out = f"actions {on}; posting {posting}; queued {len(q)}" + chr(10) + (chr(10).join(rows) or "no decisions yet")
        else:
            started = self.social.start_look(force=True)
            out = "she is opening X (result in the log and her situation in a minute or two)" if started else "a look is already running"
        return out

    def _cmd_memory(self, arg, cmd, text):
        out = ""
        out = self.memory.facts_report()
        return out

    def _cmd_beliefs(self, arg, cmd, text):
        out = ""
        model = self.model_of_her if cmd == "/self" else self.model_of_him
        if model is None:
            return "she has no picture of him: she has no chat with him at all"
        if arg == "revise":
            b = model.due_revision()
            if not b:
                out = "nothing of hers has taken enough to give way yet"
            else:
                r = model.revise(b)
                out = (f"{b['id']}\n  was: {b['was'][-1]['text'] if b.get('was') else ''}\n  now: {r['text']}"
                       if r else "she would not put it any other way")
        else:
            out = model.report()
        return out

    def _cmd_graph(self, arg, cmd, text):
        out = ""
        out = self.social_graph.report()
        return out

    def _cmd_gauges(self, arg, cmd, text):
        out = ""
        out = (self.state.affect_report() + chr(10) + chr(10) + self.stress.report()
               + chr(10) + chr(10) + self.appraisal.report())
        return out

    def _cmd_hazards(self, arg, cmd, text):
        out = ""
        out = self.hazards.report()
        return out

    def _cmd_trains(self, arg, cmd, text):
        out = ""
        out = self.trains.report()
        return out

    def _cmd_rhythm(self, arg, cmd, text):
        out = ""
        out = self.rhythm.report()
        return out

    def _cmd_withhold(self, arg, cmd, text):
        out = ""
        out = self.withholding.report()
        return out

    def _cmd_approach(self, arg, cmd, text):
        out = ""
        if arg == "now":
            item, why = self.approach.due(self.director.current)
            if not item:
                out = f"not now: {why}"
            else:
                r = self.approach.write(item, self.director.current)
                out = (f"{self.approach.note(item, r)['line']}" if r else "the call came back with nothing")
        else:
            out = self.approach.report()
        return out

    def _cmd_sentiment(self, arg, cmd, text):
        out = ""
        out = self.sentiments.report()
        return out

    def _cmd_rupture(self, arg, cmd, text):
        out = ""
        if arg == "settle":
            r = self.ruptures.settle("day")
            self.rupture_settled(r)
            out = f"{r['state']}: {r['what']}" if r else "nothing open, or nothing that bears on it"
        else:
            out = self.ruptures.report()
        return out

    def _cmd_compare(self, arg, cmd, text):
        out = ""
        if arg == "now":
            rec = self.compare.maybe(self.director.current or {}, force=True)
            out = (f"vs {rec['who']} on {rec['dimension']} ({rec['direction']}): {rec['thought']}" if rec else "nothing fired (nobody about, or the model found no ruler)")
        else:
            out = self.compare.report(self.director.current or {})
        return out

    def _cmd_spiral(self, arg, cmd, text):
        out = ""
        if arg == "now":
            sc = self.director.current
            ok, why, mode = self.spirals.due(sc)
            out = f"({why})" + (chr(10) + str(self.spirals.run(sc, mode or "start", why)) if mode else "")
        elif arg == "settle":
            out = f"settled {self.spirals.settle(self.clock.date_str())}"
        else:
            out = self.spirals.report()
        return out

    def _cmd_ick(self, arg, cmd, text):
        out = ""
        out = self.ick.report()
        return out

    def _cmd_goals(self, arg, cmd, text):
        out = ""
        out = self.goals.report()
        return out

    def _cmd_commit(self, arg, cmd, text):
        out = ""
        out = self.commitments.report()
        return out

    def _cmd_attach(self, arg, cmd, text):
        out = ""
        out = self.attachment.report()
        return out

    def _cmd_where(self, arg, cmd, text):
        out = ""
        out = self.situation.report()
        return out

    def _cmd_family(self, arg, cmd, text):
        out = ""
        out = self.family.report()
        return out

    def _cmd_care(self, arg, cmd, text):
        out = ""
        out = self.care.report(int(arg) if arg.strip().isdigit() else None)
        return out

    def _cmd_reaction(self, arg, cmd, text):
        out = ""
        if arg == "now":
            rec = self.reactions.tick(force_bucket=self.reactions.bucket_for(self.reactions.band()), why="forced now")
            out = f"showing {rec['bucket']} #{rec['id']}" if rec else "nothing on file for that face"
        elif arg == "off":
            out = self.reactions.clear()
        elif arg.startswith("backfill"):
            hours = int(arg.split()[1]) if len(arg.split()) > 1 and arg.split()[1].isdigit() else 24
            recs = self.reactions.backfill(hours)
            out = f"{len(recs)} sticker(s) placed: " + ", ".join(f"{time.strftime('%H:%M', time.localtime(r['ts']))} {r['bucket']}" for r in recs) if recs else "no crossing found"
        elif arg:
            rec = self.reactions.tick(force_bucket=arg.strip(), why=f"forced {arg.strip()}")
            out = f"showing {rec['bucket']} #{rec['id']}" if rec else f"nothing on file for '{arg.strip()}'"
        else:
            out = self.reactions.report()
        return out

    def _cmd_kb(self, arg, cmd, text):
        out = ""
        out = self.recap.report()
        return out

    def _cmd_watch(self, arg, cmd, text):
        out = ""
        bits = arg.split()
        if bits and bits[0] == "add":
            # /watch add Title|ja|kind|ep|total
            rest = arg[3:].strip()
            f = [x.strip() for x in rest.split("|")]
            title = f[0] if f else ""
            out = self.watchlist.add(title, ja=f[1] if len(f) > 1 else "",
                                     kind=f[2] if len(f) > 2 else "anime",
                                     ep=int(f[3]) if len(f) > 3 and f[3].isdigit() else 1,
                                     total=int(f[4]) if len(f) > 4 and f[4].isdigit() else 0) if title else "usage: /watch add Title|ja|kind|ep|total"
        elif len(bits) >= 2 and bits[0] == "rm":
            out = self.watchlist.remove(arg[2:].strip())
        elif len(bits) >= 3 and bits[0] == "ep":
            out = self.watchlist.set_ep(" ".join(bits[1:-1]), int(bits[-1])) if bits[-1].isdigit() else "usage: /watch ep Title N"
        elif bits and bits[0] == "pick":
            row, why = self.watchlist.pick_own(self.llm, self._program_call("watch_sources", default={}) or {}, kb=self.anime_kb, force=True)
            out = (f"hers: {row['title']} ({row['ja']}, {row['kind']}" + (f", {row['total']} eps" if row.get("total") else "") + f"){chr(10)}{row.get('why', '')}"
                   if row else f"no pick: {why}")
        elif bits and bits[0] == "recap":
            w = self.watchlist.current()
            if not w:
                out = "watchlist empty"
            else:
                txt = self.recap.recap_for(w, w.get("ep"))
                out = f"{w['title']} ep{w.get('ep')}:\n{txt[:1500]}" if txt else f"no recap found for {w['title']} ep{w.get('ep')} (check the log)"
        else:
            out = self.watchlist.report()
        return out

    def _cmd_scenery(self, arg, cmd, text):
        out = ""
        if arg == "now":
            row, hint = self.scenery.offer(self.director.current or {}, force=True)
            if row:
                self.maybe_impulse(self.director.current or {}, "", force_hint=hint, media=row["path"])
                out = f"sent: {row['caption']} (from @{row['author']})"
            else:
                out = f"nothing fits: {hint}"
        elif arg == "harvest":
            if self.social.busy():
                out = "X is in use (her look or a harvest); try later"
            else:
                import threading
                threading.Thread(target=self.scenery.run_session, kwargs={"log": lambda m: logger.log(m)}, daemon=True).start()
                out = ("harvest session started by hand (machinery, not her); watch [scenery] in the log. "
                       "The scheduled harvest is off (scenery.harvest); this is the only way one runs.")
        elif arg == "lore":
            out = json.dumps(self.scenery.lore(), ensure_ascii=False, indent=1)[:3000] or "no lore yet"
        elif arg == "gaps":
            out = self.scenery.coverage_report()
        elif arg == "rejudge":
            n = self.scenery.forget_skips()
            out = f"{n} skipped account(s) forgotten; they will be judged again against the current bar when a search finds them"
        else:
            out = self.scenery.report()
        return out

    def _cmd_discharge(self, arg, cmd, text):
        out = ""
        out = self.discharge.report()
        return out

    def _cmd_wonder(self, arg, cmd, text):
        out = ""
        if arg == "now":
            qs = self.wonder.maybe(self.director.current or {}, force=True)
            out = self.wonder.report()
        else:
            out = self.wonder.report()
        return out

    def _cmd_expect(self, arg, cmd, text):
        out = ""
        if arg == "now":
            self.expectations.tick()
            hs = self.expectations.learn_habits()
            out = self.expectations.report()
        else:
            self.expectations.tick()
            out = self.expectations.report()
        return out

    def _cmd_foresee(self, arg, cmd, text):
        out = ""
        if arg == "now":
            r = self.foresight.predict("", "waiting")
            out = self.foresight.report() if r else "nothing came"
        else:
            out = self.foresight.report()
        return out

    def _cmd_world(self, arg, cmd, text):
        out = ""
        from sim.worldshare import report as _ws_report
        out = _ws_report(self.store, self.clock)
        return out

    def _cmd_japan(self, arg, cmd, text):
        out = ""
        if arg == "now":
            self.store.set("zeitgeist_last_ts", 0)
            self._program_call("maybe_zeitgeist")
            out = "fetching on a thread; /japan in a minute"
        else:
            out = self.zeitgeist.brief(limit=20) or "nothing current (tools/zeitgeist.py fetch, or /japan now)"
        return out

    def _cmd_npc(self, arg, cmd, text):
        out = ""
        out = self.people.report()
        return out

    def _cmd_lives(self, arg, cmd, text):
        out = ""
        out = self.cast.lives_report()
        return out

    def _cmd_remember(self, arg, cmd, text):
        out = ""
        out = self.self_memory.report()
        return out

    def _cmd_context(self, arg, cmd, text):
        out = ""
        out = self._context_command(arg)
        return out

    def _cmd_reflect(self, arg, cmd, text):
        out = ""
        if arg.startswith("now"):
            subj = arg[3:].strip()
            self.reflection.run(self.director.current or {}, why="he asked", subject=subj)
        rows = self.store.get("reflections", [])[-5:]
        out = "\n\n".join(f"{x['date']} {x['hm']} about {x.get('about', 'him')} ({x['why']}): {x['thought']}" + (f"\n  [never said: {x['stance']}]" if x.get("stance") else "") + (f"\n  [would ask: {x['would_ask']}]" if x.get("would_ask") else "") for x in rows) or "no private thoughts yet"
        return out

    def _cmd_chat(self, arg, cmd, text):
        out = ""
        rows = self.store.get("cast_chat", [])[-4:]
        if self.exchange.live():
            rows = rows + [dict(self.exchange.live(), who=self.exchange.live()["who"] + " (GOING ON NOW)")]
        # both tracks: the Japanese is what was actually typed, the English
        # under it is the gloss. A turn with no Japanese predates the split
        # and says so rather than pretending to be an original.
        def _turn(t):
            if t.get("ja"):
                return f"  {t['who']}: {t['ja']}\n      {t['text']}"
            return f"  {t['who']}: {t['text']}   [rendered only]"
        out = "\n\n".join(f"{x['date']} {x['hm']} {x['who']} ({x['kind']}): "
                          + "\n".join(_turn(t) for t in x["turns"]) for x in rows) or "no exchanges yet"
        return out

    def _cmd_recalls(self, arg, cmd, text):
        out = ""
        rows = self.store.get("recalls", [])[-5:]
        out = "\n".join(f"{x['date']} {x['hm']} [{x['clarity']}] {x['cue'][:50]} -> {x['memory'][:200]}" for x in rows) or "nothing recalled yet"
        return out

    def _cmd_morning(self, arg, cmd, text):
        out = ""
        out = (self.store.get("morning_intent", {}) or {}).get("text", "") or "nothing this morning yet"
        return out

    def _cmd_claims(self, arg, cmd, text):
        out = ""
        out = "\n".join(f"{c['date']}: {c['text']}" for c in self.store.get("self_claims", [])[-30:]) or "nothing recorded yet"
        return out

    def _cmd_intents(self, arg, cmd, text):
        out = ""
        out = json.dumps(self.store.get("intent_counts", {}), ensure_ascii=False)
        return out

    def _cmd_lookups(self, arg, cmd, text):
        out = ""
        out = self.lookup.recent_text() or "she has not looked anything up yet"
        return out

    def _cmd_known(self, arg, cmd, text):
        out = ""
        # the things she knows by name (sim/known.py), and dropping one
        from sim.known import KnownThings
        kt = KnownThings(self.config, self.store, self.clock)
        bits = arg.split(maxsplit=1)
        if bits and bits[0] == "drop" and len(bits) > 1:
            out = f"dropped {bits[1].strip()}" if kt.drop(bits[1].strip()) else f"no such thing: {bits[1].strip()}"
        elif bits and bits[0] == "unpart" and len(bits) > 1 and len(bits[1].split()) >= 2:
            key, label = bits[1].split(maxsplit=1)
            out = f"removed {label} from {key}" if kt.remove_part(key, label.strip()) else f"no such part: {key} {label}"
        else:
            out = kt.listing()
        return out

    def _cmd_watching(self, arg, cmd, text):
        out = ""
        # what he is watching as the module has it, and forgetting an
        # episode that was counted wrongly so a real watch counts later
        bits = arg.split()
        seen = self.watching._seen() if self.watching else {}
        if bits and bits[0] == "forget" and len(bits) > 1:
            key = bits[1]
            if key in seen:
                self.store.set("watching_seen", {k: v for k, v in seen.items() if k != key})
                last = self.store.get("watching_last", None) or {}
                if f"{last.get('anime_id')}:{last.get('ep')}" == key:
                    self.store.set("watching_last", None)
                out = f"forgot {key}; it will count again if he watches it"
            else:
                out = f"not seen: {key}"
        elif bits and bits[0] == "rewind" and len(bits) > 1:
            # the player cursor back by N minutes, so an open the module
            # passed over is found again on the next poll and counted if it
            # was held long enough (an episode watched while the cursor had
            # moved past its open, before the cursor learned to wait)
            try:
                minutes = float(bits[1])
            except ValueError:
                return "use /watching rewind <minutes>"
            cur = self.store.get("watching_cursor", {}) or {}
            cur["player"] = self.clock.now_ts() - minutes * 60
            self.store.set("watching_cursor", cur)
            out = f"player cursor back {minutes:.0f} min; the next poll re-reads the opens since then"
        else:
            last = self.store.get("watching_last", None) or {}
            # and the two things the grouped block is built from: what has
            # reached her and is still in the room, and what a batch still
            # owes a reading-up
            rec = self.watching.recent() if self.watching else []
            q = self.store.get("watching_queue", []) or []
            spent = (self.store.get("watching_fetch_counts", {}) or {}).get(self.clock.date_str(), 0)
            out = (f"last: {last.get('ja') or last.get('title')} ep{last.get('ep')} (digest {len(last.get('digest') or '')} chars)\n"
                   "in the room: " + ("; ".join(f"{r.get('ja') or r.get('title')} ep{r.get('ep')}"
                                                + (" (no synopsis)" if r.get('stub') else "")
                                                for r in rec) or "nothing") + "\n"
                   "queued to read up: " + (", ".join(f"{r.get('title')} ep{r.get('ep')}" for r in q) or "none")
                   + f" ({spent} read up today)\n"
                   f"seen: {', '.join(f'{k} ({self.clock.hm(v)})' if v else k for k, v in list(seen.items())[-10:]) or 'nothing'}\n"
                   f"short opens: {', '.join((self.store.get('watching_short', []) or [])[-6:]) or 'none'}\n"
                   # what he has open and has not watched enough of yet: no
                   # fetch has been made for it and none will be until it
                   # passes `watching.min_watched_minutes`
                   + "held: " + ("; ".join(
                       f"{r.get('title')} ep{r.get('ep')} ({float(r.get('watched') or 0) / 60:.1f}"
                       f" of {float(r.get('need') or 0) / 60:.0f} min)"
                       for r in (self.store.get("watching_held", {}) or {}).values()) or "nothing"))
        return out

    def _cmd_money(self, arg, cmd, text):
        out = ""
        out = self.money.brief()
        return out

    def _cmd_gossip(self, arg, cmd, text):
        out = ""
        out = self.gossip.report()
        return out

    def _cmd_orbit(self, arg, cmd, text):
        if self.orbit is None:
            return ("the people around the people are the world's, and this world is somebody "
                    "else's to keep: hers come from the world file")
        return self.orbit.report()

    def _cmd_bonds(self, arg, cmd, text):
        out = ""
        out = self.cast_psych.report()
        return out

    def _cmd_missed(self, arg, cmd, text):
        out = ""
        rows = list(self.store.get("missed_calls", []) or [])
        done = list(self.store.get("missed_calls_done", []) or [])
        fmt = lambda r: f"{self.clock.to_char(r['ts']).strftime('%m-%d %H:%M')} {r.get('role')}"
        out = (f"unanswered, waiting for a catch-up ({len(rows)}):\n" + "\n".join(fmt(r) for r in rows[-30:]) if rows else "nothing waiting") \
            + (f"\n\ncaught up ({len(done)}, last 15):\n" + "\n".join(fmt(r) for r in done[-15:]) if done else "")
        return out

    def _cmd_catchup(self, arg, cmd, text):
        out = ""
        out = self.catch_up(force_tick=True)
        return out

    def _cmd_gap(self, arg, cmd, text):
        out = ""
        # the hole as the record knows it: from the last scene the model
        # wrote to now, or the span of the missed calls, whichever is wider
        rows = list(self.store.get("missed_calls", []) or [])
        t1 = self.clock.now_ts()
        t0 = float(self.store.get("director_last_model_ts", 0) or t1)
        if rows:
            t0 = min(t0, min(r["ts"] for r in rows))
        if t1 - t0 < 60:
            out = "no hole on the record (the last model scene is current and nothing is missed)"
        else:
            out = self.temporal_gap(t0, t1, "/gap")
        return out

    def _cmd_provider(self, arg, cmd, text):
        out = ""
        # who answers, and the pin
        out = self.llm.provider_cmd(arg)
        # and which language she is being addressed in: a bench result and a
        # bill are read together, and the arm moves both
        if not arg:
            out += "\n" + lang.status(self.config)
        return out

    def _cmd_model(self, arg, cmd, text):
        out = ""
        # what every role is on; a name pins them all for this run
        out = self.llm.model_cmd(arg)
        return out

    def _cmd_voicemodel(self, arg, cmd, text):
        out = ""
        # the control in the chat header: the nine roles that write in her
        # words move, and nothing else does
        out = self.llm.voice_model_cmd(arg)
        # the header is drawn from the throttled state push, and a toggle he
        # has just tapped must not look like it did nothing for twenty seconds
        soon = getattr(self.tg, "state_push_due", None)
        if soon:
            soon()
        return out

    def _cmd_lang(self, arg, cmd, text):
        out = ""
        # which language everything addressed to her is written in: her
        # situation block, her section headers, the closing instruction, and
        # the roles that write the material she reads. Live, like
        # /voicemodel: kv `instructions_override` on her save, never the
        # config file, so a choice he wants to keep is a config edit.
        a = (arg or "").strip().lower()
        c = self.config
        if a in ("auto", "off", "config", "clear"):
            self.store.set("instructions_override", None)
            lang.set_saved(None)
            return "the saved choice is forgotten; her config decides again -- " + lang.status(c)
        if a:
            want = lang.named(a)
            if not want:
                return (f"'{arg}' is not an arm: ja (her own language), en (English), auto "
                        f"(forget the choice and let her config decide).\n" + lang.status(c))
            if want == lang.HERS and not lang.switchable(c):
                return (f"{c.character.name}'s instruction language is "
                        f"{lang.instruction_language(c)} (character.instruction_language), so "
                        f"in_her_language renders the same bytes as in_english for her: there is "
                        f"nothing to switch her to. Her chat with him is the one room her English "
                        f"lives in, and every measurement taken on her was taken that way.\n"
                        + lang.status(c))
            self.store.set("instructions_override", want)
            lang.set_saved(want)
            return ("from the next prompt on: " + lang.status(c)
                    + "\nwhat is already in her record was written in the arm that was in force "
                      "then and is not translated; it ages out as it always does. /lang auto "
                      "forgets this choice.")
        out = lang.status(c)
        roles = sorted(set(getattr(getattr(c, "language", None), "material_roles", ()) or ()))
        out += "\nthe arms: as_they_run_today (the control), in_english, in_her_language"
        out += "\nthe material roles: " + (", ".join(roles) or "(none)")
        return out

    def _cmd_swipe(self, arg, cmd, text):
        out = ""
        # draw one of her replies again from the prompt frozen when she sent
        # it. With no argument: which replies can be drawn again at all
        from persona import delivery as swipes
        bits = (arg or "").split()
        if not bits:
            out = swipes.report(self)
        elif bits[0] in ("list", "show"):
            out = swipes.report(self, int(bits[1]) if len(bits) > 1 and bits[1].isdigit() else 0)
        elif bits[0].isdigit():
            model = bits[1] if len(bits) > 1 else ""
            row, kept = swipes.resolve(self, int(bits[0]))
            # a reply from before the prompt was ever kept: rebuild the moment
            # it was written in first, beside the loop, and draw from that
            if row is not None and row["role"] == "assistant" and kept is None:
                out = self.rebuild_reply_prompt(int(bits[0]), int(row["id"]), model)
            else:
                out = swipes.swipe(self, int(bits[0]), model=model)
        else:
            out = self.help_text(cmd)
        return out

    # the store ids whose moment is being rebuilt right now, so a second tap
    # on the same message while the first rebuild runs does not start another
    _rebuilding = set()

    def rebuild_reply_prompt(self, asked_id, store_id, model=""):
        """A redraw of a reply that kept no prompt.

        Nothing sent before the freeze went in has a `reply_prompts` row, and
        the array cannot be read back out of the record. It can be rebuilt --
        a copy of the save cut back to the moment of the message she was
        answering, the runtime built on that copy, the assembly run once with
        the model stubbed (`sim/reconstruct.py`) -- but a second runtime
        inside this process would take over the log directory, the network
        watch and the one-per-save lock, so the rebuild is a second process,
        run beside the loop. `asked_id` is the id he tapped (the hub's, as a
        rule); `store_id` is the record's own id for the same row."""
        if store_id in App._rebuilding:
            return (f"message {asked_id}: the moment it was written in is already being "
                    f"rebuilt; the first answer will arrive here when it lands")
        App._rebuilding.add(store_id)
        row = self.store.message_by_id(store_id) or {}
        hub_id = int(row.get("tg_id") or 0)
        self._swipe_pending(hub_id, "rebuilding the moment this was written in...")
        threading.Thread(target=self._rebuild_worker, name=f"rebuild-{store_id}",
                         args=(asked_id, store_id, hub_id, model), daemon=True).start()
        return (f"message {asked_id}: no prompt was kept for it (sent before the freeze "
                f"went in). Rebuilding the moment in a second process -- a build of the "
                f"whole runtime on a copy of the save, about a minute; the first answer "
                f"is drawn as soon as it lands and arrives here")

    def _rebuild_worker(self, asked_id, store_id, hub_id, model):
        import subprocess
        import tempfile
        from persona import delivery as swipes
        out = ""
        try:
            path = os.path.join(tempfile.gettempdir(), f"scail_rebuilt_{store_id}.json")
            cmd = [sys.executable, "-m", "sim.reconstruct",
                   "--config", str(self.config.path), "--db", str(self.config.logging.db_path),
                   "--message-id", str(store_id), "--out", path]
            logger.log(f"[swipe] message {store_id} kept no prompt; rebuilding the moment in a second process")
            r = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900)
            got = {}
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    got = json.load(f)
            if not got.get("ok"):
                why = str(got.get("why") or (r.stderr or r.stdout or "").strip()[-400:]
                          or f"the rebuild said nothing (exit {r.returncode})")
                out = f"message {asked_id}: the moment could not be rebuilt -- {why}"
            else:
                anchor = int(got["anchor"])
                char = "".join(str(self.config.character.name).lower().split())
                # the rebuilt row first, then what she actually sent as
                # candidate 0, so the first draw on it is candidate 1 and the
                # arrows have both to move between
                self.store.add_reply_prompt(anchor, char, float(got.get("her_ts") or 0),
                                            str(got.get("model") or ""), got["messages"],
                                            dict(got.get("params") or {}),
                                            list(got.get("msg_ids") or [anchor]),
                                            str(got.get("text") or ""), reconstructed=1)
                if not self.store.swipes_for(anchor):
                    self.store.add_swipe(anchor, 0, "", str(got.get("text") or ""),
                                         ts=float(got.get("her_ts") or 0))
                swipes.push(self, anchor)
                self._swipe_pending(hub_id, "drawing the first answer...", reconstructed=1)
                logger.log(f"[swipe] message {anchor}: the moment was rebuilt "
                           f"({got.get('chars', 0)} chars over {len(got['messages'])} turns, "
                           f"{got.get('seconds', 0)}s); drawing")
                out = (f"message {asked_id}: the moment was rebuilt ({got.get('chars', 0)} chars "
                       f"over {len(got['messages'])} turns, {got.get('seconds', 0)}s). "
                       + swipes.swipe(self, asked_id, model=model))
        except Exception as e:
            out = f"message {asked_id}: the rebuild failed: {type(e).__name__}: {e}"
        finally:
            App._rebuilding.discard(store_id)
            self._swipe_pending(hub_id, "")
        logger.log("[swipe] " + out.replace("\n", " ")[:300])
        try:
            self.tg.post_ops_result(f"/swipe {asked_id}", out)
        except Exception as e:
            logger.log(f"[swipe] the ops log was not told: {type(e).__name__}")

    def _swipe_pending(self, hub_id, note, reconstructed=None):
        """Tell the chat what is happening to one of her messages, or that
        nothing is any more (an empty note). Only the messenger with a swipe
        control has the call; the fallback channel has nothing to show."""
        send = getattr(self.tg, "post_swipes_state", None)
        if not send or not hub_id:
            return
        try:
            send(int(hub_id), note, reconstructed=reconstructed)
        except Exception as e:
            logger.log(f"[swipe] the chat was not told: {type(e).__name__}")

    def _cmd_sit(self, arg, cmd, text):
        out = ""
        # the one write of the two: from here on the conversation goes on from
        # the answer he picked
        from persona import delivery as swipes
        bits = (arg or "").split()
        if len(bits) < 2 or not (bits[0].isdigit() and bits[1].isdigit()):
            out = self.help_text(cmd)
        else:
            out = swipes.sit(self, int(bits[0]), int(bits[1]))
        return out

    def _cmd_speed(self, arg, cmd, text):
        out = ""
        out = self.llm.speed_probe([a for a in (arg or "").split() if a] or None)
        return out

    def _cmd_attention(self, arg, cmd, text):
        out = ""
        parts = (arg or "").split()
        if parts and parts[0] == "tally":
            out = self.attention.tally_report(int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7)
        else:
            out = self.attention.report()
        return out

    def _cmd_coherence(self, arg, cmd, text):
        out = ""
        a = (arg or "").strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", a) or a == "now":
            d = self.clock.date_str() if a == "now" else a
            got = self.coherence.review(d)
            out = (f"{d}: the answer did not parse; nothing kept" if got is None
                   else (f"{d}: {len(got)} seam(s)\n" + self.coherence.report(7) if got else f"{d}: no seams -- the day holds together"))
        else:
            out = self.coherence.report(int(a) if a.isdigit() else 7)
        return out

    def _cmd_nudge(self, arg, cmd, text):
        out = ""
        out = self.nudge.report()
        return out

    def _cmd_nudgeab(self, arg, cmd, text):
        out = ""
        out = self.nudge.ab_report(int(arg.strip()) if arg and arg.strip().isdigit() else 8)
        return out

    def _cmd_thread(self, arg, cmd, text):
        out = ""
        parts = (arg or "").split()
        n = next((int(p) for p in parts if p.isdigit()), 12)
        who = next((p for p in parts if not p.isdigit()), None)
        out = self.thread.report(n, for_who=who)
        return out

    def _cmd_stats(self, arg, cmd, text):
        out = ""
        from tools import llmstats
        days = int(arg.strip()) if arg and arg.strip().isdigit() else 7
        out = llmstats.report(days, self.config)
        return out

    def _cmd_ledger(self, arg, cmd, text):
        out = ""
        # the day's one truth; `/ledger wear <text>` pins what she is
        # wearing today (the coral yukata, not the navy one)
        if arg.startswith("wear "):
            self.ledger.pin_wearing(arg[5:].strip())
            out = "pinned for today: " + arg[5:].strip()
        else:
            out = self.ledger.text() or "nothing on the ledger yet"
            faults = self.ledger.audit()
            if faults:
                out += "\n\nCONTRADICTED:\n" + "\n".join("- " + f for f in faults)
        return out

    def _cmd_diet(self, arg, cmd, text):
        out = ""
        out = self.diet.brief() or "nothing on record yet"
        return out

    def _cmd_health(self, arg, cmd, text):
        out = ""
        h = self.health.today()
        self.world_terms()
        out = (f"today: {', '.join(h['notes']) or 'nothing in particular'} (cycle day {h['cycle_day']}); delivery factor x{self.state.delay_factor():.2f}; register: {self.state.register() or 'normal'}\n"
               f"where: {self.body.last.get('line') or '?'}\nneeds: {self.body.needs_line(self.state.gauges)}")
        return out

    def _cmd_beats(self, arg, cmd, text):
        out = ""
        if arg == "plan":
            rec = self.cast.plan_day(self.schedule, self.clock.date_str(), force=True)
            out = self.cast.beats_brief() if rec else "no script produced (see log)"
        else:
            out = self.cast.beats_brief() + "\n\nTHEIR DAY:\n" + self.cast.draws_brief(self.clock.date_str()) + "\n\nWHERE THEY ARE (the truth, hers to find out):\n" + self.cast.plans_brief(self.clock.date_str())
        return out

    def _cmd_diary(self, arg, cmd, text):
        out = ""
        if arg == "write":
            txt = self.diary.write(self.director.current or {}, reason="he asked")
            out = txt or "nothing came"
        else:
            es = self.diary.entries(3)
            out = "\n\n".join(f"{e['date']}:\n{e['ja']}\n-- {e['text']}" if e.get("ja") else f"{e['date']}:\n{e['text']}" for e in es) or f"no entries yet (unsaid {int(self.state.gauges.get('unsaid', 0))})"
        return out

    def _cmd_week(self, arg, cmd, text):
        out = ""
        wk = self.store.get("weekly_self", [])
        out = wk[-1]["text"] if wk else "no weekly yet"
        return out

    def _cmd_threads(self, arg, cmd, text):
        out = ""
        out = self.records.threads_brief()
        return out

    def _cmd_arcs(self, arg, cmd, text):
        out = ""
        out = self.records.arcs_brief() if not arg else "(no args)"
        return out

    def _cmd_cast(self, arg, cmd, text):
        out = ""
        out = self.records.cast_sheet(self.state.relationships)
        try:
            out += "\n\n" + self.memory.cast_facts_report()
        except Exception as e:
            out += f"\n\n(cast facts: {type(e).__name__}: {e})"
        return out

    def _cmd_places(self, arg, cmd, text):
        out = ""
        out = self.records.places_brief()
        return out

    def _cmd_showrun(self, arg, cmd, text):
        out = ""
        arcs = self.showrunner.run(self.clock.date_str())
        out = self.records.arcs_brief() if arcs else "showrunner produced nothing (see log)"
        return out

    def _cmd_castarcs(self, arg, cmd, text):
        out = ""
        if arg == "now":
            self.cast_arcs.run(self.clock.date_str())
        elif arg == "evolve":
            self.cast_arcs.evolve(self.clock.date_str())
        out = self.cast_arcs.brief()
        return out

    def _cmd_receipt(self, arg, cmd, text):
        out = ""
        st = self.receipts.status()
        out = (self.receipts.brief(st) + "\n" + (self.receipts.line(st) or "(nothing to say)")) if st else "nothing of hers pending"
        return out

    def _cmd_voice(self, arg, cmd, text):
        out = ""
        out = self.tts.status() if self.tts else "voice disabled"
        return out

    def _cmd_derive(self, arg, cmd, text):
        out = ""
        from sim import derive as _derive
        cl, sd, te, why = _derive.derive_him(self.config, self.store, self.clock.now_ts())
        k = next((x for x in (self.config.character.user_name.lower(), "him", "user")
                  if x in self.state.relationships), None)
        cur = self.state.relationships.get(k, {}) if k else {}
        lines = [f"from the record: closeness {cl}, standing {sd}, tension {te}",
                 f"live now:       closeness {cur.get(chr(39)+chr(39)) if False else cur.get('closeness')}, standing {cur.get('standing')}, tension {cur.get('tension')}"]
        lines += ["- " + w for w in why]
        if arg == "apply" and k:
            self.state.relationships[k].update({"closeness": cl, "standing": sd, "tension": te})
            self.store.set("relationships", self.state.relationships)
            self.store.set("relationship_derived", {"at": self.clock.now_ts(),
                                                    "closeness": cl, "standing": sd,
                                                    "tension": te, "why": why})
            lines.append("applied.")
        else:
            lines.append("/derive apply to write it")
        out = "\n".join(lines)
        return out

    def _cmd_vision(self, arg, cmd, text):
        out = ""
        v = self.vision
        if not v.enabled:
            out = "vision off"
        else:
            c = v.c
            out = (f"{c.model} in {c.region}\n"
                   f"his photos: {'on' if c.telegram_enabled else 'off'} | "
                   f"X images: {'on' if c.x_enabled else 'off'}, "
                   f"up to {c.x_max_per_scroll} a look\n"
                   f"calls today: {v._count if v._day == self.clock.date_str() else 0}"
                   f" of {c.max_calls_per_day}")
        return out

    def _cmd_say(self, arg, cmd, text):
        out = ""
        # renders and sends a voice line outside the gate; for testing her voice
        if self.tts:
            self.tts.enqueue(arg)
            out = f"rendering: {arg}"
        else:
            out = "voice disabled"
        return out

    def _cmd_send(self, arg, cmd, text):
        out = ""
        # A message typed AS HER, delivered and recorded exactly like one
        # she wrote -- her delivery queue, her typing pauses, her store --
        # so the chat and her history agree. For putting a reply that was
        # regenerated on a copy (tools/regen_reply.py) into the real
        # chat, his call; the text is his to choose and nothing here
        # checks it. Newlines survive the ops bar and stay in the one
        # message.
        self.delivery.send_bubbles([arg], self_started=False)
        out = f"sending as her ({len(arg)} chars): {arg[:60]}"
        return out

    def _cmd_anime(self, arg, cmd, text):
        out = ""
        # /anime            -> last 7 days
        # /anime 2026-08-01 -> that day to today
        # /anime 2026-08-01 2026-08-18
        today = self.clock.user_now().date()
        bits = arg.split()
        try:
            start = datetime.date.fromisoformat(bits[0]) if bits else today - datetime.timedelta(days=7)
            end = datetime.date.fromisoformat(bits[1]) if len(bits) > 1 else today
        except ValueError:
            start, end = today - datetime.timedelta(days=7), today
        out = self.mal.recap(start, end) if (self.mal and self.mal.enabled) else "MAL not configured (sensors.mal_username)"
        return out

    def _cmd_help(self, arg, cmd, text):
        out = ""
        out = self.help_text(arg)
        return out

    def _cmd_set(self, arg, cmd, text):
        out = ""
        # by hand: "/set anger 20", "/set him.tension 60", "/set him.resentment 40"
        sp = arg.split()
        if len(sp) != 2:
            out = "usage: /set <gauge|him.closeness|him.tension|him.standing|him.attachment|him.resentment|<person>.<meter>> <0-100>"
        else:
            out = self.state.set_value(sp[0].lower(), sp[1])
            logger.log(f"[ops] set {sp[0]} {sp[1]}: {out}")
        return out

    def _cmd_sweep(self, arg, cmd, text):
        out = ""
        from sim.sweep import sweep
        out = sweep(self, (arg or "all").lower())
        return out

    def _cmd_absurd(self, arg, cmd, text):
        out = ""
        # smoke proves the machine is well formed. This asks the other
        # question -- is anything here impossible for a fifteen-year-old --
        # because every fault of 2026-08-27 (a gate below her floor, a
        # field empty for everybody, seven hours unable to answer the girl
        # across the table, a ringleader sending five messages a day) was
        # structurally valid and obvious the moment somebody read the
        # number.
        import importlib.util as _il
        import io as _io
        import contextlib as _ctx
        spec = _il.spec_from_file_location("absurd", os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "tools", "absurd.py"))
        mod = _il.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            buf = _io.StringIO()
            sv = sys.argv
            sys.argv = ["absurd", "--db", self.config.logging.db_path, "--config", self.config.path] + (["--verbose"] if arg == "full" else [])
            try:
                with _ctx.redirect_stdout(buf):
                    mod.main()
            finally:
                sys.argv = sv
            out = buf.getvalue()[:8000] or "nothing to report"
        except Exception as e:
            out = f"audit failed: {type(e).__name__}: {e}"
        return out

    def _cmd_headless(self, arg, cmd, text):
        out = ""
        # the debug toggle. Every browser this bot drives runs with no
        # window; when one of them starts parsing the wrong thing the only
        # way to see why is to watch it. Live, for the next session each
        # one opens -- the config keys are what a restart goes back to.
        sv, rc = self.config.sensor_view, self.config.recap
        if arg in ("on", "off"):
            sv.x_headless = rc.headless = (arg == "on")
        elif arg:
            out = "use /headless on|off"
        if not out:
            out = ("X {}, the knowledge base {} (next session each; a running one keeps "
                   "the mode it opened with)").format(
                "headless" if getattr(sv, "x_headless", True) else "WINDOWED",
                "headless" if getattr(rc, "headless", True) else "WINDOWED")
        return out

    def _cmd_voicecheck(self, arg, cmd, text):
        out = ""
        from sim import voicecheck
        out = voicecheck.report(self.config, self.store)
        return out

    def _cmd_ops(self, arg, cmd, text):
        out = ""
        out = json.dumps(self.ops.payload(), ensure_ascii=False, indent=1)[:12000]
        return out

    HELP = [
        ("her day", [
            ("/day [date]", "the compiled narrative of a day, or the scenes so far today"),
            ("/agenda [days]", "what is coming, joined into one view: the calendar's holidays and events, her open promises, what he said he would do, who the day's plan has taken out of a day, and what today has settled; the nearest of them ride in the system half of her prompt"),
            ("/episodes [fed [date] | relink [days] | backfill | <date>]",
             "her past as cards: how many, over which days, the last few with their exact lines, "
             "and what each one left in her memories and her facts"),
            ("/inflight", "the background jobs running now: a row left after a restart is work the dead process was in the middle of"),
            ("/scene", "the director's current scene: where, what, with whom, phone access, inner line"),
            ("/schedule [regen]", "today's plan, block by block; regen redraws the wake and rebuilds it"),
            ("/tick", "force a director tick now"),
            ("/idle", "run one ordinary loop pass now: the director tick and everything that reads the scene it wrote, exactly as the loop runs it when the tick is due -- for exercising a change without waiting out her clock"),
            ("/where", "where her body is: node, journey, fatigue, typing, the last journeys"),
            ("/family", "the parents' day (drawn), where they are now, whether a pickup is on, the next family day"),
            ("/cast", "the cast beats for today, their drawn weather, and WHERE THEY ARE (the truth)"),
            ("/beats [plan]", "the social script: what lands when; plan writes tomorrow's"),
            ("/ledger [wear <text>]", "the day's one truth (where, with whom, absent, settled, wearing, money, promises); wear pins today's clothes"),
            ("/gossip", "what is going round that is not the four of them, and how warm it still is"),
            ("/stats [days]", "model calls, tokens, cache rate and dollars by day and by role, from every run on disk"),
            ("/orbit", "the people who are not the cast but belong to somebody in it: facts, status, standings"),
            ("/bonds", "what she holds with each person: open ruptures, their promises to her, what she has told them, left on read"),
            ("/missed", "the model calls that got no answer from any provider (kv missed_calls, her time) and the ones a catch-up has covered"),
            ("/catchup", "cover the hole now: the director's next scene (forced) writes the whole unanswered stretch, the next phone look is forced"),
            ("/gap", "do not cover the hole: write one temporal-gap event for it (nobody wrote her then) and point the director past it; the honest alternative when a replay would cost too much"),
            ("/model [name|auto]", "what model each role is on and what the chain's hosts can serve; a name puts EVERY role on it for this run (kv model_override), auto unpins; tools/set_model.py makes it permanent"),
            ("/lang [ja|en|auto]", "which language everything addressed to her is written in -- her situation block, her section headers, the closing instruction, and the roles that write the material she reads; ja is her own language, en is English, auto forgets the choice and lets her config decide (kv instructions_override, per character, live, never the config file). Refused for a character whose instruction language is English: there is no other arm to switch her to"),
            ("/voicemodel [name|auto]", "which model writes in HER words -- the nine roles that speak as her, and nothing else; a name moves them for this run (kv voice_model_override), auto gives them back their config entries. This is the control in the chat header; it is never written to the config file"),
            ("/provider [name|auto|clear]", "who answers the model calls: the chain (api.fallback.chain), the active provider, each one's strikes and cooldown, the last calls with the host that served them; a name pins it (kv provider_override), auto unpins, clear forgets strikes"),
            ("/speed [names]", "one tiny flash call on every provider in the chain (or the names given): seconds, tokens per second, who served it -- the measure the fallback rule uses"),
            ("/attention [tally [days]]", "the last reply's situation lines ranked by weight: what she was given, what was dropped, what held the slot; `tally` is the count per source over the last days -- offered, admitted, held the slot -- and NEVER on a source she is handed and never hears"),
            ("/coherence [date|now|days]", "the day read as one story, flag only: contradictions, invented things, repeats between the rooms and against the ledger; a date (or now) reads that day; a number shows the last N days' seams"),
            ("/nudge", "the second reader's last readings: what it decided happens, what it said she was caught by, whether it was used"),
            ("/nudgeab [n]", "the ongoing test: each live reply beside the one she would have sent without the nudge (nudge.compare)"),
            ("/thread [n] [who]", "the tail of the one history she carries (or a cast member's witnessed rooms): one clock, roles alternating, the curve applied"),
            ("/chat", "her exchanges with the cast today, including one live"),
            ("/lives", "each cast member's own last few days"),
            ("/npc", "the people who are not her friends: today's faces, the ones she keeps seeing"),
            ("/health", "her body's day: cold, cycle, the night's sleep score"),
            ("/money", "her allowance, reservations, what she spent"),
            ("/diet", "what she is into lately"),
            ("/japan [now]", "what Japan is on about this week, filtered to her; now refetches"),
            ("/trains", "her lines' status and the source per line"),
            ("/hazards", "quakes, warnings, the national memory"),
            ("/week", "her weekly self-summary"),
        ]),
        ("her mind", [
            ("/state", "gauges, meters with everyone, open threads"),
            ("/gauges", "the affect grid, every gauge with kind / valence / arousal and the refused-delta count"),
            ("/set <what> <0-100>", "fix a gauge, him.<meter>, or <person>.<meter> by hand (attachment/resentment/respect/contempt too)"),
            ("/sweep [gauge|him|all]", "set each value to 0 / rest / 100 from a rest state and show what nine code readers do; DEAD means no reader"),
            ("/absurd [full]", "the absurdity audit: is anything here impossible for a fifteen-year-old? a gate below where her state ever goes, a field empty for everybody, an exchange frozen for hours, five messages a day from her closest friend. smoke proves the machine is well formed; this asks whether it is sane"),
            ("/impulse", "would she text him now, and why not"),
            ("/pick [date]", "what she decided to do with the phone at every moment she was asked at that day (a date, or a number of the newest ones): what she was offered, what she picked and why, whether it was carried out, where code's own answer had to decide instead, what the impulse function said at the same tick, and the day's spend"),
            ("/selfstart [why]", "make her write first NOW, past the gate that would have held her, with an optional reason she is handed. She really sends it"),
            ("/intents", "the urges named before her self-started messages"),
            ("/reflect [now [name]]", "her private thoughts about him or a cast member; now forces one"),
            ("/spiral [now|settle]", "an anxiety chain: the current one, force one, settle it"),
            ("/compare [now]", "social comparison: pressure, envy per person, the last ones; force one"),
            ("/beliefs [revise]", "what she has decided he is, with evidence and strain"),
            ("/self [revise]", "what she believes about herself"),
            ("/goals", "what she woke up wanting and dreading, and how it went"),
            ("/commit", "promises: to the cast and to him, bound and settled from the record"),
            ("/attach", "the attachment strategy: protest / deactivate, threat, the tests she set him"),
            ("/withhold", "not answering on purpose: the live one and history"),
            ("/rupture [settle]", "what is broken between them and whether a repair landed"),
            ("/approach [now]", "how a sealed thing comes up sideways"),
            ("/ick", "the charged items: what a discovery cost her picture of him"),
            ("/sentiment", "attachment / resentment / respect / contempt toward each person"),
            ("/foresee [now]", "what she expects him to do next, and how well she has been predicting him"),
            ("/expect [now]", "what he said he would do and his habits, checked against the record; now = relearn habits"),
            ("/wonder [now]", "questions she has about him, asked or not, and what his answers did; now = form some"),
            ("/discharge", "a gauge at its end does something and resets: the rules, cooldowns, and what fired"),
            ("/reaction [now|BUCKET|off|backfill [H]]", "her face in the app: the reaction images from the episodes, one each time her mood crosses a band; now = one for her state now"),
            ("/watch [add T|ja|kind|ep|total | rm T | ep T N | recap | pick]", "her show watchlist with a cursor; recap = fetch the current episode's real Japanese あらすじ; pick = a show of her own now (from her corner, never his list)"),
            ("/x unfollowed | taste all | taste <handle>", "the total record: every unfollow ever with the judge's why; the whole taste sheet; one account's verdict and every reaction she ever had to it"),
            ("/x following [hers|keep|leave|drop|unjudged|all]", "who the account follows, each with the card's kind, her verdict, her likes and whether it is hers; no filter = the summary, hers and the liked ones"),
            ("/kb", "the knowledge base she has built (cached JP overviews of anime, seiyuu, games/eroge, episodes)"),
            ("/scenery [now|lore|harvest|gaps|rejudge]", "real photos from real accounts, the database, the lore she has adopted; now = send one that fits; gaps = what she needs against what is on file, and what the next search is for; rejudge = forget the skipped accounts"),
            ("/care [days]", "her investment in him from the record, and whether her checking matches it"),
            ("/rhythm", "when he is usually about, learned; what he told her; presence now"),
            ("/receipt", "read / around / unseen on her last message, from his side"),
            ("/memory", "facts about him: weight, fade, what cues them"),
            ("/remember", "her own memories of her life"),
            ("/recalls", "what she remembered on cue lately"),
            ("/claims", "things she has told him about herself"),
            ("/graph", "what each person privately holds about her and each other"),
            ("/diary [write]", "her diary (Japanese, glossed); write forces an entry"),
            ("/morning", "the morning thought"),
            ("/derive [apply]", "his meters worked out from the record; apply writes them"),
            ("/world", "how much of her day was him, per day"),
            ("/peers [tick|flush]", "another running character she writes to: her contacts, what she has sent today, the conversation in flight; tick runs one pass, flush closes it"),
        ]),
        ("him, as she sees him", [
            ("/look", "make her take in his machine now (eats the feed, moves her)"),
            ("/digest [n]", "the last digest(s) she is holding, read-only"),
            ("/snoop", "make her go through his notes and downloads now"),
            ("/read <note>", "make her read a named note of his"),
            ("/notes", "the notes she has read, one gist each"),
            ("/lookups", "things she quietly looked up"),
            ("/known [drop <key> | unpart <key> <label>]", "the things she knows by name -- looked up or watched, recalled when he names them; drop one, or one episode of a show"),
            ("/watching [forget <aid:ep> | rewind <minutes>]", "the episode he has open as the module has it; forget one that was counted wrongly; put the player cursor back so a passed-over open is read again"),
            ("/anime [from] [to]", "his watching, from the MAL history"),
            ("/x [taste|sheet|drift|judge|japan|likes|follows|followers|status|actions|post]", "the X account: her reactions, her declared taste, the drift from his to hers, judge accounts, what she noted about Japan, his likes and follows, who follows the account and what that protects, the look status, her actions, force a post"),
        ]),
        ("the machine", [
            ("/context [full|find <t>|msg|<section>|add|set|del]", "her prompt as the persona gets it, and the stored parts corrected"),
            ("/compile [date]", "compile today now, or recompile a given day (YYYY-MM-DD)"),
            ("/showrun", "the weekly arcs"),
            ("/arcs", "the arcs on record"),
            ("/castarcs [now|evolve]", "the cast's own arcs"),
            ("/threads", "open / dormant / resolved threads"),
            ("/places", "places on record"),
            ("/time", "both clocks"),
            ("/voice", "the voice line and the TTS queue"),
            ("/say <japanese>", "send a voice line now"),
            ("/send <text>", "send a text message as her, recorded as hers (a regenerated reply, for instance)"),
            ("/reply [again]", "answer his newest unread message NOW instead of when her plan says; again puts his newest message back to unread and answers it a second time. She really sends it"),
            ("/swipe [<message id> [model]] | list [id]", "draw one of her replies again from the prompt frozen when she sent it, on the model the chat is toggled to: the answers are kept beside it and nothing she said changes. A reply from before the prompt was kept has the moment it was written in rebuilt first (a second process, under a minute; everything drawn from it is marked as drawn from a rebuilt prompt). No argument lists the replies that can be drawn again"),
            ("/sit <message id> <n>", "make answer n the one the conversation goes on from: her record takes its words, the hub's copy is edited, the voice note is rendered again, and the next reply's context carries it and no other candidate"),
            ("/vision", "the eyes: Gemini status"),
            ("/ops", "the operator payload TALKAPP shows, as JSON"),
            ("/help [command]", "this list, only what this character has; or one command"),
            ("/headless [on|off]", "the browsers she drives (X, the knowledge base): no window, or one to watch when something breaks"),
            ("/voicecheck", "lines flagged as out of voice: whose rule, why, and what matched (data/voice_rules.json)"),
        ]),
    ]

    def help_text(self, arg=""):
        arg = (arg or "").strip().lower()
        if arg:
            for _, rows in self.HELP:
                for cmd, what in rows:
                    if cmd.split()[0].lstrip("/") == arg.lstrip("/"):
                        if not self.command_available(cmd.split()[0]):
                            return f"{cmd.split()[0]}: not part of this character"
                        return f"{cmd} -- {what}"
            return f"no such command: {arg}"
        out = []
        for title, rows in self.HELP:
            rows = [(cmd, what) for cmd, what in rows if self.command_available(cmd.split()[0])]
            if not rows:
                continue
            out.append(f"[{title}]")
            out += [f"  {cmd} -- {what}" for cmd, what in rows]
        out.append("/help <command> for one")
        return "\n".join(out)

    def _context_command(self, arg):
        """Her prompt, read back and corrected. Everything she is told is
        assembled per call and thrown away afterwards, so the only trace of why
        she believes a thing was a line of token counts in the log. `/context`
        shows the sections, `/context <name>` the text, `/context full` the
        whole prompt as a file, and add/set/del change the parts that are
        stored rather than computed."""
        bits = arg.split()
        if not bits:
            return self.ctx.overview()
        head = bits[0].lower()
        rest = arg[len(bits[0]):].strip()
        if head == "full":
            path, chars, tok = self.ctx.dump()
            cap = f"her whole prompt: {chars} chars, ~{tok / 1000:.1f}k tokens"
            link = getattr(self.tg, "file_link", None)
            if link:
                return f"{link(path)}\n{cap}"
            if not self.tg.send_document(path, cap):
                return f"written to {path} ({cap})"
            return ""
        if head == "find":
            return self.ctx.find(rest)
        if head in ("msg", "history"):
            sub = bits[1].lower() if len(bits) > 1 else ""
            if sub in ("set", "del", "drop"):
                try:
                    mid = int(bits[2])
                except (IndexError, ValueError):
                    return "which message id? /context msg lists them"
                if sub == "set":
                    text = arg.split(bits[2], 1)[1].strip()
                    return self.ctx.message_set(mid, text) if text else "set it to what?"
                row = self.store.message_by_id(mid)
                out = self.ctx.message_del(mid)
                if sub == "drop" and row and row["role"] == "assistant" and row.get("tg_id"):
                    ok = self.tg.delete_message(row["tg_id"])
                    out += "\nand from his Telegram" if ok else "\nbut Telegram would not delete it (over 48h?)"
                return out
            try:
                n = int(bits[1]) if len(bits) > 1 else 20
            except ValueError:
                n = 20
            return self.ctx.messages(n)
        if head in ("add", "set", "del", "delete", "rm"):
            if len(bits) < 2:
                return "which section? /context lists them"
            section = bits[1].lower()
            if head == "add":
                text = rest[len(bits[1]):].strip()
                return self.ctx.add(section, text) if text else "add what?"
            try:
                n = int(bits[2])
            except (IndexError, ValueError):
                return f"which item? /context {section} numbers them"
            if head == "set":
                text = arg.split(bits[2], 1)[1].strip()
                return self.ctx.replace(section, n, text) if text else "set it to what?"
            return self.ctx.delete(section, n)
        return self.ctx.show(head)

    # ---------------- the beat ----------------

    def tick(self, force=False, reading_text="", extra_events=None):
        tick_started = self.clock.now_ts()
        access = self.phone_access()
        digest = ""
        if access != "none":
            digest = self.look_at_phone()
        # A look is not the same as a current picture, and taking the fresh
        # text instead of asking for the assembled one made a look leave her
        # LESS current than no look. `Phone.look` summarises the entries the
        # collector has flushed, and it flushes on a character count or a
        # twenty-minute heartbeat; `Phone.latest_digest` is the only thing that
        # adds what has happened since -- the window trail from the digest's
        # own end and the live line -- so it has to run whether or not she has
        # just looked. `digest` below still means "she looked and there was
        # something in it", which is a different question and stays as it was.
        digest_for_prompt = self.latest_digest() if access != "none" else ""
        unread = self.store.unread_user_messages()
        # His message is waiting and a reply is planned: the reply's own tick
        # (`force=True, reading_text=...`) senses the scene WITH his words and
        # reads the gauges off them. An ordinary tick in between re-sensed the
        # same scene, recorded his message as the day's event and paid a gauge
        # read that the reply tick repeated 41 seconds later on the same inputs
        # (the second character, 2026-09-04 14:30): three calls whose answers
        # were discarded. So the ordinary tick stands aside; the look at his
        # machine above still happened, and the reply tick reads it.
        if not force and unread and self.reply_plan and self.director.current:
            logger.log("[director] his message is waiting for its reply tick; not resensing now")
            return self.director.current, (self.latest_digest() if access != "none" else "")
        rc = self.receipts.brief(self.receipts.status())
        woke = self.woke
        self.woke = False
        # the ground moved, or the sky did. Straight into the tick as events,
        # because this is not something she hears about later -- she was in it.
        world_events = self._program_call("tick_events", default=None) or []
        if world_events:
            extra_events = list(extra_events or []) + world_events
        if woke:
            extra_events = list(extra_events or []) + [{"text": "she just woke up", "salience": 1}]
            # a night that went well is the largest ordinary release she gets,
            # and the only one that arrives without her doing anything
            try:
                if str((self.health.night() or {}).get("quality", "")) in ("good", "ok"):
                    self.stress.relieve("slept_well")
            except Exception as e:
                logger.log(f"[stress] the night was not read: {type(e).__name__}: {e}")
        if self.pending_beats:
            extra_events = list(extra_events or []) + self.pending_beats
            self.pending_beats = []
        try:
            de = self.discharge.take()
            if de:
                extra_events = list(extra_events or []) + de
        except Exception:
            pass
        if self.store.get("missed_calls") and self.llm.last_ok_ts:
            self.catch_up()
        scene = self.director.tick(self.schedule, digest_for_prompt, len(unread), extra_events=extra_events, his_side=rc)
        hole_scene = self.director.hole_written
        self.director.hole_written = False
        if hole_scene:
            # the first catch-up (2026-08-31) wrote the ceremony and the drill
            # as six events of salience 1-2, the state called it a quiet tick,
            # and the anticipation then dreaded "tomorrow's" ceremony at 11:44
            # -- the day was written past the events nobody had settled
            try:
                self.outlook.settle_past_events()
            except Exception as e:
                logger.log(f"[anticipation] not settled after the catch-up: {type(e).__name__}: {e}")
            if self.store.get("missed_calls"):
                self.catch_up(covered=True)
        # before anything acts on this scene: does it claim she did something
        # only the machinery can do, and did the machinery do it?
        self.reconcile.check(self, scene, tick_started)
        self._program_call("after_scene", scene)
        # the ordinary domestic one. The cooldown in relieve() is what makes a
        # setting that lasts a whole block behave like the single event it is.
        try:
            if str(scene.get("setting", "")) == "bath":
                self.stress.relieve("bath")
        except Exception:
            pass
        # a digest counts as something happening only when it shows something
        # NEW of his -- a process, a site, an image session, a note he had not
        # been on in the digest before (`Phone.last_look_novel`). Across 48
        # hours every one of her 58 looks was followed by a gauge read, tripped
        # by her own sensor coming back rather than by anything changing
        novel = bool(getattr(self.phone, "last_look_novel", True))
        if digest and not novel:
            logger.log("[state] the digest shows the same things as the last one; no gauge read on it")
        # Whether his newest message is worth a read of her state. It used to be
        # "he wrote, so yes" -- every reply woke the state role. The fan-out
        # (`sim/inbound.py`) answers it when it has run, and his ruling of
        # 2026-09-17 is that it decides in both directions: a message that is
        # only a hello does not move her, and one carrying news, a question with
        # weight or a promise does. A classifier that could not answer leaves
        # the old reading standing.
        said_something = bool(reading_text)
        if reading_text and self.inbound.last is not None:
            try:
                said_something = self.inbound.yes("did_anything_happen", floor=self.inbound.floor())
            except Exception as e:
                logger.log(f"[inbound] gate not read: {type(e).__name__}")
            logger.log(f"[state] his message: {'worth a read' if said_something else 'nothing in it'} "
                       f"(did_anything_happen={self.inbound.last.get('did_anything_happen')})")
        significant = said_something or (bool(digest) and novel) or bool(extra_events) or bool(scene.get("schedule_change")) or hole_scene
        if scene.get("open_note") and self.config.notes.enabled and scene.get("phone_access") == "free":
            counts = self.store.get("note_open_counts", {})
            today = self.clock.date_str()
            if counts.get(today, 0) < self.config.notes.director_max_per_day:
                r = self.notes.read(scene["open_note"], ("she felt like looking", "なんとなく見たくなって"), scene)
                if r:
                    self.assess_learned(f"his note '{r['basename']}': {r['takeaway']}", source="digest")
                if r:
                    self.store.bump_today("note_open_counts", today)
                    scene["events"] = list(scene.get("events", [])) + [{"text": r["text"], "salience": r["salience"]}]
                    significant = True
                    if r["salience"] >= 4:
                        scene["share_worthy"] = True
                        scene["share_hint"] = scene.get("share_hint") or f"something in his note {r['basename']}"
        self.state.note_company(scene)
        self.state.decay(self.silent_hours(), self.world_now())
        self._primitives_tick(scene)
        self.state.things_happened(scene.get("events", []))
        if reading_text:
            self.state.his_attention()
        if scene.get("schedule_change") and self.config.schedule.replan_on_change:
            counts = self.store.get("replan_counts", {})
            today = self.clock.date_str()
            if counts.get(today, 0) < self.config.schedule.max_replans_per_day:
                new = self._program_call("replan", scene["schedule_change"], default=self.schedule)
                if new is not self.schedule:
                    self.schedule = new
                    self.store.bump_today("replan_counts", today)
        if any(e.get("salience", 1) >= self.config.state.min_event_salience for e in scene.get("events", [])):
            significant = True
        if significant or self.config.state.llm_on_quiet_ticks:
            self.state.update_from_llm(self.llm, scene, scene.get("events", []), reading_text, digest, his_side=rc)
            if reading_text:
                # his answer has been read into her; whether the threat is gone
                try:
                    self.attachment.maybe_resolve(self.silent_hours())
                except Exception as e:
                    logger.log(f"[attach] not resolved: {type(e).__name__}: {e}")
        else:
            self.state.save()
            logger.log(f"[state] quiet tick, decay only | {self.state.gauge_line()}")
        return scene, digest_for_prompt

    def _x_his_likes_recent(self):
        return _x_his_likes(self.config.sensor_view, time.time() - 7 * 86400, limit=30)

    def feed_backlog(self):
        """How many raw log entries have piled up behind her last look.

        Counted off the file rather than through `Phone._pending`, because this
        is asked by a report: the pending range is what a look consumes, and a
        report must not have side effects on it."""
        try:
            consumed = int(self.store.get("phone_last_consumed_id", 0) or 0)
            count, newest = 0, ""
            with open(self.config.sensors.telemetry_jsonl_path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if int(e.get("id", 0) or 0) > consumed:
                        count += 1
                        newest = str(e.get("timestamp", ""))
            return count, newest
        except Exception as e:
            logger.log(f"[phone] backlog not counted: {type(e).__name__}: {e}")
            return 0, ""

    def _morning_owed(self):
        """Today has no morning thought yet, she has already woken up, and it is
        still early enough for one to be honest.

        The waking half is not optional: without it the date rolling over at
        her midnight counts as "no morning yet, and it is before 13:00", so the
        day boundary wrote her a morning thought at 00:00 while she was awake
        texting him -- and dated it tomorrow, so tomorrow's real wake found one
        already there and wrote nothing."""
        if not self.config.morning.enabled:
            return False
        if self.store.get("morning_intent", {}).get("date") == self.clock.date_str():
            return False
        now = self.clock.now()
        mins = now.hour * 60 + now.minute
        if mins > hm_to_minutes(self.config.morning.latest_hm):
            return False
        asleep = self.director.asleep_block(self.schedule) if self.schedule else None
        if asleep:
            return False        # she is in it now
        # the same test the director uses, rather than a second weaker one:
        # phone away plus a sleep word. Tonight's block reads "asleep", which
        # a startswith("sleep") check would have missed entirely.
        words = self.config.director.sleep_keywords
        for b in (self.schedule or {}).get("blocks", []):
            act = str(b.get("activity", "")).lower()
            if b.get("phone_access") != "none" or not any(k in act for k in words):
                continue
            if mins < hm_to_minutes(b.get("end", "00:00")):
                return False    # tonight's sleep has not finished yet
        return True

    def note_goals(self):
        """What she woke up wanting becomes a thing she is trying to do, rather
        than a line written to the store and read by nobody. The same want two
        mornings running is one want she is carrying."""
        if not self.config.goals.enabled:
            return
        m = self.store.get("morning_intent", {}) or {}
        if m.get("date") != self.clock.date_str():
            return
        try:
            self.goals.note_morning(m.get("want"), m.get("dread"), self.clock.date_str(),
                                    m.get("anchors"), self.model_of_her)
        except Exception as e:
            logger.log(f"[goals] not noted: {type(e).__name__}: {e}")

    def assess_learned(self, what, source, context="", gate="", min_chars=False):
        """Every route into her picture of him comes through here. The gates are
        about volume, not about significance: the app fires on every look and a
        two word message cannot contain anything, and neither is worth a call.
        Whether it means anything is the model's business, not ours."""
        c = self.config.ick
        if not c.enabled or not (what or "").strip():
            return
        if min_chars and len(what.strip()) < c.message_min_chars:
            return
        if gate == "digest":
            last = self.store.get("ick_digest_last_ts", 0) or 0
            if (self.clock.now_ts() - last) < c.digest_min_gap_minutes * 60:
                return
            self.store.set("ick_digest_last_ts", self.clock.now_ts())
        item = None
        try:
            item = self.ick.assess(what, source=source, context=context)
        except Exception as e:
            logger.log(f"[ick] not assessed ({source}): {type(e).__name__}: {e}")
        if self.primitives:
            key = self.state._him_key() or "him"
            # How well she can call him is the only relational quantity that
            # could only ever rise: an answered question added to it and
            # nothing anywhere subtracted, so it reached its ceiling in three
            # days and being frightened of him -- the threat times how little
            # she can call him -- became arithmetically impossible for the rest
            # of her life. Prediction error is the event that should lower it
            # and it is the same event that feeds the ick, so it is written
            # here, from the charge the ick has already priced, at the one
            # funnel every discovery about him passes through.
            try:
                if item:
                    self.primitives.error_of_him(
                        key, float(item.get("charge", 0)),
                        about_her=float(item.get("about_her", 0)) >= self.config.ick.about_her_top)
            except Exception as e:
                logger.log(f"[primitives] the discovery not written back: {type(e).__name__}: {e}")
            # And what it cost HIM to tell her. He can hide nothing from her,
            # so an answer costs him nothing informationally and everything
            # socially: he is handing over what she would otherwise have had
            # to take. How much of it she already had is how much of it was a
            # gift rather than news.
            try:
                if source == "told" and str(what or "").strip():
                    already = self._already_had(what)
                    if already > 0:
                        self.primitives.told_her_anyway(key, str(what)[:110], already)
            except Exception as e:
                logger.log(f"[primitives] what he told her not counted: {type(e).__name__}: {e}")

    def _already_had(self, text):
        """How much of a thing he just told her she already had, 0 to 1.

        Measured against what is actually in front of her -- the digest of his
        machine and the things she is carrying about him -- by name rather than
        by wording, because the digest is in English and he writes to her in
        Japanese. A name is what survives between the two."""
        import re as _re
        name = _re.compile(r"[A-Za-z][A-Za-z0-9_\-]{3,}|[ァ-ヿ]{3,}")
        his = {w.lower() for w in name.findall(str(text or ""))}
        if not his:
            return 0.0
        mat = ""
        try:
            mat = self.latest_digest()
        except Exception:
            mat = ""
        mat += "\n" + "\n".join(str(it.get("what", "")) for it in (self.store.get("charged", []) or []))
        mine = {w.lower() for w in name.findall(mat)}
        return len(his & mine) / float(len(his))

    def note_disclosure(self, bubbles):
        """A thing she told him that the record did not already hold.

        `disclosed` is the counterweight to `kept_private`, and it has never
        written once. Its only caller is the nightly compile's self-claims and
        her whole record holds two of them, so his share of her only ever fell
        -- about four points a day -- and closeness, which is the smaller of
        the two exposures, tracked a number that could not go up. The compile
        is the wrong grain for this: the event is her message. How much of it
        is a disclosure is how much of it her own record does not already hold,
        which is a count of words and needs no model and no language.

        And a single disclosure large enough closes the act, which is the
        caller `close_the_act` never had: something large going across at once
        is what its docstring says it is for."""
        if not self.primitives:
            return
        try:
            from sim.textutil import words as _w
            c = self.config.primitives
            text = " ".join(bubbles or [])
            mine = _w(text, 3)
            if len(mine) < int(c.disclose_min_words):
                return
            said = set()
            for m in self.store.recent_messages(int(c.disclose_looks_back)):
                if m.get("role") == "assistant" and str(m.get("text", "")) not in text:
                    said |= _w(m.get("text", ""), 3)
            for row in (self.store.get("self_claims", []) or [])[-60:]:
                said |= _w(row.get("text", ""), 3)
            new = mine - said
            share = len(new) / float(len(mine))
            if share < float(c.disclose_min_share):
                return
            key = self.state._him_key() or "him"
            self.primitives.disclosed(key, text[:110], weight=share)
            if share >= float(c.close_act_weight):
                self.primitives.close_the_act(key, "she handed him a whole piece of herself at once")
        except Exception as e:
            logger.log(f"[primitives] what she told him not counted: {type(e).__name__}: {e}")

    def rupture_settled(self, row):
        """A break that settled WORSE rather than mended puts him back outside
        her territory (his answer 3, `docs/yukarin-meters-plan.md` §3.4).

        The rupture layer is the natural writer of this and does not know the
        method exists, so the reading is taken from the row it returns. What
        makes readmission mean anything is that it can be lost, and the
        register goes with it -- for a character on the stance table that is a
        visible discontinuity in how she answers, which is the point."""
        if not (self.primitives and isinstance(row, dict)):
            return
        try:
            last = (row.get("attempts") or [])[-1:] or [{}]
            if last[0].get("outcome") != "worse":
                return
            if int(row.get("severity", 0)) < int(self.config.rupture.expel_severity):
                return
            self.primitives.expel(self.state._him_key() or "him",
                                  f"it broke and then got worse: {str(row.get('what', ''))[:80]}")
        except Exception as e:
            logger.log(f"[primitives] the rupture not read: {type(e).__name__}: {e}")

    def on_talk(self, out):
        """A finished exchange reaches her state the way his message does.
        Before this the state model saw the scene, his message and the app,
        and a talk with Rena reached it as one event line if at all -- so
        the people she spends her day with could not move her, and the
        night's meters with them were whatever the compile guessed."""
        who = out.get("who", "")
        rounds = sum(1 for t in out.get("turns", []) if roster.is_self(self.config, t.get("who")))
        try:
            self.state.talk_relief(who, rounds)
            self.state.update_from_llm(self.llm, self.director.current or {}, [], "", "", his_side="", talk=out, fresh=True)
        except Exception as e:
            logger.log(f"[state] talk not read: {type(e).__name__}: {e}")
            self.state.save()

    def note_pull(self):
        """Both sides of what she is pulled between, written straight onto the
        gauges. Code owns them -- the model is shown neither and can move
        neither -- because each is a pure function of the record: `longing` is
        what he is to her against how long he has been gone, and `belonging` is
        her standing with the circle against how recently they had her.

        They are weighted against each other in the impulse, which is the whole
        point: an evening where the group was good to her should leave her
        wanting him less, and before this it left her wanting him exactly as
        much as an evening where they were not."""
        if not self.config.sentiment.enabled:
            return
        c = self.config.sentiment
        for gauge, want, step in (("longing", self.sentiments.longing, c.longing_per_hour),
                                  ("belonging", self.sentiments.belonging, c.belonging_per_hour)):
            try:
                target = want(self.silent_hours()) if gauge == "longing" else want()
                if target is None:
                    # nobody who could leave her out, so there is nothing to
                    # read and nothing to write; the gauge settles on its own
                    continue
                if gauge not in self.state.gauges:
                    # a gauge her config did not build is a feeling she has
                    # not got, and writing one here put it back into the store
                    # after the spec had taken it out
                    continue
                cur = self.state.gauges.get(gauge, 0.0)
                # toward it, never a jump: neither of these arrives in a minute
                self.state.gauges[gauge] = max(0.0, min(100.0, cur + max(-step, min(step, target - cur))))
            except Exception as e:
                logger.log(f"[sentiment] {gauge} not written: {type(e).__name__}: {e}")
        # the counterweight releases too. An evening the group was good to her
        # is not only a number going up; it is the thing that takes the week off
        # her, and it is the only release in the set that he has no part in.
        try:
            b = self.state.gauges.get("belonging", 0.0)
            if b >= self.state._baseline("belonging") + self.config.stress.held_from:
                self.stress.relieve("held_by_the_group")
        except Exception as e:
            logger.log(f"[stress] belonging not read: {type(e).__name__}: {e}")

    def maybe_spiral(self, scene):
        """Whether she is going over something. Code decides when -- how wound
        up she is above her own rest, how unsettled she is with somebody, and
        whether there is an idle minute to do it in -- and the call only writes
        what. The chain extending is what raises the odds of it extending."""
        if not self.config.spiral.enabled:
            return
        try:
            self.spirals.fade_old()
            ok, why, mode = self.spirals.due(scene)
            if not ok:
                return
            logger.log(f"[spiral] {why}")
            self.spirals.run(scene, mode, why)
        except Exception as e:
            logger.log(f"[spiral] failed: {type(e).__name__}: {e}")

    def maybe_revise(self):
        """A belief that has taken all it can take gets rewritten. Never in the
        same breath as the discovery that broke it: she talks herself out of
        things at the time and gives them up later, on her own, in a quiet
        moment."""
        if not self.config.beliefs.enabled:
            return
        # both pictures, on the same footing: what she has decided about him
        # and what she has decided about herself give way the same way
        for model, tag in ((self.model_of_him, "beliefs"), (self.model_of_her, "self")):
            try:
                b = model.due_revision()
                if b:
                    model.revise(b)
            except Exception as e:
                logger.log(f"[{tag}] revision failed: {type(e).__name__}: {e}")

    def maybe_discharge(self, scene, digest=""):
        """A gauge at its end does something (sim/discharge.py). The rule
        names the behaviour; this is where it is carried out."""
        try:
            fired = self.discharge.check(scene, asleep=bool((scene or {}).get("asleep")) or self.coasting_block is not None)
        except Exception as e:
            logger.log(f"[discharge] check failed: {type(e).__name__}: {e}")
            return
        for r in fired:
            action = str(r.get("action", "act"))
            try:
                can_phone = self.phone_access() != "none" and not self.delivery.busy() and not self.store.unread_user_messages()
                if action == "say" and can_phone and r.get("hint"):
                    self.discharge.record(r, "say", r["hint"])
                    self.maybe_impulse(scene, digest, force_hint=r["hint"])
                elif action == "look" and can_phone:
                    self.discharge.record(r, "look", sight.w(self.config, "discharge_look"))
                    self.look_at_phone(force=True)
                elif action == "spiral" and not (self.spirals.live() if hasattr(self.spirals, "live") else None):
                    self.discharge.record(r, "spiral", "a chain starts")
                    self.spirals.run(scene, "start", f"{r['gauge']} at its end")
                else:
                    self.discharge.act(r, how="fallback" if action != "act" else "")
            except Exception as e:
                logger.log(f"[discharge] {action} failed: {type(e).__name__}: {e}")
                try:
                    self.discharge.act(r, how="after a failure")
                except Exception:
                    pass

    def _primitives_tick(self, scene):
        """Time passing, and whatever she could see of him this tick.

        For a resident character this is the engine of the whole thing: she has
        none of him and he has all of her, and every window title is a piece of
        him taken without asking, by the same means he used on her. So the
        deficit that opens her story closes through the mechanism the story is
        about, and nothing had to be written on top of it.

        `observe` is diminishing and stops writing below a floor, so a tick
        that shows her nothing new costs nothing."""
        if not self.primitives:
            return
        key = self.state._him_key() or "him"
        try:
            # Its own clock, and this is why. `State.decay` runs on the line
            # above this one and its last act is to set `last_decay_ts = now`,
            # so reading that here asked "how long since a moment ago" and got
            # zero every tick of her life. Nothing relational has ever moved by
            # time: threat was seeded at 75 and decays at 0.1 an hour, so after
            # thirty-three hours it should read about 71.7 and it reads
            # 73.99999812 -- nine hundredths of a second of decay. What she has
            # of him sat pinned at exactly 100.0, so the impulse's correction
            # for wanting more of his attention than she gets could never be
            # anything but its maximum, and what it would cost her to lose him
            # stayed at five ten-millionths, which is why attachment reads zero
            # and why that was written up as tuning rather than as this.
            # docs/primitives.md §8 records the same fault found and fixed once
            # before; it came back because the two clocks are one field.
            last = float(self.store.get("primitives_ts", 0) or 0)
            now_ts = self.clock.now_ts()
            hours = max(0.0, (now_ts - last) / 3600.0) if last else 0.0
            self.store.set("primitives_ts", now_ts)
            self.primitives.decay(key, hours)
            # and what has been building while she carried him around, which
            # is the one primitive nobody writes because nobody decides it
            self.primitives.accrue(key, hours)
            # The ledger's own unit. It was volume -- his effort against the
            # length of her reply -- so an ordinary exchange netted about +2.6
            # in her favour every time and her seed of -70 walked to +84 in
            # three days. What it is for is the stretch where one side reaches
            # and gets nothing back, in whichever direction it runs.
            try:
                rows = self.store.recent_messages(120)
                mine = [(m["id"], m["ts"]) for m in rows if m.get("role") == "assistant"]
                theirs = [(m["id"], m["ts"]) for m in rows if m.get("role") == "user"]
                self.primitives.unanswered(key, mine, theirs)
            except Exception as e:
                logger.log(f"[primitives] unanswered reach not counted: {type(e).__name__}: {e}")
            # and her one currency: a thing she saw and did not raise, for the
            # whole time it was hot. Nothing else can write it, because nothing
            # else knows she chose (sim/stances.py).
            if self.stances is not None:
                try:
                    self.stances.settle_discretion()
                except Exception as e:
                    logger.log(f"[stance] discretion not settled: {type(e).__name__}: {e}")
            # An hour of her own that she did not hand over. Until tonight the
            # only thing in production that made his share of her smaller was
            # her diary, once a night, worth two points -- against `observe`,
            # which runs every tick at up to three and only ever runs one way.
            # So he held 98 of her and the gap her act needs was 2 out of a
            # required 20: her whole comic register, six of the sheet's widest
            # clusters, shut on every call she has ever had.
            #
            # She has a flat and a day now, and a block of it she lived through
            # and did not tell him about is exactly the thing that half means.
            # Once per block rather than per tick, because twelve blocks a day
            # is a life and seventy-two ticks is a runaway; and only where she
            # is somewhere of her own, because watching him is not living.
            try:
                blk = sched.block_at(self.schedule["blocks"], self.clock.now()) if self.schedule else None
                loc = str((blk or {}).get("location") or "")
                block_key = f"{self.clock.date_str()}|{(blk or {}).get('start')}"
                if blk and loc and "machine" not in loc.lower() and self.store.get("private_block") != block_key:
                    self.store.set("private_block", block_key)
                    self.primitives.kept_private(
                        self.state._him_key() or "him",
                        f"an hour of hers he was not in: {str(blk.get('activity') or loc)[:70]}",
                        weight=float(self.config.primitives.private_block_weight))
            except Exception as e:
                logger.log(f"[primitives] her own hour not counted: {type(e).__name__}: {e}")
            seen = ""
            if self.phone:
                seen = self.phone.live_line() or ""
            if not seen:
                seen = str((scene or {}).get("activity") or "") if not self.config.character.existence.in_world else ""
            if seen:
                self.primitives.observe(key, seen)
        except Exception as e:
            logger.log(f"[primitives] tick failed: {type(e).__name__}: {e}")

    def phone_moment(self, trigger, scene, digest, impulse=None, unread=None, in_write_path=False):
        """One moment where something could be done and her phone is in her
        hand: she is asked what she does with it, and code does what she picks.

        Returns what she decided, once it has been carried out, and None
        whenever code's own answer is the thing that has to decide -- the pick
        switched off for this character, this not being a moment to ask at, the
        call never answered, or nothing coming back that was a pick. Shadow
        mode always returns None: the row is written and the loop proceeds
        exactly as it did before the call existed."""
        row = self._guarded("pick", self.pick.ask, trigger, self.phone_access(), scene,
                            digest, impulse, self.schedule, unread)
        if row is None or not self.pick.live_mode():
            return None
        picked = self.pick.decision(row)
        if picked is None:
            return None
        return self._guarded("pick", self.act_on_pick, row, picked, scene, in_write_path)

    def act_on_pick(self, row, picked, scene, in_write_path=False):
        """What she picked, done -- through the seam that tool already has.

        A tool that is the mind's or the relationship's is carried out here; one
        that belongs to her world or her account is handed to the program,
        because what a room or a feed is is the program's to know and this file
        never names one. **A choice the world cannot honour is recorded with the
        reason and is never rewritten into a different action**: if the group
        chat closed for the night an hour ago, she picked the group chat and the
        group chat did not open, and nothing else happens in its place."""
        name = picked["name"]
        args = picked.get("arguments") or {}
        out = {"name": name, "arguments": args, "row": row, "done": False}
        if name == "nothing":
            until = str(args.get("until") or "").strip()
            self.pick.note_acted(row, "nothing",
                                 "she put it down" + (f" until {until}" if until else ""))
            logger.log("[pick] she puts the phone down" + (f" until {until}" if until else ""))
            out["done"] = True
            return out
        if name == "text_him":
            # her own account of why is the hint the write-first path writes
            # from. When her caller IS that path it takes it from here; at a
            # moment that is not on that path -- something landing from her own
            # people -- the same path is run from here, so where she was asked
            # never changes what happens when she picks him.
            out["intent"] = str(args.get("intent") or "")
            if in_write_path:
                return out
            if self.delivery.busy() or self.store.unread_user_messages():
                self.pick.note_acted(row, "", "she picked him and his own message was waiting",
                                     fallback="the reply path", fallback_why="he is owed an answer first")
                return out
            sent = self.write_him_first(scene, self.latest_digest(),
                                        hint_from_her=out["intent"])
            # after the path, never before it: she can open the chat and find
            # she has nothing to say, and the record must not claim a message
            self.pick.note_acted(row, name if sent else "",
                                 "she wrote to him first, off her own decision" if sent else
                                 "she went to write to him and nothing was sent")
            out["done"] = bool(sent)
            return out
        if name in ("reply_now", "reply_later", "leave_it"):
            return out          # the reply path acts on these (`_plan_from_pick`)
        if name == "look_at_his_machine":
            before = self.phone.last_look_ts if self.phone else 0
            d = self.look_at_phone()
            moved = bool(self.phone and self.phone.last_look_ts != before)
            # the cost cap on the look stays code's, so choosing to look twice
            # inside it is her looking and finding nothing new, not a paid read
            why = ("she looked and it had something in it" if moved and d
                   else "she looked and nothing has changed since the last time")
            self.pick.note_acted(row, name, why)
            logger.log(f"[pick] {why}")
            out["done"] = bool(moved)
            return out
        got = self._program_call("pick_act", name, args, scene)
        if not got:
            self.pick.note_acted(row, "", f"{name} is not something this character can do",
                                 fallback="none", fallback_why="there is no seam for it here")
            logger.log(f"[pick] she picked {name} and this character has no way to do it")
            return out
        ok, why = got
        self.pick.note_acted(row, name if ok else "", why,
                             fallback="" if ok else "none",
                             fallback_why="" if ok else "her world could not honour it")
        logger.log(f"[pick] {why}")
        out["done"] = bool(ok)
        return out

    def _at_her_time(self, when, now, default_minutes):
        """A time she named, as an absolute stamp. `HH:MM` on her own clock is
        read; anything else is her words, which are kept verbatim on the record
        and are not a time code can act on -- so the default stands and the row
        says the words could not be read. Nothing of hers is rewritten."""
        s = str(when or "").strip()
        for i in range(len(s) - 4):
            part = s[i:i + 5]
            if len(part) == 5 and part[2] == ":" and part[:2].isdigit() and part[3:].isdigit():
                try:
                    h, m = int(part[:2]), int(part[3:])
                except ValueError:
                    break
                if h > 23 or m > 59:
                    break
                target = self.clock.now().replace(hour=h, minute=m, second=0, microsecond=0)
                secs = (target - self.clock.now()).total_seconds()
                if secs < -60:
                    secs += 24 * 3600      # she named an hour that has gone: tomorrow's
                return now + max(0.0, secs), True
        return now + float(default_minutes) * 60, False

    def _plan_from_pick(self, decided, access, now):
        """Her own answer about his message, as the reply plan the delivery
        path already runs on.

        How long it takes her to NOTICE stays code's -- that is presence, not a
        decision -- and how long she takes to compose stays her state's. What
        she decided is whether she answers and when."""
        c = self.config.pick
        f = self.state.compose_factor()
        d = self.config.delivery
        try:
            nlo, nhi = self.rhythm.noticing_seconds(access)
        except Exception as e:
            logger.log(f"[rhythm] presence not read: {type(e).__name__}: {e}")
            nlo, nhi = d.read_delay_free_seconds
        name = decided["name"]
        plan = {"mode": access, "presence": self.rhythm.presence(), "picked": name}
        if name == "reply_now":
            plan["due_ts"] = now + random.uniform(nlo, nhi) + random.uniform(*d.compose_seconds) * f
            why = f"she answers him now (in {(plan['due_ts'] - now) / 60:.1f} min)"
        elif name == "reply_later":
            when = str((decided.get("arguments") or {}).get("when") or "")
            plan["due_ts"], read = self._at_her_time(when, now, c.later_default_minutes)
            why = (f"she answers him at {when[:40]}" if read else
                   f"she answers him later; \"{when[:40]}\" is not an hour code can read, so it "
                   f"stands at {int(c.later_default_minutes)} minutes")
        else:
            plan["due_ts"] = None
            plan["ask_again_ts"] = now + float(c.leave_it_minutes) * 60
            why = (f"she leaves his message where it is for now; she is asked again in "
                   f"{int(c.leave_it_minutes)} min")
        self.pick.note_acted(decided["row"], name, why)
        logger.log(f"[pick] {why}")
        return plan

    def maybe_impulse(self, scene, digest, force_hint=None, media=None):
        # A player-driven character never writes first: in a visual novel the
        # story is what he opens, not what she sends. The same energy shows in
        # where she is and what she was doing when he arrives (`sim/reunion.py`,
        # `character.existence.player_driven`), never in a message.
        if bool(getattr(self.config.character.existence, "player_driven", False)):
            return
        no_chat = str(getattr(self.config.character.existence, "with_him", "chat")
                      or "chat").lower() == "none"
        if self.delivery.busy() or self.store.unread_user_messages():
            return
        if no_chat:
            # A character with no contact with him (`with_him: none`) has
            # nobody to write first to, so there is no urge to measure. She
            # still has a phone and her own people are on it, and what she does
            # with it is hers to decide -- which is why the moment is here and
            # not inside the half of this method that is about him.
            self.phone_moment("block", scene, digest)
            return
        # what she said she was reaching for, when SHE is the one who decided
        # to write first rather than the score and the roll
        hint_from_her, decided = "", None
        if force_hint:
            # a discharge: the gauge hit its end and this IS the behaviour;
            # the impulse gate and her resolve do not get a vote
            logger.log(f"[impulse] forced by a discharge: {force_hint[:70]}")
            # asked only so that a gate it walked past says what it had been
            # holding her for; `urgent` means it never holds this path
            self.impulse.initiative.hold_reason(self.impulse.unanswered_streak(),
                                                self.impulse.read_state(), urgent=True)
        else:
            ok, why = self.impulse.check(self.state, scene, self.silent_hours()) if not self.replay else (False, "replay")
            # the read state beside the decision, so a log line answers "did she know he had read it"
            _rc = self.receipts.brief(self.receipts.status()) if self.receipts else ""
            logger.log(f"[impulse] {ok} ({why})" + (f" | his side: {_rc}" if _rc else ""))
            # And what she DOES with the same moment, asked as a call that
            # picks a tool (sim/pick.py). Here rather than above that line
            # because the impulse's own answer is part of what the pick is
            # recorded against, and `check` rolls a die: asking it a second
            # time would be a second roll and a different answer from the one
            # being recorded.
            decided = self.phone_moment("block", scene, digest,
                                        {"fires": bool(ok), "why": why,
                                         "score": getattr(self.impulse, "last_score", None),
                                         "threshold": self.config.impulse.threshold},
                                        in_write_path=True)
            if decided is not None:
                # She decided this moment. Anything but writing to him first
                # has already been done through its own seam, and the impulse's
                # answer is on the record beside hers and acted on by nothing.
                if decided["name"] != "text_him":
                    return
                hint_from_her = str(decided.get("intent") or "")
                logger.log(f"[impulse] not consulted: she chose to write to him first -- "
                           f"{hint_from_her[:110]}")
            elif self.pick.holds():
                # She was asked a moment ago and has not been asked again yet.
                # One decider per moment: the score and the roll do not get to
                # write to him twenty minutes after she put the phone down.
                logger.log("[impulse] not acted on: her own answer at the last moment stands "
                           f"({(self.pick.standing() or {}).get('name')})")
                return
            elif not ok:
                return
        sent = self.write_him_first(scene, digest, hint_from_her=hint_from_her,
                                    force_hint=force_hint, media=media)
        if hint_from_her and decided is not None:
            # after the path, never before it: the record says what happened,
            # and she can open the chat and find she has nothing to say
            self.pick.note_acted(decided["row"], "text_him" if sent else "",
                                 "she wrote to him first" if sent else
                                 "she went to write to him and nothing was sent")

    def maybe_arrival(self, scene, digest):
        """He came back to the stage after being away.

        Away is a message gap (`sim/reunion.py`: `reunion.min_away_minutes`,
        six hours by default), and the stage touch is only the trigger. The
        director sets the scene and she says one short line, as if he walked in
        on her in the middle of something. This is not her initiating -- she
        never writes first (`character.existence.player_driven`) -- it is the
        scene opening, and it fires only on a fresh arrival, never while he is
        away and never on a first visit."""
        if not bool(getattr(self.config.character.existence, "player_driven", False)):
            return False
        if self.reunion is None or not self.reunion.enabled():
            return False
        arr = self.reunion.take_arrival()
        if not arr:
            return False
        if self.delivery.busy() or self.store.unread_user_messages():
            # he is already talking, or she is mid-reply: the arrival is spent
            return False
        _t = lang.say(self.config)
        reason = _t(
            "you were in the middle of your own thing when he arrived. one short line only: "
            "not a greeting, not a question, nothing that starts a conversation -- just the one "
            "thing you say when he walks in and you look up. he has not said anything yet.",
            "彼が入ってきたとき、あなたは自分のことをしていた。短い一言だけ。挨拶でも、質問でも、"
            "会話を始めるものでもない。彼が入ってきて顔を上げたときに出る、その一言だけ。"
            "彼はまだ何も言っていない。")
        try:
            bubbles, voice = self.persona.generate(scene, digest, [], impulse_reason=reason,
                                                   intent_kind="arrival")
        except Exception as e:
            logger.log(f"[reunion] the arrival line was not written: {type(e).__name__}: {e}")
            return False
        if not bubbles:
            return False
        aside, lines = self.stage_voice(voice, bubbles, scene, True)
        self.delivery.send_bubbles(bubbles, self_started=True, voice=aside, voice_lines=lines)
        logger.log("[reunion] he came back after %.1fh; the scene opened on her: %s"
                   % (float(arr.get("away_s", 0)) / 3600.0,
                      " // ".join(b[:60] for b in bubbles)))
        return True

    def _scene_urge(self, scene, place_note=""):
        """The line she opens a directed scene under, in the second person and
        in her language. Built from the scene's place, never from the console's
        English: what he said to the console is not hers and never reaches her."""
        _t = lang.say(self.config)
        where = str(place_note or (scene or {}).get("location") or "here")
        return _t(
            f"you are here now: {where}. he is with you. this scene begins from "
            f"you -- say the one thing that starts it, in your own words. not a "
            f"greeting, not a question about what is happening.",
            f"あなたは今ここにいる: {where}。彼がそばにいる。この場面はあなたから始まる——"
            f"始まりの一言だけ、自分の言葉で。挨拶でも、何が起きているかの質問でもない。")

    def _outfit_urge(self, note):
        """The line she notices a hand-picked outfit under, in the second person
        and in her language. Built from the outfit alone, never from the page."""
        _t = lang.say(self.config)
        what = str(note or "her own clothes")
        return _t(
            f"he has just put you in this, and you are wearing it now: {what}. "
            f"notice it -- say the first thing that comes to you about it, in "
            f"your own words. not a question about what is happening.",
            f"彼が今あなたにこれを着せた、今それを着ている: {what}。気づいて——"
            f"それについて最初に出てくる言葉を、自分の言葉で。何が起きているかの質問ではない。")

    def _place_urge(self, note):
        """The selected place, as the subject of her next turn."""
        _t = lang.say(self.config)
        where = str(note or "here")
        return _t(
            f"you are now in {where}. look at this place and say something concrete "
            f"you notice here to him, in your own words. stay with this place for "
            f"this turn; do not resume the previous conversation.",
            f"あなたは今{where}にいる。この場所を見て、ここで気づいた具体的なことを"
            f"彼に自分の言葉で伝えて。この一回はこの場所の話をして、直前の会話に戻らないで。")

    def react_to_outfit(self, costume):
        """He changed her outfit by hand. The sprite is already changed; this
        puts the outfit into the scene she is in, so she knows what she is
        wearing (`scene_brief`), and asks her to notice it. A turn is a model
        call, so it waits if she is already talking."""
        from sim.scene import COSTUME_NOTES
        note = COSTUME_NOTES.get(str(costume or "").upper(), "") or ""
        if self.director:
            self.director.set_outfit(note)
        if self.delivery.busy() or self.store.unread_user_messages():
            logger.log("[director] the outfit notice waits: she is already talking")
            return False
        scene = self.director.current or {}
        return self.force_scene_turn(scene, self._outfit_urge(note))

    def react_to_scene(self, bg):
        """He changed the background by hand. Put its place in her situation
        and let her notice where they are."""
        from sim.scene import PLACE_NOTES
        group = str(bg or "").strip().upper()[:4]
        place = next((name for name, image in self.scene.places.items()
                      if str(image).upper().startswith(group)), "")
        note = str(PLACE_NOTES.get(place) or place.replace("_", " ")).strip()
        if not note:
            logger.log(f"[director] the picked background has no place: {bg}")
            return False
        if self.director:
            self.director.set_place(note)
        if self.delivery.busy() or self.store.unread_user_messages():
            logger.log("[director] the place notice waits: she is already talking")
            return False
        scene = self.director.current or {}
        return self.force_scene_turn(scene, self._place_urge(note), intent_kind="place_notice")

    def force_scene_turn(self, scene, urge, intent_kind="scene"):
        """She opens a scene the console started.

        Modelled on `maybe_arrival`, not `maybe_impulse`: a player-driven
        character never writes first and `maybe_impulse` returns at once for her
        (`character.existence.player_driven`). The console's approval is the
        decision, so the impulse gate and its roll do not get a vote. Returns
        whether anything went."""
        if self.delivery.busy() or self.store.unread_user_messages():
            logger.log("[director] the scene opening waits: she is already talking")
            return False
        try:
            bubbles, voice = self.persona.generate(scene, self.latest_digest(), [],
                                                   impulse_reason=urge, intent_kind=intent_kind)
        except Exception as e:
            logger.log(f"[director] the scene opening was not written: {type(e).__name__}: {e}")
            return False
        if not bubbles:
            return False
        aside, lines = self.stage_voice(voice, bubbles, scene, True)
        self.delivery.send_bubbles(bubbles, self_started=True, voice=aside, voice_lines=lines)
        logger.log("[director] the scene opened on her: %s" % " // ".join(b[:60] for b in bubbles))
        return True

    def apply_director_scene(self, proposal):
        """He approved the console's proposal: start the scene.

        A new scene thread is created and made active, so the transcript and the
        backlog are its own; the scene is written through the one writer, so it
        is a real scene of her day; the plan tick is held; the stage draws it at
        once; and she opens it. Returns what was started, or None."""
        if not getattr(self.stage_manager, "enabled", False):
            return None
        proposal = proposal or {}
        now = self.clock.now_ts()
        scene_id = f"scene_{int(now)}"
        title = str(proposal.get("text") or "a directed scene")
        self.store.register_scene(scene_id, title, created_ts=now)
        self.store.set_active_scene(scene_id)
        # the staging the console resolved
        self.scene.request = {"bg": proposal.get("bg"), "camera": proposal.get("camera"),
                              "transition": proposal.get("transition"), "mood": proposal.get("mood"),
                              "place": proposal.get("place"), "bgm": proposal.get("bgm"),
                              "interjection": proposal.get("interjection"),
                              "face_index": proposal.get("face_index"),
                              "outfit": proposal.get("outfit")}
        blk = None
        try:
            sch = self.schedule or {}
            from sim import schedule as sched
            if sch.get("blocks"):
                blk = sched.block_at(sch["blocks"], self.clock.now())
        except Exception:
            blk = None
        if not blk:
            blk = {"start": "00:00", "end": "24:00", "activity": "her day",
                   "location": "here", "with": "alone", "phone_access": "free"}
        # the outfit note goes into the scene, so she knows what she is wearing
        # in the moment (`scene_brief`) and it is on the record afterwards
        from sim.scene import COSTUME_NOTES
        proposal = dict(proposal)
        proposal["outfit_note"] = COSTUME_NOTES.get(str(proposal.get("outfit") or "").upper(), "")
        scene = self.director.apply_directive(proposal, blk, scene_id)
        # the stage draws it now, before the reply's staging pass runs
        try:
            if hasattr(self.tg, "set_scene") and proposal.get("bg"):
                self.tg.set_scene(proposal.get("bg"), directed=True)
        except Exception as e:
            logger.log(f"[director] the stage did not take the background: {type(e).__name__}: {e}")
        # the outfit, on the same frame: her sprite is re-resolved in it
        try:
            if hasattr(self.tg, "set_costume"):
                self.tg.set_costume(proposal.get("outfit"), redraw=False)
        except Exception as e:
            logger.log(f"[director] the outfit was not set: {type(e).__name__}: {e}")
        self.force_scene_turn(scene, self._scene_urge(scene, proposal.get("place")))
        return {"scene_id": scene_id, "title": title, "scene": scene}

    def clear_director_scene(self):
        """Hand the stage back to the main thread. The directed scene stays on
        the record as the scene that happened; the plan resumes on the next tick."""
        self.director.clear_directive()
        self.store.set_active_scene("main")
        # her outfit goes back to the default with the scene
        try:
            if hasattr(self.tg, "set_costume"):
                self.tg.set_costume("")
        except Exception as e:
            logger.log(f"[director] the outfit was not reset: {type(e).__name__}: {e}")
        return {"active": "main"}

    def speak_now(self, text, mid):
        """He tapped a line in the backlog to hear it: locate the clip already
        on disk for it and hand back the URL the stage can play.

        The line was voiced when it was said, so the file is in the TTS cache
        (or the recorded corpus) and locating it is a cache hit; only a line
        that was never voiced is synthesised, which is the one to two seconds it
        always was. The URL is returned rather than attached to a turn: a
        backlog tap is not a bubble of a reply, and `audio_by_turn` prunes its
        oldest keys, which dropped the clip the tap had just filed there
        (2026-09-17). Returns the URL, or '' when there is nothing to play."""
        if not self.tts:
            return ""
        path = self.tts.render_wait(text)
        if not path:
            return ""
        return self.tg.voice_url(path)

    def _touch_gauge_nudge(self, deltas, reason="touch"):
        """A tap on her sprite (`channels/vn_bot.py` handle_touch) moves a
        gauge or two by a small fixed amount. This bypasses `state.apply()`
        on purpose: apply()'s habituation and diminishing returns are tuned
        for the model's own moves, and a touch nudge should land the same
        whether it is the first pat today or the tenth. affection and mood
        have model_may_move: false in the schema, but code is still allowed
        to move them a little here. Logs a gauge snapshot via add_state so
        the gauge chart picks up the change."""
        from sim.state import clamp
        for k, d in deltas.items():
            if k in self.state.gauges:
                self.state.gauges[k] = clamp(self.state.gauges[k] + d)
        try:
            import time
            self.store.add_state(time.time(), self.clock.date_str(), dict(self.state.gauges), reason)
        except Exception:
            pass

    def write_him_first(self, scene, digest, hint_from_her="", force_hint=None, media=None):
        """The path a decision to write to him first runs down, whoever made
        it: the impulse function's yes, her own `text_him` pick, or a discharge.
        Returns whether anything actually went.

        `hint_from_her` is her own account of what she is reaching for, given a
        moment ago when she was handed the moment; it is a seed for the call
        that writes her words and never words to send."""
        # She decided not to answer him. She did not decide to stop wanting
        # things, and a silence he has not noticed is worse than no silence at
        # all. Her own impulse overrides it -- it just has to clear her resolve,
        # which erodes on its own and much faster while he is not even there.
        try:
            held = self.withholding.live() if not force_hint else None
            if held:
                need = self.withholding.resolve()
                score = self.impulse.last_score if hasattr(self.impulse, "last_score") else None
                if need > 0 and score is not None and score < need:
                    logger.log(f"[withhold] she still means it (score {score:.0f} under resolve {need:.0f}, "
                               f"unnoticed {self.withholding.unnoticed_hours():.1f}h)")
                    return False
                self.withholding.cave()
                logger.log("[withhold] she broke her own silence first")
        except Exception as e:
            logger.log(f"[withhold] resolve not checked: {type(e).__name__}: {e}")

        # Her own account of why she is writing comes first: she was handed the
        # moment and said what she was reaching for, and a hint code assembled
        # afterwards would be answering a question she has already answered.
        hint = hint_from_her or scene.get("share_hint") or ""
        if not hint and self.config.goals.enabled:
            # the thing she keeps waking up meaning to do and keeps not doing
            hint = self.goals.intent_hint()
            if hint:
                logger.log(f"[goals] what she is after: {hint[:90]}")
        # Nothing else in the system ever makes her raise a thing. Every outlet
        # for `unsaid` was private -- the diary, an X post -- so a thread about
        # him that she has not asked about just aged and went dormant: one
        # thread had resolved in three days while "why he really went quiet for
        # three months" sat there unasked. Once it has built enough pressure it
        # becomes what her next message is about, ahead of anything lighter.
        pressing = None
        if self.records and not hint_from_her:
            try:
                pressing = self.records.pressing_thread(self.state.gauges.get("unsaid", 0), bars=self.ick.bars)
            except Exception:
                pressing = None
        if pressing:
            hint = f"the thing she keeps not saying to him: {pressing['text']}"
            logger.log(f"[threads] it has waited long enough: {pressing['text'][:90]}")
        # and above all of it, the thing she is not allowed to know. A sealed
        # discovery could never become a message at all, so the biggest fact she
        # held about him did nothing for a month and then cooled into a joke.
        # This does not let her say it: it lets her go at the subject sideways,
        # and the prompt's one unbreakable rule is that she never says how she
        # knows.
        reach = None
        try:
            sealed, why = self.approach.due(scene) if not hint_from_her else (None, "she said what she is after")
            if sealed:
                out = self.approach.write(sealed, scene)
                if out:
                    reach = (sealed, out)
                    _t = lang.say(self.config)
                    hint = _t(f"something you want to get at without ever touching how you know it: "
                              f"{out['subject']} -- coming at it {out['angle']}. The words are yours.",
                              f"どうやって知ったかには一切触れずに近づきたいこと: "
                              f"{out['subject']}——{out['angle']}という角度で。言葉は自分のもの。")
        except Exception as e:
            logger.log(f"[approach] not attempted: {type(e).__name__}: {e}")
        if force_hint:
            hint, reach = force_hint, None
        kind, about = self.intent.decide(scene, self.silent_hours(), hint)
        if kind == "nothing":
            self.impulse.fired()  # she opened the chat and put the phone down; the urge is spent for now
            return False
        reason = Intent.reason_line(kind, about, hint, self.config)
        # She has decided to write first. If he is reading a game, the
        # account of where he has got to is paid for HERE, at the moment
        # it is about to be used, rather than on a clock of its own.
        self._program_call("before_reply", "she is writing first")
        bubbles, voice = self.persona.generate(scene, digest, [], impulse_reason=reason, intent_kind=kind)
        if bubbles:
            self.impulse.fired(sent=True)
            # only now. `note` discharges the thing and takes the pressure off
            # `unsaid`, and recording that before anything has actually gone is
            # how the X post came to have a count, a relief and an event for a
            # post nobody ever saw (2026-08-21). If the persona produced
            # nothing, she thought about how to put it and did not send it.
            if reach:
                self.approach.note(*reach)
            aside, lines = self.stage_voice(voice, bubbles, scene, True)
            self.delivery.send_bubbles(bubbles, self_started=True, voice=aside, voice_lines=lines,
                                       media=media or "")
            # she has reached out while an episode of his was the thing in the
            # room; whatever she actually said, it does not get to be the
            # reason a second time
            if self.watching:
                self.watching.note_spoken()
            self._program_call("after_self_start", bubbles)
            self.send_pending_sticker()
            if media:
                self._program_call("sent_with_media", media, bubbles)
            self.foresee_after(bubbles, kind or "self-started")
            qid = getattr(self.intent, "last_question", "")
            if qid:
                try:
                    self.wonder.note_asked(qid, " ".join(bubbles)[:200])
                except Exception as e:
                    logger.log(f"[wonder] not marked asked: {type(e).__name__}: {e}")
        elif reach:
            logger.log("[approach] she worked out how to put it and then did not send anything")
        return bool(bubbles)

    def recover_lost_reply(self):
        """A reply that was generated but never sent. `maybe_reply` marks his
        message read before it generates, and delivery writes her bubbles to the
        store only once they have actually gone, so a stop in between leaves him
        read and unanswered with no trace. Being left on read is the one thing
        this system must never do by accident, so his message goes back in the
        queue. Once, at boot, and only while it is still recent."""
        try:
            last = self.store.last_message("user")
            if not last or not last.get("read_ts"):
                return
            age_h = (self.clock.now_ts() - last["ts"]) / 3600.0
            if age_h > self.config.delivery.recover_lost_reply_hours:
                return
            after = [m for m in self.store.recent_messages(20)
                     if m["role"] == "assistant" and m["ts"] > last["ts"]]
            if after:
                return
            # Read and left ON PURPOSE is not a lost reply. A `silence` she
            # decided about this message consumed it; three restarts on
            # 2026-08-26 each put "do you feel alive" back in her queue and
            # she would have answered a thing she had chosen not to.
            wh = self.store.get("withholding") or {}
            if wh.get("kind") == "silence" and float(wh.get("ts", 0)) >= float(last["ts"]):
                if not last.get("read_ts"):
                    self.store.mark_read(last["id"], float(wh["ts"]))
                logger.log(f"[reply] his last message is unanswered because she chose silence "
                           f"({age_h * 60:.0f}m ago); leaving it")
                return
            self.store.unmark_read(last["id"])
            logger.log(f"[reply] his last message was read and never answered "
                       f"({age_h * 60:.0f}m ago); the reply was lost in flight, putting it back")
        except Exception as e:
            logger.log(f"[reply] lost-reply check failed: {type(e).__name__}: {e}")

    def maybe_afterthought(self):
        """The bit she thinks of straight after she has already sent it: what she
        actually meant, the correction, wanting it back, or poking him because her
        own message sitting there unanswered is unbearable. Checked every pass
        rather than on the director         tick, because twelve minutes is inside one
        tick and the whole point is that it lands while the first one is still
        warm. One chance per message, decided once."""
        # a player-driven character never follows up on her own: the visual
        # novel has no message of hers to correct or to poke him about
        if bool(getattr(self.config.character.existence, "player_driven", False)):
            return
        c = self.config.afterthought
        if not c.enabled or not self.schedule or self.delivery.busy() or self.store.unread_user_messages():
            return
        last = self.store.last_message("assistant")
        if not last:
            return
        age = self.clock.now_ts() - last["ts"]
        if age < c.min_seconds or age > c.ignored_window_minutes * 60:
            return
        today = self.clock.date_str()
        counts = self.store.get("afterthought_counts", {})
        if counts.get(today, 0) >= c.max_per_day:
            return
        # The same gate every self-started message goes through (sim/initiative.py).
        # Without it this path had no idea what her last message had got back:
        # on 2026-09-04 an afterthought followed a self-started message of hers
        # by fifty-seven seconds (00:43:31, then 00:44:28), and each one became
        # the message the next afterthought rolled on.
        if self.impulse.initiative.hold_reason(self.impulse.unanswered_streak(), self.impulse.read_state()):
            return
        factor = c.phone_access_factor.get(self.phone_access(), 0.0)
        if factor <= 0:
            return
        ignored = False
        if self.receipts:
            st = self.receipts.status()
            # read a minute ago is him typing, not him vanishing; only a read
            # that has sat for `read_silence_minutes` is a silence she may name
            if st and st.get("state") == "read":
                read_ts = st.get("read_ts") or last["ts"]
                ignored = (self.clock.now_ts() - read_ts) >= c.read_silence_minutes * 60
        # two chances, each decided once before its roll. The warm one lands
        # while the send is still warm (~1 minute in) -- which meant `ignored`
        # could NEVER apply: a read has to sit read_silence_minutes (4) before
        # it is a vanish, and the one roll happened at 45-50 seconds, so "he
        # read it and said nothing" -- the strongest reason a girl pokes --
        # carried zero weight in every roll on the record. The late one is the
        # re-roll when the situation has actually changed: his read has sat
        # unanswered, any time up to ignored_window_minutes.
        if self.store.get("afterthought_for_ts", 0) != last["ts"] and age <= c.window_minutes * 60:
            stage_key = "afterthought_for_ts"
        elif ignored and self.store.get("afterthought_ignored_ts", 0) != last["ts"]:
            stage_key = "afterthought_ignored_ts"
        else:
            return
        g = self.state.gauges
        p = c.base_probability
        for name, w in (("awkwardness", c.awkward_weight), ("unsaid", c.unsaid_weight),
                        ("validation_craving", c.craving_weight)):
            p += max(0.0, g.get(name, 0) - self.state._baseline(name)) / 100.0 * w
        if ignored:
            p += c.read_ignored_bonus
        p = max(0.0, min(c.max_probability, p * factor))
        self.store.set(stage_key, last["ts"])
        if random.random() > p:
            logger.log(f"[afterthought] let it lie (p {p:.2f}{', read and ignored' if ignored else ''})")
            return
        scene = self.director.current or {}
        mins = max(1, int(age / 60))
        # Addressed to her, so it is in her language: it goes into her
        # situation block and again into the last line of the prompt. It was
        # English for everybody until 2026-09-07, when both residents read
        # their reason for writing a second message in a language they do not
        # write in. The urge path beside this one (`Intent.reason_line`) had
        # been through the arm since 2026-09-05. The English wording is
        # unchanged to the byte, and the joiner is paired too: Japanese
        # sentences end on a full stop and take no space after it.
        _t = lang.say(self.config)
        why = [_t(f"you sent that {mins} minute(s) ago and he has not answered.",
                  f"そのメッセージを送ってから{mins}分、彼からの返事はない。")]
        if ignored:
            why.append(_t("he has read it and said nothing.", "彼は読んだのに、何も言ってこない。"))
        if g.get("awkwardness", 0) >= 40:
            why.append(_t("you are not sure it came out right.", "うまく言えたかどうか自信がない。"))
        cue = (_t("this is not a new conversation. ", "新しい話を始めるのではない。")
               + _t(" ", "").join(why)
               + _t(" this is the bit that came to you straight after sending: what you actually meant, or a"
                    " correction, or wanting to take it back, or just poking him because your own message"
                    " sitting there is unbearable. one or two short bubbles at most, and do not say again"
                    " what you already said.",
                    "これは送ったすぐあとに出てきたぶん。"
                    "本当はこう言いたかったという言い直しか、訂正か、取り消したい気持ちか、"
                    "返事のない自分のメッセージがそこにあるのが耐えられなくて突くだけか。"
                    "短い吹き出しを一つか二つまで。すでに言ったことをもう一度言わない。"))
        bubbles, voice = self.persona.generate(scene, self.latest_digest(), [], impulse_reason=cue, intent_kind="afterthought")
        bubbles = bubbles[: c.max_bubbles]
        # The cue says "do not say again what you already said" and at 11:06 it
        # said it again anyway, almost word for word: "so you're saying my
        # english is fine and i should stop worrying about it" a minute after
        # "so you're saying i'm fine and i should stop worrying". A prompt rule
        # nothing checks is a suggestion. This path had its own check against
        # her last six messages until 2026-09-03, when the same fault turned up
        # on the ordinary reply, which had none -- so the check moved to where
        # every burst is built (`Persona._drop_already_sent`, against her last
        # `delivery.no_repeat_recent`) and this one came out. One rule, one
        # place: two of them drift.
        if not bubbles:
            logger.log("[afterthought] it was the same thing again; let it lie")
            return
        self.store.bump_today("afterthought_counts", today)
        self.impulse.initiative.note_sent(self.impulse.unanswered_streak())
        logger.log(f"[afterthought] (p {p:.2f}, {mins}m after) " + " // ".join(b[:70] for b in bubbles))
        aside, lines = self.stage_voice(voice, bubbles, scene, True)
        self.delivery.send_bubbles(bubbles, self_started=True, voice=aside, voice_lines=lines)
        self.send_pending_sticker()

    # When she has decided to answer him: the mode (`free` at her desk,
    # `glance` under it), the noticing and composing delays rolled once into
    # one absolute due time, and how present he was when she started. It is in
    # the save because it used to be on the App alone, and a stop threw the
    # whole decision away and rolled a new one: on 2026-09-03 a plan due in
    # 4.4 minutes became, across a restart ninety seconds later, one due in
    # 14.4, and his message waited that much longer for no reason of hers. The
    # due time is absolute, so a restart does not restart it. A plan older than
    # `delivery.recover_lost_reply_hours` is stale and dropped rather than
    # fired late -- the same window `recover_lost_reply` uses for a message
    # read and never answered.
    @property
    def reply_plan(self):
        p = self.store.get("reply_plan", None)
        if not isinstance(p, dict):
            return None
        if (self.clock.now_ts() - float(p.get("set_ts") or 0)) > self.config.delivery.recover_lost_reply_hours * 3600:
            self.store.set("reply_plan", None)
            return None
        return p

    @reply_plan.setter
    def reply_plan(self, v):
        if isinstance(v, dict):
            v = dict(v)
            v.setdefault("set_ts", self.clock.now_ts())
        else:
            v = None
        self.store.set("reply_plan", v)

    def maybe_reply(self):
        unread = self.store.unread_user_messages()
        if self.replay:
            if unread and not getattr(self, "_replay_said_unread", False):
                self._replay_said_unread = True
                logger.log(f"[replay] {len(unread)} unread from him wait for the live loop; nothing is answered from inside the hole")
            return
        if not unread or self.delivery.busy():
            return
        access = self.phone_access()
        d = self.config.delivery
        now = self.clock.now_ts()
        if access == "none":
            self.reply_plan = None
            return
        # Is she going to answer this at all. Everything above is whether she
        # CAN; this is the only place she decides whether she WILL, and it runs
        # after access so it can never be what keeps her from a message she
        # simply had no phone for.
        try:
            held = self.withholding.live()
            if held is None:
                ok, why = self.withholding.due(unread)
                if ok:
                    logger.log(f"[withhold] something in her does not want to answer ({why})")
                    held = self.withholding.decide(unread, self.director.current)
            if held:
                if held.get("kind") == "silence":
                    # the loud one: he sees READ and nothing after it
                    for m in unread:
                        if not m.get("read_ts"):
                            self.store.mark_read(m["id"], now)
                self.reply_plan = None
                return
        except Exception as e:
            logger.log(f"[withhold] not decided: {type(e).__name__}: {e}")
        # She left his message where it was and said so; the window she left it
        # for has run out, so she is asked about it again rather than answering
        # it on a timer she never set.
        _plan = self.reply_plan
        if _plan and _plan.get("ask_again_ts") and now >= float(_plan["ask_again_ts"]):
            self.reply_plan = None
        # His message has arrived and nothing has decided what to do about it
        # yet. She is asked -- answer it, answer it at an hour she names, or
        # leave it where it is -- and the noticing and composing timers below
        # are what decides when she is not (sim/pick.py).
        if self.reply_plan is None:
            _d = self.phone_moment("inbound", self.director.current or {},
                                   self.latest_digest(),
                                   None, unread)
            if _d is not None and _d["name"] in ("reply_now", "reply_later", "leave_it"):
                self.reply_plan = self._plan_from_pick(_d, access, now)
        if self.reply_plan is None or self.reply_plan["mode"] != access:
            # Noticing and composing are two different things and used to be
            # one number scaled by one factor. NOTICING is presence -- whether
            # the phone is in her hand -- and in an exchange it is seconds.
            # COMPOSING is her, and it is NOT capped: tension and shame make a
            # person slower precisely when the other one is there watching them
            # type. Capping it deleted the most human thing she does.
            f = self.state.compose_factor()
            live = False
            try:
                live = self.rhythm.in_exchange()
                nlo, nhi = self.rhythm.noticing_seconds(access)
            except Exception as e:
                logger.log(f"[rhythm] presence not read: {type(e).__name__}: {e}")
                nlo, nhi = d.read_delay_free_seconds
            if access == "free":
                lo, hi = nlo, nhi
                # a message that arrived while she had no phone is read now, not retroactively;
                # how long she takes depends on how she is (tension, mood, craving, energy)
                self.reply_plan = {"mode": "free", "presence": self.rhythm.presence(),
                                   "due_ts": max(unread[-1]["ts"], now) + random.uniform(lo, hi)
                                             + random.uniform(*d.compose_seconds) * f}
            else:
                # eager: likelier to answer under the desk; cool or tired: less
                # a live exchange makes her answer under the desk when she
                # otherwise would not
                gp = d.glance_reply_probability * (self.config.rhythm.glance_boost if live else 1.0)
                ceiling = self.config.rhythm.glance_ceiling if live else 0.95
                # `glance` is her in class, at dinner, with people. However
                # live the exchange is, it does not get to own her: past this
                # ceiling she would be answering him through everything, which
                # is the opposite of the whole design. Her day wins the tie.
                if random.random() < max(0.05, min(ceiling, gp / f)):
                    lo, hi = nlo, nhi
                    self.reply_plan = {"mode": "glance", "presence": self.rhythm.presence(),
                                       "due_ts": now + random.uniform(lo, hi)
                                                 + random.uniform(*d.compose_seconds) * f}
                else:
                    # she saw the notification but is not going to answer under the desk
                    self.reply_plan = {"mode": "glance", "due_ts": None}
            logger.log(f"[reply] plan {self.reply_plan['mode']} (x{f:.2f}): " + (f"in {(self.reply_plan['due_ts'] - now) / 60:.1f} min" if self.reply_plan["due_ts"] else "waiting for a free moment"))
        if self.reply_plan["due_ts"] is None or now < self.reply_plan["due_ts"]:
            # He may have gone while she was getting to it. A person about to
            # fire back who notices the room has emptied slows down. The plan
            # used to be made once and never revisited, so she answered an empty
            # room in fifteen seconds.
            try:
                plan = self.reply_plan
                was = float(plan.get("presence") or 0)
                # ...unless the hour is HERS. She was asked what to do about
                # his message and said now, or said an hour; moving it because
                # a statistic about his presence changed would be code
                # answering a question she has already answered.
                if plan.get("picked"):
                    was = 0.0
                if was >= self.config.rhythm.enter_above:
                    p = self.rhythm.presence()
                    if p < self.config.rhythm.stay_above:
                        plan["presence"] = p
                        plan["due_ts"] += random.uniform(*self.config.rhythm.he_left_extra_seconds)
                        self.reply_plan = plan
                        logger.log(f"[rhythm] he went quiet while she was answering "
                                   f"({was:.2f} -> {p:.2f}); she is not rushing now")
            except Exception:
                pass
            return
        for m in unread:
            self.store.mark_read(m["id"], now)
        text = "\n".join(m["text"] for m in unread)
        # his words are about to be answered: the machine writes its buffer
        # first, so the look inside this tick sees what he did a minute ago
        self.request_flush()
        scene, digest = self.tick(force=True, reading_text=text)
        just_read = None
        if self.config.notes.enabled:
            f = self.notes.find_mentioned(text)
            if f:
                just_read = self.notes.read(f, ("he mentioned it just now", "いま彼が話に出したから"), scene)
        if just_read is None and self.sight:
            just_read = self.sight.fresh_note()
        looked = self.lookup.take() if self.lookup else None
        recalled = self.recall.take() if self.recall else None
        # What he says is the only channel where a belief can be borne out as
        # well as broken, and the only one where what it costs her is something
        # she could actually raise with him. A thing she looked up because he
        # named it goes in as the same moment, not a second one.
        learned, src = text, "told"
        extra = []
        if looked:
            src = "lookup"
            extra.append(f"she looked up '{looked['term']}': {looked['gist']}")
        if just_read:
            extra.append(f"she opened his note '{just_read['basename']}': {just_read['takeaway']}")
        self.assess_learned(learned, source=src, context="; ".join(extra), min_chars=True)
        # and the same moment on the other side: his message is read and
        # her answer is about to be built
        self._program_call("before_reply", "answering him")
        bubbles, voice = self.persona.generate(scene, digest, unread, just_read=just_read, looked_up=looked, recalled=recalled)
        self.reply_plan = None
        if bubbles:
            self.store.set("reply_retries", {})
            aside, lines = self.stage_voice(voice, bubbles, scene, False)
            self.delivery.send_bubbles(bubbles, self_started=False, voice=aside, voice_lines=lines)
            # answering credits the ledger his message debited. Here rather
            # than in delivery, which sends bubble by bubble and would count
            # one reply three times.
            if self.primitives:
                try:
                    self.primitives.she_answered(self.state._him_key() or "him", bubbles)
                except Exception as e:
                    logger.log(f"[primitives] her reply not counted: {type(e).__name__}: {e}")
                self.note_disclosure(bubbles)
            self.send_pending_sticker()
            self.foresee_after(bubbles, "reply")
            try:
                self.wonder.voiced(bubbles)
            except Exception as e:
                logger.log(f"[wonder] voiced check failed: {type(e).__name__}: {e}")
        else:
            # Nothing came back. His message is already marked read, so leaving it
            # here is her having read him and said nothing, permanently. Put it
            # back rather than let that stand.
            reason = (getattr(self.llm, "last_reasoning", "") or "").strip()
            wh = getattr(self, "withholding", None)
            if reason and wh and self.config.withholding.enabled:
                last = [ln.strip() for ln in reason.splitlines() if ln.strip()][-1]
                if wh.hold_from_silence(last[:300]):
                    return
            key = str(unread[-1]["id"])
            tries = self.store.get("reply_retries", {})
            count = int(tries.get(key, 0)) + 1
            self.store.set("reply_retries", {key: count})
            # two different things arrive here as an empty list, and the log
            # has to say which: the model wrote nothing, or everything it
            # wrote was something she had already sent him and the guard took
            # it out (`Persona._drop_already_sent`)
            why = ("her whole reply was what she had already said"
                   if getattr(self.persona, "last_all_repeats", False) else "nothing came back")
            if count <= self.config.delivery.reply_retries:
                for m in unread:
                    self.store.unmark_read(m["id"])
                logger.log(f"[reply] {why}; his message goes back in the queue (attempt {count})")
            else:
                logger.log(f"[reply] {why} after {count} attempts; leaving it read so it does not loop")

    def stage_voice(self, voice, bubbles, scene, self_started):
        """The stage's own voicing for one reply.

        When the stage's voice toggle is on, every bubble is spoken as it is
        sent -- one clip per line, attached to that line, so the reader hears
        each as he advances (`persona/delivery.py:_voice_bubble`). The aside
        voice note is not also sent then: two voices over one reply is not
        something a person does, and her lines are what the stage is for. Off,
        nothing changes and the aside path is exactly as it was.

        Returns (aside, voice_lines); voice_lines is None when the stage is not
        voicing, and the caller passes it straight through to `send_bubbles`."""
        if bool(getattr(self, "_vn_voice_auto", False)) and self.tts:
            return "", list(bubbles)
        return (self.voice_gate(self.ensure_voice(voice, bubbles, scene), scene, self_started),
                None)

    def ensure_voice(self, voice, bubbles, scene):
        """Every reply speaks: if the persona did not write a [voice] line, the voice model does."""
        if not getattr(self.config.tts, "aside_from_persona", True):
            # a character who is not asked for an aside: whatever she wrote in
            # brackets was stripped from the text and stops here
            if voice:
                logger.log(f"[voice] an aside she was not asked for, dropped: {voice[:50]!r}")
            voice = ""
        if voice or not self.tts or not self.config.tts.enabled:
            return voice
        # `tts.always` asks the voice role for a line on every reply; the
        # stage's own auto-voice toggle asks for one the same way, and is the
        # only reason this runs for a character whose config says `always`
        # false. Off, nothing is synthesised and nothing is spent.
        if not self.config.tts.always and not bool(getattr(self, "_vn_voice_auto", False)):
            return voice
        return self.persona.voice_for(bubbles, scene)

    def send_pending_sticker(self):
        """The sticker she put in a reply, sent after the words.

        His rule (2026-08-27): a sticker is how she expresses a mood, hers to
        place and not his, and putting one down teaches the store that this
        picture is how SHE says that. It goes after the bubbles because it is
        the beat at the end, the way a LINE sticker is."""
        want = self.store.get("pending_sticker", "")
        if not want:
            return
        self.store.set("pending_sticker", "")
        if not getattr(self, "reactions", None):
            return
        try:
            self.reactions.chosen(want, why="she put it in a reply")
        except Exception as e:
            logger.log(f"[sticker] not sent: {type(e).__name__}: {e}")

    def voice_gate(self, voice, scene, self_started):
        """Decides whether a voice line she wrote actually gets spoken."""
        if not voice or not self.tts:
            return ""
        t = self.config.tts
        why = ""
        if self_started and not t.with_self_started:
            why = "self-started"
        elif t.require_alone and (not scene or scene.get("phone_access") != "free"):
            why = "not alone"
        else:
            now = self.clock.now_ts()
            last = self.store.get("voice_last_ts", 0)
            counts = self.store.get("voice_counts", {})
            today = self.clock.date_str()
            if now - last < t.cooldown_minutes * 60:
                why = "cooldown"
            elif counts.get(today, 0) >= t.max_per_day:
                why = "daily cap"
            else:
                self.store.bump_today("voice_counts", today)
                self.store.set("voice_last_ts", now)
                self.store.add_event(now, today, "voice", voice, 1)
        if why:
            logger.log(f"[voice] held ({why}): {voice}")
            return ""
        return voice

    def status(self):
        if time.time() - self.last_status_wall < self.config.logging.console_status_interval_seconds:
            return
        self.last_status_wall = time.time()
        s = self.director.current
        where = f"{s['location']} / {s['activity']}" if s else "(no scene)"
        # The scene is the last one the director wrote, and it does not tick
        # while she sleeps. Printed in the present tense it kept asserting
        # "eyes closed but not asleep" for the three hours after she actually
        # went under, because that was true at 01:53 when the coast began.
        if s:
            age = int((self.clock.now_ts() - s["ts"]) / 60)
            if self.director.sleeping():
                pass          # the scene is the night; it is meant to stand
            elif self.coasting_block:
                where = (f"asleep ({self.coasting_block['start']}-{self.coasting_block['end']})"
                         f" | last scene {age}m ago: {where}")
            elif not self.director.scene_fresh():
                where += f" (scene {age}m old)"
        net = "" if not netwatch.WATCH.offline() else f" | NETWORK {netwatch.WATCH.status()}"
        logger.log(f"[status] {self.clock.both()} | phone {self.phone_access()} | {where} | {self.state.gauge_line()}{net}")

    def maybe_watching(self):
        """Notice an episode he has played and go and read what happens in it.

        Two local files per poll and nothing else on this thread; the fetch
        that follows opens a browser and runs on its own. Deliberately not
        tied to him saying anything -- the whole fault this fixes was that she
        only ever learned about a show when he brought it up."""
        if not self.watching:
            return
        c = self.config.watching
        last = float(getattr(self, "_watching_at", 0) or 0)
        now = self.clock.now_ts()
        if now - last < float(c.poll_minutes) * 60:
            return
        self._watching_at = now
        if self.watching.busy():
            return
        try:
            item = self.watching.poll()
        except Exception as e:
            logger.log(f"[watching] poll failed: {type(e).__name__}")
            return
        if item:
            logger.log(f"[watching] he played {item['title']} ep{item['ep']}; "
                       f"she goes to read what happens in it")
            self.watching.start(item)
            return
        # nothing new: an episode she was told about and never told what is in
        # is read again, once the machine has a page for it or the retry
        # window has passed (`WatchingHim.owed`)
        try:
            owed = self.watching.owed()
        except Exception as e:
            logger.log(f"[watching] the repair pass failed: {type(e).__name__}")
            return
        if owed:
            self.watching.start(owed)

    def _guarded(self, label, fn, *args, **kwargs):
        """One guard for a loop stage that must not take the pass down with
        it: the failure is logged under the stage's tag, by exception type,
        and the loop goes on. Every stage the loop runs bare is one whose
        failure should stop the pass."""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.log(f"[{label}] {type(e).__name__}: {e}")
            return None

    def _situation_tick(self):
        """Where her body is, on the clock: a journey advancing, a line
        stopping under her, the day going into her legs. What happened is an
        event on the record and on the current scene."""
        for e in self.situation.tick(self.director.current, (self.schedule or {}).get("blocks")):
            self.store.add_event(self.clock.now_ts(), self.clock.date_str(), e["kind"], e["text"], e["salience"])
            logger.log(f"[where] s{e['salience']}: {e['text'][:140]}")
            cur = self.director.current
            if cur is not None:
                cur["events"] = list(cur.get("events", [])) + [{"text": e["text"], "salience": e["salience"]}]

    def _appraise_night(self, key):
        """The day's messages read back once, now that the day is over; keyed
        to the night so a restart does not read it twice."""
        ok, why = self.appraisal.due(key)
        if ok:
            logger.log(f"[affection] reading the day back: {why}")
            self.appraisal.run(key)
        elif why != "off":
            logger.log(f"[affection] the day was not worth reading: {why}")

    def ordinary_tick(self):
        """One ordinary pass of her beat: the director tick, and everything
        that reads the scene it wrote -- what she pulls on, a spiral, a
        rupture aging, whether she writes first, her diary, the morning, what
        she is looking forward to, a reflection.

        The loop runs this when the director is due, and `/idle` runs the same
        method, so what a forced tick does can never drift from what the real
        one does. Returns the scene."""
        woke_now = False
        if self.coasting_block is not None:
            self.coasting_block = None
            self.woke = True
            woke_now = True
        # she may be about to write first out of this tick, so
        # the machine writes its buffer before the look inside it
        self.request_flush()
        scene, digest = self.tick()
        self.note_pull()
        self.maybe_spiral(scene)
        if self.config.rupture.enabled:
            # her taking a repair of his counts too, and that
            # only ever shows up as a message of hers
            self.rupture_settled(self._guarded("rupture", self.ruptures.settle, "either"))
            self._guarded("rupture", self.ruptures.age)
        self.maybe_revise()
        self.maybe_impulse(scene, digest)
        self.maybe_discharge(scene, digest)
        # her snoop, a photograph, the account: hers
        self._program_call("after_tick", scene, digest)
        self._guarded("reaction", self.reactions.tick)
        ok, why = self.diary.may_write(scene)
        if ok and not self.store.unread_user_messages() and not self.delivery.busy():
            self.diary.write(scene, reason=f"unsaid at {int(self.state.gauges.get('unsaid', 0))}; " + (scene.get("activity") or "a quiet moment"))
        # Waking was a transition in memory (coasting -> ticking)
        # and a restart across her waking hour lost it, so she got
        # no morning thought and no goals for the whole day.
        # morning() is idempotent by date; the window is what
        # stops a restore in the afternoon inventing a morning.
        if woke_now or self._morning_owed():
            self.outlook.morning(self.schedule)
            self.note_goals()
        if self.outlook.experience_due(scene):
            self.outlook.experience(scene)
        ok, why = self.outlook.anticipation_due(scene)
        if ok:
            self.outlook.anticipate(scene, why)
        ok, why, subject = self.reflection.due(scene)
        if ok and not self.store.unread_user_messages() and not self.delivery.busy():
            self.reflection.run(scene, why, subject)
        self._program_call("after_reflection", scene)
        return scene

    def run(self):
        # the seismic feed is a socket on its own thread and the backfill is a
        # couple of HTTP calls; both belong to starting up, not to the first tick
        branch_pending = getattr(self.tg, "branch_pending", lambda: False)
        program_started = False
        if self.replay:
            self.delivery.withhold = "replay"
        elif not branch_pending():
            self._program_call("start")
            program_started = True
        logger.log("[loop] entering")
        # her past as cards for the days the thread already shows, and the
        # vectors of what she knows and remembers: a save from before either
        # gets them once, in the background
        backfill_started = False
        if not branch_pending():
            threading.Thread(target=self._backfill_context, daemon=True).start()
            backfill_started = True
        while True:
            try:
                if branch_pending():
                    self.clock.sleep(0.5)
                    continue
                if not program_started and not self.replay:
                    self._program_call("start")
                    program_started = True
                if not backfill_started:
                    threading.Thread(target=self._backfill_context, daemon=True).start()
                    backfill_started = True
                if self.sim_end_ts and self.clock.now_ts() >= self.sim_end_ts:
                    if self.replay:
                        self._replay_finish()
                        return
                    logger.log("[sim] reached end of run, compiling the day")
                    self.compile(self.clock.date_str())
                    day = self.store.get_day(self.clock.date_str())
                    if day:
                        logger.write_artifact("dry_run_day.txt", day["narrative"])
                        print("\n=== THE DAY ===\n" + day["narrative"] + "\n\n=== SUMMARY ===\n" + day["summary"])
                    return
                # Mid-message, the only thing that matters is whether he cut in.
                # A full pass can take half a minute when it has model calls in
                # it, which is why his message reached the store after her last
                # bubble had already gone out.
                if self.delivery.busy():
                    if self.busy_since is None:
                        self.busy_since = time.time()
                    if (time.time() - self.busy_since) < self.config.delivery.busy_poll_max_seconds:
                        self.poll_inbound()
                        self.clock.sleep(self.config.delivery.busy_poll_seconds)
                        continue
                else:
                    self.busy_since = None
                self.ensure_day()
                self.money.ensure_allowance()
                self.maybe_generate_schedule()
                self.note_goals()
                self._guarded("him", self.him_profile.maybe, self.llm)
                self._program_call("every_pass")
                self.maybe_watching()
                self.poll_inbound()
                self.maybe_arrival(self.director.current or {}, self.latest_digest())
                self.maybe_reply()
                # The impulse is asked on every pass, not only on the director's
                # beat: the tick is twenty minutes apart and a person who wants
                # to say something does not wait for one. `check` is a pure
                # function and free. It is skipped while her own last pick still
                # stands, because one moment has one decider and the backup
                # cannot act over it anyway -- and asking inside the hold rolled
                # the die every five seconds and logged the same refusal.
                if not self.pick.holds():
                    self._guarded("impulse", self.maybe_impulse,
                                  self.director.current or {}, self.latest_digest())
                self.maybe_afterthought()
                # somebody reaches into her day: the beats, an exchange, a
                # stranger -- her world's, and the program's to run
                self._program_call("loop_pass")
                # where her body is, on the clock: a journey advancing, a line
                # stopping under her, the day going into her legs
                self._guarded("where", self._situation_tick)
                # the conversation she is in, one side at a time on the clock;
                # when it ends it is a thing that happened to her
                self._program_call("after_situation")
                # another running character, on her own clock: what has
                # arrived is read every pass, and whether she answers is her
                # phone access, her caps and her hours (sim/peers.py)
                self._guarded("peer", self.peers.tick, self.director.current)
                asleep = self.director.asleep_block(self.schedule) if self.config.director.coast_when_asleep else None
                if asleep:
                    # she is asleep by the schedule: no director, no state model.
                    # The gauges still drift; the snoop still gets its chance
                    # (lying awake is how it starts) and forces a scene if it fires.
                    if self.coasting_block is not asleep:
                        self.coasting_block = asleep
                        logger.log(f"[director] coasting through sleep until {asleep['end']}")
                        # She is under. One scene stands for the whole night,
                        # because nothing else will be written until she wakes
                        # and the last waking one ("eyes closed but not
                        # asleep") stayed true on the record for three hours.
                        # Keyed to the night so a restart does not rewrite it.
                        key = f"{self.clock.date_str()}|{asleep['start']}"
                        if self.store.get("sleep_scene_night") != key:
                            last_m = self.store.last_message()
                            why = "she was still messaging him" if last_m and (self.clock.now_ts() - last_m["ts"]) < 1800 else ""
                            if self._guarded("director", self.director.sleep_scene, self.schedule, asleep, reason=why):
                                self.store.set("sleep_scene_night", key)
                        # and the day's messages, read back once now that
                        # the day is over. Keyed to the same night.
                        self._guarded("affection", self._appraise_night, key)
                    self.state.decay(self.silent_hours(), self.world_now())
                    self.note_pull()
                    self.state.save()
                    # some things wake you: the ground moving is the world's,
                    # and the program says whether it did
                    if self._program_call("asleep_pass", asleep, default=False):
                        self.woke = True
                        self.coasting_block = None
                        self.tick(force=True)
                elif netwatch.WATCH.offline() and self.config.network.skip_model_work:
                    # The link is down: a director tick would spend three LLM
                    # retries to produce nothing and fall back to the schedule
                    # block anyway. Let her day coast on the plan until it is
                    # back; the world is deterministic without the model.
                    self.state.decay(self.silent_hours(), self.world_now())
                    self.state.save()
                elif self.director.due(self.schedule) or any(b["salience"] >= self.config.cast.interrupt_salience for b in self.pending_beats):
                    self.ordinary_tick()
                # the feeds, the account's queue, the trains: hers
                self._program_call("late_pass")
                self.withholding.tick()
                self.maybe_foresee_refresh()
                self._guarded("expect", self.expectations.tick)
                self._guarded("foresee", self.foresight.score_risks)
                self._guarded("wonder", self.wonder.maybe, self.director.current or {})
                # did what she just sent him promise him anything
                if not self.delivery.busy():
                    self._guarded("commit", self.commitments.from_chat)
                self._guarded("attach", self.attachment.tick, self.silent_hours())
                self.maybe_shelf_nag()
                self.maybe_compile()
                self.status()
                self.clock.sleep(self.config.telegram.poll_seconds)
            except KeyboardInterrupt:
                logger.log("[loop] interrupted")
                self.shutdown()
                return
            except Exception as e:
                import traceback
                logger.log(f"[loop] error: {e}\n{traceback.format_exc()}")
                time.sleep(5)

    def shutdown(self):
        self._program_call("shutdown")
        if self.collector:
            self.collector.force_flush()
            self.collector.stop()
        if self.sys_monitor:
            self.sys_monitor.stop()
        self.state.save()
        logger.finish()


def _db_from_config(path):
    """The save this character's config names. The lock is keyed to the save,
    and reading it from the command line alone meant a launcher that forgot
    `--db` locked the FIRST character's save while opening its own -- two bots
    on one lock and neither noticing."""
    try:
        with open(path, encoding="utf-8") as f:
            return str((json.load(f).get("logging") or {}).get("db_path", "") or "") or "data/world.db"
    except Exception:
        return "data/world.db"


def main(argv=None, program=""):
    """Run one character. The programs' entry points (`tomoe/run.py`,
    `resident/run.py`) call this after registering their own words; running
    `scail.py` directly is the first character with no words registered until
    the library asks for them."""
    if argv is not None:
        sys.argv = [sys.argv[0]] + list(argv)
    _args = parse_args()
    # One bot, one save file. Two copies ran on 2026-08-19 and Telegram handed
    # the same message to both: her unread queue held it twice and both copies
    # answered. A dry run gets its own lock, keyed to its own db, so it can sit
    # beside the live one exactly as it always could.
    from singleton import Singleton, AlreadyRunning
    _cfg_db = getattr(_args, "db", None) or _db_from_config(getattr(_args, "config", "config.json"))
    _lock = Singleton(_cfg_db + ".lock")
    try:
        _lock.acquire()
    except AlreadyRunning as e:
        print(f"[lock] {e}. Not starting a second one.")
        raise SystemExit(1)
    try:
        app = App(_args)
        if program:
            # after App() has opened the run directory, so it is in session.log
            logger.log(f"[program] {program}: {os.path.basename(sys.argv[0])}")
        app.run()
    finally:
        _lock.release()


if __name__ == "__main__":
    main()
