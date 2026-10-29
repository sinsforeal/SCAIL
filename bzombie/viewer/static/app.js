"use strict";
// B-zombie viewer front end. No build step, no CDN. All state lives in the URL query.
const $ = (s) => document.querySelector(s);
const VIEWS = [["runs", "Runs"], ["conv", "Conversation"], ["side", "Side by side"], ["judge", "Judged results"], ["stats", "Raw stats"], ["vote", "Blind vote"]];
let Q = new URLSearchParams(location.search);
let OPTS = {arm: [], character: [], model: [], status: [], days: [], branches: []};
let RUNS = [];
let lastSig = {};
let selOutput = null;
let tracePanelSig = "";

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}
const get = (k, d = "") => Q.get(k) || d;
function setQ(obj, push = true) {
  for (const [k, v] of Object.entries(obj)) { if (v === "" || v === null || v === undefined) Q.delete(k); else Q.set(k, v); }
  history[push ? "pushState" : "replaceState"](null, "", "?" + Q.toString());
}
async function api(path) {
  const r = await fetch("/api/" + path, {cache: "no-store"});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
const fmt = {
  usd: (x) => x == null ? "-" : "$" + Number(x).toFixed(x < 1 ? 4 : 2),
  n: (x) => x == null ? "-" : Number(x).toLocaleString(),
  f: (x, d = 2) => x == null ? "-" : Number(x).toFixed(d),
  pct: (x) => x == null ? "-" : (x * 100).toFixed(1) + "%",
  vt: (ts) => ts ? String(ts).slice(5, 16).replace("T", " ") : "-",
};
function longText(text, limit = 300, label) {
  text = text == null ? "" : String(text);
  if (text.length <= limit) return h("pre", {}, text);
  return h("details", {}, h("summary", {}, (label ? label + " " : "") + text.slice(0, 100).replace(/\s+/g, " ") + "... (" + text.length + " chars)"), h("pre", {}, text));
}
function pre(o) { return h("pre", {}, typeof o === "string" ? o : JSON.stringify(o, null, 1)); }
function statusCls(s) { return "pill " + (s || ""); }

// ---------- filters ----------
function sel(name, label, values, extra) {
  const s = h("select", {onchange: () => { setQ({[name]: s.value}); go(true); }}, h("option", {value: ""}, "any " + label), values.map((v) => h("option", {value: v, selected: get(name) === String(v)}, v)));
  return h("label", {}, label + " ", s);
}
const devOn = () => get("dev") === "1";
function passes(r) {
  if (r.dev && !devOn()) return false;
  if (get("arm") && r.arm !== get("arm")) return false;
  if (get("char") && r.character !== get("char")) return false;
  if (get("model") && r.model !== get("model")) return false;
  const b = get("branch");
  if (b === "none" && r.branch_id) return false;
  if (b && b !== "none" && r.branch_id !== b) return false;
  return true;
}
function renderFilters(view) {
  const f = $("#filters");
  f.replaceChildren();
  if (!["runs", "conv", "side", "stats"].includes(view)) return;
  f.append(sel("arm", "arm", OPTS.arm), sel("char", "character", OPTS.character), sel("model", "model", OPTS.model),
    sel("branch", "branch", ["none", ...OPTS.branches]));
  if (["conv", "side"].includes(view)) {
    f.append(sel("day", "day", OPTS.days));
    const c = h("input", {type: "checkbox", checked: get("env", "1") !== "0", onchange: () => { setQ({env: c.checked ? "" : "0"}); go(true); }});
    f.append(h("label", {}, c, " environment events"));
  }
  const dv = h("input", {type: "checkbox", checked: devOn(), onchange: () => { setQ({dev: dv.checked ? "1" : ""}); go(true); }});
  f.append(h("label", {}, dv, " show dev runs"));
  f.append(h("a", {href: "?view=" + view, class: "dim", onclick: (e) => { e.preventDefault(); for (const k of ["arm", "char", "model", "branch", "day", "env"]) Q.delete(k); history.pushState(null, "", "?" + Q.toString()); go(true); }}, "reset"));
}
// ---------- run list (always visible, one click) ----------
const cap = (s) => s ? s[0].toUpperCase() + s.slice(1) : "?";
const mmdd = (ts) => { if (!ts) return "-"; const d = new Date(ts * 1000); return String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); };
const badge = (s) => h("span", {class: "badge " + (s || "")}, s || "?");
const cannedBadge = (r) => r && r.canned ? h("span", {class: "badge canned", title: "canned content, not a real model reply"}, r.canned) : null;
const runLabel = (r) => `${r.arm || "?"} · ${cap(r.character)} · ${r.sim_days ?? "?"}-day ${r.kind || ""} · ${mmdd(r.start_ts)}` + (r.branch_id ? " ~ " + r.branch_id : "");
function groupedRuns(extra) {
  let rows = RUNS.filter((r) => passes(r) || (extra && extra.includes(r.ref)));
  rows = rows.slice().sort((a, b) => (b.start_ts || 0) - (a.start_ts || 0));
  const g = new Map();
  for (const r of rows) {
    const key = r.dev ? "Dev runs" : cap(r.character) + " · " + (r.arm || "?");
    if (!g.has(key)) g.set(key, {key, dev: !!r.dev, c: r.character || "", a: r.arm || "", rows: []});
    g.get(key).rows.push(r);
  }
  return [...g.values()].sort((x, y) => (x.dev - y.dev) || x.c.localeCompare(y.c) || (y.a.localeCompare(x.a)));
}
const flatRuns = () => groupedRuns([get("run"), get("a"), get("b")]).flatMap((x) => x.rows);
function defaultRun() {
  const pick = (a) => a.slice().sort((x, y) => (y.start_ts || 0) - (x.start_ts || 0))[0];
  const real = RUNS.filter((r) => !r.dev && !r.branch_id);
  return (pick(real) || pick(RUNS) || {}).ref || "";
}
function pickRun(slot, ref) {
  if (slot === "run") { selOutput = null; Q.delete("output"); }
  setQ({[slot]: ref}); go(true);
}
function runList(mode) {
  const cur = get("run"), A = get("a"), B = get("b");
  const wrap = h("details", {class: "runs"}, h("summary", {}, "Runs (" + RUNS.filter(passes).length + ")"));
  if (window.innerWidth > 820) wrap.open = true;
  const dv = h("input", {type: "checkbox", checked: devOn(), onchange: () => { setQ({dev: dv.checked ? "1" : ""}); go(true); }});
  wrap.append(h("div", {class: "small dim"}, h("label", {}, dv, " show dev runs")),
    h("div", {class: "small dim"}, mode === "side" ? "click = A, shift-click = B, j/k or arrows move A (shift: B)" : "click, or j/k and up/down, to switch run"));
  for (const gr of groupedRuns([cur, A, B])) {
    wrap.append(h("div", {class: "rgroup"}, gr.key));
    for (const r of gr.rows) {
      const isA = mode === "side" ? r.ref === A : r.ref === cur, isB = mode === "side" && r.ref === B;
      const row = h("div", {class: "rrow" + (isA ? " sel" : "") + (isB ? " selb" : ""), title: r.run_id + " | " + r.status + (r.canned ? " | " + r.canned : ""), "data-ref": r.ref,
        onclick: (e) => { if (mode === "side") pickRun(e.shiftKey ? "b" : "a", r.ref); else pickRun("run", r.ref); }},
        h("div", {}, (mode === "side" && (isA || isB)) ? h("b", {}, (isA ? "A " : "") + (isB ? "B " : "")) : null, runLabel(r)),
        h("div", {}, badge(r.status), " ", cannedBadge(r), " ", h("span", {class: "id"}, r.run_id)));
      wrap.append(row);
    }
  }
  return wrap;
}
document.addEventListener("keydown", (e) => {
  const view = get("view", "runs");
  if (!["conv", "side"].includes(view) || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
  const dir = (e.key === "j" || e.key === "ArrowDown") ? 1 : (e.key === "k" || e.key === "ArrowUp") ? -1 : 0;
  if (!dir) return;
  const slot = view === "conv" ? "run" : (e.shiftKey ? "b" : "a");
  const list = flatRuns();
  if (!list.length) return;
  const i = list.findIndex((r) => r.ref === get(slot));
  const n = list[Math.min(list.length - 1, Math.max(0, i < 0 ? 0 : i + dir))];
  e.preventDefault();
  if (n && n.ref !== get(slot)) pickRun(slot, n.ref);
});
const runName =(r) => `${r.arm || "?"} ${r.character || "?"} ${r.model || "?"}${r.branch_id ? " [" + r.branch_id + "]" : ""} (${r.run_id})`;

// ---------- runs ----------
function viewRuns(main) {
  const rows = RUNS.filter(passes);
  if (!RUNS.length) return main.replaceChildren(h("div", {class: "empty"}, "no runs yet. This page fills in on its own when the harness writes the first run."));
  if (!rows.length) return main.replaceChildren(h("div", {class: "empty"}, "no runs match these options" + (devOn() ? "" : " (dev runs are hidden, tick show dev runs)")));
  const t = h("table", {}, h("thead", {}, h("tr", {}, ["Run", "Arm", "Character", "Model", "Status", "Virtual clock", "Day", "Msgs (him/her)", "Calls", "Spend", "Cap", "Errors"].map((x) => h("th", {}, x)))),
    h("tbody", {}, rows.map((r) => h("tr", {class: "click", onclick: () => { setQ({view: "conv", run: r.ref}); go(true); }},
      h("td", {}, r.run_id, r.branch_id ? h("span", {class: "dim"}, " ~ " + r.branch_id) : null), h("td", {}, r.arm), h("td", {}, r.character, " ", h("span", {class: "dim"}, r.lang)), h("td", {}, r.model),
      h("td", {}, badge(r.status), " ", cannedBadge(r)),
      h("td", {}, fmt.vt(r.virtual_ts)), h("td", {class: "num"}, r.sim_day ?? "-", r.sim_days ? "/" + r.sim_days : ""),
      h("td", {class: "num"}, `${r.messages} (${r.him}/${r.her})`), h("td", {class: "num"}, fmt.n(r.calls)),
      h("td", {class: "num"}, fmt.usd(r.cost_usd)), h("td", {class: "num"}, r.cap_usd != null ? "$" + r.cap_usd : "-"),
      h("td", {class: "num " + (r.errors ? "bad" : "")}, r.errors)))));
  const nDev = devOn() ? 0 : RUNS.filter((r) => r.dev).length;
  main.replaceChildren(t, h("p", {class: "dim small"}, "Click a run to read it. " + (nDev ? nDev + " dev run(s) hidden (tick show dev runs). " : "") + "Data: " + (window.__root || "")));
}

// ---------- conversation ----------
function lineEl(x, ref, withTrace = true) {
  const who = x.who;
  const e = h("div", {class: "line " + who + (x.output_id && x.output_id === selOutput ? " sel" : ""), "data-oid": x.output_id || ""},
    h("span", {class: "t"}, "D" + (x.sim_day ?? "?") + " " + fmt.vt(x.virtual_ts).slice(6)),
    h("span", {class: "w"}, who === "him" ? "HIM" : who === "her" ? "HER" : "ENV"),
    h("span", {class: "x"}, x.text || "", who !== "him" && x.kind ? h("span", {class: "dim small"}, "  [" + x.kind + "]") : null,
      who !== "env" && (RUNS.find((r) => r.ref === ref) || {}).canned ? h("span", {class: "canned", title: "canned test content"}, "canned") : null));
  if (who === "her" && x.output_id && withTrace) e.addEventListener("click", () => { selOutput = x.output_id; tracePanelSig = ""; setQ({output: x.output_id}, false); document.querySelectorAll(".line.sel").forEach((n) => n.classList.remove("sel")); e.classList.add("sel"); loadTrace(ref, x.output_id); });
  return e;
}
function dayFilter(lines) {
  const d = get("day");
  const env = get("env", "1") !== "0";
  return lines.filter((x) => (!d || String(x.sim_day) === d) && (env || x.who !== "env"));
}
async function viewConv(main) {
  let ref = get("run");
  if (!ref && RUNS.length) { ref = defaultRun(); setQ({run: ref}, false); }
  const wrapSplit = (...c) => h("div", {class: "split"}, runList("conv"), h("section", {}, ...c));
  if (!ref) return main.replaceChildren(wrapSplit(h("div", {class: "empty"}, "no runs yet")));
  let d;
  try { d = await api("transcript?run=" + encodeURIComponent(ref)); } catch (e) { return main.replaceChildren(wrapSplit(h("div", {class: "empty"}, "run not found: " + ref))); }
  const sig = JSON.stringify(d) + get("day") + get("env") + ref + get("dev") + JSON.stringify(RUNS.map((r) => [r.ref, r.status, r.canned, r.dev]));
  if (sig === lastSig.conv && main.firstChild) return;
  lastSig.conv = sig;
  const sc = window.scrollY;
  const oldRuns = main.querySelector(".runs"), rsc = oldRuns ? oldRuns.scrollTop : 0;
  const lines = dayFilter(d.lines);
  const list = h("div", {class: "pane"});
  let day = null;
  for (const x of lines) {
    if (x.sim_day !== day) { day = x.sim_day; list.append(h("div", {class: "day"}, "Simulated day " + (day ?? "?"))); }
    list.append(lineEl(x, ref));
  }
  if (!lines.length) list.append(h("div", {class: "empty"}, "no lines yet"));
  const r = d.run;
  const perDay = r.days_done ? ` | per sim day (${r.days_done}): ${fmt.f(r.calls_per_day, 1)} calls, ${fmt.usd(r.cost_per_day_usd)}` : "";
  const head = h("div", {class: "pane", style: "margin-bottom:8px"}, h("b", {}, runLabel(r)), " ", badge(r.status), " ", cannedBadge(r),
    h("div", {class: "dim small"}, `${r.run_id} | ${r.model || "?"} | clock ${fmt.vt(r.virtual_ts)} | ${fmt.n(r.calls)} calls, ${fmt.usd(r.cost_usd)}${perDay}`),
    r.canned ? h("div", {class: "bad small"}, r.canned === "DUMMY" ? "DUMMY run: her lines are canned test text, not a real model." : "STUB run: no real model calls behind these lines.") : null);
  const panel = h("div", {class: "pane sticky", id: "trace"}, h("div", {class: "dim"}, "Click one of her lines to see what led to it."));
  main.replaceChildren(wrapSplit(head, h("div", {class: "conv"}, list, panel)));
  const nr = main.querySelector(".runs"); if (nr) nr.scrollTop = rsc;
  window.scrollTo(0, sc);
  const o = selOutput || get("output");
  if (o) { selOutput = o; loadTrace(ref, o); }
}
async function loadTrace(ref, oid) {
  const p = $("#trace"); if (!p) return;
  let t;
  try { t = await api(`trace?run=${encodeURIComponent(ref)}&output=${encodeURIComponent(oid)}`); }
  catch (e) { p.replaceChildren(h("div", {class: "dim"}, "no trace for " + oid + " yet (" + e.message + ")")); return; }
  const sig = JSON.stringify(t);
  if (sig === tracePanelSig) return;
  const open = new Set([...p.querySelectorAll("details[open]")].map((d) => d.dataset.k));
  tracePanelSig = sig;
  const kids = [h("h2", {}, "Trace ", h("span", {class: "dim small"}, oid)), h("div", {class: "line her"}, h("span", {class: "t"}, fmt.vt(t.virtual_ts)), h("span", {class: "x"}, t.text || ""))];
  kids.push(h("h3", {}, "Inputs by kind"));
  const byKind = {};
  for (const i of t.inputs || []) (byKind[i.kind || "other"] = byKind[i.kind || "other"] || []).push(i);
  for (const [k, arr] of Object.entries(byKind)) {
    kids.push(h("div", {}, h("span", {class: "kind"}, k), h("span", {class: "dim small"}, arr.length + " piece(s)")));
    for (const i of arr) kids.push(h("div", {}, h("span", {class: "dim small"}, "source " + (i.source ?? "-")), longText(i.text, 240)));
  }
  kids.push(h("h3", {}, "Causal block"), causalEl(t));
  if (t.state_at_output) kids.push(h("details", {}, h("summary", {}, "State at output"), pre(t.state_at_output)));
  kids.push(h("h3", {}, "Calls (" + (t.calls || []).length + ")"));
  for (const c of t.calls || []) {
    const cid = typeof c === "string" ? c : c.call_id;
    const m = (t.call_meta || {})[cid] || {};
    const d = h("details", {"data-k": cid}, h("summary", {}, `${c.role || c.phase || "call"} ${cid === t.final_call_id ? "(final) " : ""}| ${fmt.f(m.latency_s)} s | ${fmt.usd((m.cost_micro || 0) / 1e6)} | ${fmt.n(m.prompt_tokens)}+${fmt.n(m.completion_tokens)} tok | ${m.model || ""}${m.error ? " ERROR" : ""}`));
    d.addEventListener("toggle", () => { if (d.open && !d.dataset.loaded) loadCall(d, ref, cid); });
    if (open.has(cid)) d.open = true;
    kids.push(d);
  }
  p.replaceChildren(...kids);
}
function causalEl(t) {
  const c = t.causal;
  if (!c || !Object.keys(c).length) return h("div", {class: "dim"}, "no causal block in this trace");
  const out = [];
  if (Array.isArray(c.admitted)) {
    out.push(h("table", {}, h("thead", {}, h("tr", {}, ["Admitted attention line", "Weight", "Constant"].map((x) => h("th", {}, x)))),
      h("tbody", {}, c.admitted.map((a) => h("tr", {}, h("td", {}, a.text), h("td", {class: "num"}, a.weight), h("td", {}, a.constant ? "yes" : ""))))));
  }
  const rest = Object.assign({}, c); delete rest.admitted;
  out.push(pre(rest));
  return h("div", {}, out);
}
async function loadCall(d, ref, cid) {
  d.dataset.loaded = "1";
  const box = h("div", {}, "loading...");
  d.append(box);
  try {
    const c = await api(`call?run=${encodeURIComponent(ref)}&call=${encodeURIComponent(cid)}`);
    const kids = [h("div", {class: "dim small"}, `${c.call_id} | wall ${c.wall_ts} | virtual ${c.virtual_ts} | ${c.model}`)];
    kids.push(h("b", {}, "Prompt"));
    const req = c.request || {};
    for (const m of req.messages || []) kids.push(h("div", {}, h("span", {class: "kind"}, m.role), longText(typeof m.content === "string" ? m.content : JSON.stringify(m.content, null, 1), 200)));
    const extra = Object.assign({}, req); delete extra.messages;
    if (Object.keys(extra).length) kids.push(h("details", {}, h("summary", {}, "Request parameters"), pre(extra)));
    kids.push(h("b", {}, "Response"));
    const resp = c.response || {};
    const ch = (resp.choices || [])[0] || {};
    const msg = ch.message || {};
    if (msg.reasoning || msg.reasoning_content) kids.push(h("div", {}, h("span", {class: "kind"}, "reasoning"), longText(msg.reasoning || msg.reasoning_content, 200)));
    if (msg.content != null) kids.push(h("div", {}, h("span", {class: "kind"}, "content"), longText(msg.content, 2000)));
    kids.push(h("details", {}, h("summary", {}, "Full response, usage, error"), pre({response: resp, usage: c.usage, cost_micro: c.cost_micro, latency_s: c.latency_s, error: c.error})));
    box.replaceChildren(...kids);
  } catch (e) { box.textContent = "call not available: " + e.message; }
}

// ---------- side by side ----------
async function viewSide(main) {
  const a = get("a"), b = get("b");
  const wrapSplit = (...c) => h("div", {class: "split"}, runList("side"), h("section", {}, ...c));
  if (!a || !b) return main.replaceChildren(wrapSplit(h("div", {class: "empty"}, RUNS.length ? "click a run for A, shift-click another for B" : "no runs yet")));
  let d;
  try { d = await api(`compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}&env=${get("env", "1")}`); } catch (e) { return main.replaceChildren(wrapSplit(h("div", {class: "empty"}, "run not found"))); }
  const sig = JSON.stringify(d) + get("day") + a + b + get("dev") + JSON.stringify(RUNS.map((r) => [r.ref, r.status, r.canned, r.dev]));
  if (sig === lastSig.side && main.firstChild) return;
  lastSig.side = sig;
  const oldRuns = main.querySelector(".runs"), rsc = oldRuns ? oldRuns.scrollTop : 0;
  const dayF = get("day");
  const head = h("div", {class: "cols"}, ...["a", "b"].map((k) => {
    const r = d[k], s = d.stats[k];
    return h("div", {class: "pane"}, h("b", {}, (k === "a" ? "A " : "B ") + runLabel(r)), " ", badge(r.status), " ", cannedBadge(r), h("div", {class: "dim small"}, `${r.run_id} | clock ${fmt.vt(r.virtual_ts)} | ${fmt.n(r.calls)} calls | ${fmt.usd(r.cost_usd)}${r.days_done ? " (" + fmt.f(r.calls_per_day, 1) + " calls, " + fmt.usd(r.cost_per_day_usd) + " per sim day)" : ""} | replies ${s.replies} unprompted ${s.unprompted} | mean len ${fmt.f(s.reply_len.mean, 1)}`));
  }));
  const body = h("div", {});
  let lastDay = "x";
  for (const row of d.rows) {
    if (dayF && String(row.day) !== dayF) continue;
    if (row.day !== lastDay) { lastDay = row.day; body.append(h("div", {class: "day"}, "Simulated day " + (row.day ?? "?"))); }
    body.append(h("div", {class: "rowhdr"}, "hour " + (row.hour == null ? "?" : String(row.hour).padStart(2, "0") + ":00")));
    body.append(h("div", {class: "cols"}, ...["a", "b"].map((k) => h("div", {}, row[k].map((x) => lineEl(x, k === "a" ? a : b, false))))));
  }
  const sc = window.scrollY;
  main.replaceChildren(wrapSplit(head, body));
  const nr = main.querySelector(".runs"); if (nr) nr.scrollTop = rsc;
  window.scrollTo(0, sc);
}

// ---------- judged ----------
const vtag = (v) => h("span", {class: "pill"}, v);
async function viewJudge(main) {
  const d = await api("judge");
  const sig = JSON.stringify(d);
  if (sig === lastSig.judge && main.firstChild) return;
  lastSig.judge = sig;
  const open = new Set([...main.querySelectorAll("details[open]")].map((x) => x.dataset.k));
  const kids = [h("h2", {}, "Calibration")];
  if (!(d.calibrations || []).length) kids.push(h("div", {class: "dim"}, "no calibration runs yet"));
  (d.calibrations || []).forEach((c, ci) => {
    const allOk = c.of > 0 && c.calibrated === c.of;
    const crits = [...new Set(c.rows.map((x) => x.criterion))];
    const cellFor = (crit, lang) => {
      const x = c.rows.find((y) => y.criterion === crit && y.lang === lang);
      if (!x) return h("td", {}, "-");
      return h("td", {}, h("span", {class: x.calibrated ? "ok" : "bad"}, x.calibrated ? "calibrated" : "NOT calibrated"),
        h("div", {class: "dim small"}, `planted ${x.planted ?? "-"}, caught ${x.caught ?? "-"}, controls ${x.controls_passed ?? "-"}/${x.controls ?? "-"}`),
        h("div", {class: "small"}, x.entries.map((e) => h("span", {class: e.caught === true ? "ok" : e.caught === false ? "bad" : "dim", title: e.id}, (e.caught === true ? "caught " : e.caught === false ? "MISSED " : "? ") + e.id.split(".").slice(-1)[0] + "  "))));
    };
    const box = h("div", {class: "pane", style: "margin-bottom:12px"},
      h("h3", {}, c.stamp, " ", h("span", {class: allOk ? "ok" : "bad"}, `${c.calibrated} of ${c.of} criterion/language pairs calibrated`)),
      h("div", {class: "dim"}, `${c.model || "?"} | ${c.entries ?? "?"} entries | ${c.calls ?? "?"} calls | cost ${c.cost_usd == null ? "-" : fmt.usd(c.cost_usd)}` + (c.uncalibrated.length ? " | uncalibrated: " + c.uncalibrated.join(", ") : "")));
    const det = h("details", {"data-k": "cal" + c.stamp}, h("summary", {}, "per criterion and language"),
      h("table", {}, h("thead", {}, h("tr", {}, ["Criterion", "ja", "en"].map((x) => h("th", {}, x)))),
        h("tbody", {}, crits.map((crit) => h("tr", {}, h("td", {}, crit), cellFor(crit, "ja"), cellFor(crit, "en"))))));
    if (ci === 0) det.open = true;
    box.append(det);
    kids.push(box);
  });
  kids.push(h("h2", {}, "Judged results"));
  if (!d.matches.length) kids.push(h("div", {class: "empty"}, "no judged results yet"));
  for (const m of d.matches) {
    const lm = m.label_map;
    const ag = m.agreement;
    const box = h("div", {class: "pane", style: "margin-bottom:12px"},
      h("h3", {}, m.match_id, " ", h("span", {class: "dim"}, m.character || "")),
      h("div", {class: "dim"}, lm ? `Revealed: A = ${lm.A}, B = ${lm.B}` : "Labels not revealed yet"),
      h("div", {}, `Agreement between the two passes: ${ag.agreed} of ${ag.of} (${fmt.pct(ag.rate)}). Agreed verdicts: A ${m.tally_agreed.A}, B ${m.tally_agreed.B}, tie ${m.tally_agreed.tie}. Mean score A ${fmt.f(m.mean_scores.A)} / B ${fmt.f(m.mean_scores.B)}.`),
      m.summary ? h("div", {}, h("b", {}, "Summary "), typeof m.summary === "string" ? m.summary : pre(m.summary)) : null);
    for (const c of m.criteria) {
      const det = h("details", {"data-k": m.match_id + c.id}, h("summary", {}, `${c.name || c.id}: `, c.passes.map((p) => `pass ${p.pass} ${p.verdict} (${p.scores ? p.scores.A + "/" + p.scores.B : "-"})`).join(" | "), "  ",
        h("span", {class: c.agree ? "ok" : c.agree === false ? "bad" : "dim"}, c.agree ? "agree" : c.agree === false ? "DISAGREE" : "single pass")));
      if (open.has(m.match_id + c.id)) det.open = true;
      for (const p of c.passes) {
        det.append(h("div", {class: "pane", style: "margin:4px 0"}, h("b", {}, `Pass ${p.pass}: ${p.verdict}`), h("div", {}, p.reason),
          h("div", {class: "cols"}, ["A", "B"].map((k) => h("div", {}, h("span", {class: "kind"}, k + " score " + (p.scores ? p.scores[k] : "-")), ((p.quotes || {})[k] || []).map((q) => h("pre", {}, q)))))));
      }
      box.append(det);
    }
    box.append(h("h3", {}, "Calibration: " + m.calibration_caught.caught + " of " + m.calibration_caught.of + " planted defects caught"));
    for (const x of m.calibration) box.append(h("div", {}, h("span", {class: x.caught ? "ok" : "bad"}, x.caught ? "caught " : "MISSED "), x.defect));
    kids.push(box);
  }
  const mc = d.modelcheck;
  kids.push(h("h2", {}, "Model check"));
  if (!mc) kids.push(h("div", {class: "dim"}, "no model check files yet"));
  else {
    const v = mc.view || {};
    kids.push(h("div", {class: "dim"}, `run ${v.run_id || "?"}, judge ${v.judge || "?"}, ${v.pass_count || 0} passes, winner agreement across passes: ${v.agreement ?? "?"}`));
    const sm = v.summary || {};
    const models = Object.keys(sm);
    if (models.length) {
      const cell = (o) => o ? `${fmt.f(o.kino)} / ${fmt.f(o.natural)} / ${fmt.f(o.rank)}` : "-";
      kids.push(h("h3", {}, "Summary per model (kino / natural / rank, rank lower is better)"),
        h("table", {}, h("thead", {}, h("tr", {}, ["Model", "All", "Momoka", "Tomoe", "First places", "Flags"].map((x) => h("th", {}, x)))),
          h("tbody", {}, models.map((m) => h("tr", {}, h("td", {}, m), h("td", {class: "num"}, cell(sm[m].all)), h("td", {class: "num"}, cell(sm[m].momoka)), h("td", {class: "num"}, cell(sm[m].tomoe)),
            h("td", {class: "num"}, sm[m].first_places ?? "-"), h("td", {}, Object.entries(sm[m].flags || {}).map(([k, n]) => `${k} ${n}`).join(", ") || "-"))))));
    }
    for (const m of v.moments || []) {
      const det = h("details", {"data-k": "mcm" + m.id}, h("summary", {}, `${m.id} ${m.character || "?"}: ${m.situation || ""}`));
      det.append(h("div", {class: "pane"}, h("div", {class: "dim"}, "mood: " + (m.mood || "-")),
        (m.chat || []).map((c) => h("div", {}, h("b", {}, c[0] + ": "), c[1])), h("div", {}, h("b", {}, "newest: "), m.newest || "-")));
      det.append(h("table", {}, h("thead", {}, h("tr", {}, ["Label", "Model", "Text", "Pass scores (kino/natural, rank, flags)", "Cost"].map((x) => h("th", {}, x)))),
        h("tbody", {}, (m.samples || []).map((s) => h("tr", {}, h("td", {}, s.label), h("td", {}, s.model || "?"), h("td", {}, h("pre", {}, s.text || "")),
          h("td", {}, (s.passes || []).map((p) => h("div", {}, `p${p.pass}: ${p.kino ?? "-"}/${p.natural ?? "-"}, rank ${p.rank ?? "-"}` + ((p.flags || []).length ? ", " + p.flags.join(", ") : "")))),
          h("td", {class: "num"}, s.cost_usd == null ? "-" : fmt.usd(s.cost_usd) + (s.finish_reason && s.finish_reason !== "stop" ? " " + s.finish_reason : "")))))));
      kids.push(det);
    }
    kids.push(h("details", {"data-k": "mcraw"}, h("summary", {}, "raw JSON"), ["samples", "key", "judgments"].map((k) => h("details", {"data-k": "mc" + k}, h("summary", {}, k), pre(mc[k])))));
  }
  main.replaceChildren(...kids);
  main.querySelectorAll("details").forEach((x) => { if (open.has(x.dataset.k)) x.open = true; });
}

// ---------- stats ----------
function card(l, v, sub) { return h("div", {class: "card"}, h("div", {class: "l"}, l), h("div", {class: "v"}, v), sub ? h("div", {class: "dim small"}, sub) : null); }
async function viewStats(main) {
  const rows = RUNS.filter(passes);
  if (!rows.length) return main.replaceChildren(h("div", {class: "empty"}, RUNS.length ? "no runs match these options" : "no runs yet"));
  const stats = await Promise.all(rows.map((r) => api("stats?run=" + encodeURIComponent(r.ref)).catch(() => null)));
  const sig = JSON.stringify(stats) + rows.length;
  if (sig === lastSig.stats && main.firstChild) return;
  lastSig.stats = sig;
  const cmp = h("table", {}, h("thead", {}, h("tr", {}, ["Run", "Calls", "Prompt tok", "Compl tok", "Cost", "Lat mean / p95 s", "Calls per reply", "Replies", "Unprompted", "Reply len mean / p90", "Repetition", "Language purity", "Causal share", "Constant lines"].map((x) => h("th", {}, x)))),
    h("tbody", {}, rows.map((r, i) => { const s = stats[i]; if (!s) return null; return h("tr", {},
      h("td", {}, runName(r)), h("td", {class: "num"}, fmt.n(s.calls)), h("td", {class: "num"}, fmt.n(s.prompt_tokens)), h("td", {class: "num"}, fmt.n(s.completion_tokens)), h("td", {class: "num"}, fmt.usd(s.cost_usd)),
      h("td", {class: "num"}, fmt.f(s.latency.mean) + " / " + fmt.f(s.latency.p95)), h("td", {class: "num"}, fmt.f(s.calls_per_reply)), h("td", {class: "num"}, s.replies), h("td", {class: "num"}, s.unprompted),
      h("td", {class: "num"}, fmt.f(s.reply_len.mean, 1) + " / " + fmt.f(s.reply_len.p90, 0)), h("td", {class: "num"}, fmt.pct(s.repetition_rate)), h("td", {class: "num"}, fmt.pct(s.language_purity)),
      h("td", {class: "num"}, fmt.pct(s.causal.causal_share)), h("td", {class: "num"}, fmt.pct(s.causal.constant_line_share))); })));
  const kids = [h("h2", {}, "Raw stats"), cmp];
  rows.forEach((r, i) => {
    const s = stats[i]; if (!s) return;
    const maxc = Math.max(...s.cost_per_day.map((d) => d.cost_usd), 1e-9);
    const maxh = Math.max(...s.reply_len.hist.map((d) => d.n), 1);
    kids.push(h("h3", {}, runName(r)),
      h("div", {class: "grid"}, card("Calls", fmt.n(s.calls), s.errors + " errors"), card("Tokens in / out", fmt.n(s.prompt_tokens) + " / " + fmt.n(s.completion_tokens)), card("Cost", fmt.usd(s.cost_usd), "per reply " + fmt.usd(s.cost_per_reply_usd)),
        card("Latency p50 / p95 / max", fmt.f(s.latency.p50) + " / " + fmt.f(s.latency.p95) + " / " + fmt.f(s.latency.max) + " s"), card("Calls per reply", fmt.f(s.calls_per_reply)),
        card("Lines him / her / env", `${s.lines.him} / ${s.lines.her} / ${s.lines.env}`, `${s.replies} replies, ${s.unprompted} unprompted`), card("Repetition", fmt.pct(s.repetition_rate)), card("Language purity", fmt.pct(s.language_purity), "target " + (r.lang || "?")),
        card("Causal share", fmt.pct(s.causal.causal_share), s.causal.traces_with_causal + " traces with causal"), card("Constant lines", fmt.pct(s.causal.constant_line_share))),
      h("div", {class: "cols"},
        h("div", {}, h("b", {}, "Cost per simulated day"), s.cost_per_day.map((d) => h("div", {}, `D${d.day ?? "?"} `, h("span", {class: "bar", style: `width:${Math.max(2, 200 * d.cost_usd / maxc)}px`}), ` ${fmt.usd(d.cost_usd)} (${d.calls} calls)`))),
        h("div", {}, h("b", {}, "Reply length (chars)"), s.reply_len.hist.map((d) => h("div", {}, `${d.lo}${d.hi ? "-" + (d.hi - 1) : "+"} `, h("span", {class: "bar", style: `width:${Math.max(d.n ? 2 : 0, 200 * d.n / maxh)}px`}), ` ${d.n}`)))));
  });
  main.replaceChildren(...kids);
}

// ---------- vote ----------
async function viewVote(main) {
  const d = await api("pairs");
  if (!d.pairs.length) return main.replaceChildren(h("div", {class: "empty"}, "no pairs to vote on yet"));
  let id = get("pair");
  if (!d.pairs.some((p) => p.pair_id === id)) { const nxt = d.pairs.find((p) => !p.voted) || d.pairs[0]; id = nxt.pair_id; }
  const sig = JSON.stringify(d.pairs) + id;
  if (sig === lastSig.vote && main.firstChild) return;
  lastSig.vote = sig;
  const p = await api("pair?id=" + encodeURIComponent(id));
  const note = h("textarea", {rows: 3, style: "width:100%", placeholder: "note (optional)"});
  note.value = (p.vote && p.vote.note) || "";
  const msg = h("div", {class: "dim"}, p.vote ? "You voted " + p.vote.choice + " on this one. Voting again replaces it." : "");
  const cast = async (choice) => {
    const r = await fetch("/api/vote", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({pair_id: id, choice, note: note.value})});
    const j = await r.json();
    if (!r.ok) { msg.textContent = "not saved: " + j.error; return; }
    const nxt = d.pairs.find((x) => !x.voted && x.pair_id !== id);
    if (nxt) setQ({pair: nxt.pair_id}, false);
    go(true);
  };
  main.replaceChildren(
    h("div", {class: "dim"}, "Pair " + id + " (" + (d.pairs.filter((x) => x.voted).length) + " of " + d.pairs.length + " voted)"),
    h("div", {}, d.pairs.map((x) => h("a", {href: "?view=vote&pair=" + x.pair_id, class: x.voted ? "dim" : "", onclick: (e) => { e.preventDefault(); setQ({pair: x.pair_id}); go(true); }}, " [" + x.pair_id + (x.voted ? " done" : "") + "]"))),
    h("div", {class: "cols", style: "margin-top:10px"}, h("div", {class: "pane"}, h("h2", {}, "A"), h("div", {class: "voteA"}, p.A)), h("div", {class: "pane"}, h("h2", {}, "B"), h("div", {class: "voteB"}, p.B))),
    h("div", {style: "text-align:center;margin-top:10px"}, h("button", {class: "vbtn", onclick: () => cast("A")}, "A is better"), h("button", {class: "vbtn", onclick: () => cast("tie")}, "Tie"), h("button", {class: "vbtn", onclick: () => cast("B")}, "B is better")),
    note, msg);
}

