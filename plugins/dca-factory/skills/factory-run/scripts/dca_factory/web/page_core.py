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
const S = {tab: "now", menu: null, help: null, status: null, decisions: null, discover: null, requests: null, follow: null, followOn: "", autoFollow: "", factoryLogOff: false, followSource: null,
           followLines: [], drawer: null, opener: null, drafts: {}, handed: {}, fold: new Map(),
           rules: null, rulesFor: null, ruleKind: "story", ruleStory: "", flowPick: null, partText: {}, meta: {},
           part: "", detail: "", storyFrom: "", record: "", topicPick: "", storyView: {}, changing: ""};
const stored = key => { try { return localStorage.getItem(key) || ""; } catch (e) { return ""; } };
const store = (key, value) => { try { localStorage.setItem(key, value); } catch (e) {} };
// the page opens where it stands; a link to a view opens that view
const known = id => id === "now" || id === "components" || TABS.some(([t]) => t === id);
// a view, and where it holds one: `#describe/<part>` reads a part, `#backlog/<story>` opens a story (WP-183)
function readHash() {
  const [tab, sub] = location.hash.slice(1).split("/");
  if (!known(tab)) return false;
  S.tab = tab;
  S.part = tab === "describe" && sub ? decodeURIComponent(sub) : "";
  S.detail = ["backlog", "run"].includes(tab) && sub ? decodeURIComponent(sub) : "";
  S.topicPick = tab === "discover" && sub ? decodeURIComponent(sub) : "";
  return true;
}
readHash();
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
  : linked(part)).join("");
