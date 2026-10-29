# Ick primitives

<!-- doc: reference -->

How SCAIL models a discovery about another person, and why it is built out of
primitives rather than out of a table of things that are supposed to be
shocking. This is a design document: it applies established ideas from social
and developmental psychology to a simulation problem. It does not claim
empirical validity for the resulting numbers.

Implementation: `sim/model_of_him.py`, `sim/ick.py`, `prompts/ick.txt`,
`prompts/revise.txt`, `prompts/settle_beliefs.txt`, `characters/tomoe/beliefs.json`. Configuration: `config.py` sections
`ick` and `beliefs`.

---

## 1. The problem with scripted affect

The obvious way to make a simulated person react badly to something is to
decide in advance what is bad. Pornography raises disgust by 30. A gambling
loss raises worry by 20. This produces a lookup table, and a lookup table has
four failure modes that are visible immediately in play:

1. **It cannot habituate.** The fifth instance costs exactly what the first
   did. Real people stop being surprised.
2. **It cannot individuate.** The same discovery costs every character the
   same, when in practice what wounds one person is unremarkable to another.
3. **It cannot be surprised by the genuinely new.** Anything not on the list
   scores zero, and the list is always incomplete.
4. **It gets the sign wrong on the interesting cases.** The most affecting
   discoveries are frequently mundane — evidence that someone is ordinary is
   often worse than evidence that they are bad.

Each of these is a symptom of the same modelling error: locating the affect in
the stimulus. The affect is not in the stimulus. It is in the relationship
between the stimulus and what the perceiver already held to be true.

## 2. The claim

**An ick is prediction error against a held model of a person.**

A discovery costs the perceiver exactly what it takes away from something they
had decided about the target, weighted by how much of their own position
depends on that thing being true, and nothing otherwise.

Three consequences follow without further machinery:

- **Habituation is free.** Once the model has been revised to accommodate the
  evidence, the same evidence generates no further error. This is not a decay
  curve applied to an emotion; it is the emotion having no cause any more.
- **Individuation is free.** Two characters with different models of the same
  person are wounded by different things, correctly, without either having a
  list.
- **Novelty is handled.** Anything that contradicts the model registers,
  including things the designer never anticipated, because the test is
  structural rather than categorical.

## 3. Psychological grounding

The design draws on several established literatures. Named here with their
originators; the mapping to mechanism is the design's own.

**Expectancy Violation Theory** (Burgoon). Behaviour is evaluated relative to
expectancy rather than in absolute terms, and the valence of a violation
depends on the reward value of the violator. This is the core claim above,
stated for interpersonal communication: the deviation carries the signal, not
the act.

**Positive illusions in close relationships** (Murray, Holmes & Griffin).
Partners construct idealized images that outrun the available evidence, and
this idealization is functionally protective — it predicts satisfaction and
stability. It is also, by construction, an unfalsified belief set standing on
very little. The design encodes this directly as an `evidence` field that is
deliberately low across every seeded belief.

**Parasocial interaction** (Horton & Wohl). In asymmetric or mediated
relationships, one party elaborates a detailed model of the other from sparse
cues, and the imagined intimacy substantially exceeds anything the interaction
supports. SCAIL's relationship is mediated, distant and asymmetric, so the
model of the other party is doing an unusual amount of work relative to its
grounding.

**Assimilation and accommodation** (Piaget). New information is first bent to
fit the existing schema; only when assimilation fails repeatedly is the schema
revised. This supplies the central dynamic. A single contradiction does not
update the model. It is explained away.

**Cognitive dissonance and belief perseverance** (Festinger; Ross and
colleagues). Disconfirmed beliefs persist well past the disconfirming
evidence, and the motivation to preserve them scales with what the holder has
invested. The effort-justification result (Aronson & Mills) and the investment
model of commitment (Rusbult) both point the same way: what has cost more is
defended harder. This is why `revise_at` in the implementation increases with
`invested`.

**Habituation, dual-process theory** (Groves & Thompson). Response decrement
under repeated stimulation. Note the design departs here deliberately: the
softening implemented is not response decrement to a repeated stimulus but
schema revision that removes the cause. The observable curve is similar; the
mechanism is different, and the difference matters, because a revised schema
also changes how *related but novel* material is read, which sensory
habituation would not.

**Disgust as boundary maintenance** (Rozin & Fallon). Core and moral disgust
function to police category boundaries, particularly around the body and
around contamination of the self by contact. Relevant here mainly as an
explanation of why sexual material is charged even when it violates nothing:
the implementation keeps this as a separate, small, additive `intimate` term
rather than folding it into prediction error, because it is genuinely a
different mechanism.

