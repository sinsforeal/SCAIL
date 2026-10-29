# The language a character is addressed in

The spec of one switch in the shared library: which language everything
addressed TO a character is written in, and how the sentences another role
wrote follow it. The mechanism is `sim/lang.py` plus the `language` section of
the config, and it applies to any character. What the switch measured on the
second character in particular is `docs/yukarin.md`, "Which language she is
addressed in"; the dated entry is in `HISTORY.md` under section 19.

The rule it enforces is his: **anything addressed to a character is in her
language, and only what the machine says to itself stays English.** What is
covered is decided by AUDIENCE, never by file. Her bible, her speech guide,
her situation block, what she notices of him, the closing instruction: hers. A
gauge JSON, a field name, a log line, a verdict written for a developer:
English, because nobody is being spoken to in it.

---

## 1. The two halves

The switch has two halves because two different kinds of writer put words in
front of a character.

**The arm covers what the prompt BUILDER writes at her.** `character.
instructions` names one of three (`sim/lang.py`, `ARMS`), or `auto`:

| arm | what it renders |
|---|---|
| `as_they_run_today` | the control, and the default. Her prompt as it stands, byte for byte: English scaffolding and section headers around whatever her identity sections are written in. Not "the English version" of anything -- a mixture -- and its value is that every measurement taken so far was taken under it |
| `in_english` | a clean, consistent English arm. Today it renders the same bytes as the control, because the scaffolding was already English and nothing was invented to fill the slot. It exists as a name a bench result can carry |
| `in_her_language` | the instructions in the language the character lives in |
| `auto` | **the default, and what an unset value means.** Not an arm: it is decided from `character.instruction_language`, and resolves to `in_her_language` when this switch has a second language to render for her and to the control when it has not. A character who says she lives in Japanese is instructed in Japanese without anybody switching her on, which two of the four were not while the control was everybody's default |

Every wording lives in the source twice, side by side, and the arm picks which
one renders (`sim.lang.say` returns the `t(en, ja)` closure every caller uses).
**Every translated string goes behind this switch**: the first character is on
the control and shares every line of the code those strings live in, so a
Japanese line not selected here would reach her too.

**What language `in_her_language` renders is declared per character**,
`character.instruction_language`. It is not derived from `writes_to_him` and
cannot be: the first character is bilingual, answers him in English, and every
measurement ever taken on her was taken with English instructions. So her
declaration is "english", `lang.switchable` is false for her, and `/lang ja`
refuses her with that reason rather than rendering her nothing.
`lang.reads_ja` needs both halves -- the arm AND a second language to render --
so setting the arm on a character who has no second arm changes no byte.

**The material line covers the sentences UNDER the headings.** The builder
cannot reach those, because other roles wrote them: the facts about him, the
notes of his she read, what she has decided about herself and about him, her
reflections, her promises, the gist of a lookup. Flipping the arm alone leaves
her reading her own language over English prose, which is what the coverage
audit found. So each role named in `language.material_roles` is given one line
(`sim.lang.material_line`) naming the language its prose goes out in. The line
is addressed to a mechanism, so it is English, and it excepts three things by
name: field names, keys and any value the prompt lists as a fixed choice stay
as spelled, because code reads those and cannot find a translated one; and
anything quoted from the record is quoted as written.

`language.enabled` is the switch over that half alone. Off, the labels move
and the prose under them does not.

**Nothing already in the record is translated.** A fact written in English
stays as written and ages out through the forgetting curve like any other. The
effect of a flip therefore arrives over a day, as the material roles refresh
what they wrote.

---

## 2. The 30 material roles, and the five that are deliberately not

`language.material_roles`: `anticipation`, `approach`, `commit`,
`commit_him`, `diary`, `downloads`, `experience`, `expect_him`, `foresee`,
`habits_him`, `him_profile`, `ick`, `lookup_gist`, `morning`, `note_read`,
`nudge`, `recall`, `reflect`, `revise`, `revise_self`, `rupture`,
`search_gist`, `settle_beliefs`, `spiral`, `timeline`, `vault`, `weekly`,
`withhold`, `wonder`, `wonder_answer`.

`vault` and `downloads` joined it when those two roles started writing the
record of what she read rather than her reaction to it: the record is put in
front of her, so it goes out in her language. `affection` left it at the same
time: its `why` is a few machine-facing words for the log now, and telling it
to write its prose in her language would contradict its own instruction.

A role is on that list only when its output is prose FOR HER and nothing else.
Five roles write into her prompt and are off it on purpose, each for a reason
that must be read before anything is added:

| role | why it stays English |
|---|---|
| `phone` | the digest's prose is scanned with English patterns for the one thing off his screen she remarks on (`resident/sight.py` `noticed_line`: "searched", "he had open", a filename). Its LABEL in her prompt is already in her language; the account under it is the machine's. The raw activity the role is HANDED is English on every arm for the same reason and one step further out: how hard he was typing and how long the machine has been up are bands with a wording in each language (`sensors/bands.py`), and the caller passes no chooser (his call) |
| `director` | the scene's `location`, `activity` and `with` are matched by the ledger and the wardrobe |
| `schedule` | the same: the day's blocks carry places and activities other modules match on |
| `state` | gauge arithmetic. Nobody is being addressed in it |
| `editor` | it writes two things at once. Its note is put in front of her and its verdict goes to the log, so instead of a list entry it forks inside its own prompt on `[[?her_language]]` (`prompts/editor.txt`, `prompts_yukarin/editor.txt`): the note in her language, the verdict in English |

The first three are the largest patch of English still addressed to a
character running on the third arm, and the ground for two of them only half
holds: the digest and the scene are both rendered into her situation as prose
she reads. That is an open decision, recorded in `HANDOVER.md`.

Also correctly English, so that nobody translates them by mistake: the
editor's `problem` field and its whole evidence bundle (machinery reading
machinery); the `intent`, `coherence`, `digest_judge`, `gloss` and `devoice`
roles, which are judgements the machine asks itself; the single-string labels
in the programs' words tables that head a block inside a ROLE's prompt rather
than inside hers (`editor_digest_label`, `state_digest_label`, the
`director_*` labels, `timeline_label`, `him_profile_digests_label`,
`expect_days_label`); every log line, every `/command` answer and
`sim/context.py`'s view, which are for a developer or for him; and the two
belief briefs beside the belief pairs, which go to the ick call.

---

## 3. Where each piece of her prompt gets its language

The audit that produced this table built one character's whole reply prompt
twice for one real moment with the model refused, and listed every line of the
Japanese arm that was still English: 83 lines before the work, 77 after, and
every one of the 77 is material another role wrote (receipts:
`data/retired/20260904_lang_switch/`).

| what she reads | who writes it | how the language is decided |
|---|---|---|
| her bible, her speech guide | her own prompt files, per character | the file itself |
| her backstory | kv `backstory`, her sheet | the sheet itself |
| every section heading in the system prompt | `persona/persona.py` `_system` | the arm, through `lang.say` |
| what she has decided about herself and about him -- the items | `revise_self`, `revise` | the material line |
| ... the asides beside them ("you used to think this more simply") | `sim/model_of_her.py`, `sim/model_of_him.py` | the arm |
| what these people are to her -- every item | `sim/sentiment.py`, composed in code | the arm |
| facts about him -- the heading | the program's words table | the words table |
| ... the facts | `timeline` | the material line |
| his anime list, the shelf summary and what he is on | `sensors/mal_monitor.py` | the caller's own `t()`; the editor still gets English |
| notes of his she has read -- each takeaway | `note_read` | the material line |
| the record of his notes folder and of his downloads | `vault`, `downloads` | the material line |
| ... the sentence each record is filed under | the program's words table | the words table |
| her diary, her own memories, her reflections | `diary`, `experience`, `reflect` | the material line. All three of the reflect role's prose fields -- the thought, the line under it she would never say, the question she will not ask -- are hers, because she reads all three back as something she is carrying; its delta keys and field names are code's and stay as spelled. The second character's own copy of that prompt used to order the three written in English, against the material line in the same prompt; the dated note is in `HISTORY.md` |
| things she has told him about herself | `timeline`, kv `self_claims` | the material line |
| a rupture, a spiral, withholding, an attachment stance | `sim/rupture.py`, `spiral.py`, `withholding.py`, `attachment.py` | the arm |
| the `<carrying>` frame line | `persona.carried_for` | the arm |
| the situation block: the clock, her feelings, her register, her stance, what is aimed where, the unsent draft | `persona/persona.py`, `sim/state.py`, `sim/stances.py`, `sim/primitives.py` | the arm |
| ... him: the silence, the receipts, the gap, his rhythm, his mood, what she expects, foresees and wonders | `persona/persona.py`, `sim/receipts.py`, `rhythm.py`, `expectations.py`, `foresight.py`, `wonder.py` | the arm |
| ... her day: the household, the scene label, today so far, goals, promises, the ledger, the shape of the day, yesterday, the morning | `persona/persona.py`, `sim/household.py`, `goals.py`, `commitments.py`, `ledger.py`, `outlook.py` | the arm |
| ... the scene TEXT under that label, and the day's plan | `director`, `schedule` | off the list on purpose: English |
| ... her promises' text | `commit`, `commit_him` | the material line |
| ... the phone: the digest label, the glance, the note read, the recall, the lookups, what she knows by name, what he is watching | the program's words table, `sim/known.py`, `recall.py`, `watching_him.py` | the words table, `t()` passed in |
| ... the digest TEXT | `phone` | off the list on purpose: English |
| ... the raw activity the `phone` role is HANDED, bands included | `sensors/system_monitor.py`, `sensors/bands.py` | English on every arm, deliberately: it is material for a role, not prose for her. The band wordings are paired and the renderer takes a `t(en, ja)`, which `sim/phone.py` passes as `None` -- the decision, not an omission |
| ... a lookup's gist | `lookup_gist`, `search_gist` | the material line |
| ... the line saying a work is not one of hers | `sim/works.py` + the words table | the words table |
| ... lore recalled, and its preamble | her own lore file; `persona/persona.py` | the file; the arm |
| this message, the phrases she has been reusing, the closing instruction, the length line | `persona/persona.py`, `sim/shape.py` | the arm |
| why she is writing a second message straight after her own | `scail.py` `maybe_afterthought` | the arm. It was English for every character until both residents were found reading it in English, cut off mid-word; the closing line's cut now falls where a sentence ends (`sim/thread.py` `cut_to_sentence`) |
| the one imperative line's header, and a nudge's text | `persona/persona.py`; `nudge` | the arm; the material line |
| the editor's note to her | `editor` | `[[?her_language]]` inside its own prompt |
| why she is the one starting this -- the urge, named, in front of what she wants to say | `sim/intent.py` `reason_line` | the arm |
| a line another running character wrote to her | `sim/peers.py` | the room's own `language` setting, per contact |

