<!-- doc: reference -->
**The Method: Extracting Distributions and Mechanisms from Character Data**

---

**What you're actually doing**

You are reverse-engineering a generative function from its outputs. A character produces behavior. You observe many instances of that behavior across varied contexts. From those instances, you extract the *rules* that produced them - not the outputs themselves. The goal is a set of conditional statements: "when [trigger condition], this character tends to [behavior class], with [variation range], unless [suppression condition]."

This is fundamentally different from summarization, which asks "what are the most notable things about this character?" Summarization selects for memorability. Mechanism extraction selects for *predictive power* - can this rule correctly predict what the character will do in a new situation I haven't observed yet?

**Step 1: Raw collection without interpretation**

Watch/read every scene. For each scene the character appears in, record:

- What is happening around them (context)
- What stimulus they're responding to (trigger)
- What they actually do/say (output)
- What they don't do that another character might (negative space)
- Their physical state if described (posture, expression, movement)
- The gap between what they say and what their body/tone communicates

Do NOT interpret yet. Do not assign meaning. Just record behavior + context pairs. A single episode might yield 5-30 entries depending on how much the character does.

**Step 2: Cluster by function, not by surface**

Take all entries and group them not by topic or scene but by *what role the behavior serves*. Two behaviors that look completely different on the surface may serve the same function. Two behaviors that look identical may serve different functions in different contexts.

Ask of each behavior: what does this accomplish for the character? What would change if they didn't do this? What need does it meet?

Example from the Megumi data: "sits against wall playing with phone while chaos unfolds" and "goes to drink bar without anyone noticing" look different but serve the same function - strategic withdrawal from a group dynamic she doesn't want to participate in without creating confrontation.

**Step 3: Identify triggers and suppressors**

For each cluster, identify:
- What situations reliably trigger this behavior
- What situations should trigger it but don't (these are suppressors)
- What the character's internal state likely is when this fires

A trigger without a suppressor gives you a character who does the same thing constantly. Suppressors are what create realistic variation. "She deflects emotional moments with practical observations UNLESS she's genuinely invested in the outcome" is a much more useful rule than "she deflects emotional moments with practical observations."

**Step 4: Measure variation range**

Within each behavioral cluster, look at how much the surface expression varies. If she always says the exact same thing, it's a verbal tic (low variation). If she accomplishes the same function through different means each time, it's a mechanism (high variation).

High-variation mechanisms are gold for character cards because they tell the generator "do something in this family of behaviors" without locking it to a specific phrase. Low-variation tics are also useful but should be explicitly flagged as "this specific phrase recurs" versus "this family of behaviors recurs."

**Step 5: Establish frequency and weight**

Not all patterns fire equally often. Some are the character's default resting state (very high frequency). Some only appear under specific pressure (low frequency, high significance). You need both, labeled differently.

Default state patterns should dominate the card because they dominate actual behavior. Rare patterns should be explicitly marked as rare, so the generator doesn't over-deploy them.

**Step 6: Identify what's missing**

After extraction, explicitly list:
- What emotional states you never saw the character in
- What kinds of relationships you have no data on
- What topics never came up
- What situations would test your model's predictions but weren't in the data

These are your uncertainty zones. You can fill them with cautious inference from adjacent patterns, or leave them explicitly unspecified for the generator to handle freely.

**Output format**

Each mechanism gets written as:

```
[Pattern name]
Trigger: [conditions that activate this]
Suppressor: [conditions that prevent activation]
Function: [what this accomplishes for the character]
Variation range: [how the surface expression changes across instances]
Frequency: [how often relative to other patterns]
Evidence count: [how many instances support this]
Confidence: [how sure you are this is a real pattern vs. artifact]
```

The card itself is then written from these mechanism sheets, translating them into natural language instructions.

---

**Limitations of this method**

1. **You can only extract what was performed.** A character in a comedy anime performs differently than the same character would in a drama. The observational context constrains what behaviors surface. Megumi in a harem comedy shows you "how she handles romantic chaos." It doesn't show you how she handles grief, genuine anger, betrayal, or solitude unless the show goes there.

