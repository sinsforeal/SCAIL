# -*- coding: utf-8 -*-
"""Where she is being shown, decided before she writes a word of it.

This is a pre-writer stage pass. It reads her scene (the director's own block:
where she is, what she is doing, who is there) and the feeling the moment is
carrying, and it returns the staging the VN channel draws and the guidance
line her draft is written under: a background, a camera state, a transition
and the mood of the light. It is Orb's Scene Director, narrowed to Momoka's
corpus.

Two rules shape it.

* The background is an id that is on disk. The `vn.bg_dir` is walked once at
  load, and an id is emitted only if its file is there; anything else -- the
  model naming BG99z99, a place with no verified mapping -- falls back to
  `default_bg`, which is checked the same way. The channel draws what this
  returns without checking again.
* It rides in the FAST half. The guidance is a block appended inside the
  `<situation>` she is given, never the cached system prompt
  (`docs/context.md` §1): the system half must stay byte-identical across
  turns for the provider to read its cache.

The model pass is the `scene_director` role -- a judge, neutral, no character
sheet. With it off or the model refused, the deterministic pass reads the
place out of the scene's own words and takes the mood off the reaction band,
so the stage still changes.

Nothing here writes to her record. The last guidance is kept in kv
`scene_guidance` so the channel can draw it, and that is all.
"""

import os
import re
import time

import logger

# Where a place name in her scene maps to a background of Momoka's corpus.
# Only ids confirmed against the extracted game are here; a place that is not
# in this table is drawn as `default_bg` rather than guessed. The table is
# data, not code, and a bundle may extend it with `scene_director.places`.
PLACE_BACKGROUNDS = {
    "club_room": "BG02a01",     # the club room: bookshelves, boxes, a couch
    "meeting_room": "BG03a01",  # the conference room with the projector
    "staff_room": "BG04a01",    # the school staff room / office
    "gym": "BG05a01",           # the gymnasium
    "stage": "BG06a01",         # backstage, behind the curtain
    "classroom": "BG07a01",
    "hallway": "BG08a01",       # the school corridor
    "pool": "BG09a01",          # the indoor pool
    "entrance": "BG10a01",      # the shoe lockers at the school entrance
    "living_room": "BG12a01",   # the living room of a house
    "his_room": "BG13a01",      # a bedroom with a desk
    "her_room": "BG18a01",      # her own bedroom, the pink one
    "city_night": "BG21a01",    # a street at night
    "lounge": "BG23a01",        # a lounge to sit and talk in
    "sky": "BG26a01",           # open sky
    "cafe": "BG27a01",          # a cafe
    "school_gate": "BG01a01",   # the school gate and its courtyard
    "mansion_gate": "BG16a01",  # the stone gate with the mansion beyond
    "building_entrance": "BG11a01",  # the entrance hall of an apartment block
    "academy_corridor": "BG17a01",   # a long corridor with a red carpet
    "city_street": "BG20a01",   # a shopping street in town
    "convenience_store": "BG22a01",  # a convenience store
    "modern_building": "BG24a01",     # a modern hall from outside
    "theater": "BG25a01",       # the seats of a theater
    "traditional_house": "BG28a01",  # an old Japanese house from outside
    "family_room": "BG14a01",   # a family living room with a houseplant
    "tv_living_room": "BG19a01",     # a living room with a low table and a TV
    "twin_bedroom": "BG15a01",  # a pink bedroom with two beds
}

# The surveyed light for each place. `PLACE_BACKGROUNDS` remains the day
# default. A missing sunset or night entry means the corpus has no separate
# image for that place, so the day image remains in use at that time.
PLACE_LIGHTING = {
    "school_gate": {"day": "BG01a01", "sunset": "BG01b01", "night": "BG01c01"},
    "club_room": {"day": "BG02a01", "sunset": "BG02b01", "night": "BG02c01"},
    "meeting_room": {"day": "BG03a01", "sunset": "BG03b01", "night": "BG03c01"},
    "staff_room": {"day": "BG04a01", "sunset": "BG04b01", "night": "BG04c01"},
    "gym": {"day": "BG05a01", "sunset": "BG05b01", "night": "BG05c01"},
    "stage": {"day": "BG06a01", "sunset": "BG06b01", "night": "BG06c01"},
    "classroom": {"day": "BG07a01", "sunset": "BG07b01", "night": "BG07d01"},
    "hallway": {"day": "BG08a01", "sunset": "BG08b01", "night": "BG08c01"},
    "pool": {"day": "BG09a01", "night": "BG09c01"},
    "entrance": {"day": "BG10a01", "sunset": "BG10b01", "night": "BG10d01"},
    "building_entrance": {"day": "BG11a01", "sunset": "BG11b01", "night": "BG11c01"},
    "living_room": {"day": "BG12a01", "sunset": "BG12b01", "night": "BG12c01"},
    "his_room": {"day": "BG13a01", "sunset": "BG13b01", "night": "BG13c01"},
    "family_room": {"day": "BG14a01", "sunset": "BG14b01", "night": "BG14c01"},
    "twin_bedroom": {"day": "BG15a01", "night": "BG15c01"},
    "mansion_gate": {"day": "BG16a01", "sunset": "BG16b01", "night": "BG16c01"},
    "academy_corridor": {"day": "BG17a01", "sunset": "BG17b01", "night": "BG17c01"},
    "her_room": {"day": "BG18a01", "sunset": "BG18b01", "night": "BG18c01"},
    "tv_living_room": {"day": "BG19a01", "sunset": "BG19b01", "night": "BG19c01"},
    "city_street": {"day": "BG20a01", "sunset": "BG20b01", "night": "BG20c01"},
    "city_night": {"day": "BG21a01", "sunset": "BG21b01", "night": "BG21c01"},
    "convenience_store": {"day": "BG22a01", "night": "BG22c01"},
    "lounge": {"day": "BG23a01"},
    "modern_building": {"day": "BG24a01"},
    "theater": {"day": "BG25a01"},
    "sky": {"day": "BG26a01", "sunset": "BG26b01", "night": "BG26c01"},
    "cafe": {"day": "BG27a01"},
    "traditional_house": {"day": "BG28a01"},
}

