"""The page `factory.sh serve` shows (WP-91): one HTML file with its script inline, no dependency and no build step.

It draws the factory's own JSON views — status, decisions, discovery, requests, one story, a stage's output — in the
cockpit's tabs, and every press writes a request (or starts and stops the factory). It decides nothing: the order, the
marks, the words and which request a press writes come from the factory (`action.request` beside `action.skill`).
Kept as a module so it ships, installs and is hashed with the package.
"""

import base64
import hashlib
import re

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Factory</title>
<style>
:root {
  --bg: #f6f5f2; --panel: #ffffff; --ink: #1d1d1b; --muted: #6b6a66; --line: #e2e0da; --accent: #2a5bd7;
  --done: #2e7d4f; --wait: #b26a00; --stop: #c0392b; --run: #2a5bd7; --soft: #eef1f8; --code: #f0efea;
  --radius: 8px; --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #141413; --panel: #1d1d1b; --ink: #ecebe6; --muted: #9c9a93; --line: #33322f; --accent: #7aa2ff;
          --done: #5fbf86; --wait: #e0a03a; --stop: #ef6f61; --run: #7aa2ff; --soft: #232a3a; --code: #262522; }
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 var(--sans); }
header { position: sticky; top: 0; z-index: 5; background: var(--panel); border-bottom: 1px solid var(--line); }
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 10px 16px; max-width: 1200px; margin: 0 auto; }
.title { font-weight: 650; font-size: 17px; margin-right: auto; }
.title small { color: var(--muted); font-weight: 400; margin-left: 8px; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; background: var(--soft); font-size: 13px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
.dot.up { background: var(--done); } .dot.stopping { background: var(--wait); } .dot.down { background: var(--stop); }
nav { display: flex; gap: 2px; padding: 0 16px; max-width: 1200px; margin: 0 auto; overflow-x: auto; }
nav button { border: 0; background: none; color: var(--muted); padding: 8px 12px; font: inherit; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
nav button.on { color: var(--ink); border-bottom-color: var(--accent); }
nav button .n { display: inline-block; min-width: 18px; padding: 0 5px; margin-left: 4px; border-radius: 9px; background: var(--wait); color: #fff; font-size: 11px; }
main { max-width: 1200px; margin: 0 auto; padding: 16px; }
section.card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; margin-bottom: 14px; }
h2 { font-size: 15px; margin: 0 0 10px; display: flex; align-items: center; gap: 8px; }
h2 .sub { color: var(--muted); font-weight: 400; font-size: 13px; }
h3 { font-size: 14px; margin: 12px 0 6px; }
p.muted, .muted { color: var(--muted); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--muted); font-weight: 500; border-bottom: 1px solid var(--line); padding: 4px 6px; }
td { border-bottom: 1px solid var(--line); padding: 6px; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.mark { font-weight: 700; width: 1.4em; display: inline-block; text-align: center; }
.m-done { color: var(--done); } .m-look, .m-question { color: var(--wait); } .m-stopped { color: var(--stop); }
.m-running { color: var(--run); } .m-next { color: var(--accent); } .m-none { color: var(--muted); }
button.act, a.act { font: inherit; font-size: 13px; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); cursor: pointer; text-decoration: none; }
button.act:hover { border-color: var(--accent); }
button.act.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.act.danger { color: var(--stop); }
button.act:disabled { opacity: .5; cursor: default; }
.acts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
textarea, input[type=text], select { font: inherit; font-size: 14px; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; }
textarea { width: 100%; min-height: 64px; resize: vertical; }
input.by { width: 150px; }
.row { display: flex; gap: 8px; align-items: flex-start; flex-wrap: wrap; }
.grow { flex: 1 1 260px; }
.state { font-size: 12px; padding: 1px 7px; border-radius: 4px; background: var(--code); white-space: nowrap; }
.st-queued { color: var(--accent); } .st-running { color: var(--run); } .st-waiting { color: var(--wait); } .st-failed { color: var(--stop); }
pre.out { font: 12.5px/1.45 var(--mono); background: var(--code); border-radius: 6px; padding: 10px; max-height: 420px; overflow: auto; white-space: pre-wrap; word-break: break-word; margin: 8px 0 0; }
code { font-family: var(--mono); font-size: 12.5px; background: var(--code); padding: 0 4px; border-radius: 3px; }
.empty { color: var(--muted); padding: 6px 0; }
.option { display: flex; gap: 8px; align-items: baseline; margin: 4px 0; }
.option .key { font-weight: 700; min-width: 1.2em; }
.rec { color: var(--wait); font-size: 12px; }
#toast { position: fixed; right: 16px; bottom: 16px; max-width: 420px; z-index: 20; display: flex; flex-direction: column; gap: 8px; }
.toast { background: var(--panel); border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 6px; padding: 8px 12px; box-shadow: 0 4px 16px rgba(0,0,0,.12); font-size: 14px; white-space: pre-wrap; }
.toast.err { border-left-color: var(--stop); }
.drawer { position: fixed; top: 0; right: 0; height: 100%; width: min(720px, 100%); background: var(--panel); border-left: 1px solid var(--line); z-index: 10; overflow-y: auto; padding: 16px; box-shadow: -6px 0 24px rgba(0,0,0,.15); }
.drawer .close { float: right; }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 2px 12px; font-size: 14px; }
.kv dt { color: var(--muted); } .kv dd { margin: 0; }
.link { color: var(--accent); cursor: pointer; text-decoration: none; }
.link:hover { text-decoration: underline; }
.next { padding: 10px 14px; border-radius: var(--radius); background: var(--soft); margin-bottom: 14px; }
.err-banner { background: var(--stop); color: #fff; padding: 8px 16px; display: none; }
@media (max-width: 640px) { .hide-s { display: none; } td, th { padding: 4px; } }
</style>
</head>
<body>
<div class="err-banner" id="banner"></div>
<header>
  <div class="bar">
    <div class="title">Factory<small id="project"></small></div>
    <span class="pill" id="worker"><span class="dot"></span><span>…</span></span>
    <button class="act primary" id="up" hidden>up</button>
    <button class="act" id="down" hidden>down</button>
    <label class="muted" style="font-size:13px">as <input class="by" id="by" type="text" autocomplete="name"></label>
  </div>
  <nav id="tabs"></nav>
</header>
<main id="main"></main>
<div id="toast"></div>
<div class="drawer" id="drawer" hidden></div>
<script>
"use strict";
const TOKEN = new URLSearchParams(location.search).get("t") || "";
const TABS = [["describe", "0 Describe"], ["discover", "1 Discover"], ["backlog", "2 Backlog"], ["run", "3 Run"],
              ["decide", "4 Decide"], ["delivered", "5 Delivered"]];
const MARKS = {look: "!", question: "?", stopped: "✗", running: "▶", done: "✓", none: "·", next: "→"};
const S = {tab: "backlog", status: null, decisions: null, discover: null, requests: null, meta: null, follow: null,
           followSource: null, followLines: [], drawer: null, busy: false};
try { S.tab = localStorage.getItem("factory.tab") || S.tab; } catch (e) {}
if (TABS.some(([id]) => id === location.hash.slice(1))) S.tab = location.hash.slice(1);

// --- helpers -------------------------------------------------------------------------------------------------------
const $ = id => document.getElementById(id);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const when = v => v ? String(v).replace("T", " ").replace(/:\d\dZ$/, "").replace("Z", "") : "";
const tokens = n => !n ? "" : n >= 1e6 ? (n / 1e6).toFixed(1) + " M" : n >= 1e3 ? Math.round(n / 1e3) + " k" : String(n);
const cost = n => n ? "$" + n.toFixed(2) : "";
const took = s => !s ? "" : s >= 3600 ? (s / 3600).toFixed(1) + " h" : s >= 60 ? Math.round(s / 60) + " min" : Math.round(s) + " s";
const mark = m => `<span class="mark m-${esc(m)}">${esc(MARKS[m] || "·")}</span>`;
function by() { return $("by").value.trim(); }

async function api(path, body) {
  const options = {headers: {"X-Factory-Token": TOKEN}};
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch (e) { data = {error: "no JSON from " + path}; }
  if (!response.ok) throw new Error(data.error || data.output || ("HTTP " + response.status));
  return data;
}

function toast(text, isError) {
  const node = document.createElement("div");
  node.className = "toast" + (isError ? " err" : "");
  node.textContent = text;
  $("toast").appendChild(node);
  setTimeout(() => node.remove(), isError ? 9000 : 4500);
}

// A press writes a request: its kind, the fields it names, the person's words — as the factory's action says.
async function request(kind, fields, words) {
  try {
    const data = await api("/api/request", Object.assign({kind, words: words || "", by: by()}, fields || {}));
    toast(data.duplicate ? `already queued: ${data.id}` : `request written: ${data.id}`);
    refresh();
    return true;
  } catch (e) { toast(e.message, true); return false; }
}

// An action from the factory's JSON: its request where the factory names one; what is still open is asked here.
function press(action, label, primary, prefix) {
  if (!action || !action.request) return "";
  const id = (prefix || "a") + Math.random().toString(36).slice(2);
  ACTIONS[id] = action;
  return `<button class="act${primary ? " primary" : ""}" data-action="${id}">${esc(label)}</button>`;
}
const ACTIONS = {};
document.addEventListener("click", async event => {
  const target = event.target.closest("[data-action],[data-call],[data-story],[data-tab]");
  if (!target) return;
  if (target.dataset.tab) { show(target.dataset.tab); return; }
  if (target.dataset.story) { openStory(target.dataset.story); return; }
  if (target.dataset.action) {
    const action = ACTIONS[target.dataset.action], r = action.request;
    let words = r.words || "";
    if (r.open === "words") {
      words = prompt(action.text || action.skill || "Your words:", "");
      if (!words) return;
    }
    if (r.open === "record") { show("decide"); return; }
    target.disabled = true;
    await request(r.kind, r.fields, words);
    target.disabled = false;
    return;
  }
  if (target.dataset.call) {
    target.disabled = true;
    try { await CALLS[target.dataset.call](target); } finally { target.disabled = false; }
  }
});

const CALLS = {
  async up() {
    try { const d = await api("/api/up", {by: by()}); toast(d.output || "up"); }
    catch (e) { toast(e.message, true); }
    refresh();
  },
  async down(node) {
    const now = node.dataset.now === "1";
    if (now && !confirm("Interrupt the running stage too? Its work so far stays; the stage runs again later.")) return;
    try { const d = await api("/api/down", {by: by(), now}); toast(d.output || "stopping"); }
    catch (e) { toast(e.message, true); }
    refresh();
  },
  async form(node) {
    const box = node.closest("[data-form]"), kind = box.dataset.form;
    const fields = JSON.parse(box.dataset.fields || "{}");
    const text = box.querySelector("textarea, input[type=text]");
    const pick = box.querySelector("select");
    if (pick && pick.value) fields.option = pick.value;
    if (await request(kind, fields, text ? text.value.trim() : "")) { if (text) text.value = ""; }
  },
  async option(node) {
    await request("answer", {record: node.dataset.record, option: node.dataset.key}, "");
  },
  async drop(node) {
    if (!confirm(`Drop request ${node.dataset.id}?`)) return;
    try { await api("/api/requests/drop", {id: node.dataset.id}); toast("dropped"); } catch (e) { toast(e.message, true); }
    refresh();
  },
  async retry(node) {
    try { await api("/api/requests/retry", {id: node.dataset.id}); toast("queued again"); } catch (e) { toast(e.message, true); }
    refresh();
  },
  async follow(node) { follow(node.dataset.kind, node.dataset.id); },
  async unfollow() { follow(null); },
  async close() { S.drawer = null; $("drawer").hidden = true; },
};

function form(kind, fields, placeholder, label, extra) {
  return `<div data-form="${esc(kind)}" data-fields="${esc(JSON.stringify(fields || {}))}" class="row">
    <textarea class="grow" placeholder="${esc(placeholder)}"></textarea>${extra || ""}
    <button class="act primary" data-call="form">${esc(label)}</button></div>`;
}

// --- loading -------------------------------------------------------------------------------------------------------
async function load(name, path) {
  try { S[name] = await api(path); return true; }
  catch (e) { S[name] = S[name] || null; banner(`${name}: ${e.message}`); return false; }
}
function banner(text) {
  const node = $("banner");
  node.textContent = text || "";
  node.style.display = text ? "block" : "none";
}

let refreshing = false, lastSlow = 0;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const slow = Date.now() - lastSlow > 15000 || ["decide", "discover"].includes(S.tab);
    const jobs = [load("status", "/api/view/status"), load("requests", "/api/view/requests")];
    if (slow || !S.decisions) jobs.push(load("decisions", "/api/view/decisions"));
    if (slow || !S.discover) jobs.push(load("discover", "/api/view/discover"));
    const results = await Promise.all(jobs);
    if (results.every(Boolean)) banner("");
    if (slow) lastSlow = Date.now();
    render();
  } finally { refreshing = false; }
}