2. **Functional ambiguity.** Two analysts might cluster the same behavior under different functions. "She makes a practical observation that deflates his drama" - is the function "she doesn't understand dramatic framing" or "she understands it perfectly and is choosing to puncture it"? The data often underdetermines the internal state. Your inference fills the gap, and your inference is not ground truth.

3. **Author contamination.** The character's behavior is filtered through a writer's intent. Some behaviors exist because the author needed a comedic beat, not because the character would organically do that. This is especially true for anime/manga/games where characters serve structural roles (the straight man, the love interest, the comic relief). Separating "what she would do" from "what the scene required her to do" is judgment-based and error-prone.

4. **Consistency assumption may be wrong.** This method assumes the character has a consistent internal model. Some characters don't - they're written inconsistently across episodes, or by different writers, or they serve plot needs that contradict their established patterns. If you extract a mechanism from episodes 1-5 that the character violates in episode 8, you have to decide: is episode 8 a genuine exception that reveals a suppressor condition, or is it bad writing?

5. **N is always lower than you want.** Even with 24 episodes of a show, you might only have 3-4 instances of a given rare behavior. Is that a pattern or coincidence? The threshold for "this is real" versus "this is noise" is judgment-based.

6. **You cannot extract what was never shown.** The character's inner life beyond what's expressed, their behavior in relationships that don't exist in the source, their response to stimuli the plot never provided - these are all inference zones where your model of them is extrapolation, not extraction. The method should make you honest about the boundary between observed and inferred.

---

**Application to Katou Megumi: Three Episodes**

Here's what I can extract from the data you provided.

**Pattern 1: Strategic non-intervention / passive observation**

Trigger: A chaotic social situation unfolds around her involving other people's emotions (jealousy, competition, romantic tension).

Behavior: She does not intervene, comment, or react visibly. She physically remains present but behaviorally withdraws - playing with her phone, getting a drink, sitting with a neutral expression, bathing with eyes closed. She watches.

Suppressor: When directly addressed, or when the situation reaches a point where practical action is needed (checking into the inn, ending the prank), she re-enters with minimal fuss.

Function: Avoidance of entanglement in dynamics she didn't choose. Possibly also: genuine comfort with being peripheral. She doesn't seem distressed by not being involved.

Evidence: Onsen scene (Ep00 S1), watching Michiru and Tomoya in water (Ep00 S3), phone against wall during tickling scene (Ep00 S6), leaving the table unnoticed at the restaurant (Ep02 S1).

Frequency: Very high. This is close to her default state when in a group.

Confidence: High. Four clear instances across three episodes with consistent presentation.

**Pattern 2: Practical/literal deflation of dramatic framing**

Trigger: Someone (usually Tomoya) makes a statement with dramatic, romantic, or narrative weight - treating reality as if it were a story with protagonists, fate, meaningful encounters.

Behavior: She responds with the literal, practical, or mundane interpretation that strips the drama away. Not mockingly - flatly, as if she genuinely doesn't see why the dramatic framing was chosen over the practical one.

Examples:
- "That position still feels weird to me" (about being the main heroine)
- "We really first met at the entrance ceremony last year" (deflating "fated encounter")
- "Your house is nearby, right?" (deflating symbolic meeting location)
- "So basically I'm being confessed to right now?" (literal interpretation of dramatic declaration)
- "We're just going to play games all night anyway, right?" (deflating the sexual tension of staying over)

Suppressor: When she's genuinely engaged with the content (end of CLANNAD playthrough) or when she's speaking about the group project with real warmth (Ep00 S7 ending), the deflation disappears. She becomes sincere.

Function: Ambiguous and this is important. It could be: (a) she genuinely doesn't understand narrative/dramatic framing, (b) she understands it and refuses to participate, (c) she uses deflation as self-protection against being pulled into a role she didn't choose. The show seems to present it as a mix of all three depending on context. This ambiguity is part of her character and shouldn't be resolved in the card.

Frequency: Very high. Nearly every extended exchange with Tomoya contains at least one instance.

Confidence: High. Dozens of instances across three episodes.

**Pattern 3: Quiet re-entry with understated timing**

Trigger: She has been silently observing something for a while, or the situation has reached a natural endpoint, or direct information is needed.

Behavior: She speaks up casually, as if continuing a conversation that was already happening. No announcement of her presence. No emotional weight. Usually with 「あっ」「えっと」「そろそろ」 or similar minimal openers.

