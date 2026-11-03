r"""The page's views (WP-180): each tab, the story's drawer, and the pattern library — composed of the components alone.

A view decides what to show and in which order, as the factory gives it; how a thing looks is its component's. So
this module writes no class and no style of its own — `test_page_components.py` refuses one — and every component
of `page_ui.py` is shown in the pattern library (`#components`), in its variants and states.
"""

SCRIPT_VIEWS = r"""
// === the views ===================================================================================================
const when = text => {
  const day = String(text || "").slice(0, 10), today = new Date().toISOString().slice(0, 10);
  return !day ? "" : day === today ? `today ${String(text).slice(11)}` : day;
};
// on every tab: the factory that ended on its own, and why
function endedLine(st) {
  const gone = st.ended;
  return gone ? ui.notice(`${esc(gone.text)}${gone.log ? ` ${ui.hint(gone.log)}` : ""}`,
    {ended: true, action: ui.btn("▶ start the backlog", {primary: true, plain: true, attrs: {"data-call": "up"}})}) : "";
}

// --- now: where it stands --------------------------------------------------------------------------------------------
// The cycle as four columns, each as the factory says it: its count, one line, the one item that matters most there and
// the one action at its foot. Then the inflow — the wish part —, the last deliveries and what may wait.
function column(c) {
  const delivered = c.column === "delivered", items = [];
  if (c.last_text) items.push(`last ${esc(when(c.last_text))}`);
  if (c.title) items.push((c.story ? ui.story(c.story, c.title) : esc(c.title)) + (c.sub ? ui.id(c.sub, {block: true}) : ""));
  const press = !c.action ? "" : c.action.call ? ui.btn(c.action.label, {primary: true, plain: true, attrs: {"data-call": c.action.call}}) : act(c.action);
  const all = delivered ? ui.link("all →", {to: true, attrs: {"data-tab": "delivered"}}) : "";
  return ui.column({name: c.column, count: c.count, of: delivered ? c.total : null, line: c.line, hot: c.hot, items,
    meter: delivered ? c.percent : null, meterLabel: delivered ? `${c.count} of ${c.total} stories delivered, ${c.percent} percent` : "",
    actions: press + all});
}
function now(st) {
  const rows = Object.fromEntries((st.rows || []).map(r => [r.story, r]));
  const recent = (st.delivered_order || []).slice(0, 3).map(id => rows[id]).filter(Boolean).map(r => ({mark: "done",
    what: ui.story(r.story, r.title) + ui.id(r.epic, {block: true}), aside: `${esc(when(r.delivered_text))}<br>${esc(r.cost_text || "")}`}));
  const sums = [st.cost_text, st.seconds_text].filter(Boolean).join(" · ");
  const findings = (st.findings || []).length;
  return ui.board((st.now || []).map(column))
    + ui.inflow("Inflow →", "a wish, a discovery, a finding, an epic's journey fill the backlog")
    + wishPart(st)
    + (recent.length ? ui.card("Last delivered", sums ? `${esc(sums)} in all` : "", ui.list(recent) + ui.link("delivered →", {to: true, attrs: {"data-tab": "delivered"}})) : "")
    + (findings ? ui.quietLine(`Beside that: ${ui.link(`${findings} open finding${findings > 1 ? "s" : ""} beside their stories →`, {attrs: {"data-tab": "backlog"}})}`) : "");
}

// --- the wish: one part wherever it stands, the field and the trail of what became of each wish ------------------------
function wishPart(st) {
  const items = ((S.requests || {}).wishes || []).map(w => {
    const since = w.state === "running" && w.started ? ` — ${Math.max(0, Math.round((Date.now() - Date.parse(w.started)) / 1000))} s` : "";
    const ops = (w.operations || []).map(op => ui.btn(op.label, {small: true, danger: op.name === "drop",
      title: op.name === "hide" ? "hide it here; the draft stays in the backlog" : "",
      attrs: {"data-call": op.name, "data-kind": "request", "data-id": w.id, "aria-label": op.name === "hide" ? "hide" : null}})).join("");
    const answer = w.state === "waiting" ? ui.btn("answer", {small: true, primary: true, attrs: {"data-tab": w.place}}) : "";
    const open = (w.made || []).slice(0, 1).map(m => ui.btn("open", {small: true, attrs: {"data-story": m.id}})).join("");
    const glyph = {ok: "✓ ", ask: "? ", bad: "✗ "}[w.tone] || "";
    return {words: w.words, tone: w.tone, text: glyph + w.text + since, by: w.by, actions: answer + acts(w.actions, "s") + open + ops};
  });
  return ui.wish(act((st.entries || {}).wish), items);
}

// --- 0 describe ----------------------------------------------------------------------------------------------------
// a part of the description opens in place and reads as written, section by section
async function loadPart(name) {
  try { S.partText[name] = await api(`/api/view/part?id=${encodeURIComponent(name)}`); }
  catch (e) { S.partText[name] = {error: e.message}; }
  render();
}
function partBody(name) {
  const v = S.partText[name];
  if (!v || v.loading) {          // one read at a time, whatever redraws meanwhile
    if (!v) { S.partText[name] = {loading: true}; loadPart(name); }
    return ui.empty(`Reading ${name}…`);
  }
  if (v.error) return ui.error(v.error, {block: true});
  return v.sections.length ? v.sections.map(sec => `<h3>${esc(sec.heading)}</h3>${sec.text ? ui.prose(sec.text) : ui.empty("empty")}`).join("")
    : ui.empty(`${v.path} is missing.`);
}

function describe(st) {
  const parts = (st.description || []).map(p => {
    const key = `part:${p.part}`;
    return {key, open: opened(key), body: () => partBody(p.part), cells: [
      `${ui.mark(p.mark)}<b>${esc(p.part)}</b>${ui.id(p.path)}`,
      (p.present ? esc((p.sections || []).join(" · ")) : ui.flag("missing", "gone"))
        + ((p.missing || []).length ? ` ${ui.flag("missing: " + p.missing.join(", "), "changes")}` : "")
        + ((p.empty || []).length ? ` ${ui.flag("empty: " + p.empty.join(", "), "changes")}` : "")]};
  });
  return ui.card("The parts", "written by you, through the description — what is built, how, and in which domain; open one to read it",
      ui.foldTable([{label: "part", width: "minmax(0, 14em)"}, {label: "sections"}], parts))
    + domainCard()
    + ui.card("Change the description", "", ui.intro(`In your words — <code>&lt;part&gt;: &lt;change&gt;</code> where it is one part. Where it needs a decision of yours, it asks here.`, {html: true})
      + act((st.entries || {}).describe))
    + ((S.decisions || {}).records || []).filter(r => (r.actions || []).length && r.place === "describe").map(recordCard).join("");
}

// --- the spec: what holds, per context — its domain model, its features, rules and scenarios ---------------------------
async function loadSpec() {
  if (S.spec || S.specLoading) return;
  S.specLoading = true;
  if (await load("spec", "/api/view/spec")) render();
  S.specLoading = false;
}
// a scenario's step as a sentence: its Gherkin keyword set apart
const gherkin = line => { const m = String(line).match(/^\s*-\s*(Given|When|Then|And|But)\b\s*(.*)$/);
  return m ? ui.said(m[1], inline(m[2])) : ui.said("", inline(String(line).replace(/^\s*-\s*/, ""))); };
function scenario(item) {
  const key = `scenario:${item.key}`, open = opened(key);
  const heading = item.form === "line" ? item.lines.join(" ").replace(/\s+/g, " ").replace(/^-\s*[a-z0-9-]+:\s*/, "") : item.key.replace(/-/g, " ");
  const h = item.health || null;
  const proof = !h ? "" : h.proof === "orphaned" ? ui.flag("test gone", "gone", {title: h.missing.join(", ")})
    : h.proof === "untested" ? ui.flag("no test", "gone") : "";
  const changes = proof + item.changed_by.map(c => ui.flag(`${c.verdict} by ${c.story}`, c.verdict, {title: `${c.title} (${c.status})`})).join(" ");
  return ui.accordion({key, variant: "row", open, head: inline(heading), meta: changes, body: () =>
    (item.form === "scenario" ? item.lines.slice(1).map(gherkin).join("") : "")
    + ui.hint(`${item.tests.length ? "test: " + item.tests.map(t => esc(t) + (h && h.missing.includes(t) ? " <b>— not in the code</b>" : "")).join(", ") : "no test named"} · <code>${esc(item.key)}</code>
      · ${h && h.delivered_by ? `delivered by ${esc(h.delivered_by.story)}${h.delivered_by.how ? " (" + esc(h.delivered_by.how) + ")" : ""}` : "no delivered story brought it"}`, {block: true, html: true})
    + ui.actions(act(item.fix, "s")) + ui.actions(act(item.change, "s"))});
}

// a context as the designed domain and the spec hold it: an ink head with its numbers, then its course — 1 its model
// as a profile by kind, 2 its features as groups, each rule a line above its criteria
const KIND_LABEL = {"aggregate": "aggregate", "entity": "entities", "identity": "ids", "value object": "values", "domain event": "events",
  "domain service": "services", "domain gateway": "gateways", "specification": "specifications", "factory": "factories",
  "read model": "read models", "failure": "failures", "concept": "concepts", "other": "other"};
const subdomainKind = sd => /core/i.test(sd) ? "core" : /generic/i.test(sd) ? "generic" : "supporting";
// a model as its kinds, each a row of terms; a shared term in the kernel's colour, saying who uses it
const modelFacts = model => model.map(g => ({kind: KIND_LABEL[g.kind] || g.kind, terms: g.terms.map(t => ({name: t.name, shared: t.shared,
  minor: !t.shared && ["concept", "other"].includes(g.kind),
  title: [t.meaning, t.shared ? "shared kernel" : "", (t.used_by || []).length ? "used by " + t.used_by.join(", ") : ""].filter(Boolean).join(" — ")}))}));

function specContext(c) {
  const facts = modelFacts(c.model);
  const features = c.features.map(f => {
    const key = `feature:${c.context}:${f.feature}`, total = f.rules.reduce((n, r) => n + r.criteria.length, 0);
    const pending = f.rules.reduce((n, r) => n + r.criteria.filter(x => x.changed_by.length).length, 0);
    return ui.accordion({key, variant: "group", open: opened(key), head: `<b>${esc(f.feature || "the context itself")}</b>`,
      meta: `${total}${pending ? ` · ${pending} changed` : ""}`,
      body: () => f.rules.map(r => ui.ruleBlock(r.rule ? inline(r.rule) : "", r.criteria.map(scenario))).join("") + ui.actions(act(f.add, "s"))});
  }).join("");
  const coming = ui.ruleGroup("coming — new criteria of open stories", c.coming.map(s =>
    `<p>${ui.flag(s.status, "adds")} ${ui.story(s.story)} — ${s.keys.map(k => `<code>${esc(k.key)}</code>`).join(", ")}</p>`));
  return ui.domain(ui.domainNode("Domain model", "from its glossary")
    + (facts.length ? ui.facts(facts) : ui.hint("The glossary names no term of a model.", {block: true}))
    + ui.domainNode("Features", "what holds, by rule")
    + (features || ui.hint("No criterion holds yet.", {block: true})) + coming
    + (c.add ? ui.accordion({key: `addfeature:${c.context}`, variant: "quiet", open: opened(`addfeature:${c.context}`), head: "add a feature",
        body: () => act(c.add, "s")}) : ""));
}

// how a context stands over the whole of it: tests gone or missing, criteria no delivered story brought
function healthCell(h) {
  if (!h) return "";
  const bad = [h.orphaned ? ui.flag(`${h.orphaned} test gone`, "gone") : "", h.untested ? ui.flag(`${h.untested} no test`, "gone") : ""].filter(Boolean);
  return (bad.length ? bad.join(" ") : ui.hint("all tested"))
    + (h.undelivered ? ` ${ui.hint(`· ${h.undelivered} not from a story`, {title: "adopted, delivered by hand without a story, or written before the factory"})}` : "");
}

function domainCard() {
  if (!S.spec) { loadSpec(); return ui.card("Domain", "", ui.empty("Reading the contexts…")); }
  const rows = (S.spec.contexts || []).map(c => {
    const key = `context:${c.context}`;
    const pending = c.features.reduce((n, f) => n + f.rules.reduce((m, r) => m + r.criteria.filter(x => x.changed_by.length).length, 0), 0) + c.coming.length;
    return {key, open: opened(key), body: () => specContext(c), cells: [
      `<b>${esc(c.context)}</b> ${c.subdomain ? ui.pill(c.subdomain, subdomainKind(c.subdomain)) : ""}`, esc(c.purpose),
      `${c.features.length}`, `${c.criteria}`, pending ? ui.flag(`${pending}`, "changes") : "—", healthCell(c.health)]};
  });
  const kernel = S.spec.shared_kernel ? ui.kernel(modelFacts(S.spec.shared_kernel.model)) : "";
  return ui.card("Domain", "the contexts as designed, and what holds in each — the model from its glossary, the features as the gate delivered them",
    kernel + (rows.length ? ui.foldTable([{label: "context", width: "minmax(0, 12em)"}, {label: "what it is for", hide: true}, {label: "features", num: true},
        {label: "criteria", num: true}, {label: "open changes", num: true}, {label: "health", width: "minmax(0, 12em)", hide: true}], rows)
      : ui.empty("No spec yet — what holds is written by the stories the gate delivers.")));
}

// --- 1 discover ----------------------------------------------------------------------------------------------------
// a discovery opens in place like a context: its report, what it proposes, and words that continue it
function discoveryBody(t) {
  const proposals = t.proposals.map(p => ({goal: p.goal || p.intent || p.id, intent: p.goal && p.intent ? p.intent : "", metric: p.metric,
    contact: p.domain_contact, id: p.id, epic: p.epic, actions: acts(p.actions)}));
  const changes = t.description_changes.map(c => [`<b>${esc(c.target)}</b>`, `${esc(c.change)}${ui.id(c.why, {block: true})}`, acts(c.actions)]);
  const report = (t.sections || []).filter(sec => !/^proposed /i.test(sec.heading)).map(sec => `<h3>${esc(sec.heading)}</h3>${ui.prose(sec.text)}`).join("");
  return ui.domain(ui.domainNode("The report", t.report)
    + (report || ui.empty("The report says nothing beyond what it proposes."))
    + ui.domainNode("Proposed epics", `${t.proposals.length} proposed — each becomes an epic when you make it one`)
    + (proposals.length ? ui.proposals(proposals) : ui.empty("No proposed work."))
    + (changes.length ? ui.domainNode("Changes to the description", "applied one by one, through the description")
        + ui.table([{label: "part"}, {label: "change"}, {act: true}], changes) : "")
    + ui.domainNode("Continue this discovery", "a question, a document, a wish — the report grows")
    + acts(t.actions, "s"));
}

function discover(st) {
  const topics = (S.discover || {}).topics || [];
  const rows = topics.map(t => {
    const key = `topic:${t.topic}`, made = t.proposals.filter(p => p.epic).length;
    return {key, open: opened(key), body: () => discoveryBody(t), cells: [`<b>${esc(t.title)}</b>${ui.id(t.topic)}`,
      `${t.proposals.length}`, `${made}`, `${t.description_changes.length}`]};
  });
  // a discovery on its way: where it stands and its output, until its report stands below
  const working = ((S.discover || {}).working || []).map(r => ui.ticket({kind: r.topic || "new", word: r.state === "waiting" ? "asks you" : r.state,
    state: r.state, words: r.words, actions: ui.btn("follow", {small: true, attrs: {"data-call": "follow", "data-kind": "request", "data-id": r.id}})})).join("");
  // what a discovery asks back is answered where the discovery stands — the same record Decide lists
  const records = ((S.decisions || {}).records || []).filter(rec => (rec.actions || []).length);
  const asking = ((S.discover || {}).working || []).map(r => records.find(rec => r.record && rec.path === r.record))
    .filter(Boolean).map(recordCard).join("");
  return ui.card("A new discovery", "a problem worth solving, or what should exist — the report and the epics it proposes", act((st.entries || {}).discover)
      + (working ? `<h3>In progress</h3>${ui.queue(working)}` : "") + asking)
    + ui.card("Discoveries", "each topic with its report — open one to read it, act on what it proposes, or continue it",
      rows.length ? ui.foldTable([{label: "topic"}, {label: "proposed", num: true}, {label: "epics made", num: true},
        {label: "description changes", num: true, hide: true}], rows) : ui.empty(`No discovery yet — it goes to ${(S.discover || {}).store || ""}.`));
}

// --- 2 backlog -----------------------------------------------------------------------------------------------------
// a list draws its marks' column only where one of its rows has a mark
const marked = list => list.some(r => MARKS[r.mark]);
const storyRow = (r, withMark) => [...(withMark ? [ui.mark(r.mark)] : []), ui.story(r.story, r.title) + ui.id(r.story, {block: true}),
  esc(r.state), esc(r.stage === "—" ? "" : r.stage), esc(r.tokens_text), acts(r.actions)];
const storyCols = withMark => [...(withMark ? [{label: "state", sr: true, mark: true}] : []), {label: "story"}, {label: "state"},
  {label: "stage", hide: true}, {label: "tokens", num: true, hide: true}, {act: true}];

// where a story stands, as a lane of its epic — the factory's `lane`
const LANES = ["draft", "approved", "running", "delivered"];
const laneOf = r => r.lane || "approved";
// a segment a story, in the lanes' order from left to right — draft, released, on its way, delivered —, the superseded
// last: the strip reads as the lanes beneath it
const STRIP = ["draft", "approved", "running", "stopped", "delivered", "superseded"];
const segment = r => r.mark === "stopped" ? "stopped" : laneOf(r);
const stripOf = rows => rows.map(segment).sort((a, b) => STRIP.indexOf(a) - STRIP.indexOf(b));
const STRIP_KEY = [["draft", "draft"], ["approved", "released"], ["running", "on its way"], ["stopped", "stopped"], ["delivered", "delivered"], ["superseded", "superseded"]];
const cardOf = r => ({id: r.story, title: r.title, state: segment(r), actions: acts(r.actions),
  line: `${r.state}${r.stage && r.stage !== "—" ? ` · ${r.stage}` : ""}${r.delivered_text ? ` · ${r.delivered_text}` : ""}`});
function laneProps(name, rows, order, epic) {
  if (name === "delivered") rows = rows.slice().sort((a, b) => order.indexOf(a.story) - order.indexOf(b.story));
  const shown = name === "delivered" ? rows.slice(0, 3) : rows, key = `lane:${epic}:${name}`;
  return {name, cards: shown.map(cardOf), more: rows.slice(shown.length).map(cardOf), key, open: opened(key)};
}
// what an epic needs first, in one word: stopped, waiting for a person, running, a draft to release, ready, done
function epicTone(e) {
  const n = m => e.rows.filter(r => r.mark === m && laneOf(r) !== "draft").length;
  const drafts = e.rows.filter(r => laneOf(r) === "draft").length, ready = e.rows.filter(r => r.state === "ready").length;
  if (n("stopped")) return ui.state(`${n("stopped")} stopped`, "stopped");
  if (n("look") + n("question")) return ui.state(`${n("look") + n("question")} waits for you`, "waiting");
  if (n("running")) return ui.state("running", "running");
  if (drafts) return ui.state(`${drafts} draft${drafts === 1 ? "" : "s"}`, "draft");
  if (e.total && e.delivered === e.total) return ui.state("delivered", "delivered");
  return ready ? ui.state(`${ready} ready`, "ready") : "";
}

function backlog(st) {
  // the epics as one list, as the cockpit shows them; an epic opens its stories in place, and stays open on a redraw
  const filter = S.backlogFilter || "all", order = st.delivered_order || [];
  const keep = r => filter === "all" || (filter === "drafts" ? r.lane === "draft" : !["delivered", "superseded"].includes(r.lane));
  const shown = (st.epics || []).map(e => Object.assign({}, e, {rows: e.rows.filter(keep)})).filter(e => filter === "all" || e.rows.length);
  const counts = {all: (st.epics || []).length,
    open: (st.epics || []).filter(e => e.rows.some(r => !["delivered", "superseded"].includes(r.lane))).length,
    drafts: (st.epics || []).filter(e => e.rows.some(r => r.lane === "draft")).length};
  const filters = ui.toolbar(ui.switch(["all", "open", "drafts"].map(f => ({label: f, pressed: f === filter, n: counts[f], attrs: {"data-filter": f}})), {label: "which epics"}));
  const epics = shown.map(e => {
    const full = (st.epics || []).find(x => x.epic === e.epic) || e, key = `epic:${e.epic}`;
    return ui.epic({key, open: opened(key, filter !== "all"), title: e.title || e.epic, id: e.epic, metric: e.metric, tone: epicTone(full),
      count: `${full.delivered}/${full.total}`, strip: stripOf(full.rows), stripTitle: `${full.delivered} of ${full.total} delivered`,
      body: () => (e.goal ? ui.intro(e.goal) : "") + qualityLine(full.signals)
        + (e.rows.length ? ui.lanes(LANES.map(name => laneProps(name, e.rows.filter(r => laneOf(r) === name || (name === "delivered" && laneOf(r) === "superseded")), order, e.epic)))
          : ui.empty("No story yet."))
        // the epic's own buttons, and beside them why one is offered — a delivered epic without its journey
        + ui.actions(acts(e.actions) + (st.journeys || []).filter(j => j.epic === e.epic).map(j => ui.hint(j.text)).join(""))});
  }).join("");
  const findings = (st.findings || []).map(f => [ui.state(f.severity, f.severity), `${esc(f.plain || f.defect)}${ui.id(`${f.row} · ${f.where}`, {block: true})}`, act(f.action)]);
  return wishPart(st)
    + (epics || filter !== "all" ? ui.card("Epics", filter === "all" ? "newest first — open one to see its stories by where they stand" : filter === "drafts" ? "the drafts, waiting for your release" : "what is not delivered yet",
        filters + ui.legend(STRIP_KEY) + (epics || ui.empty("Nothing here.")))
      : ui.card("", "", ui.empty("The backlog is empty.")))
    + (findings.length ? ui.accordion({key: "findings", variant: "card", level: 2, open: opened("findings"),
        head: `Findings ${ui.hint(`${findings.length} the judge kept open — each to the backlog or done`)}`,
        body: () => ui.table([{label: "severity"}, {label: "finding"}, {act: true}], findings)}) : "");
}

// --- 3 run ---------------------------------------------------------------------------------------------------------
function run(st) {
  const w = st.worker, reqs = (S.requests || {}).requests || [];
  // the backlog is the one thing switched here: a person's requests are worked while this page is open (WP-177)
  const factory = (backlogOn(st) ? (w.stopping ? ui.intro("Stopping after the running stage.")
      : ui.actions(ui.btn("■ stop the backlog — after the running stage", {attrs: {"data-call": "down"}})
        + ui.btn("■ stop now", {danger: true, attrs: {"data-call": "down", "data-now": "1"}})))
    : ui.actions(ui.btn("▶ start the backlog", {primary: true, plain: true, attrs: {"data-call": "up"}})))
    + (w ? ui.accordion({key: "worker", variant: "quiet", open: opened("worker"), head: "the worker",
        body: () => ui.kv([["worker", esc(w.owner)], ["since", esc(w.since_text)], w.log ? ["log", `<code>${esc(w.log)}</code>`] : null])}) : "");
  const ops = r => (r.operations || []).map(op => ui.btn(op.label, {small: true, danger: op.name === "drop",
    attrs: {"data-call": op.name, "data-kind": "request", "data-id": r.id}})).join("");
  const tickets = reqs.map(r => ui.ticket({kind: r.kind, target: r.target, word: r.state, state: r.state, id: `${r.id} · ${r.by}`,
    error: r.error, note: r.record ? `asks: <code>${esc(r.record)}</code> — answer it under Decide` : "", actions: ops(r)})).join("");
  const titles = Object.fromEntries((st.rows || []).map(r => [r.story, r.title]));
  // a story in flight as its course: running, or stopped where it goes on from, with why and what goes on
  const follows = id => ui.btn("follow", {small: true, attrs: {"data-call": "follow", "data-kind": "story", "data-id": id}});
  const live = (st.running || []).map(r => ui.course({id: r.story, title: titles[r.story], state: r.interrupted ? "interrupted" : "running",
      word: r.interrupted ? "interrupted" : `${r.part || r.stage}${r.round > 1 ? ` · round ${r.round}` : ""}`,
      steps: r.course, doing: r.activity, right: ui.hint(r.ago || "") + follows(r.story)})).join("")
    + (st.waiting || []).filter(x => x.mark === "stopped" && !(st.running || []).some(r => r.story === x.story))
      .map(x => ui.course({id: x.story, title: titles[x.story], state: "stopped", word: "stopped", steps: x.course,
        doing: (x.action && x.action.text) || x.what, right: act(x.action) + follows(x.story)})).join("");
  const readyRows = (st.rows || []).filter(r => st.queue && st.queue.ready.includes(r.story)), readyMarked = marked(readyRows);
  return ui.card("The backlog", backlogOn(st) ? "on — the released stories one after the other"
        : `off — ${(st.queue || {ready: []}).ready.length} released stories would run`, factory)
    + wishPart(st)
    + ui.card("Running", "a story's course through its stages — running, or stopped where it goes on", live || ui.empty("No stage runs."))
    + ui.card("Output", `<span id="follow-title" data-own></span>`, ui.terminal())
    + ui.card("Requests", "everything asked of the factory, oldest first", tickets ? ui.queue(tickets) : ui.empty("No request waits."))
    + (readyRows.length ? ui.card("Next in line", "ready, in the order the factory takes them", ui.table(storyCols(readyMarked), readyRows.map(r => storyRow(r, readyMarked)))) : "");
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
  // the output is a card of the run page: the story's drawer would hide it, so it closes, and the card comes into view
  if (S.drawer) CALLS.close();
  if (S.tab !== "run") show("run"); else paintFollow();
  if (kind) requestAnimationFrame(() => { const out = $("follow-out"); if (out) out.closest("section").scrollIntoView({behavior: "smooth", block: "start"}); });
}

function paintFollow() {
  const out = $("follow-out");
  if (!out) return;
  $("follow-title").textContent = S.follow ? `${S.follow.kind} ${S.follow.id}` : "follow a running stage or request";
  $("follow-acts").innerHTML = S.follow ? ui.btn("stop following", {attrs: {"data-call": "unfollow"}}) : "";
  const atEnd = out.scrollTop + out.clientHeight >= out.scrollHeight - 20;   // at the end it follows the newest line
  const text = S.followLines.join("\n") || (S.follow ? "waiting for output…" : "");
  if (out.textContent !== text) out.textContent = text;
  if (atEnd) out.scrollTop = out.scrollHeight;
}

// --- 4 decide ------------------------------------------------------------------------------------------------------
function recordCard(r) {
  const offered = (r.actions || []).filter(a => !a.waits_on), accept = r.kind === "acceptance";
  const options = offered.filter(a => a.request.open !== "words" && !accept);
  const words = offered.filter(a => a.request.open === "words");
  // what to look at is the acceptance itself and stands open; a question's full text folds under its answers
  const key = `more:${r.id}`;
  const full = (r.sections || []).length ? ui.accordion({key, variant: "quiet", open: opened(key, accept),
    head: accept ? "what to look at" : "the question in full", body: () => r.sections.map(one => ui.section(one)).join("")}) : "";
  const body = (accept ? full : "")
    + (accept ? ui.actions(acts(offered.filter(a => a.request.open !== "words")))
      : options.length ? ui.options(options.map(a => ({advised: a.primary, pick: act(a),
          text: inline(a.text) + (a.note ? ` ${ui.hint("— " + a.note)}` : "")}))) : "")
    + words.map(a => `<h3>${accept ? "or correct it" : options.length ? "or in your words" : "your answer"}</h3>${act(a)}`).join("")
    + (accept ? "" : full)
    + ui.id(`${r.story ? `${ui.story(r.story, r.story)} · ` : ""}${esc(r.path)}`, {block: true, html: true});
  return ui.record({accept, about: `${accept ? "acceptance" : "question"} · ${r.id}${r.story ? ` · ${r.stage}` : ""}`, text: inline(r.text), body});
}

function decide(st) {
  const records = ((S.decisions || {}).records || []).filter(r => (r.actions || []).length && (r.place || "decide") === "decide");
  // a waiting story whose record is open stands above as that record; the others — a draft, a stopped story — here
  const waiting = (st.waiting || []).filter(w => !w.record), waitMarked = marked(waiting);
  const others = waiting.map(w => [...(waitMarked ? [ui.mark(w.mark)] : []), ui.story(w.story), esc(w.what),
    act(w.action) || ui.hint(w.action.text || w.action.skill || w.action.shell || "")]);
  const cols = [...(waitMarked ? [{label: "state", sr: true, mark: true}] : []), {label: "story"}, {label: "what waits"}, {act: true}];
  return records.map(recordCard).join("")
    + (others.length ? ui.card(records.length ? "Also waiting for you" : "", "", ui.table(cols, others)) : "")
    + (!records.length && !others.length ? ui.card("", "", ui.empty("Nothing waits for you.")) : "");
}

// --- 5 delivered ---------------------------------------------------------------------------------------------------
function curveCard(st) {
  const curve = st.delivered_curve || [];
  if (curve.length < 2) return "";
  S.curve = curve;
  const last = curve[curve.length - 1], unpriced = curve.length - last.priced_total;
  return ui.curve(curve) + (unpriced ? ui.hint(`${unpriced} deliver${unpriced === 1 ? "y carries" : "ies carry"} no price and add nothing to the cost.`, {block: true}) : "");
}
// quality: the signals the factory counts per story, summed — shown as counted, never rated
const sum = o => Object.values(o || {}).reduce((n, v) => n + v, 0);
const domainWords = o => Object.entries(o || {}).sort((a, b) => b[1] - a[1]).map(([c, n]) => `${n} ${c.replace(/^domain-/, "")}`).join(" · ");
function qualityCard(q) {
  if (!q || !q.stories) return "";
  const domain = sum(q.domain), corrected = sum(q.corrections);
  const tiles = [
    [`${q.answered}/${q.asked}`, "questions answered", "a stage asked, a person answered", false],
    [`${q.assumptions_answered}`, "assumptions answered", `${q.assumptions_open} still open`, !!q.assumptions_open],
    [`${q.plan_open}`, "left open by plans", "what a plan named and did not decide", false],
    [`${domain}`, "domain findings", domain ? domainWords(q.domain) : "none confirmed", !!domain],
    [`${corrected}`, "corrections at acceptance", corrected ? domainWords(q.corrections) : "none", !!corrected],
  ].map(([n, label, said, bad]) => ui.tile(n, label, {said, bad})).join("");
  const found = Object.entries(q.findings || {}).sort((a, b) => b[1] - a[1]), most = found.length ? found[0][1] : 1;
  // the rules a broken implementation was tried against: one tile, the count by kind on hover
  const counted = `killed ${q.killed} · red ${q.red} · survived ${q.survived} · no-break ${q["no-break"]} — of ${q.stories} stories: ${q.measured} measured, ${q.not_measured} tested before rules were recorded, ${q.without_test || 0} without a test stage, ${q.open || 0} not delivered`;
  const ruleTile = ui.tile(q.named ? `${q.killed}/${q.named}` : "–", "rules caught when broken", {said: `${q.measured} of ${q.stories} stories measured`, bad: !!q.survived, title: counted});
  return ui.card("Quality", "what the stages asked, what the judge confirmed, what a person corrected — counted over every story, never rated",
    ui.tiles(tiles + ruleTile, {many: true})
    + (found.length ? `<h3>Findings the judge confirmed, by perspective</h3>${ui.bars(found.map(([name, n]) => [name, n, Math.round(100 * n / most)]))}` : ""));
}
// the same figures in one line, for an epic
function qualityLine(q) {
  if (!q || !q.stories) return "";
  const domain = sum(q.domain), found = Object.entries(q.findings || {}).sort((a, b) => b[1] - a[1]);
  return ui.figures([["questions", `${q.answered}/${q.asked}`],
    ["assumptions", `${q.assumptions_answered}${q.assumptions_open ? ` · ${q.assumptions_open} open` : ""}`, !!q.assumptions_open],
    ["left open by plans", `${q.plan_open}`],
    found.length ? ["findings", found.map(([n, c]) => `${esc(n)} ${c}`).join(" · ")] : null,
    ["domain", domain ? esc(domainWords(q.domain)) : "0", !!domain],
    q.named ? ["rules caught when broken", `${q.killed}/${q.named}`, !!q.survived] : null]);
}

function delivered(st) {
  const rows = Object.fromEntries((st.rows || []).map(r => [r.story, r])), events = Object.fromEntries((st.epics || []).map(e => [e.epic, e.metric]));
  const tiles = [[`${st.delivered}`, `of ${st.total} stories delivered`, true], [st.seconds_text, "worked"], [st.tokens_text, "tokens"], [st.cost_text, "cost"]]
    .filter(([n]) => n).map(([n, label, lead]) => ui.tile(n, label, {lead})).join("");
  const days = [];
  for (const r of (st.delivered_order || []).map(id => rows[id]).filter(Boolean)) {
    const day = (r.delivered_text || "").slice(0, 10) || "undated";
    if (!days.length || days[days.length - 1].day !== day) days.push({day, rows: []});
    days[days.length - 1].rows.push({at: (r.delivered_text || "").slice(11), story: r.story, title: r.title, epic: r.epic,
      event: events[r.epic], seconds: r.seconds_text, tokens: r.tokens_text, cost: r.cost_text});
  }
  return ui.card("Delivered", "what is delivered, and what it cost as it summed up", ui.tiles(tiles) + curveCard(st))
    + qualityCard(st.signals)
    + ui.card("By day", "each delivery with the outcome event its epic is measured by", days.length ? ui.days(days) : ui.empty("Nothing delivered yet."));
}

// --- 6 the rules: the factory's rulebook, drawn as it says it ------------------------------------------------------------
async function loadRules() {
  const want = S.ruleStory || "";
  if (S.rules && S.rulesFor === want) return;
  S.rulesFor = want;
  if (await load("rules", "/api/view/rules" + (want ? `?id=${encodeURIComponent(want)}` : ""))) render();
}
// a rule read as sentences: its title, why, when, and each outcome after its keyword, where it sends the story
const SAYS = {pass: "Passes when", fail: "Fails when", skip: "Skips when", note: "Notes when", wait: "Waits when", ask: "Asks when"};
const sentence = t => { const s = String(t || "").trim(); return s ? s[0].toUpperCase() + s.slice(1) + (/[.!?)]$/.test(s) ? "" : ".") : ""; };
const clause = t => { const s = String(t || "").trim(); return s + (/[.!?)]$/.test(s) ? "" : "."); };
const going = goes => (goes || []).length ? `→ ${goes.map(g => g === "stop" ? "stop" : g === "again" ? "once more" : "back to " + g).join(" or ")}` : "";

function ruleRow(id, rules, story, stage) {
  const r = rules[id] || {id, enforcement: "", outcomes: []}, key = `rule:${id}`;
  const fired = story && story.fired[id] ? story.fired[id].filter(f => !stage || f.stage === stage) : [];
  const state = fired.some(f => f.state === "fail") ? "fail" : fired.length ? fired[fired.length - 1].state : "";
  const refused = story && story.refused[id];
  const head = r.title ? sentence(r.title).replace(/\.$/, "") : r.text ? r.text.replace(/\s+/g, " ").slice(0, 140) + (r.text.length > 140 ? "…" : "") : sentence(r.why || r.when);
  return ui.accordion({key, variant: "row", open: opened(key), head: inline(head), meta: ui.ruleId(id, r.enforcement, state, refused),
    body: () => (r.text ? ui.said("Where", inline(clause(r.when))) + ui.prose(r.text)
      : (r.why ? ui.intro(inline(sentence(r.why)), {html: true}) : "") + ui.said("When", inline(clause(r.when)))
        + (r.outcomes || []).map(o => ui.said(SAYS[o.state] || o.state, inline(clause(o.said)), {icon: o.state, state: o.state, goes: going(o.goes)})).join(""))
      + (fired.length ? ui.note(`this story: ${fired.map(f => `${f.stage}: ${f.state}`).join(" · ")}${refused ? ` · refused ${refused}×` : ""}`, {state: "wait"}) : "")
      + ui.accordion({key: `src:${id}`, variant: "quiet", open: opened(`src:${id}`), head: "source",
          body: () => ui.hint(`${r.source || ""}${r.bound ? (r.part === "instruction" ? " · placed in " : " · bound in ") + r.bound : ""}`, {block: true})})});
}
const ruleGroup = (label, ids, rules, story, stage) => ui.ruleGroup(label, (ids || []).map(id => ruleRow(id, rules, story, stage)));
const waysLine = (edges, title, rules) => {
  const named = id => (rules && rules[id] && rules[id].title) || id;
  return ui.ways(title, edges.map(e => ({source: e.source, target: e.target, key: `${e.source}>${e.target}>${e.way}`,
    rules: [...new Set(e.rules.map(r => named(r.rule)))].join(" · ")})));
};
function foldGroup(key, label, ids, rules, story, stage) {
  if (!ids || !ids.length) return "";
  return ui.accordion({key, variant: "quiet", open: opened(key), head: `${esc(label)} (${ids.length})`, body: () => ruleGroup("", ids, rules, story, stage)});
}
function folded(key, title, sub, ids, rules, story) {
  if (!ids || !ids.length) return "";
  return ui.accordion({key, variant: "card", level: 2, open: opened(key), head: `${esc(title)} ${ui.hint(`${ids.length} rules — ${sub}`)}`,
    body: () => ruleGroup("", ids, rules, story)});
}

function picked(flow, rules, story) {
  const graph = flow.graph || {edges: [], every_gate: [], anywhere: []}, p = S.flowPick;
  const ids = es => [...new Set(es.flatMap(e => e.rules.map(r => r.rule)))];
  if (!p) {
    return ui.card("", "", ui.empty("Pick a step, a gate or a way in the drawing — its rules show here.")
      + ui.hint(`<b>Four kinds of rule.</b> A <b>check</b> (GATE-…) is a question a gate asks after a stage — it passes or refuses. A <b>decision</b> (RUN-…) says where the story goes then: on, once more, back, or stop. A <b>pass</b> rule says what a passing gate does. What a stage is <b>told</b> (STAGE-…) is its instruction; no gate asks it directly.`, {block: true, html: true})
      + ui.hint("A teal dot is a gate: the checks between two steps. A dashed arc above is a round — a refused gate sends the story back into its step, three times at most. A way back appears below while the pointer is on its step. A red mark stops the run; a grey one waits for a person.", {block: true}));
  }
  if (p.type === "stage") {
    // a stage told as it runs: what it is told, the gate that asks, what a pass does, where a refusal sends it
    const step = flow.steps.find(s => s.stage === p.stage) || {gate_before: [], told: [], gate_after: [], passed: [], decided: []};
    const at = flow.steps.findIndex(s => s.stage === p.stage), next = (flow.steps[at + 1] || {}).stage || "delivered";
    const own = e => e.source === p.stage;
    const round = graph.edges.find(e => own(e) && e.way === "again"), on = graph.edges.find(e => own(e) && e.way === "on" && e.rules.length);
    const out = graph.edges.filter(e => own(e) && e.way === "back"), into = graph.edges.filter(e => e.target === p.stage && e.way === "back");
    const stops = graph.edges.filter(e => own(e) && (e.way === "stop" || e.way === "waits"));
    const named = new Set([round, on, ...out, ...stops].filter(Boolean).flatMap(e => e.rules.map(r => r.rule)));
    const rest = (step.decided || []).filter(id => !named.has(id));
    // a stage told as it runs: before it, while it runs, after it — where a pass and a refusal part ways —, and what else
    const passes = ui.part(`${step.gate === "none" ? "if its verdict is yes" : "if the gate passes"} ${ui.hint(`→ on to <b>${esc(next)}</b>`, {html: true})}`,
      ruleGroup("", [...(step.passed || []), ...(on ? on.rules.map(r => r.rule) : [])], rules, story, p.stage) || " ", {branch: true, level: 4});
    const refuses = ui.part(step.gate === "none" ? "if it asks for changes" : "if a check refuses",
      (round ? ruleGroup("once more into this stage", ids([round]), rules, story, p.stage) : "")
      + waysLine(out, "back to an earlier stage", rules) + (stops.length ? ruleGroup("stop, or wait for a person", ids(stops), rules, story, p.stage) : ""),
      {branch: true, level: 4});
    return ui.card(esc(p.stage), esc((step.window || "") + (step.gate === "none" ? " · decides with its verdict, no gate" : "")),
      ui.part(`Before ${ui.hint("— the gate before the stage asks; a refusal keeps it from starting")}`, ruleGroup("", step.gate_before, rules, story, p.stage))
      + ui.part(`While it runs ${ui.hint(`— it is told ${(step.told || []).length} instructions`)}`, foldGroup(`told:${p.stage}`, "show what it is told", step.told, rules, story, p.stage))
      + ui.part(`After ${ui.hint(step.gate === "none" ? "— its verdict decides, no gate" : (step.gate_after || []).length ? `— the gate asks ${(step.gate_after || []).length} checks, each can refuse` : "— the gate after it asks no checks")}`,
          foldGroup(`checks:${p.stage}`, "show the checks", step.gate_after, rules, story, p.stage) + ui.branches(passes, refuses) || " ")
      + ui.part("The runner also decides here", ruleGroup("", rest, rules, story, p.stage), {aside: true})
      + (into.length ? ui.part("Ways back to this stage", waysLine(into, "", rules), {aside: true}) : ""));
  }
  if (p.type === "gate") {
    const [where, stage] = p.gate.split(":"), step = flow.steps.find(s => s.stage === stage) || {};
    const round = graph.edges.find(e => e.source === stage && e.target === stage && e.way === "again");
    return ui.card(`gate ${esc(where === "gate-before" ? "before" : "after")} ${esc(stage)}`,
      where === "gate-before" ? "a refused check keeps the stage from starting" : "a refused check sends the story once more into its step",
      ruleGroup("its checks — each can refuse", (where === "gate-before" ? step.gate_before : step.gate_after) || [], rules, story, stage)
      + (where === "gate-after" && round ? ruleGroup("when one refuses — what decides where the story goes", ids([round]), rules, story, stage) : "")
      + ruleGroup("also at every gate", flow.every_gate, rules, story, stage));
  }
  const edge = graph.edges.concat(graph.every_gate || [], graph.anywhere || []).find(e => `${e.source}>${e.target}>${e.way}` === p.key);
  if (p.way === "again") {
    const step = flow.steps.find(s => s.stage === p.source) || {};
    return ui.card(`${esc(p.source)} once more`, step.gate === "after" ? "a refused check of its gate sends the story back into it" : "the stage runs again",
      ruleGroup("what sends it once more", edge ? ids([edge]) : [], rules, story, p.source)
      + (step.gate === "after" ? ruleGroup(`the checks of the gate after ${p.source} — each can refuse`, step.gate_after, rules, story, p.source) : ""));
  }
  return ui.card(`${esc(p.source)} → ${esc(p.target)}`, esc(p.way), ruleGroup("the rules that take it", edge ? ids([edge]) : [], rules, story, p.source));
}

// a story laid over the drawing: the steps its gates ran at, where it stands, which gate refused it and how often
function storyMarks(flow, story) {
  if (!story) return null;
  // the steps run in order: every step before the last one the story's gates ran at was reached too (a judge has none)
  const ran = new Set(Object.values(story.fired).flat().map(f => f.stage));
  const last = Math.max(-1, ...flow.steps.map((s, i) => ran.has(s.stage) ? i : -1));
  const reached = new Set([...ran, ...flow.steps.slice(0, last + 1).map(s => s.stage)]);
  const at = story.refused_at || {};
  const gates = flow.steps.filter(s => s.gate === "after").map(s => {
    const refused = Object.values(at[s.stage] || {}).reduce((n, k) => n + k, 0);
    const failed = (s.gate_after || []).some(id => (story.fired[id] || []).some(f => f.stage === s.stage && f.state === "fail"));
    return {stage: s.stage, refused, failed};
  });
  return {reached, gates};
}
function storyLine(st, flow, story) {
  if (!story) return "";
  const row = (st.rows || []).find(r => r.story === story.id) || {};
  const marks = storyMarks(flow, story), refused = marks.gates.filter(g => g.refused);
  const other = [...marks.reached].filter(name => !flow.steps.some(s => s.stage === name));
  return ui.intro(`<b>${esc(story.id)}</b> — ${esc(row.state || "")}${row.stage && row.stage !== "—" ? `, now at <b>${esc(row.stage)}</b>` : ""}.
    ${refused.length ? "Refused: " + refused.map(g => `${esc(g.stage)} ×${g.refused}`).join(", ") + "." : "No gate refused it."}
    ${other.length ? ui.hint(`It also ran ${other.join(", ")} — another kind's steps; pick that kind to see them.`) : ""}`, {html: true});
}

function rulesTab(st) {
  if (!S.rules) { loadRules(); return ui.card("", "", ui.empty("Reading the rules…")); }
  const v = S.rules, rules = Object.fromEntries((v.rules || []).map(r => [r.id, r]));
  const story = v.story || null;
  const kinds = Object.keys(v.flow || {});
  if (story && S.kindFor !== story.id) {
    S.kindFor = story.id;
    const ran = new Set(Object.values(story.fired).flat().map(f => f.stage));
    const fits = kinds.filter(k => [...ran].every(x => v.flow[k].steps.some(s => s.stage === x)))
      .sort((a, b) => v.flow[a].steps.length - v.flow[b].steps.length);
    if (fits.length) S.ruleKind = fits[0];
  }
  const kind = kinds.includes(S.ruleKind) ? S.ruleKind : kinds[0];
  const flow = (v.flow || {})[kind] || {steps: [], edges: [], every_gate: []};
  const stories = (st.rows || []).map(r => r.story);
  const picks = ui.toolbar(ui.switch(kinds.map(k => ({label: k, pressed: k === kind, attrs: {"data-flow": k}})), {label: "which kind of story"})
    + ui.formRow({id: "overlay", label: "a story's gate runs", quiet: true, inline: true, attrs: {"data-overlay": ""},
        options: [{value: "", label: "no story"}, ...stories.map(id => ({value: id, selected: id === S.ruleStory}))]}));
  return ui.card(esc(kind), `${(v.rules || []).length} rules`, picks + storyLine(st, flow, story) + (flow.svg_one_at_a_time ? ui.flow(flow.svg_one_at_a_time) : ""))
    + picked(flow, rules, story)
    + folded("every-gate", "At every gate", "the checks each gate of this flow runs as well", flow.every_gate, rules, story)
    + folded("anywhere", "Anywhere in a run", "what stops a run or waits for a person at any step",
             [...new Set(((flow.graph || {}).anywhere || []).flatMap(e => e.rules.map(r => r.rule)))], rules, story)
    + folded("outside", "Outside the stages", "the whole run, the commit hook, every stage alike", v.outside || [], rules, story)
    + ((v.problems || []).length ? ui.card("Problems", "the rulebook itself", `<ul>${v.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul>`) : "");
}

// --- one story -----------------------------------------------------------------------------------------------------
async function openStory(id) {
  if (!S.drawer) S.opener = document.activeElement;
  S.drawer = id;
  // below the bar, so the tabs and the factory's state stay in reach
  document.documentElement.style.setProperty("--bar-height", $("topbar").getBoundingClientRect().height + "px");
  const node = $("drawer"), close = ui.btn("close", {attrs: {"data-call": "close"}});
  node.hidden = false;
  node.innerHTML = ui.drawerFrame(close, "", ui.empty(`Reading ${id}…`));
  node.focus();
  let v;
  try { v = await api(`/api/view/story?id=${encodeURIComponent(id)}`); }
  catch (e) { node.innerHTML = ui.drawerFrame(close, "", ui.error(e.message, {block: true})); return; }
  if (S.drawer !== id) return;
  forget("d");
  const row = v.row || {};
  // the factory's sections in its order, the scenarios where its criteria stood
  const scenarios = (v.scenarios || []).map(c => `<h3>${esc(c.title || c.key)}</h3>${c.rule ? ui.hint(c.rule, {block: true}) : ""}
    ${(c.steps || []).map(s => ui.step(s.word, s.text)).join("")}`).join("");
  const list = v.sections || [], at = v.criteria_at == null ? list.length : v.criteria_at;
  const sections = list.slice(0, at).map(one => ui.section(one, 2)).join("") + (scenarios ? `<h2>Scenarios</h2>${scenarios}` : "")
    + list.slice(at).map(one => ui.section(one, 2)).join("");
  const stages = Object.entries(v.stages || {}).map(([name, e]) => [esc(name), e.runs || "", esc(e.seconds_text), esc(e.tokens_text), esc(e.cost_text), ui.id(e.why || "")]);
  const head = ui.pageHead(v.epic, v.title || id, "")
    + ui.kv([["story", ui.id(id)], ["state", esc(row.state || v.situation || "")], v.context ? ["context", esc(v.context)] : null,
             ["file", `<code>${esc(v.path)}</code>`], row.tokens_text ? ["tokens", `${esc(row.tokens_text)}${row.cost_text ? " · " + esc(row.cost_text) : ""}`] : null]);
  const body = ui.actions(acts((v.actions || []).filter(a => a.request.open !== "words"), "d")
      + (Object.keys(v.stages || {}).length || row.mark === "running" ? ui.btn("output", {attrs: {"data-call": "follow", "data-kind": "story", "data-id": id}}) : ""))
    + (v.actions || []).filter(a => a.request.open === "words" && !a.waits_on).map(a => `<h2>${esc(a.label)}</h2>${act(a, "d")}`).join("")
    + sections
    + (stages.length ? `<h2>Processes</h2>${ui.table([{label: "process"}, {label: "runs", num: true}, {label: "time", num: true}, {label: "tokens", num: true},
        {label: "cost", num: true, hide: true}, {label: "why"}], stages)}` : "");
  node.innerHTML = ui.drawerFrame(close, head, body);
}
"""