// --- the frame -----------------------------------------------------------------------------------------------------
function show(tab) {
  S.tab = tab;
  try { localStorage.setItem("factory.tab", tab); } catch (e) {}
  history.replaceState(null, "", "#" + tab);
  render();
}

function waitingCount() {
  return (S.status && S.status.waiting || []).length;
}

function renderFrame() {
  const st = S.status || {}, w = st.worker, req = (S.requests || {}).counts || {};
  $("project").textContent = st.project ? "· " + st.project : "";
  document.title = (st.project ? st.project + " — " : "") + "Factory";
  const dot = !w ? "down" : !w.alive ? "down" : w.stopping ? "stopping" : "up";
  const text = !w ? "down" : !w.alive ? `${w.how} — no sign of life` : w.stopping ? `stopping (${w.how})` :
    `up · ${w.how}` + (w.how === "session" ? "" : "");
  $("worker").innerHTML = `<span class="dot ${dot}"></span><span>${esc(text)}</span>` +
    (req.queued || req.running || req.waiting ? `<span class="muted">· ${req.queued || 0} queued` +
     (req.running ? `, ${req.running} running` : "") + (req.waiting ? `, ${req.waiting} asking` : "") + "</span>" : "");
  $("worker").title = w ? `${w.owner} since ${w.since}` : "nobody holds the checkout";
  $("up").hidden = !!(w && w.alive);
  $("down").hidden = !(w && w.alive) || w.stopping;
  $("tabs").innerHTML = TABS.map(([id, label]) => {
    const n = id === "decide" ? waitingCount() : id === "run" ? (req.failed || 0) : 0;
    return `<button data-tab="${id}" class="${S.tab === id ? "on" : ""}">${esc(label)}${n ? `<span class="n">${n}</span>` : ""}</button>`;
  }).join("");
}

