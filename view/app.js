// VN view: the stage (background, sprite, overlay), her text, and her voice.
// The live edge is server-sent events; a poll is kept as the fallback, so a
// reader that cannot hold the stream open still sees every finished turn.

const canvas = document.getElementById("sprite");
const ctx = canvas.getContext("2d");
const spritePrevEl = document.getElementById("sprite-prev");
const prevCtx = spritePrevEl.getContext("2d");
const bgEl = document.getElementById("bg");
const bgPrevEl = document.getElementById("bg-prev");
const transitionOverlayEl = document.getElementById("transition-overlay");
const weatherEl = document.getElementById("weather");
const overlayEl = document.getElementById("overlay");
const faceEl = document.getElementById("face");
const textEl = document.getElementById("text");
const moodEl = document.getElementById("mood");
const audioEl = document.getElementById("audio");
const inputEl = document.getElementById("input");
const sendEl = document.getElementById("send");
const statusEl = document.getElementById("status");
const formEl = document.getElementById("say");
const replyOpenEl = document.getElementById("reply-open");
const dialogueContentEl = document.getElementById("dialogue-content");
const motionEl = document.getElementById("idle-motion");
const swayEl = document.getElementById("idle-sway");
const voiceAutoEl = document.getElementById("voice-auto");
const voiceModeEl = document.getElementById("voice-mode");
const qualityOnEl = document.getElementById("quality-on");
const scenePickEl = document.getElementById("scene-pick");
const outfitPickEl = document.getElementById("outfit-pick");
const voiceBadgeEl = document.getElementById("voice-badge");
const backlogEl = document.getElementById("backlog");
const bgmEl = document.getElementById("bgm");
const bgmOnEl = document.getElementById("bgm-on");
const seOnEl = document.getElementById("se-on");
const seEl = new Audio();
const voiceVolEl = document.getElementById("voice-vol");
const bgmVolEl = document.getElementById("bgm-vol");
const controlsEl = document.getElementById("controls");
const optionsOpenEl = document.getElementById("options-open");
const optionsCloseEl = document.getElementById("options-close");
const saveCreateEl = document.getElementById("save-create");
const saveListEl = document.getElementById("save-list");
const saveDialogEl = document.getElementById("save-dialog");
const saveCloseEl = document.getElementById("save-close");
const saveTabEl = document.getElementById("save-tab");
const loadTabEl = document.getElementById("load-tab");
const saveTitleEl = document.getElementById("save-title");
const saveLeadEl = document.getElementById("save-lead");
const loadConfirmEl = document.getElementById("load-confirm");
const loadCancelEl = document.getElementById("load-cancel");
const loadAcceptEl = document.getElementById("load-accept");
const loadConfirmTitleEl = document.getElementById("load-confirm-title");
const loadConfirmTextEl = document.getElementById("load-confirm-text");
const voiceReplayEl = document.getElementById("voice-replay");
const historyIndicatorEl = document.getElementById("history-indicator");
const historyReturnEl = document.getElementById("history-return");
const historyChangeEl = document.getElementById("history-change");
const replyDialogEl = document.getElementById("reply-dialog");
const replyCloseEl = document.getElementById("reply-close");
const replyContinueEl = document.getElementById("reply-continue");
const replyDrawEl = document.getElementById("reply-draw");
const replyCandidatesEl = document.getElementById("reply-candidates");
const fullscreenToggleEl = document.getElementById("fullscreen-toggle");
const quickSaveEl = document.getElementById("quick-save");
const quickLoadEl = document.getElementById("quick-load");
const saveOpenEl = document.getElementById("save-open");
const loadOpenEl = document.getElementById("load-open");
const autoToggleEl = document.getElementById("auto-toggle");
const skipReplyEl = document.getElementById("skip-reply");
const logOpenEl = document.getElementById("log-open");
const backLineEl = document.getElementById("back-line");
const trackPickEl = document.getElementById("track-pick");
const modelPickEl = document.getElementById("model-pick");
const stageModelPickEl = document.getElementById("model-stage-pick");
const stageEl = document.getElementById("stage");
const hudEl = document.getElementById("hud");
const nameEl = document.getElementById("name");
const advanceEl = document.getElementById("advance");
const directorOpenEl = document.getElementById("director-open");
const directorEl = document.getElementById("director");
const directorCloseEl = document.getElementById("director-close");
const directorSceneEl = document.getElementById("director-scene");
const directorLogEl = document.getElementById("director-log");
const directorProposalEl = document.getElementById("director-proposal");
const directorFormEl = document.getElementById("director-form");
const directorInputEl = document.getElementById("director-input");
const gaugeOpenEl = document.getElementById("gauge-open");
const gaugePanelEl = document.getElementById("gauge-panel");
const gaugeCloseEl = document.getElementById("gauge-close");
const gaugeLegendEl = document.getElementById("gauge-legend");
const gaugeCanvasEl = document.getElementById("gauge-canvas");

let currentTurn = -1;
let currentState = null;   // the frame the box is drawing, for its clip
let currentShownTs = 0;    // when that line went up, so a stuck clip cannot trap him
let composeToken = 0;
let lastSceneUrl = null;
let displayedSceneUrl = null;
let sceneTransitionToken = 0;
let lastFaceKey = null;  // face + sprite + overlay + mood, so a same-turn frame redraws only on a change
let lastBgmUrl = null;   // the track the stage is playing, from the staging
let bgmLoop = null;      // the game's own loop points for that track, seconds
let lastCueId = "";
let seenSceneCue = false;
let snowDrawn = false;
// the gauge chart: /gauge_history rows (oldest first), the gauge names in the
// order first seen (which fixes each one's color), and which are checked on
const GAUGE_COLORS = [
  "#d63031", "#0f8b82", "#1f7ea8", "#4f8f6a", "#b8860b",
  "#5f6b73", "#c2306f", "#5b46d1", "#00805f", "#c0502f",
  "#0a63b8", "#b86e00", "#b8236f", "#007f86", "#3d474d",
  "#b5543a", "#2f6fd0", "#7a63d8", "#1d9a6e", "#2a8a9a",
  "#c23b3b", "#8a6d00", "#6b7a80", "#7d8a90",
];
const GAUGE_DEFAULT_VISIBLE = new Set(["mood", "affection", "anxiety", "energy", "loneliness"]);
let gaugeData = [];
let gaugeOrder = [];
let gaugeVisible = {};
// A reply that spans several bubbles arrives as several published turns, one
// per bubble, with the channel's own delays between them. The stage shows one
// at a time and a click advances: the rest wait here. This is the visual
// novel's own shape, and it is why a per-bubble face is right -- each line he
// clicks to carries the face of the line he is reading.
let pending = [];
let awaiting = false;
let hisLinePending = false;   // he has sent and her reply has not landed yet
let streamingPreview = false; // the model's live draft is in the box
let saveResumeUsed = false;
let viewedFrames = [];
let viewedIndex = -1;
let historyPreview = null;
let backlogRows = [];
let saveMode = "save";
let quickSlotId = "";
let chosenLoadSlot = "";
let chosenLoadKind = "save";
let autoAdvance = false;
let branchDialogShown = false;
let readerBusy = true;
let composerOpen = false;
let replaySerial = 0;
let lastSpriteKey = "";
let spriteFadeTimer = 0;
let sceneFadeTimer = 0;
let idleMotion = null;   // the channel's default; null until a turn says
let idleSway = null;
let lastCamera = "static";      // the standing camera transform on #stage
let transitionOverlayTimer = 0; // clears a queued fade/flash step if another scene lands mid-transition

const reduceQuery = window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)")
  : null;

function preference(key) {
  try {
    return localStorage.getItem(key);
  } catch (e) {
    return null;
  }
}

function remember(key, on) {
  try {
    localStorage.setItem(key, on ? "1" : "0");
  } catch (e) { /* a browser with no storage is not a failure */ }
}

// A stored number rather than a switch, for the volume sliders.
function rememberValue(key, val) {
  try {
    localStorage.setItem(key, String(val));
  } catch (e) { /* a browser with no storage is not a failure */ }
}

// The player's own volume for her voice and for the music, independent of the
// two on/off switches. 1.0 is full; the slider is the multiplier the element
// and the music fade read, and the stored choice is restored on load.
let voiceVolume = 1.0;
let bgmVolume = 0.5;

function applyVoiceVolume() {
  if (audioEl) audioEl.volume = voiceVolume;
}

function applyBgmVolume() {
  bgmSetVolume(bgmVolume);
}

function restoreVolumes() {
  const vv = preference("vn.voiceVol");
  const bv = preference("vn.bgmVol");
  if (vv !== null && isFinite(Number(vv))) {
    voiceVolume = Math.min(1, Math.max(0, Number(vv)));
    if (voiceVolEl) voiceVolEl.value = String(voiceVolume);
  }
  if (bv !== null && isFinite(Number(bv))) {
    bgmVolume = Math.min(1, Math.max(0, Number(bv)));
    if (bgmVolEl) bgmVolEl.value = String(bgmVolume);
  }
  applyVoiceVolume();
  applyBgmVolume();
}

// Idle motion: the player's own choice wins. Then the channel's configured
// default, which is deliberate for this stage and beats the machine's
// reduced-motion preference. Reduced motion decides only when neither has said
// anything -- no stored choice and no default in the state. Sway rides on top,
// so turning motion off turns the drift off with it.
function effectiveMotion() {
  const saved = preference("vn.idleMotion");
  if (saved !== null) return saved === "1";
  if (idleMotion !== null) return idleMotion;
  return !(reduceQuery && reduceQuery.matches);
}

function effectiveSway() {
  const saved = preference("vn.idleSway");
  if (saved !== null) return saved === "1";
  return idleSway === true;
}

function applyIdle() {
  const motion = effectiveMotion();
  const sway = effectiveSway();
  document.body.classList.toggle("motion-on", motion);
  document.body.classList.toggle("sway-on", motion && sway);
  // Motion that resolved on is deliberate -- the player's toggle or the
  // channel's default -- so the reduced-motion media query must not override
  // it; this class is what lets the animation through.
  document.body.classList.toggle("force-motion", motion);
  if (motionEl) motionEl.checked = motion;
  if (swayEl) swayEl.checked = sway;
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("image failed: " + src));
    img.src = src;
  });
}

// The frame zoom the channel sends with the sprite. Her art is cut at the
// socks, so it is drawn larger than the viewport and anchored to the top, which
// puts the cut below the visible area; the CSS carries the same default for the
// first paint, before the first poll arrives.
function applyFrame(sprite) {
  const zoom = Number(sprite && sprite.zoom);
  if (!isFinite(zoom) || zoom <= 0) return;
  document.documentElement.style.setProperty("--vn-zoom", String(zoom));
}

async function composeSprite(sprite) {
  const key = sprite && sprite.base
    ? [sprite.base, sprite.diff || "", JSON.stringify(sprite.geometry || {})].join("|") : "";
  if (key === lastSpriteKey) return;
  const token = ++composeToken;
  if (!sprite || !sprite.base) {
    stageOldSprite();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    lastSpriteKey = "";
    return;
  }
  try {
    const base = await loadImage(sprite.base);
    if (token !== composeToken) return;
    // Build the complete face offscreen. Painting the base first exposes its
    // open eyes while the expression diff is still loading.
    const composed = document.createElement("canvas");
    composed.width = base.naturalWidth;
    composed.height = base.naturalHeight;
    const composedCtx = composed.getContext("2d");
    composedCtx.drawImage(base, 0, 0);
    if (sprite.diff && sprite.geometry) {
      const diff = await loadImage(sprite.diff);
      if (token !== composeToken) return;
      composedCtx.drawImage(diff, sprite.geometry.x, sprite.geometry.y);
    }
    if (token !== composeToken) return;
    stageOldSprite();
    canvas.width = composed.width;
    canvas.height = composed.height;
    ctx.drawImage(composed, 0, 0);
    lastSpriteKey = key;
  } catch (e) {
    setStatus(e.message);
  }
}