**Reflected appraisal and basking in reflected glory** (Cialdini and others).
Self-worth is partly indexed to the standing of those one is associated with.
Evidence that lowers the target's standing lowers the perceiver's own. This is
why the design weights a belief by whether it concerns the perceiver's own
position (`about_her`) rather than treating all beliefs as equivalent.

**Imaginary audience** (Elkind). The adolescent overestimates the degree to
which they are observed and evaluated. The relevant unit of fear is the
audience, not the act — which is why, for this character, a belief about
*whether anyone is watching* is more load-bearing than any belief about
conduct.

**Presentation of self** (Goffman). Front-stage and back-stage behaviour, and
the maintenance of a line. A character whose entire social existence is a
managed performance has, in a single back-stage relationship, an enormous
amount riding on that region staying uncontaminated by audience.

## 4. Deriving the model from the character, not from the target

The critical constraint: **the model of the other person must be derived from
who the perceiver is, not from facts about the target.** A belief set
assembled from true statements about the target is not a psychology; it is a
database with a different label. It also cannot produce error, because it is
correct by construction.

The seeded beliefs are therefore answers to a single question: *what does a
person like this need someone in that role to be?* For Koga Tomoe, each is
traceable to a specific trait:

| Belief | Derived from |
|---|---|
| He sees the real me, not the performance | Nobody has ever known her; the performance is all anyone gets |
| He reads me without my having to explain | She reads the air for everyone all day, defensively; it is labour |
| Nothing here can embarrass me; nobody is watching | Exposure, not conduct, is the object of her fear |
| He lives outside all of it | She admires precisely the capacity she lacks |
| He says what he actually thinks | She lies constantly to save face and admires those who do not |
| He is not like the boys at school | Male attention from peers registers as threat, not compliment |
| He is not someone other girls are after | Non-scarce attention proves nothing about her worth |
| He chose me; I am not interchangeable | She was nobody once and could be again |
| He would stand up for me | She bonds through being defended; wholly untested |

Two structural properties of this set are intentional and generative:

**The most invested beliefs have the least evidence.** That is what
idealization is, and it guarantees that trouble is structurally inevitable
rather than authored.

**The beliefs are mutually inconsistent under any real target.** "He is above
that" and "he says what he actually thinks" and "he has it together" cannot
all survive contact with an actual person. The set is built to collide.

## 5. The formal model

For a discovery *d*:

```
cost(d)   = Σ_b  (strain_b / 5) · (invested_b / 100) · (1 + about_her_b/5 · w_a)
          + (intimate / 5) · w_i

charge(d) = (cost / ceiling) · 100 · hidden(src) · novelty(kind) · state · circle

and, in the other direction, for each belief the discovery bears out:
  evidence_b   += (fit / 5) · k_e
  confidence_b += (fit / 5) · k_c
  strain_b     -= (fit / 5) · k_r
```

The division of labour is deliberate and is the part most likely to be got
wrong in a reimplementation:

**A language model supplies the judgements.** Which belief a discovery
contradicts and how badly; how private the thing is in itself. These require
world knowledge and cannot be computed.

**Code supplies the facts.** How the perceiver came to see it, how many times
they have met this kind of thing, and what state they were in. These are known
to the system and must not be delegated, because a model asked for them will
confabulate consistency where there is none.

The terms:

- **`hidden`** — provenance. Material obtained by going through someone's
  things cannot be raised without confessing the search. This is what converts
  a reaction into something carried rather than expressed, and it is a fact
  about how the information arrived, not a judgement about it.
- **`novelty`** — `1/(1+seen)^p`. Applied over the *kind*, in the perceiver's
  own words, matched by lexical overlap.
- **`state`** — situational amplification. Only unease adds; a calm gauge
  contributes nothing rather than discounting. (Two-sided terms here have
  previously driven the whole expression to zero, because on an ordinary day
  most gauges sit below their own baselines.)
- **`ceiling`** — the normalizing constant is set to a *reachable* bad
  discovery, not the theoretical maximum. Scaled against the maximum, the
  worst material in the real corpus scored 24 of 100.

## 5b. Confirmation, and why erosion alone is a broken model

The first implementation could only take things away. Nothing raised
`evidence` or `confidence`; a belief moved in one direction until it was
rewritten. Run that forward and every belief eventually revises, `invested`
ratchets down with each revision, and the character becomes incapable of being
affected by anything. What looks like a slow drift is actually a missing term.