// a picture and a link in a record's, a report's or a story's markdown (WP-184): a picture only from the project, by
// its path beside the file it stands in, served by the page's own server; a link out only to https, a link to a
// project file through the same server — never a script's URL, never a foreign picture (the CSP's img-src is 'self')
let mdBase = "";
const projectPath = src => {
  const parts = (mdBase.includes("/") ? mdBase.slice(0, mdBase.lastIndexOf("/") + 1) : "").concat(src).split("/");
  const out = [];
  for (const p of parts) { if (p === "..") out.pop(); else if (p && p !== ".") out.push(p); }
  return out.join("/");
};
const fileOf = path => `/api/file?path=${encodeURIComponent(path)}&t=${encodeURIComponent(TOKEN)}`;   // a project path
const fileUrl = src => fileOf(projectPath(src));
const local = src => !/^[a-z][a-z0-9+.-]*:/i.test(src) && !src.startsWith("//") && !src.startsWith("/");
const strong = part => esc(part).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
const linked = part => part.split(/(!?\[[^\]]*\]\([^)\s]+\))/).map((bit, i) => {
  if (!(i % 2)) return strong(bit);
  const [, picture, label, target] = bit.match(/^(!?)\[([^\]]*)\]\(([^)\s]+)\)$/);
  // a mockup an option shows: a page of its own, drawn in a frame that runs no script (WP-184)
  if (picture && local(target) && /\.html$/i.test(target)) return `<iframe src="${esc(fileUrl(target))}" title="${esc(label || target)}" sandbox loading="lazy"></iframe>`
    + (label ? `<small>${esc(label)}</small>` : "");
  if (picture) return local(target)
    ? `<a href="${esc(fileUrl(target))}" target="_blank" rel="noopener"><img src="${esc(fileUrl(target))}" alt="${esc(label)}" loading="lazy"></a>`
      + (label ? `<small>${esc(label)}</small>` : "")
    : strong(label || target);
  if (/^https:\/\//i.test(target)) return `<a href="${esc(target)}" target="_blank" rel="noopener noreferrer">${strong(label)}</a>`;
  return local(target) ? `<a href="${esc(fileUrl(target))}" target="_blank" rel="noopener">${strong(label)}</a>` : strong(label);
}).join("");
function markdown(text, base = "") {
  mdBase = base;
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

// the one line above the bar, kept in sight as the bar is: what went wrong (`stop`), or a notice that is none (`info`)
function banner(text, tone = "stop") {
  $("banner-text").textContent = text || "";
  $("banner").dataset.state = tone;
  $("banner").hidden = !text;
}

// --- actions: the factory's, drawn as given ------------------------------------------------------------------------
// An action carries its label, whether it is the one to press, and the request it writes; `open` says what the person
// still gives — their words (a form), or an answer under Decide; one whose request is written already says so
// (`queued`). One without a request is no press on this page.
const ACTIONS = {};
let actionCount = 0;
// how long something has run, in the largest unit that still reads: 42 s, 5 min, 3 h, 2 d
const took = secs => secs < 60 ? `${secs} s` : secs < 3600 ? `${Math.round(secs / 60)} min`
  : secs < 86400 ? `${Math.round(secs / 3600)} h` : `${Math.round(secs / 86400)} d`;
function act(action, scope, also = "", shape = {}) {
  if (!action || !action.request) return "";
  if (action.waits_on) return "";                       // another choice of the same record is on its way
  if (action.queued) return ui.state(`${action.label} — ${action.queued_text || "queued"}`, "queued", {title: `request ${action.queued}`});
  const id = `${scope || "m"}${++actionCount}`;
  ACTIONS[id] = action;
  // a press that has an agent write something new says so before it is pressed: ✦ on the button, words in its title
  // `shape` sets how a press looks where it stands — small and plain beside a row, say — never what it does
  const r = action.request, look = Object.assign({primary: action.primary, write: action.creates}, shape);
  const said = [action.creates ? "an agent writes this, in the factory's queue" : "", action.text].filter(Boolean).join(" — ");
  if (r.open === "words") {
    // what the person typed outlives a redraw: kept by the action's command, until its request is written
    const draft = r.draft || action.skill;
    return ui.ask(Object.assign({id, draft, label: action.label, text: action.text, title: said, value: S.drafts[draft] || "",
                                 files: S.handed[draft] || [],
                                 choices: r.choices, also}, look));
  }
  if (r.open === "record") return ui.btn(action.label, Object.assign({attrs: {"data-tab": "decide"}}, look));
  return ui.btn(action.label, Object.assign({title: said, attrs: {"data-press": id}}, look));
}
const acts = (list, scope, shape = {}) => (list || []).map(a => act(a, scope, "", shape)).join("");
function forget(scope) { for (const key of Object.keys(ACTIONS)) if (key[0] === scope) delete ACTIONS[key]; }

async function press(button) {
  const action = ACTIONS[button.dataset.press];
  if (!action) return;
  const r = action.request, box = button.closest("[data-ask]"), fields = Object.assign({}, r.fields);
  let words = r.words || "";
  if (box) {
    words = box.querySelector("[data-draft]").value.trim();
    const pick = box.querySelector("[data-ask-why]");
    if (pick && pick.value) fields.option = pick.value;
    if (!words) { toast(`${action.label}: ${action.text}`, true); return; }
    var files = [];
    try { files = await handedData(box.dataset.hand); } catch (e) { toast(e.message, true); return; }
    if (r.prefix) words = `${r.prefix}\n\n${words}`;
    if (r.lead) words = `${r.lead} ${words}`;                 // the same line: `tech.md — Stack: <words>`
  }
  try {
    const data = await api("/api/request", Object.assign({kind: r.kind, words, by: by()}, fields, files.length ? {files} : {}));
    toast(data.duplicate ? `queued already: ${data.id}`
      : r.kind === "wish" ? "✦ your wish is being written as a draft — it shows below the field" : `request written: ${data.id}`);
    if (box) { box.querySelector("[data-draft]").value = ""; delete S.drafts[r.draft || action.skill]; (S.handed[box.dataset.hand] || []).forEach(f => handed.delete(f.key)); delete S.handed[box.dataset.hand]; }
    refresh();
    if (S.drawer) openStory(S.drawer);
    if (S.detail) loadStory(S.detail);
  } catch (e) { toast(e.message, true); }
}
// --- files beside the words (WP-184): chosen with "+ file" or dropped on the field, they stay in the page until the
// request is sent — then they go with it, one command, and the factory's domain decides what it takes. Here only a
// first look, so a person sees at once what will not go: the kind by its name, the size, the number
const HANDED_MAX = 5, HANDED_BYTES = 10 * 1024 * 1024;
const HANDED_TYPES = /\.(png|jpe?g|gif|webp|pdf|txt|md|csv|json)$/i;
let handedCount = 0;
const handed = new Map();                                     // a chip's key → the File it stands for
async function handOver(key, list) {
  const files = S.handed[key] = S.handed[key] || [];
  for (const file of list) {
    if (files.filter(f => !f.error).length >= HANDED_MAX) { toast(`at most ${HANDED_MAX} files go with a request`, true); break; }
    const entry = {key: `h${++handedCount}`, name: file.name, size: file.size};
    if (file.size > HANDED_BYTES) entry.error = "over 10 MB";
    else if (!HANDED_TYPES.test(file.name)) entry.error = "a picture, a PDF or a text (txt, md, csv, json) — not this one";
    else handed.set(entry.key, file);
    if (!entry.error && /^image\/(png|jpeg|gif|webp)$/.test(file.type) && file.size < 2 * 1024 * 1024) {
      entry.preview = await new Promise(done => { const read = new FileReader(); read.onload = () => done(read.result); read.onerror = () => done(""); read.readAsDataURL(file); });
    }
    files.push(entry);
  }
  render();
}
// the files of one entry, read as base64 for the request that carries them
const handedData = key => Promise.all((S.handed[key] || []).filter(f => !f.error && handed.has(f.key)).map(f => new Promise((done, fail) => {
  const read = new FileReader();
  read.onload = () => done({name: f.name, data: String(read.result).split(",", 2)[1] || ""});
  read.onerror = () => fail(new Error(`${f.name} could not be read`));
  read.readAsDataURL(handed.get(f.key));
})));
document.addEventListener("click", event => {
  const pick = event.target.closest("[data-attach]");
  if (pick) { const input = document.querySelector(`[data-attach-input="${CSS.escape(pick.dataset.attach)}"]`); if (input) input.click(); return; }
  const drop = event.target.closest("[data-unhand]");
  if (drop) { handed.delete(drop.dataset.file); S.handed[drop.dataset.unhand] = (S.handed[drop.dataset.unhand] || []).filter(f => f.key !== drop.dataset.file); render(); }
});
document.addEventListener("change", event => {
  const input = event.target.closest && event.target.closest("[data-attach-input]");
  if (input && input.files.length) { handOver(input.dataset.attachInput, [...input.files]); input.value = ""; }
});
document.addEventListener("dragover", event => {
  const box = event.target.closest && event.target.closest("[data-hand]");
  if (!box || ![...(event.dataTransfer.types || [])].includes("Files")) return;
  event.preventDefault(); box.dataset.over = "";
});
document.addEventListener("dragleave", event => { const box = event.target.closest && event.target.closest("[data-hand]"); if (box) delete box.dataset.over; });
document.addEventListener("drop", event => {
  const box = event.target.closest && event.target.closest("[data-hand]");
  if (!box || !event.dataTransfer.files.length) return;
  event.preventDefault(); delete box.dataset.over; handOver(box.dataset.hand, [...event.dataTransfer.files]);
});
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
  async unfollow() { if (S.follow && S.follow.kind === "log") S.factoryLogOff = true; follow(null); },
  async closeDetail() {
    if (S.followOn === "story") stopFollowing();
    const from = S.storyFrom || S.tab; S.detail = ""; S.storyFrom = ""; S.autoFollow = "";
    if (from !== S.tab) return show(from);
    place(); render();
  },
  async close() { S.drawer = null; $("drawer").hidden = true; forget("d"); if (S.opener && document.contains(S.opener)) S.opener.focus(); S.opener = null; },
};