function stageOldSprite() {
  clearTimeout(spriteFadeTimer);
  if (!lastSpriteKey || !effectiveMotion()) {
    spritePrevEl.hidden = true;
    return;
  }
  spritePrevEl.width = canvas.width;
  spritePrevEl.height = canvas.height;
  prevCtx.drawImage(canvas, 0, 0);
  spritePrevEl.hidden = false;
  spritePrevEl.classList.remove("fade-out");
  void spritePrevEl.offsetWidth;
  requestAnimationFrame(() => spritePrevEl.classList.add("fade-out"));
  spriteFadeTimer = setTimeout(() => { spritePrevEl.hidden = true; }, 340);
}

// ---- the stage manager console (舞台相談) ----
// He talks to the out-of-character console in English: it answers about the
// current scene and proposes a scene for his approval. Nothing is written and
// no scene starts until he approves; the approve button is wired when the write
// path lands.
async function loadDirector() {
  try {
    const r = await fetch("/director", { cache: "no-store" });
    const data = await r.json();
    renderDirector(data);
  } catch (e) {
    setStatus("director: " + e.message);
  }
}

function renderDirector(data) {
  const status = (data && data.status) || {};
  const hist = (data && data.history) || [];
  if (directorSceneEl) directorSceneEl.textContent = status.current_scene || "(no scene yet)";
  if (directorLogEl) {
    directorLogEl.innerHTML = "";
    for (const turn of hist) appendDirectorTurn(turn.role, turn.text);
  }
}

function appendDirectorTurn(role, text) {
  if (!directorLogEl) return;
  const div = document.createElement("div");
  div.className = "director-turn " + (role === "assistant" ? "console" : "him");
  div.textContent = text;
  directorLogEl.appendChild(div);
  directorLogEl.scrollTop = directorLogEl.scrollHeight;
}

async function sendDirector(text) {
  const line = (text || "").trim();
  if (!line) return;
  appendDirectorTurn("user", line);
  if (directorInputEl) directorInputEl.value = "";
  setStatus("舞台相談…");
  try {
    const r = await fetch("/director", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: line }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { setStatus("director: " + (data.error || r.status)); return; }
    if (data.reply) appendDirectorTurn("assistant", data.reply);
    if (data.proposal) showProposal(data.proposal);
    setStatus("");
  } catch (e) {
    setStatus("director: " + e.message);
  }
}

function showProposal(p) {
  if (!directorProposalEl) return;
  directorProposalEl.hidden = false;
  directorProposalEl.innerHTML = "";
  const line = document.createElement("div");
  line.className = "director-proposal-text";
  line.textContent = p.text || "(a scene)";
  directorProposalEl.appendChild(line);
  const meta = document.createElement("div");
  meta.className = "director-proposal-meta";
  meta.textContent = [
    "place: " + (p.place || "none"),
    "bg: " + (p.bg || "?"),
    "light: " + (p.mood || "neutral"),
    "outfit: " + (p.outfit || "default"),
    "opening face: " + (p.face_index || "line emotion"),
    "music: " + (p.bgm ? (p.bgm + (p.bgm_title ? " " + p.bgm_title : "")) : "silence"),
    "voice cue: " + (p.interjection || "none"),
  ].join("  ·  ");
  directorProposalEl.appendChild(meta);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "承認して開始";
  btn.addEventListener("click", () => approveProposal(p));
  directorProposalEl.appendChild(btn);
  const clear = document.createElement("button");
  clear.type = "button";
  clear.textContent = "戻す";
  clear.title = "hand the scene back to the main thread";
  clear.addEventListener("click", clearDirector);
  directorProposalEl.appendChild(clear);
}

// He approved the proposal: the channel holds it and the loop writes the scene
// and opens it. The console chat is already on the record; the scene is not
// written until here.
async function approveProposal(p) {
  setStatus("舞台相談: 開始…");
  try {
    const r = await fetch("/director/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proposal: p }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { setStatus("director: " + (data.error || r.status)); return; }
    if (directorProposalEl) directorProposalEl.hidden = true;
    setStatus("舞台相談: 開始しました");
  } catch (e) {
    setStatus("director: " + e.message);
  }
}

async function clearDirector() {
  try {
    await fetch("/director/clear", { method: "POST" });
    if (directorProposalEl) directorProposalEl.hidden = true;
    setStatus("舞台相談: 戻しました");
    loadDirector();
  } catch (e) {
    setStatus("director: " + e.message);
  }
}

// What the face is drawn from, as one string. A same-turn frame (a voice clip
// arriving, a control toggled, the four-second poll) carries the same face as
// the last one, and redrawing it would restart the overlay's animation and
// reload the sprite every time; a reaction or a track he picked by hand changes
// this key, and only then is the face redrawn.
function faceKey(state) {
  const s = state.sprite || {};
  return [state.face || "", s.tag || "", s.diff || "", state.overlay || "", state.mood || ""].join("|");
}

// The director names the kind of cut with `scene.transition`; each kind is a
// different way to get from `displayedSceneUrl` to `scene.url`. `cut` and a
// missing prior frame skip the animation outright; `fade`/`crossfade` are the
// original opacity fade at two speeds; `fade_black`/`white`/`flash` cross a
// solid overlay (added above `#bg`, below `#stage`) instead of the two
// backgrounds fading into each other.
function renderScene(scene) {
  if (!scene || !scene.url) return;
  if (scene.url === lastSceneUrl) return;
  lastSceneUrl = scene.url;
  const kind = scene.transition || "cut";
  const token = ++sceneTransitionToken;
  loadImage(scene.url).then(() => {
    if (token !== sceneTransitionToken) return;
    clearTimeout(sceneFadeTimer);
    clearTimeout(transitionOverlayTimer);
    const motion = effectiveMotion();
    const hadPrior = !!displayedSceneUrl;
    const swap = () => { bgEl.style.backgroundImage = "url('" + scene.url + "')"; displayedSceneUrl = scene.url; };

    if (!motion || kind === "cut" || !hadPrior) {
      bgPrevEl.hidden = true;
      if (transitionOverlayEl) { transitionOverlayEl.style.transition = "none"; transitionOverlayEl.style.opacity = "0"; transitionOverlayEl.hidden = true; }
      swap();
      return;
    }

    if (kind === "flash" && transitionOverlayEl) {
      transitionOverlayEl.style.background = "#fff";
      transitionOverlayEl.style.transition = "none";
      transitionOverlayEl.style.opacity = "1";
      transitionOverlayEl.hidden = false;
      swap();
      void transitionOverlayEl.offsetWidth;
      requestAnimationFrame(() => {
        transitionOverlayEl.style.transition = "opacity 0.15s ease";
        transitionOverlayEl.style.opacity = "0";
      });
      transitionOverlayTimer = setTimeout(() => { transitionOverlayEl.hidden = true; }, 180);
      return;
    }

    if ((kind === "fade_black" || kind === "white") && transitionOverlayEl) {
      transitionOverlayEl.style.background = kind === "white" ? "#fff" : "#000";
      transitionOverlayEl.style.transition = "none";
      transitionOverlayEl.style.opacity = "0";
      transitionOverlayEl.hidden = false;
      void transitionOverlayEl.offsetWidth;
      transitionOverlayEl.style.transition = "opacity 0.3s ease";
      requestAnimationFrame(() => { transitionOverlayEl.style.opacity = "1"; });
      transitionOverlayTimer = setTimeout(() => {
        swap();
        requestAnimationFrame(() => { transitionOverlayEl.style.opacity = "0"; });
        transitionOverlayTimer = setTimeout(() => { transitionOverlayEl.hidden = true; }, 320);
      }, 320);
      return;
    }

    // fade (0.42s) and crossfade (0.6s): the old background stays on top of
    // the new one, drawn immediately below, and fades out over it.
    const slow = kind === "crossfade";
    bgPrevEl.style.backgroundImage = "url('" + displayedSceneUrl + "')";
    bgPrevEl.hidden = false;
    bgPrevEl.classList.remove("fade-out", "fade-out-slow");
    void bgPrevEl.offsetWidth;
    requestAnimationFrame(() => bgPrevEl.classList.add(slow ? "fade-out-slow" : "fade-out"));
    sceneFadeTimer = setTimeout(() => { bgPrevEl.hidden = true; }, slow ? 650 : 470);
    swap();
  }).catch((e) => setStatus(e.message));
}

// The director's `scene.camera` value as a standing transform on `#stage`.
// `shake` is transient: it plays the keyframe animation once, then restores
// whatever transform was standing before it (or `static` if the shake somehow
// followed another shake). Reduced motion applies the target transform
// instantly and skips the shake animation entirely.
function applyCameraTransform(el, cam) {
  switch (cam) {
    case "pan_left":  el.style.transform = "translateX(5%)"; break;
    case "pan_right": el.style.transform = "translateX(-5%)"; break;
    case "zoom_in":   el.style.transform = "scale(1.15)"; break;
    case "zoom_out":  el.style.transform = "scale(0.9)"; break;
    case "focus":     el.style.transform = "scale(1.1)"; break;
    default:          el.style.transform = ""; break;
  }
}

function renderCamera(scene) {
  const cam = (scene && scene.camera) || "static";
  if (cam === lastCamera) return;
  const prev = lastCamera;
  lastCamera = cam;
  if (!stageEl) return;
  const motion = effectiveMotion();
  if (cam === "shake") {
    if (!motion) { lastCamera = prev === "shake" ? "static" : prev; return; }
    stageEl.style.animation = "camera-shake 0.4s ease";
    stageEl.addEventListener("animationend", () => {
      stageEl.style.animation = "";
      applyCameraTransform(stageEl, prev === "shake" ? "static" : prev);
    }, { once: true });
    return;
  }
  if (!motion) {
    stageEl.style.transition = "none";
    applyCameraTransform(stageEl, cam);
    requestAnimationFrame(() => { stageEl.style.transition = ""; });
    return;
  }
  applyCameraTransform(stageEl, cam);
}

function renderWeather(scene) {
  if (!weatherEl) return;
  const on = !!(scene && scene.snow && scene.snow_urls && scene.snow_urls.length);
  weatherEl.hidden = !on;
  if (!on || snowDrawn) return;
  const urls = scene.snow_urls;
  for (let i = 0; i < 32; i++) {
    const flake = document.createElement("span");
    flake.className = "snowflake";
    flake.style.left = ((i * 37 + 11) % 100) + "%";
    flake.style.setProperty("--flake", "url('" + urls[i % urls.length] + "')");
    flake.style.setProperty("--size", (14 + (i * 11) % 22) + "px");
    flake.style.setProperty("--opacity", String(0.35 + (i % 5) * 0.11));
    flake.style.setProperty("--duration", (9 + (i * 7) % 12) + "s");
    flake.style.setProperty("--delay", "-" + ((i * 13) % 20) + "s");
    flake.style.setProperty("--still-top", ((i * 23) % 100) + "vh");
    weatherEl.appendChild(flake);
  }
  snowDrawn = true;
}

function renderSound(scene) {
  const cueId = scene && scene.cue_id ? String(scene.cue_id) : "";
  if (!seenSceneCue) {
    seenSceneCue = true;
    lastCueId = cueId;
    return;
  }
  if (!cueId || cueId === lastCueId) return;
  lastCueId = cueId;
  if (!scene.se_url || (seOnEl && !seOnEl.checked)) return;
  seEl.pause();
  seEl.src = scene.se_url;
  seEl.currentTime = 0;
  seEl.volume = Math.min(1, bgmVolume);
  const p = seEl.play();
  if (p && p.catch) p.catch(() => {});
}

// The music `sim/scene.py` chose for the staging. It is a bed under the scene:
// it changes only when the track does, so a turn that keeps the same music
// never restarts it, and a change fades in rather than cutting mid-phrase.
// Muted until he turns it on, and browsers hold playback until the page has
// been touched, which the send button does.
//
// The loop is the game's own. The `.sli` points are sample positions and the
// game applied them inside KiriKiri's WaveSoundBuffer, which loops the decoded
// samples exactly (`data/Sound.tjs`, `.looping = loop`). An <audio> element only
// seeks on a coarse timeline and lands on an Ogg granule, which is audible on a
// track with a lead-in. So the track is decoded once with the Web Audio API and
// looped on an AudioBufferSourceNode at `loopStart`/`loopEnd` -- the same
// sample-accurate seam the game has. If the context or the decode is
// unavailable, the element path with the corrected points is the fallback.
let audioCtx = null;
let bgmSource = null;      // the playing AudioBufferSourceNode
let bgmGain = null;        // its gain, which the volume slider drives
let bgmPlayingUrl = null;  // the track that source is playing
let bgmToken = 0;          // a load that finishes late must not win
const bgmBuffers = new Map();

function bgmContext() {
  if (audioCtx) return audioCtx;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  try { audioCtx = new Ctx(); } catch (e) { audioCtx = null; }
  return audioCtx;
}

// Browsers hold an AudioContext suspended until the page is touched; resume it
// on any interaction so the bed starts as soon as he does anything.
function resumeAudio() {
  const ctx = audioCtx;
  if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {});
}
window.addEventListener("pointerdown", resumeAudio);
window.addEventListener("keydown", resumeAudio);

