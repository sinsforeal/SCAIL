# The friends' room drawn as a sky -- a proposal

Proposal, 2026-09-10. Target: `talkapp/app/index.html` (the whole client is
that one file). The spec of record for everything it touches is
`docs/talkapp.md`; the group payload it draws is §6 there and
`docs/peer-talk.md` §4b. Nothing in this proposal changes the hub, the bot
channel, the adapter or the APK.

## 1. What the reference material shows

Eighteen frames in `UI proposal/`, all of one messenger: an anime phone app
that draws a group conversation as a night sky instead of a stack of
rectangles.

**The surface.** The whole screen is a sky -- a vertical gradient, pale green
at the top through teal to blue at the bottom, scattered with small white
stars and a few soft lens flares with faint trails. It is the background, not
a panel; nothing is boxed.

**A person is a round token lying on that sky.** A coloured disc with the
person's name or picture on it, about a fifth of the screen wide, resting on
the lower two thirds of the sky at a fixed place: `Fu` on yellow, `東郷` on
pale blue over a cloud, `Yuna` on pink over cherry blossom
(`Screenshot_628`, `_630`, `_631`). One frame has a name plate under the token
(`風`, `Screenshot_635`). The disc is the picture and the identity both; there
is no name in the message.

**A line said is a coloured band curved into an arc across the top.** Each
band holds exactly one line of text, has a round cap at its left end in the
speaker's colour, and reads left to right along the curve. The bands are
concentric and nested, all struck from a centre off the screen up and to the
right. Four to six are legible at once; older ones curl away toward the
top-right corner and off the edge.

**A thin white filament runs from a band's cap down across the sky to its
speaker's token.** That is how the app says who spoke: a line you follow, not
a name you read. Watch it work across four frames -- `Screenshot_625` has
`私も〜` newly arrived with its filament still unattached, `_628` has it
landed on `Yuna`, `_630` adds `トドですか!?` on a new blue band with its own
filament, `_631` has that filament resolved onto `東郷`. In `_641` and `_642`
two filaments cross, which the design allows and does not try to avoid.

**The newest line is the outermost band, at the bottom of the stack.** Each
arrival pushes the older bands up and inward toward the corner. The crown of
the stack carries a tab reading 履歴 (history) with an up-arrow
(`Screenshot_624`): the door to the full scrollback.

**Everything else is minimal.** Emoji sit inline at the end of the text on the
band (☀, 😖, a spiral). The composer in `Screenshot_624` is a plain white
field at the foot of the screen with an attach clip, a place pin and a swap
control. `Screenshot_634`--`_637` show the same sky with a bottom bar of small
glyphs and a single token at lower left, so the layout survives a
conversation with one other person in it. `Screenshot_632`/`_633` are the
phone's home screen, round app orbs on a decorated wallpaper -- context for
where the app lives, not part of this proposal.

## 2. Where it goes

The design's one strong idea is that **identity is spatial**: who spoke is a
place on the screen and a line drawn to it.

That solves a problem the friends' room has plainly. The room she is in with
her own people (`renderHerChat`, drawn from `buckets("phone")`) carries five
to ten speakers. Right now each turn is a row with the name printed above it,
and the name has already been through two repairs: `splitLines` cuts a burst
apart on its `Name:` prefix, `canon(who)` folds a nickname back onto the
roster name, and which side a turn sits on comes down in the payload as every
name that means the open character (`group.me`). All three exist because a
name as text is a weak handle. A token per person and a filament to it is the
same information, stronger, and it keeps working when a burst has four
speakers in it.

**His own chat gets it too** -- his call, 2026-09-10, over a recommendation to
leave it in bubbles. Two tokens rather than eight, hers and his, and every
line of the conversation as a band tethered to one of them. That view is also
the one carrying every piece of working machinery in the client, so §6a below
is the list of what has to be rehomed onto arcs and what each one becomes.

The in-person panel (`renderIrlChat`) reads the same item shape from
`buckets("irl")` and gets the sky for free, with the sky's own gradient
shifted -- a room, not a night.

**The bubble drawing is kept and stays reachable** from the menu, as the way
back. Not a narrowing of the above: the sky is what every panel opens in, and
the switch exists because this is his live messenger and a layout that turns
out to be unreadable on the phone in his hand needs an answer that is not a
rebuild.

## 3. What is already there to draw from

`buckets(mode)` hands back, per conversation, an ordered list of items with
everything the sky needs:

| field | what the sky does with it |
|---|---|
| `who` | picks the token; already through `canon` |
| `me` | the open character's own token, in a fixed home spot |
| `ja` | the text on the band |
| `text` | the English gloss -- **not** on the band, see §5 |
| `ts` | the time in the cap's tooltip and on tap, on his clock (`tlabel` / `ttitle`) |
| `date` | the day the panel header names |
| `undone` | a beat tonight's script has not played yet -- backstage only |
| `img` | a photo on the turn |
| `note` | a gist line or a turn she left on read; not an utterance |