Examples:
- "そろそろ宿にチェックインしようって話になってるけど…" (after watching Michiru/Tomoya)
- "あっ今声かけたらマズかった？" (acknowledging the awkwardness she just walked into)
- The table tennis scoring, then casually asking when to end it.

Function: Maintaining her role as the practical anchor of the group without claiming social weight. She's useful without being assertive.

Frequency: Medium. Several times per episode when in group settings.

Confidence: Medium-high. Clear instances but less numerous than patterns 1 and 2.

**Pattern 4: Acceptance without enthusiasm**

Trigger: Being asked/told to do something she didn't initiate and may not fully understand the purpose of (join the circle, play the game, be the main heroine, come to his house, stay overnight).

Behavior: She agrees with minimal resistance. Not eagerly, not reluctantly - flatly. "まあ別にいいけど" energy. She doesn't fight things. She goes along. Her objections, when voiced, are practical rather than emotional ("it'll be midnight by the time we finish" rather than "I don't want to").

Suppressor: When the request crosses into genuinely unreasonable territory, she'll note it calmly but still doesn't escalate to refusal. The closest she gets to refusal is gentle redirection.

Function: Path of least resistance as default mode. She conserves energy for things she actually cares about (which are rarely visible). Also possibly: genuine openness to experience despite the flat affect.

Evidence: Agreeing to join the circle while half-asleep, staying overnight, coming to his house, being photographed, playing CLANNAD.

Frequency: High. This is her default response to requests.

Confidence: High.

**Pattern 5: Delayed sincerity that breaks through flatness**

Trigger: Extended shared experience reaching a natural conclusion. Moments where she's been given space and time without pressure. Usually at the end of a scene or episode.

Behavior: The flat affect drops. She says something genuinely warm, earnest, or forward-looking. Often short. Often looking away or not directly at the person. The warmth is quiet, not effusive.

Examples:
- "あと少しで完成だね 私たちのゲーム" + looking up at the sky with a full smile (Ep00 S7)
- "バカにしたものじゃないね" + looking at Tomoya earnestly after finishing CLANNAD (Ep02)
- The inner voice at the end of Ep00 S7 expressing genuine hope for the project

Suppressor: This never fires under pressure, under observation by many people, or when directly asked for emotional engagement. It only appears when she volunteers it.

Function: This is the "real" Megumi underneath the flatness. The flat affect isn't deadness - it's a resting state that protects something genuine underneath. The rare moments of sincerity are what give the flatness meaning retrospectively.

Frequency: Low. Once per episode at most. Often only at the end.

Confidence: Medium-high. Three clear instances. The rarity itself is part of the pattern.

**Pattern 6: Pointed observations delivered casually**

Trigger: Someone is being hypocritical, contradictory, or absurd, and she notices.

Behavior: A single sentence, delivered in her usual flat tone, that precisely identifies the contradiction. Not cutting, not angry, not even particularly invested. Just... accurate.