function renderBgm(scene) {
  if (!bgmEl) return;
  const url = scene && scene.bgm_url ? scene.bgm_url : null;
  bgmLoop = (scene && scene.bgm_loop) || null;
  if (url === lastBgmUrl) return;
  lastBgmUrl = url;
  applyBgm();
}

function bgmStop() {
  if (bgmSource) {
    try { bgmSource.stop(); } catch (e) { /* already stopped */ }
    try { bgmSource.disconnect(); } catch (e) { /* already gone */ }
  }
  bgmSource = null;
  bgmPlayingUrl = null;
  if (bgmEl) bgmEl.pause();
}

async function bgmPlayWebAudio(url, loop, token) {
  const ctx = bgmContext();
  if (!ctx) return false;
  let buf = bgmBuffers.get(url);
  if (!buf) {
    const r = await fetch(url, { cache: "force-cache" });
    if (!r.ok) throw new Error("bgm " + r.status);
    buf = await ctx.decodeAudioData(await r.arrayBuffer());
    bgmBuffers.set(url, buf);
  }
  if (token !== bgmToken) return true; // a newer track won the race
  bgmStop();
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.loop = true;
  if (loop && loop.to > 0 && loop.from > loop.to && loop.from <= buf.duration) {
    src.loopStart = loop.to;
    src.loopEnd = loop.from;
  }
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0, ctx.currentTime);
  gain.gain.linearRampToValueAtTime(bgmVolume, ctx.currentTime + 0.8);
  src.connect(gain).connect(ctx.destination);
  src.start(0);
  src.onended = () => {
    if (bgmSource === src) { bgmSource = null; bgmPlayingUrl = null; }
  };
  bgmSource = src;
  bgmGain = gain;
  bgmPlayingUrl = url;
  return true;
}

function bgmPlayElement(url, loop) {
  if (!bgmEl) return;
  bgmEl.dataset.track = url;
  bgmEl.dataset.loopFrom = loop ? String(loop.from) : "";
  bgmEl.dataset.loopTo = loop ? String(loop.to) : "";
  if (bgmEl.src !== url) bgmEl.src = url;
  bgmEl.loop = true;
  bgmEl.volume = 0;
  const fade = () => {
    let v = 0;
    const id = setInterval(() => {
      v = Math.min(1, v + 0.08);
      bgmEl.volume = v * bgmVolume;
      if (v >= 1) clearInterval(id);
    }, 60);
  };
  const p = bgmEl.play();
  if (p && p.then) p.then(fade).catch(() => setStatus("music blocked (click the page)"));
  else fade();
}

function applyBgm() {
  const token = ++bgmToken;
  const on = (bgmOnEl ? bgmOnEl.checked : true) && !!lastBgmUrl;
  if (!on) {
    bgmStop();
    return;
  }
  if (bgmSource && bgmPlayingUrl === lastBgmUrl) {
    bgmSetVolume(bgmVolume);
    return;
  }
  const ctx = bgmContext();
  if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {});
  const url = lastBgmUrl;
  const loop = bgmLoop;
  bgmPlayWebAudio(url, loop, token)
    .then((ok) => { if (!ok && token === bgmToken) bgmPlayElement(url, loop); })
    .catch(() => { if (token === bgmToken) bgmPlayElement(url, loop); });
}

function bgmSetVolume(v) {
  if (bgmGain && audioCtx) {
    try { bgmGain.gain.setTargetAtTime(v, audioCtx.currentTime, 0.05); } catch (e) { /* gone */ }
  }
  if (bgmEl) bgmEl.volume = v;
}

// The element fallback still needs its own seam watch: `timeupdate` fires about
// four times a second and the gap between the loop end and the file's end can
// be under a tenth of a second, so it is checked far more often. With Web Audio
// running, `bgmEl.paused` is true and this does nothing.
if (bgmEl) {
  setInterval(() => {
    if (bgmEl.paused) return;
    const from = parseFloat(bgmEl.dataset.loopFrom || "");
    const to = parseFloat(bgmEl.dataset.loopTo || "");
    if (!(from > to) || !(to > 0)) return;
    if (bgmEl.currentTime >= from) {
      try { bgmEl.currentTime = to; } catch (e) { /* not seekable yet */ }
    }
  }, 25);
}

// The emotion marks the corpus carries, by the family of their file name.
// Each family gets motion suited to the mark (a heart drifts up and fades, a
// question bobs); a name outside the table falls back to the gentle bob.
const MARK_GROUPS = ["heart", "star", "question", "drop", "attention", "baloon", "chat"];

function overlayMark(url) {
  const base = String(url || "").split("/").pop().toLowerCase().replace(/\.png$/, "");
  return MARK_GROUPS.find((g) => base.startsWith(g)) || "generic";
}

// Where each family of mark sits on her head, from the game's own
// `BUSTUP_EMOTION_POS` for her costume (`CgSetupInfo.tjs`, MMK_X/Y/Z). The
// game names five points on the head and the script picks one per mark; the
// values here are the named point relative to the face box, as a fraction of
// it (0.5, 0.5 is its centre). The deltas between the game's own points, in
// units of that box: the temple is +0.47 across and -0.17 up, the head (the
// top of her hair) +0.17 across and -1.16 up, the forehead +0.08 across and
// -0.50 up -- so the head and the forehead read above the face and the temple
// sits at her upper right, which is where the sweat drop belongs.
const MARK_ANCHOR = {
  drop:      { x: 0.97, y: 0.33 },   // temple, beside her upper right
  question:  { x: 0.67, y: -0.66 },  // the head, above the face box
  attention: { x: 0.67, y: -0.66 },
  chat:      { x: 0.67, y: -0.66 },
  star:      { x: 0.58, y: 0.00 },   // the forehead
  heart:     { x: 0.85, y: -0.50 },  // above and right of head
  baloon:    { x: 0.50, y: 0.50 },
  generic:   { x: 0.67, y: -0.66 },
};

// The face box the last frame carried, in canvas pixels (`geometry` on the
// sprite, the diff patch that paints the face). A face with no patch of its
// own -- the worried one is drawn on the neutral base -- keeps this box,
// which is right because the base and the pose are the same.
let faceBox = null;
let overlayOn = false;

function renderOverlay(state) {
  const sprite = state.sprite || {};
  if (sprite.geometry) faceBox = sprite.geometry;
  if (state.overlay) {
    // reset the class so a new mark's motion starts from its first frame
    overlayEl.className = "";
    overlayEl.src = state.overlay;
    overlayEl.className = "on mark-" + overlayMark(state.overlay);
    overlayOn = true;
    placeOverlay();
  } else {
    overlayEl.className = "";
    overlayOn = false;
  }
}

// Put the mark on her head. The sprite's own rect is read after its
// transforms, so the mark rides the breathing and the sway for free; the face
// box is in canvas pixels and scales with it, so a change to `--vn-zoom`
// carries both. The size is the piece's native pixels times that same scale --
// the game draws a mark at its art size on the sprite's grid -- then capped so
// a stray aspect or a very tall viewport cannot blow it up.
function placeOverlay() {
  if (!overlayOn || !overlayEl.naturalWidth || !overlayEl.naturalHeight) return;
  const s = canvas.getBoundingClientRect();
  if (!s.height || !canvas.height) return;
  const scale = s.height / canvas.height;
  const g = faceBox || {
    x: canvas.width * 0.32, y: canvas.height * 0.088,
    w: canvas.width * 0.248, h: canvas.height * 0.094,
  };
  const a = MARK_ANCHOR[overlayMark(overlayEl.src)] || MARK_ANCHOR.generic;
  const cx = s.left + (g.x + g.w * a.x) * scale;
  const cy = s.top + (g.y + g.h * a.y) * scale;
  let w = overlayEl.naturalWidth * scale;
  let h = overlayEl.naturalHeight * scale;
  const cap = Math.min(window.innerWidth * 0.20, window.innerHeight * 0.34);
  const k = Math.min(1, cap / w, cap / h);
  w *= k;
  h *= k;
  // Her head sits at the very top of the stage, so a tall mark (the
  // exclamation is 169px of art) would otherwise be cut off above the
  // viewport; hold it inside the stage rather than let it leave.
  const left = Math.max(0, Math.min(cx - w / 2, window.innerWidth - w));
  const top = Math.max(0, cy - h / 2);
  overlayEl.style.width = w + "px";
  overlayEl.style.height = h + "px";
  overlayEl.style.left = left + "px";
  overlayEl.style.top = top + "px";
}

// The mark's place is recomputed every frame while it is on: the idle motion
// is a CSS animation, so polling it on a timer would sawtooth and the mark
// would slide off her head between ticks.
function overlayTick() {
  if (overlayOn) placeOverlay();
  requestAnimationFrame(overlayTick);
}
requestAnimationFrame(overlayTick);

// Her voice. Each line's audio is prefetched the moment the frame names it, so
// advancing plays at once instead of waiting on a fetch; the element itself is
// the one player, and a blocked autoplay says so rather than failing silently.
// The audio for a turn can arrive after its text (the channel publishes the
// line, then attaches the clip), which is why `render` plays it on the
// unchanged-turn path too.
let lastAudioUrl = null;
const audioCache = new Map();

function preloadAudio(url) {
  if (!url || audioCache.has(url)) return;
  const a = new Audio();
  a.preload = "auto";
  a.src = url;
  audioCache.set(url, a);
}