#: The pattern library (`#components`): every component, by level, in its variants and states — drawn with the page's
#: own components and whatever theme the project gives it, so it cannot drift from what runs.
SCRIPT_GALLERY = r"""
// --- the pattern library: every component, by level, in its variants and states ---------------------------------------
function components() {
  const sample = {story: "a-reader-borrows-a-book", title: "A reader borrows a book", epic: "lending"};
  const lines = ["- Given a reader with no loan", "- When they borrow a book", "- Then the book is lent to them"];
  const curve = [{at: "2026-10-01T09:00:00Z", story: "one", title: "the first", cost_total: 4, tokens_total: 1e6, cost: 4, tokens: 1e6},
                 {at: "2026-10-08T09:00:00Z", story: "two", title: "the second", cost_total: 9, tokens_total: 3e6, cost: 5, tokens: 2e6},
                 {at: "2026-10-15T09:00:00Z", story: "three", title: "the third", cost_total: 15, tokens_total: 4.5e6, cost: 6, tokens: 1.5e6}];
  S.curve = curve;
  const states = ["success", "warning", "danger", "info", "done", "delivered", "running", "waiting", "queued", "draft", "stopped", "failed", "superseded"];
  const card = {id: sample.story, title: sample.title, line: "ready · plan", actions: ui.btn("run it", {small: true, primary: true})};
  return ui.gallery([
    {level: "atoms — controls", items: [
      ["btn", [ui.btn("change this"), ui.btn("accept", {primary: true}), ui.btn("✦ draft it", {write: true}), ui.btn("draft it", {primary: true, write: true}),
               ui.btn("▶ start", {primary: true, plain: true}), ui.btn("drop", {danger: true}), ui.btn("open", {small: true})].join(" ")],
      ["link", `${ui.link("a link in a sentence")} · ${ui.link("a story's title", {title: true})} · ${ui.link("all →", {to: true})} · ${ui.link("plan → test", {way: true})} · ${ui.link("a quiet head", {plain: true})}`],
      ["switch", ui.switch([{label: "all", pressed: true, n: 12}, {label: "open", n: 4}, {label: "drafts", n: 1}], {label: "which"})],
      ["select · field", ui.formRow({id: "g-select", label: "a select", options: [{value: "one"}, {value: "two"}]})
        + ui.formRow({id: "g-field", label: "a field", value: "words"})],
      ["caret", `${ui.caret(false)} ${ui.caret(true)}`]]},
    {level: "atoms — form text", items: [
      ["label · hint · error", `${ui.label("A label", "g-field")} ${ui.hint("what the field takes")} ${ui.error("what was wrong")}`]]},
    {level: "atoms — displays", items: [
      ["term", `${ui.term("Loan")} ${ui.term("Reader", {minor: true})} ${ui.term("Money", {shared: true})}`],
      ["event", ui.event("BookLent")],
      ["state", states.map(s => ui.state(s, s)).join(" ")],
      ["mark", Object.keys(MARKS).filter(m => MARKS[m]).map(ui.mark).join(" ")],
      ["icon", ["pass", "fail", "wait", "ask", "minor"].map(ui.icon).join(" ")],
      ["num", `${ui.num("22")} ${ui.num("4.2", "M")}`],
      ["id", ui.id(sample.story)],
      ["dot", ["up", "stopping", "down"].map(ui.dot).join(" ")],
      ["spinner", ui.spinner()],
      ["meter", `${ui.meter(64)} ${ui.meter(30, {thin: true})}`],
      ["flag", `${ui.flag("test gone", "gone")} ${ui.flag("changes by x", "changes")} ${ui.flag("adds", "adds")}`],
      ["pill", ["core", "supporting", "generic"].map(k => ui.pill(k, k)).join(" ")],
      ["empty · intro · note", ui.empty("Nothing here.") + ui.intro("What a card says first.") + ui.note("asks: a record", {state: "wait"})],
      ["rule-id", `${ui.ruleId("GATE-TESTS", "gate", "pass")} ${ui.ruleId("RUN-ROUND-1", "runner", "fail", 2)} ${ui.ruleId("STAGE-PLAN-1", "instructed")}`]]},
    {level: "molecules", items: [
      ["story", ui.story(sample.story, sample.title)],
      ["form-row", ui.formRow({id: "g-row", label: "Your name", hint: "as it stands beside your requests", value: "Ann"})
        + ui.formRow({id: "g-row-bad", label: "A story id", value: "Not An Id", error: "an id is lower case words joined by -"})],
      ["ask", ui.ask({id: "g-ask", draft: "gallery-ask", label: "wish", text: "What should exist?", primary: true, write: true, choices: ["too big", "unclear"]})],
      ["actions", ui.actions(ui.btn("release", {primary: true}) + ui.btn("change this"))],
      ["tile", ui.tiles(ui.tile("22", "of 26 stories delivered", {lead: true}) + ui.tile("3", "domain findings", {bad: true, said: "2 model · 1 language"}) + ui.tile("$41", "cost"))],
      ["kv", ui.kv([["story", ui.id(sample.story)], ["state", "ready"]])],
      ["toast", ui.toast("request written: r-12") + ui.toast("the gate refused", true)],
      ["legend · strip", ui.legend(STRIP_KEY) + ui.strip(["draft", "approved", "running", "stopped", "delivered", "superseded"], "the strip")],
      ["said", ui.said("Given", "a reader with no loan") + ui.said("Fails when", "the tests are red.", {icon: "fail", state: "fail", goes: "→ once more"})],
      ["figures · bars", ui.figures([["questions", "3/4"], ["domain", "2", true]]) + ui.bars([["ddd", 4, 100], ["hexagonal", 1, 25]])],
      ["toolbar", ui.toolbar(ui.switch([{label: "story", pressed: true}, {label: "task"}]))],
      ["inflow · quiet-line", ui.inflow("Inflow →", "a wish, a discovery, a finding fill the backlog") + ui.quietLine(`Beside that: ${ui.link("2 open findings →")}`)],
      ["notice", ui.notice("What comes next stands here.") + ui.notice("The factory ended on its own.", {ended: true, action: ui.btn("▶ start", {primary: true, plain: true})})],
      ["story-card", `<ul>${["draft", "approved", "running", "stopped", "delivered", "superseded"].map(s => ui.storyCard(Object.assign({}, card, {state: s}))).join("")}</ul>`],
      ["ticket", `<ul>${ui.ticket({kind: "wish", target: "", word: "running", state: "running", id: "r-12 · Ann", actions: ui.btn("take back", {small: true, danger: true})})}</ul>`],
      ["option", `<ul>${ui.option({advised: true, pick: ui.btn("a", {primary: true}), text: "the recommended answer"}) + ui.option({pick: ui.btn("b"), text: "another answer"})}</ul>`],
      ["list-item", ui.list([{mark: "done", what: ui.story(sample.story, sample.title), aside: "today 10:12<br>$3.10"}])],
      ["delivery", ui.delivery({head: true}) + ui.delivery({at: "10:12", story: sample.story, title: sample.title, epic: sample.epic, event: "BookLent", seconds: "14 min", tokens: "4.1 M", cost: "$3.10"})],
      ["domain-node · facts · rule-block", ui.domainNode("Domain model", "from its glossary")
        + ui.facts([{kind: "aggregate", terms: [{name: "Loan"}]}, {kind: "values", terms: [{name: "Due date"}, {name: "Money", shared: true}]}])
        + ui.ruleBlock("A reader holds three loans at most.", [ui.accordion({key: "gallery:scenario", variant: "row", open: false, head: "a fourth loan is refused"})])],
      ["proposal", `<ul>${ui.proposal({goal: "Readers find a free copy", intent: "fewer empty shelves", metric: "CopyFound", contact: "the desk", id: "p-1", actions: ui.btn("✦ make it an epic", {write: true})})}</ul>`],
      ["aside · section · prose", ui.aside("Why it is not built", ui.prose("It **waits** for `a-reader-joins`.")) + ui.section({heading: "Scope", text: "- one\n- two"})],
      ["trail · trail-item", ui.trail([{words: "readers may reserve", tone: "wait", text: "writing", by: "Ann", actions: ""}, {words: "a due-date reminder", tone: "ok", text: "✓ became the draft story x", actions: ui.btn("open", {small: true})}]) + `<ul>${ui.trailItem({words: "fines in another currency", tone: "bad", text: "✗ failed", actions: ""})}</ul>`],
      ["tab", ui.tab({id: "gallery-a", key: 9, n: 2, on: true}) + ui.tab({id: "gallery-b", key: 8})],
      ["step", lines.map(l => l.slice(2).split(" ")).map(([w, ...rest]) => ui.step(w, rest.join(" "))).join("")]]},
    {level: "organisms", items: [
      ["card", ui.card("A card", "what it holds", ui.intro("Its body."))],
      ["accordion", ["row", "quiet", "group", "ink", "panel", "card"].map(variant => ui.accordion({key: `gallery:${variant}`, variant, open: opened(`gallery:${variant}`, variant === "row"),
        level: variant === "card" ? 3 : 0, head: `the ${variant} fold`, meta: ui.hint("meta"), body: () => ui.intro("What it folds.")})).join("")],
      ["fold-table", ui.foldTable([{label: "context"}, {label: "features", num: true}, {label: "criteria", num: true}],
        [{key: "gallery:ft:lending", open: opened("gallery:ft:lending"), cells: ["<b>lending</b>", "1", "2"], body: () => ui.intro("What it folds.")},
         {key: "gallery:ft:catalogue", open: false, cells: ["<b>catalogue</b>", "3", "14"], body: ""}])],
      ["tabs", ui.tabs([{tabs: [{id: "gallery-c", key: 1}, {id: "gallery-d", key: 2, on: true}], ordered: true}])],
      ["board · column", ui.board([ui.column({name: "backlog", count: 4, line: "released — 2 more blocked", items: [ui.story(sample.story, sample.title)], actions: ui.btn("run it", {primary: true})}),
        ui.column({name: "decide", count: 1, line: "waits for you", hot: true, items: ["a question"]}),
        ui.column({name: "delivered", count: 22, of: 26, line: "85 %", meter: 85, actions: ui.link("all →", {to: true})})])],
      ["wish", ui.wish(ui.ask({id: "g-wish", draft: "gallery-wish", label: "wish", text: "What should exist?", primary: true, write: true}),
        [{words: "readers may reserve", tone: "ask", text: "? asks back", actions: ui.btn("answer", {small: true, primary: true})}])],
      ["list", ui.list([{mark: "done", what: "one delivery"}, {mark: "done", what: "another"}])],
      ["lane · lanes", ui.lanes(["draft", "approved", "running", "delivered"].map(name => ({name, key: `gallery:lane:${name}`, open: false,
        cards: name === "running" ? [Object.assign({}, card, {state: "running"})] : [], more: name === "delivered" ? [Object.assign({}, card, {state: "delivered"})] : []})))],
      ["epic", ui.epic({key: "gallery:epic", open: opened("gallery:epic"), title: "Lending", id: sample.epic, metric: "BookLent", tone: ui.state("running", "running"), count: "2/5",
        strip: ["approved", "running", "delivered", "delivered", "superseded"], stripTitle: "2 of 5 delivered", body: () => ui.intro("The epic's goal.")})],
      ["stepper · course", ui.course({id: sample.story, title: sample.title, state: "running", word: "build · round 2", right: ui.btn("follow", {small: true}),
        steps: [{stage: "plan", state: "done"}, {stage: "test", state: "done"}, {stage: "build", state: "now"}, {stage: "tidy", state: ""}, {stage: "judge", state: "stopped"}],
        doing: "writing the adapter"})],
      ["queue", ui.queue(ui.ticket({kind: "release", target: sample.story, word: "queued", state: "queued"}))],
      ["record · options", ui.record({about: "question · q-1 · plan", text: "Which store holds the loans?",
        body: ui.options([{advised: true, pick: ui.btn("a", {primary: true}), text: "the existing one"}, {pick: ui.btn("b"), text: "a new one"}])})
        + ui.record({accept: true, about: "acceptance · a-1", text: "Look at the lending page.", body: ui.actions(ui.btn("accept", {primary: true}))})],
      ["tiles", ui.tiles([1, 2, 3, 4, 5].map(n => ui.tile(`${n}`, `figure ${n}`)).join(""), {many: true})],
      ["days", ui.days([{day: "2026-10-15", rows: [{at: "10:12", story: sample.story, title: sample.title, epic: sample.epic, event: "BookLent", seconds: "14 min", cost: "$3.10"}]}])],
      ["domain · kernel", ui.domain(ui.domainNode("Domain model", "") + ui.facts([{kind: "aggregate", terms: [{name: "Loan"}]}])) + ui.kernel([{kind: "values", terms: [{name: "Money", shared: true}]}])],
      ["proposals", ui.proposals([{goal: "one goal", id: "p-1", epic: "lending"}, {goal: "another goal", id: "p-2", actions: ui.btn("make it an epic")}])],
      ["rule-group · ways · part · branches", ui.branches(ui.part("if the gate passes", ui.hint("→ on to <b>test</b>", {block: true, html: true}), {branch: true, level: 4}), ui.part("if a check refuses", ui.ruleGroup("its checks", [ui.accordion({key: "gallery:rule", variant: "row", open: false, head: "The tests are red", meta: ui.ruleId("GATE-TESTS", "gate", "fail")})])
        + ui.ways("back to an earlier stage", [{source: "build", target: "plan", key: "build>plan>back", rules: "a plan gap"}]), {branch: true, level: 4}))],
      ["flow", ui.flow(`<svg viewBox="0 0 880 60" role="img" aria-label="a drawing the factory gives"><text x="10" y="36">the factory draws the flow</text></svg>`)],
      ["table", ui.table([{label: "story"}, {label: "state"}, {label: "tokens", num: true}, {act: true}], [[ui.story(sample.story, sample.title), "ready", "1.2 M", ui.btn("run it", {small: true})]])],
      ["terminal", ui.terminal()],
      ["curve", ui.curve(curve)],
      ["curve-tip", ui.curveTip(curve[2], [["cost so far", "$15.00"], ["this one", "$6.00"]])]]},
    {level: "templates", items: [
      ["page-head", ui.pageHead("Now", "Where it stands", "The lede of a tab.")],
      ["drawer-frame", ui.drawerFrame(ui.btn("close"), ui.pageHead(sample.epic, sample.title, ""), ui.intro("The story's sections."))],
      ["gallery", ui.hint("this page", {block: true})]]}]);
}
"""