function render() {
  renderFrame();
  const view = {describe, discover, backlog, run, decide, delivered}[S.tab] || backlog;
  const keepFocus = document.activeElement && document.activeElement.tagName === "TEXTAREA";
  if (keepFocus) return;                                   // a person typing is not redrawn under their hands
  for (const key of Object.keys(ACTIONS)) if (key[0] === "a") delete ACTIONS[key];
  $("main").innerHTML = S.status ? view() : `<section class="card"><p class="muted">Reading the factory…</p></section>`;
  if (S.tab === "run") paintFollow();
}

function nextLine() {
  const nx = (S.status || {}).next;
  if (!nx) return "";
  return `<div class="next">${mark("next")} ${esc(nx.text)} ${press(nx.action, "do it", true)}</div>`;
}

// --- 0 Describe ----------------------------------------------------------------------------------------------------
function describe() {
  const parts = (S.status.description || []).map(p => `<tr><td>${mark(p.present && !(p.missing || []).length ? "done" : "question")}</td>
    <td><b>${esc(p.part)}</b><br><code>${esc(p.path)}</code></td>
    <td>${p.present ? esc((p.sections || []).join(" · ")) : "<span class='muted'>missing</span>"}
    ${(p.missing || []).length ? `<div class="rec">missing: ${esc(p.missing.join(", "))}</div>` : ""}
    ${(p.empty || []).length ? `<div class="rec">empty: ${esc(p.empty.join(", "))}</div>` : ""}</td></tr>`).join("");
  return `<section class="card"><h2>The project description <span class="sub">what is built, how, and in which domain — written once, changed when things move</span></h2>
    <table><tr><th></th><th>part</th><th>sections</th></tr>${parts}</table></section>
    <section class="card"><h2>Change the description</h2>
    <p class="muted">In your words — <code>&lt;part&gt;: &lt;change&gt;</code> where it is one part. The description skill writes it; where it needs a decision of yours it asks under Decide.</p>
    ${form("describe", {}, "e.g. tech: the shop runs on PostgreSQL 17", "describe")}</section>`;
}