function playAudio(url) {
  if (!url) return;
  lastAudioUrl = url;
  preloadAudio(url);
  if (audioEl.src !== url) audioEl.src = url;
  try { audioEl.currentTime = 0; } catch (e) { /* not seekable yet */ }
  applyVoiceVolume();
  const p = audioEl.play();
  if (p && p.catch) p.catch((e) => setStatus("voice blocked (click the page): " + e.message));
}

// A line he asked to hear again: play it from the top even if it is the clip
// that just played. `playAudio` short-circuits on the same url, which is right
// for a turn that arrives once and wrong for a ♪ pressed twice. This does NOT
// touch `lastAudioUrl`: that name tracks the clip of the turn on screen, and
// moving it to the replayed line made the next frame see a mismatch and start
// the turn's own clip again -- so a ♪ on an older line was interrupted by the
// line on screen, which then kept replaying on every frame (2026-09-17).
function replayAudio(url) {
  if (!url) return Promise.reject(new Error("no audio URL"));
  preloadAudio(url);
  if (audioEl.src !== url) audioEl.src = url;
  try { audioEl.currentTime = 0; } catch (e) { /* not seekable yet */ }
  applyVoiceVolume();
  const p = audioEl.play();
  return p && p.then ? p : Promise.resolve();
}

// The clip for a turn. The channel attaches each bubble's audio to that
// bubble's hub id (`audio_by_turn`), because a clip can land after the next
// bubble was published; the frame's own `audio` is the line on screen.
function turnAudio(state) {
  if (!state) return null;
  const byTurn = state.audio_by_turn || {};
  const id = state.turn_id;
  if (id && byTurn[id]) return byTurn[id];
  return state.audio || null;
}

// Whether the WHOLE reply behind the line on screen has its clips. The mark
// means the reply is finished being prepared, not just the next line: checking
// only `pending[0]` showed the ready mark while later lines were still being
// voiced, and a click landed on a line with no clip yet (2026-09-17).
function queuedReady() {
  if (!pending.length) return true;
  return pending.every((s) => {
    const url = turnAudio(s);
    return !!(url && audioCache.has(url));
  });
}

// A line is finished once its own clip has arrived, when voice is on for this
// engagement. Until then it is not finished and the mark must not pretend it
// is: the button used to appear on the text alone, so a click advanced and
// played silence while the clip was still being made (2026-09-17).
function lineReady(state) {
  if (!state) return true;
  if (!(state.voice && state.voice.auto)) return true;  // no voice wanted
  if (state.audio_error) return true;                   // it failed; do not hold him
  const url = turnAudio(state);
  return !!(url && audioCache.has(url));
}

// The one authority for the advance mark. It shows only when there is a line
// behind this one and this line is finished (its clip ready). While the clip is
// being made the mark reads `waiting`; a clip that never comes releases after
// the cap so a broken render cannot trap him in a line.
const CLIP_WAIT_MS = 20000;

function markReady() {
  if (!advanceEl) return;
  if (historyPreview) {
    advanceEl.classList.remove("waiting");
    advanceEl.classList.toggle("on", historyPreview.index < historyPreview.entries.length - 1);
    updateReplyAffordance();
    return;
  }
  const capped = (Date.now() - currentShownTs) >= CLIP_WAIT_MS;
  const curWaiting = !!currentState && !lineReady(currentState) && !capped;
  const nextWaiting = pending.length > 0 && !queuedReady() && !capped;
  advanceEl.classList.toggle("waiting", curWaiting || nextWaiting);
  advanceEl.classList.toggle("on", !curWaiting && !nextWaiting && pending.length > 0);
  if (hudEl) hudEl.classList.toggle("generating", curWaiting || nextWaiting);
  updateReplyAffordance();
}

function updateReplyAffordance() {
  if (!replyOpenEl) return;
  const isHis = currentState && (currentState.speaker === "一悟" || currentState.speaker === "you");
  const voiceDone = !audioEl || audioEl.paused || audioEl.ended;
  const ready = !currentState || lineReady(currentState) || Date.now() - currentShownTs >= CLIP_WAIT_MS;
  replyOpenEl.hidden = !(currentState && !isHis && !historyPreview && !composerOpen &&
    !readerBusy && !hisLinePending && !pending.length && awaiting && ready && voiceDone);
}

function closeComposer({restoreReply = true} = {}) {
  composerOpen = false;
  formEl.hidden = true;
  hudEl.classList.remove("replying");
  if (restoreReply) awaiting = true;
  updateReplyAffordance();
}

function openComposer() {
  if (!replyOpenEl || replyOpenEl.hidden) return;
  composerOpen = true;
  awaiting = false;
  formEl.hidden = false;
  hudEl.classList.add("replying");
  replyOpenEl.hidden = true;
  inputEl.focus();
}
if (replyOpenEl) replyOpenEl.addEventListener("click", (ev) => {
  ev.stopPropagation();
  openComposer();
});
formEl.addEventListener("click", (ev) => ev.stopPropagation());
audioEl.addEventListener("ended", markReady);
audioEl.addEventListener("pause", markReady);

function setStatus(msg) {
  statusEl.textContent = msg || "";
}

function postControl(payload) {
  return fetch("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => null);
}

// The ♪ beside one of her lines: she says that line again. The clip is already
// on disk -- it was made when the line was first spoken -- so the channel
// locates it and hands back its URL, and the stage plays it directly. Nothing
// is re-filed against a turn and nothing waits on a new turn.
async function speak(text, id, button) {
  if (button) {
    button.dataset.replayTitle = button.dataset.replayTitle || button.title;
    button.disabled = true;
    button.textContent = "…";
  }
  setStatus("百花、もう一度…");
  try {
    const r = await fetch("/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, id }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || !data.url) {
      throw new Error(data.error || String(r.status));
    }
    await replayAudio(data.url);
    setStatus("");
    if (button) button.title = button.dataset.replayTitle;
  } catch (e) {
    setStatus("voice: " + e.message);
    if (button) { button.textContent = "!"; button.title = "再生できません: " + e.message; }
  } finally {
    if (button) {
      button.disabled = false;
      if (button.textContent === "…") button.textContent = "\u266a";
    }
  }
}

// A background he picked by hand. Sent once for this turn and stored, so a
// refresh puts the same one back instead of dropping to the director's default.
async function requestScene(bg) {
  if (!bg) return;
  try {
    const r = await fetch("/scene", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bg }),
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      setStatus("background: " + (data.error || r.status));
    }
  } catch (e) {
    setStatus("background: " + e.message);
  }
}

