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
    {ended: true, action: ui.btn("start the backlog", {icon: "play", primary: true, plain: true, attrs: {"data-call": "up"}})}) : "";
}

// --- now: where it stands --------------------------------------------------------------------------------------------
// The cycle as four columns, each as the factory says it: its count, one line, the one item that matters most there and
// the one action at its foot. Then the last deliveries and, beside them, the wish that fills the backlog.
function column(c) {
  const delivered = c.column === "delivered", items = [];
  if (c.last_text) items.push(`last ${esc(when(c.last_text))}`);
  if (c.title) items.push((c.story ? ui.story(c.story, c.title, {ink: true}) : esc(c.title)) + (c.sub ? ui.id(c.sub, {block: true}) : ""));
  const press = !c.action ? "" : c.action.call ? ui.btn(c.action.label, {primary: true, plain: true, attrs: {"data-call": c.action.call}}) : act(c.action);
  const all = delivered ? ui.link("all →", {to: true, attrs: {"data-tab": "delivered"}}) : "";
  return ui.column({name: c.column, count: c.count, of: delivered ? c.total : null, line: c.line, hot: c.hot, items,
    meter: delivered ? c.percent : null, meterLabel: delivered ? `${c.count} of ${c.total} stories delivered, ${c.percent} percent` : "",
    actions: press + all});
}
function now(st) {
  const rows = Object.fromEntries((st.rows || []).map(r => [r.story, r]));
  const recent = (st.delivered_order || []).slice(0, 6).map(id => rows[id]).filter(Boolean).map(r => ({mark: "done",
    what: ui.story(r.story, r.title) + ui.id(r.epic, {block: true}), aside: `${esc(when(r.delivered_text))}<br>${esc(r.cost_text || "")}`}));
  const sums = [st.cost_text, st.seconds_text].filter(Boolean).join(" · ");
  const findings = (st.findings || []).length;
  // the cycle across the width; beneath it what was delivered, and beside that what fills the backlog (WP-183)
  return ui.board((st.now || []).map(column))
    + ui.split({
        main: (recent.length ? ui.card("Last delivered", sums ? `${esc(sums)} in all` : "", ui.list(recent) + ui.link("delivered →", {to: true, attrs: {"data-tab": "delivered"}})) : "")
          + (findings ? ui.quietLine(`Beside that: ${ui.link(`${findings} open finding${findings > 1 ? "s" : ""} beside their stories →`, {quiet: true, attrs: {"data-tab": "backlog"}})}`) : ""),
        side: wishPart(st)});
}

// --- the wish: one part wherever it stands, the field and the trail of what became of each wish ------------------------
function wishPart(st) {
  const items = ((S.requests || {}).wishes || []).map(w => {
    const since = w.state === "running" && w.started ? ` — ${took(Math.max(0, Math.round((Date.now() - Date.parse(w.started)) / 1000)))}` : "";
    const ops = (w.operations || []).map(op => ui.btn(op.label, {size: "s", danger: op.name === "drop",
      title: op.name === "hide" ? "hide it here; the draft stays in the backlog" : "",
      attrs: {"data-call": op.name, "data-kind": "request", "data-id": w.id, "aria-label": op.name === "hide" ? "hide" : null}})).join("");
    const answer = w.state === "waiting" ? ui.btn("answer", {size: "s", primary: true, attrs: {"data-tab": w.place}}) : "";
    const open = (w.made || []).slice(0, 1).map(m => ui.btn("open", {size: "s", attrs: {"data-story": m.id}})).join("");
    const glyph = {ok: "✓ ", ask: "? ", bad: "✗ "}[w.tone] || "";
    const files = w.files ? ` · ${w.files} file${w.files === 1 ? "" : "s"}` : "";
    return {words: w.words, tone: w.tone, text: glyph + w.text + since + files, by: w.by, actions: answer + acts(w.actions, "s", {size: "s"}) + open + ops};
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
  return v.sections.length ? ui.document(v.sections.map(sec => `<h3>${esc(sec.heading)}</h3>${sec.text ? ui.prose(sec.text) : ui.empty("empty")}`).join(""), {compact: true})
    : ui.empty(`${v.path} is missing.`);
}

function describe(st) {
  if (S.part) return partReader(st, S.part);
  // the parts as a short list beside the domain; one opens as a document of its own (WP-183)
  const parts = (st.description || []).map(p => ({mark: p.mark, press: {label: p.part, attrs: {"data-part": p.part}},
    what: ui.id(p.path, {block: true})
      + (p.present ? ui.hint((p.sections || []).join(" · "), {prose: true}) : ui.flag("missing", "gone"))
      + ((p.missing || []).length ? ` ${ui.flag("missing: " + p.missing.join(", "), "changes")}` : "")
      + ((p.empty || []).length ? ` ${ui.flag("empty: " + p.empty.join(", "), "changes")}` : "")}));
  return ui.split({main: domainCard(), side:
    ui.card("The parts", "written by you, through the description — open one to read it", ui.list(parts))
    + ui.card("Change the description", "", ui.intro(`In your words — <code>&lt;part&gt;: &lt;change&gt;</code> where it is one part. Where it needs a decision of yours, it asks here.`, {html: true})
      + act((st.entries || {}).describe))
    + ((S.decisions || {}).records || []).filter(r => (r.actions || []).length && r.place === "describe").map(recordCard).join("")});
}
// a part read as a document: its sections beside the text; a section changes in the person's words alone — the press
// only opens the field, the field's own button writes the request (WP-183)
// written as the description skill takes a change to one section: `<file> — <section>: <change>`
const sectionChange = (base, part, file, heading) => Object.assign({}, base, {text: `what “${heading}” should say instead — in your words`,
  request: Object.assign({}, base.request, {draft: `describe:${part}:${heading}`, lead: `${file} — ${heading}:`})});
function partReader(st, name) {
  const v = S.partText[name];
  if (!v || v.loading) {
    if (!v) { S.partText[name] = {loading: true}; loadPart(name); }
    return ui.empty(`Reading ${name}…`);
  }
  if (v.error) return ui.error(v.error, {block: true});
  if (!v.sections.length) return ui.empty(`${v.path} is missing.`);
  const base = (st.entries || {}).describe, file = v.path.split("/").pop();
  // the margin beside the text carries the press; the field opens beneath the section's words, its cancel beside its button
  const sections = v.sections.map((sec, i) => {
    const key = `${name}:${sec.heading}`, changing = !!base && S.changing === key;
    const field = changing ? ui.caption(`${name} · ${sec.heading}`)
      + act(sectionChange(base, name, file, sec.heading), "m", ui.btn("cancel", {attrs: {"data-change": ""}})) : "";
    return {id: `section-${i}`, heading: sec.heading, body: (sec.text ? ui.prose(sec.text) : ui.empty("empty")) + field,
      aside: base && !changing ? ui.link("change this section", {quiet: true, compact: true, attrs: {"data-change": key}}) : ""};
  });
  return ui.reader({label: `${name} — its sections`, head: ui.caption("sections"), sections});
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
    + ui.hint(`${item.tests.length ? "test: " + item.tests.map(t => esc(t) + (h && h.missing.includes(t) ? " " + ui.em("— not in the code") : "")).join(", ") : "no test named"} · <code>${esc(item.key)}</code>
      · ${h && h.delivered_by ? `delivered by ${esc(h.delivered_by.story)}${h.delivered_by.how ? " (" + esc(h.delivered_by.how) + ")" : ""}` : "no delivered story brought it"}`, {block: true, html: true})
    + ui.actions(act(item.fix, "s")) + ui.actions(act(item.change, "s"))});
}

// a context as the designed domain and the spec hold it: an ink head with its numbers, then its course — 1 its model
// as a profile by kind, 2 its features as groups, each rule a line above its criteria
const KIND_LABEL = {"aggregate": "aggregate", "entity": "entities", "identity": "ids", "value object": "values", "domain event": "events",
  "domain service": "services", "domain gateway": "gateways", "specification": "specifications", "factory": "factories",
  "read model": "read models", "failure": "failures", "concept": "concepts", "other": "other"};
const subdomainKind = sd => sd.toLowerCase();   // the spec says Core, Supporting or Generic — the domain classifies
// a model as its kinds, each a row of terms; a shared term in the kernel's colour, saying who uses it
const modelFacts = model => model.map(g => ({kind: KIND_LABEL[g.kind] || g.kind, terms: g.terms.map(t => ({name: t.name, shared: t.shared,
  minor: !t.shared && ["concept", "other"].includes(g.kind),
  title: [t.meaning, t.shared ? "shared kernel" : "", (t.used_by || []).length ? "used by " + t.used_by.join(", ") : ""].filter(Boolean).join(" — ")}))}));