// --- 1 Discover ----------------------------------------------------------------------------------------------------
function discover() {
  const topics = (S.discover || {}).topics || [];
  const cards = topics.map(t => {
    const proposals = t.proposals.map(p => `<tr><td><code>${esc(p.id)}</code></td><td>${esc(p.goal || p.intent)}</td>
      <td>${esc(p.metric)}</td><td>${p.epic ? `epic <b>${esc(p.epic)}</b>` :
        press({request: {kind: "epic-from", fields: {topic: t.topic, proposal: p.id}, words: "", open: ""}}, "make epic", true)}</td></tr>`).join("");
    const changes = t.description_changes.map(c => `<li><b>${esc(c.target)}</b> — ${esc(c.change)}
      <span class="muted">${esc(c.why)}</span> ${press({request: {kind: "describe", fields: {}, words: `${c.target}: ${c.change}`, open: ""}}, "apply")}</li>`).join("");
    return `<section class="card"><h2>${esc(t.title)} <span class="sub"><code>${esc(t.report)}</code></span></h2>
      ${proposals ? `<table><tr><th>proposal</th><th>goal</th><th>outcome event</th><th></th></tr>${proposals}</table>` : "<p class='empty'>No proposed work.</p>"}
      ${changes ? `<h3>Changes to the description</h3><ul>${changes}</ul>` : ""}</section>`;
  }).join("");
  return `<section class="card"><h2>A new discovery <span class="sub">a problem or a wished deliverable — the report, its sources and the epics it proposes</span></h2>
    ${form("discover", {}, "What problem is worth solving, or what should exist?", "discover")}</section>
    ${cards || `<section class="card"><p class="empty">No discovery yet (${esc((S.discover || {}).store || "")}).</p></section>`}`;
}

