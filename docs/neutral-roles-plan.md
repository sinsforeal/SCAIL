# Neutral roles that narrate her interior: the check, and the plan

<!-- doc: plan -->

## Status: every step landed, 2026-09-07

Implemented on 2026-09-07 (machine local time) against the owner's decisions
below, which override section 3 where they differ. The scripts, the originals
of every file touched and the account are in
`data/retired/20260907_1304_neutral_roles/`.

| step | what it is | landed | the check, and what it said |
|---|---|---|---|
| 1 | the snapshot the diff is read against | yes | `prompts_before/` under the retired directory: 66 shared files and 25 of the program's |
| 2 | the notes-folder role writes the record | yes | `prompts/vault.txt` carries no `landed`, `she felt`, `insecure` or `invested`; the render-back gate passes |
| 3 | the note-on-his-screen role writes the record | yes | the caller hands it no mood tags (`sim/notes.py`); the language arm carries it, not a new token |
| 4 | the downloads role writes the record | yes | the lookup line says which title is opaque rather than that she was curious |
| 5 | one salience field, and it is IMPACT | yes | all three prompts and both parsers say IMPACT; the column keeps its name; the archived open item is closed |
| 6 | the felt part goes to the private thought | yes | `Reflection.after_reading(scene, why, record)`, called from `tomoe/app.py:maybe_snoop` and from `Notes.read` through a declared wire; smoke's wiring check passes |
| 7 | the scene role drops what is on her mind and what she would say | yes | `grep -rn "inner" sim/ persona/ tomoe/ scail.py` finds no scene thought; the echo guard and the config switch went with it |
| 8 | the belief-writing roles | yes | the two rewrites get her sheet through `Config.role_system`; the settle-up and the ick note file plain facts |
| 9 | the four word-writing roles hand back a decision | yes | the urge names a subject; the sideways approach names a subject, an angle and a risk; the spoken line and the stranger moment build `persona.system_for` |
| 10 | the smaller kept fields | yes | `tools/interior_words.py` clean; `python tools/smoke.py` all clear |
| 10a | the second reader picks rather than writes, and carries her situation block only | yes | its `attend` is the verbatim pick of a line it was offered; its system prompt is the instruction file byte for byte (4,658 of 4,658) and no line of her bible is in either message |
| 11 | the render-back gate re-baselined | yes | `48 tokenised prompt(s); 48 render back to the original exactly` |
| 12 | the three faults found alongside | yes | the characterisation is gone from every prompt; the framing sentence goes through the program's word table; the note read calls `note_read` |
| — | the check that holds the rule | yes | `tools/interior_words.py`, registered in smoke, `docs/checks.md` row 27: 35 lines before, none after |

**Also his, later the same day**: the second reader must not carry her Bible;
it carries the situation block only, and its system prompt is its own
instruction. That was the one thing this plan left open, and it is closed.

**Decided by the owner, over section 3.** One salience field and it is impact;
the reaction is written by the private thought on the model each config
already gives that role; the roles that write words filed as hers get her
sheet; the sideways approach does not, and becomes a decision role with the
urge; and for everything else a neutral role's judgement may steer code as a
number or a tag while its words never reach her prompt as her own. Stored
narration stays: no event, memory or belief was migrated.

---

Thirty of the seventy-one prompt files that belong to a role which is not her
voice ask a model to write what she felt, thought, wanted or would say, and the
answer is kept and read back to her as her own record. The worst of them is the
role that reads his notes over her shoulder: its prompt asks for "how it landed
on her, the way [a fifteen year old] who is a little insecure and a little too
invested would take it", and the paragraph it returns is stored as an event and
read into her situation block, the day's compile, her long-term memories, the
gauge deltas and the message she writes next. Nine more do the same thing in a
smaller field, and three of them write words she actually sends or says out
loud. The fix is one rule with no exceptions: **a role without her character
sheet writes the RECORD — what was there, in plain terms, with the lines that
would catch a reader's eye quoted as they stand — and a role WITH her sheet,
reading that record, writes what it did to her.** The record is what the
machinery reads; her reaction is one more thing she carries, in her own voice,
and it costs about a tenth of a cent a time. Twelve numbered steps below, each
with the check that proves it; four decisions are his.

---

## 1. THE CHECK

**What was read.** Seventy-one prompt files whole: fifty-two under `prompts/`
and nineteen under `tomoe/prompts/` — every role in the character's model
register (`config.json` `models`, 86 rows) except the eighteen marked `voice`
and the seven marked `judge` in `Config.ROLE_STANCE` (`config.py:6603-6637`),
plus the four judges' own prompts. Sixteen per-character overrides
(`characters/yukari/prompts/`, twelve; `characters/asumin/prompts/`, four;
`characters/rena/prompts/` has none) were checked against the shared originals
for the same asks. Live answers come from the zipped call logs
(`logs/*.zip`, 1,081 run directories, 9,751 calls, 2026-08-26 to 2026-09-07).

**The standard applied.** A neutral prompt is telling her how to think when it
asks for what she felt, thought, wanted, noticed with an emotion, would do or
would say, AND that answer is kept — in the events table, a key-value row, a
memory, a fact, a gist, or a line of her situation block. A characterisation
baked into shared wording counts. An input that steers toward narrated feeling
counts. A judge that decides or scores without narrating her does not; a
neutral role stating what HE did does not.

