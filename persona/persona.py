import re
from sim import wiring
import json
import datetime
import logger
from sim import existence
from sim import sight
from sim import works
from sim import reconcile
from sim import recall
from sim.textutil import drop_repeats, near_duplicate, words as cue_words
from sim.director import scene_brief
from sim.shape import Shape
from types import SimpleNamespace
from persona import sections as _sections
from sim import thread as _thread
from sim.thread import STAMP_HEAD, strip_stamps


# Plain words for a clock hour. It lives on the clock now, because the role
# that decides what she wants needs the same words and used to get two bare
# readings instead.
from world.clock import daypart as _daypart


_WEEKDAY_JA = "月火水木金土日"


def _when(dt, ja=False):
    """A day and a time she can read at a glance. `%A` is an English weekday
    and the clock line is the first thing in her situation block."""
    if ja:
        return f"{_WEEKDAY_JA[dt.weekday()]}曜 {dt.strftime('%H:%M')}"
    return dt.strftime("%A %H:%M")


def _clip(text, n):
    """Whole words, at most n chars, an ellipsis when cut."""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return cut + "..."


def _grab(obj, method, *a):
    """A subsystem's line for the block, or nothing: the subsystem may be
    absent for this character, and a subsystem that raises costs her a line,
    never the reply."""
    if not obj:
        return ""
    try:
        return getattr(obj, method)(*a) or ""
    except Exception:
        return ""

# The only model that speaks as her. It sees: who she is (bible + style),
# what she knows about him, the real chat, and one <situation> block that is
# her present awareness. It never sees telemetry, instructions about tags,
# or its own diary. Output is split on blank lines into separate bubbles.


from sim.attention import tag
# which language a line addressed to her is written in. One switch,
# `character.writes_to_him`; the first character writes English and shares
# every line of this file.
from sim.lang import say, reads_ja

# what a scraped window title must not look like: a clock time, or a clause
# about him. Both are the digest's own prose, not the name of anything
# (`ResidentSight.noticed_title`, which uses them).


def _gap_text(hours, ja=False):
    """A stretch of time the way a person says it, never a decimal."""
    if hours < 1:
        m = int(round(hours * 60))
        return f"{m}分" if ja else f"{m} minutes"
    if hours < 24:
        h = int(round(hours))
        if ja:
            return f"{h}時間"
        return f"{h} hour{'s' if h != 1 else ''}"
    d = hours / 24.0
    if d < 2:
        return "1日" if ja else "a day"
    return f"{int(round(d))}日" if ja else f"{int(round(d))} days"


def _mostly_japanese(text):
    """More of the letters are kana or kanji than Latin: the answer is in
    the other room's language."""
    import re as _re
    ja = len(_re.findall(r"[぀-ヿ一-鿿]", str(text)))
    la = len(_re.findall(r"[A-Za-z]", str(text)))
    return ja > 0 and ja > la


def _run(a, b):
    """The longest run the two sequences share."""
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            best = max(best, k)
    return best


def _copied(hers, theirs):
    """The longest run her text shares with the line that was put in front of
    her -- the measure of an instruction speaking through her.

    Two scripts, two units. For English it is consecutive words of three
    letters or more, lowercased, so 'the' and 'you' do not count as a run.
    Japanese is not written with spaces, so there are no words to line up and
    the unit is the character: a run inside kana and kanji, tokenised the way
    the attention gate tokenises (`sim/attention.py`). Without this the
    measure returned 0 for every reply the second character has ever written,
    which reads as "the line did not speak through her" and means "nothing was
    measured". The larger of the two is returned; four is a run either way."""
    import re as _re
    a = [w for w in _re.findall(r"[a-z']+", str(hers).lower()) if len(w) >= 3]
    b = [w for w in _re.findall(r"[a-z']+", str(theirs).lower()) if len(w) >= 3]
    ja = _re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]{2,}")
    ja_a = list("".join(ja.findall(str(hers))))
    ja_b = list("".join(ja.findall(str(theirs))))
    return max(_run(a, b), _run(ja_a, ja_b))


def closing_instruction(config, spillish=False, tell_length=None, embodied=None, writes_ja=None,
                        place_notice=False):
    """The last thing she reads before she writes: what language this chat is
    in, what makes two bubbles, and the four standing rules.

    A function rather than lines inside `_situation` because a bench has to be
    able to build it for a character in any arm, and a copy of it in a harness
    is a copy that drifts -- `tools/voicelab.py` held one for a week.

    Two independent settings meet here and neither may be read off the other.
    `writes_to_him` is the language she ANSWERS in and decides what this block
    SAYS; `instructions` is the arm and decides what language it says it in
    (`sim/lang.py`). A character can be told in English to write Japanese,
    which is what the second character was told until 2026-09-02, and it is
    what the control arm still renders for her."""
    t = say(config)
    ch = config.character
    if writes_ja is None:
        writes_ja = str(getattr(ch, "writes_to_him", "english")).lower().startswith("ja")
    if tell_length is None:
        tell_length = bool(getattr(config.shape, "tell_length", True))
    if embodied is None:
        embodied = bool(ch.existence.embodied)
    # what language this chat is in, and whether she has another one at all
    if writes_ja:
        lang = t("write your message(s) now, to HIM, in your chat with him, IN JAPANESE. "
                 "Japanese is the only language you have and this chat is no different from anywhere else; "
                 "the [time · room · who] labels are the app's, never typed. ",
                 "いま彼に、彼とのチャットでメッセージを書く。日本語で書く。"
                 "あなたが持っている言葉は日本語だけで、このチャットも他のどこと変わらない。"
                 "記録についている [time · room · who] のラベルはアプリのもので、自分では打たない。")
    else:
        lang = t("write your text message(s) now, to HIM, in your chat with him, IN ENGLISH -- this chat is the one place your English lives; "
                 "the Japanese above is your other rooms and stays there (a Japanese word only where you would actually drop one in): the other rooms in the record (LINE, the group, "
                 "the kitchen) are answered there, never here, and the [time · room · who] labels are the app's, never typed. ",
                 "いま彼に、彼とのチャットでメッセージを書く。英語で書く。"
                 "このチャットだけがあなたの英語の居場所で、上に出てくる日本語は別の部屋のもので、そこに置いておく"
                 "（日本語の単語は、実際に混ざるところにだけ）。記録にある別の部屋（LINE、グループ、台所）はそこで返すもので、"
                 "ここでは返さない。[time · room · who] のラベルはアプリのもので、自分では打たない。")
    # Nothing about bubbles for a character who is not told a length
    # either: the two are one instruction, and the second character was
    # given both and sent 39 single bubbles, 17 of them holding lines she
    # had split with a soft break rather than the blank line asked for.
    # She writes a message; it goes as she wrote it.
    bubble_rule = (t(
        "separate bubbles are separated by a BLANK LINE, and nothing else makes two bubbles: "
        "a single line break is one bubble with a break in it. ",
        "吹き出しを分けるのは空行だけで、他の何も二つには分けない。"
        "改行が一つだけなら、それは中に改行が入った一つの吹き出しになる。")
        if tell_length else "")
    return (
        lang
        + bubble_rule
        # The examples in her style notes are quoted, because a document
        # quotes what it is showing you. A model reading them as surface
        # copies the marks: the second character's first reply came back as
        # one bubble holding three lines each wrapped in 「」, which is not
        # a chat message, and it cost the delivery its typing pauses and
        # its interruptibility as well.
        + t("never wrap a message in quotation marks -- the 「」 and \" \" around the examples in your "
            "style notes belong to the notes, marking where a quotation starts and stops; you are "
            "typing into a chat box, and nobody types the brackets. ",
            "メッセージをかぎ括弧でくくらない。喋り方のメモにある例についている「」や\" \"は"
            "メモのもので、引用の始まりと終わりを示すためのもの。あなたはチャットの入力欄に打っていて、"
            "括弧を打つ人はいない。")
        + (t("what you can see of him is background: never narrate it back at him unless he asked, "
             "and never repeat a detail (the window he had open, how long he has been at it) already in your recent messages. ",
             "彼のことで見えているものは背景。聞かれない限り、それを彼に語り直さない。"
             "直近のメッセージにもう出てきた細かいこと（開いていたウィンドウ、どれだけ長く向かっているか）を繰り返さない。")
           if not embodied else
           ("" if place_notice else
           t("where you are and what you are doing is background: never report it unless he asked or it is the reason you have to go, "
             "and never repeat a scene detail (the floor, your hair, the heat, what you are holding) that is already in your recent messages. ",
             "自分がどこにいて何をしているかは背景。聞かれたときと、それが席を立つ理由になるとき以外は報告しない。"
             "直近のメッセージにもう出てきた場面の細かいこと（床、髪、暑さ、手に持っているもの）を繰り返さない。")))
        # the reason clause is a length instruction wearing a style rule's
        # clothes -- "how short you are, what you ask" is the steer that
        # produced 36% of her messages ending on a question back at him.
        # A character who is told nothing about length is not told this
        # either; the rule itself, which is her own style file's
        # 自分の心理を説明しない, stays for both.
        + ("" if spillish else
           (t("do not name your feelings in a sentence; what you feel shows in how short you are, what you skip, what you ask. ",
              "自分の気持ちを文章で説明しない。感じていることは、短さ、飛ばしたこと、何を訊くかに出る。")
            if tell_length else
            t("do not name your feelings in a sentence; it shows in what you say and what you leave out. ",
              "自分の気持ちを文章で説明しない。言うことと言わないことに出る。")))
        + t("the [Thu 01:24] stamps in the chat are the app's timestamps, not part of what anyone typed; never write one. "
            "the chat above is the record of what has been said, not a script to carry on: you write the NEXT message, never another line of it. ",
            "チャットについている [Thu 01:24] のような刻印はアプリがつけた時刻で、誰かが打った文字ではない。自分では絶対に書かない。"
            "上のチャットは交わされたことの記録で、続きを書くための台本ではない。書くのは次のメッセージだけで、記録の続きではない。")
        # her prompt with her friends has had this since 08-30 and this one
        # never did: the same sentence went to him twice, two hours apart,
        # after he had already answered it.
        + t("a thing you have already sent him is said, and the chat above carries it: you take it further, "
            "answer what came back to it, or drop it -- you never send it again in the same words or in shuffled ones.",
            "もう送ったことは言い終わっていて、上のチャットがそれを持っている。先へ進めるか、返ってきたものに答えるか、やめるか。"
            "同じ言葉でも並べ替えた言葉でも、二度は送らない。"))


# The grammatical furniture of Japanese: particles, inflections, pointing
# words, and the stalls and endings every speech guide in the project asks
# for. Masked out before her own recent phrases are counted, so what is
# counted is what she chose rather than what the language and her own guide
# put there. No person is named here and none may be: a character's own
# name forms come off her sheet (`_own_phrases`).
_FURNITURE = ("そう", "けど", "ない", "して", "こと", "もう", "でも", "だけ", "から", "って", "った", "たら",
              "ます", "です", "ません", "なかっ", "てる", "たい", "んだ", "のに", "ある", "いる", "する",
              "なる", "とか", "まで", "より", "ため", "とき", "それ", "これ", "あれ", "どこ", "なに", "でき",
              "じゃ", "ちゃ", "いま", "でしょ", "じゃん", "だよね", "もん", "なの", "っけ", "みたい", "かも",
              "わかん", "なんか", "えっと", "えー", "あの", "うーん", "ほんと", "ちょっと", "だから",
              "あんた", "ねえ", "ほら")

_PHRASE_RUN = re.compile(r"[぀-ヿ一-鿿]{2,}")

# Where one bubble of hers stops and the next starts is code's decision, not the
# model's. The model is asked for a blank line between bubbles and cannot be
# relied on to give one: on 2026-09-17 a four-line reply came back with single
# line breaks, `_split` read it as ONE bubble, and the stage had nothing to
# click through and one voice clip for four lines. A bubble now ends at a line
# break, and inside a line after every Japanese full stop. A character whose
# config does not split keeps one bubble, unchanged.
_BUBBLE_STOP = "\u3002"  # 。


def split_bubbles(text):
    """Split her draft into bubbles on line breaks and after each 「。」."""
    parts = []
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        start = 0
        for i, ch in enumerate(line):
            if ch == _BUBBLE_STOP:
                seg = line[start:i + 1].strip()
                if seg:
                    parts.append(seg)
                start = i + 1
        tail = line[start:].strip()
        if tail:
            parts.append(tail)
    return parts


def _runs(text, mask):
    """The stretches of a message left once the furniture is taken out."""
    t = str(text or "")
    for s in mask:
        t = t.replace(s, " ")
    return _PHRASE_RUN.findall(t)