Avatars are already served: `/avatar/<Name>` with a letter circle when there
is no picture, reached through `avImg(name)`. Colours are the only new thing
per person, and they are derived, not stored -- a hash of the name onto a
fixed palette of eight, so the same person is the same colour on every render
and no name is written into the client.

## 3a. The screen this is built for, and what is out of scope

**Scope: one portrait, full-screen layout.** No landscape. No cover display.
No separate tablet layout. The goal is to reproduce the drawing in the
reference frames on the phone's main display, and nothing else.

**The panel is 1080 x 2640 physical pixels, 6.7 inches, 22:9, 120Hz**
(a phone panel). That never
changes.

**Separately from the panel, he sets the smallest-width developer option to
600 layout units**, so that everything is drawn smaller and more fits on
screen. That setting does not touch the resolution -- it only changes how many
layout units the same pixels are divided into. At 600 the density works out to
288 against the stock 425, giving a viewport of 600 x 1467 layout units.

**So the app branches on nothing.** No size-qualified resources, no
phone-versus-tablet variants, no size classes. It measures the viewport it is
given and lays out in it. Then his setting is just a number read at runtime
rather than a mode the app switches into, and changing it later cannot break
the layout. 600 is also exactly Android's phone/tablet threshold, which is one
more reason to branch on nothing: sitting on that line is where variant
selection would be most surprising.

**Two units, kept apart.** Type size, touch targets and how much text and how
many tokens fit are in layout units, from the measured viewport. The drawing
itself rasterises at the full panel resolution -- arcs, glow and particles are
not coarser because more layout units were asked for.

Design against 600 x 1467 because that is what he actually looks at, and
sanity-check at the stock viewport so that a change of setting cannot break
it. Hardcode neither.

## 4. The geometry

All of it is one SVG per panel, sized to the view, plus two ordinary elements
for the header and the composer.

**The centre of the arcs sits off the screen, up and to the right**, at about
`(1.35 W, -0.55 W)` for a view `W` wide. Band `i` counting from the oldest
visible line is a circular arc of radius `R_i = R_min + i * (band + gap)`,
drawn as a `<path>`, with its text riding it in a `<textPath>` and its cap a
`<circle>` at the path's start. The newest line has the largest radius and
sits lowest; each arrival grows the stack downward and pushes nothing.

**Six bands are visible.** Older ones fade over the last two and are clipped
at the screen edge. The stack's crown carries the history tab, which opens the
flat list already written -- `renderHerChat` stays in the file and becomes the
scrollback behind the sky rather than being deleted.

**A token's place is deterministic**: the speaker's name hashed onto a
jittered grid over the lower two thirds, the open character's own token always
in the same corner. Deterministic because the panel is rebuilt from every
payload the bot pushes (about every 20 s) and a token that jumped on each
rebuild would be unreadable.

**The filament** is a two-segment polyline from the cap to the token's centre,
kinked once, in the screenshots' style. It is drawn under the tokens and over
the sky.

**The starfield is painted once.** A tiled CSS radial gradient or a canvas
drawn on resize -- never a per-frame animation loop. This runs in a WebView on
his phone all day.

**Motion on arrival only.** Bands are keyed by `date|time|who` so a rebuild
can tell an old band from a new one, and only a band that was not there last
render animates: the cap appears, the band sweeps in, the filament draws to
its token. Every other band is placed with no transition, or the twenty-second
push would make the whole stack twitch.

## 5. The five decisions this design forces

These are the places where the reference material is a Japanese messenger with
short lines and this project is not. His rulings, 2026-09-10; they are the
answers the implementer builds to.

**Text longer than a band becomes another band.** An arc at the innermost
radius holds roughly 22 Japanese characters, the outermost about 34. Her
friends' turns are regularly longer. A long line flows onto continuation bands
in the same speaker's colour; only the first carries the cap and the filament.
No ellipsis and no truncation. This is what the reference does -- the
two-line bands in `Screenshot_636` and `_637`.

**There is no English gloss in the client at all, anywhere, any more.** Not on
a band, not in the tap card, not in the flat list. The per-turn translation is
removed from the drawing entirely: the Japanese stands alone. The bot and the
hub are unchanged and the gloss may keep arriving in the payload; the client
simply never draws it.

**A photo does not go into a band.** The band extends outward and carries a
small preview hanging off it; tapping the preview opens the lightbox that
already exists. A sticker the same.

**He can scroll up through the conversation, through the blue up-arrow
button** at the crown of the stack -- the tab reading 履歴 in
`Screenshot_624`. It is a real control opening a scrollable history, not
decoration.