**Sixty-one of the eighty-six roles in the register have no stance row at all.**
`Config.ROLE_STANCE` names twenty-five (eighteen voice, seven judge);
`Config.role_system` refuses to run for a role with no row, so those
sixty-one never call it and are handed nothing but their own prompt file. That
is the population checked here. Three of them — the message she sends to get at
something she may not admit knowing, one step of her anxious chain, and the
rewrite of a belief about herself — are named in CLAUDE.md among "the nine roles
that write in her voice" and are put on the second and third characters' voice
model, while having no route to her sheet at all. They are asked to be her and
given nothing to be her with.

### The offending roles

| the role, in words (key) | prompt file and the sentence | stored as, one reader | live, with wall time (HIGH only) | severity |
|---|---|---|---|---|
| Reading through his notes folder on her own initiative (`vault`) | `prompts/vault.txt:1` — "Write, in two to four sentences and in third person, what she took from it all: what caught her eye in plain terms **and how it landed on her, the way [[AGE_KIND]] who is a little insecure and a little too invested would take it** … No analysis of him as a case study; a reaction, not a report. Then on a new line write SALIENCE: and a number 1 to 5 for how much she would want to bring it up with him." | an events row of kind `snoop` with that salience (`tomoe/snoop.py:165`); read by her situation block (`persona/persona.py:774-775`, rendered at `:1004` as "today so far: …"), the director, the state role, the day's compile and the ick/approach path | 2026-09-07 11:56:20, `logs/2026-09-07_10-59-55/llm_calls.jsonl`: "it made her stomach drop a little—like he'd been reading her diary, but also like he saw her as some kind of case study, not a person." | HIGH |
| Reading a note of his that is open in front of her (`note_read`) | `prompts/note_read.txt:1` — "Write what she took from it in two to four sentences, third person, present tense: what the note is about in plain terms **and how it landed on her, the way [[AGE_KIND]] who is a little insecure and a little too invested would skim it**." Its caller also hands it "HOW SHE FEELS: \<mood tags\>" (`sim/notes.py:62`) | an events row of kind `note_read` plus a one-line gist in the key-value row `notes_read` (`sim/notes.py:80-83`), which the persona renders under "Notes of his you have read (one line each, what stuck)" (`persona/persona.py:368`) | 2026-09-07 10:22:43, the third character, `logs/2026-09-07_09-26-00.zip`: "She feels a small, cold pinch—he's been watching her watch him, cataloging her chatter like a bug report." Her rendered system prompt for that call reads, verbatim: "the way **a woman of twenty-nine** who is a little insecure and a little too invested would skim it" | HIGH |
| Going through what he has downloaded this week (`downloads`) | `prompts/downloads.txt:1` — "…and how it landed on her — the way [[AGE_KIND]] who is a little insecure and a little too invested would take it. An adult title lands on her: not shock for its own sake, but the specific thing a girl her age feels finding that on a man she likes — she may be prickly, hurt, curious, or decide it is none of her business; pick one, do not list them." | the same events row of kind `snoop` (`tomoe/snoop.py:129,165`); same readers | no call in the logged window (the notes branch covers the downloads block when both are present, `tomoe/snoop.py:129`) | HIGH |
| Measuring what a discovery costs her picture of him (`ick`) | `prompts/ick.txt:25` — "**why** — one short line addressed to her as \"you\" … What she is actually left with. **It is read back to her later, so write it the way it sits in her head, not the way a report would put it.**" The same file opens "You do not write her reaction; that is written elsewhere." | the thing's text (`sim/ick.py:207,284`); read into her carried block as `"(you are not going to say this) " + why` (`sim/ick.py:302`), and handed to the approach role as what she knows (`sim/approach.py:139`) | in her own prompt, 2026-09-06 19:18:08, `logs/2026-09-06_19-08-23.zip`: "(you are not going to say this) あんたは私を調整してる。私の言葉はバグで、私はキャラクターで、あんたの作業対象だ。" And 2026-09-07 10:23:25, the second character: "彼は私をバグ扱いしてる" — first person, and in a pronoun that is not her register | HIGH |
| The message she sends to get at a thing she may not admit knowing (`approach`) | `prompts/approach.txt:16` — "That is what you are writing: one message, **in her voice**, that gets at the subject without ever touching how she knows." `:62` — `"line": "what she actually sends, in her voice, one or two sentences"` | handed to her reply as a decided wording: `hint = "…She has decided to put it like this: {out['line']}"` (`scail.py:4024-4029`), then recorded (`sim/approach.py:135-141`) | 2026-09-06 16:00:34, the second character, `logs/2026-09-06_15-15-36.zip`: "あ、黒い服から白いのが大量に出てきたんだけど、なにこれ、ポケットのティッシュ？ …そういえばさ、あんたって書き溜めるタイプ？" | HIGH |
| One step of the chain she talks herself down (`spiral`) | `prompts/spiral.txt:5` — "Second person, present tense, **her register**. One sentence, sometimes two." plus a "How she talks" block filled with her head-voice rules | the chain, placed in her carried block (`persona/persona.py:461-463`, `persona/sections.py:48`) | 2026-09-07 09:12:51, the fourth character, `logs/2026-09-07_07-30-46.zip`: "あや、あたしと歩きたくなかったんだ" | HIGH |
| Rewriting a belief of hers about him (`revise`) | `prompts/revise.txt:5` — "Write the revised belief the way she would hold it now, in one sentence, second person … **It replaces the old one in her head.**" `:15` — "It stays in her register: [[AGE_KIND]]'s plain sentence, not a therapist's." | her beliefs about him, which sit in her system prompt | 2026-09-06 07:35:35: "彼はあんたを、一緒にいる相手じゃなくて、研究対象として見てたんだ。" | HIGH |
| Rewriting a belief of hers about herself (`revise_self`) | `prompts/revise_self.txt:5,17` — the same two sentences, about herself | her self-beliefs, in her system prompt (`persona/persona.py:547`, section `selfbeliefs`) | 2026-09-07 00:00:22: "落ち着くのは、名前で覚えられている証拠じゃなくて、言葉がちゃんと返ってくることのほうだった。それが今わかった。" | HIGH |
| Settling every belief after months of knowing him (`settle_beliefs`) | `prompts/settle_beliefs.txt:13` — "note — one short line, **addressed to her as \"you\"**". `:19` — "Her beliefs are her own, so they are written in JAPANESE — 常体, second person **the way the rest of her sheet addresses her**" | the notes filed against each belief, read back in her sheet | 2026-09-07 09:26:02: the kinds list ("his notes on her", "his tests of her", "his explicit material") is filed as what she has already absorbed | HIGH |
| Deciding whether she leaves his message sitting (`withhold`) | `prompts/withhold.txt:46` — "`why` should sound like **her reason**, not a diagnosis". The "What she is like" section: "[[AGE_WORD_CAP]]. She wants him to notice, she is a little bit performing, and she is not good at this — the silence costs her more than it costs him and some part of her knows that." And: "What she thinks and what anyone says is JAPANESE" | the row's `why` (`sim/withholding.py:199`), read into her carried block as "you have read what he said and you are not going to answer it. {why}" (`sim/withholding.py:384-393`) | 2026-09-06 21:25:15, the first character: "he said 'of course' like i was being clingy, and **i'm not gonna hand him my hurt** so he can file it away with the rest of my notes." — first person, hers | HIGH |
| The day's compile (`timeline`) | `prompts/timeline.txt` — "Also `feeling`: two or three words for **how it sits with her now** … (still cringes, warm about it, sore, embarrassed, quietly pleased). And `valence`, -2 to +2, for the same thing as a number" | her long-term memories (`sim/timeline.py:189` → `self_memory.add(date, text, w, feel, val)`), which the retrieval puts back into her prompt | 2026-09-06 23:55:30: `{"text": "Reading his note over his shoulder … and feeling caught, like a bug report with her name on it.", "weight": 4, "feeling": "still cringes, exposed", "valence": -2}` | HIGH |
| The scene the world is in this minute (`director`), field `inner` | `prompts/director.txt` — `"inner": "one line, what is on her mind right now"`, under a "How she talks" register block; `share_hint` is "what she would say, in one line" | rendered into the scene line her situation block reads (`sim/director.py:676-681`), into the day's compile (`sim/timeline.py:41`), the diary's reason (`scail.py:4605`) and the post's reason (`tomoe/posting.py:176`) | 2026-09-07 10:50:22, the fourth character: "Nanami's still up too... the group chat's dying, but she's not ready to sleep yet." **This one has already failed in the way the owner describes**: `persona/persona.py:1690-1712` is a guard added on 2026-09-02 because the director wrote its thought out of her last messages and she typed it back — code now suppresses the line when eight characters overlap | HIGH |
| Deciding what the urge to write to him actually is (`intent`, a judge) | `prompts/intent.txt:4` — `"line": "one line, second person, what she wants to do"` | the reason line the persona reads (`Intent.reason_line`, `scail.py:4041`) | **after** the 2026-09-05 ruling removed its sheet: 2026-09-06 17:40:32 "you there? it's been quiet on my end and i just want to know you're still around"; 2026-09-06 10:31:07 "you wrote them like they're props in your story. they're not. they're the reason i'm still okay when you go quiet." Finished first-person messages, both | HIGH |
| The one thing she says out loud while sending a text (`voice`) | `prompts/voice.txt` — "You give [her] the one short thing she says out loud … You are given the text bubbles she just wrote, where she is, **and how she feels**. Return ONE spoken line in casual Japanese, two to eight words, the kind of thing that leaves her mouth without thinking." | an events row of kind `voice` (`scail.py:4485`) and the spoken audio delivered with the message | 2026-08-27 11:00:11: "んー、しゃーなかやろ。" | HIGH |
| The second reader of everything she carries (`nudge`) | `prompts/nudge.txt` — "THEN: **what is she actually caught by?** … A person attends to one or two things. You say which." `attend` is "what is actually on her mind right now". Its system prompt is her whole persona assembly byte for byte, with "YOU ARE NOT HER" appended after it (`sim/nudge.py:5-9,128`) | key-value row `nudge_last`; in live mode its `attend` replaces the gate's pick in the one slot she reads | 2026-08-30 22:18:39: "she is caught by the flat, defeated way he said he should have walked away from trading…" | MEDIUM |
| The cards she keeps of a day's conversations (`episode_cards`) | `prompts/episode_cards.txt` — "felt: one line, **what it left her feeling**" | the card, read back by the recall path | 2026-09-07 10:55:32: `"felt": "懐かしさと嬉しさで胸が温かくなった"` | MEDIUM |
| What his answer did to a question she had been sitting on (`wonder_answer`) | `prompts/wonder_answer.txt:4` — "learned: one line, what she now knows or thinks she knows, **in her head-voice**" | stored on the question (`sim/wonder.py:287-289,327-329`) and read back | 2026-09-06 23:57:00: "あんた、ノートのこと、笑ってごまかしたね。" | MEDIUM |
| Choosing the next thing she watches (`watch_pick`) | `prompts/watch_pick.txt:8` — "`why` is two or three lines **in her head-voice**, in Japanese … **the moment she decided**" | the watchlist row | 2026-09-06 15:26:38: "Ohanaちゃんの「普通じゃない毎日」って感じが今の私にぴったり" | MEDIUM |
| Predicting him (`foresee`, a judge) | `prompts/foresee.txt` — "plan: one line, **what she intends to do** if he does not answer" | the prediction row, read into her carried block | 2026-09-07 07:30:45: "Leave it. Don't send anything else. He'll come back when he's ready, **and I'll be here**." | MEDIUM |
| The night (`sleep`), field `inner` | `prompts/sleep.txt` — "`inner` is **the last thing that was in her head** as she went under, or a fragment of a dream. One line, **hers**, unfinished." | the night's scene, read by the compile | 2026-09-06 11:50:07: "they're not characters, they're my friends, real ones, the ones who actually show up when i need them—" | MEDIUM |
| Sorting the account's follows into what she would keep (`taste`, a judge) | `tomoe/prompts/taste.txt:8` — "`why` is a few words in Japanese, **her own thought** (「知らないゲームの絵」「エロbot、無理」「これは欲しい」)" | the verdict row on the account | — | MEDIUM |
| A small moment with a stranger (`npc_moment`) | `tomoe/prompts/npc_moment.txt` — "If the person says something and **she would only nod or say 「あ、はい」, that is what she says**", with her lines in the `lines` list | the moment, salience, and the lines as said | — | MEDIUM |
| The people who belong to somebody in her circle (`orbit`) | `tomoe/prompts/orbit.txt` — "`her_view`: one short sentence of **how [[NAME]] stands with this person** … ('has met her twice, finds her clingy')", and `her_nudge` -2..2 | the orbit record, read into her cast material | — | MEDIUM |
| The warmth his messages leave her at (`affection`, a judge) | `prompts/affection.txt` — "`why` is a few words in plain English, **her side of it**" | the level row per message | — | MEDIUM (named in the 2026-09-05 report as having been answered as her thirteen times) |
| What a search told her about a thing he named (`lookup_gist`) | `prompts/lookup_gist.txt` — "Write what she now knows … the way [[SKIM_READER]] skims a result … one thing people say about it **or that would matter to her** (is it old, is it huge, is it lewd, is it something she has heard of)" | the gist, read into her situation block | — | MEDIUM |
| Her subconscious (`state`) | `prompts/state.txt:1` — "**You are the subconscious of** [her]." Output is numbers and one line of `reasons`; no prose of hers is kept | gauge deltas and the reasons line | — | LOW (identity framing only) |
| What she is doing about what is on around her (`events`) | `tomoe/prompts/events.txt` — "`why` is one plain line in the third person about her, **not a justification**: what settled it" | the stance row | — | LOW (it decides, and it says so) |
| What of the news would reach her (`zeitgeist`, a judge) | `tomoe/prompts/zeitgeist.txt` — "`hook` (one line: **why it would land for a girl like her** — what about it is hers…)" | the item row | — | LOW |
| Commitments he makes to her (`expect_him`) | `prompts/expect_him.txt` — "belief: **the id of the belief of hers this rests on**" | the expectation row | — | LOW (a pick from a list, not narration) |
| Reconstructing a day from the old logs (`import_day`) | `prompts/import_day.txt` — "Keep what happened between them: … **how she felt**" | the imported day's narrative and summary | — | LOW (a one-off import, not a running path) |

