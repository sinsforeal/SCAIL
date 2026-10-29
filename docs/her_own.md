# Something of her own

A plan, not a build. PROJECT §19 is the character; `docs/primitives.md` is the
psychology it plugs into; dated notes go to HISTORY under §19.

---

## 1. The problem, stated as a measurement

Every relational quantity the second character has is a reading of one man.
Closeness, attachment, cost of loss, the ledger, fright, the territory latch --
all of them are about him. Her one interior accumulator is the diary, and the
diary's only mechanical job is to lower what he holds of her. There is a ruler
for exactly this already: `sim/worldshare.py`, built at his ask *"want to see
her world being mostly me decrease over time"*, which records per day what
share of her inner lines, her events, her reasons and her own memories mention
him. For her that share is close to everything, and nothing in the machinery
can move it, because there is nothing else for her to be about.

That is the difference between a relationship simulation and an entity. It is
not fixed by more psychology; it is fixed by giving her something outside
herself that is not him.

## 2. What the tape says she actually does alone

The hand extraction of her week and the reading of the earlier extraction agree
on a shape, and it is not the shape I would have guessed. She does not have
hobbies in any useful sense. **She attaches to a real external thing with a
very slow clock, checks on it far more often than it changes, and is genuinely
moved when it changes without her.**

The clearest instance is ep058, cues 80-91, verified verbatim on the tape:

> 「いよいよゆかりのお家がね、なくなってしまいました。」
> 「前に住んでたお家がね、その不動産屋さんのホームページで、おすすめ物件って
> 載ってるのを見るのが楽しみだったの。」
> 「昨日いつものように、日課として、そのホームページに行ったらね、なんとも
> うおすすめられてなくって、ついに、誰かの手元へ行ってしまいましたよ。」
> 「髪の毛を切りに行った帰りに、こっそりなんか遠くから眺めることもできなく
> なったなー…切ない気持ちになりましたよ。」
> 「誰が住むんだろうね。」

Read what is actually in that. The flat she used to live in is listed on an
estate agent's site. She calls it **her** house. Checking the listing is 日課, a
daily ritual, and she says she looked forward to it. She *also* went and looked
at the building itself, secretly, from a distance, on the way back from the
hairdresser. When the listing disappeared she felt a small real grief. And the
last thing she says is not about herself at all: *I wonder who'll live there.*

It is not an isolated moment. The same shape recurs across the run:

- A pair of shoes left at the agency that somebody took by mistake. She has
  been watching them **for months** and speculating about the person walking
  around in the wrong ones (ep063).
- The corridor light outside her flat, out for six months, fixed, then
  flickering again (ep020, ep023, ep037).
- Flat-pack shelves that arrive in ep008 and are finished in ep015, occupying
  her entrance for seven weeks, which is how the entrance came to be described
  at all. Her own count of what is left does not reconcile between weeks.
- A rabbit soft toy going round in the washing machine on the lowest water
  setting, watched for no reason, on a day she describes as being as alone as a
  locked-room murder (ep051).
- The cardboard box with her own name printed on it, taken from the bin store
  by a neighbour, whose onward journey she narrates as a story (ep049).

**The mechanism is the same every time: a slow external state, watched much
more often than it moves, cared about out of proportion, and mourned when it
resolves without her.** That is the thing to build, and it is not a hobby
system. A hobby would be about her enjoying something. This is about her
attaching to something that does not know she exists.

## 3. The proposal

Follow the pattern `tomoe/scenery.py` already established for the first
character. Its rule is the important part: *"This is machinery, not her. She
'took' these photos; she never searched for them."* The harvester runs on its
own clock, when she is not looking, and her record shows only what reached her.
The same rule holds here -- **she never scrapes anything.** A watcher keeps a
small database of real external things with real state; she is told, at most
once a day and often not at all, that one of them has changed.

Three parts.

### 3.1 The watcher

A harvester on its own schedule (`watch.harvest_every_hours`, off her ticks)
that keeps a handful of real, public, slow-moving things and records their
state each time it looks. One table: what it is, where it is, when it was last
seen, what it looked like, and whether it is still there. Nothing more.

The bar for a candidate is exactly three properties, and everything else is
decoration:

1. **Real**, with a stable public address that can be checked again tomorrow.
2. **Slow** -- it changes on the scale of weeks or months, not hours. A feed
   that updates constantly is news, and news is not this.
3. **Indifferent** -- it has no relationship to her and no relationship to him.

### 3.2 What she watches

Ranked by how well the corpus supports them, not by how easy they are.

**A property listing, and it is the strongest by a distance.** Japanese estate
sites list flats with photographs and a price and they *disappear when let*.
That is a real slow clock with a real terminal event, and the corpus documents
her doing precisely this, daily, with the emotional payload attached. One
listing, chosen once, checked by the watcher, and one day it is not there.