# What each place is, in words, for the director's catalog. The same rule the
# BGM catalog follows: the model picks an option it can read, and code owns the
# mapping from that option to the file. Kept beside PLACE_BACKGROUNDS so a new
# place is one edit, and a bundle may extend `scene_director.places` without
# touching this.
PLACE_NOTES = {
    "club_room": "the club room: bookshelves, boxes, a couch",
    "meeting_room": "the conference room with the projector",
    "staff_room": "the school staff room, an office",
    "gym": "the gymnasium",
    "stage": "backstage, behind the curtain",
    "classroom": "a classroom",
    "hallway": "the school corridor",
    "pool": "the indoor pool",
    "entrance": "the shoe lockers at the school entrance",
    "living_room": "the living room of a house",
    "his_room": "his bedroom, a desk and a bed",
    "her_room": "her own bedroom, the pink one",
    "city_night": "a street at night",
    "lounge": "a lounge to sit and talk in",
    "sky": "open sky",
    "cafe": "a cafe",
    "school_gate": "the school gate and its courtyard",
    "mansion_gate": "a tall stone gate with ironwork, a mansion beyond it",
    "building_entrance": "the entrance hall of an apartment block",
    "academy_corridor": "a long corridor with a red carpet",
    "city_street": "a shopping street in town",
    "convenience_store": "a convenience store",
    "modern_building": "a modern hall from outside",
    "theater": "the rows of seats in a theater",
    "traditional_house": "an old Japanese house seen from outside",
    "family_room": "a family living room, a sofa, a kitchen beyond and a houseplant",
    "tv_living_room": "a living room with a low table, cushions and a television",
    "twin_bedroom": "a pink bedroom with two beds and a blue floor cushion",
}

# What each costume is, in words, for the console's catalog. The corpus names a
# costume by its set id (`CD01`..`CD07`) and says nothing about what it is; these
# descriptions are read off the art. Same rule as the place and music catalogs:
# the model picks a described option and code owns the id, and the channel
# refuses an id that is not on disk. Every outfit now has 16 labeled faces.
COSTUME_NOTES = {
    "CD01": "her bare body, nothing on",
    "CD02": "her school uniform: a grey blazer, a blue plaid skirt and a red bow",
    "CD03": "a pale green one-piece dress with a white collar",
    "CD04": "a cream frilled nightdress, her hair down",
    "CD05": "the white school swimsuit",
    "CD06": "the light blue gym jersey and shorts",
    "CD07": "a fairy costume: a green petal dress, wings, long gloves and a flower crown",
}

# The place a scene is read as, from the words the director already wrote.
# First match wins; the list is ordered so a specific room is not read as the
# general one.
_PLACE_WORDS = (
    ("pool", ("pool", "swim", "swimming", "プール", "水泳")),
    ("club_room", ("club room", "clubroom", "部室", "circle room", "clubhouse")),
    ("meeting_room", ("meeting room", "conference", "会議", "projector")),
    ("gym", ("gym", "gymnasium", "体育館")),
    ("stage", ("stage", "backstage", "舞台", "ステージ")),
    ("classroom", ("classroom", "教室")),
    ("staff_room", ("staff room", "staffroom", "職員室")),
    ("her_room", ("her room", "her bedroom", "自分の部屋", "私の部屋", "自室", "彼女の部屋")),
    ("his_room", ("his room", "his bedroom", "彼の部屋")),
    ("twin_bedroom", ("twin bed", "two beds", "twin bedroom")),
    ("family_room", ("family room", "houseplant")),
    ("tv_living_room", ("television", "low table")),
    ("living_room", ("living room", "living-room", "livingroom", "リビング", "居間")),
    ("lounge", ("lounge", "ラウンジ")),
    ("convenience_store", ("convenience store", "konbini", "コンビニ")),
    ("cafe", ("cafe", "café", "喫茶", "カフェ")),
    ("traditional_house", ("traditional house", "old house", "japanese house", "日本家屋", "旅館")),
    ("theater", ("theater", "theatre", "cinema", "映画館", "劇場")),
    ("modern_building", ("modern hall", "concert hall", "museum", "美術館", "ホール")),
    ("building_entrance", ("building entrance", "apartment", "マンション", "アパート")),
    ("entrance", ("entrance", "shoe locker", "玄関", "下駄箱", "昇降口", "靴箱")),
    ("mansion_gate", ("mansion", "stone gate", "academy gate", "邸宅", "屋敷")),
    ("school_gate", ("school gate", "main gate", "校門", "正門")),
    ("academy_corridor", ("red carpet", "academy corridor", "赤絨毯")),
    ("hallway", ("hallway", "corridor", "廊下")),
    ("sky", ("sky", "青空", "星空", "屋上", "rooftop")),
    ("city_street", ("shopping street", "high street", "商店街")),
    ("city_night", ("city", "street", "station", "駅", "繁華街", "outside")),
)

# The camera states the stage understands. `static` is the resting one; the
# pans and zooms are the ones the game's own macros animate.
CAMERAS = ("static", "pan_left", "pan_right", "zoom_in", "zoom_out", "shake", "focus")
# How one scene hands over to the next.
TRANSITIONS = ("cut", "fade", "fade_black", "crossfade", "white", "flash")

# The mood of the light. Kept to the words the `mood` field is spoken in. The
# last three came from the corpus's own track titles, which name feelings the
# first seven had no word for: 涙 (sad), セピア色のあの日 (nostalgic),
# ロマンティシズム (romantic). The reaction band still cuts only neutral, warm,
# cool and dim; the model is what reaches the rest.
MOODS = ("neutral", "warm", "cool", "dim", "bright", "tense", "tender",
         "sad", "nostalgic", "romantic")

# Where the corpus lives, relative to the repo root, when a bundle has not
# named one. The absolute path a character uses is in her own config.
DEFAULT_BG_DIR = (
    "extracted_games/koikano/png/scene/bg"
)
# The music, same rule. The tracks are the game's own BGM01..BGMnn.
DEFAULT_BGM_DIR = (
    "extracted_games/koikano/audio/bgm"
)
DEFAULT_SE_DIR = (
    "extracted_games/koikano/audio/se"
)

# These five uses have an unambiguous macro beside the sound in the game's
# stage record. The other named sounds cover several different motions, are
# loops rather than one-shots, or have no macro, so a word match would give
# them a false meaning (see docs/2026-09-18_corpus_sound_effects.md).
EVENT_SOUNDS = (
    ("SE123_b", ("camera shot", "takes a photo", "take a photo", "photograph", "camera", "photo", "カメラ撮影", "写真を撮")),
    ("SE119", ("flashback", "recollection begins", "recall", "回想")),
    ("SE074", ("head pat", "pats her head", "patting her head", "headpat", "なでなで", "頭を撫で")),
    ("SE115", ("time passes", "time passing", "hours later", "next morning", "next day",
               "some time later", "after a while", "the next", "time skip")),
    ("SE121", ("sits down", "takes a seat", "sitting down", "stands up", "gets up",
               "座", "立ち上が")),
)

