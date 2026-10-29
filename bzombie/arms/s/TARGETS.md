# S arm inject targets (`POST /control/inject {target, value}`)

- `bz.order`, `bz.cut_constant`, `bz.answer_first`, `bz.echo`, `bz.trend`, `bz.reality`, `bz.keep_mood_tags`, `bz.keep_register`: the real sim/bz.py switches (true/false), set on `app.config.bz`, which `Bz.on()` reads on every call. Aliases: constant_cut, change_words, reality_labels, mood_tags=keep_mood_tags, register=keep_register. Unknown: 409.
- `gauge.<name>`: a gauge value 0-100 through `State.set_value`. Derived gauges answer 409 with the reason.
- `stances`, `memory_cards`, bare: no switch in this build (409).

Unknown target: 409. A removal test snapshots first, restores, injects, then replays.