function specContext(c) {
  const facts = modelFacts(c.model);
  const features = c.features.map(f => {
    const key = `feature:${c.context}:${f.feature}`, total = f.rules.reduce((n, r) => n + r.criteria.length, 0);
    const pending = f.rules.reduce((n, r) => n + r.criteria.filter(x => x.changed_by.length).length, 0);
    return ui.accordion({key, variant: "group", open: opened(key), head: `${ui.em(f.feature || "the context itself")}`,
      meta: `${total}${pending ? ` · ${pending} changed` : ""}`,
      body: () => f.rules.map(r => ui.ruleBlock(r.rule ? inline(r.rule) : "", r.criteria.map(scenario))).join("") + ui.actions(act(f.add, "s"), {indent: true})});
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
      `${ui.em(c.context)} ${c.subdomain ? ui.pill(c.subdomain, subdomainKind(c.subdomain), {line: true}) : ""}`, esc(c.purpose),
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
// a discovery stands as the backlog's epics do: the topics on the width, a new one beside them; one opened is a place of
// its own beneath discover — what it asks first, then its report, and beside it what it proposes (WP-183)
function discover(st) {
  const d = S.discover || {}, topics = d.topics || [], ways = d.working || [];
  // a discovery on its way belongs to its topic — continued — or stands as a topic of its own until its report is written
  const wayOf = topic => ways.find(w => w.topic && w.topic === topic);
  const all = [...ways.filter(w => !topics.some(t => t.topic === w.topic))
      .map(w => ({key: w.id, title: w.words || "a new discovery", sub: "a new discovery — no report yet", way: w})),
    ...topics.map(t => ({key: t.topic, title: t.title, topic: t, way: wayOf(t.topic),
      sub: `${t.proposals.length} proposed · ${t.proposals.filter(p => p.epic).length} epics made`}))];
  const picked = all.find(x => x.key === S.topicPick);
  if (S.topicPick && picked) return discoveryPlace(picked);
  const waits = x => x.way && x.way.state === "waiting";
  const items = [...all.filter(waits), ...all.filter(x => !waits(x))].map(x => ({
    mark: waits(x) ? "question" : x.way ? "running" : "", press: {label: x.title, attrs: {"data-pick-topic": x.key}},
    what: (x.topic ? ui.id(x.topic.topic, {block: true}) : "") + ui.hint((waits(x) ? "asks you · " : x.way ? "on its way · " : "") + x.sub, {prose: true})}));
  return ui.split({
    main: ui.card("Discoveries", "each topic with its report — open one to read it, act on what it proposes, or continue it",
      items.length ? ui.list(items) : ui.empty(`No discovery yet — it goes to ${d.store || ""}.`)),
    side: ui.card("A new discovery", "a problem worth solving, or what should exist — the report and the epics it proposes", act((st.entries || {}).discover))});
}
function discoveryPlace(x) {
  const t = x.topic, w = x.way, asks = w ? (w.state === "waiting" ? "asks you" : w.state) : "reported";
  const back = ui.actions(ui.btn("← discover", {attrs: {"data-pick-topic": ""}}));
  const head = ui.pageHead("Discovery", x.title, "")
    + ui.figures([["state", esc(asks)], t ? ["topic", esc(t.topic)] : null, t ? ["report", esc(t.report)] : null]);
  // on its way: what it asks back first, answered here — the same record Decide lists —, then its output when followed
  const records = ((S.decisions || {}).records || []).filter(rec => (rec.actions || []).length);
  const rec = w && records.find(r => w.record && r.path === w.record);
  const followed = w && S.follow && S.follow.kind === "request" && S.follow.id === w.id;
  // its output is pressed beneath its head, as a story's is
  const buttons = w ? ui.actions(ui.btn("output", {attrs: {"data-call": "follow", "data-kind": "request", "data-id": w.id}})) : "";
  const way = !w ? "" : (followed ? ui.card("Output", `<span id="follow-title" data-own></span>`, ui.terminal()) : "")
    + (rec ? recordCard(rec, {about: `${t ? t.topic : "this discovery"} asks back — before it writes its report`}) : "");
  if (!t) return back + head + buttons + way + ui.card("", "", ui.empty(`It works on “${w.words}” — its report and the epics it proposes appear here once written.`));
  const report = (t.sections || []).filter(sec => !/^proposed /i.test(sec.heading)).map(sec => ui.section(sec, 2, t.report)).join("");
  const proposals = t.proposals.map(p => ({goal: p.goal || p.intent || p.id, intent: p.goal && p.intent ? p.intent : "", metric: p.metric,
    contact: p.domain_contact, id: p.id, epic: p.epic, actions: acts(p.actions)}));
  // a change a row of the side column, as a finding is: the part it changes, the change, why — its press small at the end
  const changes = t.description_changes.map(c => ({what: `${ui.em(c.target)}<br>${esc(c.change)}${ui.id(c.why, {block: true})}`,
    aside: acts(c.actions, "m", {primary: false, size: "s"})}));
  return back + head + buttons + ui.split({
    main: way + ui.card("", "", report ? ui.document(report) : ui.empty("The report says nothing beyond what it proposes.")),
    side: ui.card("Proposed epics", `${t.proposals.length} proposed — each becomes an epic when you make it one`,
        proposals.length ? ui.proposals(proposals) : ui.empty("No proposed work."))
      + (changes.length ? ui.card("Changes to the description", "applied one by one, through the description",
          ui.list(changes)) : "")
      + ui.card("Continue this discovery", "a question, a document, a wish — the report grows", acts(t.actions, "s"))});
}

// a finding as a row of a side column, as decide's are: its severity and words, where it is beneath — whose it is and
// the file —, its press small at the row's end; a table of three columns does not fit four of twelve
const shortWhere = where => { const parts = String(where || "").replace(/`/g, "").split("/"); return parts.length > 2 ? `…/${parts.slice(-2).join("/")}` : parts.join("/"); };
const findingRow = (f, whose) => ({what: `${ui.state(f.severity, f.severity)} ${esc(f.plain || f.defect)}`
    + (whose ? ui.id(whose, {block: true}) : "") + (f.where ? ui.id(shortWhere(f.where), {block: true}) : ""),
  aside: act(f.action, "m", "", {primary: false, size: "s"})});

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
  if (S.detail) return storyPage(st, S.detail);
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
  const findings = (st.findings || []).map(f => findingRow(f, f.row));
  // the epics are the view, on 8 of the 12 columns so an epic's lanes stand side by side; the wish and the findings
  // beside them (WP-183)
  const epicsCard = epics || filter !== "all" ? ui.card("Epics", filter === "all" ? "newest first — open one to see its stories by where they stand" : filter === "drafts" ? "the drafts, waiting for your release" : "what is not delivered yet",
        filters + ui.legend(STRIP_KEY) + (epics || ui.empty("Nothing here.")))
      : ui.card("", "", ui.empty("The backlog is empty."));
  const findingsCard = findings.length ? ui.accordion({key: "findings", variant: "card", level: 2, open: opened("findings"),
        head: `Findings ${ui.hint(`${findings.length} the judge kept open — each to the backlog or done`)}`,
        body: () => ui.list(findings)}) : "";
  return ui.split({main: epicsCard, side: wishPart(st) + findingsCard});
}

// --- 3 run ---------------------------------------------------------------------------------------------------------
function run(st) {
  if (S.detail) return storyPage(st, S.detail);
  // the run page's output is the factory's own log while nothing else is followed here, until it is stopped
  if (!S.follow && !S.factoryLogOff) setTimeout(() => { if (!S.follow && S.tab === "run" && !S.detail) follow("log", "factory"); });
  const w = st.worker, reqs = (S.requests || {}).requests || [];
  // the backlog is the one thing switched here: a person's requests are worked while this page is open (WP-177)
  const factory = (backlogOn(st) ? (w.stopping ? ui.intro("Stopping after the running stage.")
      : ui.actions(ui.btn("stop after the running story", {icon: "stop", attrs: {"data-call": "down"}})
        + ui.btn("stop now", {icon: "stop", danger: true, attrs: {"data-call": "down", "data-now": "1"}})))
    : ui.actions(ui.btn("start the backlog", {icon: "play", primary: true, plain: true, attrs: {"data-call": "up"}})))
    + (w ? ui.accordion({key: "worker", variant: "quiet", open: opened("worker"), head: "the worker",
        body: () => ui.kv([["worker", esc(w.owner)], ["since", esc(w.since_text)], w.log ? ["log", `<code>${esc(w.log)}</code>`] : null])}) : "");
  const ops = r => (r.operations || []).map(op => ui.btn(op.label, {size: "s", danger: op.name === "drop",
    attrs: {"data-call": op.name, "data-kind": "request", "data-id": r.id}})).join("");
  const tickets = reqs.map(r => ui.ticket({kind: r.kind, target: r.target, word: r.state, state: r.state, id: `${r.id} · ${r.by}`,
    error: r.error, note: r.record ? `asks: <code>${esc(r.record)}</code> — answer it under Decide` : "", actions: ops(r)})).join("");
  const titles = Object.fromEntries((st.rows || []).map(r => [r.story, r.title]));
  // a story in flight as its course: running, or stopped where it goes on from, with why and what goes on
  const follows = id => ui.btn("follow", {size: "s", attrs: {"data-call": "follow", "data-kind": "story", "data-id": id}});
  const live = (st.running || []).map(r => ui.course({id: r.story, title: titles[r.story], state: r.interrupted ? "interrupted" : "running",
      word: r.interrupted ? "interrupted" : `${r.part || r.stage}${r.round > 1 ? ` · round ${r.round}` : ""}`,
      steps: r.course, doing: r.activity, right: ui.hint(r.ago || "") + follows(r.story)})).join("")
    + (st.waiting || []).filter(x => x.mark === "stopped" && !(st.running || []).some(r => r.story === x.story))
      .map(x => ui.course({id: x.story, title: titles[x.story], state: "stopped", word: "stopped", steps: x.course,
        doing: (x.action && x.action.text) || x.what, right: act(x.action, "", "", {size: "s"}) + follows(x.story)})).join("");
  const readyRows = (st.rows || []).filter(r => st.queue && st.queue.ready.includes(r.story)), readyMarked = marked(readyRows);
  // what runs, its output and what comes next on the width; beside them the backlog's switch, the wish and the requests (WP-183)
  return ui.split({
    main: ui.card("Running", "a story's course through its stages — running, or stopped where it goes on", live || ui.empty("No stage runs."))
      + ui.card("Output", `<span id="follow-title" data-own></span>`, ui.terminal())
      + (readyRows.length ? ui.card("Next in line", "ready, in the order the factory takes them", ui.table(storyCols(readyMarked), readyRows.map(r => storyRow(r, readyMarked)))) : ""),
    side: ui.card("The backlog", backlogOn(st) ? "on — the released stories one after the other"
        : `off — ${(st.queue || {ready: []}).ready.length} released stories would run`, factory)
      + wishPart(st)
      + ui.card("Requests", "everything asked of the factory, oldest first", tickets ? ui.queue(tickets) : ui.empty("No request waits."))});
}

function stopFollowing() {
  if (S.followSource) { S.followSource.close(); S.followSource = null; }
  S.follow = null; S.followOn = ""; S.followLines = [];
}
function follow(kind, id) {
  if (S.followSource) { S.followSource.close(); S.followSource = null; }
  S.follow = kind ? {kind, id} : null;
  S.followLines = [];
  // a story that runs is followed as it writes; one that does not shows what its last stage left, once — or says that
  // nothing is kept here: a stage's output stays beside the story's evidence, outside git, in the checkout that ran it
  const live = kind !== "story" || ((S.status || {}).running || []).some(r => r.story === id);
  if (kind && !live) {
    api(`/api/view/output?id=${encodeURIComponent(id)}`).then(o => {
      if (!S.follow || S.follow.id !== id) return;
      const lines = (o && o.lines) || [];
      S.followLines = lines.length ? [`— the last output kept: ${o.stage || "a stage"}${o.file ? ` (${o.file})` : ""} —`, ...lines]
        : [`No output is kept for this story here — a stage's output stays beside its evidence in the checkout that ran it (.dca-factory/evidence/${id}/), outside git, so a clone has none.`];
      paintFollow();
    }).catch(e => { S.followLines = [e.message]; paintFollow(); });
  }
  if (kind && live) {
    const source = new EventSource(`/api/follow?${kind}=${encodeURIComponent(id)}&t=${encodeURIComponent(TOKEN)}`);
    source.onmessage = event => {
      try { S.followLines.push(JSON.parse(event.data)); } catch (e) { S.followLines.push(event.data); }
      if (S.followLines.length > 1500) S.followLines.splice(0, S.followLines.length - 1500);
      paintFollow();
    };
    source.addEventListener("end", () => { S.followLines.push("— the output ended —"); paintFollow(); source.close(); });
    S.followSource = source;
  }
  // a story's output shows on the story's own place, beneath its pipeline; a discovery's in its own detail on discover;
  // any other output is a card of the run page
  const atDiscovery = S.tab === "discover" && kind === "request" && ((S.discover || {}).working || []).some(w => w.id === id);
  const here = (onStoryPlace() && kind === "story" && S.detail === id) || atDiscovery;
  S.followOn = !kind ? "" : atDiscovery ? "discover" : here ? "story" : "run";
  if (S.drawer) CALLS.close();
  if (here || !kind) render(); else if (S.tab !== "run") show("run"); else paintFollow();
  if (kind && kind !== "log") requestAnimationFrame(() => { const out = $("follow-out"); if (out) out.closest(".card").scrollIntoView({behavior: "smooth", block: "start"}); });
}

function paintFollow() {
  const out = $("follow-out");
  if (!out) return;
  $("follow-title").textContent = !S.follow ? "follow a running stage or request"
    : S.follow.kind === "log" ? "the factory's log — what the worker does" : `${S.follow.kind} ${S.follow.id}`;
  $("follow-acts").innerHTML = S.follow ? ui.btn("stop following", {attrs: {"data-call": "unfollow"}}) : "";
  const atEnd = out.scrollTop + out.clientHeight >= out.scrollHeight - 20;   // at the end it follows the newest line
  const text = S.followLines.join("\n") || (S.follow ? "waiting for output…" : "");
  if (out.textContent !== text) out.textContent = text;
  if (atEnd) out.scrollTop = out.scrollHeight;
}

// --- 4 decide ------------------------------------------------------------------------------------------------------
// `about` names who asks where the place says it better than the record's kind and id
function recordCard(r, o = {}) {
  const offered = (r.actions || []).filter(a => !a.waits_on), accept = r.kind === "acceptance";
  const options = offered.filter(a => a.request.open !== "words" && !accept);
  const words = offered.filter(a => a.request.open === "words");
  // what to look at is the acceptance itself and stands open; a question's full text folds under its answers — unless
  // there are none to pick, then it is what the words answer and stands open above them
  // and a question with pictures — mockups to choose between — stands open above its options too (WP-184)
  const pictured = (r.sections || []).some(one => /!\[[^\]]*\]\(/.test(one.text || ""));
  const key = `more:${r.id}`, first = accept || !options.length || pictured;
  const full = (r.sections || []).length ? ui.accordion({key, variant: "quiet", open: opened(key, first),
    head: accept ? "what to look at" : "the question in full", body: () => ui.document(r.sections.map(one => ui.section(one, 3, r.path)).join(""), {compact: true})}) : "";
  const body = (first ? full : "")
    + (accept ? ui.actions(acts(offered.filter(a => a.request.open !== "words")))
      : options.length ? ui.options(options.map(a => ({advised: a.primary, pick: act(a),
          text: inline(a.text) + (a.note ? ` ${ui.hint("— " + a.note)}` : "")}))) : "")
    + words.map(a => ui.part(accept ? "or correct it" : options.length ? "or in your words" : "your answer", act(a))).join("")
    + (first ? "" : full)
    + ui.id(`${r.story ? `${ui.story(r.story, r.story)} · ` : ""}${esc(r.path)}`, {block: true, html: true});
  return ui.record({accept, about: o.about || `${recordKind(r)} · ${r.id}${r.story ? ` · ${r.stage}` : ""}`, text: inline(r.text), body});
}

// a record's kind in words: an acceptance, a question, or a lesson — what repeats across the stories (WP-185)
const recordKind = r => r.kind === "acceptance" ? "acceptance" : r.kind === "lesson" ? "lesson" : "question";
const plain = text => String(text || "").replace(/[`*_]/g, "");
function decide(st) {
  const records = ((S.decisions || {}).records || []).filter(r => (r.actions || []).length && (r.place || "decide") === "decide");
  // a waiting story whose record is open stands above as that record; the others in two kinds of their own: a draft the
  // backlog waits to release, and a run that stopped — a stopped story is not run again by itself, it waits for a look
  const waiting = (st.waiting || []).filter(w => !w.record);
  // each as a row that opens the story, why it waits beneath its title, its one press small at the row's end
  const titles = Object.fromEntries((st.rows || []).map(r => [r.story, r.title]));
  // what to do stands at the row's end as a press; without one, its words go under the title, where a sentence fits
  const item = w => {
    const press = act(w.action, "m", "", {primary: false, size: "s"});
    const todo = press ? "" : (w.action.text || w.action.skill || w.action.shell || "");
    return {mark: w.mark === "stopped" ? "stopped" : "", press: {label: titles[w.story] || w.story, attrs: {"data-story": w.story}},
      what: (titles[w.story] ? ui.id(w.story, {block: true}) : "") + ui.hint(w.what, {prose: true}) + (todo ? " — " + ui.hint(todo) : ""),
      aside: press};
  };
  const drafts = waiting.filter(w => w.draft || ((w.action || {}).request || {}).kind === "release"), stopped = waiting.filter(w => !w.draft && w.mark === "stopped");
  const rest = waiting.filter(w => !drafts.includes(w) && !stopped.includes(w));
  const group = (title, sub, list) => list.length ? ui.card(title, sub, ui.list(list.map(item))) : "";
  const also = group("Drafts to release", "the backlog runs a story once it is released", drafts)
    + group("Stopped runs", "a stopped story is not run again by itself — read why, correct it or run it again", stopped)
    + group("Also waiting for you", "", rest);
  if (!records.length && !also) return ui.card("", "", ui.empty("Nothing waits for you."));
  // on a wide window the records stand as a list, the one picked open beside it — the first until another is (WP-183)
  if (wide() && records.length) {
    const on = records.find(r => r.id === S.record) || records[0];
    const items = records.map(r => ({mark: r.kind === "acceptance" ? "look" : "question", on: r.id === on.id,
      press: {label: plain(r.text), attrs: {"data-record": r.id}},
      what: ui.id(`${recordKind(r)} · ${r.id}${r.story ? ` · ${r.story} · ${r.stage}` : ""}`, {block: true})}));
    const lessons = records.filter(r => r.kind === "lesson").length;
    return ui.master({label: "the record", bare: true, detail: recordCard(on),
      list: ui.card(lessons ? "Questions, results and lessons" : "Questions and results",
        `${records.length} to answer or to accept — open one` + (lessons ? `; ${lessons} lesson${lessons === 1 ? "" : "s"} — where a repeated correction belongs, holding no story back` : ""), ui.list(items)) + also});
  }
  return records.length ? ui.split({main: records.map(recordCard).join(""), side: also}) : also;
}

// --- 5 delivered ---------------------------------------------------------------------------------------------------
function curveCard(st) {
  const curve = st.delivered_curve || [];
  if (curve.length < 2) return "";
  S.curve = curve;
  const last = curve[curve.length - 1], unpriced = curve.length - last.priced_total;
  return ui.curve(curve, {w: S.curveW}) + (unpriced ? ui.hint(`${unpriced} deliver${unpriced === 1 ? "y carries" : "ies carry"} no price and add nothing to the cost.`, {block: true}) : "");
}
// quality: the signals the factory counts per story, summed — shown as counted, never rated
const sum = o => Object.values(o || {}).reduce((n, v) => n + v, 0);
const domainWords = o => Object.entries(o || {}).sort((a, b) => b[1] - a[1]).map(([c, n]) => `${n} ${c.replace(/^domain-/, "")}`).join(" · ");
function qualityCard(q, lessons) {
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
  // the step from these signals to a place for their correction: what repeats becomes a lesson in decide (WP-185)
  const l = lessons || {};
  const lessonTile = ui.tile(`${l.waiting || 0}`, `lessons for the ${l.role || "loop keeper"}`,
    {said: `${l.answered || 0} answered — what these figures repeat across stories, counted; answered in decide by ${l.who || ""}`, bad: !!l.waiting,
     title: "a question of the same tag, a finding of the same rule, a correction of the same code, an assumption answered the same way, a term flagged — in several stories"});
  return ui.card("Quality", "what the stages asked, what the judge confirmed, what a person corrected — counted over every story, never rated",
    ui.tiles(tiles + ruleTile + lessonTile, {many: true})
    + (found.length ? ui.part("Findings the judge confirmed, by perspective", ui.bars(found.map(([name, n]) => [name, n, Math.round(100 * n / most)]))) : ""));
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
    days[days.length - 1].rows.push({at: (r.delivered_text || "").slice(11, 16), story: r.story, title: r.title, epic: r.epic,
      event: events[r.epic], seconds: r.seconds_text, tokens: r.tokens_text, cost: r.cost_text});
  }
  // the deliveries by day on the width; beside them the sums with their curve, above the quality they came with (WP-183)
  const byDay = ui.card("By day", "each delivery with the outcome event its epic is measured by", days.length ? ui.days(days) : ui.empty("Nothing delivered yet."));
  const sums = ui.card("Delivered", "what is delivered, and what it cost as it summed up", ui.tiles(tiles) + curveCard(st));
  return ui.split({main: byDay, side: sums + qualityCard(st.signals, st.lessons), sideFirst: true});
}

// --- 6 the rules: the factory's rulebook — a stage read, the checks against the stages, a story's run ----------------
// Three renderings of one read model (`factory.sh rules --format json`): the track of the picked kind with its ways back
// (derived by the factory from the rules), the stage's rules, and what the project's journals say. Where the page
// stands — the view, the kind, the stage, the story — is in its address: `#rules/<view>/<kind>/<stage|all>[/<story>]`.
// The read is the story's own: until it is in, the view says it reads instead of showing the one before, and an
// answer for a story no longer picked is dropped. A story read before shows at once and is read again behind it.
const RULE_READS = new Map();
async function loadRules() {
  const want = S.ruleStory || "";
  if (S.rules && S.rulesFor === want) return;
  S.rulesFor = want;
  if (RULE_READS.has(want)) [S.rules, S.rulesOf] = [RULE_READS.get(want), want];
  try {
    const read = await api("/api/view/rules" + (want ? `?id=${encodeURIComponent(want)}` : ""));
    RULE_READS.set(want, read);
    if (S.rulesFor !== want) return;
    [S.rules, S.rulesOf] = [read, want];
    render();
  } catch (e) { banner(`rules: ${e.message}`); }
}
const RULE_VIEWS = [["stage", "stage"], ["matrix", "checks × stages"], ["run", "run"]];
// a rule read as sentences: its title, why, when, and each outcome after its keyword, where it sends the story
const SAYS = {pass: "Passes when", fail: "Fails when", skip: "Skips when", note: "Notes when", wait: "Waits when", ask: "Asks when"};
const sentence = t => { const s = String(t || "").trim(); return s ? s[0].toUpperCase() + s.slice(1) + (/[.!?)]$/.test(s) ? "" : ".") : ""; };
const clause = t => { const s = String(t || "").trim(); return s + (/[.!?)]$/.test(s) ? "" : "."); };
const going = goes => (goes || []).length ? `→ ${goes.map(g => g === "stop" ? "stop" : g === "again" ? "once more" : "back to " + g).join(" or ")}` : "";
const PARTS = {check: "check — a question the gate asks of a stage's work; it passes or refuses",
  decision: "decision — where the runner sends the story next", pass: "pass — what a passing gate does",
  instruction: "told — what a stage reads before it works; no gate asks it directly"};
const times = n => `${n}×`;
// a told rule's name: its first sentence
const firstSentence = text => { const plainText = String(text || "").replace(/^\s*\d+[A-Za-z]?\.\s*/, "").replace(/\*\*/g, "").replace(/\s*\n\s*/g, " ");
  const m = plainText.match(/^(.{20,170}?[.:;])(\s|$)/); return m ? m[1] : plainText.slice(0, 140) + (plainText.length > 140 ? "…" : ""); };
const ruleTitle = r => r.title ? sentence(r.title).replace(/\.$/, "") : r.text ? firstSentence(r.text) : sentence(r.why || r.when || r.id);

// what the view reads: the kind's flow and track, the stage picked, the story's run where one is picked
function rulesContext(st) {
  const v = S.rules, rules = Object.fromEntries((v.rules || []).map(r => [r.id, r])), kinds = Object.keys(v.flow || {});
  const story = v.story && v.story.id === S.ruleStory ? v.story : null, run = story ? story.run : null;
  // a story picked is seen as the kind it ran as, whatever the address said; the address follows
  if (run && kinds.includes(run.kind) && S.ruleKind !== run.kind) {
    S.ruleKind = run.kind;
    if (S.tab === "rules") history.replaceState(null, "", rulesHash());
  }
  const kind = kinds.includes(S.ruleKind) ? S.ruleKind : kinds[0];
  const flow = (v.flow || {})[kind] || {steps: [], every_gate: [], graph: {anywhere: []}, track: {tiles: [], ways: []}};
  const track = flow.track || {tiles: [], ways: []}, route = track.tiles.map(t => t.stage);
  const stage = S.ruleStage === null ? (route.includes("build") ? "build" : route[0] || "") : route.includes(S.ruleStage) ? S.ruleStage : "";
  const stepOf = name => flow.steps.find(s => s.stage === name) || {gate: "none", gate_before: [], told: [], gate_after: [], passed: [], decided: []};
  const refusals = (v.refusals || {}).rules || {};
  return {v, st, rules, kinds, kind, flow, track, route, stage, stepOf, story, run, refusals};
}
const checksOf = step => [...(step.gate_before || []), ...(step.gate_after || [])];
const nextOf = (c, stage) => { const i = c.route.indexOf(stage); return i >= 0 && i < c.route.length - 1 ? c.route[i + 1] : "delivered"; };
// how often a rule refused: at one stage of this project, or — a story picked — that story between the stages
function refusedAt(c, id, stage) {
  if (c.run) {
    const at = c.run.stages[stage], r = c.rules[id] || {};
    return at ? (r.reports || []).reduce((n, name) => n + (at.checks[name] || 0), 0) : 0;
  }
  return ((c.refusals[id] || {}).stages || {})[stage] || 0;
}
// `bare`: in a narrow column the id stands in the row's title, not beside it
function ruleRow(c, id, stage, bare = false) {
  const r = c.rules[id] || {id}, n = stage ? refusedAt(c, id, stage) : 0;
  const aside = n ? ui.flag(`✗ ${n}`, "fail", {title: c.run ? `refused ${c.story.id} ${times(n)} here, between the stages` : `refused ${times(n)} here in this project`}) : "";
  return {id, title: ruleTitle(r), aside: aside || (bare ? "" : undefined), state: c.run && n ? "fail" : ""};
}
// a list of rules, the first few shown and the rest behind a fold
function ruleList(c, key, ids, stage, first = 99, bare = false) {
  const rows = (ids || []).map(id => ruleRow(c, id, stage, bare));
  if (rows.length <= first + 1) return ui.ruleRows(rows);
  return ui.ruleRows(rows.slice(0, first)) + ui.accordion({key: `rules:${key}`, variant: "quiet", open: opened(`rules:${key}`),
    head: `${rows.length - first} more`, body: () => ui.ruleRows(rows.slice(first))});
}

// the track: a tile per stage of the kind, the delivered end, the ways back — the picked stage's solid, or the ways the
// picked story took; a repeat of a stage is its tile's ↺, a restart its tile's grey note, never a line
function ruleTrack(c) {
  const t = c.track, limit = t.round_limit || 3, ways = [];
  const free = w => w.source === "delivered" ? `${w.reason} · a new pass` : w.reason;
  // on the line only the first reason — the line stays short; every reason stays in its tooltip
  const first = w => { const r = w.reason.split(" · ")[0]; return w.source === "delivered" ? `${r} · a new pass` : r; };
  if (c.run) {
    for (const took of c.run.ways) {
      const w = t.ways.find(x => x.source === took.source && x.target === took.target);
      if (w) ways.push({source: w.source, target: w.target, round: w.cost === "round", solid: true, label: `${first(w)} · ${times(took.times)}`,
        title: `${w.source} → ${w.target} · ${free(w)} (${w.rules.join(", ")}) — ${c.story.id} took it ${times(took.times)}`});
    }
  } else {
    for (const w of t.ways) ways.push({source: w.source, target: w.target, round: w.cost === "round", solid: !!c.stage && w.source === c.stage,
      label: first(w), title: `${w.source} → ${w.target} · ${free(w)} (${w.rules.join(", ")}) — ${w.cost === "round" ? "costs a round" : "costs no round"}`});
  }
  const tiles = t.tiles.map(tile => {
    const step = c.stepOf(tile.stage), told = (step.told || []).length, checks = checksOf(step).length;
    const meta = tile.decides ? `decides · told ${told}` : `${checks} checks · told ${told}`;
    let state = null, notes = [];
    if (c.run) {
      const x = c.run.stages[tile.stage] || {};
      state = !x.reached ? {text: "not reached"} : x.refused ? {text: `✗ refused ${times(x.refused)}`, tone: "fail"}
        : {text: `✓ passed${x.tries ? ` · ${x.tries} ${x.tries === 1 ? "try" : "tries"} inside` : ""}`, tone: "pass"};
      const again = c.run.restarts[tile.stage];
      if (again) notes = [{text: `↩ started again here · ${times(again.times)}`, title: `restarted here — no round${again.reasons.length ? `: ${again.reasons.join(", ")}` : ""}`}];
    } else {
      state = tile.rounds ? {text: `↺ up to ${limit} rounds`, tone: "wait"} : tile.decides ? {text: "↺ sends back · a round", tone: "wait"} : null;
      if (tile.restarts.length) notes = [{text: `↩ again from here when ${tile.restart_when.join(" or ")}`, title: `${tile.restarts.join(" · ")} — no round`}];
    }
    return {stage: tile.stage, picked: tile.stage === c.stage, here: !!c.run && c.run.last === tile.stage, meta, state, notes};
  });
  tiles.push({end: true, stage: "delivered", name: "delivered", note: t.accepted ? "after a person's acceptance" : ""});
  const legend = [["wait", "━ costs a round, as ↺ on a tile"], ["", "━ costs no round"], ["", "↩ started again at that stage — a note, no line"],
    ["", c.run ? `solid: a way back ${c.story.id} took, with how often` : "solid: where the picked stage sends a story back · dashed: the others"]];
  return ui.ruleTrack({tiles, ways, legend});
}
// the ways drawn once the tiles stand; a newly picked tile scrolled into its track's sight where the track scrolls
let trackPicked = "";
function paintTracks() {
  document.querySelectorAll(".rule-track").forEach(drawWays);
  const picked = document.querySelector('.rule-track__tile[aria-pressed="true"]'), key = picked ? `${S.ruleKind}/${picked.dataset.trackStage}` : "";
  if (picked && key !== trackPicked) picked.scrollIntoView({block: "nearest", inline: "nearest"});
  trackPicked = key;
}

// the three groups beneath: at every gate, anywhere in a run, what every stage is told
function ruleGroups(c) {
  const anywhere = [...new Set([...(((c.flow.graph || {}).anywhere) || []).flatMap(e => e.rules.map(r => r.rule)),
    ...(c.v.outside || []).filter(id => (c.rules[id] || {}).part !== "instruction")])];
  const told = (c.v.rules || []).filter(r => r.part === "instruction" && !(r.stages || []).length).map(r => r.id);
  const group = (key, title, sub, ids) => ids.length ? ui.accordion({key: `group:${key}`, variant: "card", level: 2, open: opened(`group:${key}`),
    head: `${esc(title)} ${ui.hint(`${ids.length} rules — ${sub}`)}`, body: () => ruleList(c, `group:${key}`, ids, "")}) : "";
  return ui.ruleFolds([group("every", "At every gate", "what each gate of this kind asks as well", c.flow.every_gate || []),
    group("anywhere", "Anywhere in a run", "what stops a run or waits for a person at any stage", anywhere),
    group("told", "Every stage is told", "what each stage reads whatever it is", told)]);
}

// --- the stage view: the picked stage in three columns — what it is told, what is checked, what comes next
function stageView(c) {
  if (!c.stage) return ruleTrack(c) + ui.hint("Pick a stage to read what it is told, what its gate checks and where it sends a story back — a second click on the picked stage shows every way at once.", {block: true}) + ruleGroups(c);
  const s = c.stage, step = c.stepOf(s), tile = c.track.tiles.find(t => t.stage === s) || {};
  const before = step.gate === "before", checks = checksOf(step);
  const told = ui.card("While it works", `told · ${(step.told || []).length}`, ui.hint(`What the ${s} stage reads before it starts.`, {block: true})
    + ((step.told || []).length ? ruleList(c, `told:${s}`, step.told, "", 8) : ui.empty("Nothing of its own — what every stage is told, below.")));
  const checked = ui.card(before ? "Checked before it starts" : "Checked afterwards", tile.decides ? "decides" : `${checks.length} checks`,
    tile.decides ? ui.hint("No gate: reviewers read the change, and the judge's verdict decides — it passes, sends the story back, or asks a person.", {block: true}) + ruleList(c, `decided:${s}`, step.decided || [], s)
      : ui.hint(`${before ? "Before the stage" : "After the stage"}, a script — not a model — asks each of these; one refusal and the stage is not done.${c.run ? ` The counts are ${c.story.id}'s refusals between the stages.` : " The counts are this project's refusals."}`, {block: true})
        + ruleList(c, `checks:${s}`, checks, s));
  const out = c.track.ways.filter(w => w.source === s);
  const sent = new Set(out.flatMap(w => w.rules));
  const rest = (step.decided || []).filter(id => !sent.has(id));
  const wayRows = out.flatMap(w => w.rules.map(id => ({id, title: `back to ${w.target} — ${w.reason}`, aside: ui.id(id)})));
  const next = ui.card("", "", ui.outcome("pass", `${tile.decides ? "it says yes" : "all pass"} → ${ui.em(nextOf(c, s))}`, ruleList(c, `passed:${s}`, step.passed || [], s)))
    + ui.card("", "", ui.outcome("fail", "one fails → what happens next",
        ui.ruleRows(wayRows) + (rest.length ? ruleList(c, `next:${s}`, rest, s) : !wayRows.length ? ui.hint("the stage tries once more", {block: true}) : "")));
  return ruleTrack(c) + ui.stageRead({told, checked, next}) + ruleGroups(c);
}

// --- checks × stages: a row per check — those at (almost) every gate first, then the others in stage order
function matrixView(c) {
  const gated = c.route.filter(s => c.stepOf(s).gate !== "none"), at = new Map();
  const add = (id, s) => { if (!at.has(id)) at.set(id, new Set()); at.get(id).add(s); };
  c.route.forEach(s => checksOf(c.stepOf(s)).forEach(id => add(id, s)));
  (c.flow.every_gate || []).forEach(id => gated.filter(s => !((c.rules[id] || {}).stages || []).length || c.rules[id].stages.includes(s)).forEach(s => add(id, s)));
  const all = [...at.entries()].map(([id, stages]) => ({id, stages}));
  const many = Math.max(2, gated.length - 1);
  const every = all.filter(x => x.stages.size >= many).sort((a, b) => b.stages.size - a.stages.size);
  const first = x => Math.min(...[...x.stages].map(s => c.route.indexOf(s)));
  const some = all.filter(x => !every.includes(x)).sort((a, b) => first(a) - first(b));
  const row = x => ({id: x.id, title: ruleTitle(c.rules[x.id] || {id: x.id}), name: ((c.rules[x.id] || {}).reports || []).join(" · "),
    cells: Object.fromEntries([...x.stages].map(s => { const n = refusedAt(c, x.id, s);
      return [s, {n, title: n ? `refused ${times(n)} at ${s}${c.run ? ` — ${c.story.id}, between the stages` : " in this project"}` : `the ${s} gate asks it`}]; }))});
  const told = {title: "told before the stage", cells: Object.fromEntries(c.route.map(s => [s, {text: `${(c.stepOf(s).told || []).length}`}]))};
  const matrix = ui.ruleMatrix({stages: c.route.map(s => ({stage: s, picked: s === c.stage})),
    bands: [{label: `at (almost) every gate · ${every.length}`, rows: every.map(row)}, {label: `at some gates · ${some.length}`, rows: some.map(row)},
            {label: "per stage", rows: [told]}]});
  const step = c.stage ? c.stepOf(c.stage) : null, tile = c.track.tiles.find(t => t.stage === c.stage) || {};
  const side = !step ? ui.card("", "", ui.hint("A column's head picks a stage.", {block: true}))
    : ui.card(esc(c.stage), `${tile.decides ? "decides, no gate" : `${checksOf(step).length} checks`} · told ${(step.told || []).length} · ✓ → ${esc(nextOf(c, c.stage))}`,
        ui.part("if refused", ruleList(c, `side:${c.stage}`, step.decided || [], c.stage) || ui.hint("it tries once more", {block: true}))
        + ui.actions(ui.btn(`open ${c.stage} in the stage view`, {attrs: {"data-rule-view": "stage"}})));
  const legend = ui.card("", "", ui.hint(c.run ? `A dot: that gate asks it. A count: it refused ${c.story.id} there, between the stages.`
    : "A dot: that gate asks it. A count: it refused there, over every story of this project — a stage's own tries inside it among them.", {block: true}));
  return ui.split({main: ui.card("Checks × stages", `${all.length} checks of the ${esc(c.kind)} kind`, matrix), side: side + legend});
}

// --- the run: every stage as a column — the rulebook, or with a story picked what that story met at each
function runView(c) {
  const cols = c.route.map(s => {
    const step = c.stepOf(s), tile = c.track.tiles.find(t => t.stage === s) || {}, checks = checksOf(step);
    const parts = [];
    let verdict = null, flag = "";
    if (c.run) {
      const x = c.run.stages[s] || {}, named = Object.keys(x.checks || {});
      verdict = !x.reached ? {state: "minor", text: "not reached"}
        : x.refused ? {state: "fail", text: `✗ refused ${times(x.refused)}`, small: `${named.length ? named.join(", ") : "the checks are not in the journal (an older run)"}${x.ended === "pass" ? " · then passed" : " · not passed yet"}`}
        : x.ended === "fail" ? {state: "fail", text: "✗ refused inside the stage", small: `${x.tries} ${x.tries === 1 ? "try" : "tries"}`}
        : {state: "pass", text: "✓ passed", small: x.tries ? `${x.tries} ${x.tries === 1 ? "try" : "tries"} inside the stage` : ""};
    } else {
      const total = checks.reduce((n, id) => n + refusedAt(c, id, s), 0);
      flag = total ? ui.flag(`✗ ${total}`, "fail", {title: `refusals at ${s} in this project`}) : "";
      parts.push({label: `told · ${(step.told || []).length}`, html: ruleList(c, `board-told:${s}`, step.told || [], "", 3, true)});
    }
    parts.push(tile.decides ? {label: "decides", html: ui.hint("no gate — reviewers read the change, the judge decides", {block: true})}
      : {label: `checked · ${checks.length}`, html: ruleList(c, `board-checks:${s}`, checks, s, c.run ? 4 : 6, true)});
    if ((step.decided || []).length) parts.push({label: "if refused", html: ruleList(c, `board-decided:${s}`, step.decided, s, 2, true)});
    return {stage: s, picked: s === c.stage, here: !!c.run && c.run.last === s, flag, verdict, parts};
  });
  const line = c.run
    ? ui.hint(`${c.story.id} · ${c.run.kind} · ${Object.values(c.run.stages).reduce((n, x) => n + x.refused, 0)} refusals between the stages · last at ${c.run.last}${c.run.reading === "gate-order" ? " · its ways back read from the order of its gates — its journal is older than the runner's own lines" : ""}`, {block: true})
    : ui.hint("Pick a story above to see where it passed, where it was refused and where it went back.", {block: true});
  return ruleTrack(c) + line + ui.ruleBoard(cols) + (c.run ? "" : ruleGroups(c));
}

function rulesTab(st) {
  if (!S.rules) { loadRules(); return ui.card("", "", ui.empty("Reading the rules…")); }
  if (S.rulesFor !== (S.ruleStory || "")) loadRules();
  const c = rulesContext(st);
  const titles = Object.fromEntries((st.rows || []).map(r => [r.story, r.title]));
  const stories = ((c.v.refusals || {}).stories || []);
  const head = ui.toolbar(ui.switch(RULE_VIEWS.map(([id, label]) => ({label, pressed: id === S.ruleView, attrs: {"data-rule-view": id}})), {label: "the view"})
    // a story picked ran as one kind: the switch shows it and holds; without a story, any kind is picked
    + ui.labelled("kind", ui.switch(c.kinds.map(k => ({label: k, pressed: k === c.kind, attrs: {"data-rule-kind": k},
        disabled: !!c.run, title: c.run ? `${c.story.id} ran as ${c.run.kind}` : ""})), {label: "which kind of story"}))
    + ui.formRow({id: "rule-story", label: "a story", quiet: true, inline: true, attrs: {"data-rule-pick": ""},
        options: [{value: "", label: "no story"}, ...stories.map(id => ({value: id, label: titles[id] ? `${id} — ${titles[id]}` : id, selected: id === S.ruleStory}))]}));
  const view = {stage: stageView, matrix: matrixView, run: runView}[S.ruleView] || stageView;
  if (S.rulesOf !== (S.ruleStory || "")) return head + ui.card("", "", ui.empty(S.ruleStory ? `Reading ${S.ruleStory}…` : "Reading the rules…"));
  return head + view(c)
    + ((c.v.problems || []).length ? ui.card("Problems", "the rulebook itself", `<ul>${c.v.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul>`) : "");
}

// --- the drawer: one rule in full — what it is, where it holds, how it comes out, why or its whole instruction, and
// what the project's journals say of it
function ruleSheet(id) {
  if (!S.rules) return "";
  const c = rulesContext(S.status || {}), r = c.rules[id] || ((S.rules.retired || []).find(x => x.id === id)) || {id, outcomes: []};
  const facts = [["kind of rule", esc(PARTS[r.part] || r.part || "")], ["stages", esc((r.stages || []).join(", ") || "outside the stages")],
    ["kinds", esc((r.kinds || []).join(", ") || "every kind")], (r.reports || []).length ? ["in the gate report", esc(r.reports.join(", "))] : null,
    r.restart ? ["starts anew", esc(`at ${r.restart.stage} when ${r.restart.when} — no round`)] : null];
  const outcomes = (r.outcomes || []).map(o => ui.said(SAYS[o.state] || o.state, inline(clause(o.said)), {icon: o.state, state: o.state, goes: going(o.goes)})).join("");
  const body = r.text ? ui.said("Where", inline(clause(r.when))) + ui.part("the instruction", ui.prose(r.text))
    : (r.why ? ui.intro(inline(sentence(r.why)), {html: true}) : "") + (r.when ? ui.said("When", inline(clause(r.when))) : "");
  const parts = [], found = c.refusals[id], unnamed = (c.v.refusals || {}).unnamed || 0;
  if (found) {
    const list = Object.entries(found.stories).map(([story, n]) => ({press: {label: story, attrs: {"data-rule-story": story}}, aside: times(n)}));
    parts.push({label: "in this project", html: ui.hint(`Refused ${times(found.times)}, last ${found.last.replace("T", " ").slice(0, 16)}, in ${list.length} ${list.length === 1 ? "story" : "stories"} — counting a stage's own tries inside it as well as the refusals between the stages.`, {block: true})
      + ui.list(list.slice(0, 12)) + (list.length > 12 ? ui.hint(`and ${list.length - 12} more`, {block: true}) : "")});
  } else if ((r.reports || []).length) {
    parts.push({label: "in this project", html: ui.hint(`Never refused in the journals.${unnamed ? ` ${unnamed} older refusals name no check — their lines are from before 2026-10-10.` : ""}`, {block: true})});
  }
  if (c.run && (r.reports || []).length) {
    const n = c.run.refused[id] || 0;
    parts.push({label: `in ${c.story.id}`, html: ui.hint(n ? `Refused it ${times(n)} between the stages — each a round.` : "Did not refuse it between the stages (or the journal does not name the checks).", {block: true})});
  }
  return ui.ruleSheet({id, title: inline(ruleTitle(r)), facts, outcomes, body, parts,
    source: `${r.source || ""}${r.bound ? (r.part === "instruction" ? " · placed in " : " · bound in ") + r.bound : ""}`});
}

// --- one story -----------------------------------------------------------------------------------------------------
// a story has a place of its own, `#backlog/<story>`, like a part of the description: its pipeline as a track across,
// beneath it its words beside its figures — from whichever view it is opened, and back to that view (WP-183)
async function loadStory(id) {
  try { S.storyView[id] = await api(`/api/view/story?id=${encodeURIComponent(id)}`); }
  catch (e) { S.storyView[id] = {error: e.message}; }
  if (S.detail === id) render();
}
async function openStory(id) {
  if (S.drawer) CALLS.close();
  if (!onStoryPlace()) S.storyFrom = S.tab;
  if (S.followOn === "story" && S.follow && S.follow.id !== id) stopFollowing();
  // opened from run it stays under run; from anywhere else it stands under the backlog
  S.tab = S.tab === "run" ? "run" : "backlog"; S.detail = id; S.changing = ""; S.autoFollow = "";
  delete S.storyView[id];
  place(); render(); window.scrollTo(0, 0);
}
const secs = s => !s ? "—" : s < 60 ? `${Math.round(s)} s` : s < 3600 ? `${Math.floor(s / 60)} min${s % 60 >= 1 && s < 600 ? ` ${Math.round(s % 60)} s` : ""}`
  : `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min`;
const usd = c => c == null || c === 0 ? "—" : `$${c.toFixed(2)}`;
const toks = n => !n ? "—" : n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)} k` : `${n}`;
// the processes as the factory ran them, a shared builder by its parts; and where a stage stands — the story's course
// while it runs or stopped, everything done once it is delivered
function stagesOf(v, st, id) {
  const live = (st.running || []).find(r => r.story === id) || (st.waiting || []).find(w => w.story === id && w.course) || {};
  const course = live.course || [], done = (v.row || {}).mark === "done";
  const stateOf = name => { const c = course.find(x => x.stage === name); return c ? c.state : done ? "done" : ""; };
  const ran = [];
  for (const [name, e] of Object.entries(v.stages || {})) {
    if ((e.parts || []).length) e.parts.forEach(p => ran.push(Object.assign({name: p.stage, part: true}, p)));
    else ran.push(Object.assign({name}, e));
  }
  for (const c of course) if (!ran.some(r => r.name === c.stage)) ran.push({name: c.stage});
  return ran.map(r => Object.assign(r, {state: stateOf(r.name)}));
}
function storyPage(st, id) {
  const from = S.storyFrom || S.tab;
  const back = ui.actions(ui.btn(`← ${from}`, {attrs: {"data-call": "closeDetail"}}));
  const v = S.storyView[id];
  if (!v) { S.storyView[id] = {loading: true}; loadStory(id); }
  if (!v || v.loading) return back + ui.empty(`Reading ${id}…`);
  if (v.error) return back + ui.error(v.error, {block: true});
  const [head, buttons, text, words] = storyParts(v, id, "m"), row = v.row || {};
  if ((st.running || []).some(r => r.story === id) && !(S.follow && S.follow.id === id) && S.autoFollow !== id) {
    S.autoFollow = id; setTimeout(() => follow("story", id));
  }
  const stages = stagesOf(v, st, id), longest = Math.max(1, ...stages.map(s => s.seconds || 0));
  const track = stages.map(s => ({name: s.name, state: s.state, share: s.seconds ? 100 * s.seconds / longest : null, lines: [
    s.seconds ? `${ui.em(secs(s.seconds))}` : "not run yet",
    s.tokens ? `${esc(toks(s.tokens))} · ${esc(usd(s.cost))}` : "",
    s.runs > 1 ? ui.state(`${s.runs} rounds`, "wait") : ""].filter(Boolean)}));
  const passes = v.passes || [];
  const sum = key => typeof row[key] === "number" ? row[key] : Object.values(v.stages || {}).reduce((all, e) => all + (e[key] || 0), 0);
  const totals = ui.tiles([[secs(sum("seconds")), "worked"], [toks(sum("tokens")), "tokens"], [usd(sum("cost")), "cost"], [`${passes.length}`, passes.length === 1 ? "pass" : "passes"]]
    .map(([n, label]) => ui.tile(n, label)).join(""));
  // the processes as the factory ran them, a shared builder or verifier with its stages beneath it — the cockpit's table
  const processes = [];
  for (const [name, e] of Object.entries(v.stages || {})) {
    processes.push(Object.assign({name}, e));
    (e.parts || []).forEach(p => processes.push(Object.assign({name: p.stage, part: true}, p)));
  }
  const ranStages = processes.filter(s => s.seconds), slowest = Math.max(1, ...ranStages.map(s => s.seconds));
  const time = ranStages.length ? ui.card("Time per stage", "each process and the stages it ran — the bar its share of the longest", ui.table(
      [{label: "process"}, {label: "share"}, {label: "time", num: true}, {label: "runs", num: true}, {label: "tokens", num: true}, {label: "cost", num: true}],
      ranStages.map(s => [s.part ? ui.hint(`· ${s.name}`) : ui.id(s.name), ui.meter(100 * s.seconds / slowest, {thin: true}), esc(secs(s.seconds)),
        s.runs > 1 ? ui.state(`${s.runs}`, "wait") : `${s.runs || ""}`, esc(toks(s.tokens)), esc(s.part ? `≈${usd(s.cost)}` : usd(s.cost))]))
      + ui.accordion({key: `tokens:${id}`, variant: "quiet", open: opened(`tokens:${id}`), head: "tokens per stage — input, output, cache",
          body: () => ui.table([{label: "stage"}, {label: "input", num: true}, {label: "output", num: true}, {label: "cache write", num: true},
            {label: "cache read", num: true}, {label: "tokens", num: true}],
            ranStages.map(s => [esc(s.name), esc(toks(s.input)), esc(toks(s.output)), esc(toks(s.cache_write)), esc(toks(s.cache_read)), esc(toks(s.tokens))]))}))
    : "";
  const passCard = passes.length ? ui.card("Passes", "each time the story went through", ui.table(
      [{label: "#", num: true}, {label: "pass"}, {label: "started"}, {label: "time", num: true}, {label: "tokens", num: true}],
      passes.map((p, i) => [`${i + 1}`, i ? ui.state(p.label || "again", "wait") : esc(p.label || "first"), esc((p.start || "").replace("T", " ").slice(5, 16)),
        esc(secs(p.seconds)), esc(toks(p.tokens))]))) : "";
  // what the judge found in it: the rows still open, each to the backlog or done, and what each perspective found in all
  const found = Object.entries(((v.signals || {}).findings) || {}).map(([who, n]) => `${who} ${n}`).join(" · ");
  const open = (st.findings || []).filter(f => f.story === id);
  const findings = open.length || found ? ui.card("Findings", found ? `found: ${found}` : "", open.length
      ? ui.list(open.map(f => findingRow(f, f.perspective)))
      : ui.empty("None open — each was fixed, or set done or won't fix.")) : "";
  return back + head + buttons
    + ui.card("Pipeline", (v.models || []).length ? `run by ${(v.models || []).join(", ")}` : "", totals + (track.length ? ui.track(track) : ui.empty("Not run yet.")))
    // what its stages took a picture of — a browser test's screenshot, the judge's look — beneath its pipeline (WP-184)
    + ((v.shots || []).length ? ui.card("Screenshots", `${v.shots.length} taken by its stages, newest first — open one to see it large`,
        ui.shots(v.shots.map(s => ({href: fileOf(s.path), alt: s.name, stage: s.stage, at: (s.at || "").replace("T", " ").slice(5, 16),
          // what it shows, in words: its name without the stage before it and the kind after it
          name: s.name.replace(/\.[a-z]+$/i, "").replace(s.stage ? new RegExp(`^${s.stage}-`) : /^$/, "").replace(/[-_]+/g, " ")})))) : "")
    // its output, while followed, stands above its words in the content's column, never across the page
    + ui.split({main: (S.follow && S.follow.kind === "story" && S.follow.id === id ? ui.card("Output", `<span id="follow-title" data-own></span>`, ui.terminal()) : "")
        + ui.card("", "", text || ui.empty("The story has no words yet.")), side: words + findings + time + passCard});
}
function storyParts(v, id, scope) {
  const row = v.row || {};
  // the factory's sections in its order, the scenarios where its criteria stood — each folded to its title, opened
  // to its rule and its steps
  const scenarios = (v.scenarios || []).map(c => {
    const key = `scenario:${id}:${c.key || c.title}`, steps = c.steps || [];
    return ui.accordion({key, variant: "row", open: opened(key), head: esc(c.title || c.key),
      meta: ui.hint(`${steps.length} step${steps.length === 1 ? "" : "s"}`),
      body: () => (c.rule ? ui.hint(c.rule, {block: true}) : "") + steps.map(s => ui.step(s.word, s.text)).join("")});
  }).join("");
  const list = v.sections || [], at = v.criteria_at == null ? list.length : v.criteria_at;
  // the story's words as written text, its scenarios among its sections
  const text = list.length || scenarios ? ui.document(list.slice(0, at).map(one => ui.section(one, 2, v.path)).join("") + (scenarios ? `<h2>Scenarios</h2>${scenarios}` : "")
    + list.slice(at).map(one => ui.section(one, 2, v.path)).join("")) : "";
  const head = ui.pageHead(v.epic, v.title || id, "")
    + ui.figures([["state", esc(row.state || v.situation || "")], v.context ? ["context", esc(v.context)] : null, ["file", esc(v.path)]].filter(Boolean));
  const buttons = ui.actions(acts((v.actions || []).filter(a => a.request.open !== "words"), scope)
      + (Object.keys(v.stages || {}).length || row.mark === "running" ? ui.btn("output", {attrs: {"data-call": "follow", "data-kind": "story", "data-id": id}}) : ""));
  // what the person says to a story in words — a correction, a change — stands beside its text, not above its pipeline
  // its card is named for what the words become — the button keeps its verb
  const named = a => ({correct: "A correction", change: "A change", answer: "An answer", describe: "A change to the description"})[a.request.kind]
    || a.label.charAt(0).toUpperCase() + a.label.slice(1);
  const words = (v.actions || []).filter(a => a.request.open === "words" && !a.waits_on).map(a => ui.card(esc(named(a)), "", act(a, scope))).join("");
  return [head, buttons, text, words];
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
  const card = {id: sample.story, title: sample.title, line: "ready · plan", actions: ui.btn("run it", {size: "s", primary: true})};
  return ui.gallery([
    {level: "primitives — controls", items: [
      ["btn", [ui.btn("change this"), ui.btn("accept", {primary: true}), ui.btn("draft it", {write: true}), ui.btn("draft it", {primary: true, write: true}),
               ui.btn("start", {icon: "play", primary: true, plain: true}), ui.btn("drop", {danger: true}), ui.btn("open")].join(" ")],
      ["btn · sizes", ["s", "m", "l"].map(size => ui.btn(size, {size}) + " " + ui.btn(size, {size, primary: true})).join(" · ")],
      ["link", `${ui.link("a link in a sentence")} · ${ui.link("a story's title", {title: true})} · ${ui.link("all →", {to: true})} · ${ui.link("plan → test", {way: true})} · ${ui.link("a quiet head", {plain: true})}`],
      ["switch", ui.switch([{label: "all", pressed: true, n: 12}, {label: "open", n: 4}, {label: "drafts", n: 1}], {label: "which"})],
      ["select · field", ui.formRow({id: "g-select", label: "a select", options: [{value: "one"}, {value: "two"}]})
        + ui.formRow({id: "g-field", label: "a field", value: "words"})],
      ["caret", `${ui.caret(false)} ${ui.caret(true)}`]]},
    {level: "primitives — form text", items: [
      ["label · hint · error", `${ui.label("A label", "g-field")} ${ui.hint("what the field takes")} ${ui.error("what was wrong")}`]]},
    {level: "primitives — displays", items: [
      ["em", `a line with ${ui.em("one word")} that stands out`],
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
    {level: "components — parts", items: [
      ["story", ui.story(sample.story, sample.title)],
      ["menu", ui.menu({id: "g-menu", label: "CB", title: "a menu, closed"})],
      ["list · press", ui.list([{mark: "done", press: {label: "product"}, what: ui.id("product/overview.md", {block: true}) + ui.hint("an item that opens as a whole")},
        {mark: "stopped", on: true, press: {label: sample.title}, what: ui.id(sample.story, {block: true}) + ui.hint("open beside its list; its one press at the row's end", {prose: true}),
         aside: ui.btn("run it again", {size: "s"})}])],
      ["form-row", ui.formRow({id: "g-row", label: "Your name", hint: "as it stands beside your requests", value: "Ann"})
        + ui.formRow({id: "g-row-bad", label: "A story id", value: "Not An Id", error: "an id is lower case words joined by -"})],
      ["ask", ui.ask({id: "g-ask", draft: "gallery-ask", label: "wish", text: "What should exist?", primary: true, write: true, choices: ["too big", "unclear"]})],
      ["shots", ui.shots([{href: "data:image/gif;base64,R0lGODlhAQABAIAAAA5ubv///yH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==", name: "the desk", stage: "judge", at: "11-04 18:02"},
                          {href: "data:image/gif;base64,R0lGODlhAQABAIAAAMhkUP///yH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==", name: "the queue", stage: "test", at: "11-04 17:40"}])],
      ["ask · files", ui.ask({id: "g-ask-files", draft: "gallery-ask-files", label: "answer", text: "in your words",
        files: [{key: "g1", name: "the-page-today.png", size: 182000}, {key: "g2", name: "process.pdf", size: 1400000},
                {key: "g3", name: "notes.md", size: 900, busy: true}, {key: "g4", name: "big.mov", size: 0, error: "not a picture, a PDF or a text"}]})],
      ["actions", ui.actions(ui.btn("release", {primary: true}) + ui.btn("change this"))],
      ["tile", ui.tiles(ui.tile("22", "of 26 stories delivered", {lead: true}) + ui.tile("3", "domain findings", {bad: true, said: "2 model · 1 language"}) + ui.tile("$41", "cost"))],
      ["kv", ui.kv([["story", ui.id(sample.story)], ["state", "ready"]])],
      ["toast", ui.toast("request written: r-12") + ui.toast("the gate refused", true)],
      ["legend · strip", ui.legend(STRIP_KEY) + ui.strip(["draft", "approved", "running", "stopped", "delivered", "superseded"], "the strip")],
      ["said", ui.said("Given", "a reader with no loan") + ui.said("Fails when", "the tests are red.", {icon: "fail", state: "fail", goes: "→ once more"})],
      ["figures · bars", ui.figures([["questions", "3/4"], ["domain", "2", true]]) + ui.bars([["ddd", 4, 100], ["hexagonal", 1, 25]])],
      ["toolbar", ui.toolbar(ui.switch([{label: "story", pressed: true}, {label: "task"}]))],
      ["quiet-line", ui.quietLine(`Beside that: ${ui.link("2 open findings →", {quiet: true})}`)],
      ["notice", ui.notice("What comes next stands here.") + ui.notice("The factory ended on its own.", {ended: true, action: ui.btn("start", {icon: "play", primary: true, plain: true})})],
      ["story-card", ui.galleryList(["draft", "approved", "running", "stopped", "delivered", "superseded"].map(s => ui.storyCard(Object.assign({}, card, {state: s}))).join(""))],
      ["ticket", ui.galleryList(ui.ticket({kind: "wish", target: "", word: "running", state: "running", id: "r-12 · Ann", actions: ui.btn("take back", {size: "s", danger: true})}))],
      ["option · options", ui.options([{advised: true, pick: ui.btn("a", {primary: true}), text: "the recommended answer"}, {pick: ui.btn("b"), text: "another answer"}])],
      ["list-item", ui.list([{mark: "done", what: ui.story(sample.story, sample.title), aside: "today 10:12<br>$3.10"}])],
      ["delivery", ui.delivery({head: true}) + ui.delivery({at: "10:12", story: sample.story, title: sample.title, epic: sample.epic, event: "BookLent", seconds: "14 min", tokens: "4.1 M", cost: "$3.10"})],
      ["domain-node · facts · rule-block", ui.domainNode("Domain model", "from its glossary")
        + ui.facts([{kind: "aggregate", terms: [{name: "Loan"}]}, {kind: "values", terms: [{name: "Due date"}, {name: "Money", shared: true}]}])
        + ui.ruleBlock("A reader holds three loans at most.", [ui.accordion({key: "gallery:scenario", variant: "row", open: false, head: "a fourth loan is refused"})])],
      ["proposal", ui.galleryList(ui.proposal({goal: "Readers find a free copy", intent: "fewer empty shelves", metric: "CopyFound", contact: "the desk", id: "p-1", actions: ui.btn("make it an epic", {write: true})}))],
      ["aside · section · prose", ui.aside("Why it is not built", ui.prose("It **waits** for `a-reader-joins`.")) + ui.document(ui.section({heading: "Scope", text: "- one\n- two"}), {compact: true})],
      ["trail · trail-item", ui.trail([{words: "readers may reserve", tone: "wait", text: "writing", by: "Ann", actions: ""}, {words: "a due-date reminder", tone: "ok", text: "✓ became the draft story x", actions: ui.btn("open", {size: "s"})}, {words: "fines in another currency", tone: "bad", text: "✗ failed", actions: ""}])],
      ["tab", ui.tab({id: "gallery-a", key: 9, n: 2, on: true}) + ui.tab({id: "gallery-b", key: 8})],
      ["step", lines.map(l => l.slice(2).split(" ")).map(([w, ...rest]) => ui.step(w, rest.join(" "))).join("")]]},
    {level: "components — sections", items: [
      ["card", ui.card("A card", "what it holds", ui.intro("Its body."))],
      ["run-control · run-panel", ["up", "stopping", "down"].map(state => ui.runControl({state, say: state === "down" ? "stopped · 1 ready" : `${ui.em(sample.story)} · build`,
          act: ui.btn(state === "down" ? "start the backlog" : "stop", {icon: state === "down" ? "play" : "stop", primary: state === "down", plain: state === "down", bar: true, size: "s"}), panel: ""})).join(" ")
        + ui.runPanel({runs: [{id: sample.story, title: sample.title, word: "build · round 2 · 3 min", doing: "writing the loan's adapter",
            steps: [{stage: "plan", state: "done"}, {stage: "test", state: "done"}, {stage: "build", state: "now"}, {stage: "tidy", state: ""}]}],
          lines: ["next: a-reader-renews-a-loan, then 1 more"], acts: ui.btn("stop after the running story", {icon: "stop"}) + ui.link("open the run →", {quiet: true})})],
      ["accordion", ["row", "quiet", "group", "ink", "panel", "card"].map(variant => ui.accordion({key: `gallery:${variant}`, variant, open: opened(`gallery:${variant}`, variant === "row"),
        level: variant === "card" ? 3 : 0, head: `the ${variant} fold`, meta: ui.hint("meta"), body: () => ui.intro("What it folds.")})).join("")],
      ["fold-table", ui.foldTable([{label: "context"}, {label: "features", num: true}, {label: "criteria", num: true}],
        [{key: "gallery:ft:lending", open: opened("gallery:ft:lending"), cells: [ui.em("lending"), "1", "2"], body: () => ui.intro("What it folds.")},
         {key: "gallery:ft:catalogue", open: false, cells: [ui.em("catalogue"), "3", "14"], body: ""}])],
      ["tabs · tab-bar", ui.tabBar([{tabs: [{id: "gallery-c", key: 1}, {id: "gallery-d", key: 2, on: true}], ordered: true}])],
      ["board · column", ui.board([ui.column({name: "backlog", count: 4, line: "released — 2 more blocked", items: [ui.story(sample.story, sample.title)], actions: ui.btn("run it", {primary: true})}),
        ui.column({name: "decide", count: 1, line: "waits for you", hot: true, items: ["a question"]}),
        ui.column({name: "delivered", count: 22, of: 26, line: "85 %", meter: 85, actions: ui.link("all →", {to: true})})])],
      ["wish", ui.wish(ui.ask({id: "g-wish", draft: "gallery-wish", label: "wish", text: "What should exist?", primary: true, write: true}),
        [{words: "readers may reserve", tone: "ask", text: "? asks back", actions: ui.btn("answer", {size: "s", primary: true})}])],
      ["list", ui.list([{mark: "done", what: "one delivery"}, {mark: "done", what: "another"}])],
      ["lane · lanes", ui.lanes(["draft", "approved", "running", "delivered"].map(name => ({name, key: `gallery:lane:${name}`, open: false,
        cards: name === "running" ? [Object.assign({}, card, {state: "running"})] : [], more: name === "delivered" ? [Object.assign({}, card, {state: "delivered"})] : []})))],
      ["epic", ui.epic({key: "gallery:epic", open: opened("gallery:epic"), title: "Lending", id: sample.epic, metric: "BookLent", tone: ui.state("running", "running"), count: "2/5",
        strip: ["approved", "running", "delivered", "delivered", "superseded"], stripTitle: "2 of 5 delivered", body: () => ui.intro("The epic's goal.")})],
      ["document", ui.document(`<h2>Story</h2>${ui.prose("As a reader I want to return a book, so that I owe nothing more.")}<h2>Scenarios</h2><h3>A returned book is free again</h3>`
        + ui.step("Given", "a lent copy") + ui.step("When", "the reader returns it") + ui.step("Then", "the copy is free"))],
      ["track", ui.track([{name: "plan", state: "done", share: 45, lines: [ui.em("3 min 10 s"), "0.8 M · $0.60"]},
        {name: "build", state: "now", share: 100, lines: [ui.em("6 min 40 s"), "2.0 M · $1.50", ui.state("2 rounds", "wait")]},
        {name: "tidy", state: "", lines: ["not run yet"]}])],
      ["stepper · course", ui.course({id: sample.story, title: sample.title, state: "running", word: "build · round 2", right: ui.btn("follow", {size: "s"}),
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
      ["rule-group · part · outcome", ui.part("Checked afterwards", ui.outcome("pass", "All pass → on to " + ui.em("test"), "") + ui.outcome("fail", "One fails → what happens next", ui.ruleGroup("its checks", [ui.accordion({key: "gallery:rule", variant: "row", open: false, head: "The tests are red", meta: ui.ruleId("GATE-TESTS", "gate", "fail")})])))],
      ["rule-track", ui.ruleTrack({tiles: [{stage: "plan", meta: "4 checks · told 9", notes: [{text: "↩ again from here when the story changed", title: "a restart — no round"}]},
          {stage: "test", meta: "6 checks · told 12", state: {text: "↺ up to 3 rounds", tone: "wait"}},
          {stage: "build", picked: true, meta: "5 checks · told 8", state: {text: "↺ up to 3 rounds", tone: "wait"}},
          {stage: "judge", meta: "decides · told 4", state: {text: "↺ sends back · a round", tone: "wait"}}, {end: true, stage: "delivered", name: "delivered", note: "after a person's acceptance"}],
        ways: [{source: "build", target: "test", round: true, solid: true, label: "a test cannot pass", title: "build → test"},
               {source: "judge", target: "build", round: true, label: "changes requested", title: "judge → build"},
               {source: "delivered", target: "plan", round: false, label: "a correction at acceptance", title: "delivered → plan"}],
        legend: [["wait", "━ costs a round"], ["", "━ costs no round"], ["", "solid: where the picked stage sends a story back"]]})],
      ["rule-row · rule-rows", ui.ruleRows([{id: "GATE-SUITE", title: "The whole suite is green", aside: ui.flag("✗ 8", "fail")}, {id: "STAGE-BUILD-1", title: "Build the smallest change that turns the tests green"},
        {id: "GATE-TESTS-KEPT", title: "A test the stage kept is unchanged", state: "fail", aside: ui.flag("✗ 2", "fail")}])],
      ["labelled", ui.labelled("kind", ui.switch([{label: "story", pressed: true}, {label: "task"}], {label: "which kind"}))],
      ["stage-read", ui.stageRead({told: ui.card("While it works", "told · 2", ui.ruleRows([{id: "STAGE-BUILD-1", title: "Build the smallest change"}])),
        checked: ui.card("Checked afterwards", "1 check", ui.ruleRows([{id: "GATE-SUITE", title: "The whole suite is green"}])),
        next: ui.card("", "", ui.outcome("pass", "all pass → " + ui.em("tidy"), "")) + ui.card("", "", ui.outcome("fail", "one fails → what happens next", ""))})],
      ["rule-matrix", ui.ruleMatrix({stages: [{stage: "test"}, {stage: "build", picked: true}, {stage: "tidy"}],
        bands: [{label: "at (almost) every gate · 1", rows: [{id: "GATE-OWNED", title: "What a person owns stays unchanged", name: "owned", cells: {test: {}, build: {n: 2}, tidy: {}}}]},
                {label: "per stage", rows: [{title: "told before the stage", cells: {test: {text: "12"}, build: {text: "8"}, tidy: {text: "5"}}}]}]})],
      ["rule-board", ui.ruleBoard([{stage: "test", verdict: {state: "pass", text: "✓ passed", small: "2 tries inside the stage"}, parts: [{label: "checked · 1", html: ui.ruleRows([{id: "GATE-RED", title: "The new tests are red"}])}]},
        {stage: "build", here: true, picked: true, verdict: {state: "fail", text: "✗ refused 2×", small: "suite · not passed yet"}, parts: [{label: "checked · 1", html: ui.ruleRows([{id: "GATE-SUITE", title: "The whole suite is green", state: "fail", aside: ui.flag("✗ 2", "fail")}])}]},
        {stage: "tidy", verdict: {state: "minor", text: "not reached"}, flag: ui.flag("✗ 3", "fail"), parts: []}])],
      ["rule-sheet", ui.ruleSheet({id: "GATE-SUITE", title: "The whole suite is green", facts: [["kind of rule", "check"], ["stages", "build, tidy"], ["in the gate report", "suite"]],
        outcomes: ui.said("Passes when", "every test is green.", {icon: "pass", state: "pass"}) + ui.said("Fails when", "a test is red.", {icon: "fail", state: "fail", goes: "→ once more"}),
        body: ui.intro("A story is done only on a green suite."), parts: [{label: "in this project", html: ui.hint("Refused 26× in 20 stories.", {block: true})
          + ui.list([{press: {label: sample.story}, aside: "3×"}])}], source: "workflow/rules/gate/GATE-SUITE.md"})],
      ["rule-folds", ui.ruleFolds([ui.accordion({key: "gallery:fold-a", variant: "card", level: 3, open: opened("gallery:fold-a"), head: "At every gate", body: () => ui.intro("What it folds.")}),
        ui.accordion({key: "gallery:fold-b", variant: "card", level: 3, open: opened("gallery:fold-b"), head: "Anywhere in a run", body: () => ui.intro("What it folds.")})])],
      ["table", ui.table([{label: "story"}, {label: "state"}, {label: "tokens", num: true}, {act: true}], [[ui.story(sample.story, sample.title), "ready", "1.2 M", ui.btn("run it", {size: "s"})]])],
      ["terminal", ui.terminal()],
      ["curve", ui.curve(curve)],
      ["curve-tip", ui.curveTip(curve[2], [["cost so far", "$15.00"], ["this one", "$6.00"]])]]},
    {level: "templates", items: [
      ["page-head", ui.pageHead("Now", "Where it stands", "The lede of a tab.")],
      ["split", ui.split({main: ui.card("The content", "8 of the 12 columns on a wide window", ui.intro("What the view is about.")),
        side: ui.card("Beside it", "the other 4", ui.intro("What belongs to it."))})],
      ["split · side first", ui.split({sideFirst: true, main: ui.card("The content", "beneath on a narrower window", ui.intro("The detail.")),
        side: ui.card("The summary", "above it on a narrower window, beside it on a wide one", ui.intro("What sums it up."))})],
      ["master", ui.master({label: "the opened item", list: ui.card("A list", "", ui.intro("Its items; one opens beside it.")),
        detail: ui.drawerFrame(ui.btn("close"), ui.pageHead(sample.epic, sample.title, ""), ui.intro("The opened item."))})],
      ["reader", ui.reader({label: "a part — its sections", head: ui.caption("sections"), sections: [
        {id: "g-sec-1", heading: "What and for whom", body: ui.prose("A part of the description, read as a document."),
         aside: ui.link("change this section", {quiet: true, compact: true})},
        {id: "g-sec-2", heading: "Surfaces", body: ui.prose("Each section with its own heading; the margin carries what one does with it.")}]})],
      ["drawer-frame", ui.drawerFrame(ui.btn("close"), ui.pageHead(sample.epic, sample.title, ""), ui.intro("The story's sections."))],
      ["gallery", ui.hint("this page", {block: true})]]}]);
}
"""
