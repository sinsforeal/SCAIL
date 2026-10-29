# Her voice: recorded koikano lines first, MiniMax otherwise

The VN channel plays her generated line in one of two ways. If the line is one
she already spoke in the koikano record, the recorded clip is played. If not,
MiniMax synthesises it in a cloned voice. The recorded clips are the source
material for that clone, so the two are meant to sound like the same woman.

## The recorded-clip path

`tools/voice_index.py` reads the read-only koikano record
(`...\koikano_work\game_logic.jsonl`), keeps every line whose `voice` id is
`MMK` plus six digits, normalizes its text, and writes
`data/vn/voice_index.json`:

    python tools\voice_index.py            # build the index
    python tools\voice_index.py --check    # fail if the file on disk is stale

The build reports its size; the current record gives 2509 lines with a clip id,
2455 distinct normalized texts, 20 texts that more than one clip carries, and
0 clip ids not on disk. The corpus is read in place and never written.

`channels/vn_voice.py` loads the table and answers one question for the
channel: for this line, is there a recorded clip, and which file. Where her
voice comes from is one mode, `tts.voice_mode`, also a control on the stage:

- `tts` -- never play from tape. Every line is synthesised, a clip id the
  model named included.
- `exact` (the default) -- play a recorded clip only when the line, normalized
  (NFKC width fold, whitespace removed, edge punctuation and brackets
  removed), is exactly a line in the table. This is a line she said verbatim.
- `approximate` -- `exact`, and also a pause-only near miss: the line is at
  least eight characters (`PARTIAL_MIN_LEN`), one recorded line's normalized
  edit-distance ratio is at least 0.9 (`PARTIAL_RATIO`, one edit in ten
  characters of the longer string), that line is the unique best by a margin
  (`PARTIAL_MARGIN`, 0.05), and the words themselves are identical -- only
  pauses may differ. A changed particle (ね/よ/わ), a changed number, or a
  changed negation is a different sentence and still misses; the ratio cannot
  read meaning, so the words are compared directly rather than trusted to the
  ratio.

A line that normalizes to a tiny fragment (`……っ` -> `っ`) is refused in every
mode: it is a recording artifact, not a sentence. Real short utterances
(`はい`) still play. A miss returns nothing and the caller synthesises the
line instead.

A clip id the model names itself (`MMK000123`, as the line, not merely inside
it) wins over any text match, in `exact` and `approximate`.

The old boolean `tts.clip_partial` still seeds the mode where `voice_mode` is
absent: false -> `exact`, true -> `approximate`. A save that holds the old
`vn_clip_partial` is read once the same way.

## How the channel chooses

`channels/tts_handler.py` (`TTSQueue`) owns the voice worker. Before it renders
or serves a cached line it asks the channel for a recorded clip through the
optional `clip_for(text)` method. The order is:

1. a clip id named in the line (`exact` or `approximate`; `tts` skips it);
2. a recorded koikano clip whose text matches the line under the mode above;
3. the MiniMax cache, keyed by voice, model, synthesis text, emotion, language and pronunciation settings;
4. a fresh MiniMax render.

The phone and Telegram channels have no `clip_for`, so their path is unchanged.
The VN channel serves a recorded clip from the corpus in place at
`/asset/clip/<MMK....ogg>`; a synthesised line is copied into `data/vn/voice`
and served at `/audio/<name>`. The page plays either through the same audio
element.

Without a MiniMax key, a line with no recorded clip stays silent and the text
is still shown; nothing raises. A recorded clip needs no network at all.

## Clone the voice (the MiniMax step)

The recorded clips are the clone reference. The prepared sample and its
manifest are read-only corpus files:

    F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\bible\hyakka\voice\hyakka_voice_sample_2min.mp3   (123.0 s, 35 non-H clips)
    F:\REPS2\clipboard capture (kirikiri)\extracted_games\koikano\koikano_work\bible\hyakka\voice\hyakka_voice_sample_manifest.json

To clone:

1. Upload `hyakka_voice_sample_2min.mp3` to the MiniMax voice-clone endpoint or
   console (the file-upload plus voice-clone pair, or the "voice cloning"
   screen). The 30 s sample beside it is a shorter alternative.
2. The voice MiniMax issues is named `moss_audio_<uuid>`.
3. Set that id in `config_momoka.json` at `tts.voice_id`. The commented default
   in `config.py` is empty, which means "whatever the shared MiniMax config
   says"; a character's own value overrides it.

**Done (2026-09-17):** Momoka's clone was made and the id is set in
`config_momoka.json` and `characters\momoka\bundle.json`:

    YOUR_VOICE_ID

Synthesised lines are now in her own voice; recorded clips still play from tape
when her line matches one (that is what the index is for).

## MiniMax expression controls

The linked [speech-to-text API](https://platform.minimax.io/docs/api-reference/speech-to-text)
returns transcription, optional speaker segments and timestamps. Its response
does not label emotion. Our voice path uses the separate
[HTTP text-to-speech API](https://platform.minimax.io/docs/api-reference/speech-t2a-http).
The API's [request schema](https://platform.minimax.io/docs/api-reference/speech/t2a/api/openapi.json)
allows `voice_setting.emotion`: `happy`, `sad`, `angry`, `fearful`, `disgusted`,
`surprised`, `calm`, `fluent` and `whisper`. The schema recommends leaving it
unset unless a particular delivery is needed; the model then reads emotion
from the text. `fluent` and `whisper` are limited to the 2.6 models, and the
current `speech-2.8-hd` does not support `whisper`. Speech 2.8 also supports
short interjection tags such as `(laughs)` and `(sighs)` inside text.

Momoka's generated lines now use `speech-2.8-hd`, her cloned voice id,
`language_boost: Japanese`, and
`pronunciation_dict: {tone: ["百花/ももか", "一悟/いちご"]}`.
The delivery worker asks the existing 28-label emotion reader before it
prepares each clip and freezes that label for the VN face. A small mapping
sets MiniMax emotion only for clear labels (joy, sadness, anger, fear, disgust,
surprise, relief and close variants); other labels leave MiniMax's automatic
reading in control. Recorded koikano clips still win and retain their acting.

The scene director may propose one supported interjection tag on a new scene
opening or emotional beat. The channel consumes the cue once by identity;
delivery adds it to the first suitable synthesis request only. The visible
dialogue stays unchanged. When no director tag is offered, an explicit laugh
or sigh written in the line may add an audio-only tag. Cache identity includes
the actual synthesis text, selected emotion, model, language, and pronunciation
dictionary. The sync endpoint is preferred. Its failure invokes an internal
async create/query/retrieve fallback with the same settings and a bounded
wait. The old external script remains for characters without these options.
The live config wraps nested dictionaries in `Config.Section`; the worker
converts the pronunciation rule to ordinary JSON data before computing the
cache key or calling MiniMax. This fixed the 2026-09-18 TTS error that also
left the backlog's ♪ without audio.

The [async T2A task API](https://platform.minimax.io/docs/api-reference/speech-t2a-async-create)
has the same `voice_setting.emotion` values in its
[request schema](https://platform.minimax.io/docs/api-reference/speech/t2a-async/api/openapi.json).
Its [long-form workflow](https://platform.minimax.io/docs/guides/speech-t2a-async)
creates a task, polls its status, then retrieves the completed file. It is
intended for long text (up to 50,000 characters directly or 1,000,000 by file),
so it would add a task wait to each short VN line without unlocking extra
emotion controls. The current synchronous HTTP path fits interactive lines.

Re-running `python tools\voice_index.py` after a corpus change rebuilds the
index; it names the clips only, so the clone step does not need to be repeated
for the index to work.