**Backstage keeps its present drawing exactly.** The banner, the amber items
and the checkbox are untouched; the sky does not restyle them.

**A gist line and a turn left on read are not utterances.** Items with `note`
set get no band and no filament.

## 6a. His chat: what has to move onto arcs

Everything below works today in the bubble drawing and is the reason his chat
was the cautious answer. Each keeps its meaning; only where it is drawn
changes.

**His reads.** Today an `IntersectionObserver` watches a row: a bubble of hers
on a visible screen is a read, sent to the hub as a phone event and stamped by
`store.mark_read`, which is how her schedule becomes visible to her. On the
sky the observer moves to the band's group, and the rule tightens: a band
counts as read only while it is one of the bands actually legible -- **not
clipped at the screen edge and not under the fade at the crown of the stack**.
A band that has curled away is not something he read. The history sheet counts
too: a row of hers on screen there is the same event, on the same path. This
is the single most delicate part of the job, because a read that fires early
tells her he saw something he did not.

**Her 既読 marks.** Today a mark under his bubble. On the sky the mark rides
the cap of his own band, with the time in its tooltip on his clock.

**The scrollback pager.** Reaching the top of the chat loads the page before
it: `before: msgs[0].ts`, the answer *prepended* never assigned, an empty page
stops it, the scroll offset held by the exact height the new rows added, and a
page still in flight when he opens another character does not land. The sky
has no scrolling container, so **the pager moves whole into the history
sheet**, which is a scrolling list of the same rows and keeps that behaviour
byte for byte. The sky itself draws only the newest bands. `takeSwipes` still
merges rather than assigns on an older page, for the reason it already does.

**Voice.** An `<audio controls>` cannot ride an arc. A band whose row has a
`voice` file gets a play control on its cap; the scrub bar and the save
control (the same `?dl=` URL, the same name on his clock) live in the tap
card. The speaker button for a line with no sound yet, on a character whose
bot renders on request, is also a tap-card control.

**Photos and stickers.** Not text and not a band. They are drawn as small
framed cards resting on the sky, tethered by a filament like any other line,
and tapping one opens the lightbox that already exists.

**The other answers to a message.** The three-dot menu, the "N answers" tag,
the waiting line and the rebuilt marker all move into the tap card. The
viewer itself is already a sheet over the chat and opens unchanged.

**Typing.** Today a line. On the sky it is a cap with no band yet, pulsing at
the foot of the stack with its filament already drawn to her token -- which is
the state `Screenshot_625` happens to catch.

**Link previews.** The card under the first link in a message goes in the tap
card, still fetched from `GET /preview?url=` and still appended with
`insertAdjacentHTML` rather than `innerHTML +=`.

**Day separators.** The sky has none. A band carries its day in the cap's
tooltip; the history sheet keeps the separators it has, from the same instant
(`dayOf`), so they still agree with the times beneath them.

**Two tokens, not eight.** Her token and his, each in a fixed corner, hers
carrying her reaction face when there is one -- the header already shows it
and the sky is a better place for it.

## 6. What must not break

- **Every time on the screen is his** (`tlabel`, `ttitle`, `dayOf`), and the
  panel header keeps naming its unit: *her `<date>`, times on your clock*.
  Her wall time reaches a screen only labelled.
- **No character's name is written into the client.** Whose turns are hers
  comes down in the payload as `group.me`; a nickname is resolved by
  `canon(who)`; a colour is a hash of a name, never a table of names.
- **A payload from a bot too old to send `me` marks nothing as hers** -- the
  sky must render that case as every token being somebody else's, not crash
  and not guess.
- **A read still means he saw it.** Whatever the observer is moved to, a band
  that is clipped or faded past legibility does not report a read.
- **Nothing is recorded before the action it claims happened.** A read is sent
  when the band was on the screen, never on a render.
- **The bubble drawing still works** and is one switch away.
- **No APK.** The Android app is a WebView over this page. The build stamp at
  the top of the file is bumped and the client reloads itself.

## 7. The work, in order

Each step lands in `talkapp/app/index.html`, which is the whole client in one
file. That is why these are sequential and not parallel.

1. **The sky renderer and the two panels that have no machinery on them**: the
   layout maths, the SVG, the tokens, the filaments, the colour derivation,
   the tap card, the history sheet, the arrival animation, the backstage
   styling, the CSS in both themes, and the friends' room and in-person panel
   drawn with it.
2. **His chat on the sky**: everything in §6a, on top of step 1's renderer.
3. **Run it**: `python tools/smoke.py`, the tests each step wrote, and a read
   of the client for the static faults the project keeps hitting -- a block
   pasted twice, an unbound name.
4. **Review before it goes live**, then the restart.

## 8. What this is not

It does not change what she says, what the hub records, what the bot sends, or
what any prompt contains. It is a new drawing of a record the app already
has.
