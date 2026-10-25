"""The page `factory.sh serve` shows (WP-91): one HTML file with its script inline, no dependency and no build step.

It draws the factory's own JSON views — status, decisions, discovery, requests, one story, a stage's output — in the
cycle's tabs, in the project's look (the mark, its colours and faces, a light and a dark theme). It decides nothing:
the order, the marks, the words, the figures and every action — its label, whether it is the one to press, the request
it writes and what the person still gives — come from the factory. A press writes that request, or starts and stops
the factory. Kept as a module so it ships, installs and is hashed with the package.
"""

import base64
import hashlib
import re

#: The mark in its text cut (under 44 px), its strokes in the colour of the text around it.
MARK = ('<svg viewBox="17.4 12 85.2 96" fill="none" aria-hidden="true"><polygon points="60,20 94.6,40 94.6,80 60,100 '
        '25.4,80 25.4,40" stroke="currentColor" stroke-width="7" stroke-linejoin="round"/>'
        + "".join(f'<circle cx="{x}" cy="{y}" r="8" fill="currentColor"/>'
                  for x, y in ((60, 20), (94.6, 40), (94.6, 80), (60, 100), (25.4, 80), (25.4, 40)))
        + '<circle cx="60" cy="60" r="12" fill="var(--teal)"/></svg>')

#: The tab's icon: the same drawing in ink, as the website's favicon.
FAVICON = MARK.replace('aria-hidden="true"', 'xmlns="http://www.w3.org/2000/svg" width="32" height="36"') \
    .replace("currentColor", "#1c2433").replace('stroke-width="7"', 'stroke-width="7.7"').replace("var(--teal)", "#148f96")

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Factory</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
@font-face { font-family: "Space Grotesk"; font-weight: 300 700; font-display: swap; src: url(/fonts/space-grotesk-latin.woff2) format("woff2"); }
@font-face { font-family: "Newsreader"; font-weight: 200 800; font-display: swap; src: url(/fonts/newsreader-latin.woff2) format("woff2"); }
@font-face { font-family: "JetBrains Mono"; font-weight: 100 800; font-display: swap; src: url(/fonts/jetbrains-mono-latin.woff2) format("woff2"); }
:root {
  --teal: #148f96; --deep: #171d29; --mist: #e8eaf0;
  --bg: #f7f6f3; --panel: #ffffff; --ink: #1c2433; --muted: #5b6472; --line: #dedbd3; --soft: #eef4f4; --code: #f0eee9;
  --accent: #0d6b70; --accent-hover: #0b5b60; --on-accent: #ffffff; --fill: #0d6b70; --fill-hover: #0b5b60;
  --done: #0d6b70; --wait: #93600f; --stop: #a33a2a; --run: #148f96;
  --shadow: 0 6px 24px rgba(28, 36, 51, .10);
  --display: "Space Grotesk", "Avenir Next", "Trebuchet MS", sans-serif;
  --body: "Newsreader", Georgia, "Times New Roman", serif;
  --mono: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12171f; --panel: #1a2130; --ink: #e8eaf0; --muted: #9aa3b2; --line: #2b3445; --soft: #172a30; --code: #222a39;
    --accent: #3cbcc3; --accent-hover: #5fcdd3; --on-accent: #ffffff; --fill: #0d6b70; --fill-hover: #0b5b60;
    --done: #3cbcc3; --wait: #e2ab55; --stop: #e8806e; --run: #3cbcc3; --shadow: 0 6px 24px rgba(0, 0, 0, .35);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #12171f; --panel: #1a2130; --ink: #e8eaf0; --muted: #9aa3b2; --line: #2b3445; --soft: #172a30; --code: #222a39;
  --accent: #3cbcc3; --accent-hover: #5fcdd3; --on-accent: #ffffff; --fill: #0d6b70; --fill-hover: #0b5b60;
  --done: #3cbcc3; --wait: #e2ab55; --stop: #e8806e; --run: #3cbcc3; --shadow: 0 6px 24px rgba(0, 0, 0, .35);
  color-scheme: dark;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font: 17px/1.55 var(--body); min-height: 100vh; }
a, .link { color: var(--accent); cursor: pointer; text-decoration: none; }
.link:hover { text-decoration: underline; }
button.link { background: none; border: 0; padding: 0; text-align: left; } button.link:not(.title) { font: inherit; }
button:focus-visible, a:focus-visible, textarea:focus-visible, select:focus-visible, input:focus-visible {
  outline: 3px solid var(--teal); outline-offset: 2px; border-radius: 4px; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 0 24px; }
code, .mono { font-family: var(--mono); font-size: .78em; }
code { background: var(--code); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }

/* the bar: the website's top bar, in either theme */
.topbar { position: sticky; top: 0; z-index: 20; background: var(--deep); color: var(--mist);
  border-bottom: 1px solid rgba(232, 234, 240, .08); }