document.addEventListener("click", async event => {
  const target = event.target.closest("[data-press],[data-call],[data-story],[data-tab],[data-pick],[data-flow],[data-filter],[data-part],[data-goto],[data-change],[data-record],[data-pick-topic]");
  if (!target) return;
  if (target.dataset.record) { S.record = target.dataset.record; return render(); }
  // a discovery opens on a place of its own beneath discover, as a story beneath the backlog (WP-183)
  if (target.dataset.pickTopic !== undefined) {
    if (S.followOn === "discover") stopFollowing();
    S.topicPick = target.dataset.pickTopic; place(); render(); return window.scrollTo(0, 0);
  }
  if (target.dataset.part !== undefined) { S.part = target.dataset.part; S.changing = ""; place(); render(); return window.scrollTo(0, 0); }
  if (target.dataset.goto) { const at = $(target.dataset.goto); if (at) at.scrollIntoView({behavior: "smooth", block: "start"}); return; }
  if (target.dataset.change !== undefined) {
    S.changing = target.dataset.change; render();
    const field = S.changing && document.querySelector("[data-draft^='describe:']");
    if (field) field.focus();
    return;
  }
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
    if ((await Promise.all(jobs)).every(Boolean)) banner(S.meta.fixture ? `fixture “${S.meta.fixture}” — what the page shows is canned, every press is refused` : "", "info");
    if (slow) lastSlow = Date.now();
    // a story that runs is read again with each look, so its place shows its progress as it goes
    if (onStoryPlace() && ((S.status || {}).running || []).some(r => r.story === S.detail)) await loadStory(S.detail);
    render();
  } finally { refreshing = false; }
}