# balloon overlays available on the sprite; not wired into run() yet
BALLOON_CUES = ("baloon01", "baloon02")

# sd_ chibi CGs are per-scene story art, not generic reactions -- nothing to map here
CHIBI_REACTIONS = {}

SNOW_WORDS = ("snowing", "snowfall", "snow falls", "falling snow", "雪が降", "降雪", "雪景色")
SNOW_NEGATIONS = ("not snowing", "stopped snowing", "snow has stopped", "雪は降っていない")
BEAT_WORDS = ("confesses", "confession", "kiss", "breaks down", "starts crying",
              "revelation", "reveals", "goodbye", "farewell", "argument",
              "reconciles", "remembers", "告白", "キス", "涙", "別れ", "和解", "回想")


def _norm_name(name):
    """The form a character name is compared under: case folded, spaces out.
    The corpus writes 百花 in the track title and the config may write her full
    name (千代田百花), so callers compare by containment rather than equality."""
    return "".join(str(name or "").split()).lower()

# The music a mood falls back to, when the director names none.
#
# From the corpus's own track names, which the game shipped and which are the
# authority here -- the classifier pass (`tools/bgm_mood_axes.py`) only ever
# guessed, and its worst call is a reason to prefer the names: it read BGM13
# (涙, tears) as *positive* (+1.52) because the scenes around tears are tender.
# Each pairing below is the track whose name says the thing:
#   03 学生の本業なので        the school-day bed          -> neutral
#   16 穏やかな暖かな          "calm and warm"             -> warm
#   12 冷たい空気              "cold air"                  -> cool
#   05 秋の夕暮れ              "autumn dusk", subdued      -> dim
#   02 朝は前向きな気持ちで    "a positive feeling in the morning" -> bright
#   11 白と黒の狭間            "between white and black"   -> tense
#   15 伝わって欲しい          "I want it to reach you"    -> tender
#   13 涙                      "tears"                     -> sad
#   18 セピア色のあの日        "that sepia-coloured day"   -> nostalgic
#   26 ロマンティシズム        "romanticism"               -> romantic
# It is data: a bundle replaces it with `scene_director.bgm`.
MOOD_BGM = {
    "neutral": "BGM03",
    "warm": "BGM16",
    "cool": "BGM12",
    "dim": "BGM05",
    "bright": "BGM02",
    "tense": "BGM11",
    "tender": "BGM15",
    "sad": "BGM13",
    "nostalgic": "BGM18",
    "romantic": "BGM26",
}

# The corpus's own titles for its BGM, keyed by the id on disk. Used to hand
# the director a catalog it can read instead of opaque ids -- the same rule the
# place catalog follows. A track not named here still plays; it is only offered
# by its id.
BGM_TITLES = {
    "BGM01": "Dreamer short ver.",
    "BGM02": "朝は前向きな気持ちで",
    "BGM03": "学生の本業なので",
    "BGM04": "のんびりまったりゆったり",
    "BGM05": "秋の夕暮れ",
    "BGM06": "澄んだ夜空に満月が",
    "BGM07": "very fun !",
    "BGM08": "大好きだけど恥ずかしい!",
    "BGM09": "あれあれあれれ?",
    "BGM10": "急いで逃げろ!?",
    "BGM11": "白と黒の狭間",
    "BGM12": "冷たい空気",
    "BGM13": "涙",
    "BGM14": "覚悟",
    "BGM15": "伝わって欲しい",
    "BGM16": "穏やかな暖かな",
    "BGM17": "イチャイチャしてるよ?",
    "BGM18": "セピア色のあの日",
    "BGM19": "輝く舞台",
    "BGM20": "真優のテーマ",
    "BGM21": "千奈のテーマ",
    "BGM22": "アリスのテーマ",
    "BGM23": "百花のテーマ",
    "BGM24": "文芸部",
    "BGM25": "演劇部",
    "BGM26": "ロマンティシズム",
    "BGM27": "深く熱く繋がって",
    "BGM28": "アイキャッチ 1",
    "BGM29": "アイキャッチ 2",
    "BGM30": "オープニングテーマ instrumental ver.",
    "BGM31": "エンディングテーマ instrumental ver.",
    "BGM32": "叶えたい未来 short ver.",
}

# The character themes in the corpus, by the character each belongs to. These
# are not mood cues: they say *who is on stage*, and the game named them after
# the people in it. `BGM23` is Momoka's own. The stage never picks one of these
# by mood -- the director names one when the scene is about that person, which
# is the only thing that knows who the scene is about.
BGM_CHARACTERS = {
    "BGM20": "真優",
    "BGM21": "千奈",
    "BGM22": "アリス",
    "BGM23": "百花",
}

# The tracks the stage may play as a scene bed. The two eyecatches are eleven
# and eight seconds -- stingers for a transition, not music under a scene. The
# OP/ED instrumentals (BGM30/BGM31) and the four character themes (BGM20-23)
# stay in the catalog: the director can name one when it is what the scene is,
# and code has no business deciding that.
BGM_NOT_A_BED = ("BGM28", "BGM29")
INTERJECTION_NOTES = {
    "(laughs)": "a clear laugh at something funny or joyful",
    "(chuckle)": "a brief, restrained laugh; less forceful than laughs",
    "(coughs)": "an actual cough, not a sign of embarrassment",
    "(clear-throat)": "she audibly clears her throat before speaking",
    "(groans)": "an audible groan of discomfort or frustration",
    "(breath)": "a noticeable breath, with no specified direction",
    "(pant)": "repeated short breaths after physical exertion",
    "(inhale)": "a deliberate inward breath before words",
    "(exhale)": "a deliberate outward breath after tension",
    "(gasps)": "a sudden sharp intake at a surprise or shock",
    "(sniffs)": "an audible sniff, such as while holding back tears",
    "(sighs)": "a long breath out at relief, fatigue or resignation",
    "(snorts)": "a short nasal sound of amusement or disdain",
    "(burps)": "an actual burp, only when the scene describes one",
    "(lip-smacking)": "an audible lip sound, such as tasting food",
    "(humming)": "she audibly hums a tune without words",
    "(hissing)": "an audible hiss, such as a sharp reaction to pain",
    "(emm)": "a voiced hesitation while searching for words",
    "(sneezes)": "an actual sneeze, only when the scene describes one",
}
INTERJECTIONS = tuple(INTERJECTION_NOTES)