// --- 2 Backlog -----------------------------------------------------------------------------------------------------
function storyRow(r) {
  const st = S.status, waiting = (st.waiting || []).find(w => w.story === r.story);
  const acts = [];
  if (waiting && waiting.action && waiting.action.request) acts.push(press(waiting.action, waiting.draft ? "release" : "answer", true));
  if (!r.done && st.queue && st.queue.ready.includes(r.story)) acts.push(press({request: {kind: "run", fields: {story: r.story}, words: "", open: ""}}, "run now"));
  return `<tr><td>${mark(r.mark)}</td><td><a class="link" data-story="${esc(r.story)}">${esc(r.title || r.story)}</a>
    <div class="muted" style="font-size:12px">${esc(r.story)}</div></td><td>${esc(r.state)}</td>
    <td class="hide-s">${esc(r.stage === "—" ? "" : r.stage)}</td><td class="num hide-s">${tokens(r.tokens)}</td><td>${acts.join(" ")}</td></tr>`;
}

function backlog() {
  const st = S.status;
  const epics = (st.epics || []).map(e => {
    const drafts = e.rows.filter(r => r.state && /draft/.test(r.state) || (st.waiting || []).some(w => w.story === r.story && w.draft));
    const acts = [press({request: {kind: "stories", fields: {epic: e.epic}, words: "", open: ""}}, "suggest stories", !e.total)];
    if (drafts.length) acts.push(press({request: {kind: "release", fields: {epic: e.epic}, words: "", open: ""}}, `release ${drafts.length} draft(s)`));
    const journey = (st.journeys || []).find(j => j.epic === e.epic);
    if (journey) acts.push(press(journey.action, "add guard"));
    return `<section class="card"><h2>${esc(e.title || e.epic)} <span class="sub">${esc(e.epic)} · ${e.delivered}/${e.total} delivered${e.metric ? " · " + esc(e.metric) : ""}</span></h2>
      ${e.goal ? `<p class="muted" style="margin:0 0 8px">${esc(e.goal)}</p>` : ""}
      ${journey ? `<p class="rec">${esc(journey.text)}</p>` : ""}
      ${e.rows.length ? `<table><tr><th></th><th>story</th><th>state</th><th class="hide-s">stage</th><th class="num hide-s">tokens</th><th></th></tr>${e.rows.map(storyRow).join("")}</table>` : "<p class='empty'>No story yet.</p>"}
      <div class="acts">${acts.join("")}</div></section>`;
  }).join("");
  const findings = (st.findings || []).map(f => `<tr><td>${esc(f.severity)}</td><td>${esc(f.plain || f.defect)}<div class="muted" style="font-size:12px">${esc(f.row)} · ${esc(f.where)}</div></td>
    <td>${press(f.action, "to backlog")}</td></tr>`).join("");
  return `${nextLine()}<section class="card"><h2>A wish <span class="sub">your words become a story, kept as a draft until you release it</span></h2>
    ${form("wish", {}, "What should the product do that it does not do yet?", "wish")}</section>
    ${epics || `<section class="card"><p class="empty">The backlog is empty.</p></section>`}
    ${findings ? `<section class="card"><h2>Findings <span class="sub">what the judge kept open</span></h2><table>${findings}</table></section>` : ""}`;
}

