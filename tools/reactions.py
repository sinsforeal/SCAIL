"""Reaction images of one anime character, from her episodes, sorted by
expression, curated by hand, read by SCAIL (sim/reactions.py) as her face
in the app. Plug in a folder of videos and ~20 face crops; everything else
is automatic, and one config per character under data/reactions/<name>/.

THE RECIPE, for any character (GPU; ffmpeg on PATH; HF_TOKEN optional):

    python tools/reactions.py init   NAME --refs DIR         # ~20 face crops of her, any size, faces only
    python tools/reactions.py run    NAME --videos DIR       # every video in DIR; resumable; one run at a time (run.lock)
    python tools/reactions.py dense  NAME --videos DIR       # second pass: +/-1.5 s at 6 fps around every kept frame,
                                                             #   the same moment only, a sharper frame replaces in place
    python tools/reactions.py merge  NAME                    # the replaced first-pass crops come back as siblings
    python tools/reactions.py subs   NAME --videos DIR       # the subtitle line at each image's second (no model)
    python tools/reactions.py review NAME                    # a contact sheet per bucket, for a first look
    -- open data/reactions/NAME/merged/<bucket>/ and DELETE what you do not want, MOVE what is in the wrong bucket --
    python tools/reactions.py prune  NAME                    # the table follows the folder: moves become labels, deletions delete
    python tools/reactions.py stats  NAME                    # counts per bucket, per video
    python tools/reactions.py spans  NAME                    # where she is on screen, per video (the appearance record)
    python tools/reactions.py learn  NAME                    # optional: a classifier from the labels; only worth it past a few
                                                             #   hundred corrections (measured 08-26: at 46 it does not beat the rules)
    python tools/reactions.py verify NAME                    # the dense pass judged: before | after sheet and the numbers
    python tools/reactions.py pairs  NAME                    # the same as files, pairs/<id>_1_first.jpg + _2_dense_...jpg
    python tools/reactions.py sort   NAME [--rules]          # re-bucket after editing `buckets`; his labels always stand
    python tools/reactions.py dedupe NAME                    # near-duplicates after the fact (sibling pairs are kept)
    then in config.json: "reactions": {"character": "NAME", ...}  and restart the bot (SCAIL reads reactions.db directly)

Every step is idempotent and cached; `run --redo` and `dense --redo` start
a video or the second pass over. Buckets are the folder names (happy,
flustered, angry, sad, surprised, nervous, smug, tired, neutral) and the
`buckets` block of the character's config; SCAIL asks for those names.

Stages of `run`, all cached under data/reactions/<name>/:
  1. frames    ffmpeg, `fps` frames a second (1 by default) plus the shot
               changes (scene filter), scaled to 1280 wide, with timestamps.
  2. faces     deepghs anime face detector (YOLOv8, onnx, GPU), min size.
  3. identity  CCIP (deepghs/ccip_onnx, anime character re-identification):
               each face's 768-d feature against the reference crops; a
               face is hers when its cosine distance to the nearest three
               references averages under `id_threshold` (the model's
               published threshold is 0.178). CLIP is the fallback only
               if CCIP cannot load. The tagger does not know her name
               (checked: no koga_tomoe in wd-vit-tagger-v3), so identity is
               the references and nothing else. Every face that passes is
               a row of `appearances` (video, t, box) before any other gate.
  4. expression wd-vit-tagger-v3 on the framed crop: expression tags ->
               a bucket by `buckets` in the config, scored on how far a
               tag is above HER OWN baseline face (a design with permanent
               blush shading would otherwise read flustered all day).
  5. framing   a square around the face with room for chin and shoulders
               (side = frame_scale x face size, centred a little below the
               face centre), clamped to the frame, 512 px.
  6. dedup     perceptual hash: dropped if within `dup_hamming` of a kept
               image in the same video inside `dup_window_s`, CCIP feature
               distance under `dup_feat_dist` in the same window, or phash
               within `dup_hamming_global` (3/64, ~95%) of anything kept.
  7. quality   face at least `min_face` px, Laplacian sharpness over
               `min_sharp`, face not clipped by the frame edge.
  8. store     reactions.db (sqlite) and merged/<bucket>/<id>.jpg; a
               `videos` table makes a run resumable.
"""
import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "data", "reactions")

DEFAULT_CONFIG = {
    "fps": 1.0,
    "scene_threshold": 0.3,
    "dense_fps": 6.0,
    "dense_window_s": 1.5,
    "dense_gain": 0.10,
    "layout": "merged",
    "dense_same_moment": 0.10,
    "dense_mouth_open": 0.5,
    "dense_mouth_closed": 0.3,
    "frame_width": 1280,
    "min_face": 72,
    "det_conf": 0.35,
    "id_threshold": 0.20,
    "id_topk": 3,
    "frame_scale": 2.4,
    "frame_down": 0.12,
    "out_size": 512,
    "dup_hamming": 10,
    "dup_window_s": 20,
    "dup_hamming_global": 3,
    "dup_feat_dist": 0.06,
    "baseline_quantile": 0.5,
    "min_sharp": 25.0,
    "tag_threshold": 0.10,
    "bucket_min": 0.35,
    "video_exts": [".mkv", ".mp4", ".webm", ".avi", ".m4v"],
    "buckets": {
        "happy": ["smile", "grin", "laughing", "light_smile", "^_^", "happy", "open_mouth+smile"],
        "flustered": ["blush", "embarrassed", "nose_blush", "full-face_blush", "light_blush", "ear_blush", "wavy_mouth", "flustered"],
        "angry": ["angry", "annoyed", "pout", "furrowed_brow", "clenched_teeth", "frown", "jitome", "v-shaped_eyebrows", "anger_vein"],
        "sad": ["sad", "crying", "tears", "crying_with_eyes_open", "light_frown", "tearing_up", "streaming_tears"],
        "surprised": ["surprised", "wide-eyed", "o_o", ":o", "0_0"],
        "nervous": ["nervous", "sweatdrop", "sweat", "nervous_sweating", "flying_sweatdrops", "scared", "worried"],
        "smug": ["smug", "evil_smile", "seductive_smile", "smirk", ":3"],
        "tired": ["sleepy", "closed_eyes", "half-closed_eyes", "expressionless", "tired", "yawning"],
    },
    "bucket_priority": ["sad", "angry", "flustered", "surprised", "nervous", "smug", "happy", "tired", "neutral"],
}


# ---------------------------------------------------------------- helpers

def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def chardir(name):
    return os.path.join(BASE, name)


def load_config(name):
    p = os.path.join(chardir(name), "config.json")
    if not os.path.exists(p):
        sys.exit(f"no character '{name}': run init first ({p})")
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(json.load(open(p, encoding="utf-8")))
    return cfg


