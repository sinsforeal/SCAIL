# SCAILV4 — 百花 (Momoka) one-character fork

A minimal visual-novel runtime for **千代田百花 / Momoka only**. She replies to
you in her own voice, on screen, with an expression and spoken audio. This is
the first cut: the goal is to get her running, not the full SCAIL feature set.

**Not here:** no memory tiers, no cast, no world, no peers, no sensors, no
phone. One character, one conversation, no autonomy.

## What it does

One turn:

1. Your line is appended to a running message list.
2. The model is called with her `bible.md` + `style.md` as the system prompt.
3. Her reply's trailing `[mood: X]` is split off (or inferred from keywords).
4. The mood is resolved to a koikano sprite (base + diff patch) and a face crop.
5. The line is rendered to audio by MiniMax and converted to Ogg/Opus.
6. The turn is written to `data/state.json`; the view polls it and draws.

She is always on screen. The sprite is composited on a canvas: the base PNG is
drawn, then the diff PNG at its `(x, y)` offset from
`expression_inventory.json`.

## Files

```
SCAILV4/
  config.json              provider, model, key path, TTS, absolute asset roots
  serve.py                 stdlib http.server: view, assets, audio, state.json, POST /say
  README.md
  momoka/
    prompts/bible.md       her prompt (used as-is)
    prompts/style.md       her speech guide (used as-is)
    sheet.json             her sheet
  runtime/
    common.py              paths + config + system prompt assembly
    llm.py                 OpenRouter chat client (one call, honest errors)
    expression.py          mood -> sprite + face, and the mood tag parser
    voice.py               MiniMax TTS with an on-disk cache; can play a game clip
    app.py                 the turn loop and state.json writer
  view/
    index.html / app.js / style.css
  data/                    generated: state.json, conversation.json, audio/, voice_cache/
```

## Facts it needs

- **OpenRouter key**: `F:/REPS2/SCAILV3/secerts/openrouter.txt` (read by path,
  never copied into this tree). Provider `openrouter`, base
  `https://openrouter.ai/api/v1`.
- **MiniMax key**: inside `minimax/config.json` (`api_key`), with the
  shared `voice_id` and `model_id`. Endpoint `https://api.minimax.io/v1/t2a_v2`.
- **Assets**: read in place from
  `…/extracted_games/koikano/by_character/MOMOKA_百花/` (sprites, faces, voice)
  and the koikano inventory/labels. Nothing in the koikano tree is modified.

## Run

Server (recommended):

```powershell
cd F:\REPS2\SCAILV4
python serve.py
```

Then open <http://127.0.0.1:8770/>. Type a line, press 送信. The first voice
must be started by a click (browser autoplay rule); click the page once.

Console only:

```powershell
python runtime/app.py
```

## Self-tests

```powershell
python runtime/expression.py                       # every mapped asset exists on disk
python runtime/llm.py --selftest                   # one real model call, prints her reply
python runtime/voice.py --selftest "百花、こんにちは。"   # one real TTS render
```

`llm.py --selftest` fails with the provider's own status and body if the call
does not work; it never prints a fake reply.

## Mood map

`runtime/expression.py` maps `{happy, smile, laugh, surprised, sad, worried,
angry, shy, neutral}` (plus `excited`, `talk`) to concrete CD asset ids. Every
id was checked against `expression_inventory.json` and against the files on
disk. Her **recorded** repertoire is `smile, worried, sad, talk, neutral,
surprise, excited, laugh`; `angry` and `shy` never appear on her lines and are
mapped to the nearest face she actually has (`angry`→sad, `shy`→smile).
`worried` uses a clasped-hands base sprite with no diff patch, matching the
worried face crop.

## Honest limits

- **No memory.** The conversation is one message list, kept to the last 40
  turns on disk (`data/conversation.json`). Nothing is summarised or recalled
  across sessions beyond that raw list.
- **No idle animation.** A static sprite per turn; no transitions, no `.ams`
  motion (matching the phase-1 koikano renderer).
- **Voice is the shared MiniMax voice.** Until a Momoka clone exists, she
  speaks with the machine's `YOUR_VOICE_ID…` voice. Set `tts.voice_id`
  in `config.json` to override it; the cache key includes the voice id.
- **One synchronous call per turn** on the server thread, so the input box
  waits for the reply and the voice render. That is fine for one user.
- **No safety net on the model.** A provider error is surfaced in the view's
  status line and returned as HTTP 502; the turn is not retried.