async function loadScenes() {
  if (!scenePickEl) return;
  try {
    const r = await fetch("/scenes", { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    scenePickEl.innerHTML = "";
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "背景…";
    scenePickEl.appendChild(none);
    for (const id of data.backgrounds || []) {
      const o = document.createElement("option");
      o.value = id;
      o.textContent = id;
      scenePickEl.appendChild(o);
    }
    // the background he picked is remembered: put it back on the list and
    // re-apply it, so a refresh does not silently drop it
    const saved = preference("vn.bg");
    if (saved) {
      scenePickEl.value = saved;
      requestScene(saved);
    }
  } catch (e) { /* the picker is optional; the stage still draws */ }
}

// A track he picked by hand. Unlike the background the channel holds it until
// he picks "director", and the track carries the mood of its own title, so the
// music he chose also colours the light and her face.
async function requestTrack(bgm) {
  try {
    const r = await fetch("/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bgm }),
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      setStatus("track: " + (data.error || r.status));
    }
  } catch (e) {
    setStatus("track: " + e.message);
  }
}

async function loadTracks() {
  if (!trackPickEl) return;
  try {
    const r = await fetch("/tracks", { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    trackPickEl.innerHTML = "";
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "監督任せ";
    trackPickEl.appendChild(auto);
    for (const t of data.tracks || []) {
      const o = document.createElement("option");
      o.value = t.id;
      o.textContent = t.title ? t.id + " " + t.title : t.id;
      trackPickEl.appendChild(o);
    }
    // the track he picked is remembered: put it back and re-apply it
    const saved = preference("vn.track");
    if (saved) {
      trackPickEl.value = saved;
      requestTrack(saved);
    }
  } catch (e) { /* the picker is optional; the stage still draws */ }
}

// An outfit he picked by hand. The sprite changes at once and the channel asks
// the runtime to let her notice it, so she knows what she is wearing and reacts
// to it. An empty pick is her default.
async function requestOutfit(outfit) {
  try {
    const r = await fetch("/outfit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outfit }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      setStatus("outfit: " + (data.error || r.status));
      return;
    }
    setStatus("");
  } catch (e) {
    setStatus("outfit: " + e.message);
  }
}

async function loadOutfits() {
  if (!outfitPickEl) return;
  try {
    const r = await fetch("/outfits", { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    outfitPickEl.innerHTML = "";
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "いつもの服";
    outfitPickEl.appendChild(auto);
    for (const o of data.outfits || []) {
      const opt = document.createElement("option");
      opt.value = o.id;
      opt.textContent = o.what ? o.id + " " + o.what : o.id;
      outfitPickEl.appendChild(opt);
    }
    const saved = preference("vn.outfit");
    if (saved) outfitPickEl.value = saved;
  } catch (e) { /* the picker is optional; the stage still draws */ }
}

// The model her words are written on. The choice is pinned on her own save by
// the runtime, so it outlives a restart and nothing is stored here.
async function requestModel(name) {
  try {
    const r = await fetch("/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: name }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      setStatus("model: " + (data.error || data.message || r.status));
      return;
    }
    if (modelPickEl && data.model) modelPickEl.value = data.model;
  } catch (e) {
    setStatus("model: " + e.message);
  }
}

async function loadModels() {
  if (!modelPickEl) return;
  try {
    const r = await fetch("/models", { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    modelPickEl.innerHTML = "";
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "設定どおり";
    modelPickEl.appendChild(auto);
    const names = data.models || [];
    if (data.model && names.indexOf(data.model) === -1) names.push(data.model);
    for (const name of names) {
      const o = document.createElement("option");
      o.value = name;
      o.textContent = name;
      modelPickEl.appendChild(o);
    }
    if (data.model) modelPickEl.value = data.model;
  } catch (e) { /* the picker is optional; the stage still draws */ }
}

// The model the STAGE roles are on -- the machinery behind the scene, not her
// words. The first picker moves only the eleven voice roles; 79 of her 90
// roles are the stage's and this is the only way to move them from the stage.
// The two choices are independent, and each is pinned on her own save.
async function requestStageModel(name) {
  try {
    const r = await fetch("/model-stage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: name }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      setStatus("model: " + (data.error || data.message || r.status));
      return;
    }
    if (stageModelPickEl) stageModelPickEl.value = data.model || "";
  } catch (e) {
    setStatus("model: " + e.message);
  }
}

async function loadStageModel() {
  if (!stageModelPickEl) return;
  try {
    const r = await fetch("/model-stage", { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    stageModelPickEl.innerHTML = "";
    const auto = document.createElement("option");
    auto.value = "";
    auto.textContent = "設定どおり";
    stageModelPickEl.appendChild(auto);
    const names = data.models || [];
    if (data.model && names.indexOf(data.model) === -1) names.push(data.model);
    for (const name of names) {
      const o = document.createElement("option");
      o.value = name;
      o.textContent = name;
      stageModelPickEl.appendChild(o);
    }
    if (data.model) stageModelPickEl.value = data.model;
  } catch (e) { /* the picker is optional; the stage still draws */ }
}

function voiceBadge(voice, audio) {
  if (!voice || !audio) return "";
  if (voice.source === "clip") {
    // a tilde marks a near match rather than the line itself (tier 3)
    const near = voice.match && voice.match.tier === 3 ? "~" : "";
    return voice.clip ? "録音" + near + " " + voice.clip : "録音";
  }
  if (voice.source === "tts") return "合成";
  return "";
}

// What the clip actually says, when it is a recorded line: the matched line,
// how close it was, and which tier matched. The stage says which real match it
// is playing instead of leaving it to the ear.
function voiceTitle(voice) {
  const m = voice && voice.match;
  if (!m) return "";
  const parts = [];
  if (m.matched) parts.push("元の台詞: " + m.matched);
  if (m.tier) parts.push("tier " + m.tier);
  if (typeof m.ratio === "number") parts.push("一致 " + Math.round(m.ratio * 100) + "%");
  return parts.join(" · ");
}

// What the backlog says about a line's recorded clip. An exact line is just
// marked as recorded; a near miss names the line that will actually be heard
// and how close it was, so the ear is never the only way to know (2026-09-17).
function matchLabel(m) {
  if (!m) return "";
  if (m.tier === 3) {
    const pct = typeof m.ratio === "number" ? " " + Math.round(m.ratio * 100) + "%" : "";
    return "近似: 「" + (m.matched || "") + "」" + pct;
  }
  return "録音";
}

// The backlog: the conversation so far, both sides, so what he typed is still
// readable after it has been sent -- the frame carries only the newest turn.
// It is a plain scroll box, so the wheel works over it and nowhere else.
// The rendered rows are keyed to a signature of the whole window, not its
// length: /log returns a fixed newest 80, so the length stops changing while
// the rows keep shifting. Comparing length alone left the DOM showing an older
// window, and Jump then replayed whatever now sat at that position (2026-09-18).
let logSig = null;

function logSignature(rows) {
  return rows.map((m) => {
    const match = m.match
      ? [m.match.tier, m.match.matched || "",
         typeof m.match.ratio === "number" ? m.match.ratio : ""].join(":")
      : "";
    return [m.id == null ? "" : m.id, m.role || "", m.text || "", match].join("|");
  }).join("\u0001");
}

function nearBottom(el) {
  return el.scrollHeight - el.scrollTop - el.clientHeight < 40;
}

async function loadLog() {
  if (!backlogEl) return;
  try {
    const r = await fetch("/log", { cache: "no-store" });
    if (!r.ok) return;
    const data = await r.json();
    const rows = data.messages || [];
    backlogRows = rows;
    const sig = logSignature(rows);
    if (sig === logSig) return;
    const stick = nearBottom(backlogEl);
    backlogEl.replaceChildren();
    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = "各行の Jump でそこから読み返せます · Esc で閉じる";
    backlogEl.appendChild(hint);
    for (const m of rows) {
      const div = document.createElement("div");
      div.className = "bl " + (m.role === "him" ? "him" : "her");
      const jump = document.createElement("button");
      jump.type = "button";
      jump.className = "jump";
      jump.textContent = "Jump";
      jump.title = "この行から読み返す（現在の進行は変わりません）";
      jump.addEventListener("click", () => jumpToLog(m.id));
      div.appendChild(jump);
      // the game puts a ♪ beside a line that has a voice; here every one of
      // hers does, because she can always say it again
      if (m.role === "her") {
        const note = document.createElement("button");
        note.type = "button";
        note.className = "note";
        note.textContent = "\u266a";
        note.title = m.match ? "もう一度きく（" + matchLabel(m.match) + "）" : "もう一度きく";
        note.addEventListener("click", () => speak(m.text, m.id, note));
        div.appendChild(note);
      }
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = m.role === "him" ? "一悟" : "百花";
      // the speaker sits alone on its line and the line itself is quoted, as
      // the game's own log draws every entry
      const line = document.createElement("span");
      line.className = "line";
      line.textContent = "「" + (m.text || "") + "」";
      div.appendChild(who);
      div.appendChild(line);
      // a line the ♪ would play from tape: name the real line, so a near miss
      // is visible in the record and not only in the ear
      if (m.match) {
        const match = document.createElement("span");
        match.className = "match";
        match.textContent = matchLabel(m.match);
        match.title = "録音から再生: 「" + (m.match.matched || "") + "」";
        div.appendChild(match);
      }
      backlogEl.appendChild(div);
    }
    logSig = sig;
    if (stick) backlogEl.scrollTop = backlogEl.scrollHeight;
  } catch (e) { /* the backlog is a convenience; the stage still draws */ }
}

function replayFrame(row) {
  if (row.stage) return row.stage;
  // A player's old line has no character frame of its own. Keep the last
  // preceding character image on stage; clearing it made her disappear as the
  // replay walked between older lines.
  const previous = historyPreview && historyPreview.entries
    .slice(0, historyPreview.index).reverse()
    .find((entry) => entry.role === "her" && entry.stage && entry.stage.sprite);
  const base = (previous && previous.stage) || (historyPreview && historyPreview.current) || currentState || {};
  return {...base, turn: -Number(row.id || 0), turn_id: 0,
    text: row.text || "", speaker: row.role === "him" ? "一悟" : "百花",
    voice: {auto: false}, audio: null, audio_by_turn: {}};
}

function showReplayEntry(entry) {
  if (!historyPreview) return;
  historyPreview.entry = entry;
  const historyLabel = historyIndicatorEl && historyIndicatorEl.querySelector("span");
  if (historyLabel) historyLabel.textContent = entry.stage_source === "inferred"
    ? "履歴を表示中 · 古い行の舞台と表情は推定です"
    : "履歴を表示中 · 現在の進行は変わりません";
  const frame = replayFrame(entry);
  renderScene(frame.scene);
  renderCamera(frame.scene);
  renderBgm(frame.scene);
  renderWeather(frame.scene);
  showTurn(frame, {record: false, play: false});
  replayEntryAudio(entry, frame);
  if (historyChangeEl) historyChangeEl.hidden = !(entry.role === "her" && entry.checkpoint);
  markReady();
}

async function replayEntryAudio(entry, frame) {
  const serial = ++replaySerial;
  audioEl.pause();
  try { audioEl.currentTime = 0; } catch (e) { /* not seekable yet */ }
  if (entry.role !== "her") return;
  let url = turnAudio(frame);
  if (!url) {
    try {
      const r = await fetch("/speak", {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: entry.text, id: entry.id})});
      const got = await r.json();
      if (!r.ok) throw new Error(got.error || "声が見つかりません");
      url = got.url;
    } catch (e) {
      if (serial === replaySerial) setStatus("voice: " + String(e.message || e));
      return;
    }
  }
  if (serial !== replaySerial || !historyPreview || historyPreview.entry !== entry) return;
  replayAudio(url).catch((e) => {
    if (serial === replaySerial) setStatus("voice: " + String(e.message || e));
  });
}

function jumpToLog(id) {
  if (historyPreview) leaveHistory();
  if (composerOpen) closeComposer();
  // Resolve the clicked row by its stable message id. The rendered row and the
  // fetched window can be a moment apart; a positional index would then replay
  // the wrong line (2026-09-18).
  const index = backlogRows.findIndex((m) => m.id === id);
  if (index < 0) return;
  const entries = backlogRows.slice(index);
  if (!entries.length || !currentState) return;
  historyPreview = {current: currentState, pending: [...pending],
    awaiting, extra: [], entries, index: 0, entry: entries[0]};
  closeLog();
  if (historyIndicatorEl) historyIndicatorEl.hidden = false;
  if (autoToggleEl) autoToggleEl.setAttribute("aria-pressed", "false");
  autoAdvance = false;
  showReplayEntry(entries[0]);
}

function bufferWhileReplaying(state) {
  if (!historyPreview || !state || state.streaming) return;
  const preview = historyPreview;
  if (preview.current && state.turn === preview.current.turn) {
    preview.current = state;
    return;
  }
  const at = preview.pending.findIndex((f) => f.turn === state.turn);
  if (at >= 0) { preview.pending[at] = state; return; }
  const later = preview.extra.findIndex((f) => f.turn === state.turn);
  if (later >= 0) preview.extra[later] = state;
  else preview.extra.push(state);
}

function leaveHistory() {
  if (!historyPreview) return;
  replaySerial++;
  audioEl.pause();
  const preview = historyPreview;
  historyPreview = null;
  if (historyIndicatorEl) historyIndicatorEl.hidden = true;
  const extra = preview.extra.sort((a, b) => a.turn - b.turn);
  if (!preview.awaiting && extra.length) {
    showTurn(extra.shift(), {play: false});
    pending = [...extra];
    awaiting = true;
  } else {
    showTurn(preview.current, {play: false});
    pending = [...preview.pending, ...extra];
    awaiting = preview.awaiting;
  }
  const latest = [...pending, currentState].sort((a, b) => a.turn - b.turn).at(-1);
  if (latest) { renderScene(latest.scene); renderCamera(latest.scene); renderBgm(latest.scene); renderWeather(latest.scene); }
  lastAudioUrl = turnAudio(currentState);
  markReady();
}

function setSpeaker(who) {
  // the name element holds the name text then the voice badge span; only the
  // text node is hers to change
  if (nameEl && nameEl.firstChild && nameEl.firstChild.nodeType === 3) {
    nameEl.firstChild.nodeValue = who;
  } else if (nameEl) {
    nameEl.insertBefore(document.createTextNode(who), nameEl.firstChild);
  }
}

function showTurn(state, {record = true, play = true} = {}) {
  if (composerOpen) closeComposer({restoreReply: false});
  currentTurn = state.turn;
  currentState = state;
  currentShownTs = Date.now();
  hisLinePending = false;
  if (!historyPreview) loadLog();
  const isHis = state.speaker === "一悟" || state.speaker === "you";
  if (hudEl) hudEl.classList.toggle("his", isHis);
  if (hudEl) hudEl.classList.remove("streaming");
  if (faceEl) faceEl.style.visibility = isHis ? "hidden" : "";
  if (voiceReplayEl) voiceReplayEl.hidden = isHis;
  setSpeaker(isHis ? "一悟" : "百花");
  textEl.textContent = state.text || "……";
  if (dialogueContentEl) {
    dialogueContentEl.classList.remove("line-in");
    if (effectiveMotion()) {
      void dialogueContentEl.offsetWidth;
      dialogueContentEl.classList.add("line-in");
    }
  }
  moodEl.textContent = state.mood ? "[" + state.mood + "]" : "";
  if (state.face) faceEl.src = state.face;
  if (state.idle) {
    // the channel always sends a boolean; when it does not, reduced motion is
    // the only thing left to decide on
    if (typeof state.idle.motion === "boolean") idleMotion = state.idle.motion;
    idleSway = state.idle.sway === true;
    applyIdle();
  }
  applyFrame(state.sprite);
  // render() owns the live stage. A queued text line contains an older scene;
  // replaying it here briefly switches the background and music on each click.
  renderOverlay(state);
  composeSprite(state.sprite);
  lastFaceKey = faceKey(state);
  const url = turnAudio(state);
  if (play) { preloadAudio(url); playAudio(url); }
  if (record && !historyPreview) {
    const at = viewedFrames.findIndex((f) => f.turn === state.turn);
    if (at >= 0) { viewedFrames[at] = state; viewedIndex = at; }
    else { viewedFrames.push(state); viewedIndex = viewedFrames.length - 1; }
    if (viewedFrames.length > 100) { viewedFrames.shift(); viewedIndex--; }
  }
  if (voiceBadgeEl) voiceBadgeEl.textContent = voiceBadge(state.voice, url);
  if (voiceAutoEl && state.voice && typeof state.voice.auto === "boolean") {
    voiceAutoEl.checked = state.voice.auto;
  }
  if (voiceModeEl && state.voice && state.voice.mode) {
    voiceModeEl.value = state.voice.mode;
  }
  if (state.audio_error) setStatus("voice: " + state.audio_error);
  else setStatus("");
}

// His own line, briefly, in the floating box -- the player's line the way a
// visual novel shows it, from the moment he sends until her reply replaces it.
// Never her speaker and never her face.
function showHisLine(text) {
  const line = String(text || "").trim();
  if (!line) return;
  if (hudEl) hudEl.classList.add("his");
  if (faceEl) faceEl.style.visibility = "hidden";
  setSpeaker("一悟");
  textEl.textContent = line;
  moodEl.textContent = "";
  // notice balloon while his text is on stage
  overlayEl.src = "/asset/emotion/baloon02.png";
  overlayEl.className = "on mark-baloon";
  overlayOn = true;
  placeOverlay();
}

function advance() {
  if (historyPreview) {
    historyPreview.index++;
    if (historyPreview.index < historyPreview.entries.length) {
      showReplayEntry(historyPreview.entries[historyPreview.index]);
      markReady();
    } else leaveHistory();
    return;
  }
  // a line still being voiced is not finished: the click waits rather than
  // showing the next line over silence. The whole reply must be ready, not
  // only the line on screen, or the click lands on a line whose voice is still
  // being made. `markReady` releases after CLIP_WAIT_MS so a render that never
  // comes cannot trap him.
  const capped = (Date.now() - currentShownTs) >= CLIP_WAIT_MS;
  if (currentState && !lineReady(currentState) && !capped) {
    setStatus("声を生成中…");
    markReady();
    return;
  }
  if (pending.length) {
    if (!queuedReady() && !capped) {
      setStatus("声を生成中…");
      markReady();
      return;
    }
    const next = pending.shift();
    showTurn(next);
    if (advanceEl) advanceEl.classList.toggle("on", pending.length > 0);
    markReady();
  } else {
    // The final line stays visible. Its own button opens the reply composer.
    if (advanceEl) advanceEl.classList.remove("on");
    markReady();
  }
}

function stepBack() {
  if (historyPreview) {
    if (historyPreview.index > 0) {
      historyPreview.index--;
      showReplayEntry(historyPreview.entries[historyPreview.index]);
      markReady();
    }
    return;
  }
  if (viewedIndex < 1 || !currentState) return;
  if (!pending.some((f) => f.turn === currentState.turn)) pending.unshift(currentState);
  const prior = viewedFrames[viewedIndex - 1];
  showTurn(prior, {play: false});
  markReady();
}

function render(state) {
  if (!state || state.turn === undefined) return;
  if (state.turn !== currentTurn && typeof state.reply_busy !== "boolean") readerBusy = true;
  if (typeof state.reply_busy === "boolean") readerBusy = state.reply_busy;
  if (historyPreview) { bufferWhileReplaying(state); return; }
  // An offline load restores the visible bubble and the queued remainder.
  // Consume it once: the server still serves this same state on each poll.
  if (!saveResumeUsed && state.resume_view && state.resume_view.current) {
    saveResumeUsed = true;
    pending = Array.isArray(state.resume_view.pending) ? state.resume_view.pending : [];
    awaiting = true;
    showTurn(state.resume_view.current);
    markReady();
    if (state.branch_from && !branchDialogShown) {
      branchDialogShown = true;
      openReplyDialog(Number(state.branch_from));
    }
    return;
  }
  // The stage is global to the reply: the background and the track belong to
  // the stage, not to one bubble, so they are drawn from every frame. A track
  // he picked by hand must start at once, not wait for a click (2026-09-17).
  renderScene(state.scene);
  renderCamera(state.scene);
  renderBgm(state.scene);
  renderWeather(state.scene);
  renderSound(state.scene);
  // the live text while the model is still writing is NOT drawn: putting the
  // whole message up and then replacing it with its first line was the flash
  // he saw. Only finished bubbles are shown, and only once their voice is
  // ready. The flag still lets the first real bubble replace whatever is up.
  if (state.streaming && state.partial) {
    streamingPreview = true;
    if (advanceEl) advanceEl.classList.remove("on");
    return;
  }
  // The model was writing a new reply and the first real bubble is here: it
  // replaces the live preview instead of queueing behind the turn still on
  // screen, so the whole draft does not sit there until a click. The bubbles
  // that follow it queue normally.
  if (streamingPreview) {
    streamingPreview = false;
    pending = [];
    showTurn(state);
    awaiting = true;
    if (advanceEl) advanceEl.classList.remove("on");
    markReady();
    return;
  }
  if (state.turn === currentTurn) {
    // a face, a mood or the sprite can move on the same line (a reaction, a
    // track picked by hand): redraw what moved here, or it waits for a click
    // that would also show a line he has already read. Only when it moved --
    // the poll and a clip arriving carry the same face, and redrawing it would
    // restart the overlay's animation and reload the sprite every four seconds
    const key = faceKey(state);
    if (key !== lastFaceKey) {
      lastFaceKey = key;
      if (state.face && faceEl) faceEl.src = state.face;
      if (moodEl) moodEl.textContent = state.mood ? "[" + state.mood + "]" : "";
      applyFrame(state.sprite);
      renderOverlay(state);
      composeSprite(state.sprite);
    }
    if (state.idle) {
      if (typeof state.idle.motion === "boolean") idleMotion = state.idle.motion;
      idleSway = state.idle.sway === true;
      applyIdle();
    }
    // the frame on screen is refreshed with every update, so the clip that
    // arrives on a later frame is seen by `markReady`
    currentState = state;
    // the voice can arrive after the line it belongs to: the channel publishes
    // the text, then attaches the clip. Play it here, or it never plays.
    const url = turnAudio(state);
    if (url && url !== lastAudioUrl) {
      preloadAudio(url);
      playAudio(url);
      if (voiceBadgeEl) {
        voiceBadgeEl.textContent = voiceBadge(state.voice, url);
        voiceBadgeEl.title = voiceTitle(state.voice);
      }
    }
    markReady();
    // his line, after he sends and before her reply lands
    if (hisLinePending && state.user_text) showHisLine(state.user_text);
    return;
  }
  if (awaiting) {
    // a bubble behind the one on screen: it waits for the click, and its voice
    // is fetched now so advancing does not wait on the network. The channel
    // publishes a bubble's text and then attaches its clip, so the same turn
    // arrives twice; keep the newest frame for a line rather than queueing it
    // twice, or the advance lands on the copy without the clip (2026-09-17).
    const at = pending.findIndex((s) => s.turn === state.turn);
    if (at >= 0) pending[at] = state;
    else pending.push(state);
    preloadAudio(turnAudio(state));
    markReady();
    return;
  }
  showTurn(state);
  awaiting = true;
  if (advanceEl) advanceEl.classList.remove("on");
  markReady();
}

async function poll() {
  try {
    const r = await fetch("/state.json", { cache: "no-store" });
    if (r.ok) render(await r.json());
  } catch (e) {
    setStatus("offline");
  }
}

function stream() {
  if (!window.EventSource) return;
  const es = new EventSource("/events");
  es.onmessage = (ev) => {
    try {
      const state = JSON.parse(ev.data);
      if (!state.ping) render(state);
    } catch (e) { /* a malformed event is dropped; the poll still runs */ }
  };
  es.onerror = () => {
    // EventSource reconnects on its own; the poll covers the gap
  };
}

formEl.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!composerOpen) return;
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.disabled = true;
  sendEl.disabled = true;
  readerBusy = true;
  closeComposer({restoreReply: false});
  setStatus("百花、考え中…");
  // his own line goes into the floating box at once, the way the player's line
  // shows in a visual novel, and stays until her reply replaces it
  hisLinePending = true;
  showHisLine(text);
  try {
    const r = await fetch("/say", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || ("error " + r.status));
    inputEl.value = "";
  } catch (e) {
    setStatus("error: " + e.message);
    hisLinePending = false;
    readerBusy = false;
    awaiting = true;
    composerOpen = true;
    formEl.hidden = false;
    hudEl.classList.add("replying");
  } finally {
    inputEl.disabled = false;
    sendEl.disabled = false;
    if (composerOpen) inputEl.focus();
    markReady();
    // his own line lands in the record as soon as the channel has it, so the
    // backlog shows what he wrote before she has answered
    loadLog();
  }
});

// A click on the stage or the box advances her reply, one line at a time. The
// controls and the input are separate elements above the stage, so a click
// there never advances by accident.
for (const el of [stageEl, hudEl, advanceEl]) {
  if (!el) continue;
  el.addEventListener("click", () => { if (!composerOpen) advance(); });
}

// A tap on the sprite itself, before it can bubble up to the stage and
// advance the line. Only while she is just standing there -- nothing
// pending, no composer, no history replay -- so a touch never eats a line
// he hasn't read yet or fires mid-reply. faceBox (set in renderOverlay) is
// the diff-patch rect in canvas pixels; head/face/shoulder/body are read off
// it top to bottom.
canvas.addEventListener("pointerdown", function (e) {
  if (pending.length > 0 || composerOpen || historyPreview || readerBusy) return;
  if (!faceBox) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
  const cy = (e.clientY - rect.top) * (canvas.height / rect.height);
  let region;
  if (cy < faceBox.y) {
    region = "head";
  } else if (cx >= faceBox.x && cx <= faceBox.x + faceBox.w &&
             cy >= faceBox.y && cy <= faceBox.y + faceBox.h) {
    region = "face";
  } else if (cy < faceBox.y + faceBox.h * 3) {
    region = "shoulder";
  } else {
    region = "body";
  }
  e.stopPropagation();
  fetch("/touch", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({region: region}),
  }).then((r) => r.json()).then((data) => {
    if (data.sound) {
      seEl.pause();
      seEl.src = data.sound;
      seEl.currentTime = 0;
      seEl.volume = Math.min(1, bgmVolume);
      const p = seEl.play();
      if (p && p.catch) p.catch(() => {});
    }
    if (data.voice && audioEl) {
      audioEl.pause();
      audioEl.src = data.voice;
      try { audioEl.currentTime = 0; } catch (e) {}
      audioEl.volume = voiceVolume;
      const p = audioEl.play();
      if (p && p.catch) p.catch(() => {});
    }
  }).catch(() => {});
});

// The click that follows the same pointer-down: swallow it too, so the
// advance() listener on #stage never sees a touch that was already handled.
// Same idle gate as the pointerdown above -- a pending line must still reach
// advance() when he clicks the sprite to read it.
canvas.addEventListener("click", function (e) {
  if (pending.length > 0 || composerOpen || historyPreview || readerBusy || !faceBox) return;
  e.stopPropagation();
});

if (motionEl) {
  motionEl.addEventListener("change", () => {
    remember("vn.idleMotion", motionEl.checked);
    applyIdle();
  });
}
if (swayEl) {
  swayEl.addEventListener("change", () => {
    remember("vn.idleSway", swayEl.checked);
    applyIdle();
  });
}
// The stage's own switches: automatic voice (the runtime asks the voice role
// for a line and speaks it) and the draft guard. Both are held by the channel
// and read by the runtime on its next pass, so a toggle reaches the next turn;
// the stored choice is re-sent on load so a reload keeps them.
if (voiceAutoEl) {
  voiceAutoEl.addEventListener("change", () => {
    remember("vn.voiceAuto", voiceAutoEl.checked);
    postControl({ auto_voice: voiceAutoEl.checked });
  });
}
if (qualityOnEl) {
  qualityOnEl.addEventListener("change", () => {
    remember("vn.quality", qualityOnEl.checked);
    postControl({ quality: qualityOnEl.checked });
  });
}
if (bgmOnEl) {
  bgmOnEl.addEventListener("change", () => {
    remember("vn.bgm", bgmOnEl.checked);
    applyBgm();
  });
}
if (seOnEl) seOnEl.addEventListener("change", () => remember("vn.se", seOnEl.checked));
if (voiceVolEl) {
  voiceVolEl.addEventListener("input", () => {
    voiceVolume = Number(voiceVolEl.value);
    rememberValue("vn.voiceVol", voiceVolume);
    applyVoiceVolume();
  });
}
if (bgmVolEl) {
  bgmVolEl.addEventListener("input", () => {
    bgmVolume = Number(bgmVolEl.value);
    rememberValue("vn.bgmVol", bgmVolume);
    applyBgmVolume();
  });
}
// Where her voice comes from: synthesis only, a recorded line only when it is
// exact, or a recorded near miss too. The choice is kept on the channel, so it
// outlives a restart.
if (voiceModeEl) {
  voiceModeEl.addEventListener("change", () => {
    rememberValue("vn.voiceMode", voiceModeEl.value);
    postControl({ voice_mode: voiceModeEl.value });
  });
}
// The settings and save sheets sit above the stage; the bottom rail keeps the
// common reader actions in the same place as the game's own controls.
if (optionsOpenEl && controlsEl) {
  optionsOpenEl.addEventListener("click", () => {
    const open = controlsEl.classList.toggle("open");
    remember("vn.optionsOpen", open);
    if (open && saveDialogEl) saveDialogEl.hidden = true;
  });
}
if (optionsCloseEl) optionsCloseEl.addEventListener("click", () => controlsEl.classList.remove("open"));
if (fullscreenToggleEl) fullscreenToggleEl.addEventListener("click", async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch (e) { setStatus("全画面: " + e.message); }
});

function openSaveDialog(mode) {
  saveMode = mode;
  if (controlsEl) controlsEl.classList.remove("open");
  if (saveDialogEl) saveDialogEl.hidden = false;
  if (saveTitleEl) saveTitleEl.innerHTML = mode === "save" ? "セーブ <small>Save</small>" : "ロード <small>Load</small>";
  if (saveLeadEl) saveLeadEl.textContent = mode === "save"
    ? "現在の場面と彼女の記録を一緒に保存します。"
    : "保存した場面を選ぶと、その時の彼女の記録へ戻ります。";
  if (saveCreateEl) saveCreateEl.hidden = mode !== "save";
  if (saveTabEl) saveTabEl.classList.toggle("active", mode === "save");
  if (loadTabEl) loadTabEl.classList.toggle("active", mode === "load");
  loadSaves();
}
function closeSaveDialog() { if (saveDialogEl) saveDialogEl.hidden = true; }
if (saveOpenEl) saveOpenEl.addEventListener("click", () => openSaveDialog("save"));
if (loadOpenEl) loadOpenEl.addEventListener("click", () => openSaveDialog("load"));
if (saveCloseEl) saveCloseEl.addEventListener("click", closeSaveDialog);
if (saveTabEl) saveTabEl.addEventListener("click", () => openSaveDialog("save"));
if (loadTabEl) loadTabEl.addEventListener("click", () => openSaveDialog("load"));

async function loadSaves() {
  if (!saveListEl) return;
  try {
    const r = await fetch("/saves", {cache: "no-store"});
    if (!r.ok) throw new Error("一覧を読めません");
    const data = await r.json();
    quickSlotId = data.quick || "";
    saveListEl.replaceChildren();
    for (const slot of (data.saves || [])) {
      const card = document.createElement("div");
      card.className = "save-card";
      const thumb = document.createElement("div");
      thumb.className = "save-thumb";
      if (String(slot.background_url || "").startsWith("/asset/bg/"))
        thumb.style.backgroundImage = `url(${JSON.stringify(slot.background_url)})`;
      if (String(slot.face_url || "").startsWith("/asset/face/")) {
        const face = document.createElement("img");
        face.src = slot.face_url;
        face.alt = "";
        thumb.appendChild(face);
      }
      const stamp = document.createElement("div");
      stamp.className = "save-stamp";
      const when = new Date(slot.created_utc || "");
      stamp.textContent = (isNaN(when.getTime()) ? slot.id : when.toLocaleString("ja-JP"))
        + (slot.id === quickSlotId ? " · QUICK" : "");
      thumb.appendChild(stamp);
      const info = document.createElement("div");
      info.className = "save-info";
      const place = document.createElement("div");
      place.className = "save-place";
      place.textContent = slot.place || slot.scene_id || "場面";
      const line = document.createElement("div");
      line.className = "save-text";
      line.textContent = slot.text || "……";
      const actions = document.createElement("div");
      actions.className = "save-actions";
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "ロード";
      button.addEventListener("click", () => askLoad(slot.id, "save"));
      actions.appendChild(button);
      info.append(place, line, actions);
      card.append(thumb, info);
      saveListEl.appendChild(card);
    }
    if (!(data.saves || []).length) saveListEl.textContent = "保存はまだありません";
  } catch (e) { saveListEl.textContent = String(e.message || e); }
}
async function saveSlot(quick = false) {
  if (!currentState || historyPreview) { setStatus("履歴の表示中は保存できません。現在へ戻ってください。"); return; }
  if (saveCreateEl) saveCreateEl.disabled = true;
  try {
    const stage = {current: currentState, pending};
    const r = await fetch("/saves", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({stage, quick})});
    const got = await r.json();
    if (!r.ok) throw new Error(got.error || "保存できません");
    if (quick) quickSlotId = got.save.id;
    setStatus((quick ? "クイックセーブ: " : "保存しました: ") + got.save.id);
    loadSaves();
  } catch (e) { setStatus("保存: " + String(e.message || e)); }
  finally { if (saveCreateEl) saveCreateEl.disabled = false; }
}
if (saveCreateEl) saveCreateEl.addEventListener("click", () => saveSlot(false));
if (quickSaveEl) quickSaveEl.addEventListener("click", () => saveSlot(true));
if (quickLoadEl) quickLoadEl.addEventListener("click", async () => {
  if (!quickSlotId) await loadSaves();
  if (quickSlotId) askLoad(quickSlotId, "save");
  else setStatus("クイックセーブはまだありません");
});

function askLoad(id, kind) {
  chosenLoadSlot = id;
  chosenLoadKind = kind;
  if (loadConfirmTitleEl) loadConfirmTitleEl.textContent = kind === "line"
    ? "この行から返事を変えますか？" : "この場面へ戻りますか？";
  if (loadConfirmTextEl) loadConfirmTextEl.textContent = kind === "line"
    ? "ここまでの彼女の記録へ戻り、後の会話は復旧用に保存します。再起動後、別の返事を選べます。"
    : "現在の進行は復旧用に保存されます。ロード後、画面を再読み込みします。";
  if (loadConfirmEl) loadConfirmEl.hidden = false;
}
if (loadCancelEl) loadCancelEl.addEventListener("click", () => { loadConfirmEl.hidden = true; });
if (loadAcceptEl) loadAcceptEl.addEventListener("click", async () => {
  if (!chosenLoadSlot) return;
  loadAcceptEl.disabled = true;
  const path = chosenLoadKind === "line" ? "/replay/branch" : "/saves/load";
  const body = chosenLoadKind === "line" ? {checkpoint: chosenLoadSlot} : {slot: chosenLoadSlot};
  try {
    const r = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    const got = await r.json();
    if (!r.ok) throw new Error(got.error || "ロードを始められません");
    loadConfirmEl.hidden = true;
    closeSaveDialog();
    setStatus("ロード中…");
    await waitForLoad(got.request_id);
  } catch (e) { setStatus("ロード: " + String(e.message || e)); }
  finally { loadAcceptEl.disabled = false; }
});
async function waitForLoad(requestId) {
  for (let i = 0; i < 180; i++) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    let got;
    try {
      const r = await fetch("/saves/load-status", {cache: "no-store"});
      if (!r.ok) continue;
      got = await r.json();
    } catch (e) { continue; }
    if (got.request_id !== requestId) continue;
    if (got.phase === "error") throw new Error(got.error || "ロード失敗");
    if (got.phase === "ready") { window.location.reload(); return; }
    setStatus("ロード中: " + got.phase);
  }
  throw new Error("再起動を確認できません。ロード状態を確認してください。");
}

let replyTurnId = 0;
async function openReplyDialog(turnId) {
  replyTurnId = turnId;
  if (replyDialogEl) replyDialogEl.hidden = false;
  if (replyCandidatesEl) replyCandidatesEl.textContent = "返事を読み込み中…";
  try {
    const r = await fetch("/replies/" + encodeURIComponent(turnId), {cache: "no-store"});
    const got = await r.json();
    if (!r.ok) throw new Error(got.error || "返事を読めません");
    renderReplyCandidates(got);
  } catch (e) { if (replyCandidatesEl) replyCandidatesEl.textContent = String(e.message || e); }
}
function renderReplyCandidates(reply) {
  if (!replyCandidatesEl) return;
  replyCandidatesEl.replaceChildren();
  for (const c of (reply.candidates || [])) {
    const row = document.createElement("div");
    row.className = "reply-choice";
    const label = document.createElement("strong");
    label.textContent = `返事 ${c.n}${c.n === reply.sat ? " · 現在" : ""}`;
    const words = document.createElement("p");
    words.textContent = c.text;
    row.append(label, words);
    if (c.n !== reply.sat) {
      const select = document.createElement("button");
      select.type = "button";
      select.textContent = "この返事にする";
      select.addEventListener("click", async () => {
        select.disabled = true;
        try {
          const r = await fetch("/replies/sit", {method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({turn_id: replyTurnId, n: c.n})});
          const got = await r.json();
          if (!r.ok) throw new Error(got.error || "返事を選べません");
          replyDialogEl.hidden = true;
          logSig = null;
          await loadLog();
          await poll();
          setStatus("選んだ返事から続けられます");
        } catch (e) { setStatus("返事: " + String(e.message || e)); }
        finally { select.disabled = false; }
      });
      row.appendChild(select);
    }
    replyCandidatesEl.appendChild(row);
  }
}
if (historyReturnEl) historyReturnEl.addEventListener("click", leaveHistory);
if (historyChangeEl) historyChangeEl.addEventListener("click", () => {
  const entry = historyPreview && historyPreview.entry;
  if (entry && entry.checkpoint) askLoad(entry.checkpoint, "line");
});
async function continueOriginalReply() {
  if (!replyTurnId) return;
  try {
    const r = await fetch("/replies/continue", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({turn_id: replyTurnId})});
    const got = await r.json();
    if (!r.ok) throw new Error(got.error || "再開できません");
    replyDialogEl.hidden = true;
    setStatus("元の返事から続けます");
  } catch (e) { setStatus("返事: " + String(e.message || e)); }
}
if (replyCloseEl) replyCloseEl.addEventListener("click", continueOriginalReply);
if (replyContinueEl) replyContinueEl.addEventListener("click", continueOriginalReply);
if (replyDrawEl) replyDrawEl.addEventListener("click", async () => {
  if (!replyTurnId) return;
  replyDrawEl.disabled = true;
  setStatus("別の返事を描いています…");
  try {
    const r = await fetch("/replies/draw", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({turn_id: replyTurnId})});
    const got = await r.json();
    if (!r.ok) throw new Error(got.error || "返事を作れません");
    renderReplyCandidates(got.reply);
    setStatus("別の返事ができました");
  } catch (e) { setStatus("返事: " + String(e.message || e)); }
  finally { replyDrawEl.disabled = false; }
});
if (voiceReplayEl) voiceReplayEl.addEventListener("click", (ev) => {
  ev.stopPropagation();
  const row = historyPreview && historyPreview.entry;
  const text = row ? row.text : (currentState && currentState.text);
  const id = row ? row.id : undefined;
  if (text) speak(text, id, voiceReplayEl);
});
if (logOpenEl) logOpenEl.addEventListener("click", openLog);
if (backLineEl) backLineEl.addEventListener("click", stepBack);
if (skipReplyEl) skipReplyEl.addEventListener("click", () => {
  if (historyPreview) { leaveHistory(); return; }
  if (pending.length) {
    const last = pending.at(-1);
    pending = [];
    showTurn(last);
    markReady();
  }
});
if (autoToggleEl) autoToggleEl.addEventListener("click", () => {
  autoAdvance = !autoAdvance;
  autoToggleEl.setAttribute("aria-pressed", String(autoAdvance));
});
setInterval(() => {
  if (!autoAdvance || historyPreview || !pending.length || !currentState) return;
  if (audioEl && !audioEl.paused) return;
  if (Date.now() - currentShownTs < 1600) return;
  if (lineReady(currentState) && queuedReady()) advance();
}, 600);
if (directorOpenEl && directorEl) {
  directorOpenEl.addEventListener("click", () => {
    directorEl.hidden = false;
    loadDirector();
  });
}
if (directorCloseEl && directorEl) {
  directorCloseEl.addEventListener("click", () => { directorEl.hidden = true; });
}
if (gaugeOpenEl && gaugePanelEl) {
  gaugeOpenEl.addEventListener("click", () => {
    gaugePanelEl.hidden = false;
    loadGaugeHistory();
  });
}
if (gaugeCloseEl && gaugePanelEl) {
  gaugeCloseEl.addEventListener("click", () => { gaugePanelEl.hidden = true; });
}
if (gaugePanelEl) {
  // a click on the dimmed backdrop closes it; a click on the card itself does not
  gaugePanelEl.addEventListener("click", (e) => {
    if (e.target === gaugePanelEl) gaugePanelEl.hidden = true;
  });
}
if (directorFormEl) {
  directorFormEl.addEventListener("submit", (e) => {
    e.preventDefault();
    sendDirector(directorInputEl ? directorInputEl.value : "");
  });
}
if (scenePickEl) {
  scenePickEl.addEventListener("change", () => {
    const bg = scenePickEl.value;
    if (!bg) return;
    rememberValue("vn.bg", bg);
    requestScene(bg);
  });
}
if (outfitPickEl) {
  outfitPickEl.addEventListener("change", () => {
    rememberValue("vn.outfit", outfitPickEl.value);
    requestOutfit(outfitPickEl.value);
  });
}
if (trackPickEl) {
  trackPickEl.addEventListener("change", () => {
    rememberValue("vn.track", trackPickEl.value);
    requestTrack(trackPickEl.value);
  });
}
if (modelPickEl) {
  modelPickEl.addEventListener("change", () => {
    requestModel(modelPickEl.value);
  });
}
if (stageModelPickEl) {
  stageModelPickEl.addEventListener("change", () => {
    requestStageModel(stageModelPickEl.value);
  });
}