// --- 3 Run ---------------------------------------------------------------------------------------------------------
function run() {
  const st = S.status, w = st.worker, reqs = (S.requests || {}).requests || [];
  const workerCard = w ? `<dl class="kv"><dt>worker</dt><dd>${esc(w.owner)}</dd><dt>how</dt><dd>${esc(w.how)}${w.alive ? "" : " — no sign of life"}${w.stopping ? " — stopping after its stage" : ""}</dd>
      <dt>since</dt><dd>${esc(when(w.since))} UTC</dd>${w.log ? `<dt>log</dt><dd><code>${esc(w.log)}</code></dd>` : ""}</dl>
      <div class="acts">${w.alive && !w.stopping ? `<button class="act" data-call="down">down — after the running stage</button>
      <button class="act danger" data-call="down" data-now="1">down now</button>` : ""}</div>`
    : `<p class="muted">The factory is down. Requests wait in the queue until it is up.</p><div class="acts"><button class="act primary" data-call="up">up</button></div>`;
  const running = (st.running || []).map(r => `<tr><td>${mark(r.interrupted ? "stopped" : "running")}</td>
    <td><a class="link" data-story="${esc(r.story)}">${esc(r.story)}</a></td><td>${esc(r.stage)}${r.part ? " · " + esc(r.part) : ""}</td>
    <td class="hide-s">${esc(r.ago || when(r.since))}</td><td class="hide-s muted">${esc(r.activity || "")}</td>
    <td><button class="act" data-call="follow" data-kind="story" data-id="${esc(r.story)}">follow</button></td></tr>`).join("");
  const ready = (st.queue && st.queue.ready || []).map(s => `<li><a class="link" data-story="${esc(s)}">${esc(s)}</a>
    ${press({request: {kind: "run", fields: {story: s}, words: "", open: ""}}, "run now")}</li>`).join("");
  const requests = reqs.map(r => `<tr><td><span class="state st-${esc(r.state)}">${esc(r.state)}</span></td>
    <td><b>${esc(r.kind)}</b> ${esc(r.target)}<div class="muted" style="font-size:12px">${esc(r.id)} · ${esc(r.by)} · ${esc(when(r.asked))}</div>
    ${r.error ? `<div class="m-stopped" style="font-size:13px">${esc(r.error)}</div>` : ""}
    ${r.record ? `<div class="rec">asks: <code>${esc(r.record)}</code> — answer it under Decide</div>` : ""}</td>
    <td>${r.state === "running" ? `<button class="act" data-call="follow" data-kind="request" data-id="${esc(r.id)}">follow</button>` : ""}
    ${r.state === "failed" ? `<button class="act" data-call="retry" data-id="${esc(r.id)}">retry</button>` : ""}
    ${r.state !== "running" ? `<button class="act danger" data-call="drop" data-id="${esc(r.id)}">drop</button>` : ""}</td></tr>`).join("");
  return `${nextLine()}<section class="card"><h2>The factory</h2>${workerCard}</section>
    <section class="card"><h2>Requests <span class="sub">worked before the next story, oldest first</span></h2>
      ${requests ? `<table>${requests}</table>` : "<p class='empty'>No request waits.</p>"}</section>
    <section class="card"><h2>Running</h2>${running ? `<table>${running}</table>` : "<p class='empty'>No stage runs.</p>"}
      ${ready ? `<h3>Ready</h3><ul>${ready}</ul>` : ""}</section>
    <section class="card"><h2>Output <span class="sub" id="follow-title"></span></h2><div class="acts" id="follow-acts"></div><pre class="out" id="follow-out"></pre></section>`;
}

function follow(kind, id) {
  if (S.followSource) { S.followSource.close(); S.followSource = null; }
  S.follow = kind ? {kind, id} : null;
  S.followLines = [];
  if (kind) {
    const query = kind === "request" ? `request=${encodeURIComponent(id)}` : `story=${encodeURIComponent(id)}`;
    const source = new EventSource(`/api/follow?${query}&t=${encodeURIComponent(TOKEN)}`);
    source.onmessage = event => {
      try { S.followLines.push(JSON.parse(event.data)); } catch (e) { S.followLines.push(event.data); }
      if (S.followLines.length > 1500) S.followLines.splice(0, S.followLines.length - 1500);
      paintFollow();
    };
    source.addEventListener("end", () => { S.followLines.push("— the output ended —"); paintFollow(); source.close(); });
    source.onerror = () => {};
    S.followSource = source;
  }
  if (S.tab !== "run") show("run"); else paintFollow();
}

function paintFollow() {
  const out = $("follow-out");
  if (!out) return;
  $("follow-title").textContent = S.follow ? `${S.follow.kind} ${S.follow.id}` : "follow a running stage or request";
  $("follow-acts").innerHTML = S.follow ? `<button class="act" data-call="unfollow">stop following</button>` : "";
  const atEnd = out.scrollTop + out.clientHeight >= out.scrollHeight - 20;
  out.textContent = S.followLines.join("\n") || (S.follow ? "waiting for output…" : "");
  if (atEnd) out.scrollTop = out.scrollHeight;
}