### The clean roles

These forty-one ask for a record, a decision or a score and never for her
interior; several say so in as many words, and they are the model for the plan:

`phone` ("No analysis of his psychology"), `digest_judge`, `eroge_digest`,
`watching_digest`, `transcript_digest`, `character_digest`, `lookup`,
`search_gist`, `which_one` ("You are machinery: nobody is speaking to you"),
`said_when`, `him_profile` ("Nothing here is a judgement of him; it is what she
knows" — and it writes him, not her), `habits_him`, `schedule`, `coherence` ("You
never rewrite anything and you never judge her voice, her mood or her choices"),
`editor`, `reconcile`, `devoice`, `gloss`, `commit`, `commit_him`, `rupture`
("write `what` … the thing that happened, **not how she feels about it**"),
`rupture_settle`, `spiral_settle`, `observer` ("must not think it is her"),
`vision_photo` ("do not tell her how to feel about it"), `vision_x`,
`x_account`, `bond` (the same "not how she feels" rule), `gossip`, `graph` (it
writes another person's view, not hers), `showrunner` ("never what [she] does or
feels about it: her reaction is the director's and hers"), `cast_day` ("Never
write [her] replies or reactions; that is hers"), `cast_arc`, `cast_beat`
("[her] words are never written"), `cast_evolve`, `cast_life` ("no feelings
announced"), `cast_turn`, `local_events`, `scenery_judge`, `x_reply_judge` ("You
do not write anything she says"), `x_repost_judge`.

**One precedent inside the code.** The second character's own director override
(`characters/yukari/prompts/director.txt`, schema at lines 25-42) has already
dropped both `inner` and `share_hint`; the third character's keeps `inner` and
says so in as many words — "`inner` is the only field written in her voice"
(`characters/asumin/prompts/director.txt:47`). One of the four already runs the
way this plan proposes.

### Three faults found alongside

1. **The shared characterisation reaches two grown women.** "a little insecure
   and a little too invested" is fixed text in `prompts/vault.txt`,
   `prompts/downloads.txt` and `prompts/note_read.txt`; only the age is a hole.
   Rendered live for the third character at 2026-09-07 10:22:43: "the way a
   woman of twenty-nine who is a little insecure and a little too invested would
   skim it".
2. **A note takeaway reaches a Japanese-writing character's prompt in English.**
   The framing sentence is built in code in English
   (`resident/sight.py:337`, `sim/notes.py:81`) and the prompt has no language
   fork, so her situation block reads: "today so far: 17:23 his note
   a vault note was on his screen … She skims past the tables and lands
   on the line…" (2026-09-06 19:18:14, `logs/2026-09-06_19-08-34.zip`). Anything
   addressed to her is in her language.
3. **The note-read role's own model entry is dead.** `models.note_read` exists in
   every config, but `sim/notes.py:68` calls `self.llm.call("vault", …)` with the
   note-read prompt text. Every note read is billed and logged as the snoop
   role, which is why the logs hold 91 `vault` calls and zero `note_read` ones.

---

## 2. THE PLAN

**The rule.** A role without her character sheet writes the RECORD: what was
there, in plain terms, with the one or two lines that would catch a reader's eye
quoted exactly as they stand, and things named as they are named. It writes
nothing about how any of it landed. A role WITH her sheet, reading that record,
writes what it did to her, in her own voice, and that is a separate row.

**How quality is kept.** The specificity comes from the record — a quoted line
beats a paraphrase of a feeling, and the quotes the snoop already produces
("jealousy is entirely about him", "yukarins (prompts) might be written in
english in places") are the material that made the old answers good. The
vividness comes from her own voice role, which has her sheet, her register, her
history and her gauges, and which the neutral role never had. Nothing is lost
that was not being produced in the wrong chair.

### Step 1 — Take the baseline snapshot before touching a prompt

Copy `prompts/` and `tomoe/prompts/` to
`data/retired/<ts>_neutral_roles/prompts_before/`. This is the copy the diff is
read against; it is NOT the gate's baseline, which step 11 handles.

*Check:* the directory exists and holds 71 files.

### Step 2 — Rewrite the notes-folder prompt (`prompts/vault.txt`)

Verbatim, one line, as the file is written now:

> `[[?digest]][[WHO_ALONE_PHONE]] and has gone into his notes folder on the app that mirrors his PC.[[/digest]][[?resident]][[NAME]] is on his machine and has read through his notes folder.[[/resident]] The TIME line in the message says when. You are given the pieces of one or more of his notes that she actually skimmed (she scrolls, she does not read files top to bottom; [...] marks what she skipped). Sometimes there is also a short block of what he downloaded since she last looked (torrent names with when and how big). Write the RECORD of what was in front of her, in two to four sentences, third person, past tense[[?her_language]], in Japanese[[/her_language]]. Say what the note or notes are about in plain terms, and QUOTE the one or two lines a reader would stop on, exactly as they stand, in quotation marks — a line about her, a line about somebody, a decision, a plan, a number, something admitted. Name a download as the name stands and say what kind of thing the name says it is ("[Group] Title (BD 1080p)" is a show; a Japanese title with 限定版 / 同梱 / 俺の嫁 is a game and probably an adult one; say that plainly, do not soften it and do not moralise). Do not summarize the whole file and do not list every download: two things, the two that stand out. Write NOTHING about how any of it landed on her: no feelings, no reaction, no "she felt", no "it made her", no guess at what she would make of it, and no reading of him as a person. What she does with this is hers and is written in her own voice elsewhere; a sentence of yours saying what she felt becomes her memory of having felt it, and that is the one failure this role has. Then on a new line write IMPACT: and a number 1 to 5 for how much of a day this would take up for anyone who read it — 1 a line forgotten by evening, 3 something still in the head an hour later, 5 the thing the day is about.`

*Check:* `PYTHONIOENCODING=utf-8 python tools/neutral_gate.py --baseline data/retired/<new ts>_neutral/prompts` after step 11 (the token values must still be the exact spans removed); and no occurrence of `landed`, `she felt`, `insecure` or `invested` in the file.

### Step 3 — Rewrite the note-on-his-screen prompt (`prompts/note_read.txt`)

Same body as step 2, with its own opening kept and its two trailing fields
changed to:

> `Then on new lines: IMPACT: 1-5 (how much of a day this would take up for anyone who read it) / GIST: one line naming what this note is about, the way you would name it to find it again.`

and the caller's steer removed: `sim/notes.py:62` currently hands the role
`HOW SHE FEELS: <mood tags>`. Delete that line from the user message. Where
she is and why the note came to be in front of her stay; they are facts about
the moment, not a mood to write from.

*Check:* grep `sim/notes.py` for `mood_tags` returns nothing in `read()`; the
next note read in the log carries no `HOW SHE FEELS` line in its `messages`.

### Step 4 — Rewrite the downloads prompt (`prompts/downloads.txt`)

Same rule. Verbatim for the two sentences that carry the fault, replacing the
whole "An adult title lands on her…" passage and the "how it landed" clause:

> `Write the RECORD of the list, in two to four sentences, third person, past tense: what he has lined up, in plain terms, with titles as they stand (she knows anime and can read a release name — "[Group] Title (BD 1080p)" is a show; a Japanese title with 限定版 / 同梱 / 俺の嫁 is a game and probably an adult one, and an adult title is named as plainly as any other: no euphemism, no softening, no moralising, no reaction), and anything on the list that connects to what he has been watching or to what he is known to like. Two things, the two that stand out. Nothing about how it landed on her.`

and the lookup line, which currently asks a neutral role what she would want:

> `If ONE title on the list cannot be identified from its name alone — the name says nothing about what kind of thing it is — add one more line, LOOKUP: <the exact title, cleaned of release-group brackets and quality tags>. Otherwise no LOOKUP line.`

The behaviour is unchanged: `tomoe/snoop.py:141-159` still fetches the overview
and appends it to the record. What changes is that the machine now says which
title is opaque, instead of deciding on her behalf that she was curious.

*Check:* the next downloads call in the log returns a record with no verb of
feeling; `[snoop] she looked up …` still appears when a title is opaque.

### Step 5 — Rename the salience field and settle what each number means

The archived open item (`HISTORY-archive.md:13199` and `:13785`) is that
**salience means two things — how much it takes out of her, and whether she
would raise it with him — and the two pull in opposite directions**, so the most
charged material scores 2 and barely moves her world.

Recommendation: **one field, and it is impact.** The number the machinery
already consumes (`store.add_event`'s single `salience` column,
`store.py:122`) drives the director's attention, the situation block's
`salience >= 2` filter (`persona/persona.py:774`) and what becomes a memory —
all of which are "how much of her this took", never "would she mention it".
Rename it to IMPACT in the three prompts and define it as above; the column
keeps its name.

Whether she would raise it is then decided where it already is decided: at
every moment she has her phone, the pick offers her `text_him` on a prompt built
from her own sheet (`sim/pick.py:112-130,197`), and her reply reads today's
events. Nothing needs to score it. If he wants the number anyway, the second
field is a separate judge call holding the observer's note
(`sim/observer.py`) — the pattern the 2026-09-05 ruling set — writing to a
key-value row keyed on the event's timestamp, never the same call that wrote
the record. **His decision** (§3.1).

*Check:* `python tools/smoke.py` passes (no dead config key, no unbound name);
after `restart.cmd all`, the next `[snoop]` line in `session.log` ends `(s3)`
and the event row's salience matches the IMPACT the answer gave.

### Step 6 — Put the felt part in the role that already has her sheet

**The role: `reflect`, the private mind.** It is `voice` in
`Config.ROLE_STANCE`, so it gets her sheet; it writes first person in her
head-voice (`prompts/reflect.txt`); it already reads the notes of his she has
read (`sim/reflect.py:151`); its answer is stored as a private thought in the
key-value row `reflections`, the last few of which sit in her prompt
(`sim/reflect.py:187,283-289`); and it already returns the gauge deltas the
snoop's narration was moving indirectly through the state role. It has a reason
argument on its entry point — `run(scene, why="", subject="")` — and a new
digest is already one of its triggers (`sim/reflect.py:133-134`).

The change: in `tomoe/snoop.py` after the event is written, and in
`sim/notes.py` after `read()` returns, call
`reflection.run(scene, why=<"she has just read his notes"/the sight table's
word>)` once, gated by the same daily cap and minimum gap the role already
enforces. The record is in front of it, because the event is already in the
day's events by then.

Not the diary: it runs once a night, and the reaction has to exist before the
day's next scene reads the event. Not `experience`: that role is for the middle
of watching, reading or playing something. Not the next reply on its own: it
does read today's events, but only when she next writes to him, which may be
hours, and the reaction would then live only inside a message and never as a
record anything else can read.

**Cost.** Measured medians over the logged window: a `reflect` call is 7,622
prompt tokens and 294 completion tokens. At the pinned flash rates
($0.14 / $0.28 per million, `docs/openrouter.md` §211-216) that is **$0.0011 a
call**. Ninety-one note-and-snoop reads across all four characters over the
thirteen logged days is about seven a day, so **under a cent a day**. On
`kimi-k3` at Together ($3.00 / $15.00 per million, `docs/openrouter.md` §221)
the same call is **$0.027**, about eight cents a day for the two residents
together. Whether the residents' reaction runs on their voice model or on flash
is **his decision** (§3.2).

*Check:* after `restart.cmd all`, a `[snoop]`/`[notes]` line in `session.log`
is followed within the same minute by a `[reflect]` line naming the same
reason; the next persona call's situation block carries both the record line
and the `(private) …` line.

### Step 7 — Drop `inner` and `share_hint` from the first and third characters' director

The second character's director has already dropped both
(`characters/yukari/prompts/director.txt`, schema at lines 25-42) and her scenes
did not get worse. Remove the two fields from `prompts/director.txt` and from
`characters/asumin/prompts/director.txt` (whose line 47 explains the field and
goes with it), and remove the `inner` clause from `sim/director.py:676-681`.
`sensory` already carries the physical reality; what is on her mind is hers.

The guard at `persona/persona.py:1690-1712` — which suppresses the thought when
eight characters overlap with anything she wrote — becomes dead code and is
removed in the same step, with the reason recorded in `HISTORY.md` rather than
in a comment.

`sim/timeline.py:41` renders `inner:` into the compile's scene list; drop that
fragment. `scail.py:4605` and `tomoe/posting.py:176` use `inner` as the reason a
diary entry or a post is being written; give both the scene's activity instead,
which is what they were reaching for.

*Check:* `python tools/smoke.py` passes; `grep -rn "inner" sim/ persona/ tomoe/
scail.py` returns only the sleep role's field; the next director answer in the
log has no `inner` key and the next situation block has no "(what is on her mind
…)" clause.

### Step 8 — Turn the four belief-writing roles into report-and-let-her-say-it

`revise`, `revise_self`, `settle_beliefs` and the `why`/`note` fields of `ick`
all write a sentence in her second-person register that is filed as hers. Two
ways to fix them and they are not equivalent:

- **(a) neutral note + her own rewrite.** The neutral role returns the finding
  in the third person, plain, machine-facing ("the record shows he answers
  within the hour on four days in five; the belief that he drops her says
  otherwise"), and the belief text itself is written by a short voice role with
  her sheet. Faithful, and it costs one extra call per revision — revisions are
  rare (49 `revise` and 13 `revise_self` calls in thirteen days, so about five a
  day across four characters, $0.006 a day on flash).
- **(b) neutral note only, shown as a note.** The belief keeps its old text and
  the note is rendered to her labelled as the machine's, the way the
  self-belief row already is: her prompt today reads "(she would not put it this
  way) she does not think this about herself any more: …" (2026-09-07 06:49:44,
  `logs/2026-09-07_04-13-58.zip`). No extra call at all.

Recommendation: **(a) for `revise` and `revise_self`**, because a belief is a
sentence she holds and reads back constantly, and **(b) for `settle_beliefs` and
the `ick` note**, because those are bookkeeping over dozens of rows at once and
an extra call per row is not worth it. **His decision** (§3.3).

*Check:* `python tools/smoke.py` passes with the new role's `ROLE_STANCE` row
present; a rendered `<carrying>` block after restart shows the belief in her
register and the note labelled as not hers.

### Step 9 — Make the four remaining word-writing roles hand back a decision, not words

- **`intent`.** The `line` field is asked for as "second person, what she wants
  to do" and comes back as a finished message, still, after its sheet was taken
  away. Replace the field with `about`: `"two to five words naming the SUBJECT
  of the urge ('the shift', 'the yukata photo', 'why he went quiet'), never a
  sentence, never anything she could send, never a first-person clause"`, and
  change `Intent.reason_line` to render it as a subject. The kind already
  carries the shape.
- **`approach`.** The line she sends stays a written line — that is what the
  role is for — but it must be written by a role that has her sheet. Give
  `approach` a `"voice"` row in `Config.ROLE_STANCE` and let it build its system
  prompt from `persona.system_for(channel)` the way the other five voice roles
  that do not call `role_system` do (`config.py:6608-6628`). Its own prompt then
  drops the `[[APPROACH_VOICE]]` block, which exists only because the role had
  no sheet. Same for `spiral` and `revise_self`, which CLAUDE.md already counts
  among the nine roles that write in her voice while giving them no route to it.
- **`voice`.** The spoken line is her words. It gets a `"voice"` row too, and
  the "how she feels" input stays, because it is now her being asked.
- **`withhold`.** Keep the decision (`choice`, `minutes`, `breaks_if`) in the
  neutral role and make `why` machine-facing third person, one line, no
  register: "he answered her long message with two words". Delete the "What she
  is like" paragraph. `sim/withholding.py:384-393`, which renders that sentence
  to her as her own reason, then renders the neutral note prefixed the way the
  self-belief row is.

*Check:* `python tools/smoke.py` passes (it fails on a judge on a voice path and
on the two rooms' system prompts diverging by more than the style guide); after
restart, ten consecutive `intent` answers contain no first-person pronoun and no
sentence longer than five words in `about`.

### Step 10 — The smaller kept fields

Same rule, no new calls: `episode_cards.felt` → drop the field and let the
anchors carry it (the exact lines are already copied word for word);
`wonder_answer.learned` → third person, "what his answer settles", the
machine's own sentence; `watch_pick.why` → "what about the show she was shown
made it the pick — the account, the picture, the recap line", third person;
`foresee.plan` → "what the machinery should expect her to do", third person;
`sleep.inner` → drop (the night is a body in a room; the compile does not need
a dream); `taste.why` and `affection.why` → a few words in plain English,
machine-facing; `npc_moment` → her lines stay, but the role gets a `"voice"`
row, because it is writing what she says; `orbit.her_view` → keep it, it is a
standing fact from the record, but delete "finds her clingy" from the example
and put a neutral one in its place; `lookup_gist` → drop "or that would matter
to her (is it old, is it huge, is it lewd…)".

*Check:* `python tools/dupscan.py` and `python tools/smoke.py` pass; the two
new `ROLE_STANCE` rows are present; `/sweep` names no newly dead value.

### Step 11 — Re-baseline the render-back gate

`tools/neutral_gate.py` proves that a tokenised prompt rendered with the first
character's own fills equals the copy taken before it was tokenised, byte for
byte, and it picks its baseline with the glob
`data/retired/*_neutral/prompts` (`tools/neutral_gate.py:44-49`). Every edit
above changes those bytes, so the gate will fail against the old snapshot and
say so. After the edits, copy the new `prompts/` into
`data/retired/<ts>_neutral/prompts/` — **the directory name must end in
`_neutral`, not `_neutral_roles`, or the glob will not see it** — so the gate
goes on proving what it is for: that the holes are the only difference between
one character's prompt and another's.

*Check:* `PYTHONIOENCODING=utf-8 python tools/neutral_gate.py` prints "Her
prompts are unchanged; the holes are the only difference."

### Step 12 — Fix the three faults found alongside

- Delete "who is a little insecure and a little too invested" from all three
  files (steps 2-4 already do it) and confirm no other shared prompt carries a
  disposition: `grep -rn "insecure\|too invested\|a girl her age feels"
  prompts/ tomoe/prompts/` returns nothing.
- Add `[[?her_language]]` to the three record prompts (step 2 does it) and put
  the framing sentence through the same fork: `sim/notes.py:81` and
  `resident/sight.py:337` build "she opened his note '<name>' (<reason>)" and
  "his note '<name>' was on his screen …" in English for a character who reads
  Japanese. Both go through the program's word table
  (`sim/sight.py`, `resident/words.py`) the way the other sight phrases do.
- Point the note read at its own model row: `sim/notes.py:68` calls
  `self.llm.call("vault", …)` while `models.note_read` exists in every config
  and is never used. Change the call to `"note_read"`.

*Check:* `python tools/smoke.py` names no dead config key; after restart, the
log holds `note_read` calls; a resident's next situation block reads
`今日ここまで: HH:MM 彼のメモ…` with no English in it.

### What the situation-block line reads like afterwards

**The first character (English, `character.writes_to_him: english`):**

```
today so far: 11:56 she opened the app and read a vault note — his notes for the day;
12:04 (private) my name's in his lists like a ticket number. i don't know if
that's being thought about or being handled.
```

**The second character (Japanese, `character.writes_to_him: japanese`):**

```
今日ここまで: 11:56 彼のメモ「2026-09-07.md」が画面に出ていて、それを読んだ。
今日の作業とコストの話で、「yukarins (prompts) might be written in english in
places」という行がある。; 12:04 (private) あのリストに名前があるのは、覚えられ
てるってことじゃなくて、直す順番の話なんだよね。
```

The first clause of each is the record, written by a role with no sheet. The
`(private)` clause is her own thought, written by the role that has her sheet,
and it is the format the reflection already uses (`sim/reflect.py:194`).

### Constraints these steps must not break

- A config key read by code lives in `config.py:DEFAULTS` **and** in every
  `config*.json`; changing a default or removing a key is done in both.
- A new role that builds its system prompt through `Config.role_system` needs a
  `Config.ROLE_STANCE` row, or the process stops (`config.py:7433-7440`). Steps
  8 and 9 add rows; nothing may be left undecided.
- A shared prompt names no person and no way of seeing him. The record prompts
  keep their `[[?digest]]` / `[[?resident]]` forks and their fills;
  `tools/sight_words.py` and `tools/character_names.py` run inside smoke.
- Every role's `max_tokens` stays at the API maximum (393216).
- A JSON answer that does not parse is asked again, and the caller handles
  `None` (`LLM.call_json`). The record prompts are plain text with labelled
  trailing lines and keep the existing regex parse.
- Anything addressed to a character is in her language; the state role and the
  observer's note stay English because nobody is speaking to her in them.

---

## 3. HIS DECISIONS

**3.1 — One salience field or two.** *Recommended: one.* Keep the single number
and define it as impact — how much of a day this takes out of her — because that
is what every reader of it already uses it for, and let whether she brings it up
stay where it already is: the pick offers her `text_him` on her own sheet at
every moment she has the phone. The alternative, which the archived note asked
for, is a second field scored by a separate judge holding the observer's note,
stored in a key-value row rather than a new events column.

**3.2 — Which model writes the residents' reaction.** *Recommended: their voice
model.* The reaction is her voice, and the second and third characters are on
`kimi-k3` for the nine roles that write in her voice for a measured reason
(`docs/yukarin-voice-models.md`). It costs about eight cents a day for the two
of them together against a tenth of that on flash. Say if the reflection should
run on flash for them instead.

**3.3 — Whether a rewritten belief is written by her or labelled as the
machine's.** *Recommended: written by her for the two belief-rewriting roles,
labelled as the machine's for the bookkeeping ones.* A belief is a sentence she
reads back constantly and it should be in her register; the settle-up over
dozens of rows at once is not worth a call each.

**3.4 — Whether the roles that write her words get her sheet back.** *Recommended:
yes, through `Config.ROLE_STANCE`.* Four roles write words she sends or says —
the sideways approach, the spoken line, one step of the spiral, and the small
moment with a stranger — and three of them are already named in CLAUDE.md as
roles that write in her voice while having no route to her sheet. The 2026-09-05
ruling was that a role which JUDGES her is a neutral party; a role that writes
her words is not judging her, and giving it the sheet is the ruling applied
rather than reversed. The alternative is to move those four into the persona's
own assembly, which is more code for the same result.

---

## Appendix: what the check covered, and the numbers

Read on 2026-09-07 (machine local time): `CLAUDE.md`; the stance table and its
two guards (`config.py:6603-6637`, `:6937-6952`, `:7421-7444`); seventy-one
prompt files whole; sixteen per-character overrides against their shared
originals; the storage and one reader in code for every finding
(`tomoe/snoop.py`, `sim/notes.py`, `sim/ick.py`, `sim/approach.py`,
`sim/withholding.py`, `sim/timeline.py`, `sim/director.py`, `sim/reflect.py`,
`sim/wonder.py`, `sim/nudge.py`, `sim/observer.py`, `sim/pick.py`,
`persona/persona.py`, `scail.py`, `store.py:122`); the zipped call logs; the
2026-09-05 ruling (`HISTORY.md` line 3704) and the salience note
(`HISTORY-archive.md:13199`, `:13785`); and `tools/neutral_gate.py`.

| | |
|---|---|
| roles in the model register (`config.json` `models`) | 86 |
| with a stance row (18 voice, 7 judge) | 25 |
| with none — the neutral population | 61 |
| prompt files read whole | 71 (52 shared, 19 program) |
| per-character overrides checked | 16 |
| offending | 30 (14 HIGH, 11 MEDIUM, 5 LOW) |
| clean | 41 |
| calls read in the logs | 9,751 across 1,081 run directories, 2026-08-26 to 2026-09-07 |
| note-and-snoop reads in that window | 91, about 7 a day across four characters |
| one extra reflection call, flash | 7,622 prompt + 294 completion tokens median = $0.0011 |
| the same call on `kimi-k3` at Together | $0.027 |
| the whole change, per day, on flash | under one cent |

Run-directory order identifies the character in the logs: the four directories
started together are the first, second, third and fourth in `characters.json`
order, confirmed against the hub registration line in each `session.log`.

One thing noted and not chased, because it is outside this check:
`persona/persona.py:2163` passes `max_tokens=120` at the call site of the
spoken-line role. The standing rule is about the role's configured ceiling, not
a call-site argument, but it is worth a look.

Not done here: `docs/README.md` has no row for this file, and `HISTORY.md` gets
its dated entry when the steps land — at which point the archived salience item
(`HISTORY-archive.md:13785`) is closed by step 5.