.nav { display: flex; align-items: center; gap: 18px; padding: 12px 0; flex-wrap: wrap; }
.brand { display: flex; align-items: center; gap: 1ex; font: 700 19px var(--display); letter-spacing: -.3px; color: var(--mist); }
.brand svg { width: 2.13ex; height: 2.4ex; overflow: visible; transform: translateY(.1ex); }
.brand .tld { color: var(--teal); }
.brand .project { font: 400 13px var(--mono); color: rgba(232, 234, 240, .62); letter-spacing: .3px; margin-left: 4px; }
.tabs { display: flex; gap: 4px; margin-left: auto; overflow-x: auto; scrollbar-width: none; }
.tabs button { font: 400 13px var(--mono); letter-spacing: .4px; color: rgba(232, 234, 240, .72); background: none; border: 0;
  padding: 8px 10px; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.tabs button:hover { color: var(--teal); }
.tabs button[aria-selected="true"] { color: var(--mist); border-bottom-color: var(--teal); }
.tabs .n { display: inline-block; min-width: 18px; margin-left: 6px; padding: 0 5px; border-radius: 9px; background: var(--fill);
  color: #fff; font-size: 11px; text-align: center; }
.status { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font: 400 13px var(--mono); color: rgba(232, 234, 240, .8); }
.dot { width: 9px; height: 9px; border-radius: 50%; background: #8a93a3; display: inline-block; margin-right: 6px; }
.dot.up { background: var(--teal); box-shadow: 0 0 0 3px rgba(20, 143, 150, .25); }
.dot.stopping { background: #c9922e; } .dot.down { background: #8a93a3; }
.bar-btn { font: 500 13px var(--display); color: var(--mist); background: none; border: 1px solid rgba(232, 234, 240, .35);
  border-radius: 6px; padding: 5px 12px; cursor: pointer; }
.bar-btn:hover { border-color: var(--teal); color: var(--teal); }
.bar-btn.primary { background: var(--fill); border-color: var(--fill); color: var(--on-accent); }
.by { font: 400 13px var(--mono); color: var(--mist); background: rgba(232, 234, 240, .06); border: 1px solid rgba(232, 234, 240, .2);
  border-radius: 6px; padding: 4px 8px; width: 170px; }
.theme { display: inline-flex; border: 1px solid rgba(232, 234, 240, .25); border-radius: 6px; overflow: hidden; }
.theme button { font: 400 12px var(--mono); color: rgba(232, 234, 240, .7); background: none; border: 0; padding: 4px 8px; cursor: pointer; }
.theme button[aria-pressed="true"] { background: rgba(232, 234, 240, .14); color: var(--mist); }

/* a tab: the eyebrow and heading of a website section, then its cards */
main.wrap { padding-top: 40px; padding-bottom: 72px; }
.eyebrow { font: 400 12.5px var(--mono); letter-spacing: 2.5px; text-transform: uppercase; color: var(--accent); margin-bottom: 10px; }
h1 { font: 700 clamp(28px, 4vw, 38px)/1.1 var(--display); letter-spacing: -1px; }
.lede { margin-top: 10px; color: var(--muted); max-width: 44em; font-size: 18px; }
.next { margin-top: 26px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 14px 18px;
  border: 1px solid var(--line); border-left: 4px solid var(--teal); border-radius: 10px; background: var(--panel); }
.next .text { flex: 1 1 280px; font: 500 16px var(--display); }
.next .arrow { color: var(--accent); margin-right: 6px; }
.next.ended { border-left-color: var(--stop); } .next.ended .arrow { color: var(--stop); }
.card { margin-top: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 20px 22px; }
.card > h2 { font: 700 20px/1.25 var(--display); letter-spacing: -.3px; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.card > h2 .sub { font: 400 12.5px var(--mono); color: var(--muted); letter-spacing: .2px; }
.card > .about { color: var(--muted); margin-top: 6px; font-size: 16px; max-width: 48em; }
h3 { font: 600 15px var(--display); margin: 18px 0 6px; }
.drawer h2 { font: 600 16px var(--display); margin: 20px 0 6px; }
.sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
.prose { font-size: 16px; }
.prose p, .prose ul, .prose ol { margin: 0 0 8px; } .prose ul, .prose ol { padding-left: 1.3em; } .prose li { margin: 2px 0; }
.more { margin: 10px 0 6px; } .more summary { cursor: pointer; font: 500 14px var(--display); color: var(--accent); }
.more[open] summary { margin-bottom: 4px; }
.aside { margin-top: 18px; padding: 4px 14px 6px; border-left: 4px solid var(--wait); border-radius: 6px; background: var(--panel); }
.empty { color: var(--muted); font-style: italic; margin-top: 8px; }
.rec { color: var(--wait); font-size: 15px; margin-top: 4px; }

table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 16px; }
th { text-align: left; font: 500 11.5px var(--mono); letter-spacing: 1.2px; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding: 6px 8px; }
td { border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
.num { text-align: right; font-family: var(--mono); font-size: 13px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.id { font: 400 12.5px var(--mono); color: var(--muted); margin-top: 2px; overflow-wrap: anywhere; }
.title { font: 500 16.5px var(--display); }
.mark { font: 700 15px var(--display); display: inline-block; width: 1.3em; text-align: center; }
.m-done { color: var(--done); } .m-look, .m-question { color: var(--wait); } .m-stopped { color: var(--stop); }
.m-running, .m-next { color: var(--run); } .m-none { color: var(--muted); }
.state { font: 400 12px var(--mono); padding: 2px 8px; border-radius: 999px; background: var(--code); white-space: nowrap; }
.st-queued { color: var(--accent); } .st-running { color: var(--run); } .st-waiting { color: var(--wait); } .st-failed { color: var(--stop); }

.btn { font: 500 14px var(--display); padding: 7px 14px; border-radius: 8px; border: 1px solid var(--line); background: var(--panel);
  color: var(--ink); cursor: pointer; white-space: nowrap; }
.btn:hover { border-color: var(--teal); color: var(--accent); }
.btn.primary { background: var(--fill); border-color: var(--fill); color: var(--on-accent); }
.btn.primary:hover { background: var(--fill-hover); border-color: var(--fill-hover); color: var(--on-accent); }
.btn.danger:hover { border-color: var(--stop); color: var(--stop); }
.btn:disabled { opacity: .5; cursor: default; }
.acts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }
td .acts { margin-top: 0; justify-content: flex-end; }
.ask { display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; margin-top: 12px; }
.ask textarea { flex: 1 1 320px; min-height: 72px; resize: vertical; font: 17px/1.5 var(--body); color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.ask select { font: 400 13px var(--mono); color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.option { display: flex; gap: 12px; align-items: baseline; padding: 8px 0; border-bottom: 1px solid var(--line); }
.option:last-child { border-bottom: 0; }
.option .btn { min-width: 2.6em; }
.nowrap { white-space: nowrap; }
.hint { font: 400 12.5px var(--mono); color: var(--muted); }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin-top: 12px; font-size: 16px; }
.kv dt { font: 400 12.5px var(--mono); color: var(--muted); padding-top: 3px; }
pre.out { font: 12.5px/1.5 var(--mono); background: var(--code); border-radius: 8px; padding: 12px; max-height: 460px; overflow: auto;
  white-space: pre-wrap; word-break: break-word; margin-top: 12px; }
pre.out:empty { display: none; }
.step b { font: 600 14px var(--display); color: var(--accent); margin-right: 6px; }

.banner { display: none; background: var(--stop); color: #fff; font: 500 14px var(--display); padding: 8px 0; }
#toasts { position: fixed; right: 16px; bottom: 16px; z-index: 40; display: flex; flex-direction: column; gap: 8px; max-width: min(440px, calc(100% - 32px)); }
.toast { background: var(--panel); color: var(--ink); border: 1px solid var(--line); border-left: 4px solid var(--teal); border-radius: 8px;
  padding: 10px 14px; box-shadow: var(--shadow); font-size: 15px; white-space: pre-wrap; }
.toast.err { border-left-color: var(--stop); }
.drawer { position: fixed; inset: var(--bar, 0px) 0 0 auto; width: min(760px, 100%); z-index: 15; background: var(--bg); border-left: 1px solid var(--line);
  box-shadow: var(--shadow); overflow-y: auto; padding: 24px; }
.drawer .close { float: right; }
@media (max-width: 760px) {
  .wrap { padding: 0 16px; }
  .tabs { order: 3; width: 100%; margin-left: 0; }
  .hide-s { display: none; }
  td, th { padding: 8px 4px; }
  .by { width: 100px; }
  /* a row with buttons: its cells side by side, the buttons on a line of their own beneath */
  tr:has(> td.act) { display: grid; grid-template-columns: auto 1fr fit-content(40%); border-bottom: 1px solid var(--line); }
  tr:has(> td.act) > td { border-bottom: 0; } tr:has(> td.act) > td.hide-s { display: none; }
  td.act { grid-column: 1 / -1; padding-top: 0; } td.act:has(> .acts:empty) { display: none; } td.act .acts { justify-content: flex-start; }
  table:has(td.act) tr:has(> th) { display: none; }
}
</style>
</head>
<body>
<header class="topbar" id="topbar">
  <div class="wrap nav">
    <div class="brand">__MARK__<span>factory<span class="tld">.</span></span><span class="project" id="project"></span></div>
    <nav class="tabs" id="tabs" role="tablist" aria-label="the cycle"></nav>
    <div class="status">
      <span id="worker"><span class="dot"></span>…</span>
      <button class="bar-btn primary" data-call="up" id="up" hidden>up</button>
      <button class="bar-btn" data-call="down" id="down" hidden>down</button>
      <label>as <input class="by" id="by" type="text" autocomplete="name" aria-label="your name"></label>
      <span class="theme" role="group" aria-label="theme">
        <button data-pick="light" aria-pressed="false">light</button><button data-pick="auto" aria-pressed="false">auto</button><button data-pick="dark" aria-pressed="false">dark</button>
      </span>
    </div>
  </div>
</header>
<div class="banner" id="banner" role="alert"><div class="wrap" id="banner-text"></div></div>
<main class="wrap" id="main"></main>
<div id="toasts" aria-live="polite"></div>
<aside class="drawer" id="drawer" aria-label="story" tabindex="-1" hidden></aside>
<script>
"use strict";
const TOKEN = new URLSearchParams(location.search).get("t") || "";
const TABS = [
  ["describe", "0 describe", "Once", "The project description", "What is built, how, and in which domain — written once, changed when things move."],
  ["discover", "1 discover", "Cycle", "Discovery", "Which problem is worth solving — a report with its sources and the epics it proposes."],
  ["backlog", "2 backlog", "Cycle", "Backlog", "Epics and their stories, newest first. A story runs once released."],
  ["run", "3 run", "Cycle", "The factory at work", "Your requests first, then the stories — one stage after the other, a gate between them."],
  ["decide", "4 decide", "Cycle", "Waiting for you", "A question a stage may not decide alone, or a result to look at."],
  ["delivered", "5 delivered", "Cycle", "Delivered", "What the factory delivered, the newest first."]];
const MARKS = {look: "!", question: "?", stopped: "✗", running: "▶", done: "✓", none: "·", next: "→"};
const S = {tab: "backlog", status: null, decisions: null, discover: null, requests: null, follow: null, followSource: null,
           followLines: [], drawer: null, opener: null, drafts: {}, folded: {}};
const stored = key => { try { return localStorage.getItem(key) || ""; } catch (e) { return ""; } };
const store = (key, value) => { try { localStorage.setItem(key, value); } catch (e) {} };
S.tab = stored("factory.tab") || S.tab;
if (TABS.some(([id]) => id === location.hash.slice(1))) S.tab = location.hash.slice(1);

// --- helpers -------------------------------------------------------------------------------------------------------
const $ = id => document.getElementById(id);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const mark = m => `<span class="mark m-${esc(m)}" aria-hidden="true">${esc(MARKS[m] || "·")}</span>`;
// a section's markdown as the website sets it: paragraphs, lists, `code` and **strong** — escaped first
const inline = text => esc(text).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
function prose(text) {
  const out = [];
  let para = [], list = null;
  const endPara = () => { if (para.length) out.push(`<p>${inline(para.join(" "))}</p>`); para = []; };
  const endList = () => { if (list) out.push(`<${list.tag}>${list.items.map(i => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; };
  for (const line of String(text || "").split("\n")) {
    const item = line.match(/^\s*(?:([-*])|\d+\.)\s+(.*)$/);
    if (item) {
      endPara();
      const tag = item[1] ? "ul" : "ol";
      if (list && list.tag !== tag) endList();
      list = list || {tag, items: []};
      list.items.push(item[2]);
    } else if (!line.trim()) { endPara(); endList(); }
    else if (list && /^\s/.test(line)) list.items[list.items.length - 1] += " " + line.trim();
    else { endList(); para.push(line.trim()); }
  }
  endPara(); endList();
  return `<div class="prose">${out.join("")}</div>`;
}
// one of the factory's sections; one with a kind (why a story is not built) set apart in the wait colour
const section = (s, h = 3) => s.kind ? `<div class="aside"><h${h}>${esc(s.heading || s.kind)}</h${h}>${prose(s.text)}</div>`
  : `${s.heading ? `<h${h}>${esc(s.heading)}</h${h}>` : ""}${prose(s.text)}`;
const story = (id, title) => `<button type="button" class="link title" data-story="${esc(id)}">${esc(title || id)}</button>`;
const by = () => $("by").value.trim();

async function api(path, body) {
  const options = {headers: {"X-Factory-Token": TOKEN}};
  if (body !== undefined) Object.assign(options, {method: "POST", body: JSON.stringify(body),
    headers: {"X-Factory-Token": TOKEN, "Content-Type": "application/json"}});
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch (e) { data = {error: "no JSON from " + path}; }
  if (!response.ok) throw new Error(data.error || data.output || "HTTP " + response.status);
  return data;
}

function toast(text, isError) {
  const node = document.createElement("div");
  node.className = "toast" + (isError ? " err" : "");
  node.textContent = text;
  $("toasts").appendChild(node);
  setTimeout(() => node.remove(), isError ? 9000 : 4500);
}

function banner(text) {
  $("banner-text").textContent = text || "";
  $("banner").style.display = text ? "block" : "none";
}

// --- actions: the factory's, drawn as given ------------------------------------------------------------------------
// An action carries its label, whether it is the one to press, and the request it writes; `open` says what the person
// still gives — their words (a form), or an answer under Decide; one whose request is written already says so
// (`queued`). One without a request is no press on this page.
const ACTIONS = {};
let actionCount = 0;
function act(action, scope) {
  if (!action || !action.request) return "";
  if (action.waits_on) return "";                       // another choice of the same record is on its way
  if (action.queued) return `<span class="state st-queued" title="request ${esc(action.queued)}">${esc(action.label)} — ${esc(action.queued_text || "queued")}</span>`;
  const id = `${scope || "m"}${++actionCount}`;
  ACTIONS[id] = action;
  const r = action.request, cls = `btn${action.primary ? " primary" : ""}`;
  if (r.open === "words") {
    const choices = (r.choices || []).length ? `<select aria-label="why"><option value="">why? (optional)</option>${r.choices.map(c => `<option>${esc(c)}</option>`).join("")}</select>` : "";
    // what the person typed outlives a redraw: kept by the action's command, until its request is written
    return `<div class="ask" data-ask="${id}"><textarea data-draft="${esc(action.skill)}" placeholder="${esc(action.text)}" aria-label="${esc(action.label)}">${esc(S.drafts[action.skill] || "")}</textarea>${choices}
      <button class="${cls}" data-press="${id}">${esc(action.label)}</button></div>`;
  }
  if (r.open === "record") return `<button class="${cls}" data-tab="decide">${esc(action.label)}</button>`;
  return `<button class="${cls}" data-press="${id}" title="${esc(action.text)}">${esc(action.label)}</button>`;
}
const acts = (list, scope) => (list || []).map(a => act(a, scope)).join("");
function forget(scope) { for (const key of Object.keys(ACTIONS)) if (key[0] === scope) delete ACTIONS[key]; }

async function press(button) {
  const action = ACTIONS[button.dataset.press];
  if (!action) return;
  const r = action.request, box = button.closest("[data-ask]"), fields = Object.assign({}, r.fields);
  let words = r.words || "";
  if (box) {
    words = box.querySelector("textarea").value.trim();
    const pick = box.querySelector("select");
    if (pick && pick.value) fields.option = pick.value;
    if (!words) { toast(`${action.label}: ${action.text}`, true); return; }
  }
  try {
    const data = await api("/api/request", Object.assign({kind: r.kind, words, by: by()}, fields));
    toast(data.duplicate ? `queued already: ${data.id}` : `request written: ${data.id}`);
    if (box) { box.querySelector("textarea").value = ""; delete S.drafts[action.skill]; }
    refresh();
    if (S.drawer) openStory(S.drawer);
  } catch (e) { toast(e.message, true); }
}
document.addEventListener("input", event => {
  if (event.target.dataset && event.target.dataset.draft !== undefined) S.drafts[event.target.dataset.draft] = event.target.value;
});

// what the page itself calls: the factory up and down, a request taken back or queued again, an output followed
const CALLS = {
  async up() { const d = await api("/api/up", {by: by()}); toast(d.output || "up"); },
  async down(node) {
    const now = node.dataset.now === "1";
    if (now && !confirm("Interrupt the running stage too? Its work so far stays; the stage runs again later.")) return;
    const d = await api("/api/down", {by: by(), now}); toast(d.output || "stopping");
  },
  async drop(node) {
    if (!confirm(`Take request ${node.dataset.id} back?`)) return;
    await api("/api/requests/drop", {id: node.dataset.id}); toast("taken back");
  },
  async retry(node) { await api("/api/requests/retry", {id: node.dataset.id}); toast("queued again"); },
  async follow(node) { follow(node.dataset.kind, node.dataset.id); },
  async unfollow() { follow(null); },
  async close() { S.drawer = null; $("drawer").hidden = true; forget("d"); if (S.opener && document.contains(S.opener)) S.opener.focus(); S.opener = null; },
};

document.addEventListener("click", async event => {
  const target = event.target.closest("[data-press],[data-call],[data-story],[data-tab],[data-pick]");
  if (!target) return;
  if (target.dataset.pick) return theme(target.dataset.pick);
  if (target.dataset.tab) return show(target.dataset.tab);
  if (target.dataset.story) return openStory(target.dataset.story);
  target.disabled = true;
  try {
    if (target.dataset.press) await press(target);
    else { await CALLS[target.dataset.call](target); refresh(); }
  } catch (e) { toast(e.message, true); }
  finally { target.disabled = false; }
});

// --- the theme: the person's choice over the system's ----------------------------------------------------------------
function theme(choice) {
  store("factory.theme", choice);
  if (choice === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", choice);
  document.querySelectorAll(".theme button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.pick === choice)));
}

// --- loading -------------------------------------------------------------------------------------------------------
async function load(name, path) {
  try { S[name] = await api(path); return true; }
  catch (e) { banner(`${name}: ${e.message}`); return false; }
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
    if ((await Promise.all(jobs)).every(Boolean)) banner("");
    if (slow) lastSlow = Date.now();
    render();
  } finally { refreshing = false; }
}

// --- the frame -----------------------------------------------------------------------------------------------------
function show(tab) {
  if (S.drawer) CALLS.close();
  S.tab = tab;
  store("factory.tab", tab);
  history.replaceState(null, "", "#" + tab);
  render();
  window.scrollTo(0, 0);
}

function renderFrame() {
  const st = S.status || {}, w = st.worker, counts = (S.requests || {}).counts || {};
  $("project").textContent = st.project || "";
  document.title = (st.project ? st.project + " — " : "") + "factory";
  const dot = !w || !w.alive ? "down" : w.stopping ? "stopping" : "up";
  const queued = (S.requests || {}).counts_text;
  $("worker").innerHTML = `<span class="dot ${dot}"></span>${esc(st.worker_text || "…")}${queued ? ` · ${esc(queued)}` : ""}`;
  $("worker").title = w ? `${w.owner} since ${w.since_text}` : "nobody holds the checkout";
  $("up").hidden = !!(w && w.alive);
  $("down").hidden = !(w && w.alive) || w.stopping;
  $("tabs").innerHTML = TABS.map(([id, label]) => {
    const n = id === "decide" ? (st.waiting || []).length : id === "run" ? (counts.failed || 0) : 0;
    return `<button role="tab" data-tab="${id}" aria-selected="${S.tab === id}">${esc(label)}${n ? `<span class="n">${n}</span>` : ""}</button>`;
  }).join("");
}

function render() {
  renderFrame();
  const editing = document.activeElement && ["TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
    && $("main").contains(document.activeElement);
  if (editing) return;                                   // a person typing is not redrawn under their hands
  forget("m");
  const [, , eyebrow, title, lede] = TABS.find(([id]) => id === S.tab) || TABS[2];
  const view = {describe, discover, backlog, run, decide, delivered}[S.tab] || backlog;
  $("main").innerHTML = `<div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p class="lede">${esc(lede)}</p>`
    + (S.status ? endedLine(S.status) + view(S.status) : `<section class="card"><p class="empty">Reading the factory…</p></section>`);
  if (S.tab === "run") paintFollow();
}

// on every tab: the factory that ended on its own, and why
function endedLine(st) {
  const gone = st.ended;
  return gone ? `<div class="next ended"><div class="text"><span class="arrow">!</span>${esc(gone.text)}${gone.log ? ` <span class="hint">${esc(gone.log)}</span>` : ""}</div>
    <button class="btn primary" data-call="up">up</button></div>` : "";
}

function nextLine(st) {
  const nx = st.next;
  if (!nx) return "";
  return `<div class="next"><div class="text"><span class="arrow">→</span>${esc(nx.text)}</div>${act(nx.action)}</div>`;
}

function card(title, sub, body) {
  const head = title ? `<h2>${title}${sub ? ` <span class="sub">${sub}</span>` : ""}</h2>` : "";
  return `<section class="card">${head}${body}</section>`;
}

// --- 0 describe ----------------------------------------------------------------------------------------------------
function describe(st) {
  const parts = (st.description || []).map(p => `<tr><td>${mark(p.mark)}</td>
    <td><div class="title">${esc(p.part)}</div><div class="id">${esc(p.path)}</div></td>
    <td>${p.present ? esc((p.sections || []).join(" · ")) : `<span class="empty">missing</span>`}
    ${(p.missing || []).length ? `<div class="rec">missing: ${esc(p.missing.join(", "))}</div>` : ""}
    ${(p.empty || []).length ? `<div class="rec">empty: ${esc(p.empty.join(", "))}</div>` : ""}</td></tr>`).join("");
  return card("The parts", "", `<table><tr><th><span class="sr">state</span></th><th>part</th><th>sections</th></tr>${parts}</table>`)
    + card("Change the description", "", `<p class="about">In your words — <code>&lt;part&gt;: &lt;change&gt;</code> where it is one part. Where it needs a decision of yours, it asks under Decide.</p>${act((st.entries || {}).describe)}`);
}

// --- 1 discover ----------------------------------------------------------------------------------------------------
function discover(st) {
  const topics = (S.discover || {}).topics || [];
  const cards = topics.map(t => {
    const proposals = t.proposals.map(p => `<tr><td><div class="title">${esc(p.goal || p.intent || p.id)}</div><div class="id">${esc(p.id)}</div></td>
      <td>${esc(p.metric)}</td><td>${p.epic ? `<span class="hint">epic ${esc(p.epic)}</span>` : `<div class="acts">${acts(p.actions)}</div>`}</td></tr>`).join("");
    const changes = t.description_changes.map(c => `<tr><td><div class="title">${esc(c.target)}</div></td>
      <td>${esc(c.change)}<div class="id">${esc(c.why)}</div></td><td class="act"><div class="acts">${acts(c.actions)}</div></td></tr>`).join("");
    return card(esc(t.title), esc(t.report),
      (proposals ? `<table><tr><th>proposal</th><th>outcome event</th><th><span class="sr">actions</span></th></tr>${proposals}</table>` : `<p class="empty">No proposed work.</p>`)
      + (changes ? `<h3>Changes to the description</h3><table>${changes}</table>` : ""));
  }).join("");
  return card("A new discovery", "", act((st.entries || {}).discover))
    + (cards || card("", "", `<p class="empty">No discovery yet — it goes to ${esc((S.discover || {}).store || "")}.</p>`));
}

// --- 2 backlog -----------------------------------------------------------------------------------------------------
function storyRow(r) {
  return `<tr><td>${mark(r.mark)}</td><td>${story(r.story, r.title)}<div class="id">${esc(r.story)}</div></td>
    <td>${esc(r.state)}</td><td class="hide-s">${esc(r.stage === "—" ? "" : r.stage)}</td>
    <td class="num hide-s">${esc(r.tokens_text)}</td><td class="act"><div class="acts">${acts(r.actions)}</div></td></tr>`;
}

function backlog(st) {
  const epics = (st.epics || []).map(e => card(esc(e.title || e.epic),
    `${esc(e.epic)} · ${e.delivered}/${e.total} delivered${e.metric ? " · " + esc(e.metric) : ""}`,
    (e.goal ? `<p class="about">${esc(e.goal)}</p>` : "")
    + ((st.journeys || []).filter(j => j.epic === e.epic).map(j => `<p class="rec">${esc(j.text)}</p>`).join(""))
    + (e.rows.length ? `<table><tr><th><span class="sr">mark</span></th><th>story</th><th>state</th><th class="hide-s">stage</th><th class="num hide-s">tokens</th><th><span class="sr">actions</span></th></tr>${e.rows.map(storyRow).join("")}</table>` : `<p class="empty">No story yet.</p>`)
    + `<div class="acts">${acts(e.actions)}</div>`)).join("");
  const findings = (st.findings || []).map(f => `<tr><td><span class="state">${esc(f.severity)}</span></td>
    <td>${esc(f.plain || f.defect)}<div class="id">${esc(f.row)} · ${esc(f.where)}</div></td><td class="act"><div class="acts">${act(f.action)}</div></td></tr>`).join("");
  return nextLine(st) + card("A wish", "your words become a story, kept as a draft until you release it", act((st.entries || {}).wish))
    + (epics || card("", "", `<p class="empty">The backlog is empty.</p>`))
    + (findings ? card("Findings", "what the judge kept open", `<table>${findings}</table>`) : "");
}

// --- 3 run ---------------------------------------------------------------------------------------------------------
function run(st) {
  const w = st.worker, reqs = (S.requests || {}).requests || [];
  const factory = w ? `<dl class="kv"><dt>worker</dt><dd>${esc(w.owner)}</dd><dt>state</dt><dd>${esc(st.worker_text)}</dd>
      <dt>since</dt><dd>${esc(w.since_text)}</dd>${w.log ? `<dt>log</dt><dd><code>${esc(w.log)}</code></dd>` : ""}</dl>
      ${w.alive && !w.stopping ? `<div class="acts"><button class="btn" data-call="down">down — after the running stage</button>
      <button class="btn danger" data-call="down" data-now="1">down now</button></div>` : ""}`
    : `<p class="about">The factory is down. Requests wait in the queue until it is up.</p><div class="acts"><button class="btn primary" data-call="up">up</button></div>`;
  const ops = r => (r.operations || []).map(op => `<button class="btn${op.name === "drop" ? " danger" : ""}" data-call="${esc(op.name)}"
    data-kind="request" data-id="${esc(r.id)}">${esc(op.label)}</button>`).join("");
  const requests = reqs.map(r => `<tr><td><span class="state st-${esc(r.state)}">${esc(r.state)}</span></td>
    <td><span class="title">${esc(r.kind)}</span> ${esc(r.target)}<div class="id">${esc(r.id)} · ${esc(r.by)}</div>
    ${r.error ? `<div class="m-stopped">${esc(r.error)}</div>` : ""}
    ${r.record ? `<div class="rec">asks: <code>${esc(r.record)}</code> — answer it under Decide</div>` : ""}</td>
    <td class="act"><div class="acts">${ops(r)}</div></td></tr>`).join("");
  const running = (st.running || []).map(r => `<tr><td>${mark(r.interrupted ? "stopped" : "running")}</td>
    <td class="nowrap">${story(r.story)}</td><td class="nowrap">${esc(r.stage)}${r.part ? " · " + esc(r.part) : ""}</td>
    <td class="hide-s nowrap">${esc(r.ago || "")}</td><td class="hide-s id">${esc(r.activity || "")}</td>
    <td class="act"><div class="acts"><button class="btn" data-call="follow" data-kind="story" data-id="${esc(r.story)}">follow</button></div></td></tr>`).join("");
  const ready = (st.rows || []).filter(r => st.queue && st.queue.ready.includes(r.story)).map(storyRow).join("");
  return nextLine(st) + card("The factory", "", factory)
    + card("Requests", "worked before the next story, oldest first", requests ? `<table>${requests}</table>` : `<p class="empty">No request waits.</p>`)
    + card("Running", "", (running ? `<table>${running}</table>` : `<p class="empty">No stage runs.</p>`)
      + (ready ? `<h3>Ready</h3><table>${ready}</table>` : ""))
    + card("Output", `<span id="follow-title"></span>`, `<div class="acts" id="follow-acts"></div><pre class="out" id="follow-out"></pre>`);
}

function follow(kind, id) {
  if (S.followSource) { S.followSource.close(); S.followSource = null; }
  S.follow = kind ? {kind, id} : null;
  S.followLines = [];
  if (kind) {
    const source = new EventSource(`/api/follow?${kind}=${encodeURIComponent(id)}&t=${encodeURIComponent(TOKEN)}`);
    source.onmessage = event => {
      try { S.followLines.push(JSON.parse(event.data)); } catch (e) { S.followLines.push(event.data); }
      if (S.followLines.length > 1500) S.followLines.splice(0, S.followLines.length - 1500);
      paintFollow();
    };
    source.addEventListener("end", () => { S.followLines.push("— the output ended —"); paintFollow(); source.close(); });
    S.followSource = source;
  }
  if (S.tab !== "run") show("run"); else paintFollow();
}

function paintFollow() {
  const out = $("follow-out");
  if (!out) return;
  $("follow-title").textContent = S.follow ? `${S.follow.kind} ${S.follow.id}` : "follow a running stage or request";
  $("follow-acts").innerHTML = S.follow ? `<button class="btn" data-call="unfollow">stop following</button>` : "";
  const atEnd = out.scrollTop + out.clientHeight >= out.scrollHeight - 20;
  out.textContent = S.followLines.join("\n") || (S.follow ? "waiting for output…" : "");
  if (atEnd) out.scrollTop = out.scrollHeight;
}

// --- 4 decide ------------------------------------------------------------------------------------------------------
function recordCard(r) {
  const offered = (r.actions || []).filter(a => !a.waits_on);
  const options = offered.filter(a => a.request.open !== "words" && r.kind !== "acceptance");
  const words = offered.filter(a => a.request.open === "words");
  const body = `<p class="hint">${esc(r.path)}${r.story ? ` · ${story(r.story, "the story")}` : ""}</p>`
    + ((r.sections || []).length ? `<details class="more" data-more="${esc(r.id)}"${S.folded[r.id] ? "" : " open"}><summary>${r.kind === "acceptance" ? "what to look at" : "the question in full"}</summary>${r.sections.map(one => section(one)).join("")}</details>` : "")
    + (r.kind === "acceptance"
      ? `<div class="acts">${acts(offered.filter(a => a.request.open !== "words"))}</div>`
      : options.map(a => `<div class="option">${act(a)}<span>${inline(a.text)}${a.note ? ` <span class="hint">— ${esc(a.note)}</span>` : ""}</span></div>`).join(""))
    + words.map(a => `<h3>${r.kind === "acceptance" ? "or correct it" : options.length ? "or in your words" : "your answer"}</h3>${act(a)}`).join("");
  return card(`${mark(r.kind === "acceptance" ? "look" : "question")} ${esc(r.text)}`, esc(`${r.story || "project"} · ${r.stage}`), body);
}

function decide(st) {
  const records = ((S.decisions || {}).records || []).filter(r => (r.actions || []).length);
  // a waiting story whose record is open stands above as that record; the others — a draft, a stopped story — here
  const others = (st.waiting || []).filter(w => !w.record).map(w => `<tr><td>${mark(w.mark)}</td>
    <td>${story(w.story)}</td><td>${esc(w.what)}</td>
    <td class="act"><div class="acts">${act(w.action) || `<span class="hint">${esc(w.action.text || w.action.skill || w.action.shell || "")}</span>`}</div></td></tr>`).join("");
  return records.map(recordCard).join("")
    + (others ? card(records.length ? "Also waiting for you" : "", "", `<table>${others}</table>`) : "")
    + (!records.length && !others ? card("", "", `<p class="empty">Nothing waits for you.</p>`) : "");
}

// --- 5 delivered ---------------------------------------------------------------------------------------------------
function delivered(st) {
  const rows = Object.fromEntries((st.rows || []).map(r => [r.story, r]));
  const list = (st.delivered_order || []).map(id => rows[id]).filter(Boolean).map(r => `<tr><td>${mark("done")}</td>
    <td>${story(r.story, r.title)}<div class="id">${esc(r.epic)} · ${esc(r.story)}</div></td>
    <td class="hide-s num">${esc(r.delivered_text)}</td><td class="num hide-s">${esc(r.seconds_text)}</td>
    <td class="num">${esc(r.tokens_text)}</td><td class="num hide-s">${esc(r.cost_text)}</td></tr>`).join("");
  return card(`${st.delivered} of ${st.total}`, [st.tokens_text && `${st.tokens_text} tokens`, st.seconds_text, st.cost_text].filter(Boolean).map(esc).join(" · "),
    list ? `<table><tr><th><span class="sr">mark</span></th><th>story</th><th class="hide-s num">delivered (UTC)</th><th class="num hide-s">worked</th><th class="num">tokens</th><th class="num hide-s">cost</th></tr>${list}</table>` : `<p class="empty">Nothing delivered yet.</p>`);
}

// --- one story -----------------------------------------------------------------------------------------------------
async function openStory(id) {
  if (!S.drawer) S.opener = document.activeElement;
  S.drawer = id;
  // below the bar, so the tabs and the factory's state stay in reach
  document.documentElement.style.setProperty("--bar", $("topbar").getBoundingClientRect().height + "px");
  const node = $("drawer"), close = `<button class="btn close" data-call="close">close</button>`;
  node.hidden = false;
  node.innerHTML = `${close}<p class="empty">Reading ${esc(id)}…</p>`;
  node.focus();
  let v;
  try { v = await api(`/api/view/story?id=${encodeURIComponent(id)}`); }
  catch (e) { node.innerHTML = `${close}<p class="m-stopped">${esc(e.message)}</p>`; return; }
  if (S.drawer !== id) return;
  forget("d");
  const row = v.row || {};
  // the factory's sections in its order, the scenarios where its criteria stood
  const scenarios = (v.scenarios || []).map(c => `<h3>${esc(c.title || c.key)}</h3>${c.rule ? `<p class="hint">${esc(c.rule)}</p>` : ""}
    ${(c.steps || []).map(s => `<div class="step"><b>${esc(s.word)}</b>${esc(s.text)}</div>`).join("")}`).join("");
  const list = v.sections || [], at = v.criteria_at == null ? list.length : v.criteria_at;
  const sections = list.slice(0, at).map(one => section(one, 2)).join("") + (scenarios ? `<h2>Scenarios</h2>${scenarios}` : "")
    + list.slice(at).map(one => section(one, 2)).join("");
  const stages = Object.entries(v.stages || {}).map(([name, e]) => `<tr><td>${esc(name)}</td><td class="num">${e.runs || ""}</td>
    <td class="num">${esc(e.seconds_text)}</td><td class="num">${esc(e.tokens_text)}</td><td class="num hide-s">${esc(e.cost_text)}</td><td class="id">${esc(e.why || "")}</td></tr>`).join("");
  node.innerHTML = `${close}<div class="eyebrow">${esc(v.epic)}</div><h1>${mark(row.mark || "none")} ${esc(v.title || id)}</h1>
    <dl class="kv"><dt>story</dt><dd class="mono">${esc(id)}</dd><dt>state</dt><dd>${esc(row.state || v.situation || "")}</dd>
      ${v.context ? `<dt>context</dt><dd>${esc(v.context)}</dd>` : ""}<dt>file</dt><dd><code>${esc(v.path)}</code></dd>
      ${row.tokens_text ? `<dt>tokens</dt><dd>${esc(row.tokens_text)}${row.cost_text ? " · " + esc(row.cost_text) : ""}</dd>` : ""}</dl>
    <div class="acts">${acts((v.actions || []).filter(a => a.request.open !== "words"), "d")}<button class="btn" data-call="follow" data-kind="story" data-id="${esc(id)}">output</button></div>
    ${(v.actions || []).filter(a => a.request.open === "words" && !a.waits_on).map(a => `<h2>${esc(a.label)}</h2>${act(a, "d")}`).join("")}
    ${sections}
    ${stages ? `<h2>Processes</h2><table><tr><th>process</th><th class="num">runs</th><th class="num">time</th><th class="num">tokens</th><th class="num hide-s">cost</th><th>why</th></tr>${stages}</table>` : ""}`;
}

// --- start ---------------------------------------------------------------------------------------------------------
// a record's text folded by the person stays folded through the next redraw
document.addEventListener("toggle", event => {
  const more = event.target.closest && event.target.closest("[data-more]");
  if (more) S.folded[more.dataset.more] = !more.open;
}, true);

document.addEventListener("keydown", event => {
  if (event.target.closest("textarea, input, select")) return;
  const tab = TABS.find(([, label]) => label[0] === event.key);
  if (tab) show(tab[0]);
  if (event.key === "Escape") CALLS.close();
});
window.addEventListener("hashchange", () => {
  const tab = location.hash.slice(1);
  if (tab !== S.tab && TABS.some(([id]) => id === tab)) show(tab);
});
theme(stored("factory.theme") || "auto");
(async () => {
  if (!TOKEN) { banner("This page needs the token `factory.sh serve` printed — open that URL."); return; }
  try { $("by").value = stored("factory.by") || (await api("/api/meta")).by || ""; } catch (e) { banner(e.message); }
  $("by").addEventListener("change", () => store("factory.by", by()));
  await refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 5000);
})();
</script>
</body>
</html>
""".replace("__MARK__", MARK)


#: The page's one script as its Content-Security-Policy names it: no other script runs, an injected one included.
SCRIPT_HASH = "sha256-" + base64.b64encode(hashlib.sha256(
    re.search(r"<script>(.*?)</script>", PAGE, re.S).group(1).encode("utf-8")).digest()).decode("ascii")