**A role's own prompt file is not in the table, with one exception.** The
instructions in `prompts/<role>.txt` are addressed to the role rather than to
her, so they are English for every character and the arm does not reach them.
The exception is the paragraph inside several of them headed "How she talks":
that is addressed about her voice, and it was one character's -- her register,
her filler words and her dialect -- sitting in a file the other character
loads. It is now a hole the character fills from her own sidecar
(`character.neutral_file`, `Config.fill`), so the language and the register of
that paragraph are hers by construction. The roles it covers are the five that
write her head-voice (`anticipation`, `experience`, `morning`, `reflect`,
`spiral`), the scene director, the diary, the spoken aside, the role that
decides how she goes at a question she is afraid to ask, and the two that turn
over one of her own people.

**Known English no character reaches today.** `embodied/money.py`
`persona_line` and `embodied/situation.py` `persona_line` / `travel_line` /
`trip_lines` are English with no pair, and the sleep-block note in
`resident/sight.py` is appended to a plan the `schedule` role writes in English
anyway. None of them renders for a character on the third arm as things stand.
They are a gap for a future embodied character in another language, written
down here rather than fixed blind.

---

## 4. Throwing the switch

    /lang            the arm in force, where the choice came from, the three
                     arms, and the material roles it carries
    /lang ja         her own language, from the next prompt on
    /lang en         English
    /lang auto       forget the choice; her config decides again

`/lang` writes kv `instructions_override` on that character's own save and is
read back at boot before anything builds a prompt, so the arm moves between two
replies and survives a restart with no config edit. Precedence, highest first:

1. a process override (`sim.lang.set_override`, which is how
   `tools/voicelab.py --instructions` benches the arms inside one process);
2. `SCAIL_INSTRUCTIONS` in the environment, for a whole run;
3. `/lang`, the saved choice;
4. her config, when it names an arm;
5. `auto` -- her config saying so, or saying nothing -- which is her own
   language when she declares one this switch can render, and the control
   when she does not.

The boot line and `/provider` both print which arm is rendering and where the
choice came from, so a bench result and a bill are read together. Nothing is
written to a config file, so a choice to keep permanently is a config edit.

**A character whose instruction language is english is refused, with the
reason**, because the third arm would render the same bytes as the second for
her and every measurement taken on her was taken that way.

---

## 5. Config, and the existence table

| key | what it is |
|---|---|
| `character.instructions` | the arm, or `auto` (the default): decided from `instruction_language` |
| `character.instruction_language` | which language the third arm renders for this character |
| `language.enabled` | whether the roles that write her material are told which language to write it in |
| `language.material_roles` | the 30 roles that get the line |

`Config.REQUIRES` carries `"language": None` -- the mind and the relationship,
because every character is addressed in something -- and
`Config.conditions()` carries `her_language`, which is what
`[[?her_language]]` in a prompt forks on.

---

## 6. What it costs, and what it changed

The arm is +405 prompt tokens a call on the second character (+0.9%) and one
cold cache call after a flip; the same dollars to four decimal places. Over 24
draws on six real moments, with the scene, the digest, the gauges and the drawn
length all held still, the arm moved nothing measurable: 304 characters mean
against 309, one bubble in every draw either way, nothing meta leaking in
either arm, one polite ending in 24 drafts, and the same longest verbatim run
taken out of the block she was handed. The reason there was nothing to see is
that the control arm already handed her a bible and a speech guide in her own
language: her identity was never the English part. What is English is the
account of him, which is the half the material line reaches, and that arrives
over a day rather than in one reply.

The first reply on the third arm measured 23 of 34 situation lines with no
character of her language before the flip and 2 after, both of the 2 being the
block's own tags. The full tables are in
`data/retired/20260904_lang_switch/REPORT.md` and the reading of that reply is
`data/retired/20260904_reply_audit/REPORT.md`.
