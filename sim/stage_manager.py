# -*- coding: utf-8 -*-
"""The stage manager: the out-of-character console behind the director button.

He opens it from the stage and talks to it in English. It is not her
and it never speaks as her. It knows the whole machine -- the current scene,
the scene list, the catalogs of places, music, cameras, transitions and moods,
the recent thread and her state -- and it answers questions and proposes
scenes. Only his approval executes one.

Nothing it says reaches her prompt or her record. What reaches them is the
resolved scene, written through the one writer (`sim/director.py:Director`), so
a directed scene is a real scene of her day and a real part of her memory; the
transcript of the scene is its own thread (`store.active_scene`), which is what
lets it be returned to.

This module is the console's core: the context it is handed, the one tool it
may call, and the proposal resolved against the catalogs. The window and the
runtime that execute an approved proposal live elsewhere
(`channels/vn_bot.py`, `scail.py`).

The scope is `docs/2026-09-17_vn_stage_manager_scope.md`.
"""

import os

import logger
from sim.scene import CAMERAS, TRANSITIONS, MOODS, INTERJECTIONS

# The one tool the console may call. Answering a question needs no tool: the
# current scene and the catalogs are in its context already. Proposing is the
# only thing it does that has to be structured, so it is the only schema, and
# `tool_choice` stays `auto` so it can answer in prose when he is only asking.
PROPOSE_SCENE = {
    "type": "function",
    "function": {
        "name": "propose_scene",
        "description": (
            "Propose a scene to start or switch to, for him to approve. "
            "One short sentence of what this scene is and what will happen, in "
            "English, plus the staging chosen from the catalogs. Nothing is "
            "written and no scene is started until he approves it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "One short sentence, in English, of what this scene is and what will happen. Shown to him for approval.",
                },
                "place": {
                    "type": "string",
                    "description": "A place name copied exactly from the places list, or none.",
                },
                "camera": {
                    "type": "string",
                    "description": "One of: " + ", ".join(CAMERAS) + ".",
                },
                "transition": {
                    "type": "string",
                    "description": "One of: " + ", ".join(TRANSITIONS) + ".",
                },
                "mood": {
                    "type": "string",
                    "description": "One of: " + ", ".join(MOODS) + ".",
                },
                "bgm": {
                    "type": "string",
                    "description": "A track id copied exactly from the music list, or none for silence.",
                },
                "interjection": {
                    "type": "string",
                    "enum": sorted(INTERJECTIONS) + ["none"],
                    "description": "Optional one-time vocal action on the scene opening. It is heard in synthesized voice only, never shown in dialogue.",
                },
                "outfit": {
                    "type": "string",
                    "description": "A costume id copied exactly from the outfits list, or none for her default.",
                },
                "face_index": {
                    "type": "string",
                    "description": "Optional expression index 1 to 16 from the face list for the chosen outfit. It appears on the opening line; subsequent lines follow her dialogue emotion.",
                },
            },
            "required": ["text"],
        },
    },
}

TOOLS = [PROPOSE_SCENE]