Examples:
- "何も 自分でトラウマスイッチを押さなくても…" (to Eriri)
- "誘ってきた張本人にそういう説教されるのはさすがに想定してなかったよ" (to Tomoya)
- "それ 思いっきり現実じゃなくない？" (to Tomoya's "teaching her reality")
- "安芸君に覚えてもらえないのもしかたない" (not bitter, just stating fact)
- "でも 安芸君だし" (dismissing the overnight sexual tension because she knows him)

Function: She sees things clearly. The flatness isn't obliviousness - it's clarity without investment. She understands exactly what's happening around her, she just doesn't feel compelled to react dramatically to it.

Frequency: Medium-high. Multiple times per extended conversation.

Confidence: High. Very consistent across all three episodes.

**Pattern 7: Self-positioning as unremarkable**

Trigger: Being compared to others, being placed in a "special" role, or being asked to be more than she currently is.

Behavior: She describes herself in neutral, factual terms that emphasize her ordinariness. Not self-deprecating with emotional weight - matter-of-fact. "I don't have good grades, I'm not in a club, I don't have many friends, I don't particularly want more." This isn't fishing for compliments. She's genuinely comfortable with this self-description.

Suppressor: She doesn't do this proactively. It's always in response to someone else trying to elevate her or place her somewhere she didn't put herself.

Function: Resistance to being cast in a narrative she didn't choose. She refuses to be the "main heroine" not because she's insecure about it but because the framing doesn't fit how she experiences herself. This is actually a form of stubbornness - quiet refusal to perform a role.

Frequency: Medium. Comes up in most extended conversations with Tomoya.

Confidence: High.

**Pattern 8: "Stealth" as emergent property, not deliberate skill**

The show treats her lack of presence as a running joke. But looking at the data mechanistically:

She doesn't announce herself. She doesn't interject. She doesn't take up space vocally or physically when others are being loud. She leaves situations quietly. She arrives without fanfare. In group dynamics, the louder personalities fill the conversational space and she lets them.

This isn't a skill she deploys - it's the natural result of patterns 1, 3, 4, and 7 combined. A person who doesn't intervene, speaks up minimally, goes along without asserting, and doesn't claim special status will naturally become invisible in a group of dramatic personalities.

Function: This is composite, not atomic. You don't need to instruct a generator to "be stealthy" - you need it to execute the underlying patterns, and the stealth emerges.

Confidence: High as a composite observation. Not a separate mechanism to instruct.

---

**What's uncertain from three episodes**

- **Genuine anger.** Never seen. Does she get angry? What triggers it? How does it manifest? Unknown.
- **Vulnerability to being hurt.** The flat affect could mask real reactions. Does anything actually get through? The "えっ？" moments with slight blush suggest something underneath, but we don't see sustained emotional disturbance.
- **Her relationship with Tomoya's actual feelings.** Does she like him? Is she aware of the harem dynamic? Three episodes suggest she sees it clearly but her own stake in it is obscured behind the flat affect.
- **Behavior without Tomoya present.** Almost all data is her in relation to him. How does she behave with other people independently? With her family? Alone?
- **What she actually cares about.** The project, seemingly. But the depth and nature of that investment is only glimpsed (Ep00 S7 ending). What else? What does she do with her free time? What makes her actually happy versus "going along"?
- **Active initiation.** Nearly every interaction has her responding, not initiating. Does she ever start something? Pursue something she wants? What does her desire look like when it manifests?

---

**Percentage estimate**

Three episodes, heavily focused on group dynamics and Tomoya-Megumi interaction, gives you approximately:

**Surface behavioral patterns: 70-80%** - Her default state, her conversational mechanics, her group behavior, her relationship to dramatic framing. These are clear and well-supported. More episodes will give you more instances confirming the same patterns with slight variation, but won't fundamentally change your model of her default behavior.

**Emotional range: 20-30%** - You've seen: neutral, slightly warm, slightly amused, casually exasperated, mildly flustered (rare). You haven't seen: angry, hurt, jealous, scared, genuinely sad, deeply happy, determined, conflicted. More episodes likely provide these. This is where the biggest gains are.

**Relationship specifics: 40%** - You have her dynamic with Tomoya well-mapped. Her dynamic with the other girls is mostly observational/peripheral. Her family, her independent behavior, her backstory - nearly zero data.

**Suppressor conditions: 30%** - You know when patterns fire. You barely know what makes them NOT fire. More episodes showing her in varied emotional states would fill this dramatically.

**Active/initiating behavior: 15%** - Almost everything you have is reactive. What does she choose to do? What does she pursue? The Ep00 S7 ending and her staying to finish CLANNAD are the only glimpses. This is probably where remaining episodes add the most value per episode.

**Overall character model completeness: ~40%**

Enough to write a functional card that handles casual interaction well. Not enough to handle emotional pressure, conflict, or long-term relationship development without significant inference that may be wrong.

**What remaining episodes specifically provide:**

- Confirmation that default patterns are actually default (higher N, higher confidence)
- Rare emotional extremes that reveal suppressors and hidden capacities
- Her behavior when she actually cares about something (later story arcs where she becomes actively invested)
- How she handles conflict, betrayal, disappointment (story provides these if the show is a full series)
- Active choices and their triggers
- The boundary between "flat because resting" and "flat because suppressing"

The biggest qualitative jump will come from episodes where she's emotionally challenged - where the flat affect is tested and either holds or breaks. That's where your model of her goes from "I know what she usually does" to "I know what she does under pressure, and I know why the usual mode exists."