class Persona:
    WIRES = ('agenda', 'anime_kb', 'anime_sense', 'attachment', 'attention', 'cast_psych', 'commitments', 'diet', 'expectations', 'foresight', 'goals', 'hazards', 'him_profile', 'household', 'ick', 'ledger', 'lookup', 'lore', 'mechanisms', 'model_of_her', 'model_of_him', 'nudge', 'orbit', 'quality', 'rhythm', 'ruptures', 'scenery', 'scene_director', 'seen_images', 'self_memory', 'sentiments', 'director', 'phone', 'sight', 'situation', 'social', 'spirals', 'stances', 'thread', 'watching', 'withholding', 'wonder', 'world_shared', 'zeitgeist', 'reunion',)
    def __init__(self, config, llm, store, clock, state, mal=None, receipts=None, notes=None, records=None, social=None, diary=None, body=None, diet=None, money=None, memory=None, reflection=None, outlook=None):
        self.config = config
        self.diary = diary
        self.mal = mal
        self.receipts = receipts
        self.notes = notes
        self.records = records
        self.social = social
        self.llm = llm
        self.store = store
        self.clock = clock
        self.state = state
        self.body = body
        self.diet = diet
        self.money = money
        self.memory = memory
        self.reflection = reflection
        self.outlook = outlook
        # set by `_drop_already_sent`: whether the last draft came back as
        # nothing but things she had already sent him
        self.last_all_repeats = False
        self._phrase_mask = None
        self._sections = {}
        # set by the app after construction, like anime_sense
        self.model_of_him = None
        self.model_of_her = None
        self.spirals = None
        self.ruptures = None
        self.sentiments = None
        self.self_memory = None
        self.goals = None
        self.ick = None
        # the VN staging pass and the draft guard (`sim/scene.py`,
        # `sim/quality.py`), set by the app after construction
        self.scene_director = None
        self.quality = None
        # where a streaming channel reads her tokens as they are written
        # (`channels/vn_bot.py`): a callable (text) -> None, or None
        self.stream_sink = None
        self.bible = config.prompt_text("persona")
        self.style = config.read_text(config.character.style_prompt)
        # how much she says is drawn by code, never left to the model
        self.shape_engine = Shape(config, state, clock)
        wiring.declare(self)

    # Everything she is addressed in -- the section headers, the situation
    # block, the closing instruction -- is written in the arm she is on.
    # Read per call rather than stored at construction, so a harness that
    # flips the arm inside one process gets the other arm without rebuilding
    # her (`sim.lang.set_override`).
    @property
    def t(self):
        return say(self.config)

    # ---------------- a world somebody else keeps ----------------
    #
    # Two sections that settle once a day belong to whoever KEEPS the world:
    # the people around the people, and what is going round. A character in a
    # world she does not keep has neither running, and would otherwise carry
    # a blank where the owner carries eight lines -- so she reads the rows
    # the owner wrote (`world/shared.py`). She never writes one.

    def _world_rows(self):
        """The world file when it is somebody else's to write, else None."""
        w = self.world_shared
        if w and w.enabled and not w.owner and getattr(self.config, "world_reader", False):
            return w
        return None

    def _world_limit(self):
        return int(getattr(self.config.world_shared, "read_rows", 8) or 8)

    def _world_orbit(self):
        w = self._world_rows()
        if not w:
            return ""
        try:
            return "\n".join(w.orbit_lines(limit=self._world_limit()))
        except Exception:
            return ""

    def _world_gossip(self):
        w = self._world_rows()
        if not w:
            return []
        try:
            return w.gossip_lines(limit=self._world_limit())
        except Exception:
            return []

    @property
    def ja(self):
        return reads_ja(self.config)

    def _system(self, cue_text=""):
        t = self.t
        if self.memory and self.config.memory.enabled:
            facts = self.memory.facts_for_prompt(cue_text)
        else:
            facts = self.store.user_facts()[-40:]
        # AND WHAT HE WATCHED TODAY THAT NOTHING HAS WRITTEN DOWN YET. The
        # block about his watching is a window of a few hours round the play
        # and the compile that turns it into a fact runs once a day, so
        # between them she can be left agreeing that he never watches
        # anything (`sim/watching_him.provisional_facts`). Only the ones no
        # fact she already holds names, so a day already compiled does not
        # say it twice, and never for a character with no chat with him --
        # `_facts_head` drops the whole section for her.
        if self.watching and self._facts_head():
            try:
                for name, line in self.watching.provisional_facts(ja=self.ja):
                    if not any(name in f for f in facts):
                        facts = facts + [line]
            except Exception as e:
                logger.log(f"[watching] the same-day line was not added: {type(e).__name__}: {e}")
        facts_txt = "\n".join(f"- {f}" for f in facts) if facts else t(
            "- (nothing specific yet beyond what you already know)",
            "- （まだ特にない。すでに知っていること以外は）")
        backstory = self.store.get("backstory", "")
        back_txt = ("\n\n" + t("## How you got here", "## ここまでの経緯") + f"\n{backstory}") if backstory else ""
        shelf = ""
        if self.mal and self.mal.enabled:
            sv = self.config.sensor_view
            # her own reading of his list: the wording around the titles is
            # the one she is addressed in (`_knowledge` below asks for the
            # same summary in English, because the editor is machinery)
            shelf_txt = self.mal.shelf_summary(sv.mal_shelf_watching_max, sv.mal_shelf_completed_max, t=t)
            if shelf_txt:
                shelf = ("\n\n" + t(
                    "## His anime list (he shared it with you; you look at it more than you admit. Be coy about how often you check, "
                    "never pretend you do not know what is on it: what he is watching, how far he is, what he finished)",
                    "## 彼のアニメリスト（彼が見せてくれたもので、あなたは認めているより頻繁に見ている。どれくらい見ているかははぐらかしていいが、"
                    "中身を知らないふりはしない。彼が何を観ていて、何話まで進んでいて、何を観終わったか）") + "\n" + shelf_txt)
        notes_txt = ""
        if self.notes:
            idx = self.notes.index_text()
            if idx:
                notes_txt = ("\n\n" + t("## Notes of his you have read (one line each, what stuck)",
                                        "## あなたが読んだ彼のメモ（一行ずつ、印象に残ったこと）") + f"\n{idx}")
        cast_txt = ""
        if self.records:
            if self.memory and self.config.memory.enabled:
                lines = self.memory.cast_lines(self.state.relationships)
            else:
                lines = []
                for name, r in self.state.relationships.items():
                    if name == "him" or not (r.get("situation") or r.get("unresolved")):
                        continue
                    bit = r.get("situation", "")
                    if r.get("unresolved"):
                        bit += f" (between you: {r['unresolved']})"
                    lines.append(f"- {name}: {bit}")
            try:
                # The people around the people, and what is going round.
                # Both are settled once a day by whoever KEEPS the world; a
                # character who is in a world somebody else keeps has neither
                # module running (`Config.REQUIRES`, the `world_owner`
                # property) and reads the owner's rows instead. Reader only:
                # the owner's own bytes are what they were.
                # the reader first: for the owner both of these are empty,
                # because the world file is hers to write and her own
                # modules are the ones that hold the rows
                ob = self._world_orbit() or (self.orbit.brief(limit=8) if self.orbit else "")
                gz = self._world_gossip()
                if gz:
                    lines = list(lines) + [t("what is going round (nobody's own business; you have heard it, "
                                             "you did not check it):",
                                             "みんなが言っていること（誰のものでもない噂。聞いただけで、確かめてはいない）:")] + gz
                if ob:
                    ob = self._own_people_as_yours(ob)
                    lines = list(lines) + [t("their people (a friend's sister, a mother, a teacher -- the same one each time):",
                                             "その人たちの周りの人（友だちの姉、母親、先生 -- 毎回同じ人）:")] + ob.split("\n")
            except Exception:
                pass
            if lines:
                cast_txt = ("\n\n" + t("## People around you lately (what is going on with them, as far as you know)",
                                       "## 最近のあなたの周りの人たち（あなたが知っている範囲で、その人たちに何があるか）") + "\n" + "\n".join(lines))
            try:
                cast_txt += self.cast_psych.prompt_text() if self.cast_psych else ""
            except Exception:
                pass
        selfmem_txt = ""
        if self.self_memory and self.config.self_memory.enabled:
            selfmem_txt = self.self_memory.prompt_text(cue_text)
        diary_txt = ""
        if self.diary:
            d = self.diary.prompt_text()
            if d:
                diary_txt = ("\n\n" + t("## From your diary (what you wrote, the last nights; yours alone, he has never seen it)",
                                        "## あなたの日記から（ここ数日の夜に書いたこと。あなただけのもので、彼は一度も見ていない）") + "\n" + d)
        weekly_txt = ""
        wk = self.store.get("weekly_self", [])
        if wk and self.config.weekly.enabled:
            weekly_txt = ("\n\n" + t("## How you have been lately (your own sense of it)",
                                     "## 最近の自分の調子（自分でどう感じているか）") + "\n"
                          + "\n\n".join(w["text"] for w in wk[-self.config.weekly.in_prompt:]))
        claims_txt = ""
        cl = self.store.get("self_claims", [])[-30:]
        if cl:
            # Who she said it TO depends on whether she has a chat with him at
            # all. A character who has not still tells her own friends things
            # about herself and still has to stay consistent with them, and
            # this heading called four lines about what she had told two of
            # her own people "what you told HIM".
            claims_head = (t("## Things you have told him about yourself (stay consistent with them)",
                             "## あなたが彼に話した自分のこと（ここと食い違うことを言わない）")
                           if existence.has_chat(self.config) else
                           t("## Things you have told people about yourself (stay consistent with them)",
                             "## あなたが人に話した自分のこと（ここと食い違うことを言わない）"))
            claims_txt = ("\n\n" + claims_head + "\n"
                          + "\n".join(f"- {c['date'][5:]}: {c['text']}" for c in cl))
        reflect_txt = ""
        if self.reflection:
            rt = self.reflection.prompt_text()
            if rt:
                # Each row says who it is about, and not all of them are about
                # him: a comparison against one of her own people is written
                # into the same list (the reflections channel), so a thought
                # about a friend arrived under a heading calling it a thought
                # about him. The heading says what the list is; the rows say
                # who each one is for.
                reflect_txt = ("\n\n" + t("## Things you have thought lately, to yourself (never said; each line says who it is about)",
                                          "## 最近、自分の中で思ったこと（口に出していない。各行に誰についてかが書いてある）") + "\n" + rt)
        beliefs_txt = ""
        if self.model_of_him and self.config.beliefs.enabled:
            beliefs_txt = self.model_of_him.prompt_text()
        hp = self.him_profile
        if hp:
            try:
                pt = hp.prompt_text()
                if pt:
                    beliefs_txt = (beliefs_txt + "\n\n" if beliefs_txt else "") + pt
            except Exception:
                pass
        selfbeliefs_txt = ""
        if self.model_of_her and self.config.beliefs.enabled:
            selfbeliefs_txt = self.model_of_her.prompt_text()
        spiral_txt = ""
        if self.spirals and self.config.spiral.enabled:
            spiral_txt = self.spirals.prompt_text()
        sentiment_txt = ""
        if self.sentiments and self.config.sentiment.enabled:
            sentiment_txt = self.sentiments.prompt_text()
        rupture_txt = ""
        if self.ruptures and self.config.rupture.enabled:
            rupture_txt = self.ruptures.prompt_text()
        charged_txt = ""
        if self.ick and self.config.ick.enabled:
            charged_txt = self.ick.prompt_text()
        diet_txt = ""
        own = []
        if self.diet:
            db = self.diet.brief()
            if db:
                own.append(db)
        if self.seen_images:
            # the pictures she stopped on are memory, not taste: today's are
            # still in her head, an older one comes back only when what he
            # wrote reaches for it (sim/seen_images.py)
            try:
                pics = self.seen_images.today(limit=3)
                if pics:
                    own.append(t("pictures you stopped on in your feed today (yours; bring one up only if it fits):",
                                 "今日フィードで目に留まった写真（あなた自身のもの。合うときだけ話に出す）:")
                               + "\n" + "\n".join(f"- {p}" for p in pics))
                back = self.seen_images.recall(cue_text)
                if back:
                    when = t("yesterday", "昨日") if back["days"] <= 1 else t(f"{back['days']} days ago", f"{back['days']}日前")
                    own.append(t(f"a picture you stopped on in your feed {when}: {back['noticed']} (@{back['author']})",
                                 f"{when}フィードで目に留まった写真: {back['noticed']}（@{back['author']}）"))
            except Exception as e:
                logger.log(f"[persona] pictures not read: {type(e).__name__}: {e}")
        if own:
            # "not his" only means something to a character who has a chat
            # with him and a taste of his to have drifted away from
            diet_head = (t("## What you are into lately (your own things, not his)",
                           "## 最近あなたがはまっているもの（彼のものではなく、あなた自身のもの）")
                         if existence.has_chat(self.config) else
                         t("## What you are into lately (your own things)",
                           "## 最近あなたがはまっているもの（あなた自身のもの）"))
            diet_txt = "\n\n" + diet_head + "\n" + "\n".join(own)
        japan_txt = ""
        _zg = self.zeitgeist
        if _zg:
            try:
                zb = _zg.brief()
                if zb:
                    japan_txt = ("\n\n" + t(
                        "## Going on in Japan this week (what you have seen on your phone or heard; it is just the air, not a topic)",
                        "## 今週の日本の話題（携帯で見たか、耳に入ったもの。空気であって、話題にするものではない）") + "\n" + zb)
            except Exception:
                japan_txt = ""
        national_txt = ""
        _hz = self.hazards
        if _hz:
            try:
                national_txt = _hz.national_text()
            except Exception:
                national_txt = ""
        # What makes her do a thing, what stops her, and what it gets her:
        # her own mechanisms file, built by the program because a person's
        # mechanisms are that person's. It changes when the file changes and
        # never during a day, so it rides in the system half; the one line
        # that says a standing mode of hers is on right now moves hourly and
        # is carried instead.
        mechanisms_txt, stressmode_txt = "", ""
        if self.mechanisms:
            try:
                mechanisms_txt = self.mechanisms.section()
                line = self.mechanisms.mode_line()
                if line:
                    stressmode_txt = "\n\n" + tag(
                        t("## What has been going on with you for a while now\n",
                          "## しばらく前から続いていること\n") + line,
                        "stressmode", weight=0.9)
            except Exception as e:
                logger.log(f"[persona] her own mechanisms not read: {type(e).__name__}: {e}")
        # What is already fixed in the days ahead: the calendar, her promises,
        # what he said he would do, who the day's plan has taken out of it
        # (`sim/agenda.py`). It is here rather than in what she carries
        # because it settles once a day and moves only when one of those
        # things lands, and its dates are written absolutely for the same
        # reason -- a countdown would rewrite the block every midnight.
        agenda_txt = ""
        if self.agenda:
            try:
                agenda_txt = self.agenda.prompt_text()
            except Exception as e:
                logger.log(f"[persona] the coming days not read: {type(e).__name__}: {e}")
        self._sections = {"bible": self.bible, "backstory": back_txt, "selfbeliefs": selfbeliefs_txt, "spiral": spiral_txt, "rupture": rupture_txt, "sentiment": sentiment_txt, "beliefs": beliefs_txt, "facts": facts_txt, "charged": charged_txt, "shelf": shelf, "notes": notes_txt,
                          "cast": cast_txt, "selfmem": selfmem_txt, "diary": diary_txt, "weekly": weekly_txt, "diet": diet_txt, "reflect": reflect_txt, "claims": claims_txt, "japan": japan_txt, "national": national_txt,
                          "mechanisms": mechanisms_txt, "agenda": agenda_txt, "stressmode": stressmode_txt, "style": self.style}
        return self._assemble(self._sections)

    def system_for(self, channel="him", cue_text=""):
        """ONE assembly for every call that writes her words. `him` is the
        whole of it with `style.md` last; `friend` is the same person, byte
        for byte, without `style.md` (how she writes to HIM) -- the caller
        adds its own tail. Two assemblies were how her friend turns carried
        none of her interior for eleven days: every section added to one was
        added to one. `tools/smoke.py` fails if these two ever diverge by
        more than `style.md`.

        This is the half of her prompt that changes about once a day. The
        half that moves during a day -- what she knows about him, her notes,
        what she is carrying -- is `carried_for()`, and every caller of this
        puts that block after the thread, in the final user message, so a
        new fact costs the cache only itself (`persona/sections.py`)."""
        base = self._system(cue_text)
        if channel == "him":
            return base
        return self._assemble(dict(self._sections, style="")).rstrip()

    def frame_line(self, his=True):
        """The line in her final turn that says what follows it is his.

        The third public piece of her request, beside `system_for` and
        `carried_for`: the system half, what she carries, and the one line
        that separates it from his newest messages. `sim/thread.py:place_tail`
        puts it there and `sim/thread.py:TAIL_FRAME` / `TAIL_FRAME_NONE` are
        the wordings, so a caller assembling her prompt outside this class --
        a bench, a replay, a persona-card harness -- gets the bytes the
        running bot sends rather than a copy of them.

        `his=False` is the line for a turn with nothing of his under it: there
        is no message of his to answer and she is writing first. Only his own
        messages go under the frame in his room, so those are the two wordings
        that turn can end on -- and after them the closing line
        (`sim/thread.py:closing_line`), which is the last thing she reads."""
        return _thread.frame_line(self.config, his=his)

    # The one wording of each half, so the reader that gets both and the
    # reader that gets only the situation say the same thing about it.
    CARRY_HEAD = ("WHAT SHE IS CARRYING RIGHT NOW (her own, exactly as she has it in front "
                  "of her; you are reading it, it is not addressed to you):\n")
    SITUATION_HEAD = ("HER SITUATION RIGHT NOW (exactly as she has it in front of her; the "
                      "second person in it is her, not you):\n")

    def judge_situation(self, situation=None, scene=None, digest=None):
        """Her situation block alone, headed, for a role that judges her.

        The second reader of everything she carries was handed her whole
        assembly and the carrying block with it; it gets this and nothing
        else (his call). `situation` is the block the caller has already
        built for this very minute -- the bytes she is being sent -- and
        without one it is built here the way `judge_view` builds it. The
        slot marker goes: the reader is what fills it.
        """
        if situation is None:
            situation = self._judge_build(scene, digest)[1]
        situation = str(situation or "").replace("\n@@SLOT@@", "")
        return (self.SITUATION_HEAD + situation) if situation.strip() else ""

    def judge_view(self, scene=None, digest=None):
        """What she has in front of her this minute, for a role that JUDGES her.

        A judge -- the warmth reader, the urge picker, the reply predictor, the
        account sorter -- is a neutral party and gets no character sheet
        (`Config.ROLE_STANCE`, his call 2026-09-05). It does get what she has:
        the same situation block and the same `<carrying>` block the persona
        would be sent, built HERE and NOW by the same two calls, so a reader of
        both prompts sees the same text.

        Built fresh, never the last reply's copy: `carried_for()` returns the
        sections of the last `_system` build, and the situation is rebuilt every
        tick, so a cached block would put the previous turn's afternoon in front
        of a role deciding what she wants now. Both are string assembly over the
        store -- no model call, nothing written, and the persona's own draft is
        not run.

        Returns "" when the persona is not built far enough to answer, because a
        judge with less to go on is the state every judge was in before this
        existed, and a judge that raises is a turn nobody takes.
        """
        carried, situation = self._judge_build(scene, digest)
        parts = []
        if carried:
            parts.append(self.CARRY_HEAD + carried)
        headed = self.judge_situation(situation) if situation else ""
        if headed:
            parts.append(headed)
        return "\n\n".join(parts)

    def _judge_build(self, scene=None, digest=None):
        self._peek = True
        try:
            if scene is None:
                scene = (getattr(self.director, "current", None) or {}) if self.director else {}
            if digest is None:
                digest = (self.phone.latest_digest() if self.phone else "") or ""
            unread = self.store.unread_user_messages() or []
            # the same order the reply path uses: the system half first, because
            # `carried_for` reads the sections that build lays down
            self._system(self._thread_cue())
            carried = self.carried_for()
            situation = self._situation(scene, digest, unread, "")
        except Exception as e:
            logger.log(f"[judge] what she has could not be built for a judge: "
                       f"{type(e).__name__}: {e}")
            return "", ""
        finally:
            self._peek = False
        return carried, situation

    def carried_for(self):
        """The `<carrying>` block: the CARRIED sections of the last `_system`
        build, in order, framed in her language. The same block in both
        rooms -- one person. Call after `system_for`/`_system`, and after
        `memory.fit` when the call fits its budget, so what she carries is
        what was fitted."""
        frame = self.t("(what you carry into this moment: yours, known to you already; none of it was said in the chat)",
                       "（いま持ち込んでいるもの。あなた自身のもので、すでに知っていること。チャットで言われたことではない）")
        return _sections.carried(self._sections, self._facts_head(), frame=frame)

    def _assemble(self, s):
        """The system half in the one order (`persona/sections.py`), which the
        context view reads back in as well."""
        return _sections.assemble(s, self._facts_head())

    def _own_people_as_yours(self, text):
        """Her own household in the block of her friends' people, addressed
        to her. A character promoted out of a roster is on the roster she
        reads, so the world's orbit hands her her own sister as「香芝玲奈's
        little sister」: the possessive of her own name becomes "your"."""
        ch = self.config.character
        out = text
        for nm in {str(getattr(ch, "name_ja", "") or ""), str(getattr(ch, "name", "") or "")}:
            if not nm:
                continue
            out = out.replace(f"{nm}'s ", "your ").replace(f"{nm}の", "あなたの")
        return out

    def _facts_head(self):
        """The heading over what she knows of him, in the program's words for
        how she knows it -- or "" for a character with no contact with him
        (`with_him: none`), which drops the section rather than carrying an
        empty one addressed to a girl with a boyfriend."""
        ex = self.config.character.existence
        if str(getattr(ex, "with_him", "chat") or "chat").lower() == "none":
            return ""
        return self.t(*sight.w2(self.config, "facts_head"))

    def _thread_cue(self):
        """What the thread is asked with: the messages of his she has not
        answered yet. One owner, because the situation block asks the thread
        what this same cue brings back before it pins a line about the past
        (`_phone`), and two spellings of the question would answer it
        differently."""
        return "\n".join(str(m.get("text") or "") for m in (self.store.unread_user_messages() or []))

    def _history(self):
        """One thread, both rooms (sim/thread.py). There is no other history:
        a thread that fails is a missed reply, never a thinner one."""
        return self.thread.build(cue_text=self._thread_cue())

    def _directed(self):
        """A feeling of hers that is aimed at somebody other than him, said so:
        he may get the edge of it, he is not its cause."""
        try:
            src = self.state.sources(ja=self.ja)
        except Exception:
            return ""
        him = self.state._him_key() or "him"
        if self.ja:
            from sim.lang import gauge_ja
            parts = [f"あなたの{gauge_ja(k)}({self.state.gauges.get(k, 0):.0f})は{who}に向いていて、彼に向いているのではない: {why}"
                     for k, (who, why) in src.items() if who != him]
            return ("; ".join(parts) + " -- とばっちりで彼に当たることはあっても、原因は彼ではない。聞かれない限り説明しない。") if parts else ""
        parts = [f"your {k} ({self.state.gauges.get(k, 0):.0f}) is at {who}, not at him: {why}" for k, (who, why) in src.items() if who != him]
        return ("; ".join(parts) + " -- he may get the edge of it, he is not its cause, and you do not explain it unless he asks") if parts else ""

    def _primitives_line(self):
        """What he is to her, as things stand, for the situation block.

        Silent when nothing has happened -- a row of zeros read as a
        description of a feeling is the thing `sim/primitives.py` exists to
        stop, and an empty string here is the honest output for a character
        who has just met somebody."""
        prim = getattr(self.state, "primitives", None)
        if prim is None:
            return ""
        key = self.state._him_key() or "him"
        try:
            line = prim.line(key, ja=self.ja)
        except Exception:
            return ""
        if not line:
            return ""
        return self.t("WHERE HE STANDS WITH YOU: ", "彼はあなたにとって今どういう相手か: ") + line

    def _primitives_gates(self):
        """What is not available to her with him, as conditions rather than
        numbers.

        The line above is a description of a feeling and a model does what it
        likes with a description. These are the same gates the code enforces --
        the ick is not scored, withholding has no pressure, a rupture cannot
        open -- so what she is told and what the machinery does are one
        statement instead of two. Only what is shut, and only once something
        has happened."""
        prim = getattr(self.state, "primitives", None)
        if prim is None:
            return []
        try:
            return prim.gate_lines(self.state._him_key() or "him", ja=self.ja)
        except Exception:
            return []

    def _situation(self, scene, digest, unread, impulse_reason, just_read=None, looked_up=None, recalled=None, shape=None):
        """The now, in order of weight: who she is being right now (feelings,
        stance, what is aimed where), then him (the silence, the receipts,
        his rhythm), then her day (body, scene, events, plans, money), then
        what is on her phone, then this message and the budget. The block
        used to be assembled in the order the subsystems were written, with
        "hungry" beside "angry, holding it in" and a rhythm statistic from
        the last exchange presented as now; the model picked what it liked.

        One builder per part (`_her`, `_him`, `_day`, `_phone`, `_this`),
        each reading the same moment (`_moment`: the clocks, the silence,
        the day's events) and returning its lines; `_admit` is the attention
        gate over the first four and the lore, and it is what sets the slot
        `_draft` fills."""
        m = self._moment(scene, digest, unread, impulse_reason, just_read, looked_up, recalled, shape)
        her = self._her(m)
        him = self._him(m)
        day = self._day(m)
        phone = self._phone(m)
        this = self._this(m)
        lines = self._admit(m, her, him, day, phone, this)
        return "<situation>\n" + "\n".join(lines) + "\n</situation>"

    def _moment(self, scene, digest, unread, impulse_reason, just_read, looked_up, recalled, shape):
        """What every part of the block reads: the call's arguments, her
        clock, the day's events and yesterday, the silence measured up to
        the message she is reading now, and today's plan."""
        m = SimpleNamespace(scene=scene, digest=digest, unread=unread, impulse_reason=impulse_reason,
                            just_read=just_read, looked_up=looked_up, recalled=recalled, shape=shape)
        m.now = self.clock.now()
        m.t, m.ja = self.t, self.ja
        m.cs = cs = self.config.situation_block
        t, ja, now = m.t, m.ja, m.now
        today_events = [e for e in self.store.events_for_date(self.clock.date_str()) if e["salience"] >= 2][-cs.events_max:]
        m.ev_txt = "; ".join(f"{self.clock.hm(e['ts'])} {_clip(e['text'], cs.event_chars)}" for e in today_events) or t("nothing much", "特に何も")
        recent_days = [d for d in self.store.recent_days(1) if d["summary"]]
        m.y_txt = ""
        if recent_days:
            d = recent_days[0]
            age = (now.date() - datetime.date.fromisoformat(d["date"])).days
            if ja:
                label = "昨日" if age == 1 else "今日ここまで" if age == 0 else f"{age}日前、はっきり覚えている最後の日（{d['date']}）"
            else:
                label = "yesterday" if age == 1 else "today so far" if age == 0 else f"{age} days ago, the last day you have a clear memory of ({d['date']})"
            m.y_txt = f"{label}: {_clip(d['summary'], cs.summary_chars)}"
        # the silence is measured up to the message she is reading now, not from it
        m.before = before = unread[0]["ts"] if unread else self.clock.now_ts()
        m.recent = recent = self.store.recent_messages(400)
        m.prior = prior = [m_ for m_ in recent if m_["role"] == "user" and m_["ts"] < before]
        m.silent_h = (self.clock.now_ts() - prior[-1]["ts"]) / 3600 if prior else 999.0
        m.gap_txt = ""
        if prior:
            gap_h = (before - prior[-1]["ts"]) / 3600
            if gap_h >= 24:
                days = int(gap_h // 24)
                if ja:
                    m.gap_txt = (f"これの前に彼から連絡が来たのは{days}日前。" if unread
                                 else f"彼から最後に連絡が来たのは{days}日前。")
                else:
                    m.gap_txt = (f"before this, the last time he messaged you was {days} days ago." if unread
                                 else f"the last time he messaged you was {days} days ago.")
        sched = self.store.get_schedule(self.clock.date_str())
        m.notes = sched["notes"] if sched else ""
        return m

    def _her(self, m):
        """Her, right now: the clocks, how she feels, how she is answering,
        what is aimed where, and the draft she cut."""
        t, ja, cs, now = m.t, m.ja, m.cs, m.now
        his_now = self.clock.user_now()
        # Two clocks only when there are two: a character with no world of her
        # own lives on his machine and on his clock, and "for him it is the
        # same time -- do not assume his time of day from yours" was the first
        # line she read every message.
        if self.config.character.existence.in_world:
            # The gap between the two clocks, computed. It was only ever in
            # her bible, as a number written into the prose ("many hours behind you") beside two anchors that both put him asleep while
            # she is about -- so her late evening, which is his morning and
            # the hours she actually texts in, had nothing to fix it, and she
            # opened three messages in four days with "you awake?" at his 08:10, 09:20 and 10:30.
            off = self.clock.offset_hours()
            gap_en = f", {abs(off):.0f} hours {'behind' if off > 0 else 'ahead of'} you"
            gap_ja = f"、あなたより{abs(off):.0f}時間{'遅れている' if off > 0 else '進んでいる'}"
            # the same word the record's labels carry, from the same place
            # (`WorldClock.char_zone_word`): the situation and the thread must
            # not name her clock two different ways, and which city she is in
            # is the clock's business rather than a literal in shared code
            zone = self.clock.char_zone_word()
            clock_line = t(f"it is {_when(now)} ({_daypart(now.hour)}) for you in {zone}. "
                           f"for him it is {_when(his_now)} ({_daypart(his_now.hour)} his time){gap_en} -- "
                           f"do not assume his time of day from yours, and whether he is awake is "
                           f"something his own clock answers.",
                           f"{zone}にいるあなたの時間は{_when(now, True)}（{_daypart(now.hour, True)}）。"
                           f"彼のいるところは{_when(his_now, True)}（彼の時間で{_daypart(his_now.hour, True)}）"
                           f"{gap_ja}。"
                           f"自分の時間から彼の時間帯を決めつけない。彼が起きているかどうかは、彼の時計を見れば分かること。")
        else:
            clock_line = t(f"it is {_when(his_now)} ({_daypart(his_now.hour)}), his clock and yours.",
                           f"いまは{_when(his_now, True)}（{_daypart(his_now.hour, True)}）。彼の時計で、あなたの時計でもある。")
        her = [tag(clock_line, "clock", pin=True),
               tag(t("you feel: ", "いまの気分: ") + self.state.mood_tags(ja=self.ja), "feel", pin=True)]
        reg = self.state.register(ja=self.ja)
        if reg:
            # Pinned where a stance table exists, and only there. It is the
            # one line whose whole job is to steer manner and it was droppable
            # at 0.80 while a feeling tag that is permanently true was pinned
            # above it -- but a pin is scarce, and for a character whose
            # section says only what the register says, taking the pin is
            # taking it from something else.
            staged = bool(self.stances is not None and self.stances.enabled)
            her.append(tag(t("how you are answering right now: ", "いまの返し方: ") + reg, "register", pin=staged))
        # What she does with what she has seen: one named stance out of a
        # ranked table, decided in code (`sim/stances.py`), naming the thing
        # she actually saw. Pinned, because a line the gate can drop is not an
        # instruction, and stashed for `_draft`, which lets the stance own the
        # slot.
        self._stance = None
        # A judge's copy of the situation must not DRAW anything: entering a
        # stance is a write, and the reply built a moment later would then see
        # a different one. `judge_view` sets `_peek`, and the two lines that
        # draw are the stance and the over-the-shoulder glimpse below.
        if self.stances is not None and not getattr(self, "_peek", False):
            try:
                his = "\n".join(str(x.get("text", "")) for x in (m.unread or []))
                self._stance = self.stances.current(his)
            except Exception as e:
                logger.log(f"[stance] not read: {type(e).__name__}: {e}")
        if self._stance and self._stance.get("line"):
            her.append(tag(t("what you are doing with what you have seen: ",
                             "見てしまったものに対して、いまのあなたの構え: ") + self._stance["line"],
                           "stance", pin=True))
        d = self._directed()
        if d:
            her.append(tag(d, "directed"))
        for src, line in (("attachment", _grab(self.attachment, "situation_line", ja)),
                          ("withholding", _grab(self.withholding, "situation_line", ja))):
            if line:
                her.append(tag(line, src))
        unsent = self.store.get("unsent_draft") or {}
        if unsent.get("text") and (self.clock.now_ts() - float(unsent.get("ts", 0))) / 3600 <= cs.unsent_hours:
            her.append(tag(t("what you nearly sent earlier and cut (not sent; it is still in you): ",
                             "さっき送りかけてやめたもの（送っていない。まだ自分の中に残っている）: ")
                           + _clip(unsent["text"].replace("\n\n", " / "), cs.unsent_chars), "unsent"))
        return her

    def _him(self, m):
        """Him: what he is to her, the silence, the receipts, the gap he just
        ended, his rhythm and mood, and what she expects, foresees and
        wonders. A read of him older than the silence is not "now": the
        rhythm notice and his mood only stand while the exchange is live."""
        t, ja, cs = m.t, m.ja, m.cs
        unread, prior, recent, silent_h = m.unread, m.prior, m.recent, m.silent_h
        him = []
        # what he actually is to her, made of what has happened and nothing
        # else. Silent for a character who has no primitives, and silent for
        # one who has them and to whom nothing has happened yet.
        pl = self._primitives_line()
        if pl:
            if getattr(cs, "primitives_numbers", True):
                him.append(tag(pl, "primitives", pin=True))
        for g in self._primitives_gates():
            him.append(tag(g, "gate", pin=True))
        # A visual novel has no read receipt and no away channel: he is at the
        # stage or the story is not happening. When the reunion clock is on
        # (`sim/reunion.py`, `character.existence.player_driven`) what she knows
        # is when he was last here, and the phone-era silence lines are not
        # shown at all. A character without the clock keeps them unchanged.
        if self.reunion is not None and self.reunion.enabled():
            rl = self.reunion.line(ja=ja)
            if rl:
                him.append(tag(rl, "reunion", pin=True))
        else:
            felt = self.state.felt_gap_text(silent_h, ja=ja) if prior and not unread else ""
            if felt:
                him.append(tag(felt + ".", "felt"))
            if self.receipts and not unread:
                rl = self.receipts.line(self.receipts.status(), ja=ja)
                if rl:
                    him.append(tag(rl, "receipts"))
            # the gap he just ended. Every silence line above is skipped while
            # unread is on the table (a read of him older than the silence is not
            # "now"), so at the one moment she was answering the message that
            # ENDED a gap, nothing said the gap had happened -- she met a
            # four-hour vanish like a ten-second volley. The fact only; whether
            # she remarks on it is hers.
            if unread and prior:
                back_h = (unread[0]["ts"] - prior[-1]["ts"]) / 3600.0
                if back_h >= self.config.delivery.gap_marker_hours:
                    hers_between = any(m_["role"] == "assistant" and prior[-1]["ts"] < m_["ts"] < unread[0]["ts"] for m_ in recent)
                    him.append(tag(t(f"this message of his ends {_gap_text(back_h)} of quiet on his side -- you had answered him and he was gone that long."
                                     if hers_between else
                                     f"he is texting again {_gap_text(back_h)} after his last, with nothing from you in between.",
                                     f"この彼のメッセージで、彼の側の{_gap_text(back_h, True)}の沈黙が終わった。あなたは返事をしていて、その間ずっと彼はいなかった。"
                                     if hers_between else
                                     f"彼の前のメッセージから{_gap_text(back_h, True)}あいて、また彼から来た。その間あなたからは何も送っていない。"),
                                   "gap", weight=min(0.95, 0.6 + back_h / 24.0)))
        r = self.rhythm
        rl = _grab(r, "brief", ja)
        if rl:
            him.append(tag(rl, "rhythm"))
        # the pace notice reads the latency of the very message she is
        # answering, so it is fresh on a comeback too -- "slower than he
        # usually is at this hour" is exactly the schedule sense the
        # live-hours gate was hiding behind unread
        if silent_h <= cs.live_hours or unread:
            nl = _grab(r, "notices", ja)
            if nl:
                him.append(tag(nl, "rhythm", weight=0.6 if unread else None))
        if silent_h <= cs.live_hours:
            hm = self.state.his_mood_line(ja=ja)
            if hm:
                him.append(tag(f"{hm}.", "his_mood"))
        exp_obj = self.expectations
        exp = _grab(exp_obj, "situation_line", ja)
        # Whether this line is something to DO. The control arm keeps the test
        # it has always used -- looking for "did not" inside the rendered
        # sentence -- because a rendered byte could turn on it. Every other arm
        # asks the record, which is the only form of the question that survives
        # the sentence being written in another language.
        from sim.lang import control as _control
        exp_unmet = (("did not" in (exp or "")) if _control(self.config)
                     else bool(_grab(exp_obj, "has_unmet")))
        for src, line, kind in (("foresight", _grab(self.foresight, "situation_line", ja), "fact"),
                                ("expectations", exp, "action" if exp_unmet else "fact"),
                                ("wonder", _grab(self.wonder, "situation_line", ja), "fact"),
                                ("nag", _grab(self.anime_sense, "nag_line", ja), "action")):
            if line:
                him.append(tag(line, src, kind=kind))
        if m.gap_txt:
            him.append(tag(m.gap_txt, "gap_days"))
        return him

    def _day(self, m):
        """Her day: her body, the household, the scene as background, what
        is around her, hazards, today's events, goals, promises, the ledger,
        how she travels, money, the day's shape, yesterday, the morning and
        the anticipation, and a line of scenery lore."""
        t, ja, cs, scene, notes = m.t, m.ja, m.cs, m.scene, m.notes
        day = []
        sl = _grab(self.situation, "persona_line")
        if sl:
            day.append(tag(t("your body right now: ", "いまの体の状態: ") + sl, "body"))
        hh = self.household
        if hh:
            try:
                hl = hh.situation_line(ja=ja)
                if hl:
                    day.append(tag(hl, "household", kind="fact", pin=True))
            except Exception as e:
                logger.log(f"[household] not shown to her: {type(e).__name__}")
        # the scene is manner, not material: it shapes how she types, and
        # handing it over unlabelled taught her to narrate it back at him
        # ("i'm on the floor with wet hair", four messages running)
        #
        # KNOWN DEFECT, half fixed (PROJECT §19, HANDOVER): the scene's
        # `inner` line, the impulse line below and the morning thought arrived
        # as finished prose IN HER VOICE, sitting just above the instruction to
        # write, and she transcribed them -- 17 characters out of one, 21 out
        # of the other, ellipsis-lead included. The director's line is now a
        # thought described, and labelled so (sim/director.py); the morning
        # thought still arrives as prose.
        day.append(tag(t("right now, around you (background: it colours how you type, it is not something to report to him): ",
                         "いまあなたの周りにあるもの（背景。打ち方に色がつくだけで、彼に報告するものではない）: ")
                       + scene_brief(scene), "scene", pin=True))
        around = _grab(self.body, "persona_line", ja)
        if around:
            day.append(tag(t("around you: ", "身の回り: ") + around, "around"))
        hb = _grab(self.hazards, "brief")
        if hb:
            day.append(tag(hb + ".", "hazards", pin=True))
        day.append(tag(t("today so far: ", "今日ここまで: ") + m.ev_txt, "today"))
        gl = ""
        if self.goals and self.config.goals.enabled:
            gl = self.goals.situation_line(ja=ja)
            if gl:
                day.append(tag(gl, "goals"))
        cl = _grab(self.commitments, "situation_line", ja)
        if cl:
            day.append(tag(cl, "commitments"))
        led = self.ledger
        if led:
            try:
                lt = led.text(scene=scene, for_whom="her", ja=ja)
                if lt:
                    day.append(tag(lt, "ledger"))
            except Exception:
                pass
        # what a place actually costs her to reach, off the map, because she
        # told him she would do her homework "on the bus" and there is no bus
        # in her world. She has the fact; without it in front of her the model
        # picks a vehicle that sounds right for a school trip.
        sit = self.situation
        # how she gets anywhere, and what a trip costs her. Both are about a
        # body moving through a world; `situation` is switched off for a
        # character who has neither, and the block called it anyway -- she
        # was being told she has a bike and a father who drives.
        if sit and self.config.situation.enabled:
            tv = _grab(sit, "travel_line")
            if tv:
                day.append(tag(tv, "travel"))
            try:
                day += [tag(t, "trip") for t in sit.trip_lines([cl, gl, notes], limit=cs.trip_lines,
                                                             min_minutes=cs.trip_min_minutes)]
            except Exception:
                pass
        ml = _grab(self.money, "persona_line") if self.config.money.enabled else ""
        if ml:
            day.append(tag(ml, "money"))
        if notes:
            day.append(tag(t("the shape of today: ", "今日一日の流れ: ") + _clip(notes, cs.summary_chars), "shape_of_day"))
        if m.y_txt:
            day.append(tag(m.y_txt, "yesterday"))
        if self.outlook:
            for src, line in (("morning", self.outlook.morning_line(ja=ja)), ("anticipation", self.outlook.anticipation_line(ja=ja))):
                if line:
                    day.append(tag(line, src))
        sl2 = _grab(self.scenery, "lore_line", ja)
        if sl2:
            day.append(tag(sl2, "lore"))
        return day

    def _phone(self, m):
        """What she sees of him and what she has looked up: the digest and
        one thing off his screen, his list when anime is in the air, her
        account, a note read, a recall, the lookups, the things she knows by
        name, and the episode he is watching."""
        t, ja, cs = m.t, m.ja, m.cs
        digest, unread, looked_up, just_read, recalled = m.digest, m.unread, m.looked_up, m.just_read, m.recalled
        phone = []
        resident = str(getattr(self.config.character.existence, "sees_him", "digest")).lower() == "resident"
        if digest:
            # `Phone.latest_digest` says whether any of it is current: when he
            # has not touched the machine for a while it leads with the absence
            # and puts the digest behind it as history. Nothing is added here.
            #
            # A resident character does not look at an app: she is inside the
            # machine and simply sees it, so the line names what is in front of
            # her rather than a thing she went and checked.
            # Pinned for the resident: she is inside the machine and this IS
            # what she sees. At the phone section's weight it was the first
            # thing the budget dropped -- `dropped: digest(0.70)` on four
            # replies running on 2026-09-02 -- so the director had his whole
            # evening and she had none of it.
            # A fresh one rides once, as news. After that it competes like
            # anything else at `digest_stale_weight`, so it reaches her when
            # the conversation reaches for it rather than on every call: she
            # reported something off his machine in 29 of 95 replies at the
            # same rate whether or not he had asked her anything (32% either
            # way, `data/retired/20260904_010103_voice_audit/REPORT.md` §4.3),
            # and a rate that does not move with what he said is a slot being
            # filled, not a person noticing something.
            #
            # The narration is the first line of what she is handed; the live
            # tail after it is rebuilt on every call, so a freshness test over
            # the whole string would call a day-old picture new every time.
            parts = [p for p in str(digest).split("\n") if p.strip()]
            narration, tail = parts[0], parts[1:]
            fresh = self._digest_is_news(m)
            phone.append(tag(t(*sight.w2(self.config, "digest_line")) + narration, "digest",
                             pin=resident and fresh,
                             weight=None if fresh else float(getattr(cs, "digest_stale_weight", 0.25))))
            # The live tail only when it has changed since she was last shown
            # one. "not touching anything this minute", handed over again on
            # the next call and the one after, is not something that happened.
            live = "\n".join(tail)
            if live and live != (self.store.get("persona_live_shown") or {}).get("text"):
                phone.append(tag(live, "digest_live", kind="fact"))
                self.store.set("persona_live_shown", {"ts": self.clock.now_ts(), "text": live})
            # And one thing out of it that she is going to say something about.
            #
            # The slot -- the line the gate marks as "in this message, in your
            # own words" -- is held by the heaviest line of kind `action`, and
            # every action source in this file belongs to a subsystem she has
            # not got: the weekly list nag, and two lines from an account. So
            # her slot read `none` on every reply of her life and the machine
            # she lives in arrived as background she was never asked to remark
            # on. She watches him all day and mentions none of it, which is the
            # complaint, and it was structural rather than a matter of wording.
            #
            # This is the resident's action source: one concrete thing off his
            # screen, offered as something to say rather than as scenery. It is
            # charged a showing only when it actually held the slot, the same
            # as every other action, so a thing she has already remarked on
            # does not come round again.
            # (`eyes`, not `sight`: `sight` is the words module this function
            # reads above, and a local of that name shadowed it for the whole
            # function, which killed every reply of both characters once)
            eyes = self.sight
            # also drawn once and retired, so a judge's copy leaves it for her
            # (`judge_view`, `_peek`)
            if eyes is not None and hasattr(eyes, "noticed_line") and not getattr(self, "_peek", False):
                seen = eyes.noticed_line(digest, t)
                if seen:
                    # a fact she can see, not an action she must take: as an
                    # action it rode the slot under "this is in this message",
                    # and she remarked on his browsing in every reply
                    phone.append(tag(seen, "noticed", kind="fact"))
        elif not resident:
            # and she cannot have "not opened it recently" either -- there is
            # no opening, so the honest line is no line
            phone.append(tag(t(*sight.w2(self.config, "digest_none_recent")), "digest"))
        # what he has open in front of him THIS MINUTE, when her sight can
        # see it (the page for a work; hers to act on when she was in it)
        eyes = self.sight
        glance = getattr(eyes, "glance_lines", None) if eyes is not None else None
        # not for a judge's copy: what she catches over his shoulder is drawn
        # once and retires, and a judge must leave it for her (`judge_view`)
        if glance and not getattr(self, "_peek", False):
            try:
                for line, kind, pin in glance(t):
                    phone.append(tag(line, "glance", kind=kind, pin=pin))
            except Exception as e:
                logger.log(f"[glance] not shown: {type(e).__name__}")
        recent = list(unread or []) + self.store.recent_messages(6)
        anime_air = False
        if self.anime_sense:
            try:
                anime_air = self.anime_sense.anime_in_the_air(recent, looked_up)
            except Exception:
                anime_air = False
        # his list is in her head only when anime is what they are talking about
        if anime_air and self.mal and self.mal.enabled:
            latest = self.mal.latest_watching(t=t)
            if latest:
                phone.append(tag(t("his anime list, last time you looked: ", "最後に見たときの彼のアニメリスト: ") + latest, "anime_list"))
        if anime_air and self.anime_sense and self.config.anime_sense.situation_line:
            al = _grab(self.anime_sense, "situation_line", ja)
            if al:
                phone.append(tag(al + t(*sight.w2(self.config, "anime_list_suffix")), "anime_list"))
        # her account, his likes, what she posted. `social` is switched off
        # for a character with no world, and the block called it anyway --
        # she was being told what she had done on an account she has not got.
        if self.social and self.config.social.enabled:
            for src, line, kind in (("x_recent", self.social.recent_line(), "fact"),
                                    ("his_likes", self.social.his_likes_line(), "fact"),
                                    ("his_follows", self.social.his_follows_line(), "fact"),
                                    ("her_actions", self.social.her_actions_line(), "fact"),
                                    ("share", self.social.share_line(), "action"),
                                    ("show_him", _grab(self.social, "show_him_line"), "action"),
                                    ("engagement", _grab(self.social, "engagement_line"), "fact"),
                                    ("followers", _grab(self.social, "followers_line"), "fact"),
                                    ("replies_in", _grab(self.social, "replies_line"), "fact")):
                if line:
                    phone.append(tag(line, src, kind=kind))
        if just_read:
            phone.append(tag(t(*sight.w2(self.config, "note_read_line", basename=just_read['basename']))
                             + just_read['takeaway'], "note_read", pin=True))
        if recalled:
            from sim.recall import Recall
            # not if the conversation she is remembering is one the thread is
            # about to put in front of her in full: the exact words and a
            # compiled line about them are one cue answered twice
            # (`sim/thread.py brought_back`, `docs/memory.md` §5). The memory
            # itself is kept and the continuity editor still gets it; only the
            # pinned line goes.
            covered = False
            try:
                covered = Recall.already_in_thread(recalled, self.thread.brought_back(self._thread_cue()))
            except Exception as e:
                logger.log(f"[recall] the thread was not asked what it is bringing back: {type(e).__name__}")
            if covered:
                logger.log("[recall] the exchange itself is coming back into the thread in full; "
                           "the line she remembered is not restated in the situation")
            else:
                phone.append(tag(Recall.situation_line(recalled, self.config), "recall"))
        if looked_up:
            phone.append(tag(t(f"something he said sent you to look '{looked_up['term']}' up just now, while his message sat there ({looked_up.get('source', '')}): {looked_up['gist']} (use it or not; he does not know you looked)",
                               f"彼が言ったことが気になって、返事を書く前に『{looked_up['term']}』をいま調べた（{looked_up.get('source', '')}）: {looked_up['gist']}（使っても使わなくてもいい。調べたことを彼は知らない）"),
                             "lookup", pin=True))
            # and whether the thing he named is a work of HERS. The page she
            # fetched says what the show is and nothing about whose it is, so
            # a synopsis in front of her was the whole of what she had when
            # she claimed a part in one (2026-09-04). Pinned with the lookup
            # it belongs to: a correction that the attention budget can drop
            # is not a correction.
            _v = works.verdict_line(self.config, looked_up.get("role"), looked_up["term"], t)
            if _v:
                phone.append(tag(_v, "role_check", kind="fact", pin=True))
            if looked_up.get("overview"):
                label = looked_up.get("overview_label", t("what that is", "それが何か"))
                phone.append(tag(t(f"{label} (you know it now, in your own words -- do not recite this): {looked_up['overview']}",
                                   f"{label}（もう知っていること。自分の言葉で。ここに書いてあることをそのまま読み上げない）: {looked_up['overview']}"),
                                 "lookup", pin=True))
            if looked_up.get("episode_beats"):
                phone.append(tag(t(f"what actually happens in {looked_up['term']} episode {looked_up.get('episode')} (react to it as something you know, do not narrate a summary): {looked_up['episode_beats']}",
                                   f"『{looked_up['term']}』第{looked_up.get('episode')}話で実際に起きること（知っていることとして反応する。あらすじを語らない）: {looked_up['episode_beats']}"),
                                 "lookup", pin=True))
        # What she looked up a little earlier -- the last few, inside a window --
        # so a conversation about a thing goes on across messages instead of
        # starting again from a fact fragment (his call: "do both").
        try:
            lc = self.config.lookup
            horizon = self.clock.now_ts() - float(getattr(lc, "situation_hours", 6.0) or 6.0) * 3600
            cur = (looked_up or {}).get("term")
            # only a lookup that was worth keeping as a known thing rides the
            # window: a record with no `known_key` is one made before results
            # were judged, and one of those -- a person's name answered with a
            # random show -- sat in her prompt for an evening
            from sim.known import KnownThings as _KT
            still = _KT(self.config, self.store, self.clock).keys()
            recent = [r for r in (self.store.get("lookups", []) or [])
                      if float(r.get("ts") or 0) >= horizon and r.get("term") != cur and r.get("gist")
                      and r.get("known_key") in still]
            for r in recent[-int(getattr(lc, "situation_max", 3) or 3):]:
                phone.append(tag(t(f"a little earlier you looked up '{r['term']}' ({r.get('source', '')}): {r['gist']} (yours to use; he does not know you looked)",
                                   f"少し前に『{r['term']}』を調べた（{r.get('source', '')}）: {r['gist']}（使っていい。調べたことを彼は知らない）"),
                                 "lookup_recent", pin=True))
        except Exception as e:
            logger.log(f"[lookup] recent not shown: {type(e).__name__}")
        # Things she KNOWS, by name: anything he looked up or watched before,
        # brought back by a name in what he just wrote (sim/known.py). No
        # window: みつば a week later is still みつば.
        try:
            from sim.known import KnownThings
            known = KnownThings(self.config, self.store, self.clock)
            his_text = "\n".join(str(m_.get("text") or "") for m_ in (unread or []))
            skip = set()
            if looked_up and looked_up.get("known_key"):
                skip.add(looked_up["known_key"])
            for r in known.recall(his_text, exclude=skip):
                phone.append(tag(KnownThings.situation_line(r, t, self.config), "known", pin=True))
        except Exception as e:
            logger.log(f"[known] not recalled: {type(e).__name__}")
        # An episode he PLAYED and that has since reached her -- as he
        # played it, for a character who is on his machine, or in the next
        # snapshot she went and fetched, hours later, for one who is not
        # (`WatchingHim.note_seen`; the moment is the program's). Nothing is
        # here at all until it has reached her.
        watching = self.watching
        if watching:
            try:
                # EVERYTHING he has played since she last looked, grouped by
                # work, newest first -- not only the last file he opened.
                # `grouped_lines` renders the single-episode case as the one
                # line it always was, so the common turn is unchanged.
                #
                # PINNED: the attention budget dropped the synopsis line at
                # the phone section's default weight the first time an episode
                # of his came up in chat (2026-09-02 19:41), and she answered
                # a question about the show from the model's own memory. What
                # he is watching and what happens in it is not a line that
                # competes for room; it is the reason the module exists.
                for line in watching.grouped_lines(ja=ja):
                    phone.append(tag(line, "watching", kind="fact", pin=True))
            except Exception as e:
                logger.log(f"[watching] situation failed: {type(e).__name__}")
        return phone

    def _digest_is_news(self, m):
        """Whether what she is holding about his machine was built since she
        last wrote to him.

        Pinned, it was the one line in her prompt that could not be dropped,
        and she had the same picture in front of her on the fourth reply of an
        exchange as on the first. This is the question a person would ask of
        it: has anything been added since I last spoke."""
        try:
            # the newest row there is, not today's: at ten past midnight the
            # newest picture is yesterday's, and a date lookup would call it
            # news every call until the collector flushes again
            rows = self.store.recent_digests(1)
            if not rows:
                return True
            built = float(rows[-1]["ts"])
        except Exception as e:
            logger.log(f"[digest] not aged: {type(e).__name__}")
            return True
        hers = [x["ts"] for x in (m.recent or []) if x.get("role") == "assistant"]
        return (not hers) or built > max(hers)

    def _own_phrases(self):
        """The phrases she has been reaching for lately, out of her own recent
        messages. Code counts them and no model reads anything: character
        n-grams that turn up in at least `own_phrases_min` of her last
        `own_phrases_from` messages.

        A coinage of hers is written back into her prompt by the roles that
        read her record, and then she is looking at her own last good line
        every call: her name for him appeared in ten replies over twelve
        hours after the role that writes her private thoughts put it back in
        front of her, and one self-close the tape makes about once a
        ninety-minute show she made every fourth message
        (`data/retired/20260904_010103_voice_audit/REPORT.md` §4.4).

        Three exclusions, each a different kind of not-a-tic. The grammatical
        furniture of the language and her own name in every form -- read off
        her sheet, never spelled here -- are not phrases anybody chooses. A
        phrase her own speech guide contains is a marker the guide asks of her
        (her endings, her hedges, her stalls), and listing those would be
        telling her to stop sounding like herself. And a phrase he has used in
        the same window is the subject they are both on, not something of
        hers."""
        cs = self.config.situation_block
        want = int(getattr(cs, "own_phrases_from", 16) or 0)
        if want <= 0:
            return []
        try:
            msgs = self.store.recent_messages(want * 4)
        except Exception as e:
            logger.log(f"[own phrases] not read: {type(e).__name__}")
            return []
        hers = [str(x.get("text") or "") for x in msgs if x.get("role") == "assistant"][-want:]
        his = "\n".join(str(x.get("text") or "") for x in msgs if x.get("role") == "user")
        if len(hers) < 3:
            return []
        if self._phrase_mask is None:
            ch = self.config.character
            names = [getattr(ch, "name_ja", ""), getattr(ch, "name", "")]
            names += str(getattr(ch, "reading_ja", "") or "").split()
            self._phrase_mask = sorted({x for x in list(_FURNITURE) + names if x}, key=len, reverse=True)
        guide = (self.style or "") + (self.bible or "")
        seen = {}
        for i, text in enumerate(hers):
            for run in _runs(text, self._phrase_mask):
                for n in range(3, 11):
                    for k in range(len(run) - n + 1):
                        seen.setdefault(run[k:k + n], set()).add(i)
        floor = int(getattr(cs, "own_phrases_min", 4) or 4)
        counts = {p: len(w) for p, w in seen.items()
                  if len(w) >= floor and p not in his and p not in guide}
        out = []
        for p in sorted(counts, key=lambda x: (-len(x), -counts[x])):
            if not any(p in q for q in out):
                out.append(p)
        out.sort(key=lambda p: (-counts[p], -len(p)))
        return out[:int(getattr(cs, "own_phrases_max", 5) or 5)]

    def _this(self, m):
        """This message: what she is answering or why she is writing, the
        shape's engagement line, the closing instruction and the length,
        which is the last thing she reads."""
        t = m.t
        unread, impulse_reason, shape = m.unread, m.impulse_reason, m.shape
        this = []
        if unread:
            this.append(t(f"he sent {len(unread)} message(s) and you are reading them now.",
                          f"彼から{len(unread)}通来ていて、あなたはいまそれを読んでいる。"))
        elif impulse_reason:
            if getattr(self, "_intent_kind", "") == "place_notice":
                this.append(t(f"he just chose the place around you, and you are noticing that place now. {impulse_reason}",
                              f"彼が今あなたのいる場所を選び、あなたはその場所に気づいている。{impulse_reason}").strip())
            elif getattr(self, "_intent_kind", "") == "arrival":
                this.append(t(f"he has just come back to the stage after a long time away. {impulse_reason}",
                              f"彼が長いこと離れていて、いま戻ってきた。{impulse_reason}").strip())
            else:
                this.append(t(f"he has not messaged. you feel like texting him anyway. {impulse_reason}",
                              f"彼からは来ていない。それでも自分から送りたい気分でいる。{impulse_reason}").strip())
        if shape:
            if shape.get("engage"):
                this.append(shape["engage"])
        # what she has been reaching for lately, so that she can hear it.
        # Not a ban: a phrase is named and nothing is said about what to put
        # in its place.
        own = self._own_phrases()
        if own:
            joined = "; ".join(own)
            this.append(t("phrases of your own you have used again and again in your last few messages, and he has had every one of them from you already: "
                          + joined
                          + ". nobody says the same thing every fourth message; say it another way, or say something else.",
                          "直近の自分の返事で何度も使っている言い回し。どれももう彼に出したもの: "
                          + joined
                          + "。同じ言い回しを四通に一度ずつ出す人はいない。別の言い方にするか、別のことを言う。"))
        spillish = bool(shape) and shape["kind"] == "spill"
        this.append(closing_instruction(self.config, spillish=spillish,
                                        place_notice=getattr(self, "_intent_kind", "") == "place_notice"))
        # the length is the LAST thing she reads before writing, so the first
        # draft comes out the right size and no redraft is needed (it used to
        # be a mid-list "how much" line the model overshot, then a second call
        # cut it -- wasted output)
        if shape and shape.get("line"):
            # the count is restated here because this is the last thing she
            # reads: the second character was told "two or three bubbles" here
            # and returned three lines joined by single newlines, which the
            # splitter reads as one bubble
            this.append(t("LENGTH -- this is how much you send right now: ", "長さ -- いま送るのはこれだけ: ") + shape["line"]
                        + t(" A BLANK LINE between each bubble, and no quotation marks around any of them.",
                            " 吹き出しと吹き出しのあいだは空行。どれにもかぎ括弧はつけない。"))
        elif shape is not None:
            # told nothing about length, so the last thing she reads is the one
            # rule that survives it (`shape.tell_length` false)
            this.append(t("no quotation marks around what you send.", "送るものにかぎ括弧はつけない。"))
        return this

    def _admit(self, m, her, him, day, phone, this):
        """The attention gate over the four parts and the lore: what is kept,
        and the one line that holds the slot `_draft` fills. Without the
        gate, everything, in order. Sets `_gate_slot_line`, `_gate_pick`,
        `_cand_lines`, `_action_sources` and `_candidates` for `_draft` and
        the nudge."""
        t, cs, unread, shape = m.t, m.cs, m.unread, m.shape
        att = self.attention
        if not (att and self.config.attention.enabled):
            return her + him + day + phone + this
        cue = "\n".join(str(m_.get("text", "")) for m_ in (unread or []))
        # What she can be reminded of is asked of the CONVERSATION, not of
        # his newest message alone. Two reasons, and the second is the one
        # that was missing. A subject arrives over several turns, so the
        # message that finally reaches for a memory often does not name the
        # thing -- he says the name once and then says "what was that
        # like". And **her own words are a cue**: she is the one who
        # brought up her programme, so what she has just said should be
        # able to remind her of the rest of it, exactly as his words can.
        #
        # The two sides go down separately because they are not worth the
        # same. His naming reaches a record however often he names it; hers
        # reaches one she has not been told yet, and stops reaching one she
        # has already told him, because her own telling sits in this window
        # for the next few turns and would otherwise pull the same anecdote
        # back on every call (sim/lore.py).
        lore_cue, lore_echo = cue, ""
        try:
            back = int(getattr(self.config.lore, "cue_exchanges", 3)) * 2
            if back > 0:
                recent = self.store.recent_messages(back)
                lore_cue = "\n".join([str(m_.get("text", "")) for m_ in recent
                                      if m_.get("role") == "user"] + [cue])
                lore_echo = "\n".join(str(m_.get("text", "")) for m_ in recent
                                      if m_.get("role") != "user")
        except Exception as e:
            logger.log(f"[lore] recent turns not read: {type(e).__name__}")
        # what she happens to know, if this moment reached for any of it.
        # Usually nothing: the retrieval only answers when the conversation
        # actually touches a record, and it competes for room here against
        # what she is doing rather than arriving as a separate authority.
        lore = []
        lr = self.lore
        if lr is not None:
            try:
                # An episode he has just watched is part of what this
                # moment is about even when his message is "this is
                # good". Without the show's own Japanese name in the cue,
                # a record about the part she plays in it cannot be
                # reached from anything short he types.
                w = self.watching
                watched = ""
                if w:
                    cur = w.current() or {}
                    watched = str(cur.get("ja") or "")
                lore = lr.lines(lore_cue, context_text=watched, echo_text=lore_echo)
            except Exception as e:
                logger.log(f"[lore] not retrieved: {type(e).__name__}: {e}")
        # The one imperative line is not given to the thing she is braced
        # against. What the live prediction says may land badly is matched
        # against each action (`Attention.veto_from_text`); a hit rides as a
        # plain line instead of as an order.
        veto = None
        overlap = int(getattr(self.config.attention, "foresight_veto_overlap", 0) or 0)
        if overlap and self.foresight is not None:
            try:
                veto = att.veto_from_text(_grab(self.foresight, "risk_text"), overlap)
            except Exception as e:
                logger.log(f"[attention] the foresight veto was not built: {type(e).__name__}: {e}")
        kept, slot, report = att.admit({"her": her, "him": him, "day": day,
                                        "phone": phone, "lore": lore}, cue_text=cue, veto=veto)
        # the one thing on her mind goes where she will actually read it:
        # last but for the length line. The gate's pick is stashed with
        # everything it saw; `_draft` fills the marker -- with the nudge's
        # reading when there is one, else with this pick
        self._gate_slot_line = slot
        self._gate_pick = str(slot) if slot else ""
        self._cand_lines = [l for ls in (her, him, day, phone) for l in ls if l]
        # What the second reader is shown is what the gate let through: the
        # lines it kept, and the actions still waiting their turn. A claim a
        # heavier source already made, a repeat, and an action the floor or
        # the foresight kept out of the slot are not offered to it, because
        # it may not put back what code has decided against.
        last = getattr(att, "last", {}) or {}
        queued = [l for l in (last.get("queued") or []) if l]
        demoted = {id(l) for l in (last.get("demoted") or []) if l}
        keptset = {id(l) for l in kept}
        offer = {id(l) for l in queued} | (keptset - demoted)
        if slot:
            offer.add(id(slot))
        # the things she carries that can be DONE, as against what she knows
        self._action_sources = {getattr(l, "source", "") for l in (queued + ([slot] if slot else []))
                                if getattr(l, "source", "")}
        # the same lines twice: as the text the second reader is shown, and
        # keyed on their tags, because what it picks is one of them and it
        # answers with the tag rather than with a wording of its own
        rows, self._cand_by_source = [], {}
        for sec, ls in (("her", her), ("him", him), ("day", day), ("phone", phone)):
            for l in ls:
                if not l or id(l) not in offer:
                    continue
                key = str(getattr(l, "source", "") or sec).lower()
                mark = "* " if (id(l) in keptset or (slot is not None and l is slot)) else "  "
                todo = " · to do" if getattr(l, "kind", "") == "action" else ""
                rows.append(f"{mark}[{key}{todo}] " + str(l)[:300])
                self._cand_by_source.setdefault(key, str(l))
        self._candidates = "\n".join(rows)
        this.insert(len(this) - 1 if shape else len(this), "@@SLOT@@")
        logger.log(report)
        # A retrieved line is not something happening now, and every other
        # line in this block is. Without a header it reads as an event and
        # she answers it; with the wrong header it reads as a brief and she
        # recites. So it is labelled as memory and the label says plainly
        # that saying it is not what is being asked for.
        if lore:
            loreset = {id(l) for l in lore}
            at = next((i for i, l in enumerate(kept) if id(l) in loreset), None)
            if at is not None:
                if getattr(cs, "lore_preamble", "full") == "short":
                    pre = t("things you have known for years, which this came near (not a list, not a subject to raise):",
                            "前から知っていること。話が近くを通っただけ（リストでも話題でもない）:")
                else:
                    pre = t(
                    "things you happen to know, because this came near them. NOT a list to get "
                    "through and NOT a subject to raise: you have known all of it for years, so "
                    "none of it is news to you and none of it is worth announcing. If it does not "
                    "come out of you naturally in this reply, leave it alone and say nothing about it.",
                    "話がたまたま近くを通ったので出てきた、あなたが前から知っていること。消化するリストでもなければ、"
                    "持ち出す話題でもない。どれも何年も前から知っていることで、あなたにとっては新しくないし、"
                    "わざわざ言うほどのことでもない。この返事で自然に出てこないなら、そのままにして何も言わない。")
                kept = kept[:at] + [pre] + kept[at:]
        return kept + this

    def generate(self, scene, digest, unread, impulse_reason="", just_read=None, looked_up=None, recalled=None, intent_kind=""):
        """Returns (bubbles, voice_line). voice_line is '' when she said nothing aloud.
        A continuity editor (separate model, prompts/editor.txt) reads the draft
        against what she demonstrably knows; on a real contradiction she gets
        one rewrite with a plain note about what she does know. A character
        whose sheet says she has not got the check gets no call and no evidence
        bundle, and a draft that says again what she has just said is logged
        (`_repeats_recent`) and sent as written."""
        # The current turn's kind must be set before `_situation` builds its
        # "this message" instruction. Otherwise it reads the previous turn.
        self._intent_kind = str(intent_kind or "")
        shape = self.shape_engine.draw(unread, intent_kind=intent_kind, scene=scene)
        self._slot_fill = None
        situation = self._situation(scene, digest, unread, impulse_reason, just_read, looked_up, recalled, shape=shape)
        self._looked_up = looked_up
        self._recalled = recalled
        # why she is writing at all when nothing of his is waiting: the urge,
        # as it is already stated to her in the situation block, for the
        # closing line at the very end of the prompt (`_draft`)
        self._impulse_reason = str(impulse_reason or "")
        # what kind of unprompted turn this is, so the closing line reads the
        # arrival as a scene opening and not as her reaching for him
        # The staging pass (`sim/scene.py`): where she is being shown, decided
        # before her draft is written and appended INSIDE the situation block
        # -- the fast half, never the cached system prompt (`docs/context.md`
        # §1), so the system prefix stays byte-identical across turns.
        if self.scene_director is not None:
            try:
                staged = self.scene_director.run(scene)
                block = self.scene_director.guidance_block(staged)
                if block:
                    situation = situation.replace("\n</situation>", "\n" + block + "\n</situation>")
            except Exception as e:
                logger.log(f"[scene] not staged: {type(e).__name__}: {e}")
        bubbles, voice = self._draft(situation)
        # what she asked to look up before sending (`[search: ...]` on its
        # own line in her draft): one search, and the reply written again
        # with what she found in front of her. Code decides that it happens
        # once and how often in a day; she decides what to ask.
        asked = getattr(self, "_search_asked", "")
        self._search_asked = ""
        if asked and self.lookup is not None and getattr(self.config.lookup, "on_request", False):
            rec = self.lookup.search(asked, why="she wanted to know it before answering him",
                                     by="her", access=(scene or {}).get("phone_access"))
            if rec and rec.get("from_known"):
                # She asked for a thing she was already holding, so no search
                # ran and telling her one did is how she came to say "I just
                # looked it up" about things she had simply been handed.
                found = self.t(f"you already knew this one, from before he asked ('{asked}', {rec.get('source') or 'from earlier'}): {rec['gist']} -- "
                               f"say it as something you have known, not as something you have just this moment gone and looked up.",
                               f"これはもう知っていた（『{asked}』・{rec.get('source') or '前に読んだもの'}）: {rec['gist']} -- "
                               f"前から知っていることとして言う。いま調べたことにはしない。")
            elif rec:
                found = self.t(f"you just looked this up, before sending ('{asked}'): {rec['gist']} -- it is something you know now, in your own words; "
                               f"if it says the thing does not exist or the answer is not there, say that plainly rather than guess.",
                               f"送る前に、いま調べたこと（『{asked}』）: {rec['gist']} -- もう知っていることとして、自分の言葉で。"
                               f"存在しない、あるいは答えが見つからないと出ているなら、推測せずそう言う。")
            if rec:
                situation = situation.replace("\n</situation>", "\n" + found + "\n</situation>")
                bubbles2, voice2 = self._draft(situation)
                if bubbles2:
                    bubbles, voice = bubbles2, voice2 or voice
            else:
                logger.log(f"[search] she asked and nothing came back; the first draft stands: {asked}")
        # a reply to him in the other room's language is FLAGGED, never
        # redrafted: the write line at the bottom says English, and a draft
        # that disobeys it is a signal about the prompt (his rule: flag,
        # never rewrite her dialogue). One Japanese reply on 2026-08-31.
        #
        # It has to read the same setting the write line is built from
        # (`writes_to_him`, above). It did not, so for the character whose
        # chat with him IS Japanese it fired on every single reply -- five out
        # of five on her first conversation -- and wrote a row into `flags`
        # each time, which is the store where a real voice problem is supposed
        # to stand out.
        writes_ja = str(getattr(self.config.character, "writes_to_him", "english")).lower().startswith("ja")
        if (bubbles and not writes_ja and getattr(self.config.delivery, "language_flag", True)
                and _mostly_japanese(" ".join(bubbles))):
            # and it says what she was answering when it fires. At 20:07 on
            # 2026-09-05 there was nothing of his under the frame and five
            # group-chat turns in Japanese stood above it, which is why she
            # wrote Japanese; the flag said only that she had, so the prompt
            # was not the first place anyone looked.
            _t = getattr(self, "_last_tail", None) or {}
            why = ""
            if not _t.get("his"):
                why = "; nothing of his was under the frame line"
                if _t.get("others"):
                    why += f" and {_t['others']} turn(s) of her other rooms stood above it in the record"
            logger.log("[persona] FLAG: she answered him in Japanese although the write line said "
                       "English; sent as written" + why)
            try:
                rows = list(self.store.get("flags", []) or [])
                rows.append({"ts": self.clock.now_ts(), "date": self.clock.date_str(), "what": "she answered him in Japanese",
                             "text": " ".join(bubbles)[:200], "tail": dict(_t)})
                self.store.set("flags", rows[-100:])
            except Exception:
                pass
        # she has no picture of her own to give him (sim/reconcile.py); flagged
        # where the words go out, never rewritten
        for b in (bubbles or []):
            reconcile.flag_own_photo(b, "her message to him", self.store, self.clock)
        if bubbles and not self.config.delivery.editor_enabled:
            # Her drafts are not read for continuity: her sheet says she has
            # not got the check (`mechanisms_absent`, put into effect by
            # `Config.NAMED_SWITCHES`). No call, no evidence bundle, and no
            # line per reply -- the one line about it is at boot, so a day with
            # the check off cannot be mistaken for a day of clean drafts.
            #
            # What survives is the only fault it really caught for her, and the
            # gate had already been finding that one in code for nothing: she
            # is saying again something she said earlier today. Logged, and her
            # words are not touched -- a check flags and never rewrites her
            # dialogue, and here there is nothing even to flag it to.
            said = self._repeats_recent(" ".join(str(b) for b in bubbles))
            if said:
                logger.log(f"[repeat] {said} -- sent as written; her drafts are not read for continuity")
        elif bubbles:
            why = self._editor_needed(bubbles) if getattr(self.config.delivery, "editor_gate", True) else "the gate is off"
            verdict = self._edit(bubbles, situation, digest, just_read) if why else None
            if not why:
                logger.log("[editor] skipped: the draft repeats nothing recent and claims no fact")
            elif verdict and verdict.get("ok", True):
                logger.log(f"[editor] ok ({why})")
            if verdict and not verdict.get("ok", True) and self._rests_on_his_list(
                    verdict, bubbles, digest, just_read):
                verdict = None
            if verdict and not verdict.get("ok", True) and verdict.get("note_for_her"):
                logger.log(f"[editor] contradiction: {verdict.get('problem', '')[:200]}")
                note = self.t(f"\n(continuity, before you send: {verdict['note_for_her'].strip()} Rewrite in your own words; stay in character.)",
                              f"\n（送る前に、話のつじつま: {verdict['note_for_her'].strip()} 自分の言葉で書き直す。あなたのままで。）")
                bubbles2, voice2 = self._draft(situation + note)
                if bubbles2:
                    bubbles, voice = bubbles2, voice2 or voice
                    self.store.add_event(self.clock.now_ts(), self.clock.date_str(), "editor", f"rewrite: {verdict.get('problem', '')[:200]}", 1)
        # The draft guard (`sim/quality.py`): the slop, a repeat, a run shared
        # with her own last message, and the length. Post-processing on what
        # she wrote, never a change to her prompt; off for a character whose
        # bundle does not turn it on.
        if self.quality is not None and bubbles:
            try:
                bubbles, _qnotes = self.quality.review(bubbles)
                for _n in _qnotes:
                    logger.log(f"[quality] {_n}")
            except Exception as e:
                logger.log(f"[quality] not run: {type(e).__name__}: {e}")
        # no post-hoc enforcement: the drawn length is the last line of her
        # prompt, so the draft is the right size as written. Whatever she
        # wrote is what she sends.
        tag = f" [{shape['kind']}]" if (shape and shape.get("kind")) else ""
        logger.log(f"[persona]{tag} {len(bubbles)} bubble(s): " + " // ".join(b[:80] for b in bubbles) + (f" | voice: {voice}" if voice else ""))
        # The prompt these bubbles came out of, filed under them. Taken here,
        # after the editor and the search re-draft have settled which draft
        # stands and BEFORE the compare draft below, which overwrites
        # `last_messages` with a prompt she was never sent. Nothing is written
        # to the save yet: it is filed against a message row by
        # `persona/delivery.py` once a bubble has actually left.
        self.last_reply_prompt = {
            "messages": list(getattr(self, "last_messages", None) or []),
            "model": self.llm.effective_model("persona"),
            "params": {k: v for k, v in (self.config.model("persona") or {}).items()
                       if k in ("temperature", "thinking", "effort", "max_tokens")},
            "usage": dict(getattr(self, "last_draft_usage", None) or {}),
            "provider": self.llm.active_provider(),
            "bubbles": list(bubbles or []), "voice": voice or ""}
        # the ongoing test: the same prompt once more with the gate's line in
        # the slot instead of the nudge's; logged and kept, never sent
        try:
            if (self.config.nudge.compare and getattr(self, "_slot_from_nudge", False)
                    and self.nudge and unread):
                alt, _v = self._draft(situation, slot_override=getattr(self, "_gate_fill", ""))
                nl = getattr(self.nudge, "last", {}) or {}
                copied = _copied(" ".join(bubbles), (nl.get("do", "") + " " + nl.get("attend", "")))
                rec = {"ts": self.clock.now_ts(), "him": [str(m.get("text", ""))[:200] for m in unread][-3:],
                       "do": nl.get("do", ""), "do_source": nl.get("do_source", ""), "attend": nl.get("attend", "")[:200],
                       "heavy": nl.get("heavy", False), "gate": (self._gate_pick or "")[:160],
                       "with": [b[:300] for b in bubbles], "without": [b[:300] for b in alt], "copied": copied}
                self.store.set("nudge_ab", ((self.store.get("nudge_ab", []) or []) + [rec])[-60:])
                logger.log(f"[nudge-ab] without the nudge she would have sent {len(alt)} bubble(s): " + " // ".join(b[:80] for b in alt)
                           + (f" | she copied {copied} consecutive word(s) from the nudge" if copied >= 4 else ""))
        except Exception as e:
            logger.log(f"[nudge-ab] compare draft failed: {type(e).__name__}: {e}")
        return bubbles, voice

    def _his_heavy(self):
        """Is his last message heavy -- sad, angry, hurt -- by the state
        model's reading of it (`his_mood`: valence -2..2), and fresh? Code's
        timing for the slot: the nag straight after he told her something
        bad is the case the second reader was first built for, and this is
        the mechanical half of it."""
        c = self.config.attention
        try:
            # `state.his_mood()` is the faded view (valence eased toward 0 by
            # the hours since, `hours` the age, no `ts`); the raw read is the
            # kv. The first version looked for `ts`, found none, called every
            # read stale, and the hold never fired on 2026-08-31
            m = self.state.his_mood() or {}
            raw = self.store.get("his_mood") or {}
            if not m and not raw:
                return False, ""
            if m.get("hours") is not None:
                age_min = float(m["hours"]) * 60
            else:
                age_min = (self.clock.now_ts() - float(raw.get("ts", 0) or 0)) / 60
            if age_min > float(getattr(c, "heavy_fresh_minutes", 30)):
                return False, ""
            val = float(raw.get("valence", m.get("valence", 0)) or 0)
            if val <= float(getattr(c, "heavy_valence", -1)):
                return True, str(m.get("line") or raw.get("line") or "")
        except Exception:
            pass
        return False, ""

    def _draft(self, situation, slot_override=None):
        """`slot_override` is the compare draft: the same prompt with this
        text in the slot instead of the nudge's, nothing decided or charged."""
        history = self._history()
        # the MOMENT is the cue for what comes back to her: what he just
        # wrote, her own last line, and the scene she is in. His newest
        # message alone -- which is what this was -- left where she is, who
        # she is with and what she herself had just said cueing nothing
        # (sim/recall.py: moment_cue, the same cue the record search uses)
        his = history[-1]["content"] if history and history[-1]["role"] == "user" else ""
        cue = recall.moment_cue(self.store, his_text=his)
        system = self._system(cue_text=cue)
        if self.memory:
            # the meter: nothing is trimmed here or anywhere below the one
            # target, which the thread's window fits itself to (sim/memory.py)
            self._sections, history, notes = self.memory.fit(self._sections, history, situation)
            self.memory.measure(self._sections, history, situation, notes)
        # what she carries rides after the thread, with the situation: the
        # system prompt and the thread stay a cached prefix across calls
        carried = self.carried_for()
        whole = system + ("\n\n" + carried if carried else "")
        if "@@SLOT@@" in situation and slot_override is not None:
            situation = situation.replace("\n@@SLOT@@", ("\n" + slot_override) if slot_override else "")
        elif "@@SLOT@@" in situation:
            # The stance owns the slot where there is one. Code has already
            # decided what she does with what she saw, so nothing competes for
            # the one imperative line: the nudge is not consulted and the
            # gate's pick does not ride. A stance that says do not raise it
            # holds the slot empty on purpose. This is an ownership rule in
            # code rather than a config accident -- `nudge.enabled` being false
            # for a character is a setting, and a setting can be changed by
            # somebody who does not know it was load-bearing.
            st = getattr(self, "_stance", None) or {}
            if self._slot_fill is None and st.get("claims_slot"):
                header = self.t("ON YOUR MIND NOW -- this is in this message, in your own words: ",
                                "いま頭にあること -- これはこのメッセージに、自分の言葉で入れる: ")
                self._slot_from_nudge = False
                self._gate_fill = ""
                self._slot_fill = (header + st["slot_text"]) if st.get("slot_text") else ""
                logger.log(f"[stance] {st.get('key', '')} holds the slot: "
                           + (str(st.get("slot_text"))[:110] if st.get("slot_text") else "empty, on purpose"))
            # decided once per generate (the editor's rewrite reuses it): the
            # nudge reads the very same system and history she is about to get
            if self._slot_fill is None:
                # the line states what happens; no line she reads offers a
                # choice (a model offered one takes the way out every time)
                text = self._gate_pick
                header = self.t("ON YOUR MIND NOW -- this is in this message, in your own words: ",
                                "いま頭にあること -- これはこのメッセージに、自分の言葉で入れる: ")
                att = self.attention
                nd = self.nudge
                picked, src = "", ""
                self._gate_fill = (header + text) if text else ""
                self._slot_from_nudge = False
                # the gate's line rides on every reply, stated, so she
                # addresses what she carries on her own. The one thing that
                # holds it is code's read of his last message: a heavy one
                # (his_mood.valence at or under attention.heavy_valence,
                # fresh) is no moment for the nag or a link
                heavy, hline = self._his_heavy()
                if text and heavy:
                    logger.log(f"[attention] the {getattr(self._gate_slot_line, 'source', '') or 'slot'} line waits: he sounds {hline[:80]}")
                    text, header = "", ""
                if nd and nd.enabled("him"):
                    # what she carries warms the unsaid while it waits; the
                    # nudge is its reader at the threshold -- the snap, the
                    # push-back -- not a call on every message
                    nd.carried(len(getattr(self, "_action_sources", None) or ()))
                    fires, lv = nd.due("him")
                    if fires:
                        try:
                            picked = nd.run(self.judge_situation(situation), history,
                                            self._candidates, self._gate_pick, channel="him",
                                            allowed=getattr(self, "_action_sources", None), level=lv,
                                            offered=getattr(self, "_cand_by_source", None))
                        except Exception as e:
                            logger.log(f"[nudge] not run: {type(e).__name__}: {e}")
                if picked:
                    self._slot_from_nudge = True
                    text, header = picked, ""
                    src = str((getattr(nd, "last", {}) or {}).get("do_source", "") or "")
                    # the line the decision came from rides under it: a
                    # paraphrase loses the [share: ID] token and the titles
                    orig = next((str(l) for l in (getattr(self, "_cand_lines", None) or []) if getattr(l, "source", "") == src), "") if src else ""
                    if orig and orig[:60] not in text:
                        text += self.t("\n  (what it is about: ", "\n  （何についてか: ") + orig + self.t(")", "）")
                    if att and src:
                        att.charge_source(src)
                elif att and text == self._gate_pick and self._gate_slot_line:
                    att.charge(self._gate_slot_line)
                self._slot_fill = (header + text) if text else ""
            situation = situation.replace("\n@@SLOT@@", ("\n" + self._slot_fill) if self._slot_fill else "")
        tail = (carried + "\n\n" + situation) if carried else situation
        # what she carries and the situation first, the newest messages last
        # behind a line that names who wrote them and says the rest was not
        # said to her at all (sim/thread.py)
        from sim.thread import place_tail, tail_run
        # what the answering-now block will hold. Two readers: the closing
        # line, which says whether she is answering him or writing first, and
        # the language check below, where a draft in the wrong language after
        # a block with nothing of his in it is a different fault from one
        # after his own message.
        _h, _b, _his, _others = tail_run(history)
        self._last_tail = {"his": len(_his), "others": len(_others)}
        # the last thing she reads: where this message goes, whether it
        # answers him or she is writing first and why, and the language of
        # this room. The end of the prompt is its strongest position, and the
        # instruction naming the room and the urge that made her write both
        # sit inside the situation block, with the whole tail under them.
        _writes_ja = str(getattr(self.config.character, "writes_to_him", "english")).lower().startswith("ja")
        closing = _thread.closing_line(self.config, language=("japanese" if _writes_ja else "english"),
                                       why=getattr(self, "_impulse_reason", ""), first=not _his)
        history = place_tail(history, tail, self.frame_line(), self.frame_line(his=False), closing)
        messages = [{"role": "system", "content": system}] + history
        # The exact prompt this draft went out on, and what the call cost.
        # Kept so the same call can be made again later -- a swipe -- against
        # the state as it WAS: her gauges, her scene and the thread have all
        # moved by then, and a prompt rebuilt at that point would answer a
        # different question.
        self.last_messages = messages
        out = self.llm.call("persona", messages, on_delta=self.stream_sink).strip()
        self.last_draft_usage = dict(getattr(self.llm, "last_usage", None) or {})
        if self.memory:
            u = getattr(self.llm, "last_usage", {}) or {}
            if u.get("role") == "persona":
                self.memory.calibrate(sum(len(m["content"]) for m in messages), u.get("prompt_tokens", 0))
        out, voice = self._extract_voice(out)
        out = self._clean(out)
        return self._split(out), voice

    def _knowledge(self, digest, just_read, bubbles=None, situation=""):
        """What she demonstrably knows right now, for the editor. Compact."""
        parts = []
        facts = self.store.user_facts()
        if facts:
            parts.append("FACTS ABOUT HIM:\n" + "\n".join(f"- {f}" for f in facts[-40:]))
        if self.mal and self.mal.enabled:
            sv = self.config.sensor_view
            shelf = self.mal.shelf_summary(sv.mal_shelf_watching_max, sv.mal_shelf_completed_max)
            if shelf:
                parts.append("HIS ANIME LIST (she sees this):\n" + shelf)
        if self.notes:
            idx = self.notes.index_text()
            if idx:
                parts.append("NOTES OF HIS SHE HAS READ:\n" + idx)
        # How she knows is the program's to say (sim/sight.py): an editor told
        # the resident had an app binned a true remark about his uptime as a
        # leak (2026-09-02 23:01).
        if digest:
            parts.append(sight.w(self.config, "editor_digest_label") + digest)
        if just_read:
            parts.append(sight.w(self.config, "editor_note_label", basename=just_read['basename']) + just_read['takeaway'])
        if getattr(self, "_looked_up", None):
            lu = self._looked_up
            parts.append(f"SHE JUST LOOKED UP '{lu['term']}': {lu['gist']}")
        if getattr(self, "_recalled", None):
            parts.append(f"WHAT SHE REMEMBERS ABOUT WHAT HE REFERRED TO ({self._recalled.get('clarity', '')}): {self._recalled['memory']}")
        if self.ick:
            hot = self.ick.carrying()
            if hot:
                # she knows these and is not going to say them; the editor must not
                # read her silence about them as her not knowing
                parts.append("THINGS SHE KNOWS ABOUT HIM AND IS DELIBERATELY NOT RAISING:\n" + "\n".join(f"- {it['what']}" for it in hot))
        # Which works named here are hers, and which are provably not. The
        # bundle had twelve labelled blocks and not one of them named a work
        # of her own, so the checker had nothing to hold a claim about her
        # career against: on 2026-09-04 it caught the REPETITION when she said
        # a false part a second time and had no view at all on the claim. A
        # verdict off the machine's mirror is a checkable fact, so the answer
        # is "that is false" rather than "that is a matter of voice".
        try:
            _extra = []
            _w = self.watching
            if _w is not None:
                _it = _w.current()
                if _it and _it.get("role"):
                    _extra.append((_it.get("ja") or _it.get("title") or "", _it["role"]))
            _eyes = self.sight
            _g = getattr(_eyes, "current_glance", None) if _eyes is not None else None
            _gl = _g() if _g else None
            if _gl and _gl.get("role"):
                _extra.append((_gl.get("subject") or "", _gl["role"]))
            _texts = [" ".join(bubbles or [])] if getattr(self.config.role_check, "titles_from_draft", True) else []
            _texts.append(str(digest or ""))
            _roles = works.editor_facts(self.config, self.store, _texts + [str(situation or "")],
                                        extra=_extra)
            if _roles:
                parts.append(_roles)
        except Exception as e:
            logger.log(f"[roles] the editor's list of her works was not built: {type(e).__name__}")
        cl = self.store.get("self_claims", [])[-30:]
        if cl:
            parts.append("WHAT SHE HAS TOLD HIM ABOUT HERSELF (she must not contradict these):\n" + "\n".join(f"- {c['text']}" for c in cl))
        # The conversation. A handful of messages is about five exchanges, and
        # everything older used to be invisible to the checker, so a true
        # quotation from earlier in the day read to it as a fabrication (at
        # message 121 she referred to his having called her 本物 at message 54,
        # eight hours back, and the draft was binned). Three things fix that,
        # and none of them is a bigger window: the checker is TOLD how long the
        # record really is, the draft's own words are searched against the rest
        # of it, and the prompt says an absence here is not evidence.
        d = self.config.delivery
        recent = self.store.recent_messages(int(getattr(d, "editor_recent_messages", 10)))

        def line(m, fmt="%a %H:%M"):
            # a searched message can be months old, and "Sat 06:06" on a
            # message from May reads as this Saturday: those carry the date
            return (f"[{self.clock.to_char(m['ts']).strftime(fmt)}] "
                    f"{'HIM' if m['role'] == 'user' else 'HER'}: {m['text'][:300]}")

        try:
            n_msgs, first_date, _last = self.store.message_span()
        except Exception:
            n_msgs, first_date = 0, None
        if n_msgs > len(recent):
            parts.append(f"THE RECORD: {n_msgs} messages between them"
                         + (f" since {first_date}" if first_date else "")
                         + f". You are shown the last {len(recent)} of them, and any older one the"
                           " search below reached. The rest of the record exists and is not in front of you.")
        if recent and getattr(d, "editor_lookback", True):
            older = recall.older_messages(
                self.store, self.clock, " ".join(bubbles or []), recent[0]["ts"],
                limit=int(getattr(d, "editor_lookback_max", 5)),
                scan=int(getattr(d, "editor_lookback_scan", 1500)),
                min_overlap=int(getattr(d, "editor_lookback_min_overlap", 2)),
                common_share=float(getattr(d, "editor_lookback_common_share", 0.02)))
            if older:
                logger.log("[editor] the draft reaches back to " + ", ".join(
                    self.clock.to_char(m["ts"]).strftime("%m-%d %H:%M") for m in older))
                parts.append("EARLIER IN THE CONVERSATION (older than the messages below, found by searching "
                             "the whole record for the words of her draft. These were really said):\n"
                             + "\n".join(line(m, "%Y-%m-%d %a %H:%M") for m in older))
        if recent:
            parts.append("RECENT CONVERSATION:\n" + "\n".join(line(m) for m in recent))
        return "\n\n".join(parts)

    def _seen_of_him(self, digest, just_read):
        """What she has actually been SHOWN of him, as one text: his list as
        she reads it, the notes of his she has read, what she has been shown
        of his machine, the note she just opened.

        The second witness for a verdict that says she must know a thing. The
        conversation is deliberately not in it: his own message naming the
        thing is what she is answering, not evidence that she has ever seen
        it."""
        out = []
        try:
            if self.mal and self.mal.enabled:
                sv = self.config.sensor_view
                out.append(self.mal.shelf_summary(sv.mal_shelf_watching_max,
                                                  sv.mal_shelf_completed_max) or "")
            if self.notes:
                out.append(self.notes.index_text() or "")
        except Exception as e:
            logger.log(f"[editor] what she has been shown was not read: {type(e).__name__}")
        out.append(str(digest or ""))
        if just_read:
            out.append(str((just_read or {}).get("takeaway") or ""))
        return "\n".join(x for x in out if x)

    def _rests_on_his_list(self, verdict, bubbles, digest, just_read):
        """True when this failing verdict rests on his list holding a title
        and his list does not hold it, in which case it is dropped.

        The fault: at 07:40 on 2026-09-06 her draft said "the smoking cat one.
        it's from a short anime, i think" and the checker failed it because
        "she has seen his anime list and notes" -- without anyone asking
        whether the title is on that list. It is not, in any table of the
        machine's mirror, and the rewrite said "it's a classic". So the claim
        is checked before the verdict stands, against his own list through the
        ranked resolution and the part verdict (`sim/works.list_claim_check`,
        `docs/role-check.md` §4b). The checker gains nothing by this: it still
        only flags, and a verdict on any other ground is untouched. A verdict
        that is dropped goes in the log and in kv `flags` whole, because the
        one sentence it wrote may have carried a second, sound reason with
        it and code cannot separate the two without writing new grounds."""
        try:
            chk = works.list_claim_check(
                self.config, self.anime_kb, verdict.get("problem", ""),
                draft=" ".join(str(b) for b in (bubbles or [])),
                seen=self._seen_of_him(digest, just_read))
        except Exception as e:
            logger.log(f"[editor] the check against his list did not run: {type(e).__name__}: {e}"[:200])
            return False
        if not chk.get("rests"):
            return False
        if chk.get("verdict") != "absent":
            logger.log(f"[editor] the verdict rests on his list and stands: {chk.get('why', '')}")
            return False
        logger.log(f"[editor] verdict dropped: rests on his list, which does not hold "
                   f"{chk.get('subject', '')!r} ({chk.get('why', '')}); the verdict was: "
                   + str(verdict.get("problem", ""))[:200])
        try:
            rows = list(self.store.get("flags", []) or [])
            rows.append({"ts": self.clock.now_ts(), "date": self.clock.date_str(),
                         "what": "a continuity verdict rested on his list, which does not hold it",
                         "subject": chk.get("subject", ""), "why": chk.get("why", ""),
                         "problem": str(verdict.get("problem", ""))[:300],
                         "text": " ".join(str(b) for b in (bubbles or []))[:200]})
            self.store.set("flags", rows[-100:])
        except Exception:
            pass
        return True

    def _editor_needed(self, bubbles):
        """Is there anything in this draft for the continuity editor to
        check? Its job is a contradiction with what she demonstrably knows and
        a repeat of something she has already said. A draft with no number, no
        word from a fact about him and no run shared with a recent message of
        hers has neither, and a pass verdict does nothing (2026-09-04, the
        reply-chain audit: the check ran, said ok, and the repetition it
        exists to catch had already been banned in code in the prompt).
        Returns the reason it is needed, or "" to skip."""
        text = " ".join(str(b) for b in (bubbles or []))
        if not text.strip():
            return ""
        if re.search(r"\d", text):
            return "a number in the draft"
        low = text.lower()
        if self._repeats_recent(text):
            return "a run shared with a recent message of hers"
        try:
            facts = [str(f) for f in (self.store.user_facts() or [])[-40:]]
        except Exception:
            facts = []
        keys = set()
        for f in facts:
            keys |= set(re.findall(r"[a-z][a-z'\-]{4,}", f.lower()))
            keys |= set(re.findall(r"[぀-ヿ一-鿿]{3,}", f))
        for k in keys:
            if k in low or k in text:
                return f"a word from a fact about him ({k})"
        # A work the mirror has a verdict on. Without this the check is built
        # and never asked about the sentence it was built for: her draft
        # claiming a part in a work she has never been in carried no number,
        # no run shared with a recent message and no word from a fact about
        # him, and the log recorded the skip -- "the draft repeats nothing
        # recent and claims no fact" -- while the claim went out.
        try:
            _extra = []
            _w = self.watching
            if _w is not None:
                _it = _w.current()
                if _it and _it.get("role"):
                    _extra.append((_it.get("ja") or _it.get("title") or "", _it["role"]))
            why = works.named_in(self.config, self.store, text, extra=_extra)
            if why:
                return why
        except Exception as e:
            logger.log(f"[roles] the editor's gate could not ask about her works: {type(e).__name__}")
        return ""

    def _repeats_recent(self, text, n=8, run=12):
        """Where this draft says again what she has just said, or "".

        A run of `run` characters shared with one of her last `n` own messages,
        and the time she said it. No call, no model: this is the test the
        continuity check's gate has always run, and its finding used to decide
        only whether to PAY for the check. It is also the whole of what the
        check caught for the second character -- five of her six useful
        refusals were this, dated every time -- so it is the one thing that
        stays when her drafts are not read at all."""
        low = (text or "").lower()
        if not low.strip():
            return ""
        try:
            recent = [m for m in (self.store.recent_messages(n) or []) if m.get("role") != "user"]
        except Exception:
            recent = []
        for m in recent:
            rl = str(m.get("text") or "").lower()
            for i in range(0, max(0, len(rl) - run)):
                seg = rl[i:i + run]
                if seg.strip() and seg in low:
                    when = ""
                    try:
                        when = self.clock.to_char(m["ts"]).strftime("%H:%M")
                    except Exception:
                        pass
                    return ("she is saying again what she said" + (f" at {when}" if when else "")
                            + f": {seg.strip()!r}")
        return ""

    def _edit(self, bubbles, situation, digest, just_read):
        user = (f"WHAT SHE KNOWS:\n{self._knowledge(digest, just_read, bubbles, situation)}\n\nHER SITUATION:\n{situation}\n\n"
                f"HER DRAFT (bubbles):\n" + "\n".join(f"- {b}" for b in bubbles))
        data, raw = self.llm.call_json("editor", [{"role": "system", "content": self.config.prompt_text("editor")}, {"role": "user", "content": user}])
        return data if isinstance(data, dict) else None

    def recent_aloud(self, n=8):
        """The last things she actually said out loud, newest last."""
        try:
            with self.store.lock:
                rows = self.store.conn.execute(
                    "SELECT text FROM events WHERE kind='voice' ORDER BY ts DESC LIMIT ?",
                    (int(n),)).fetchall()
            return [r[0] for r in rows][::-1]
        except Exception:
            return []

    def voice_for(self, bubbles, scene):
        """A spoken line for a reply that came without one. Short model call, no thinking."""
        if not bubbles:
            return ""
        # What she has already said aloud. The call had the bubbles, her mood
        # and the room, and no idea it had ever spoken before: 21 near-duplicate
        # pairs in her last 40 lines, and the same sentence at 11:06 and 11:09
        # with only the punctuation moved.
        said = self.recent_aloud(int(getattr(self.config.tts, "no_repeat_recent", 8) or 8))
        aloud = ""
        if said:
            aloud = ("WHAT SHE HAS ALREADY SAID OUT LOUD (do not say any of these again, in any "
                     "words -- say something else, or say nothing):\n"
                     + "\n".join(f"- {x}" for x in said) + "\n")
        user = (f"WHERE: {scene_brief(scene)}\nFEELS: {self.state.mood_tags()}\n"
                + aloud
                + f"HER TEXT BUBBLES:\n" + "\n".join(f"- {b}" for b in bubbles))
        # the one assembly every call that writes her words is built from,
        # and then what this call is for. The cap that used to sit here was
        # 120 tokens, which a thinking model can spend before it says
        # anything; the length of a spoken line is `tts.max_chars` below.
        system = self.system_for("him") + "\n\n---\n" + self.config.prompt_text("voice")
        out = self.llm.call("voice", [{"role": "system", "content": system}, {"role": "user", "content": user}]).strip()
        out = out.strip().strip("「」\"'").split("\n")[0].strip()
        if len(out) > self.config.tts.max_chars or not out:
            return ""
        # and if it said it again anyway, she says nothing: a person muttering
        # to herself does not repeat one sentence twice in five minutes
        from sim.textutil import near_duplicate
        if any(near_duplicate(x, out, 0.72) for x in said):
            logger.log(f"[voice] she had already said that, so nothing aloud: {out[:50]!r}")
            return ""
        return out

    def _extract_voice(self, text):
        import re
        # `[voice: ...]` as asked, and `[voice note you sent with it: ...]` --
        # the history's own label, which qwen and glm copied onto their
        # drafts (2026-08-31 test); either is her voice line, never her text
        m = re.search(r"\[\s*voice[^\]:：]*[:：]\s*(.+?)\s*\]\s*$", text, re.S | re.I)
        if not m:
            # a stray voice line elsewhere in the text is still hers; take it out of the bubbles
            m = re.search(r"\[\s*voice[^\]:：]*[:：]\s*(.+?)\s*\]", text, re.S | re.I)
            if m:
                voice = m.group(1).strip().strip("「」\"'")
                text = (text[: m.start()] + text[m.end():]).strip()
                return text, (voice if len(voice) <= self.config.tts.max_chars else "")
        if not m:
            return text, ""
        voice = m.group(1).strip().strip("「」\"'")
        text = text[: m.start()].rstrip()
        if len(voice) > self.config.tts.max_chars:
            voice = ""
        return text, voice

    def _clean(self, text):
        text = text.replace("—", ",").replace("–", ",")
        # strip a leading name label if the model adds one anyway
        for prefix in (f"{self.config.character.name}:", f"{self.config.character.name.lower()}:"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        text = text.replace("<situation>", "").replace("</situation>", "")
        # The record's labels are the world's turns only and her own turns in
        # it are bare (`sim/thread.py`), so a label on an answer is a tell and
        # it should never fire. It is stripped, and a second label starting a
        # line inside the answer cuts the answer there: past that point the
        # model has stopped answering and started writing the next record
        # entry, stamped minutes into the future.
        text = strip_stamps(text, "persona")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # A net under `_clean`, which has already run and taken the same labels
    # off the whole answer. One pattern for both (`sim/thread.py STAMP_HEAD`):
    # the one that lived here matched a bracket of at most 40 characters and
    # stopped matching the day the stamp gained the date.
    _STAMP = STAMP_HEAD

    def _split(self, text):
        if not self.config.delivery.split_on_blank_lines:
            parts = [text] if text else []
        else:
            parts = split_bubbles(text)
        cleaned = []
        for p in parts:
            q = self._STAMP.sub("", p).strip()
            if q != p:
                logger.log(f"[persona] stripped a history stamp from a bubble: {p[:40]!r}")
            if q:
                cleaned.append(q)
        # she repeats herself; she does not paraphrase herself. Two bubbles
        # saying the same thing with the words moved went to him this week.
        cleaned = drop_repeats(cleaned, why="bubble")
        cleaned = self._drop_already_sent(cleaned)
        cleaned = self._take_sticker(cleaned)
        cleaned = self._take_search(cleaned)
        return self._resolve_shares(cleaned[:6] if cleaned else [])

    def _drop_already_sent(self, parts):
        """A bubble that is a message she has already sent him.

        `drop_repeats` above only sees a RUN inside this burst, and the one
        that reached him twice was two hours and five messages old: he had
        answered it, she had answered his answer, and then the same sentence
        went out again word for word ("also. you followed madoka magica on
        x..."). The cause is upstream -- the model is handed the thread with
        the app's stamps on every line and now and then continues it instead
        of answering it, and `_clean` takes the stamp off, so what arrives
        here looks like an ordinary new bubble. The guard the afterthought
        already had is the one that catches it, so every burst gets it.

        The whole draft being a repeat leaves nothing, which the reply path
        reads as nothing having come back and puts his message back in the
        queue. That is the right outcome -- better a second call than sending
        him a question he has already answered -- and `last_all_repeats` is
        what lets the log say which of the two it was."""
        self.last_all_repeats = False
        n = int(getattr(self.config.delivery, "no_repeat_recent", 12) or 12)
        if not parts or n <= 0:
            return parts
        said = [str(m.get("text") or "") for m in (self.store.recent_messages(n * 4) or [])
                if m.get("role") == "assistant" and m.get("text")][-n:]
        if not said:
            return parts
        out = []
        for p in parts:
            if any(near_duplicate(s, p) for s in said):
                logger.log(f"[persona] she had already sent him that, dropped: {p[:70]!r}")
                continue
            out.append(p)
        if parts and not out:
            self.last_all_repeats = True
            logger.log("[persona] the whole draft was what she had already said")
        return out

    # `[sticker: happy]` on its own line, or on the end of a bubble. She names
    # a FEELING, never a file: which picture carries that feeling for her is
    # the store's business (`Reactions.chosen`, which learns it), and she could
    # not know an id anyway.
    _STICKER = re.compile(r"\[\s*sticker\s*[:：]\s*([a-z]+)\s*\]", re.I)

    def _take_sticker(self, parts):
        """Pull her sticker out of the text. It is not a bubble -- it goes as a
        picture after the words -- so it is recorded and `App` sends it."""
        out, want = [], ""
        for p in parts:
            m = self._STICKER.search(p)
            if not m:
                out.append(p)
                continue
            want = m.group(1).lower()
            rest = (p[: m.start()] + p[m.end():]).strip()
            if rest:
                out.append(rest)
        if want:
            self.store.set("pending_sticker", want)
        return out

    # `[search: what she wants to know]` on its own line, or on the end of a
    # bubble: not a thing she sends, a thing she does before sending
    _SEARCH = re.compile(r"\[\s*(?:search|検索|調べる)\s*[:：]\s*(.+?)\s*\]", re.I)

    def _take_search(self, parts):
        """Pull her search request out of the text and keep it for
        `generate`, which runs it and writes the reply again."""
        out, want = [], ""
        for p in parts:
            m = self._SEARCH.search(p)
            if not m:
                out.append(p)
                continue
            want = want or m.group(1).strip()
            rest = (p[: m.start()] + p[m.end():]).strip()
            if rest:
                out.append(rest)
        if want:
            self._search_asked = want
        return out

    def _resolve_shares(self, parts):
        """[share: ID] on its own line (or at the end of a bubble) becomes the
        post's URL as its own bubble. The URL and nothing else: that she
        sent it is recorded when the bubble leaves (the delivery asks the
        account, which records it then), so the draft the editor throws out
        and the compare draft nobody sends record nothing. They used to: the
        share was recorded here, while the reply was being drafted."""
        if not self.social:
            return parts
        out = []
        for p in parts:
            m = re.search(r"\[\s*share\s*[:：]\s*(\d{6,})\s*\]", p, re.I)
            if not m:
                out.append(p)
                continue
            k = self.social.find_share(m.group(1))
            rest = (p[: m.start()] + p[m.end():]).strip()
            if rest:
                out.append(rest)
            if k:
                out.append(k["url"])
        return out[:6]