function restoreControls() {
  // the panel he left open comes back open
  if (controlsEl && preference("vn.optionsOpen") === "1") controlsEl.classList.add("open");
  const voice = preference("vn.voiceAuto");
  const quality = preference("vn.quality");
  // the mode, or the boolean it replaced: "1" was the near-miss tier on
  const storedMode = preference("vn.voiceMode");
  const legacyPartial = preference("vn.clipPartial");
  const known = ["tts", "exact", "approximate"];
  let mode = known.indexOf(storedMode) >= 0 ? storedMode : null;
  if (mode === null && legacyPartial !== null) {
    mode = legacyPartial === "1" ? "approximate" : "exact";
  }
  // the music switch is the page's own; the channel holds nothing for it, so it
  // is restored here whether or not the others were ever set
  const bgm = preference("vn.bgm");
  const se = preference("vn.se");
  if (se !== null && seOnEl) seOnEl.checked = se === "1";
  if (bgm !== null && bgmOnEl) {
    bgmOnEl.checked = bgm === "1";
    applyBgm();
  }
  if (mode !== null && voiceModeEl) voiceModeEl.value = mode;
  if (voice === null && quality === null && mode === null) return;
  const payload = {};
  if (voice !== null) {
    payload.auto_voice = voice === "1";
    if (voiceAutoEl) voiceAutoEl.checked = payload.auto_voice;
  }
  if (quality !== null) {
    payload.quality = quality === "1";
    if (qualityOnEl) qualityOnEl.checked = payload.quality;
  }
  if (mode !== null) payload.voice_mode = mode;
  postControl(payload);
}
// The backlog opens the way the game's own history does: the wheel brings it
// up, and Esc or a right click puts it away. It is a sheet over the stage, not
// a panel beside it, so while it is open the wheel belongs to it.
function logOpen() {
  return !!backlogEl && backlogEl.classList.contains("open");
}