def db(name):
    conn = sqlite3.connect(os.path.join(chardir(name), "reactions.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS reactions (
        id INTEGER PRIMARY KEY, video TEXT, t REAL, frame TEXT, path TEXT, bucket TEXT, bucket_score REAL,
        tags TEXT, id_dist REAL, face_w INTEGER, sharp REAL, phash TEXT, rating INTEGER, created REAL);
    CREATE TABLE IF NOT EXISTS videos (video TEXT PRIMARY KEY, frames INTEGER, faces INTEGER, hers INTEGER, kept INTEGER, done REAL);
    CREATE TABLE IF NOT EXISTS appearances (
        id INTEGER PRIMARY KEY, video TEXT, t REAL, frame TEXT, x INTEGER, y INTEGER, w INTEGER, h INTEGER,
        id_dist REAL, reaction_id INTEGER);
    CREATE INDEX IF NOT EXISTS appearances_video_t ON appearances(video, t);
    """)
    return conn


# ---------------------------------------------------------------- models

def _cuda_dlls():
    """onnxruntime-gpu looks for cublas / cudnn / cufft DLLs on the DLL path;
    torch's nvidia wheels carry them under site-packages/nvidia/*/bin. Put
    those on the path before onnxruntime loads, or it falls back to the CPU
    without saying so beyond a warning."""
    import site
    for sp in set(site.getsitepackages() + [site.getusersitepackages()]):
        # torch's Windows wheel carries the CUDA runtime in torch/lib
        tl = os.path.join(sp, "torch", "lib")
        if os.path.isdir(tl):
            try:
                os.add_dll_directory(tl)
            except Exception:
                pass
            os.environ["PATH"] = tl + os.pathsep + os.environ.get("PATH", "")
        nv = os.path.join(sp, "nvidia")
        if not os.path.isdir(nv):
            continue
        for d in os.listdir(nv):
            b = os.path.join(nv, d, "bin")
            if os.path.isdir(b):
                try:
                    os.add_dll_directory(b)
                except Exception:
                    pass
                os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")

class Models:
    """Detector, identity and tagger, loaded once, GPU when onnxruntime has it."""

    def __init__(self, cfg):
        _cuda_dlls()
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        prov = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
        self.det = ort.InferenceSession(hf_hub_download("deepghs/anime_face_detection", "face_detect_v1.4_s/model.onnx"), providers=prov)
        self.tag = ort.InferenceSession(hf_hub_download("SmilingWolf/wd-vit-tagger-v3", "model.onnx"), providers=prov)
        rows = list(csv.DictReader(open(hf_hub_download("SmilingWolf/wd-vit-tagger-v3", "selected_tags.csv"), encoding="utf-8")))
        self.tag_names = [r["name"] for r in rows]
        self.tag_general = [i for i, r in enumerate(rows) if r["category"] == "0"]
        self.mode = "ccip"
        try:
            self.ccip = ort.InferenceSession(hf_hub_download("deepghs/ccip_onnx", "ccip-caformer-24-randaug-pruned/model_feat.onnx"), providers=prov)
        except Exception as e:
            log(f"CCIP not available ({e}); falling back to CLIP")
            self.mode = "clip"
            import torch
            from transformers import CLIPModel, CLIPProcessor
            self.torch = torch
            self.clip = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
            self.clip_p = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            if torch.cuda.is_available():
                self.clip = self.clip.cuda()
        log(f"models: providers {prov}, identity by {self.mode}")

    # --- faces
    def faces(self, img_bgr, conf=0.35):
        """[(x, y, w, h, score)] in image pixels."""
        import cv2
        h0, w0 = img_bgr.shape[:2]
        size = 640
        r = min(size / w0, size / h0)
        nw, nh = int(w0 * r), int(h0 * r)
        canvas = np.full((size, size, 3), 114, dtype=np.uint8)
        canvas[:nh, :nw] = cv2.resize(img_bgr, (nw, nh))
        x = canvas[:, :, ::-1].astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[None]
        out = self.det.run(None, {self.det.get_inputs()[0].name: x})[0]
        pred = out[0].T if out.shape[1] < out.shape[2] else out[0]   # (8400, 5)
        boxes, scores = [], []
        for cx, cy, bw, bh, sc in pred:
            if sc < conf:
                continue
            boxes.append([float(cx - bw / 2) / r, float(cy - bh / 2) / r, float(bw) / r, float(bh) / r])
            scores.append(float(sc))
        if not boxes:
            return []
        keep = cv2.dnn.NMSBoxes(boxes, scores, conf, 0.45)
        keep = [int(k) for k in np.array(keep).reshape(-1)]
        out = []
        for k in keep:
            x, y, w, h = boxes[k]
            x, y = max(0, x), max(0, y)
            w, h = min(w, w0 - x), min(h, h0 - y)
            out.append((int(x), int(y), int(w), int(h), scores[k]))
        return out

    # --- identity
    def feat(self, img_bgr):
        import cv2
        if self.mode == "ccip":
            h, w = img_bgr.shape[:2]
            s = max(h, w)
            canvas = np.full((s, s, 3), 255, dtype=np.uint8)
            canvas[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = img_bgr
            x = cv2.resize(canvas, (384, 384))[:, :, ::-1].astype(np.float32) / 255.0
            x = (x - 0.5) / 0.5
            x = np.transpose(x, (2, 0, 1))[None]
            f = self.ccip.run(None, {self.ccip.get_inputs()[0].name: x})[0][0]
        else:
            from PIL import Image
            im = Image.fromarray(img_bgr[:, :, ::-1])
            inp = self.clip_p(images=im, return_tensors="pt")
            if self.torch.cuda.is_available():
                inp = {k: v.cuda() for k, v in inp.items()}
            with self.torch.no_grad():
                out = self.clip.get_image_features(**inp)
                out = getattr(out, "image_embeds", None) if not hasattr(out, "float") else out   # transformers 5 returns an output object
                if out is None:
                    out = self.clip.get_image_features(**inp).pooler_output
                f = out[0].float().cpu().numpy()
        return f / (np.linalg.norm(f) + 1e-9)

    # --- expression
    def tags(self, img_bgr, threshold=0.3):
        import cv2
        h, w = img_bgr.shape[:2]
        s = max(h, w)
        canvas = np.full((s, s, 3), 255, dtype=np.uint8)
        canvas[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = img_bgr
        x = cv2.resize(canvas, (448, 448), interpolation=cv2.INTER_AREA).astype(np.float32)   # BGR, 0-255, as the tagger wants
        probs = self.tag.run(None, {self.tag.get_inputs()[0].name: x[None]})[0][0]
        return {self.tag_names[i]: float(probs[i]) for i in self.tag_general if probs[i] >= threshold}


# the tagger's expression vocabulary: what a face does, not what it wears
EXPR_TAGS = ["smile", "open_mouth", "closed_mouth", "closed_eyes", "blush", "tears", "crying", "sweatdrop", "sweat",
             "frown", "angry", "annoyed", "pout", "clenched_teeth", "wavy_mouth", "embarrassed", "nervous", "surprised",
             "wide-eyed", "half-closed_eyes", "jitome", "^_^", ":d", ":o", ":<", ":t", ":3", "parted_lips", "grin",
             "laughing", "sad", "nose_blush", "flying_sweatdrops", "furrowed_brow", "raised_eyebrows", "v-shaped_eyebrows",
             "one_eye_closed", "tongue", "tongue_out", "shaded_face", "gloom_(expression)", "expressionless", "serious",
             "light_smile", "happy", "excited", "scared", "worried", "confused", "thinking", "sleepy", "teeth", "squinting",
             "empty_eyes", "constricted_pupils", "tearing_up", "screaming", "shouting", "looking_away", "looking_down"]


def expr_vector(models, img_bgr):
    """Raw probability of every EXPR_TAGS entry the tagger knows, in order."""
    import cv2
    h, w = img_bgr.shape[:2]
    sz = max(h, w)
    canvas = np.full((sz, sz, 3), 255, dtype=np.uint8)
    canvas[(sz - h) // 2:(sz - h) // 2 + h, (sz - w) // 2:(sz - w) // 2 + w] = img_bgr
    x = cv2.resize(canvas, (448, 448), interpolation=cv2.INTER_AREA).astype(np.float32)
    probs = models.tag.run(None, {models.tag.get_inputs()[0].name: x[None]})[0][0]
    idx = {n: i for i, n in enumerate(models.tag_names)}
    return [float(probs[idx[t]]) if t in idx else 0.0 for t in EXPR_TAGS]


# ---------------------------------------------------------------- stages

def extract_frames(video, out_dir, fps, width, scene_thr):
    """1 fps plus shot changes, as jpgs named by their timestamp in ms."""
    os.makedirs(out_dir, exist_ok=True)
    if os.listdir(out_dir):
        return
    vf = f"select='gte(t-prev_selected_t,{1.0 / fps:.3f})+gt(scene,{scene_thr})',scale={width}:-2,showinfo"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-i", video, "-vf", vf, "-vsync", "vfr", "-q:v", "3",
           os.path.join(out_dir, "f%06d.jpg")]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    # showinfo prints pts_time per selected frame; map index -> seconds
    times = []
    for line in p.stderr.splitlines():
        if "showinfo" in line and "pts_time:" in line:
            try:
                times.append(float(line.split("pts_time:")[1].split()[0]))
            except ValueError:
                pass
    json.dump(times, open(os.path.join(out_dir, "times.json"), "w"))


def frame_times(out_dir):
    p = os.path.join(out_dir, "times.json")
    return json.load(open(p)) if os.path.exists(p) else []


def sharpness(gray):
    import cv2
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def framed(img, box, scale, down, out_size):
    """A square around the face with chin and shoulders, clamped, resized."""
    import cv2
    H, W = img.shape[:2]
    x, y, w, h = box
    side = int(max(w, h) * scale)
    side = min(side, W, H)
    cx = x + w / 2
    cy = y + h / 2 + h * down
    x0 = int(max(0, min(W - side, cx - side / 2)))
    y0 = int(max(0, min(H - side, cy - side / 2)))
    crop = img[y0:y0 + side, x0:x0 + side]
    return cv2.resize(crop, (out_size, out_size), interpolation=cv2.INTER_AREA), (x0, y0, side)


def bucket_of(tags, cfg, baseline=None):
    """Buckets from how far a tag is above HER usual face: a character drawn
    with permanent blush shading has `blush` on every frame, so absolute
    probabilities would call her flustered all day. `baseline` is the
    per-tag median over everything kept of her."""
    baseline = baseline or {}
    best, best_s = "neutral", 0.0
    scores = {}

    def p(n):
        return max(0.0, tags.get(n, 0.0) - baseline.get(n, 0.0))
    for b, names in cfg["buckets"].items():
        s = 0.0
        for n in names:
            if "+" in n:
                s = max(s, min(p(x) for x in n.split("+")))
            else:
                s = max(s, p(n))
        scores[b] = s
    for b in cfg["bucket_priority"]:
        if b == "neutral":
            continue
        if scores.get(b, 0.0) >= cfg["bucket_min"] and scores[b] > best_s * 0.9:
            if scores[b] > best_s:
                best, best_s = b, scores[b]
    return best, round(best_s, 3), scores


def ref_features(name, cfg, models):
    """Embed the reference crops (faces detected inside them when found)."""
    import cv2
    d = chardir(name)
    cache = os.path.join(d, f"refs_{models.mode}.npy")
    if os.path.exists(cache):
        return np.load(cache)
    feats = []
    for fn in sorted(os.listdir(os.path.join(d, "refs"))):
        p = os.path.join(d, "refs", fn)
        img = cv2.imread(p)
        if img is None:
            continue
        fs = models.faces(img, cfg["det_conf"])
        if fs:
            x, y, w, h, _ = max(fs, key=lambda f: f[2] * f[3])
            img = img[y:y + h, x:x + w]
        feats.append(models.feat(img))
    if not feats:
        sys.exit("no usable reference images")
    arr = np.stack(feats)
    np.save(cache, arr)
    return arr


def id_distance(f, refs, topk):
    sims = refs @ f
    top = np.sort(sims)[-topk:]
    return float(1.0 - top.mean())


# ---------------------------------------------------------------- commands

def cmd_init(a):
    d = chardir(a.name)
    os.makedirs(os.path.join(d, "refs"), exist_ok=True)
    os.makedirs(os.path.join(d, "by_bucket"), exist_ok=True)
    n = 0
    if a.refs:
        for fn in os.listdir(a.refs):
            if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                shutil.copy(os.path.join(a.refs, fn), os.path.join(d, "refs", fn))
                n += 1
    p = os.path.join(d, "config.json")
    if not os.path.exists(p):
        json.dump({"name": a.name}, open(p, "w", encoding="utf-8"), indent=2)
    for f in os.listdir(d):
        if f.startswith("refs_") and f.endswith(".npy"):
            os.remove(os.path.join(d, f))
    log(f"{a.name}: {n} reference image(s) copied to {os.path.join(d, 'refs')}; config at {p}")


def _pid_alive(pid):
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out


def _take_lock(d, name):
    lock = os.path.join(d, "run.lock")
    try:
        other = int(open(lock).read().strip() or 0)
    except (OSError, ValueError):
        other = 0
    if other and other != os.getpid() and _pid_alive(other):
        log(f"another run (pid {other}) is on {name}; refusing")
        return False
    open(lock, "w").write(str(os.getpid()))
    return True


def extract_window(video, out_dir, start, length, fps, width):
    """Every frame at `fps` inside [start, start+length): the dense look
    around a hit. Timestamps are start + k / fps."""
    os.makedirs(out_dir, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, start):.3f}", "-t", f"{length:.3f}",
           "-i", video, "-vf", f"fps={fps},scale={width}:-2", "-q:v", "3", os.path.join(out_dir, "d%04d.jpg")]
    subprocess.run(cmd, capture_output=True)
    return sorted(f for f in os.listdir(out_dir) if f.endswith(".jpg"))


def cmd_dense(a):
    """The second pass: the first pass looked once a second, so a hit is a
    face somewhere near its best moment, not at it. For every kept image,
    look at every frame `dense_window_s` either side at `dense_fps`, and if
    a sharper frame of HER is there (same identity test), the kept image is
    replaced in place: same row id, new time, new crop, new tags. No new
    rows, so the dedup of the first pass still holds; `sort` runs after so
    a changed face can change bucket."""
    import cv2
    import imagehash
    from PIL import Image
    cfg = load_config(a.name)
    d = chardir(a.name)
    if not _take_lock(d, a.name):
        return
    conn = db(a.name)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)").fetchall()}
    if "dense" not in cols:
        conn.execute("ALTER TABLE reactions ADD COLUMN dense INTEGER DEFAULT 0")
    for col in ("sharp_before REAL", "t_before REAL"):
        if col.split()[0] not in cols:
            conn.execute(f"ALTER TABLE reactions ADD COLUMN {col}")
    conn.commit()
    models = Models(cfg)
    refs = ref_features(a.name, cfg, models)
    fps = a.fps or cfg.get("dense_fps", DEFAULT_CONFIG["dense_fps"])
    win = a.window or cfg.get("dense_window_s", DEFAULT_CONFIG["dense_window_s"])
    gain = cfg.get("dense_gain", DEFAULT_CONFIG["dense_gain"])
    if a.redo:
        # put the first pass's crops back where they were kept, so the pass
        # runs again from the same start and `verify` compares fairly
        n = 0
        for r in conn.execute("SELECT id, path, sharp_before, t_before FROM reactions WHERE sharp_before IS NOT NULL").fetchall():
            src = os.path.join(d, "dense_before", f"{r['id']:06d}.jpg")
            if os.path.exists(src) and r["path"]:
                shutil.copy2(src, os.path.join(ROOT, r["path"]))
                conn.execute("UPDATE reactions SET sharp=?, t=?, sharp_before=NULL, t_before=NULL, dense=0 WHERE id=?", (r["sharp_before"], r["t_before"], r["id"]))
                n += 1
        conn.commit()
        log(f"dense --redo: {n} first-pass crop(s) restored")
    same = cfg.get("dense_same_moment", DEFAULT_CONFIG["dense_same_moment"])
    m_open = cfg.get("dense_mouth_open", DEFAULT_CONFIG["dense_mouth_open"])
    m_closed = cfg.get("dense_mouth_closed", DEFAULT_CONFIG["dense_mouth_closed"])
    q = "SELECT * FROM reactions WHERE dense=0" + (" AND video=?" if a.video else "")
    rows = conn.execute(q, ((a.video,) if a.video else ())).fetchall()
    if a.limit:
        rows = rows[: a.limit]
    log(f"dense: {len(rows)} image(s) to look around, +/-{win}s at {fps} fps")
    improved = 0
    by_video = {}
    for r in rows:
        by_video.setdefault(r["video"], []).append(r)
    for v, vrows in by_video.items():
        vpath = os.path.join(a.videos, v)
        if not os.path.exists(vpath):
            log(f"   {v}: not in --videos, skipped")
            continue
        t0 = time.time()
        n_imp = n_skip = 0
        for r in vrows:
            wdir = os.path.join(d, "dense", str(r["id"]))
            # the moment to stay in: the first pass's face, its CCIP feature
            # and whether its mouth was shut. A shot cut inside the window
            # must not swap the moment for a sharper face from the next one.
            ref_vec, ref_closed = None, False
            cur = cv2.imread(os.path.join(ROOT, r["path"])) if r["path"] else None
            if cur is not None:
                fb = models.faces(cur, cfg["det_conf"])
                if fb:
                    x0, y0, w0, h0, _ = max(fb, key=lambda b: b[2] * b[3])
                    ref_vec = models.feat(cur[y0:y0 + h0, x0:x0 + w0])
                try:
                    ref_closed = json.loads(r["tags"] or "{}").get("open_mouth", 0.0) < m_closed
                except ValueError:
                    ref_closed = False
            start = max(0.0, float(r["t"]) - win)
            frames = extract_window(vpath, wdir, start, 2 * win, fps, cfg["frame_width"])
            best = None   # (sharp, t, crop, w, dist, fvec)
            n_other_moment = 0
            for k, fn in enumerate(frames):
                t = start + k / fps
                img = cv2.imread(os.path.join(wdir, fn))
                if img is None:
                    continue
                H, W = img.shape[:2]
                for (x, y, w, h, sc) in models.faces(img, cfg["det_conf"]):
                    if min(w, h) < cfg["min_face"] or x <= 1 or y <= 1 or x + w >= W - 1 or y + h >= H - 1:
                        continue
                    face = img[y:y + h, x:x + w]
                    fvec = models.feat(face)
                    dist = id_distance(fvec, refs, cfg["id_topk"])
                    if dist > cfg["id_threshold"]:
                        continue
                    if ref_vec is not None and float(1.0 - ref_vec @ fvec) > same:
                        n_other_moment += 1
                        continue   # her, but not this moment
                    sharp = sharpness(cv2.cvtColor(face, cv2.COLOR_BGR2GRAY))
                    if best is None or sharp > best[0]:
                        crop, _ = framed(img, (x, y, w, h), cfg["frame_scale"], cfg["frame_down"], cfg["out_size"])
                        if ref_closed and models.tags(crop, cfg["tag_threshold"]).get("open_mouth", 0.0) >= m_open:
                            continue   # a mouth open mid-word is not a better reaction than the shut one
                        best = (sharp, t, crop, w, dist)
            shutil.rmtree(wdir, ignore_errors=True)
            n_skip += n_other_moment
            if best is None:
                conn.execute("UPDATE reactions SET dense=1 WHERE id=?", (r["id"],))
                conn.commit()
                continue
            sharp, t, crop, w, dist = best
            if sharp > float(r["sharp"] or 0) * (1.0 + gain):
                tags = models.tags(crop, cfg["tag_threshold"])
                ph = imagehash.phash(Image.fromarray(crop[:, :, ::-1]))
                out = os.path.join(ROOT, r["path"]) if r["path"] else os.path.join(d, "by_bucket", r["bucket"], f"{r['id']:06d}.jpg")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                # the first pass's crop is kept beside, so the pass can be judged (`verify`)
                before_dir = os.path.join(d, "dense_before")
                os.makedirs(before_dir, exist_ok=True)
                if os.path.exists(out):
                    shutil.copy2(out, os.path.join(before_dir, f"{r['id']:06d}.jpg"))
                cv2.imwrite(out, crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
                conn.execute("UPDATE reactions SET t=?, tags=?, id_dist=?, face_w=?, sharp=?, phash=?, dense=1, sharp_before=?, t_before=? WHERE id=?",
                             (t, json.dumps({k: round(p, 3) for k, p in sorted(tags.items(), key=lambda kv: -kv[1])[:24]}),
                              round(dist, 4), w, round(sharp, 1), str(ph), r["sharp"], r["t"], r["id"]))
                n_imp += 1
            else:
                conn.execute("UPDATE reactions SET dense=1 WHERE id=?", (r["id"],))
            conn.commit()
        improved += n_imp
        log(f"== {v}: {len(vrows)} looked at, {n_imp} replaced by a sharper frame, {n_skip} face(s) of her refused as another moment, {time.time() - t0:.0f}s")
    log(f"dense: {improved}/{len(rows)} replaced")
    cmd_dedupe(a)
    cmd_sort(a)
    cmd_stats(a)


def cmd_verify(a):
    """Was the second pass worth it: every replaced image before and after,
    side by side, with the sharpness and the time shift; and the numbers."""
    import cv2
    d = chardir(a.name)
    conn = db(a.name)
    rows = conn.execute("SELECT id, path, sharp, sharp_before, t, t_before, bucket FROM reactions WHERE sharp_before IS NOT NULL ORDER BY (sharp / sharp_before) DESC").fetchall()
    n_all = conn.execute("SELECT count(*) FROM reactions WHERE dense=1").fetchone()[0]
    if not rows:
        print("nothing replaced yet")
        return
    gains = [r["sharp"] / max(1e-6, r["sharp_before"]) for r in rows]
    shifts = [abs(r["t"] - r["t_before"]) for r in rows]
    print(f"{a.name}: {n_all} looked at, {len(rows)} replaced ({100 * len(rows) / max(1, n_all):.0f}%)")
    print(f"  sharpness gain: median x{np.median(gains):.2f}, mean x{np.mean(gains):.2f}, top x{max(gains):.1f}; "
          f"{sum(1 for g in gains if g >= 1.5)} at 1.5x or more, {sum(1 for g in gains if g >= 2)} at 2x or more")
    print(f"  time shift: median {np.median(shifts):.2f}s, max {max(shifts):.2f}s")
    tile = 256
    per_row = 4   # pairs per row
    rows = rows[: a.limit] if a.limit else rows
    n = len(rows)
    H = (n + per_row - 1) // per_row
    sheet = np.zeros((H * tile, per_row * 2 * tile + (per_row - 1) * 8, 3), np.uint8)
    for i, r in enumerate(rows):
        y, x = (i // per_row) * tile, (i % per_row) * (2 * tile + 8)
        for j, pth in enumerate((os.path.join(d, "dense_before", f"{r['id']:06d}.jpg"), os.path.join(ROOT, r["path"]))):
            img = cv2.imread(pth)
            if img is None:
                continue
            sheet[y:y + tile, x + j * tile:x + (j + 1) * tile] = cv2.resize(img, (tile, tile))
        label = f"{r['id']} x{r['sharp'] / max(1e-6, r['sharp_before']):.2f} {r['sharp_before']:.0f}>{r['sharp']:.0f} {r['t'] - r['t_before']:+.2f}s"
        cv2.putText(sheet, label, (x + 4, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
        cv2.putText(sheet, label, (x + 4, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    out = os.path.join(d, "verify_dense.jpg")
    cv2.imwrite(out, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"  sheet: {out} (before | after, {n} pairs)")


def cmd_merge(a):
    """His review layout: `merged/<bucket>/<id>.jpg`, with
    the first-pass crop of every dense replacement as its own row beside
    the replacement (`sibling_of`). He deletes what he does not like;
    `prune` makes the table follow."""
    import cv2
    import imagehash
    from PIL import Image
    cfg = load_config(a.name)
    d = chardir(a.name)
    conn = db(a.name)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)").fetchall()}
    if "sibling_of" not in cols:
        conn.execute("ALTER TABLE reactions ADD COLUMN sibling_of INTEGER")
        conn.commit()
    bdir = os.path.join(d, "dense_before")
    models = None
    added = 0
    for fn in sorted(os.listdir(bdir)) if os.path.isdir(bdir) else []:
        try:
            oid = int(os.path.splitext(fn)[0])
        except ValueError:
            continue
        if conn.execute("SELECT 1 FROM reactions WHERE sibling_of=?", (oid,)).fetchone():
            continue
        orig = conn.execute("SELECT * FROM reactions WHERE id=?", (oid,)).fetchone()
        if orig and orig["sharp_before"] is None:
            continue   # restored by --redo and not replaced since: the row IS this crop
        src = os.path.join(bdir, fn)
        crop = cv2.imread(src)
        if crop is None:
            continue
        if models is None:
            models = Models(cfg)
        tags = models.tags(crop, cfg["tag_threshold"])
        ph = imagehash.phash(Image.fromarray(crop[:, :, ::-1]))
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        rid = conn.execute("INSERT INTO reactions(video,t,frame,path,bucket,bucket_score,tags,id_dist,face_w,sharp,phash,created,dense,sibling_of) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
                           (orig["video"] if orig else "", (orig["t_before"] if orig and orig["t_before"] is not None else (orig["t"] if orig else 0.0)),
                            "", "", "unsorted", 0.0, json.dumps({k: round(p, 3) for k, p in sorted(tags.items(), key=lambda kv: -kv[1])[:24]}),
                            orig["id_dist"] if orig else None, orig["face_w"] if orig else None,
                            (orig["sharp_before"] if orig and orig["sharp_before"] is not None else round(sharpness(gray), 1)),
                            str(ph), time.time(), oid)).lastrowid
        out = os.path.join(d, "merged", "unsorted", f"{rid:06d}.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(src, out)
        conn.execute("UPDATE reactions SET path=? WHERE id=?", (os.path.relpath(out, ROOT), rid))
        added += 1
    conn.commit()
    cfg["layout"] = "merged"
    json.dump(cfg, open(os.path.join(d, "config.json"), "w"), indent=1)
    log(f"merge: {added} first-pass crop(s) added as siblings; layout merged")
    cmd_sort(a)
    cmd_stats(a)


def cmd_pairs(a):
    """The isolated test of the second pass: `pairs/<id>_1_first.jpg` and
    `<id>_2_dense.jpg` for every replacement that has both. Copies, for
    looking; the files that count are in the merged folder."""
    d = chardir(a.name)
    conn = db(a.name)
    out = os.path.join(d, "pairs")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    n = 0
    for r in conn.execute("SELECT r.id, r.path, r.sharp, r.sharp_before, r.t, r.t_before, s.path AS spath FROM reactions r JOIN reactions s ON s.sibling_of=r.id WHERE r.sharp_before IS NOT NULL"):
        if not (r["path"] and r["spath"]):
            continue
        a_, b_ = os.path.join(ROOT, r["spath"]), os.path.join(ROOT, r["path"])
        if os.path.exists(a_) and os.path.exists(b_):
            shutil.copy2(a_, os.path.join(out, f"{r['id']:06d}_1_first.jpg"))
            shutil.copy2(b_, os.path.join(out, f"{r['id']:06d}_2_dense_x{r['sharp'] / max(1e-6, r['sharp_before']):.2f}_{r['t'] - r['t_before']:+.2f}s.jpg"))
            n += 1
    log(f"pairs: {n} pair(s) in {out}")


def cmd_prune(a):
    """The table follows the folder. A file he moved to another bucket
    folder is a label (`label` = that bucket); a file with no row is
    adopted (id from its name, tags recomputed); a row whose file is in
    no folder goes."""
    import cv2
    import imagehash
    from PIL import Image
    cfg = load_config(a.name)
    d = chardir(a.name)
    conn = db(a.name)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)").fetchall()}
    for col in ("label TEXT", "expr TEXT", "line TEXT", "sibling_of INTEGER"):
        if col.split()[0] not in cols:
            conn.execute(f"ALTER TABLE reactions ADD COLUMN {col}")
    conn.commit()
    mroot = os.path.join(d, "merged")
    found = {}
    for b in (os.listdir(mroot) if os.path.isdir(mroot) else []):
        bd = os.path.join(mroot, b)
        if not os.path.isdir(bd):
            continue
        for fn in os.listdir(bd):
            try:
                found[int(os.path.splitext(fn)[0])] = (b, os.path.relpath(os.path.join(bd, fn), ROOT))
            except ValueError:
                pass
    rows = {r["id"]: r for r in conn.execute("SELECT id, path, bucket FROM reactions")}
    moved = adopted = gone = 0
    models = None
    for rid, (b, rel) in found.items():
        r = rows.get(rid)
        if r is None:
            crop = cv2.imread(os.path.join(ROOT, rel))
            if crop is None:
                continue
            if models is None:
                models = Models(cfg)
            tags = models.tags(crop, cfg["tag_threshold"])
            ph = imagehash.phash(Image.fromarray(crop[:, :, ::-1]))
            conn.execute("INSERT INTO reactions(id,video,t,frame,path,bucket,bucket_score,tags,sharp,phash,created,label) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         (rid, "", 0.0, "", rel, b, 0.0, json.dumps({k: round(p, 3) for k, p in sorted(tags.items(), key=lambda kv: -kv[1])[:24]}),
                          round(sharpness(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)), 1), str(ph), time.time(), b))
            adopted += 1
        else:
            if r["path"] != rel or r["bucket"] != b:
                moved += 1
            conn.execute("UPDATE reactions SET path=?, bucket=?, label=? WHERE id=?", (rel, b, b, rid))
    for rid in rows:
        if rid not in found:
            conn.execute("DELETE FROM reactions WHERE id=?", (rid,))
            conn.execute("UPDATE appearances SET reaction_id=NULL WHERE reaction_id=?", (rid,))
            gone += 1
    conn.commit()
    log(f"prune: {gone} removed, {moved} moved (labelled), {adopted} adopted; {conn.execute('SELECT count(*) FROM reactions').fetchone()[0]} stay, "
        f"{conn.execute('SELECT count(*) FROM reactions WHERE label IS NOT NULL').fetchone()[0]} labelled")
    cmd_stats(a)


def _srt_lines(video, cache_dir):
    """The video's subtitle lines as (start, end, text), one extraction per
    video, cached beside the character. Japanese track first, else English."""
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, os.path.splitext(os.path.basename(video))[0][:80] + ".json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream=index:stream_tags=language,title", "-of", "csv=p=0", video],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    streams = [ln.split(",") for ln in pr.stdout.splitlines() if ln.strip()]
    pick = None
    for want in ("jpn", "eng"):
        for st in streams:
            if len(st) > 1 and st[1] == want:
                pick = st[0]
                break
        if pick:
            break
    out = []
    if pick is not None:
        srt = cache + ".srt"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-map", f"0:{pick}", srt], capture_output=True)
        if os.path.exists(srt):
            block = []
            for ln in open(srt, encoding="utf-8", errors="replace").read().split("\n") + [""]:
                if ln.strip():
                    block.append(ln.strip())
                    continue
                if len(block) >= 3 and "-->" in block[1]:
                    def sec(x):
                        h, m, s_ = x.strip().replace(",", ".").split(":")
                        return int(h) * 3600 + int(m) * 60 + float(s_)
                    try:
                        a_, b_ = block[1].split("-->")
                        text = re.sub(r"<[^>]+>|\{[^}]+\}", "", " ".join(block[2:]))
                        out.append([sec(a_), sec(b_), text])
                    except ValueError:
                        pass
                block = []
            os.remove(srt)
    json.dump(out, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def cmd_subs(a):
    """The subtitle line at every kept image's second, one extraction per
    video, no model: the words she says or hears are the cheapest emotion
    cue there is. Stored on the row (`line`), shown on the sheets."""
    d = chardir(a.name)
    conn = db(a.name)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)").fetchall()}
    if "line" not in cols:
        conn.execute("ALTER TABLE reactions ADD COLUMN line TEXT")
        conn.commit()
    n = 0
    for v, in conn.execute("SELECT DISTINCT video FROM reactions WHERE video != ''").fetchall():
        vpath = os.path.join(a.videos, v)
        if not os.path.exists(vpath):
            continue
        lines = _srt_lines(vpath, os.path.join(d, "subs"))
        for r in conn.execute("SELECT id, t FROM reactions WHERE video=?", (v,)).fetchall():
            t = float(r["t"])
            hit = [x[2] for x in lines if x[0] - 0.5 <= t <= x[1] + 0.5]
            if hit:
                conn.execute("UPDATE reactions SET line=? WHERE id=?", (" / ".join(hit)[:200], r["id"]))
                n += 1
    conn.commit()
    log(f"subs: {n} image(s) got their line")


def cmd_learn(a):
    """His folder placements are the labels; the tagger's expression
    probabilities (EXPR_TAGS) are the features; a logistic regression is
    the sorter. Reports cross-validated accuracy against the rules, and
    writes model.json for `sort` to use."""
    import cv2
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict
    cfg = load_config(a.name)
    d = chardir(a.name)
    conn = db(a.name)
    models = Models(cfg)
    rows = conn.execute("SELECT id, path, expr, label, bucket, tags FROM reactions").fetchall()
    X, y, ids = [], [], []
    for r in rows:
        vec = None
        if r["expr"]:
            vec = json.loads(r["expr"])
            if len(vec) != len(EXPR_TAGS):
                vec = None
        if vec is None:
            img = cv2.imread(os.path.join(ROOT, r["path"])) if r["path"] else None
            if img is None:
                continue
            vec = expr_vector(models, img)
            conn.execute("UPDATE reactions SET expr=? WHERE id=?", (json.dumps([round(v, 4) for v in vec]), r["id"]))
        if r["label"]:
            X.append(vec)
            y.append(r["label"])
            ids.append(r["id"])
    conn.commit()
    if len(set(y)) < 2 or len(y) < 20:
        log(f"learn: {len(y)} labelled image(s) in {len(set(y))} bucket(s); not enough")
        return
    X = np.array(X)
    yy = np.array(y)
    clf = LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced")
    counts = {lab: int((yy == lab).sum()) for lab in set(y)}
    folds = max(2, min(5, min(counts.values())))
    pred = cross_val_predict(clf, X, yy, cv=folds)
    acc = float(np.mean(pred == yy))
    clf.fit(X, yy)
    # what the rules would have said for the same images, against his labels
    baseline = json.load(open(os.path.join(d, "baseline.json"))) if os.path.exists(os.path.join(d, "baseline.json")) else {}
    rows_by_id = {r["id"]: r for r in rows}
    rule_hits = sum(1 for rid, lab in zip(ids, y) if bucket_of(json.loads(rows_by_id[rid]["tags"] or "{}"), cfg, baseline)[0] == lab)
    log(f"learn: {len(y)} labelled, {folds}-fold accuracy {acc:.2f}; the rules get {rule_hits / len(y):.2f} on the same images")
    for lab in sorted(counts):
        m = yy == lab
        log(f"   {lab:10s} n={counts[lab]:3d}  recall {float(np.mean(pred[m] == lab)):.2f}  rules {sum(1 for rid, l2 in zip(ids, y) if l2 == lab and bucket_of(json.loads(rows_by_id[rid]['tags'] or '{}'), cfg, baseline)[0] == lab) / counts[lab]:.2f}")
    json.dump({"classes": list(clf.classes_), "coef": clf.coef_.tolist(), "intercept": clf.intercept_.tolist(), "tags": EXPR_TAGS,
               "labelled": len(y), "cv_accuracy": round(acc, 3), "folds": folds},
              open(os.path.join(d, "model.json"), "w"), indent=1)
    log("   model.json written; `sort` uses it for unlabelled rows")


def cmd_dedupe(a):
    """Near-duplicates after the fact: the sharpest of a pair stays. A pair
    is two images within `dup_hamming` (phash) in the same video inside
    `dup_window_s`, or within `dup_hamming_global` anywhere."""
    import imagehash
    cfg = load_config(a.name)
    conn = db(a.name)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(reactions)").fetchall()}
    sib = ", sibling_of" if "sibling_of" in cols else ", NULL AS sibling_of"
    rows = conn.execute(f"SELECT id, video, t, path, sharp, phash{sib} FROM reactions ORDER BY sharp DESC, id").fetchall()
    kept, gone = [], []
    for r in rows:
        if not r["phash"]:
            kept.append((r, None))
            continue
        ph = imagehash.hex_to_hash(r["phash"])
        dup = False
        for k, q in kept:
            if q is None:
                continue
            if r["sibling_of"] == k["id"] or k["sibling_of"] == r["id"]:
                continue   # a pair kept on purpose, for his eye
            dist = abs(ph - q)
            if dist <= cfg["dup_hamming_global"] or (k["video"] == r["video"] and abs(float(k["t"]) - float(r["t"])) <= cfg["dup_window_s"] and dist <= cfg["dup_hamming"]):
                dup = True
                break
        (gone if dup else kept).append((r, ph))
    for r, _ in gone:
        if r["path"]:
            try:
                os.remove(os.path.join(ROOT, r["path"]))
            except OSError:
                pass
        conn.execute("DELETE FROM reactions WHERE id=?", (r["id"],))
    conn.commit()
    log(f"dedupe: {len(gone)} near-duplicate(s) removed, {len(kept)} stay")


def cmd_run(a):
    import cv2
    import imagehash
    from PIL import Image
    cfg = load_config(a.name)
    if a.fps:
        cfg["fps"] = a.fps
    d = chardir(a.name)
    # one run per character: two runs share the frames dir and the videos
    # table, and the second marks videos done with nothing in them once
    # the first has deleted the frames under it
    if not _take_lock(d, a.name):
        return
    conn = db(a.name)
    models = Models(cfg)
    refs = ref_features(a.name, cfg, models)
    # how tight the references are among themselves, so the threshold is sane for this set
    if len(refs) > 1:
        dd = 1.0 - refs @ refs.T
        np.fill_diagonal(dd, np.nan)
        log(f"{len(refs)} references; distance between them: median {np.nanmedian(dd):.3f}, max {np.nanmax(dd):.3f}; id_threshold {cfg['id_threshold']}")
    videos = sorted(f for f in os.listdir(a.videos) if os.path.splitext(f)[1].lower() in cfg["video_exts"])
    if a.redo:
        for v in videos:
            for r in conn.execute("SELECT path FROM reactions WHERE video=?", (v,)):
                try:
                    os.remove(os.path.join(ROOT, r["path"]))
                except OSError:
                    pass
            conn.execute("DELETE FROM reactions WHERE video=?", (v,))
            conn.execute("DELETE FROM appearances WHERE video=?", (v,))
            conn.execute("DELETE FROM videos WHERE video=?", (v,))
        conn.commit()
    done = {r["video"] for r in conn.execute("SELECT video FROM videos")}
    todo = [v for v in videos if v not in done]
    if a.limit:
        todo = todo[: a.limit]
    log(f"{len(videos)} video(s), {len(done)} done, {len(todo)} to do")
    global_hashes = [imagehash.hex_to_hash(r["phash"]) for r in conn.execute("SELECT phash FROM reactions") if r["phash"]]
    for v in todo:
        t0 = time.time()
        vpath = os.path.join(a.videos, v)
        fdir = os.path.join(d, "frames", os.path.splitext(v)[0][:80])
        log(f"== {v}: extracting frames at {cfg['fps']} fps + shot changes")
        extract_frames(vpath, fdir, cfg["fps"], cfg["frame_width"], cfg["scene_threshold"])
        times = frame_times(fdir)
        frames = sorted(f for f in os.listdir(fdir) if f.endswith(".jpg"))
        log(f"   {len(frames)} frames in {time.time() - t0:.0f}s")
        n_faces = n_hers = n_kept = 0
        recent = []   # (t, phash) kept in this video
        for i, fn in enumerate(frames):
            t = times[i] if i < len(times) else i / cfg["fps"]
            img = cv2.imread(os.path.join(fdir, fn))
            if img is None:
                continue
            for (x, y, w, h, sc) in models.faces(img, cfg["det_conf"]):
                n_faces += 1
                if min(w, h) < cfg["min_face"]:
                    continue
                H, W = img.shape[:2]
                if x <= 1 or y <= 1 or x + w >= W - 1 or y + h >= H - 1:
                    continue   # clipped by the frame edge
                face = img[y:y + h, x:x + w]
                fvec = models.feat(face)
                dist = id_distance(fvec, refs, cfg["id_topk"])
                if dist > cfg["id_threshold"]:
                    continue
                n_hers += 1
                # the full record of where she is, before any quality or
                # dedup gate: every sampled frame that passed the identity test
                aid = conn.execute("INSERT INTO appearances(video,t,frame,x,y,w,h,id_dist,reaction_id) VALUES(?,?,?,?,?,?,?,?,NULL)",
                                   (v, t, fn, int(x), int(y), int(w), int(h), round(dist, 4))).lastrowid
                crop, _ = framed(img, (x, y, w, h), cfg["frame_scale"], cfg["frame_down"], cfg["out_size"])
                sharp = sharpness(cv2.cvtColor(face, cv2.COLOR_BGR2GRAY))
                if sharp < cfg["min_sharp"]:
                    continue
                ph = imagehash.phash(Image.fromarray(crop[:, :, ::-1]))
                if any(abs(ph - q) <= cfg["dup_hamming"] and abs(t - tt) <= cfg["dup_window_s"] for tt, q, _ in recent):
                    continue
                if any(float(1.0 - ff @ fvec) <= cfg["dup_feat_dist"] and abs(t - tt) <= cfg["dup_window_s"] for tt, _, ff in recent):
                    continue   # the same pose seconds apart, phash notwithstanding
                if any(abs(ph - q) <= cfg["dup_hamming_global"] for q in global_hashes):
                    continue
                tags = models.tags(crop, cfg["tag_threshold"])
                bucket, bscore = "unsorted", 0.0   # sorted against her baseline once the run is done
                rid = conn.execute("INSERT INTO reactions(video,t,frame,path,bucket,bucket_score,tags,id_dist,face_w,sharp,phash,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                   (v, t, fn, "", bucket, bscore, json.dumps({k: round(p, 3) for k, p in sorted(tags.items(), key=lambda kv: -kv[1])[:24]}),
                                    round(dist, 4), w, round(sharp, 1), str(ph), time.time())).lastrowid
                bdir = os.path.join(d, "merged" if cfg.get("layout", "merged") == "merged" else "by_bucket", bucket)
                os.makedirs(bdir, exist_ok=True)
                out = os.path.join(bdir, f"{rid:06d}.jpg")
                cv2.imwrite(out, crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
                conn.execute("UPDATE reactions SET path=? WHERE id=?", (os.path.relpath(out, ROOT), rid))
                conn.execute("UPDATE appearances SET reaction_id=? WHERE id=?", (rid, aid))
                conn.commit()
                recent.append((t, ph, fvec))
                global_hashes.append(ph)
                n_kept += 1
            if i and i % 200 == 0:
                log(f"   {i}/{len(frames)} frames, faces {n_faces}, hers {n_hers}, kept {n_kept}")
        conn.execute("INSERT OR REPLACE INTO videos(video,frames,faces,hers,kept,done) VALUES(?,?,?,?,?,?)", (v, len(frames), n_faces, n_hers, n_kept, time.time()))
        conn.commit()
        log(f"== {v}: {len(frames)} frames, {n_faces} faces, {n_hers} hers, {n_kept} kept, {time.time() - t0:.0f}s")
        if not a.keep_frames:
            shutil.rmtree(fdir, ignore_errors=True)
    cmd_sort(a)
    cmd_stats(a)


def cmd_sort(a):
    """Bucket every kept image against her own baseline face, and move the
    files into by_bucket accordingly. Re-runnable after editing `buckets`."""
    cfg = load_config(a.name)
    conn = db(a.name)
    d = chardir(a.name)
    rows = conn.execute("SELECT id, path, tags FROM reactions").fetchall()
    if not rows:
        return
    allt = [json.loads(r["tags"]) for r in rows]
    names = set(n for t in allt for n in t)
    q = cfg["baseline_quantile"]
    baseline = {n: float(np.quantile([t.get(n, 0.0) for t in allt], q)) for n in names}
    json.dump({k: round(v, 3) for k, v in sorted(baseline.items(), key=lambda kv: -kv[1]) if v > 0.05},
              open(os.path.join(d, "baseline.json"), "w"), indent=1)
    moved = 0
    model = None
    mp = os.path.join(d, "model.json")
    if os.path.exists(mp) and not getattr(a, "rules", False):
        model = json.load(open(mp))
    cols = {c["name"] for c in conn.execute("PRAGMA table_info(reactions)").fetchall()}
    extra = {r["id"]: r for r in conn.execute("SELECT id, label, expr FROM reactions")} if "label" in cols else {}
    for r, tags in zip(rows, allt):
        ex = extra.get(r["id"])
        if ex is not None and ex["label"]:
            bucket, score = ex["label"], 1.0     # his placement stands
        elif model and ex is not None and ex["expr"]:
            vec = np.array(json.loads(ex["expr"]))
            z = np.array(model["coef"]) @ vec + np.array(model["intercept"])
            pz = np.exp(z - z.max())
            pz /= pz.sum()
            bucket, score = model["classes"][int(pz.argmax())], float(pz.max())
        else:
            bucket, score, _ = bucket_of(tags, cfg, baseline)
        old = os.path.join(ROOT, r["path"]) if r["path"] else ""
        if cfg.get("layout", "merged") == "merged":
            # his review folder: merged/<bucket>/<id>.jpg, first-pass and
            # dense siblings side by side under the bucket each one earned
            bdir = os.path.join(d, "merged", bucket)
            os.makedirs(bdir, exist_ok=True)
            new = os.path.join(bdir, f"{r['id']:06d}.jpg")
        else:
            bdir = os.path.join(d, "by_bucket", bucket)
            os.makedirs(bdir, exist_ok=True)
            new = os.path.join(bdir, f"{r['id']:06d}.jpg")
        if old and os.path.exists(old) and os.path.abspath(old) != os.path.abspath(new):
            shutil.move(old, new)
            moved += 1
        conn.execute("UPDATE reactions SET bucket=?, bucket_score=?, path=? WHERE id=?", (bucket, score, os.path.relpath(new, ROOT), r["id"]))
    conn.commit()
    for root in ("by_bucket", "merged"):
        for b in (os.listdir(os.path.join(d, root)) if os.path.isdir(os.path.join(d, root)) else []):
            p = os.path.join(d, root, b)
            if os.path.isdir(p) and not os.listdir(p):
                os.rmdir(p)
    top = sorted(baseline.items(), key=lambda kv: -kv[1])[:8]
    log(f"sorted {len(rows)} against her baseline ({', '.join(f'{k} {v:.2f}' for k, v in top)}); {moved} moved")


def cmd_spans(a):
    """Where she is, per video: the appearance record collapsed into spans
    (frames within `dup_window_s` of each other join)."""
    cfg = load_config(a.name)
    conn = db(a.name)
    gap = cfg["dup_window_s"]
    cur = None
    out = {}
    for r in conn.execute("SELECT video, t FROM appearances ORDER BY video, t"):
        if cur and cur[0] == r["video"] and r["t"] - cur[2] <= gap:
            cur[2] = r["t"]
            cur[3] += 1
        else:
            if cur:
                out.setdefault(cur[0], []).append(cur)
            cur = [r["video"], r["t"], r["t"], 1]
    if cur:
        out.setdefault(cur[0], []).append(cur)
    for v, spans in out.items():
        total = sum(s[2] - s[1] for s in spans)
        print(f"{v[:70]}: {len(spans)} span(s), {total:.0f}s on screen")
        for s in spans:
            print(f"   {s[1] // 60:02.0f}:{s[1] % 60:04.1f} - {s[2] // 60:02.0f}:{s[2] % 60:04.1f}  ({s[3]} frames)")


def cmd_stats(a):
    conn = db(a.name)
    rows = conn.execute("SELECT bucket, COUNT(*) n, AVG(bucket_score) s FROM reactions GROUP BY bucket ORDER BY n DESC").fetchall()
    total = sum(r["n"] for r in rows)
    print(f"{a.name}: {total} reaction image(s)")
    for r in rows:
        print(f"  {r['bucket']:10s} {r['n']:5d}  mean score {r['s'] or 0:.2f}")
    for r in conn.execute("SELECT video, frames, faces, hers, kept FROM videos ORDER BY video"):
        print(f"  {r['video'][:70]:70s} frames {r['frames']:5d} faces {r['faces']:5d} hers {r['hers']:4d} kept {r['kept']:4d}")


def cmd_review(a):
    """A contact sheet per bucket, so the sorting can be rated by eye."""
    import cv2
    conn = db(a.name)
    d = chardir(a.name)
    buckets = [a.bucket] if a.bucket else [r["bucket"] for r in conn.execute("SELECT DISTINCT bucket FROM reactions")]
    for b in buckets:
        rows = conn.execute("SELECT id, path, bucket_score, tags FROM reactions WHERE bucket=? ORDER BY bucket_score DESC LIMIT 48", (b,)).fetchall()
        if not rows:
            continue
        tiles = []
        for r in rows:
            im = cv2.imread(os.path.join(ROOT, r["path"]))
            if im is None:
                continue
            im = cv2.resize(im, (192, 192))
            top = list(json.loads(r["tags"]).items())[:3]
            cv2.putText(im, f"{r['id']} {r['bucket_score']:.2f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(im, f"{r['id']} {r['bucket_score']:.2f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(im, ",".join(k for k, _ in top)[:34], (4, 186), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
            tiles.append(im)
        cols = 8
        while len(tiles) % cols:
            tiles.append(np.zeros((192, 192, 3), dtype=np.uint8))
        sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
        out = os.path.join(d, f"review_{b}.jpg")
        cv2.imwrite(out, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"{b}: {len(rows)} -> {out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("name"); p.add_argument("--refs", default="")
    p = sub.add_parser("run"); p.add_argument("name"); p.add_argument("--videos", required=True); p.add_argument("--fps", type=float, default=0)
    p.add_argument("--limit", type=int, default=0); p.add_argument("--keep-frames", action="store_true"); p.add_argument("--redo", action="store_true")
    p = sub.add_parser("dense"); p.add_argument("name"); p.add_argument("--videos", required=True); p.add_argument("--fps", type=float, default=0)
    p.add_argument("--window", type=float, default=0); p.add_argument("--limit", type=int, default=0); p.add_argument("--video", default=""); p.add_argument("--redo", action="store_true")
    p = sub.add_parser("dedupe"); p.add_argument("name")
    p = sub.add_parser("merge"); p.add_argument("name")
    p = sub.add_parser("prune"); p.add_argument("name")
    p = sub.add_parser("pairs"); p.add_argument("name")
    p = sub.add_parser("verify"); p.add_argument("name"); p.add_argument("--limit", type=int, default=0)
    p = sub.add_parser("spans"); p.add_argument("name")
    p = sub.add_parser("stats"); p.add_argument("name")
    p = sub.add_parser("sort"); p.add_argument("name"); p.add_argument("--rules", action="store_true")
    p = sub.add_parser("learn"); p.add_argument("name")
    p = sub.add_parser("subs"); p.add_argument("name"); p.add_argument("--videos", required=True)
    p = sub.add_parser("review"); p.add_argument("name"); p.add_argument("--bucket", default="")
    a = ap.parse_args()
    {"init": cmd_init, "run": cmd_run, "dense": cmd_dense, "dedupe": cmd_dedupe, "merge": cmd_merge, "prune": cmd_prune, "learn": cmd_learn, "subs": cmd_subs, "pairs": cmd_pairs, "verify": cmd_verify, "spans": cmd_spans, "stats": cmd_stats, "review": cmd_review, "sort": cmd_sort}[a.cmd](a)


if __name__ == "__main__":
    main()