The corpus even supplies the framing she used: the flat was one she *had lived
in*. She has no such flat -- but the premise gives her something better and
stranger, which is that her own 2003 addresses and haunts are all real places
that still exist and have been let and re-let a hundred times since. A listing
in the ward she used to live in is hers in the only way anything can be.

**A slow public object with a state.** The shoes at the agency have an obvious
analogue: anything with a public page and a status that resolves. A lost-property
notice board. A shop's "coming soon" hoarding. A building with a demolition
notice and a date. The test is that it will one day stop being there and she
will not be told why.

**The weather in Fukuoka.** She is Fukuoka-born and lives in Tokyo, and the
project already fetches weather. Fetching it for a city she is not in costs one
extra call and gives her a thing to notice that is about where she is from
rather than where she is. Small, cheap, and it is hers.

**Her own broadcast, twenty-two years to the day.** Every episode carries a real
broadcast date, from the first week of April in her first year onward. Today minus twenty-two years lands on a real episode
with real cues. This one needs no scraping and no invention: it is her own
recorded past, the one thing in the system he did not give her and cannot take.
It is also the only feed that could make the gap between 2003 and now something
she experiences rather than something the premise asserts.

### 3.3 How it reaches her

Through the machinery she already has, and never as a new kind of event.

- The watcher writes a row when a state **changes**, not when it looks.
- A change is offered to the director the way a share-worthy thing already is:
  a small fact, at most one a day, most days nothing.
- Whether she mentions it is hers. Whether it goes in the diary is hers.
- **The diary is the payoff.** Her diary today can only be about him, which is
  why `kept_private` only ever moves what he holds of *her relationship*. A
  diary entry about a flat she never lived in is the first thing she has ever
  written that is not about him, and it feeds `act_room` -- the gap between what
  she is selling and what she is -- with material he has no part in.

## 4. How it wires to the psychology

This is the part that makes it more than colour.

**`cost_of_loss` gets a second source.** Today it is the integral of her
attention on him and nothing else, so everything she stands to lose is him.
A watched thing that resolves is a small loss with no relationship in it, and
the corpus is explicit that she feels those.

**The ruler already exists.** `sim/worldshare.py` records the share of her inner
lines, events and memories that mention him, per day, and nothing reads it back
into her. **If this works, that number falls, and if it does not fall, it did
not work.** That is a real test with an existing instrument, which is rare.

**It gives the interpretation framework something safe to practise on.**
`docs/interpretation.md` specifies how a turn in never-observed space is
recorded as an inference rather than a fact. Her reaction to a listing
disappearing is exactly such a turn -- the corpus shows the shape once, in one
episode, and everything after that is extrapolation. It is a good first case
because being wrong about it costs nothing.

## 5. What is real and what is not

Worth being exact, because the failure mode of this project is a plausible
invention becoming canon.

**Real:** the listing, its address, its price, its photographs, the date it
disappeared. The weather in Fukuoka. The cue and the date of a broadcast
twenty-two years ago. All checkable, all reproducible, none of it generated.

**Not real, and must be recorded as inference:** that she cares. That she
checks daily. That she is sad when it goes. The corpus supports each of those
**once**, in ep058, for one flat that was actually hers. Extending it to a flat
she never lived in is a level-3 claim -- functional completion from a driver --
and the framework says such a thing is written down as an inference carrying
its evidence level, reviewed, and killed if it is wrong.

## 6. Cost, and what could go wrong

**Cost is close to nothing.** One fetch a day of one page. No model call for the
watching; at most one small call when something changes, and that can be folded
into the compile she already runs. Compare `tomoe/scenery.py`, which runs searches,
harvests accounts and judges authors.

**Three ways it goes wrong.**

*It becomes a tic.* She mentions the flat every day and it stops being a slow
attachment and becomes a catchphrase. The suppression rule from the
interpretation framework applies directly and should be wired from the start
rather than added after.

*It reads as quirky.* The corpus tone is not whimsical -- 「切ない」 is a small
real sadness, and the line that follows it is about a stranger, not about her.
If the output sounds like a character being endearing about a house, it is
wrong, and the fingerprint will not catch that. It needs a person to read it.

*Scraping breaks.* A listing site changes its markup and the watcher silently
returns nothing. It must fail loudly, and a thing it has stopped being able to
see must not be reported to her as having disappeared -- that would manufacture
a grief out of a broken selector, which is the exact class of fault this project
keeps paying for.

## 7. His call

1. **Which feed first.** The listing is the strongest and the most work. The
   broadcast-twenty-two-years-ago feed needs no scraping at all and is the only
   one that is unarguably hers. Fukuoka weather is the cheapest.
2. **Whether she may watch a place she never lived.** The corpus attaches her
   to a flat that was hers. Giving her one that was not is the level-3 step, and
   it is the whole plan, so it is worth saying yes or no to explicitly.
3. **Whether this waits for the interpretation framework.** Building the watcher
   first and the recorder second means her first weeks of reactions are not
   filed as inference. Building the recorder first delays this. Either is
   defensible; doing them in the wrong order quietly is not.