function openLog() {
  if (!backlogEl) return;
  backlogEl.classList.add("open");
  loadLog();
  backlogEl.scrollTop = backlogEl.scrollHeight;
}

function closeLog() {
  if (backlogEl) backlogEl.classList.remove("open");
}

// The gauge chart: a plain canvas line plot over /gauge_history, with a
// checkbox legend that toggles which lines draw. Colors are assigned once,
// by the order a gauge name is first seen, so a toggle never repaints the
// gauges that stayed on.
async function loadGaugeHistory() {
  if (!gaugeCanvasEl) return;
  if (gaugeLegendEl) gaugeLegendEl.textContent = "読み込み中…";
  try {
    const r = await fetch("/gauge_history", {cache: "no-store"});
    const data = await r.json();
    gaugeData = Array.isArray(data) ? data : [];
    const seen = new Set(gaugeOrder);
    for (const row of gaugeData) {
      const g = row && row.gauges;
      if (!g) continue;
      for (const key of Object.keys(g)) {
        if (!seen.has(key)) { seen.add(key); gaugeOrder.push(key); }
      }
    }
    if (!Object.keys(gaugeVisible).length) {
      const hasDefaults = gaugeOrder.some((k) => GAUGE_DEFAULT_VISIBLE.has(k));
      for (const key of gaugeOrder) gaugeVisible[key] = hasDefaults ? GAUGE_DEFAULT_VISIBLE.has(key) : true;
    } else {
      for (const key of gaugeOrder) if (!(key in gaugeVisible)) gaugeVisible[key] = false;
    }
    buildGaugeLegend();
    renderGaugeChart();
  } catch (e) {
    if (gaugeLegendEl) gaugeLegendEl.textContent = "読み込めません: " + String(e.message || e);
  }
}