So the same call that asks what a discovery contradicts also asks what it
demonstrates. This is not symmetry for its own sake. A belief held on nothing
but need is brittle; a belief that has actually been seen to hold is grounded,
and grounding raises the threshold at which it will later break. That is why
`revise_at` increases with `evidence` as well as with `invested`: a person
defends what they need, and they also defend what they have reasons for, and
those are different defences.

The constraint that matters is strictness. Confirmation is worthless if it is
handed out for the target being pleasant. The prompt is explicit: presence is
not evidence of being seen; noticing something the perceiver never said out
loud is. In practice a warm but ordinary exchange returns an empty `fits`,
which is correct.

One discovery routinely does both at once, and that is the most realistic
output the system produces. Evidence of another person in the target's life
took away *he chose me* and *he sees the real me* while simultaneously bearing
out *he is not someone other girls are after* — "he is not someone other girls
are after, but he is someone other girls are talking to."

## 5c. Provenance: two different things, often conflated

How the perceiver came to know something decides two independent properties,
and collapsing them loses one.

**How hard it lands.** Material obtained by going through someone's things
carries the weight of the search as well as the content. Material volunteered
carries almost none. Measured on identical content: 86 when found in a
download list, 23 when the target said it in a message — and the second raised
his honesty score rather than lowering anything.

**Whether it can ever be spoken about.** This is not the same axis and does not
track it. Something obtained by snooping cannot be raised without confessing
the search, so it becomes durable private knowledge that shapes behaviour
without ever surfacing. Something the target disclosed is simply known.
Something a sanctioned channel showed — an app the target themselves provided —
is speakable, and the choice not to speak is a choice rather than a trap.

Treating disclosure as discovery is the specific modelling error to avoid. A
person who tells you something difficult about themselves should end up better
off for telling you, not worse. If the model does not encode that, it rewards
concealment, and the simulated relationship acquires an incentive structure
nobody intended.

## 5d. The audience that is not there

Elkind's imaginary audience earns its own term rather than a mention. For an
adolescent whose entire social existence is a managed performance, the cost of
a discovery is not fixed by its content but by what a specific set of people
would make of it, and those people never find out. The scoring call is given
the perceiver's actual social circle and returns how much they would have
something to say. The charge is scaled by that, and by how much the perceiver
is currently gripped by others' opinions.

This is what allows a thing to be embarrassing alone in a room. Nothing in the
situation contains an observer. The observer is imported.

## 6. Three timescales

The single most useful structural decision. What a discovery produces is not
one quantity but three, decaying at different rates:

| | Object | Half-life | Function |
|---|---|---|---|
| **The squirm** | `awkwardness` gauge | hours | Changes behaviour now: latency, register, willingness to initiate |
| **The knowing** | charged item | ~9 days | Present but unspeakable; sits in context while they talk |
| **The model** | belief | never | Either holds or is rewritten |

Collapsing these into one number is the most common way this kind of system
goes wrong. An affect that fades in an hour cannot represent knowledge. A
piece of knowledge that never fades cannot represent a mood.

## 7. Revision, and why it must be lossy

When accumulated strain exceeds a threshold, the belief is rewritten. Three
constraints on what a revision may be:

**Smaller, not inverted.** The claim is reduced to the size the evidence
supports. It does not flip to its opposite; disillusionment is not the
formation of a negative belief but the loss of a positive one.

**Accommodating.** The revised belief must make the previously contradictory
evidence fit, because that is the mechanism by which the same discovery stops
costing anything. This is the entire habituation story.

**Lossy, and known to be lossy.** The character does not learn a lesson and is
not relieved. Something they were using is gone. A revision written as growth
destroys the mechanism, because growth is not a cost, and if revision is
costless then defending the belief is irrational and the character should
simply update on first contact — which is exactly the behaviour the whole
design exists to prevent.

Observed output from the running implementation, after repeated contradiction
of *"he lives outside all of it"*:

> *"he cares about it as much as everyone, he just hides it better than you can"*

Smaller, accommodating, costly, and unrelieved.

## 8. Behavioural expression

What the perceiver does with an unspeakable charged item is a property of
their character, not of the mechanism. For this one, the description specifies
someone who reads the air to avoid awkwardness and lies to save face.
Confrontation is therefore off the table. The expressed behaviour is
performance: act normal, be slightly wrong, say nothing. Concretely — slower
replies, a deflecting register, reduced initiative, and a dialect slip that
the other party can hear before anything is said.