// --- the frame -----------------------------------------------------------------------------------------------------
function show(tab) {
  if (S.drawer) CALLS.close();
  // output followed on a story's place or a discovery's ends with the place: the run page shows only what is followed there
  if (S.followOn === "story" || S.followOn === "discover") stopFollowing();
  S.tab = tab;
  S.part = S.detail = S.changing = S.topicPick = "";
  store("factory.tab", tab);
  place();
  render();
  window.scrollTo(0, 0);
}

function renderFrame() {
  const st = S.status || {}, w = st.worker, counts = (S.requests || {}).counts || {};
  $("project").textContent = st.project || "";
  document.title = (st.project ? st.project + " — " : "") + "domaincentric.factory";
  // the dot is the backlog's, the one thing a person switches here: a person's requests are worked while this page is
  // open, and that goes without saying (WP-177)
  const backlog = backlogOn(st);
  morph($("run"), runControl(st, backlog));
  const name = by();
  $("initials").textContent = name ? name.split(/\s+/).map(part => part[0]).join("").slice(0, 2).toUpperCase() : "you";
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
// the run from every page: what it does in a word and the one action; its panel the stories in flight, what comes next
// and what waits. With the page open the backlog off lets the running stories finish — "stop" is after the story (WP-177)
function runControl(st, backlog) {
  const w = st.worker, running = st.running || [], ready = (st.queue || {}).ready || [], waits = (st.waiting || []).length;
  const titles = Object.fromEntries((st.rows || []).map(r => [r.story, r.title]));
  const stopping = !!(w && w.stopping), state = backlog ? (stopping ? "stopping" : "up") : running.length ? "stopping" : "down";
  const first = running[0], more = running.length > 1 ? ` +${running.length - 1}` : "";
  const say = first ? `${backlog ? "" : "finishing "}${ui.em(first.story)}${more} · ${esc(first.part || first.stage)}`
    : backlog ? esc(st.worker_text || "the backlog is on") : `stopped${ready.length ? ` · ${ready.length} ready` : ""}`;
  const start = ui.btn("start the backlog", {icon: "play", primary: true, plain: true, bar: true, size: "s", title: "work the released stories off, one after the other — factory.sh up", attrs: {"data-call": "up"}});
  const stop = ui.btn("stop", {icon: "stop", bar: true, size: "s", title: "no further story starts; the running one finishes — factory.sh down", attrs: {"data-call": "down"}});
  const queued = (S.requests || {}).counts_text;
  const lines = [
    ready.length ? `next: ${ui.em(titles[ready[0]] || ready[0])}${ready.length > 1 ? `, then ${ready.length - 1} more` : ""}` : "",
    waits ? ui.link(`${waits} ${waits === 1 ? "question waits" : "wait"} for you →`, {quiet: true, attrs: {"data-tab": "decide"}}) : "",
    queued ? esc(queued) : "",
    w ? esc(`${w.owner} since ${w.since_text}`) : ""].filter(Boolean);
  const acts = (backlog && !stopping
      ? ui.btn("stop after the running story", {icon: "stop", attrs: {"data-call": "down"}}) + ui.btn("stop now", {icon: "stop", danger: true, attrs: {"data-call": "down", "data-now": "1"}})
      : !backlog ? ui.btn("start the backlog", {icon: "play", primary: true, plain: true, attrs: {"data-call": "up"}}) : "")
    + ui.link("open the run →", {quiet: true, compact: true, attrs: {"data-tab": "run"}});
  const runs = running.map(r => ({id: r.story, title: titles[r.story], steps: r.course, doing: r.activity,
    word: `${r.interrupted ? "interrupted" : r.part || r.stage}${r.round > 1 ? ` · round ${r.round}` : ""}${r.ago ? ` · ${r.ago}` : ""}`}));
  return ui.runControl({state, say, open: S.menu === "run", title: "the run — open for what runs and what comes next",
    act: backlog ? (stopping ? "" : stop) : start,
    panel: ui.runPanel({runs, idle: running.length ? "" : backlog ? "nothing runs now — the next released story starts by itself" : "the backlog is off", lines, acts})});
}
// a menu opens beneath its button; a click beside it, a press inside it or Escape closes it
function menus() {
  document.querySelectorAll("[data-menu]").forEach(b => {
    const open = S.menu === b.dataset.menu, panel = $(b.getAttribute("aria-controls"));
    b.setAttribute("aria-expanded", String(open));
    if (panel) panel.hidden = !open;
  });
}
document.addEventListener("click", event => {
  const toggle = event.target.closest && event.target.closest("[data-menu]");
  if (toggle) { event.stopPropagation(); S.menu = S.menu === toggle.dataset.menu ? null : toggle.dataset.menu; return menus(); }
  if (!S.menu) return;
  const box = event.target.closest && event.target.closest(`[data-menu-box="${S.menu}"]`);
  if (!box || event.target.closest("[data-call],[data-tab],[data-story],[data-press]")) { S.menu = null; menus(); }
}, true);
document.addEventListener("keydown", event => {
  if (event.key !== "Escape" || !S.menu) return;
  const toggle = document.querySelector(`[data-menu="${S.menu}"]`);
  S.menu = null; menus(); event.stopImmediatePropagation();
  if (toggle) toggle.focus();
}, true);
// where the page stands, in its address — a reload opens the same
function place() {
  const sub = S.tab === "describe" ? S.part : S.tab === "discover" ? S.topicPick : STORY_TABS.includes(S.tab) ? S.detail : "";
  history.replaceState(null, "", "#" + S.tab + (sub ? "/" + encodeURIComponent(sub) : ""));
}
// the wide width of the stylesheet (page_style.WIDE): the main region's content from which a view takes two columns
const WIDE_PX = 1500;
// a story has its place under the backlog or under run, whichever it was opened from (WP-183)
const STORY_TABS = ["backlog", "run"];
const onStoryPlace = () => STORY_TABS.includes(S.tab) && !!S.detail;
function wide() {
  const main = $("main"), cs = getComputedStyle(main);
  return main.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) >= WIDE_PX;
}
let wasWide = null;
const sized = new ResizeObserver(() => {
  document.documentElement.style.setProperty("--bar-height", $("topbar").getBoundingClientRect().height + "px");
  fitCurve();
  const now = wide();
  if (now === wasWide) return;
  const first = wasWide === null;
  wasWide = now;
  if (!first) render();
});
sized.observe($("main"));
sized.observe($("topbar"));
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
  // a part read as a document is a place of its own beneath the description: the way back above its title (WP-183)
  const part = S.tab === "describe" && S.part ? ((S.status || {}).description || []).find(p => p.part === S.part) || {part: S.part} : null;
  const own = onStoryPlace() || (S.tab === "discover" && !!S.topicPick);   // a story's place and a discovery's draw their own head
  morph($("main"), (own ? "" : part ? ui.actions(ui.btn("← all parts", {attrs: {"data-part": ""}})) + ui.pageHead(title, part.part, part.path || "")
                        : ui.pageHead(eyebrow, title, lede))
    + (S.status || S.tab === "components" ? endedLine(S.status || {}) + view(S.status || {}) : ui.card("", "", ui.empty("Reading the factory…"))));
  if (S.tab === "run" || S.tab === "discover" || onStoryPlace()) paintFollow();
  if (S.tab === "rules") paintFlow();
  fitCurve();
}
// the curve takes the width it is given: drawn anew at that width once it is known or has changed
function fitCurve() {
  const box = $("curve"), svg = box && box.querySelector("svg");
  if (!svg || !S.curve) return;
  const w = Math.round(box.clientWidth);
  if (!w || Math.abs(w - svg.viewBox.baseVal.width) < 4) return;
  S.curveW = w;
  svg.outerHTML = curveSvg(S.curve, w);
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
  const svg = hit.ownerSVGElement, box = svg.getBoundingClientRect(), scale = svg.viewBox.baseVal.width / box.width;
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
  if (event.key === "Escape") {
    if (S.drawer) return CALLS.close();
    if (S.changing) { S.changing = ""; return render(); }
    if (S.detail) return CALLS.closeDetail();
    if (S.part) { S.part = ""; place(); return render(); }
    if (S.tab === "discover" && S.topicPick) { if (S.followOn === "discover") stopFollowing(); S.topicPick = ""; place(); return render(); }
    return;
  }
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
window.addEventListener("hashchange", () => { if (readHash()) render(); });
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