CAMERA_NOTES = {
    "static": "the scene holds a still view during ordinary conversation",
    "pan_left": "the view follows visible movement toward the left",
    "pan_right": "the view follows visible movement toward the right",
    "zoom_in": "the moment calls attention to a close detail or reaction",
    "zoom_out": "the moment reveals more of the setting around her",
    "shake": "a physical jolt or impact shakes the view",
    "focus": "the scene draws attention to one visible subject",
}
TRANSITION_NOTES = {
    "cut": "an ordinary immediate change or no special transition",
    "fade": "a gentle handover or passage of time",
    "fade_black": "a scene ends or time passes into darkness",
    "crossfade": "two adjacent views blend across a soft change",
    "white": "a bright wash at a memory or strong sensory shift",
    "flash": "a brief abrupt flash at a sudden impact or reveal",
}
MOOD_NOTES = {
    "neutral": "ordinary light without a pronounced emotional colour",
    "warm": "welcoming or affectionate light",
    "cool": "reserved or distant light",
    "dim": "low light or a subdued moment",
    "bright": "clear, lively light",
    "tense": "uneasy or threatening atmosphere",
    "tender": "gentle closeness",
    "sad": "grief or tears",
    "nostalgic": "recollection of a past day",
    "romantic": "open romantic feeling",
}

# Plain-language reading of the game's track titles. Its 532 placement events
# show that these tracks recur across scenes; they are scene beds, not a new
# sound on each dialogue line. Descriptions avoid claims about instrumentation
# that the script and titles do not establish.
BGM_CUES = {
    "BGM02": "optimistic morning or fresh start",
    "BGM03": "ordinary school day",
    "BGM04": "unhurried, easygoing time",
    "BGM05": "subdued autumn dusk",
    "BGM06": "clear moonlit night",
    "BGM07": "playful fun",
    "BGM08": "affection with embarrassment",
    "BGM09": "confusion or comic surprise",
    "BGM10": "urgent escape",
    "BGM11": "uncertain, tense choice",
    "BGM12": "cold distance",
    "BGM13": "tears or grief",
    "BGM14": "resolve or determination",
    "BGM15": "something heartfelt she wants understood",
    "BGM16": "calm warmth",
    "BGM17": "open affection and closeness",
    "BGM18": "memory of a sepia-coloured day",
    "BGM19": "a shining stage or performance",
    "BGM24": "literature club",
    "BGM25": "theater club",
    "BGM26": "romance",
    "BGM27": "deep intimacy",
}