// ---------- driver ----------
async function go(force) {
  if (force) lastSig = {};
  const view = get("view", "runs");
  $("#nav").replaceChildren(...VIEWS.map(([k, n]) => h("a", {href: "?view=" + k, class: k === view ? "on" : "", onclick: (e) => { e.preventDefault(); setQ({view: k}); go(true); }}, n)));
  try {
    const [o, r] = await Promise.all([api("options" + (devOn() ? "?dev=1" : "")), api("runs")]);
    OPTS = o; RUNS = r.runs; window.__root = r.root;
    $("#live").textContent = "live " + new Date().toTimeString().slice(0, 8); $("#live").className = "";
    if (force || lastSig.filters !== JSON.stringify(o) + Q.toString()) { renderFilters(view); lastSig.filters = JSON.stringify(o) + Q.toString(); }
    const main = $("#main");
    if (view === "runs") { const s = JSON.stringify(RUNS) + Q.toString(); if (s !== lastSig.runs) { lastSig.runs = s; viewRuns(main); } }
    else if (view === "conv") await viewConv(main);
    else if (view === "side") await viewSide(main);
    else if (view === "judge") await viewJudge(main);
    else if (view === "stats") await viewStats(main);
    else if (view === "vote") { if (force) await viewVote(main); }
    if (view === "conv" && selOutput && get("run")) loadTrace(get("run"), selOutput);
  } catch (e) {
    $("#live").textContent = "offline: " + e.message; $("#live").className = "off";
  }
}
window.addEventListener("popstate", () => { Q = new URLSearchParams(location.search); selOutput = null; go(true); });
go(true);
setInterval(() => go(false), 3000);