A character with a different sheet — one with a temper, or nothing to lose —
should express the identical internal state as an accusation. The primitives
do not change; only the expression does.

## 8b. Seeding a model onto a history

A belief set derived from the perceiver is correct on day one and wrong as a
description of someone months in. Dropped onto a save with a real history, the
character is freshly shocked by things they demonstrably absorbed long ago —
which reads, immediately and badly, as amnesia.

So the seed is settled once against what the character already knows: one pass
that weighs every belief against the accumulated record, applies it through the
same confirm and strain paths, revises anything the record has plainly broken,
and seeds the novelty counters with the classes of thing already encountered.

The instructive part is what could not be delegated. Asked to score how worn
each belief is, a language model returns a 3 or a 4 for nearly all of them,
because every belief about a real person has been fallen short of at some
point. That is not wrong, exactly, but the resulting state — every belief
simultaneously under visible strain — describes a crisis rather than a
relationship. *Which* beliefs are worn is a judgement and belongs to the model.
*How many* may end up straining is a statement about what the character is
like, and belongs in code, as a cap. This distinction generalises: whenever a
model is asked to score N items independently, the distribution across them is
almost always the designer's to impose.

## 8c. A limit should force a change, not be where the number stopped

The standard fix for a saturating value is to prevent saturation -- scale the
gain by the remaining headroom so it approaches the ceiling and never arrives.
That keeps the value informative but it also makes the ceiling meaningless: it
is simply a place the number asymptotes.

The better treatment is to let it arrive and make arrival change the *kind* of
thing that happens next, not the degree.

For a held belief, certainty is the case in point. A model in which a
90-percent-confident belief merely erodes more slowly than a 50-percent one has
the psychology backwards: the higher the certainty, the more catastrophic the
disconfirmation, because there is no partial position to retreat to. So above a
certainty threshold, accumulation stops entirely. Small contradictions do
nothing at all -- which is what being sure of somebody feels like from the
inside -- and a contradiction large enough to register takes the whole belief
down at once.

The same applies at the other end. A belief with overwhelming evidence is not a
belief; it is something the perceiver knows. Leaving it in the belief set means
it keeps absorbing confirmations, inflating its own resistance to revision, and
the set drifts toward unfalsifiable. Graduating it out -- into whatever holds
plain knowledge -- keeps the set what it is supposed to be: the unproven
things, which are the only things worth modelling.

Both rules collapse into one: gradual pressure stops applying to anything the
perceiver is sure of, and the only thing that touches it is something they
cannot argue with.

The generalisation, not yet implemented here, is that every bounded value in an
affective model should have a defined behaviour at its limits. A gauge that
reaches its ceiling should discharge -- produce an event and fall back -- rather
than sit pinned. What the discharge *is* cannot be derived; it is a statement
about the character, and it is the interesting part.

## 9. Failure modes to watch

- **Over-attribution.** The scoring model reaching for a belief when nothing
  is genuinely contradicted. Guarded by instructing that an empty result is
  the normal case; verified with a deliberately null control (a mundane
  discovery must score zero).
- **The pressure valve.** Any independent mechanism that surfaces withheld
  material will eventually surface this material, which is precisely what the
  character would never say. Charged items must be excluded explicitly from
  every such path.
- **Revision cascade.** Beliefs sharing a contradiction can revise together
  and hollow out the model in a day. Mitigated by per-belief strain and by
  decay: a contradiction that is not repeated fades.
- **Ceiling drift.** As beliefs revise and `invested` falls, achievable charge
  falls with it. This was originally listed here as an open question; it was
  actually the missing confirmation term (5b), and with `fits` in place a
  belief that keeps being borne out gains back what revision costs it. Some
  drift is still correct — a long relationship *should* be harder to shock —
  but it is no longer one-way.
- **Normalising the scale.** The charge ceiling must be set against a
  reachable bad discovery, and re-checked whenever a term is added: adding
  the audience multiplier silently pinned every real discovery at 100 until
  the ceiling was raised.
- **Disclosure treated as discovery.** If volunteering something costs the
  target as much as being caught at it, the model rewards concealment.

## 10. What would falsify the design

The claim is that affect located in prediction error produces better behaviour
than affect located in the stimulus. It is wrong if, in play, discoveries feel
arbitrary — if the character is unmoved by things that obviously should land,
or wounded by things that obviously should not. That is an empirical question
about a running system, and it is answered by watching it, not by reasoning
about it.