// --- 4 Decide ------------------------------------------------------------------------------------------------------
const CODES = ["structural", "behavioural", "domain-concept", "domain-boundary", "domain-invariant", "domain-term", "assumption"];

function recordCard(r) {
  const options = (r.options || []).map(o => `<div class="option"><button class="act${o.key === r.recommended ? " primary" : ""}"
      data-call="option" data-record="${esc(r.id)}" data-key="${esc(o.key)}">${esc(o.key)}</button>
      <span>${esc(o.text)}${o.key === r.recommended ? ` <span class="muted">— the stage's recommendation</span>` : ""}</span></div>`).join("");
  if (r.kind === "acceptance") {
    const select = `<select title="why"><option value="">why? (optional)</option>${CODES.map(c => `<option>${c}</option>`).join("")}</select>`;
    return `<section class="card"><h2>${mark("look")} ${esc(r.text)} <span class="sub">${esc(r.story)}</span></h2>
      <p class="muted"><code>${esc(r.path)}</code> · <a class="link" data-story="${esc(r.story)}">the story</a></p>
      <div class="acts">${press({request: {kind: "accept", fields: {story: r.story}, words: "", open: ""}}, "accept", true)}</div>
      <h3>or correct it</h3>${form("correct", {story: r.story}, "What should be different?", "correct", select)}</section>`;
  }
  return `<section class="card"><h2>${mark("question")} ${esc(r.text)} <span class="sub">${esc(r.story || "project")} · ${esc(r.stage)}</span></h2>
    <p class="muted"><code>${esc(r.path)}</code>${r.story ? ` · <a class="link" data-story="${esc(r.story)}">the story</a>` : ""}</p>
    ${options}<h3>${options ? "or in your words" : "your answer"}</h3>${form("answer", {record: r.id}, "Your answer", "answer")}</section>`;
}

function decide() {
  const st = S.status, records = ((S.decisions || {}).records || []).filter(r => r.state === "open" || r.state === "draft");
  const asked = new Set(records.map(r => r.story));
  const others = (st.waiting || []).filter(w => !asked.has(w.story)).map(w => `<tr><td>${mark(w.mark)}</td>
    <td><a class="link" data-story="${esc(w.story)}">${esc(w.story)}</a></td><td>${esc(w.what)}</td>
    <td>${press(w.action, w.draft ? "release" : w.mark === "stopped" ? "" : "do it", true) || `<span class="muted">${esc((w.action || {}).text || (w.action || {}).skill || "")}</span>`}</td></tr>`).join("");
  return `${records.map(recordCard).join("")}
    ${others ? `<section class="card"><h2>Also waiting for you</h2><table>${others}</table></section>` : ""}
    ${!records.length && !others ? `<section class="card"><p class="empty">Nothing waits for you.</p></section>` : ""}`;
}

// --- 5 Delivered ---------------------------------------------------------------------------------------------------
function delivered() {
  const st = S.status, rows = Object.fromEntries((st.rows || []).map(r => [r.story, r]));
  const list = (st.delivered_order || []).map(id => rows[id]).filter(Boolean).map(r => `<tr><td>${mark("done")}</td>
    <td><a class="link" data-story="${esc(r.story)}">${esc(r.title || r.story)}</a><div class="muted" style="font-size:12px">${esc(r.epic)} · ${esc(r.story)}</div></td>
    <td class="hide-s">${esc(when(r.delivered))}</td><td class="num hide-s">${took(r.seconds)}</td><td class="num">${tokens(r.tokens)}</td><td class="num hide-s">${cost(r.cost)}</td></tr>`).join("");
  return `<section class="card"><h2>Delivered <span class="sub">${st.delivered}/${st.total} · ${tokens(st.tokens)} tokens · ${took(st.seconds)}</span></h2>
    ${list ? `<table><tr><th></th><th>story</th><th class="hide-s">delivered (UTC)</th><th class="num hide-s">worked</th><th class="num">tokens</th><th class="num hide-s">cost</th></tr>${list}</table>` : "<p class='empty'>Nothing delivered yet.</p>"}</section>`;
}

// --- one story -----------------------------------------------------------------------------------------------------
async function openStory(id) {
  S.drawer = id;
  const node = $("drawer");
  node.hidden = false;
  node.innerHTML = `<button class="act close" data-call="close">close</button><p class="muted">Reading ${esc(id)}…</p>`;
  let v;
  try { v = await api(`/api/view/story?id=${encodeURIComponent(id)}`); }
  catch (e) { node.innerHTML = `<button class="act close" data-call="close">close</button><p class="m-stopped">${esc(e.message)}</p>`; return; }
  if (S.drawer !== id) return;
  for (const key of Object.keys(ACTIONS)) if (key[0] === "d") delete ACTIONS[key];
  const row = v.row || {};
  const sections = (v.sections || []).map(s => `<h3>${esc(s.heading)}</h3><div style="white-space:pre-wrap">${esc(s.text)}</div>`).join("");
  const scenarios = (v.scenarios || []).map(c => `<h3>${esc(c.title || c.key)}</h3>${c.rule ? `<p class="muted">${esc(c.rule)}</p>` : ""}
    ${(c.steps || []).map(s => `<div><b>${esc(s.word)}</b> ${esc(s.text)}</div>`).join("")}`).join("");
  const stages = Object.entries(v.stages || {}).map(([name, e]) => `<tr><td>${esc(name)}</td><td class="num">${e.runs || ""}</td>
    <td class="num">${took(e.seconds)}</td><td class="num">${tokens(e.tokens)}</td><td class="num">${cost(e.cost)}</td><td class="muted">${esc(e.why || "")}</td></tr>`).join("");
  const waiting = (v.waiting || []).map(w => `<li>${mark(w.mark)} ${esc(w.what)} ${press(w.action, "do it", true, "d")}</li>`).join("");
  const acts = [];
  if (!row.done) acts.push(press({request: {kind: "run", fields: {story: id}, words: "", open: ""}}, "run now", false, "d"));
  acts.push(`<button class="act" data-call="follow" data-kind="story" data-id="${esc(id)}">output</button>`);
  node.innerHTML = `<button class="act close" data-call="close">close</button>
    <h2>${mark(row.mark || "none")} ${esc(v.title || id)}</h2>
    <dl class="kv"><dt>story</dt><dd>${esc(id)}</dd><dt>epic</dt><dd>${esc(v.epic)}</dd><dt>state</dt><dd>${esc(row.state || v.situation || "")}</dd>
      ${v.context ? `<dt>context</dt><dd>${esc(v.context)}</dd>` : ""}<dt>file</dt><dd><code>${esc(v.path)}</code></dd>
      ${row.tokens ? `<dt>tokens</dt><dd>${tokens(row.tokens)}${row.cost ? " · " + cost(row.cost) : ""}</dd>` : ""}</dl>
    <div class="acts">${acts.join("")}</div>
    ${waiting ? `<h3>Waiting for you</h3><ul>${waiting}</ul>` : ""}
    ${sections}${scenarios ? `<h3>Scenarios</h3>${scenarios}` : ""}
    ${stages ? `<h3>Processes</h3><table><tr><th>process</th><th class="num">runs</th><th class="num">time</th><th class="num">tokens</th><th class="num">cost</th><th></th></tr>${stages}</table>` : ""}
    ${row.done ? `<h3>Correct the delivered story</h3>${form("correct", {story: id}, "What should be different?", "correct")}` : ""}`;
}

// --- start ---------------------------------------------------------------------------------------------------------
$("up").setAttribute("data-call", "up");
$("down").setAttribute("data-call", "down");
document.addEventListener("keydown", event => {
  if (event.target.closest("textarea, input, select")) return;
  const tab = TABS.find(([, label]) => label[0] === event.key);
  if (tab) show(tab[0]);
  if (event.key === "Escape") CALLS.close();
});
(async () => {
  if (!TOKEN) { banner("This page needs the token `factory.sh serve` printed — open that URL."); return; }
  try {
    S.meta = await api("/api/meta");
    let stored = "";
    try { stored = localStorage.getItem("factory.by") || ""; } catch (e) {}
    $("by").value = stored || S.meta.by || "";
  } catch (e) { banner(e.message); }
  $("by").addEventListener("change", () => { try { localStorage.setItem("factory.by", by()); } catch (e) {} });
  await refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 5000);
})();
</script>
</body>
</html>
"""


#: The page's one script as its Content-Security-Policy names it: no other script runs, an injected one included.
SCRIPT_HASH = "sha256-" + base64.b64encode(hashlib.sha256(
    re.search(r"<script>(.*?)</script>", PAGE, re.S).group(1).encode("utf-8")).digest()).decode("ascii")
