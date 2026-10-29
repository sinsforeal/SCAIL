# Reactions -- `tools/reactions.py` (the images) and `sim/reactions.py` (her face in the app)

Spec of record. Summary: PROJECT.md §12.7. Recipe: the docstring at the
head of `tools/reactions.py`. Dated notes: HISTORY.md §5.96, §5.97.

## 1. Purpose

Not a selfie: a reaction. Frames of her from the actual anime, framed,
sorted by expression, curated by his eye, and shown as her changing icon
in the app -- one each time her mood crosses a threshold -- and as a
sticker in his chat. Character-agnostic: plug in the episodes and ~20
face crops; one config per character.

## 2. The tool: building the set

Per character under `data/reactions/<name>/`: `config.json`, `refs/`,
`refs_ccip.npy`, `reactions.db`, `merged/<bucket>/<id>.jpg`,
`dense_before/`, `pairs/`, `subs/`, `review_<bucket>.jpg`,
`verify_dense.jpg`, `baseline.json` (her own median face, per tag),
`model.json` (written by `learn`, read by `sort`), `run.lock`, `run.log`.

Stages of `run NAME --videos DIR` (GPU; cached and resumable per video;
`run.lock` refuses a second run while the first's pid is alive):

1. frames: ffmpeg at `fps` (1) plus shot changes (`scene_threshold`),
   scaled to `frame_width`, with timestamps;
2. faces: deepghs anime face detector (YOLOv8 onnx), `det_conf`,
   `min_face`, not clipped by the edge;
3. identity: CCIP (deepghs/ccip_onnx) -- the mean cosine distance over
   the `id_topk` nearest references, under `id_threshold` (0.20; the
   references' own median should sit well under it); CLIP-B/32 only if
   CCIP will not load; the tagger knows no character name, so the
   references are the whole identity signal. Every face that passes is a
   row of `appearances` (video, t, frame, box, id_dist, reaction_id)
   BEFORE any other gate -- the full record of where she is (`spans`);
4. framing: a square of `frame_scale` x the face, centred `frame_down`
   below the face centre, clamped, `out_size` 512;
5. quality: Laplacian sharpness over `min_sharp`;
6. dedup: phash within `dup_hamming` in the same video inside
   `dup_window_s`; CCIP feature distance under `dup_feat_dist` in the same
   window (the same pose seconds apart); phash within
   `dup_hamming_global` (3/64, ~95%) of anything kept;
7. expression: wd-vit-tagger-v3 on the crop, general tags over
   `tag_threshold`, stored raw; `sort` buckets them by `buckets` (tag
   lists, `a+b` a conjunction) scored on how far a tag is above HER OWN
   baseline face (`baseline_quantile`; a design with permanent blush
   would read flustered all day), `bucket_min`, `bucket_priority`;
8. store: `reactions` (id, video, t, frame, path, bucket, bucket_score,
   tags, id_dist, face_w, sharp, phash, rating, created, dense,
   sharp_before, t_before, sibling_of, label, expr, line), `videos`.

Then: `dense NAME --videos DIR` (the second pass: `dense_window_s` either
side of every kept frame at `dense_fps`; a sharper frame of her --
`dense_gain` -- replaces in place, only the same moment: CCIP distance to
the before face under `dense_same_moment`, and no open mouth
(`dense_mouth_open`) where the before was shut (`dense_mouth_closed`);
the before crop kept in `dense_before/`; `--redo` restores),
`merge NAME` (the replaced first-pass crops come back as sibling rows;
`layout: merged`), `subs NAME --videos DIR` (the subtitle line at each
image's second, jpn else eng, one extraction per video; no model),
`review NAME` (contact sheets), **his pass over `merged/<bucket>/`**
(delete, move), `prune NAME` (a moved file's folder becomes its `label`
and stands through every later sort; a file with no row is adopted; a
row whose file is gone is deleted), `stats`, `spans`, `verify` / `pairs`
(the dense pass judged), `dedupe` (sibling pairs kept), `learn NAME`
(`EXPR_TAGS` probabilities -> logistic regression on his labels; writes
`model.json` for `sort` to use on unlabelled rows; measured at 46
corrections: no feature set beats the rules -- run again past a few
hundred), `sort [--rules]`.

GPU: onnxruntime-gpu needs the NVIDIA cu12 pip wheels; `_cuda_dlls()`
puts them on the DLL path. `HF_TOKEN` in the user environment is
optional. Measured: ~6 min an episode on the 4070 SUPER; a supporting
character yields 10-90 images an episode where she appears.

## 3. The reader: her face in the app (`sim/reactions.py`)

Reads `data/reactions/<reactions.character>/reactions.db` directly: a row
whose file is present, `COALESCE(label, bucket)` as its face.

**When.** Every loop pass (`tick`). Mood valence = (mood - baseline) /
`state.mood_from.max_swing`, cut into five bands at -0.45 / -0.15 / 0.15
/ 0.45. A face when: the band changed since the last tick; or the face
that is up changed inside the band (`bucket_for` differs from the last
`wanted`, and is not neutral); or `surprise` crossed `surprise_from`.
`min_gap_minutes` between faces. The first tick after a boot only
records the band -- a restart changes no face.

**Which.** `bucket_for(band)`: surprise first; at the floor anger >=
`anger_from` -> angry, sadness >= `sadness_from` -> sad, energy <=
`tired_below` or fatigue >= `fatigue_from` -> tired, else sad; in the off
band anger, then anxiety >= `anxiety_from` -> nervous, awkwardness / shame
>= `awkward_from` -> flustered, tiredness, else sad-ish or neutral; above
baseline flustered if awkward else happy; the middle band neutral.
`pick(bucket)`: not shown inside `repeat_days`; a bucket with nothing left
falls back to neutral.

**The one she puts down herself.** She can end a reply with `[sticker:
FEELING]`, naming a feeling and never a file (the speech guide,
`prompts/style.md`, lists the eight names she may use). The persona takes
the tag out of the text into kv `pending_sticker`, and
`App.send_pending_sticker` sends it after the words through
`Reactions.chosen` -- the same publishing path as the automatic one, so
the header picture and her chat agree. Putting a sticker down adds one to
that image's weight for that feeling (kv `sticker_weight`), and
`pick(bucket, learned=True)` draws by those weights, so the frame she
reaches for when she is tired slowly becomes her tired face instead of a
fresh random one. The automatic mood-band face is unweighted.

**Where.** The image is copied to `data/talkapp/reactions/<id>.jpg`; kv
`reaction_last` / `reactions_log` (400) / `reaction_band`; the adapter's
state push carries `reaction_provider()` and the hub broadcasts
`reaction`; the app swaps the header avatar (`/reaction/<file>`) and
writes the bucket beside the presence line. With `reactions.sticker` the
same image lands in his chat as a `sticker` row through `send_sticker`
-- hub log only, never a `messages` row, never her context -- and it carries
`auto`, so the app draws it dimmed and captioned *her face changed &middot;
<face> <bucket>* -- the bucket named and marked (`FACE` / `faceLabel` in the
app) so he can see WHICH group of faces it came out of, and the same label sits
beside `online` under her name, because the sticker in the chat and her current
mood are the same thing and used to read as two unrelated words. Neutral is
shown too: it is her mood, and hiding it made the line look like nothing was
running. Rather than
letting it read as her saying something.

**Only while he is there** (`reactions.active_minutes`, 20): her mood wanders
all day and the face followed it into an empty room -- five changes pushed at
him in one night while he slept. Nothing
is recorded while he is away, so the first tick after he comes back moves her
face once, to now.
`backfill(hours)` walks `state_log` and places past crossings at their
own time (seeding one face at the window start when nothing has been
shown), and makes the last one current. `clear()` returns the plain
avatar.

## 4. Config

Tool: `data/reactions/<name>/config.json` (the DEFAULT_CONFIG keys above,
`buckets`, `layout`). App: `reactions.*` -- `enabled`, `character`,
`sticker`, `active_minutes`, `repeat_days`, `min_gap_minutes`, `surprise_from`,
`anger_from`, `sadness_from`, `anxiety_from`, `awkward_from`,
`tired_below`, `fatigue_from`.

## 5. Invariants and edge cases

- One `run` / `dense` per character at a time; two once shared the
  frames dir and stamped twelve episodes done with nothing in them.
- His placement is authoritative: `label` stands through `sort`; a
  deletion is a deletion (`prune`), a move is a label, never a
  re-bucketing.
- `merge` never adds a sibling for a row that was restored and not
  replaced (the row is that crop).
- The persona never learns which picture is up, by design: no image, no
  id and no bucket from the automatic face reaches any prompt. What her
  speech guide does tell her is that she has stickers of her own face and
  which eight feelings she can ask for by name, because putting one down
  is something she does.
- A gauge pinned in one band for a day would show one face under the
  band rule alone; the face-change rule is what keeps it moving (mood sat
  at the floor for 36 h on 08-25/26).
- Bucket names the reader asks for: happy, flustered, angry, sad,
  surprised, nervous, tired, neutral (smug if the character has one).

## 6. Ops and tests

`/reaction [now|BUCKET|off|backfill [H]]`; `tools/reaction_test.py` (18
checks). The tool's own checks are its sheets: `review_*.jpg`,
`verify_dense.jpg`, `pairs/`.
