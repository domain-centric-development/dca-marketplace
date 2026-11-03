r"""The page's script, its core (WP-180): the state, the reading, the presses, the drawing and the keys.

It writes no markup of its own: what it puts on screen it asks of the components (`page_ui.py`). A fold is the one
accordion's, kept in `S.fold` by its key; the scheme is always resolved (`data-scheme` is `light` or `dark` on the
root), so a theme writes at most two blocks; a logo the theme names replaces the mark.
"""

SCRIPT_CORE = r"""
"use strict";
const TOKEN = new URLSearchParams(location.search).get("t") || "";
// the views in the order of their keys (0 … 6, the cockpit's); which part each sits in — once, inflow, the cycle, to look
// up — comes from the factory (`help`'s parts)
const TABS = [
  ["describe", "The project description", "What is built, how, and in which domain — and in each context what holds today. You write the description; what holds changes by a story the gate delivers."],
  ["discover", "Discovery", "Which problem is worth solving — a report with its sources and the epics it proposes."],
  ["backlog", "Backlog", "Epics and their stories, newest first — from a discovery, a wish, a judge's finding or a delivered epic's journey. A story runs once released."],
  ["run", "The factory at work", "Your requests at once, while this page is open; the backlog's stories while it is started — one stage after the other, a gate between them."],
  ["decide", "Waiting for you", "A question a stage may not decide alone, or a result to look at."],
  ["delivered", "Delivered", "What the factory delivered, the newest first."],
  ["rules", "The rules", "What the gate checks, what the runner decides and what each stage is told — per stage of a story, the gates between them. Pick a rule to read it; pick a story to see which fired."]];
const NOW = ["now", "Where it stands", "The cycle a story turns through — how many stand where, and the one that matters most in each."];
const GALLERY = ["components", "The page's components", "Every component of this page in its variants and states, by level — atoms, molecules, organisms, templates. It shows the theme this project gives the page."];
const MARKS = {look: "!", question: "?", stopped: "✗", running: "▶", done: "✓", none: "", next: "→"};             // no state is no mark
// the marks are the drawing's: a gate's check for a pass, a stop's cross for a fail, a pause where a person answers
const ICONS = {
  pass: '<path d="M6 10.4l2.7 2.7L14.2 7.6"/>', fail: '<path d="M6.6 6.6l6.8 6.8M13.4 6.6l-6.8 6.8"/>',
  wait: '<path d="M8 6.5v7M12 6.5v7"/>', ask: '<path d="M7.6 7.6a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.6M10 14.4v.1"/>'};
const S = {tab: "now", help: null, status: null, decisions: null, discover: null, requests: null, follow: null, followSource: null,
           followLines: [], drawer: null, opener: null, drafts: {}, fold: new Map(),
           rules: null, rulesFor: null, ruleKind: "story", ruleStory: "", flowPick: null, partText: {}, meta: {}};
const stored = key => { try { return localStorage.getItem(key) || ""; } catch (e) { return ""; } };
const store = (key, value) => { try { localStorage.setItem(key, value); } catch (e) {} };
// the page opens where it stands; a link to a view opens that view
const known = id => id === "now" || id === "components" || TABS.some(([t]) => t === id);
if (known(location.hash.slice(1))) S.tab = location.hash.slice(1);
if (location.hash === "#spec" || S.tab === "spec") S.tab = "describe";                // what holds is part of the description
// `#rules:<story>[:<rule>]` opens the rules with that story's gate runs marked, and the rule read
if (location.hash.startsWith("#rules:")) {
  const [story, rule] = decodeURIComponent(location.hash.slice(7)).split(":");
  [S.tab, S.ruleStory] = ["rules", story || ""];
  if (rule) S.fold.set("rule:" + rule, true);
}

// --- helpers -------------------------------------------------------------------------------------------------------
const $ = id => document.getElementById(id);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
// a section's markdown as the website sets it: paragraphs, lists, `code` and **strong** — escaped first
// code first, as markdown reads it — `x`, and ``x`` that may hold a backtick —, bold only outside it
const inline = text => String(text == null ? "" : text).split(/(``.+?``|`[^`]+`)/).map((part, i) => i % 2
  ? `<code>${esc(part.startsWith("``") ? part.slice(2, -2).trim() : part.slice(1, -1))}</code>`
  : esc(part).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")).join("");
function markdown(text) {
  // the markdown a person writes in a description, a record or a story: paragraphs, lists, tables, code, headings
  const out = [];
  let para = [], list = null, table = null, code = null;
  const endPara = () => { if (para.length) out.push(`<p>${inline(para.join(" "))}</p>`); para = []; };
  const endList = () => { if (list) out.push(`<${list.tag}>${list.items.map(i => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; };
  const cells = row => row.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
  const endTable = () => {
    if (!table) return;
    const [head, ...rows] = table.filter(r => !/^\s*\|?\s*:?-{2,}/.test(r));
    out.push(`<table><tr>${cells(head).map(c => `<th>${inline(c)}</th>`).join("")}</tr>`
      + rows.map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") + `</table>`);
    table = null;
  };
  const endAll = () => { endPara(); endList(); endTable(); };
  for (const line of String(text || "").split("\n")) {
    if (code) { if (/^\s*```/.test(line)) { out.push(`<pre>${esc(code.join("\n"))}</pre>`); code = null; } else code.push(line); continue; }
    if (/^\s*```/.test(line)) { endAll(); code = []; continue; }
    if (/^\s*\|/.test(line)) { endPara(); endList(); (table = table || []).push(line); continue; }
    endTable();
    const heading = line.match(/^#{3,6}\s+(.*)$/);
    const item = line.match(/^\s*(?:([-*])|\d+\.)\s+(.*)$/);
    if (heading) { endAll(); out.push(`<h4>${inline(heading[1])}</h4>`); }
    else if (item) {
      endPara();
      const tag = item[1] ? "ul" : "ol";
      if (list && list.tag !== tag) endList();
      list = list || {tag, items: []};
      list.items.push(item[2]);
    } else if (!line.trim()) { endPara(); endList(); }
    else if (list && /^\s/.test(line)) list.items[list.items.length - 1] += " " + line.trim();
    else { endList(); para.push(line.trim()); }
  }
  if (code) out.push(`<pre>${esc(code.join("\n"))}</pre>`);
  endAll();
  return out.join("");
}
const by = () => $("by").value.trim();
const money = n => n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${Math.round(n)}`;
const count = n => n >= 1e9 ? `${(n / 1e9).toFixed(1)} G` : n >= 1e6 ? `${(n / 1e6).toFixed(0)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(0)} k` : `${n}`;
function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v || 1))); return [1, 2, 2.5, 5, 10].map(m => m * p).find(m => m >= v) || v; }

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
  $("toasts").insertAdjacentHTML("beforeend", ui.toast(text, isError));
  const node = $("toasts").lastElementChild;
  setTimeout(() => node.remove(), isError ? 9000 : 4500);
}

function banner(text) {
  $("banner-text").textContent = text || "";
  $("banner").hidden = !text;
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
  if (action.queued) return ui.state(`${action.label} — ${action.queued_text || "queued"}`, "queued", {title: `request ${action.queued}`});
  const id = `${scope || "m"}${++actionCount}`;
  ACTIONS[id] = action;
  // a press that has an agent write something new says so before it is pressed: ✦ on the button, words in its title
  const r = action.request, look = {primary: action.primary, write: action.creates};
  const said = [action.creates ? "an agent writes this, in the factory's queue" : "", action.text].filter(Boolean).join(" — ");
  if (r.open === "words") {
    // what the person typed outlives a redraw: kept by the action's command, until its request is written
    const draft = r.draft || action.skill;
    return ui.ask(Object.assign({id, draft, label: action.label, text: action.text, title: said, value: S.drafts[draft] || "",
                                 choices: r.choices}, look));
  }
  if (r.open === "record") return ui.btn(action.label, Object.assign({attrs: {"data-tab": "decide"}}, look));
  return ui.btn(action.label, Object.assign({title: said, attrs: {"data-press": id}}, look));
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
    if (r.prefix) words = `${r.prefix}\n\n${words}`;
  }
  try {
    const data = await api("/api/request", Object.assign({kind: r.kind, words, by: by()}, fields));
    toast(data.duplicate ? `queued already: ${data.id}`
      : r.kind === "wish" ? "✦ your wish is being written as a draft — it shows below the field" : `request written: ${data.id}`);
    if (box) { box.querySelector("textarea").value = ""; delete S.drafts[r.draft || action.skill]; }
    refresh();
    if (S.drawer) openStory(S.drawer);
  } catch (e) { toast(e.message, true); }
}
document.addEventListener("input", event => {
  if (event.target.dataset && event.target.dataset.draft !== undefined) S.drafts[event.target.dataset.draft] = event.target.value;
});
document.addEventListener("change", event => {
  if (!event.target.dataset || event.target.dataset.overlay === undefined) return;
  S.ruleStory = event.target.value;
  event.target.blur();                                   // a focused select holds the redraw back
  loadRules();
});

// what the page itself calls: the backlog started and stopped, a request taken back or queued again, an output followed
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
  async hide(node) { await api("/api/requests/drop", {id: node.dataset.id}); toast("hidden — the draft stays in the backlog"); },
  async follow(node) { follow(node.dataset.kind, node.dataset.id); },
  async unfollow() { follow(null); },
  async close() { S.drawer = null; $("drawer").hidden = true; forget("d"); if (S.opener && document.contains(S.opener)) S.opener.focus(); S.opener = null; },
};

document.addEventListener("click", async event => {
  const target = event.target.closest("[data-press],[data-call],[data-story],[data-tab],[data-pick],[data-flow],[data-filter]");
  if (!target) return;
  if (target.dataset.flow) { S.ruleKind = target.dataset.flow; return render(); }
  if (target.dataset.filter) { S.backlogFilter = target.dataset.filter; forgetFolds("epic:"); return render(); }
  if (target.dataset.pick) return scheme(target.dataset.pick);
  if (target.dataset.tab) return show(target.dataset.tab);
  if (target.dataset.story) return openStory(target.dataset.story);
  target.disabled = true;
  try {
    if (target.dataset.press) await press(target);
    else { await CALLS[target.dataset.call](target); refresh(); }
  } catch (e) { toast(e.message, true); }
  finally { target.disabled = false; }
});

// --- folds: one accordion, its state by key; what the person opened stays open through every redraw ----------------
const opened = (key, otherwise = false) => S.fold.has(key) ? S.fold.get(key) : otherwise;
function forgetFolds(prefix) { for (const key of [...S.fold.keys()]) if (key.startsWith(prefix)) S.fold.delete(key); }
// a part of the description is read again each time it opens
const ON_OPEN = {part: name => { delete S.partText[name]; }};
document.addEventListener("click", event => {
  const head = event.target.closest && event.target.closest("[data-fold-toggle]");
  if (!head) return;
  event.stopPropagation();
  const key = head.dataset.foldToggle, open = head.getAttribute("aria-expanded") !== "true";
  S.fold.set(key, open);
  const [kind, ...rest] = key.split(":");
  if (open && ON_OPEN[kind]) ON_OPEN[kind](rest.join(":"));
  render();
}, true);

// --- the scheme: the person's choice over the system's, always resolved to light or dark ---------------------------
const SYSTEM = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
function scheme(choice) {
  store("factory.scheme", choice);
  const root = document.documentElement;
  root.setAttribute("data-scheme", choice === "auto" ? (SYSTEM && SYSTEM.matches ? "dark" : "light") : choice);
  document.querySelectorAll("[data-pick]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.pick === choice)));
  // a logo the theme names for this scheme replaces the mark
  const logo = getComputedStyle(root).getPropertyValue("--logo").trim();
  root.toggleAttribute("data-logo", !!logo && logo !== "none");
}
if (SYSTEM && SYSTEM.addEventListener) SYSTEM.addEventListener("change", () => {
  if ((stored("factory.scheme") || "auto") === "auto") scheme("auto");
});

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
    const slow = Date.now() - lastSlow > 15000 || ["decide", "discover", "describe"].includes(S.tab);
    const jobs = [load("status", "/api/view/status"), load("requests", "/api/view/requests")];
    if (slow || !S.decisions) jobs.push(load("decisions", "/api/view/decisions"));
    if (slow || !S.discover) jobs.push(load("discover", "/api/view/discover"));
    if ((await Promise.all(jobs)).every(Boolean)) banner(S.meta.fixture ? `fixture “${S.meta.fixture}” — what the page shows is canned, every press is refused` : "");
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
  // the dot is the backlog's, the one thing a person switches here: a person's requests are worked while this page is
  // open, and that goes without saying (WP-177)
  const backlog = backlogOn(st);
  const dot = !backlog ? "down" : w.stopping ? "stopping" : "up";
  const queued = (S.requests || {}).counts_text;
  $("worker").innerHTML = `${ui.dot(dot)}${esc(st.worker_text || "…")}${queued ? ` · ${esc(queued)}` : ""}`;
  $("worker").title = w ? `${w.owner} since ${w.since_text}` : "nobody holds the checkout";
  $("up").hidden = backlog;
  $("down").hidden = !backlog || w.stopping;
  // a record waits where it is answered: a discovery's on discover, the description's on describe, the rest decide
  const asking = place => (st.waiting || []).filter(w => (w.place || "decide") === place).length;
  const tab = id => {
    const n = ["decide", "discover", "describe"].includes(id) ? asking(id) : id === "run" ? (counts.failed || 0) : 0;
    const key = TABS.findIndex(([t]) => t === id);
    return {id, key, n, on: S.tab === id, first: S.tab === "now" && key === 0};
  };
  // the parts side by side, the cycle's views with an arrow between them: the order a story turns through
  const parts = (S.help || {}).parts || [{tabs: TABS.map(([id]) => id)}];
  morph($("tabs"), ui.tabs(parts.map(p => ({ordered: p.ordered, tabs: p.tabs.map(tab)}))));
  $("main").setAttribute("aria-labelledby", S.tab === "now" || S.tab === "components" ? "home" : "tab-" + S.tab);
}
const partOf = id => ((S.help || {}).parts || []).find(p => p.tabs.includes(id));
// whether the backlog runs: a runner from a terminal or a session's, or the factory's worker with the backlog on
const backlogOn = st => { const w = st.worker; return !!(w && w.alive && (w.how !== "up" || w.backlog)); };

// --- drawing: the new page is matched against the one on screen, never put in its place -------------------------------
// An element that stays the same element keeps what the browser holds for the person — where a box is scrolled, what
// has the focus, a caret, a selection —, so nothing of it has to be remembered and put back. An element with a key
// (`id`, `data-fold`, `data-epic`, `data-context`, `data-story`) is found again by it, wherever it moved; a text
// field's words are the person's, and the match leaves them alone.
const keyOf = node => node.nodeType === 1 ? node.id || node.dataset.fold || node.dataset.epic || node.dataset.context
  || node.dataset.topic
  || (node.tagName === "BUTTON" ? "" : node.dataset.story) || "" : "";
const PERSONS = {TEXTAREA: ["value"], INPUT: ["value"], SELECT: ["value"]};
function morphNode(old, want) {
  if (old.nodeType !== 1) { if (old.nodeValue !== want.nodeValue) old.nodeValue = want.nodeValue; return; }
  const keep = PERSONS[old.tagName] || [];
  for (const {name} of [...old.attributes]) if (!want.hasAttribute(name) && !keep.includes(name)) old.removeAttribute(name);
  for (const {name, value} of [...want.attributes]) if (!keep.includes(name) && old.getAttribute(name) !== value) old.setAttribute(name, value);
  // a text field's words are the person's, and what the page fills in itself (`data-own`) is the page's
  if (old.tagName !== "TEXTAREA" && !old.hasAttribute("data-own")) morphChildren(old, want);
}
function morphChildren(from, to) {
  const keyed = new Map([...from.childNodes].filter(keyOf).map(n => [keyOf(n), n]));
  let cur = from.firstChild;
  for (const want of [...to.childNodes]) {
    const key = keyOf(want);
    const match = key ? keyed.get(key)
      : cur && !keyOf(cur) && cur.nodeType === want.nodeType && cur.nodeName === want.nodeName ? cur : null;
    if (!match) { from.insertBefore(want, cur); continue; }
    if (key) keyed.delete(key);
    if (match === cur) cur = cur.nextSibling; else from.insertBefore(match, cur);
    morphNode(match, want);
  }
  while (cur) { const next = cur.nextSibling; cur.remove(); cur = next; }
}
function morph(target, html) {
  if (target.dataset.drawn === html) return;            // nothing changed: nothing is touched
  const fresh = document.createElement("template");
  fresh.innerHTML = html;
  morphChildren(target, fresh.content);
  target.dataset.drawn = html;
}

function render() {
  renderFrame();
  const editing = document.activeElement && ["TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
    && $("main").contains(document.activeElement);
  if (editing) return;                                   // a person typing is not redrawn under their hands
  forget("m"); forget("s");
  const [, title, lede] = S.tab === "now" ? NOW : S.tab === "components" ? GALLERY : TABS.find(([id]) => id === S.tab) || NOW;
  const eyebrow = S.tab === "now" ? "Now" : S.tab === "components" ? "Pattern library" : (partOf(S.tab) || {}).eyebrow || "";
  const view = {now, describe, discover, backlog, run, decide, delivered, rules: rulesTab, components}[S.tab] || now;
  morph($("main"), ui.pageHead(eyebrow, title, lede)
    + (S.status || S.tab === "components" ? endedLine(S.status || {}) + view(S.status || {}) : ui.card("", "", ui.empty("Reading the factory…"))));
  if (S.tab === "run") paintFollow();
  if (S.tab === "rules") paintFlow();
}

// --- the drawing of the rules: a way back shows while its step is hovered; what is picked stays marked --------------
function showBacks(test) {
  document.querySelectorAll(".flow .way-back").forEach(g => g.toggleAttribute("data-shown", test(g)));
}
// a gate after a step and its round are one thing: the gate, and where a refusal of it sends the story
const gated = stage => { const f = S.rules && S.rules.flow && S.rules.flow[S.ruleKind]; const s = f && f.steps.find(x => x.stage === stage); return !!s && s.gate === "after"; };
const flowKey = g => g.dataset.gate ? "gate:" + g.dataset.gate : g.dataset.stage && !g.dataset.way ? "stage:" + g.dataset.stage
  : g.dataset.way === "again" && gated(g.dataset.source) ? "gate:gate-after:" + g.dataset.source
  : `${g.dataset.source}>${g.dataset.target}>${g.dataset.way}`;
function paintFlow() {
  const backs = new Set([...document.querySelectorAll(".flow .way-back")].map(g => g.dataset.source));
  document.querySelectorAll(".flow [data-stage]").forEach(t => t.toggleAttribute("data-has-back", backs.has(t.dataset.stage)));
  const key = S.flowPick ? S.flowPick.key : "";
  document.querySelectorAll(".flow").forEach(f => f.toggleAttribute("data-has-pick", !!key));
  document.querySelectorAll(".flow .way, .flow .gate, .flow [data-stage]").forEach(g => g.toggleAttribute("data-picked", !!key && flowKey(g) === key));
  const v = S.rules, flow = v && v.flow && v.flow[S.ruleKind], marks = flow ? storyMarks(flow, v.story) : null;
  const row = marks && S.status ? (S.status.rows || []).find(r => r.story === v.story.id) : null;
  document.querySelectorAll(".flow").forEach(f => f.toggleAttribute("data-has-story", !!marks));
  document.querySelectorAll(".flow [data-badge]").forEach(t => t.remove());
  document.querySelectorAll(".flow [data-stage]").forEach(t => {
    t.toggleAttribute("data-reached", !!marks && marks.reached.has(t.dataset.stage));
    t.toggleAttribute("data-now", !!row && row.stage === t.dataset.stage);
  });
  document.querySelectorAll(".flow .gate").forEach(g => {
    const [, stage] = (g.dataset.gate || "").split(":"), at = marks ? marks.gates.find(x => x.stage === stage) : null;
    g.toggleAttribute("data-failed", !!at && at.failed);
    if (at && at.refused) {
      const c = g.querySelector("circle"), t = document.createElementNS("http://www.w3.org/2000/svg", "text");
      t.setAttribute("x", +c.getAttribute("cx") + 14); t.setAttribute("y", +c.getAttribute("cy") - 12);
      t.setAttribute("data-badge", ""); t.textContent = `×${at.refused}`; g.appendChild(t);
    }
  });
  if (S.flowPick && S.flowPick.type === "stage") showBacks(g => g.dataset.source === S.flowPick.stage);
  else if (S.flowPick && S.flowPick.way === "back") showBacks(g => flowKey(g) === S.flowPick.key);
}
document.addEventListener("mouseover", event => {
  const at = event.target.closest && event.target.closest(".flow [data-stage]");
  if (at) showBacks(g => g.dataset.source === at.dataset.stage);
});
document.addEventListener("mouseout", event => {
  const at = event.target.closest && event.target.closest(".flow [data-stage]");
  if (at) { showBacks(() => false); paintFlow(); }
});
function pickInFlow(at) {
  const key = flowKey(at);
  if (S.flowPick && S.flowPick.key === key) S.flowPick = null;
  else if (at.dataset.gate) S.flowPick = {key, type: "gate", gate: at.dataset.gate};
  else if (key.startsWith("gate:")) S.flowPick = {key, type: "gate", gate: key.slice(5)};
  else if (at.dataset.stage && !at.dataset.way) S.flowPick = {key, type: "stage", stage: at.dataset.stage};
  else S.flowPick = {key, type: "edge", source: at.dataset.source, target: at.dataset.target, way: at.dataset.way};
  render();
}
document.addEventListener("click", event => {
  const edge = event.target.closest && event.target.closest("[data-edge]");
  if (edge) {
    event.stopPropagation();
    const [source, target, way] = edge.dataset.edge.split(">");
    S.flowPick = {key: edge.dataset.edge, type: "edge", source, target, way};
    return render();
  }
  const at = event.target.closest && event.target.closest(".flow [data-rules], .flow [data-stage]");
  if (!at) return;
  event.stopPropagation();
  pickInFlow(at);
}, true);

// the delivered curve: a hair across both panels and a tip with the delivery under the pointer
document.addEventListener("mousemove", event => {
  const hit = event.target.closest && event.target.closest("#curve-hit"), tip = $("curve-tip");
  const marks = ["curve-cross", "curve-dot-0", "curve-dot-1"].map(id => $(id));
  if (!hit || !S.curve) { if (tip) tip.hidden = true; marks.forEach(m => m && m.setAttribute("visibility", "hidden")); return; }
  const svg = hit.ownerSVGElement, box = svg.getBoundingClientRect(), scale = CURVE.w / box.width;
  const vx = (event.clientX - box.left) * scale, {t0, t1, x0, x1} = S.curveX;
  const at = t0 + (vx - x0) / (x1 - x0) * (t1 - t0);
  let i = 0; while (i + 1 < S.curve.length && Date.parse(S.curve[i + 1].at) <= at) i++;
  const c = S.curve[i], cx = x0 + (Date.parse(c.at) - t0) / (t1 - t0) * (x1 - x0);
  marks[0].setAttribute("x1", cx); marks[0].setAttribute("x2", cx); marks[0].setAttribute("visibility", "visible");
  S.curvePanels.forEach((p, n) => { marks[n + 1].setAttribute("cx", cx); marks[n + 1].setAttribute("cy", p.y(c[p.key])); marks[n + 1].setAttribute("visibility", "visible"); });
  tip.innerHTML = ui.curveTip(c, [["delivered", c.at.replace("T", " ").slice(0, 16)], ["cost so far", "$" + c.cost_total.toFixed(2)],
    ["tokens so far", c.tokens_total.toLocaleString("en")], ["this one", `${c.cost == null ? "unpriced" : "$" + c.cost.toFixed(2)} · ${count(c.tokens)}`]]);
  tip.hidden = false;
  const left = cx / scale + 14, room = box.width - tip.offsetWidth - 8;
  tip.style.left = `${Math.min(left, room)}px`; tip.style.top = `${(event.clientY - box.top) - tip.offsetHeight - 12}px`;
});

// --- keys ----------------------------------------------------------------------------------------------------------
// The tab bar by keyboard (WAI-ARIA tabs): while a tab has the focus, the arrows, Home and End move between the views
// and a digit jumps to its view — the cockpit's keys, shown as hints then. Outside the bar a digit is a digit
// (WCAG 2.1.4: a one-key shortcut acts only where its element has the focus).
document.addEventListener("keydown", event => {
  if (event.target.closest("textarea, input, select")) return;
  if (event.key === "Escape") return CALLS.close();
  const at = event.target.closest('[role="tab"]');
  if (!at) return;
  const ids = [...$("tabs").querySelectorAll('[role="tab"]')].map(b => b.dataset.tab), i = ids.indexOf(at.dataset.tab);
  const to = /^[0-9]$/.test(event.key) ? (TABS[+event.key] || [])[0]
    : {ArrowRight: ids[(i + 1) % ids.length], ArrowLeft: ids[(i - 1 + ids.length) % ids.length],
       Home: ids[0], End: ids[ids.length - 1]}[event.key];
  if (!to) return;
  event.preventDefault();
  if (to !== S.tab) show(to);
  $("tab-" + to).focus();
});
window.addEventListener("hashchange", () => {
  const tab = location.hash.slice(1);
  if (tab !== S.tab && known(tab)) show(tab);
});
"""

SCRIPT_START = r"""
// --- start ---------------------------------------------------------------------------------------------------------
scheme(stored("factory.scheme") || stored("factory.theme") || "auto");
(async () => {
  if (!TOKEN) { banner("This page needs the token `factory.sh serve` printed — open that URL."); return; }
  try {
    S.meta = await api("/api/meta");
    $("by").value = stored("factory.by") || S.meta.by || "";
  } catch (e) { banner(e.message); }
  $("by").addEventListener("change", () => store("factory.by", by()));
  load("help", "/api/view/help").then(ok => ok && render());   // the parts: once, inflow, the cycle, to look up
  await refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 5000);
})();
"""