class StageManager:
    """The console: what it is told, what it may propose, and the chat it keeps."""

    def __init__(self, config, store, clock, llm, director, scene):
        self.config = config
        self.store = store
        self.clock = clock
        self.llm = llm
        self.director = director      # sim/director.py:Director, for `current`
        self.scene = scene            # sim/scene.py:SceneDirector, for the catalogs
        c = getattr(config, "stage_manager", None)
        self.enabled = bool(getattr(c, "enabled", False))
        self.history_turns = int(getattr(c, "history_turns", 20) or 20)

    # ---------------- the catalog and the snapshot ----------------

    def catalog(self):
        """What exists, as the console reads it. Code owns the mapping from an
        option to a file; the console picks on meaning, the same rule the
        staging role follows."""
        return {
            "places": [{"name": k, "what": v} for k, v in self.scene.place_options().items()],
            "music": [{"id": k, "title": v} for k, v in self.scene.bgm_options().items()],
            "outfits": [{"id": k, "what": v} for k, v in self.scene.costume_options().items()],
            "faces": {cid: self.scene.face_options(cid)
                      for cid in self.scene.costumes},
            "cameras": list(CAMERAS),
            "transitions": list(TRANSITIONS),
            "moods": list(MOODS),
        }

    def _scene_line(self):
        cur = self.director.current or {}
        if not cur:
            return "(no scene yet)"
        w = cur.get("with") or cur.get("with_who") or ""
        out = f"{cur.get('location', '')}: {cur.get('activity', '')}"
        if w and w != "alone":
            out += f", with {w}"
        if cur.get("sensory"):
            out += f". {cur['sensory']}"
        return out

    def _staging_line(self):
        got = self.scene.current() or {}
        if not got:
            return "(nothing staged yet)"
        return (f"place {got.get('place') or '?'} (background {got.get('bg') or '?'}), "
                f"camera {got.get('camera') or 'static'}, transition {got.get('transition') or 'cut'}, "
                f"light {got.get('mood') or 'neutral'}, music {got.get('bgm') or 'none'}, "
                f"opening face {got.get('face_index') or 'line emotion'}")

    def snapshot(self):
        """The current scene, staging, scene list and recent thread, as the
        console is told them. Read fresh on every call, never cached."""
        threads = []
        for t in self.store.scene_threads():
            threads.append(f"- {t.get('id')}: {t.get('title') or ''} ({t.get('kind')})")
        recent = []
        for m in self.store.recent_messages(10):
            who = "him" if m.get("role") == "user" else "her"
            recent.append(f"[{self.clock.hm(m['ts'])} {who}] {str(m.get('text') or '')[:200]}")
        cat = self.catalog()
        places = "; ".join(f"{p['name']} ({p['what']})" for p in cat["places"])
        music = "; ".join(f"{m['id']} {m['title']}" for m in cat["music"])
        outfits = "; ".join(f"{o['id']} ({o['what']})" for o in cat["outfits"])
        return (
            "CURRENT SCENE: " + self._scene_line() + "\n"
            "STAGING: " + self._staging_line() + "\n"
            "SCENES:\n" + ("\n".join(threads) or "- main: the main thread") + "\n"
            "RECENT MESSAGES:\n" + ("\n".join(recent) or "(nothing yet)") + "\n"
            "PLACES (name and what it is; copy a name exactly):\n" + places + "\n"
            "MUSIC (id and title; copy an id exactly):\n" + music + "\n"
            "OUTFITS (id and what it is; copy an id exactly):\n" + outfits + "\n"
            "FACES (expression index and pose by outfit; choose an index from the proposed outfit):\n"
            + "\n".join(f"{cid}: " + "; ".join(f"{k} {v}" for k, v in faces.items())
                        for cid, faces in cat["faces"].items()) + "\n"
            "CAMERAS: " + ", ".join(cat["cameras"]) + "\n"
            "TRANSITIONS: " + ", ".join(cat["transitions"]) + "\n"
            "MOODS: " + ", ".join(cat["moods"]) + "\n"
            "VOCAL ACTIONS (optional at the scene opening; use none ordinarily): "
            + ", ".join(sorted(INTERJECTIONS)) + "\n"
        )

    # ---------------- the chat it keeps ----------------

    def history(self):
        rows = self.store.get("stage_console", []) or []
        return [r for r in rows if isinstance(r, dict) and r.get("text")]

    def status(self):
        """What the window is told when it opens: whether the console is on, the
        current scene and staging, the scene list and the catalogs. The window
        reads this; the model is told the same thing as a block."""
        return {"enabled": self.enabled,
                "current_scene": self._scene_line(),
                "staging": self._staging_line(),
                "scenes": self.store.scene_threads(),
                "catalog": self.catalog()}

    def _append(self, role, text):
        rows = list(self.store.get("stage_console", []) or [])
        rows.append({"role": str(role), "text": str(text), "ts": self.clock.now_ts()})
        self.store.set("stage_console", rows[-400:])

    def clear_history(self):
        self.store.set("stage_console", [])

    # ---------------- the one call ----------------

    def _messages(self, text):
        system = self.config.prompt_text("stage_manager") + "\n\n" + self.snapshot()
        msgs = [{"role": "system", "content": system}]
        for turn in self.history()[-self.history_turns:]:
            role = "assistant" if turn.get("role") == "assistant" else "user"
            msgs.append({"role": role, "content": str(turn.get("text") or "")})
        msgs.append({"role": "user", "content": str(text or "")})
        return msgs

    def resolve(self, args):
        """A proposal against the catalogs. No write, no scene: he sees
        this and approves it. A place that is not in the catalog falls to the
        default background and says so; a track that is not on disk becomes
        silence, so a wrong name can never reach the stage."""
        args = args or {}
        place = str(args.get("place") or "").strip()
        bg = self.scene.places.get(place, "") if place in self.scene.places else ""
        if place and not bg:
            logger.log(f"[stage] the console named a place that is not in the catalog: {place!r}")
        if not bg:
            bg = self.scene.default_bg
        bgm = str(args.get("bgm") or "").strip()
        bgm = self.scene._bgm_lower.get(bgm.lower(), "") if bgm else ""
        outfit = str(args.get("outfit") or "").strip().upper()
        if outfit and outfit not in {c.upper() for c in self.scene.costumes}:
            logger.log(f"[stage] the console named an outfit that is not in the catalog: {outfit!r}")
            outfit = ""
        face_index = str(args.get("face_index") or "").strip()
        face_options = self.scene.face_options(outfit or None)
        if face_index not in face_options:
            face_index = ""
        camera = str(args.get("camera") or "static").strip().lower()
        transition = str(args.get("transition") or "cut").strip().lower()
        mood = str(args.get("mood") or "neutral").strip().lower()
        interjection = str(args.get("interjection") or "")
        if interjection not in INTERJECTIONS:
            interjection = ""
        return {
            "text": str(args.get("text") or "").strip(),
            "place": place if place in self.scene.places else "",
            "bg": bg,
            "camera": camera if camera in CAMERAS else "static",
            "transition": transition if transition in TRANSITIONS else "cut",
            "mood": mood if mood in MOODS else "neutral",
            "bgm": bgm,
            "interjection": interjection,
            "bgm_title": str(self.scene.bgm_options().get(bgm) or "") if bgm else "",
            "outfit": outfit,
            "face_index": face_index,
            "known_place": bool(place and place in self.scene.places),
        }

    def chat(self, text):
        """One turn of the console. Returns `{reply, proposal}` or None.

        The model either answers in prose or calls `propose_scene`; the call is
        resolved here and handed back for him to approve. Nothing is
        written to the record and no scene is started by this method."""
        if not self.enabled or not self.llm:
            return None
        line = str(text or "").strip()
        if not line:
            return None
        got = self.llm.call_tools("stage_manager", self._messages(line), TOOLS, tool_choice="auto")
        if not got:
            return None
        reply = str(got.get("text") or "").strip()
        proposal = None
        for call in got.get("calls") or []:
            if call.get("name") == "propose_scene":
                proposal = self.resolve(call.get("arguments") or {})
                break
        if not reply and not proposal:
            return None
        self._append("user", line)
        self._append("assistant", reply or (proposal or {}).get("text", ""))
        return {"reply": reply, "proposal": proposal}