function gaugeColorFor(key) {
  const idx = gaugeOrder.indexOf(key);
  return GAUGE_COLORS[(idx < 0 ? 0 : idx) % GAUGE_COLORS.length];
}

function buildGaugeLegend() {
  if (!gaugeLegendEl) return;
  gaugeLegendEl.replaceChildren();
  if (!gaugeOrder.length) {
    gaugeLegendEl.textContent = "ゲージの記録がありません";
    return;
  }
  for (const key of gaugeOrder) {
    const label = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !!gaugeVisible[key];
    cb.addEventListener("change", () => {
      gaugeVisible[key] = cb.checked;
      renderGaugeChart();
    });
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = gaugeColorFor(key);
    label.append(cb, swatch, document.createTextNode(key));
    gaugeLegendEl.appendChild(label);
  }
}

function renderGaugeChart() {
  if (!gaugeCanvasEl) return;
  const g2 = gaugeCanvasEl.getContext("2d");
  const W = gaugeCanvasEl.width, H = gaugeCanvasEl.height;
  g2.clearRect(0, 0, W, H);
  g2.fillStyle = "#ffffff";
  g2.fillRect(0, 0, W, H);
  const padL = 32, padR = 8, padT = 8, padB = 20;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  g2.lineWidth = 1;
  g2.font = "10px 'Yu Gothic', Meiryo, sans-serif";
  for (let v = 0; v <= 100; v += 25) {
    const y = padT + plotH * (1 - v / 100);
    g2.strokeStyle = v === 0 ? "rgba(59,51,80,.35)" : "rgba(59,51,80,.14)";
    g2.beginPath();
    g2.moveTo(padL, y);
    g2.lineTo(W - padR, y);
    g2.stroke();
    g2.fillStyle = "#6f6590";
    g2.fillText(String(v), 2, y + 3);
  }
  if (!gaugeData.length) {
    g2.fillStyle = "#6f6590";
    g2.fillText("データがありません", padL + 10, padT + plotH / 2);
    return;
  }
  const n = gaugeData.length;
  const xAt = (i) => padL + (n === 1 ? plotW / 2 : (plotW * i) / (n - 1));
  const fmtTs = (ts) => {
    const d = new Date(Number(ts) * 1000);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString("ja-JP", {hour: "2-digit", minute: "2-digit", hour12: false});
  };
  g2.fillStyle = "#6f6590";
  const marks = n === 1 ? [0] : [0, Math.floor((n - 1) / 2), n - 1];
  for (const i of marks) {
    const row = gaugeData[i];
    if (!row) continue;
    const label = fmtTs(row.ts);
    if (!label) continue;
    let x = xAt(i) - 16;
    x = Math.max(padL, Math.min(x, W - padR - 32));
    g2.fillText(label, x, H - 5);
  }
  for (const key of gaugeOrder) {
    if (!gaugeVisible[key]) continue;
    g2.strokeStyle = gaugeColorFor(key);
    g2.lineWidth = 2;
    g2.beginPath();
    let started = false;
    gaugeData.forEach((row, i) => {
      const v = row && row.gauges ? row.gauges[key] : undefined;
      if (v === undefined || v === null || isNaN(Number(v))) return;
      const x = xAt(i);
      const y = padT + plotH * (1 - Math.max(0, Math.min(100, Number(v))) / 100);
      if (!started) { g2.moveTo(x, y); started = true; }
      else g2.lineTo(x, y);
    });
    g2.stroke();
  }
}

window.addEventListener("wheel", (ev) => {
  if (logOpen()) return;      // the sheet is a scroll box; the wheel is its own
  if (ev.deltaY < 0) {
    ev.preventDefault();
    openLog();
  }
}, { passive: false });

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") {
    if (composerOpen) closeComposer();
    closeLog();
    if (controlsEl) controlsEl.classList.remove("open");
  }
});

document.addEventListener("contextmenu", (ev) => {
  if (logOpen()) {
    ev.preventDefault();
    closeLog();
  }
});

if (reduceQuery && reduceQuery.addEventListener) {
  // a change to the system setting only matters while no choice is stored and
  // the channel sent no default
  reduceQuery.addEventListener("change", () => {
    if (preference("vn.idleMotion") === null && idleMotion === null) applyIdle();
  });
}
applyIdle();

restoreControls();
restoreVolumes();
loadScenes();
loadTracks();
loadOutfits();
loadModels();
loadStageModel();
loadLog();
poll();
setInterval(poll, 1000);
stream();