class SceneDirector:
    """The staging for one turn: place, camera, transition, mood."""

    def __init__(self, config, store=None, clock=None, llm=None, typesafe=None, weather=None):
        self.config = config
        self.store = store
        self.clock = clock
        self.weather = weather
        self.llm = llm
        # The hosted classifier (`typesafe.py`, `docs/system-one.md`): when her
        # config turns the `scene_director` use on, one batched call answers the
        # five staging questions -- place, camera, transition, mood, bgm -- that
        # the `scene_director` role answers in JSON today. The role call stays
        # beneath it as the fallback until the off-switch step (`use_model:
        # false`); the deterministic pass is what answers when Jev cannot.
        self.typesafe = typesafe
        c = getattr(config, "scene_director", None)
        self.enabled = bool(getattr(c, "enabled", False))
        self.use_model = bool(getattr(c, "use_model", False)) and llm is not None
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vn = getattr(config, "vn", None)
        self.bg_dir = self._resolve(
            str(getattr(c, "bg_dir", "") or getattr(vn, "bg_dir", "") or DEFAULT_BG_DIR))
        self.default_bg = str(getattr(c, "default_bg", "") or "BG02a01")
        self.places = dict(PLACE_BACKGROUNDS)
        own = getattr(c, "places", None)
        if isinstance(own, dict):
            self.places.update({str(k): str(v) for k, v in own.items()})
        # The outfits the console may set, as the id and what it is. The channel
        # owns the art and refuses an id that is not on disk; this is only the
        # catalog it chooses from.
        self.costumes = dict(COSTUME_NOTES)
        own_costumes = getattr(c, "costumes", None)
        if isinstance(own_costumes, dict):
            self.costumes.update({str(k): str(v) for k, v in own_costumes.items()})
        # The same reviewed table the channel draws: indices are offered only
        # for the currently worn outfit, each with its actual face and pose.
        self.expressions = None
        try:
            from channels.vn_expression import VnExpression
            raw = getattr(config, "raw", {})
            vn_art = raw.get("vn", {}) if isinstance(raw, dict) else {}
            if all(vn_art.get(key) for key in ("character_dir", "inventory", "labels")):
                self.expressions = VnExpression(vn_art, root=self.root)
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.log(f"[scene_director] expression catalog unavailable: {e}")
        self.bgs = self._scan_backgrounds()
        if self.default_bg not in self.bgs and self.bgs:
            # a default that is not on disk is no default; take any real one
            self.default_bg = sorted(self.bgs)[0]
        self.bgm_dir = self._resolve(
            str(getattr(c, "bgm_dir", "") or getattr(vn, "bgm_dir", "") or DEFAULT_BGM_DIR))
        self.bgm = dict(MOOD_BGM)
        own_bgm = getattr(c, "bgm", None)
        if isinstance(own_bgm, dict):
            self.bgm.update({str(k): str(v) for k, v in own_bgm.items()})
        self.bgms = self._scan_bgm()
        self.se_dir = self._resolve(str(getattr(c, "se_dir", "") or DEFAULT_SE_DIR))
        try:
            self.sounds = {name[:-4] for name in os.listdir(self.se_dir)
                           if name.lower().endswith(".ogg")}
        except OSError:
            self.sounds = set()
        self.default_bgm = str(self.bgm.get("neutral") or "")
        if self.default_bgm not in self.bgms and self.bgms:
            self.default_bgm = sorted(self.bgms)[0]
        # Her own character theme, so the catalog can say which one is hers and
        # a caller can ask for it by name (`bgm_for_character`).
        her = ""
        ch = getattr(config, "character", None)
        if ch is not None:
            her = str(getattr(ch, "name_ja", "") or getattr(ch, "name", "") or "")
        self.own_theme = self.bgm_for_character(her)
        self.last = None
        self._last_event_key = ""
        self._last_cue_id = ""
        self._last_beat_key = ""
        self._last_vocal_key = ""
        self._last_vocal_id = ""
        self._last_face_cue_id = ""
        # a background the player picked on the stage, for the next pass only;
        # set by the runtime when the channel reports one (`vn_bot.set_scene`)
        self.request = None

    def face_options(self, costume=None):
        """Index -> reviewed expression and native pose for one outfit."""
        if self.expressions is None:
            return {}
        if not costume and self.store is not None:
            try:
                costume = self.store.get("vn_costume_override", "")
            except Exception:
                costume = ""
        costume = str(costume or self.expressions.default_costume).upper()
        rows = self.expressions.variants_by_costume.get(costume, {})
        return {str(int(index)): f"{row['raw_expression']}; {row['pose'].replace('_', ' ')} pose"
                for index, row in sorted(rows.items())}

    # ---------------- setup ----------------

    def _resolve(self, path):
        if not path:
            return path
        return path if os.path.isabs(path) else os.path.join(self.root, path)

    def _scan_backgrounds(self):
        """Every background id on disk, by the spelling of its file name."""
        out = {}
        try:
            for name in os.listdir(self.bg_dir):
                if name.lower().endswith(".png"):
                    out[name[:-4]] = os.path.join(self.bg_dir, name)
        except OSError:
            pass
        # a model normalises case; match that way and emit the disk spelling
        self._bg_lower = {k.lower(): k for k in out}
        return out

    def known(self):
        return sorted(self.bgs)

    def _light_period(self):
        """The part of Momoka's day that selects a background's light."""
        if self.clock is None:
            return "day"
        try:
            hour = int(self.clock.now().hour)
        except Exception:
            return "day"
        if 6 <= hour < 16:
            return "day"
        if 16 <= hour < 19:
            return "sunset"
        return "night"

    def background_for(self, place):
        """The verified background for a place at the current clock hour."""
        place = str(place or "")
        default = self.places.get(place, "")
        choices = PLACE_LIGHTING.get(place, {})
        wanted = choices.get(self._light_period()) or choices.get("day") or default
        return wanted if wanted in self.bgs else default

    def _scan_bgm(self):
        """Every music track on disk, by the spelling of its file name.
        Missing directory is not an error: a character whose corpus has no
        music simply has none, and the stage plays nothing."""
        out = {}
        try:
            for name in os.listdir(self.bgm_dir):
                if name.lower().endswith(".ogg"):
                    out[name[:-4]] = os.path.join(self.bgm_dir, name)
        except OSError:
            pass
        self._bgm_lower = {k.lower(): k for k in out}
        return out

    def known_bgm(self):
        """The tracks the stage may play as a bed. The stingers are left out;
        everything else, character themes and the OP/ED included, is offered."""
        skip = {str(s).lower() for s in BGM_NOT_A_BED}
        return [t for t in sorted(self.bgms) if t.lower() not in skip]

    def bgm_catalog(self):
        """The catalog as the director reads it: the id, the corpus's own
        title, and -- for the four character themes -- whose theme it is, so it
        can choose on meaning instead of on an opaque number. Same rule as the
        place catalog: code owns what the option stands for."""
        out = []
        for track in self.known_bgm():
            title = str(BGM_TITLES.get(track) or "").strip()
            who = str(BGM_CHARACTERS.get(track) or "").strip()
            if who:
                title = (f"{title} ({who}'s own theme)" if track == self.own_theme
                         else f"{title} ({who}'s theme)")
            cue = BGM_CUES.get(track)
            if cue:
                title = f"{title} — {cue}"
            out.append((f"{track} {title}").strip())
        return out

    def place_options(self):
        """The place catalog as a `choice` map for the hosted classifier:
        option -> what the option is. Same rule as `place_catalog`, but the
        option key is the place name code maps to a background, so an answer
        needs no parsing."""
        out = {}
        for place in sorted(self.places):
            out[place] = str(PLACE_NOTES.get(place) or "").strip() or "a place in this story"
        return out

    def costume_options(self):
        """The outfit catalog as a `choice` map: costume id -> what it is."""
        return {cid: str(note or "").strip() or "an outfit" for cid, note in sorted(self.costumes.items())}

    def costume_catalog(self):
        """The outfit catalog as the console reads it: the id and what it is."""
        return [f"{cid} {note}".strip() for cid, note in sorted(self.costumes.items())]

    def bgm_options(self):
        """The track catalog as a `choice` map for the hosted classifier:
        track id -> the title that is the cue, with a character theme marked.
        Same rule as `bgm_catalog`."""
        out = {}
        for track in self.known_bgm():
            title = str(BGM_TITLES.get(track) or "").strip()
            who = str(BGM_CHARACTERS.get(track) or "").strip()
            if who:
                title = (f"{title} ({who}'s own theme)" if track == self.own_theme
                         else f"{title} ({who}'s theme)")
            cue = BGM_CUES.get(track)
            if cue:
                title = f"{title} — {cue}"
            out[track] = title.strip() or track
        return out

    def bgm_for_character(self, name):
        """The theme of a character, when the corpus has one and the file is on
        disk. `''` when it has none -- a character with no theme is played the
        mood's track like any other scene."""
        want = _norm_name(name)
        if not want:
            return ""
        for track, who in BGM_CHARACTERS.items():
            w = _norm_name(who)
            if w and (w in want or want in w) and track in self.bgms:
                return track
        return ""

    def place_catalog(self):
        """The place catalog as the director reads it: the name and what it is,
        so it chooses on meaning instead of on an opaque background id. Code
        owns the mapping from the name to the file (`self.places`)."""
        out = []
        for place in sorted(self.places):
            note = str(PLACE_NOTES.get(place) or "").strip()
            out.append((f"{place} ({note})").strip())
        return out

    def bgm_for(self, mood):
        """The track a mood falls back to, checked against the disk."""
        want = str(self.bgm.get(str(mood or "neutral").lower()) or self.default_bgm)
        return self._bgm_lower.get(want.lower(), self.default_bgm)

    def _scene_cues(self, scene):
        """Read only explicit scene facts. Return snow, sound and beat identity.

        A sound is a one-shot event, not an ambient property. Its key remains
        stable across repeated passes of the same scene and includes an event
        record id when one exists.
        """
        scene = scene or {}
        setting = str(scene.get("setting") or "").lower()
        weather = str(scene.get("weather") or "").lower()
        if not weather and self.weather is not None:
            try:
                weather = str(self.weather.describe(self.clock.now() if self.clock else None) or "").lower()
            except Exception:
                weather = ""
        surroundings = " ".join(str(scene.get(k) or "") for k in
                                ("location", "activity", "sensory", "around")).lower()
        snow_text = " ".join((weather, surroundings))
        outdoors = any(word in str(scene.get("location") or "").lower() for word in
                       ("outside", "street", "gate", "sky", "courtyard", "rooftop",
                        "outdoors", "外", "道", "校門", "屋上"))
        snow = ((setting in ("outdoors", "outdoor", "outside") or outdoors) and
                (any(word in snow_text for word in SNOW_WORDS) or
                 bool(re.search(r"\bsnow\b", weather))) and
                not any(word in snow_text for word in SNOW_NEGATIONS))
        events = [e for e in (scene.get("events") or []) if isinstance(e, dict)]
        event_text = " ".join(str(e.get("text") or "") for e in events).lower()
        # The plan's activity can name a physical event; dialogue and general
        # sensory prose do not trigger sound effects.
        action = " ".join((str(scene.get("activity") or ""), event_text)).lower()
        sound = ""
        for sound_id, words in EVENT_SOUNDS:
            if sound_id in self.sounds and any(word in action for word in words):
                sound = sound_id
                break
        ids = ",".join(str(e.get("id") or e.get("record_id") or e.get("text") or "")
                       for e in events)
        event_key = f"{sound}:{action}:{ids}" if sound else ""
        explicit_beat = scene.get("emotional_beat") or scene.get("beat")
        beat_text = str(explicit_beat or "").lower()
        beat = bool(explicit_beat) and str(explicit_beat).lower() not in ("none", "false", "0")
        beat = beat or any(word in (event_text + " " + beat_text + " " + str(scene.get("activity") or "").lower())
                           for word in BEAT_WORDS)
        return snow, sound, event_key, beat

    # ---------------- reading the scene ----------------

    def _read_place(self, scene):
        text = " ".join(str((scene or {}).get(k) or "")
                         for k in ("location", "activity", "sensory", "with")).lower()
        for place, words in _PLACE_WORDS:
            if any(w in text for w in words):
                return place
        return ""

    def _fallback(self, scene, mood):
        """The staging from the scene's own words and the mood band."""
        place = self._read_place(scene)
        bg = self.places.get(place) or self.default_bg
        camera = "static"
        activity = str((scene or {}).get("activity") or "").lower()
        if any(w in activity for w in ("walk", "train", "commut", "move")):
            camera = "pan_right"
        return {"place": place or "here", "bg": bg, "camera": camera,
                "transition": "cut", "mood": mood or "neutral",
                "bgm": self.bgm_for(mood), "why": "the scene's own words"}

    # ---------------- the model pass ----------------

    def _ask(self, scene, mood, brief):
        """The staging for this turn, or None so the caller falls back to the
        deterministic pass.

        System One answers first when the use is on; the `scene_director` role
        is asked only when it could not."""
        got = self._ask_typesafe(scene, mood, brief)
        if got is not None:
            return got
        return self._ask_model(scene, mood, brief)

    def _cue_brief(self, scene, brief):
        scene = scene or {}
        facts = []
        for key in ("emotional_beat", "beat", "weather"):
            value = str(scene.get(key) or "").strip()
            if value:
                facts.append(f"{key}: {value[:120]}")
        events = [str(e.get("text") or "")[:120] for e in (scene.get("events") or [])
                  if isinstance(e, dict) and e.get("text")]
        if events:
            facts.append("events: " + "; ".join(events[:3]))
        return (brief + "\n" + "\n".join(facts))[:1200]

    def _ask_typesafe(self, scene, mood, brief):
        """The hosted classifier's staging, or None when it cannot answer.

        One batched call over the catalogs this class already owns. A place
        below its floor drops the whole staging to the role fallback. Music
        and vocal actions have their own floors: an uncertain music choice
        leaves the mood's code-owned track in place, and an uncertain vocal
        action is silent."""
        ts = self.typesafe
        if ts is None or not ts.ready("scene_director"):
            return None
        use = ts.use("scene_director") or {}
        floor = float(use.get("threshold", 0.3))
        music_floor = float(use.get("music_threshold", 0.5))
        vocal_floor = float(use.get("vocal_threshold", 0.6))
        places = self.place_options()
        music = self.bgm_options()
        faces = self.face_options()
        questions = {
            "place": {"type": "choice",
                      "instructions": "Which place is this scene shown in? Copy the name that fits, or `none`.",
                      "criteria": dict(list(places.items()) + [("none", "no place in the list fits")])},
            "camera": {"type": "choice",
                       "instructions": "Which camera movement is visibly justified by this scene? Use static for ordinary dialogue.",
                       "criteria": CAMERA_NOTES},
            "transition": {"type": "choice",
                           "instructions": "How does this scene hand over from the last one? Use cut without an explicit change.",
                           "criteria": TRANSITION_NOTES},
            "mood": {"type": "choice",
                     "instructions": "Which lighting mood fits this scene's stated feeling and setting?",
                     "criteria": MOOD_NOTES},
            "bgm": {"type": "choice",
                    "instructions": "Which described track fits the current scene beat? Choose none if no track clearly fits; code then keeps or chooses the bed.",
                    "criteria": dict(list(music.items()) + [("none", "no track clearly fits; let code keep or choose by mood")])},
            "interjection": {"type": "choice",
                             "instructions": "Is one audible action explicitly justified at this scene opening or new beat? Choose none for ordinary dialogue or emotion without an audible action.",
                             "criteria": {**INTERJECTION_NOTES, "none": "no audible action is supported by the scene"}},
        }
        if faces:
            questions["face_index"] = {
                "type": "choice",
                "instructions": "Which of her real expression and pose pairs fits the scene opening or new emotional beat? Choose none if the scene does not justify a specific face. This face appears on the opening line; later dialogue can change it.",
                "criteria": {**faces, "none": "no specific expression is justified"},
            }
        # The place and track catalogs already appear in the Choice criteria.
        # Repeating them in state costs input tokens and adds irrelevant text
        # to every other question in this batch.
        state = {"scene": brief, "feeling": mood or "neutral"}
        answers = ts.ask("scene_director", state, questions)
        if not answers:
            return None
        place, pconf = ts.choice(answers, "place")
        camera, _ = ts.choice(answers, "camera")
        transition, _ = ts.choice(answers, "transition")
        mood_w, _ = ts.choice(answers, "mood")
        bgm, bconf = ts.choice(answers, "bgm")
        interjection, vconf = ts.choice(answers, "interjection")
        face_index, fconf = ts.choice(answers, "face_index") if faces else ("", 0.0)
        if not place or place not in self.places or pconf < floor:
            logger.log(f"[scene_director] typesafe: no place above the floor "
                       f"({place!r} conf {pconf:.2f} < {floor}); the fallback stages it")
            return None
        bg = self.places.get(place) or self.default_bg
        bgm = bgm if (bgm and bgm in self.bgms and bconf >= music_floor) else ""
        interjection = interjection if (interjection in INTERJECTIONS and vconf >= vocal_floor) else ""
        face_index = face_index if (face_index in faces and fconf >= 0.5) else ""
        camera = camera if camera in CAMERAS else "static"
        transition = transition if transition in TRANSITIONS else "cut"
        mood_w = mood_w if mood_w in MOODS else (mood or "neutral")
        logger.log(f"[scene_director] typesafe: {place} conf {pconf:.2f}, camera {camera}, "
                   f"transition {transition}, mood {mood_w}, bgm {bgm or '(the mood)'} "
                   f"({bconf:.2f}/{music_floor:.2f}), vocal {interjection or 'none'} "
                   f"({vconf:.2f}/{vocal_floor:.2f}), face {face_index or 'line emotion'} "
                   f"({fconf:.2f}/0.50)")
        return {"place": place, "bg": bg, "camera": camera, "transition": transition,
                "mood": mood_w, "bgm": bgm, "interjection": interjection,
                "face_index": face_index,
                "why": "the classifier's staging"}

    def _ask_model(self, scene, mood, brief):
        """The role's staging, or None when it gave nothing usable."""
        if not self.use_model:
            return None
        try:
            system = self.config.prompt_text("scene_director")
            user = (f"the scene: {brief}\n"
                    f"the feeling of the moment: {mood}\n"
                    f"places you may name (use these names exactly, or 'none'): "
                    f"{'; '.join(self.place_catalog())}\n"
                    f"music you may name (use these ids exactly, or 'none'; the title is what the cue is): "
                    f"{'; '.join(self.bgm_catalog())}\n"
                    f"face indices for her current outfit (choose one or 'none'): "
                    f"{'; '.join(f'{k} {v}' for k, v in self.face_options().items())}")
            result = self.llm.call_json("scene_director",
                                        [{"role": "system", "content": system},
                                         {"role": "user", "content": user}])
        except Exception:
            return None
        # `call_json` answers (data, raw); reading the tuple as the dict made
        # every staging pass fall back to the deterministic one
        got = result[0] if isinstance(result, tuple) else result
        if not isinstance(got, dict):
            return None
        # The place is the choice and the background is code's mapping of it, so
        # the model never has to know what a file looks like -- it was handed
        # every id on disk with no description before this and picked blind (it
        # named the school gate for a scene inside his computer). A model that
        # still names a background id is honoured only when the id is on disk
        # and the place it named is not in the catalog.
        place = re.sub(r"[^a-z_]", "", str(got.get("place") or "").strip().lower())[:40]
        bg = self.places.get(place, "") if place in self.places else ""
        if not bg:
            raw_bg = str(got.get("bg") or got.get("background") or "").strip()
            bg = self._bg_lower.get(raw_bg.lower(), "") if raw_bg else ""
        if place not in self.places:
            place = ""
        bgm = str(got.get("bgm") or got.get("music") or "").strip()
        bgm = self._bgm_lower.get(bgm.lower(), "") if bgm else ""
        camera = str(got.get("camera") or "static").strip().lower()
        transition = str(got.get("transition") or "cut").strip().lower()
        mood_w = re.sub(r"[^a-z_]", "", str(got.get("mood") or mood or "neutral").lower())
        face_index = str(got.get("face_index") or "").strip()
        face_index = face_index if face_index in self.face_options() else ""
        return {
            "place": place or "here",
            "bg": bg,
            "camera": camera if camera in CAMERAS else "static",
            "transition": transition if transition in TRANSITIONS else "cut",
            "mood": mood_w if mood_w in MOODS else (mood or "neutral"),
            "bgm": bgm,
            "interjection": str(got.get("interjection") or ""),
            "face_index": face_index,
            "why": str(got.get("why") or "the director's read")[:160],
        }

    # ---------------- the one callers make ----------------

    def run(self, scene, mood=None):
        """Decide the staging for this turn and keep it for the channel."""
        if not self.enabled:
            return None
        if not mood:
            mood = self._mood(scene)
        req = getattr(self, "request", None)
        self.request = None
        picked = ""
        if isinstance(req, dict):
            picked = self._bg_lower.get(str(req.get("bg") or "").lower(), "")
        if picked:
            # a background the player picked by hand on the stage: it stands
            # for this one turn, then the pass resumes its own reading. Validated
            # against the files on disk the same way the model's answer is.
            req_bgm = str(req.get("bgm") or "").strip()
            got = {"place": str(req.get("place") or ""), "bg": picked,
                   "camera": str(req.get("camera") or "static"),
                   "transition": str(req.get("transition") or "cut"),
                   "mood": str(req.get("mood") or mood or "neutral"),
                   "bgm": self._bgm_lower.get(req_bgm.lower(), "") if req_bgm else "",
                   "interjection": str(req.get("interjection") or ""),
                   "face_index": str(req.get("face_index") or ""),
                   "why": "picked by hand on the stage"}
        else:
            brief = ""
            try:
                from sim.director import scene_brief
                brief = scene_brief(scene)
            except Exception:
                brief = str((scene or {}).get("location") or "")
            got = self._ask(scene, mood, self._cue_brief(scene, brief)) or self._fallback(scene, mood)
        got.setdefault("mood", mood or "neutral")
        face_options = self.face_options(req.get("outfit") if isinstance(req, dict) else None)
        face_index = str(got.get("face_index") or "").strip()
        got["face_index"] = face_index if face_index in face_options else ""
        snow, sound, event_key, beat = self._scene_cues(scene)
        beat_key = (str(scene.get("emotional_beat") or scene.get("beat") or scene.get("activity") or "") +
                    ":" + "|".join(str(e.get("id") or e.get("record_id") or e.get("text") or "")
                                   for e in (scene.get("events") or []) if isinstance(e, dict))) if beat else ""
        new_beat = bool(beat_key and beat_key != self._last_beat_key)
        # The music: the director's own pick when it named one that exists, the
        # mood's floor otherwise. Never left empty when a track is on disk, so
        # the stage always has something to play and the channel never has to
        # decide what a missing field means.
        if not got.get("bgm"):
            got["bgm"] = self.bgm_for(got.get("mood") or mood)
        # The staging stands while the scene's place has not moved. Without this
        # the pass re-decided every turn, and a reply's own bubbles could move
        # the background and the track under it: the director's block says the
        # same place every tick, and the staging has to agree with it twice
        # running before it is allowed to change. A background picked by hand on
        # the stage is never held over -- that one stands for its own turn.
        if (not picked and isinstance(self.last, dict)
                and got.get("place") == self.last.get("place")):
            for key in ("bg", "camera", "transition"):
                if self.last.get(key):
                    got[key] = self.last[key]
            # A track change in the same room needs a new story beat, and the
            # candidate must actually differ. A routine line keeps the bed.
            if not new_beat and self.last.get("bgm"):
                got["bgm"] = self.last["bgm"]
            if not new_beat:
                got["face_index"] = self.last.get("face_index", "")
        if not picked and got.get("place") in self.places:
            got["bg"] = self.background_for(got["place"])
        if event_key and event_key != self._last_event_key:
            got["se"] = sound
            got["cue_id"] = str(time.time_ns())
            self._last_cue_id = got["cue_id"]
        elif event_key:
            got["se"] = sound
            got["cue_id"] = self._last_cue_id
        else:
            got["se"] = ""
            got["cue_id"] = ""
            self._last_cue_id = ""
        self._last_event_key = event_key
        self._last_beat_key = beat_key
        got["snow"] = snow
        proposed_vocal = str(got.get("interjection") or "")
        if proposed_vocal not in INTERJECTIONS:
            proposed_vocal = ""
        # A vocal action belongs to a new beat or scene opening. A model's
        # repeated proposal during the same exchange cannot make her sigh on
        # every line. The identity persists so a polling channel can consume
        # it exactly once.
        vocal_key = f"{got.get('place')}:{beat_key or got.get('place')}:{proposed_vocal}" if proposed_vocal else ""
        opening = not isinstance(self.last, dict) or got.get("place") != self.last.get("place")
        if got.get("face_index"):
            if opening or new_beat or picked or not self._last_face_cue_id:
                self._last_face_cue_id = str(time.time_ns())
            got["face_cue_id"] = self._last_face_cue_id
        else:
            got["face_cue_id"] = ""
            self._last_face_cue_id = ""
        if proposed_vocal and (opening or new_beat) and vocal_key != self._last_vocal_key:
            self._last_vocal_id = str(time.time_ns())
            self._last_vocal_key = vocal_key
        if proposed_vocal and vocal_key == self._last_vocal_key:
            got["interjection"] = proposed_vocal
            got["vocal_cue_id"] = self._last_vocal_id
        else:
            got["interjection"] = ""
            got["vocal_cue_id"] = ""
        if not proposed_vocal:
            self._last_vocal_key = ""
            self._last_vocal_id = ""
        got["updated"] = self.clock.now_ts() if self.clock else None
        self.last = got
        if self.store is not None:
            try:
                self.store.set("scene_guidance", got)
            except Exception:
                pass
        return got

    def _mood(self, scene):
        """The light of the moment, off the mood band the reaction already cut.

        Read from kv `reaction_last`, which `sim/reactions.py` writes on every
        crossing (`band`, -2..2) and which is therefore the same cut the
        channel's face is drawn from. Nothing new is measured here and no state
        object is needed."""
        last = {}
        try:
            last = (self.store.get("reaction_last", {}) or {}) if self.store is not None else {}
        except Exception:
            last = {}
        band = last.get("band")
        if band is None:
            return "neutral"
        try:
            band = int(band)
        except (TypeError, ValueError):
            return "neutral"
        if band <= -2:
            return "dim"
        if band == -1:
            return "cool"
        if band >= 1:
            return "warm"
        return "neutral"

    def current(self):
        """What the channel draws: the last staging, or nothing."""
        if self.last:
            return dict(self.last)
        if self.store is not None:
            try:
                return self.store.get("scene_guidance") or None
            except Exception:
                return None
        return None

    def guidance_block(self, got=None):
        """The line her draft is written under. Rides in the fast half."""
        got = got or self.run_standby()
        if not got:
            return ""
        return ("<stage>\n"
                f"Where this is being shown: {got.get('place', 'here')} "
                f"(background {got.get('bg', self.default_bg)}), camera {got.get('camera', 'static')}, "
                f"coming in on a {got.get('transition', 'cut')}. The light is {got.get('mood', 'neutral')}.\n"
                "You are not told this and you never describe it; your words simply fit where you are.\n"
                "</stage>")

    def run_standby(self):
        return self.last

    # ---------------- selftest ----------------

    def verify(self):
        """Every background the map names is on disk; every camera is known."""
        rows = []
        for place, bg in sorted(self.places.items()):
            rows.append((place, bg, bg in self.bgs))
        return rows, self.default_bg in self.bgs, bool(self.bgs)

    def verify_lighting(self):
        """Every catalogued lighting image is present in the background corpus."""
        rows = []
        for place, choices in sorted(PLACE_LIGHTING.items()):
            for light, bg in sorted(choices.items()):
                rows.append((place, light, bg, bg in self.bgs))
        return rows

    def verify_bgm(self):
        """Every mood's track is one the stage can actually play. A corpus with
        no music at all is not a failure -- the stage simply plays nothing."""
        return [(m, t, t in self.bgms) for m, t in sorted(self.bgm.items())]

    def music_ok(self):
        if not self.bgms:
            return True
        return all(ok for _, _, ok in self.verify_bgm()) and self.default_bgm in self.bgms


if __name__ == "__main__":
    import json
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)

    class _SD:
        enabled = True
        use_model = False
        bg_dir = ""
        default_bg = "BG02a01"
        places = {}

    class _VN:
        bg_dir = ""

    class _C:
        scene_director = _SD()
        vn = _VN()

    sd = SceneDirector(_C())
    rows, default_ok, any_bg = sd.verify()
    print(f"[scene] {len(sd.bgs)} background(s) on disk, default {sd.default_bg} "
          f"{'ok' if default_ok else 'MISSING'}")
    for place, bg, ok in rows:
        print(f"  {'OK ' if ok else 'MISS'} {place:14s} {bg}")
    lighting_rows = sd.verify_lighting()
    print(f"[scene] {len(lighting_rows)} lighting background mapping(s)")
    for place, light, bg, ok in lighting_rows:
        print(f"  {'OK ' if ok else 'MISS'} {place:20s} {light:6s} {bg}")
    bgm_rows = sd.verify_bgm()
    print(f"[scene] {len(sd.bgms)} track(s) on disk, default {sd.default_bgm} "
          f"{'ok' if sd.default_bgm in sd.bgms else 'MISSING'}")
    for mood, track, ok in bgm_rows:
        print(f"  {'OK ' if ok else 'MISS'} {mood:8s} {track}")
    for scene in ({"location": "the indoor pool", "activity": "swimming"},
                  {"location": "her room, in bed", "activity": "asleep"}):
        got = sd._fallback(scene, "dim")
        print(f"  {scene['location']!r} -> {got['bg']} {got['camera']} + {got['bgm']}")
    raise SystemExit(0 if (default_ok and any_bg and sd.music_ok()
                           and all(ok for _, _, ok in rows)
                           and all(ok for *_, ok in lighting_rows)) else 1)
