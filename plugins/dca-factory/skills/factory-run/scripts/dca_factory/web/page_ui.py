r"""The page's components (WP-180): every piece of markup the page draws, in Brad Frost's levels.

Each component is one BEM block and one function `ui.<name>` — the block named in kebab case, the function in camel
case (`ui.formRow` draws `.form-row`). A component starts at a line `ui.<name> = ` under its level's header
(`// --- atoms`, `// --- molecules`, `// --- organisms`, `// --- templates`) and calls only components of its own
level or below; an atom calls none. This is the one module of the page that writes a `class`: the views compose these
and write none of their own, and every form field is set through `ui.formRow`. A state the factory names reaches the
markup as `data-state`, its word written through — never as a class. The unit test `test_page_components.py` holds
all of it.
"""

SCRIPT_UI = r"""
// === ui: the components, by level ================================================================================
const ui = {};
const attrs = o => Object.entries(o || {}).filter(([, v]) => v !== undefined && v !== null && v !== false)
  .map(([k, v]) => v === true ? ` ${k}` : ` ${k}="${esc(v)}"`).join("");
const mods = (block, list) => [block, ...list.filter(Boolean).map(m => `${block}--${m}`)].join(" ");
const slug = key => String(key).replace(/[^A-Za-z0-9_-]+/g, "-");

// the delivered curve: two panels on one time axis — cost above, tokens below — drawn as the factory sums it
const CURVE = {w: 1000, left: 64, right: 96, top: 26, panel: 120, gap: 44, bottom: 24};
function curveSvg(curve) {
  const {w, left, right, top, panel, gap, bottom} = CURVE, h = top + panel * 2 + gap + bottom;
  const t = curve.map(c => Date.parse(c.at)), t0 = t[0], t1 = t[t.length - 1] === t0 ? t0 + 864e5 : t[t.length - 1];
  const x = v => left + (v - t0) / (t1 - t0) * (w - left - right);
  const panels = [{name: "cost, cumulative", key: "cost_total", fmt: money, y0: top},
                  {name: "tokens, cumulative", key: "tokens_total", fmt: count, y0: top + panel + gap}];
  let out = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="cost and tokens of every delivery so far, over time">`;
  for (const p of panels) {
    const max = niceMax(curve[curve.length - 1][p.key]), y = v => p.y0 + panel - v / max * panel;
    p.y = y;
    for (const f of [0, .5, 1]) out += `<line class="curve__grid" x1="${left}" x2="${w - right}" y1="${y(max * f)}" y2="${y(max * f)}"/>`
      + `<text class="curve__axis" x="${left - 8}" y="${y(max * f) + 4}" text-anchor="end">${esc(p.fmt(max * f))}</text>`;
    // a sum holds until the next delivery: a step, not a slope
    let d = `M${x(t[0])},${y(0)}`;
    curve.forEach((c, i) => { d += ` V${y(c[p.key])}` + (i + 1 < curve.length ? ` H${x(t[i + 1])}` : ""); });
    out += `<path class="curve__area" d="${d} V${y(0)} Z"/><path class="curve__line" d="${d}"/>`
      + `<text class="curve__name" x="${left}" y="${p.y0 - 10}">${esc(p.name)}</text>`
      + `<text class="curve__end" x="${x(t[t.length - 1]) + 8}" y="${y(curve[curve.length - 1][p.key]) + 4}">${esc(p.fmt(curve[curve.length - 1][p.key]))}</text>`;
  }
  const ticks = 6, axisY = top + panel * 2 + gap + 18;
  for (let i = 0; i <= ticks; i++) {
    const v = t0 + (t1 - t0) * i / ticks, day = new Date(v).toISOString().slice(5, 10);
    out += `<text class="curve__axis" x="${x(v)}" y="${axisY}" text-anchor="middle">${day}</text>`;
  }
  out += `<line class="curve__cross" id="curve-cross" x1="0" x2="0" y1="${top}" y2="${top + panel * 2 + gap}" visibility="hidden"/>`
    + panels.map((p, n) => `<circle class="curve__dot" id="curve-dot-${n}" r="4.5" cx="0" cy="0" visibility="hidden"/>`).join("")
    + `<rect id="curve-hit" x="${left}" y="${top}" width="${w - left - right}" height="${panel * 2 + gap}" fill="transparent"/></svg>`;
  S.curvePanels = panels.map(p => ({key: p.key, y: p.y}));
  S.curveX = {t0, t1, x0: left, x1: w - right};
  return out;
}

// --- atoms
// a control is pressed — a raised rectangle in the display face; a display is read — flat, in the mono face
ui.btn = (label, o = {}) => `<button type="button" class="${mods("btn", [o.primary && "primary", o.write && "write",
  o.danger && "danger", o.small && "small", o.plain && "plain", o.bar && "bar"])}"${o.title ? ` title="${esc(o.title)}"` : ""}${attrs(o.attrs)}>${esc(label)}</button>`;
ui.link = (label, o = {}) => `<button type="button" class="${mods("link", [o.title && "title", o.to && "to", o.way && "way",
  o.plain && "plain"])}"${attrs(o.attrs)}>${o.html ? label : esc(label)}</button>`;
ui.switch = (items, o = {}) => `<span class="${mods("switch", [o.bar && "bar"])}" role="group"${o.label ? ` aria-label="${esc(o.label)}"` : ""}>${items.map(i =>
  `<button type="button" class="switch__opt" aria-pressed="${!!i.pressed}"${attrs(i.attrs)}>${esc(i.label)}${i.n != null ? `<span class="switch__n">${esc(i.n)}</span>` : ""}</button>`).join("")}</span>`;
ui.select = o => `<select class="select" id="${esc(o.id)}"${attrs(o.attrs)}>${(o.options || []).map(p =>
  `<option value="${esc(p.value)}"${p.selected ? " selected" : ""}>${esc(p.label == null ? p.value : p.label)}</option>`).join("")}</select>`;
ui.field = o => o.multiline
  ? `<textarea class="${mods("field", ["area"])}" id="${esc(o.id)}"${attrs(o.attrs)}>${esc(o.value || "")}</textarea>`
  : `<input class="${mods("field", [o.bar && "bar"])}" id="${esc(o.id)}" type="${esc(o.type || "text")}" value="${esc(o.value || "")}"${attrs(o.attrs)}>`;
ui.caret = open => `<svg class="caret" viewBox="0 0 12 12" aria-hidden="true"${open ? " data-open" : ""}><path d="M4.25 2.5 7.75 6l-3.5 3.5"/></svg>`;
ui.label = (text, forId, o = {}) => `<label class="${mods("label", [o.quiet && "quiet"])}" for="${esc(forId)}">${esc(text)}</label>`;
ui.hint = (text, o = {}) => `<${o.block ? "p" : "span"} class="${mods("hint", [o.block && "block"])}"${o.id ? ` id="${esc(o.id)}"` : ""}${o.title ? ` title="${esc(o.title)}"` : ""}>${o.html ? text : esc(text)}</${o.block ? "p" : "span"}>`;
ui.error = (text, o = {}) => `<${o.block ? "p" : "span"} class="error"${o.id ? ` id="${esc(o.id)}"` : ""}>✗ ${esc(text)}</${o.block ? "p" : "span"}>`;
ui.term = (name, o = {}) => `<span class="${mods("term", [o.minor && "minor", o.shared && "shared"])}"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(name)}</span>`;
ui.event = (text, o = {}) => `<span class="event"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(text)}</span>`;
ui.state = (word, state, o = {}) => `<span class="state" data-state="${esc(state || word)}"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(word)}</span>`;
ui.mark = m => `<span class="mark" data-state="${esc(m)}" aria-hidden="true">${esc(MARKS[m] || "")}</span>`;
ui.icon = state => ICONS[state] ? `<svg class="icon" data-state="${esc(state)}" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10"/>${ICONS[state]}</svg>`
  : `<svg class="icon" data-state="minor" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 10h8"/></svg>`;
ui.num = (figure, unit) => `<span class="num">${esc(figure)}${unit ? `<span class="num__unit">${esc(unit)}</span>` : ""}</span>`;
ui.id = (text, o = {}) => `<${o.block ? "div" : "span"} class="id">${o.html ? text : esc(text)}</${o.block ? "div" : "span"}>`;
ui.dot = state => `<span class="dot" data-state="${esc(state)}"></span>`;
ui.spinner = () => `<span class="spinner" aria-hidden="true"></span>`;
ui.meter = (percent, o = {}) => `<span class="${mods("meter", [o.thin && "thin"])}"><i class="meter__fill" style="width:${Math.max(0, Math.min(100, +percent || 0))}%"></i></span>`;
ui.flag = (text, state, o = {}) => `<span class="flag" data-state="${esc(state)}"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(text)}</span>`;
ui.pill = (text, kind) => `<span class="${mods("pill", [kind])}">${esc(text)}</span>`;
ui.empty = text => `<p class="empty">${esc(text)}</p>`;
ui.intro = (text, o = {}) => `<p class="intro">${o.html ? text : esc(text)}</p>`;
ui.note = (text, o = {}) => `<div class="note"${o.state ? ` data-state="${esc(o.state)}"` : ""}>${o.html ? text : esc(text)}</div>`;
ui.ruleId = (id, enforcement, state, refused) => `<span class="${mods("rule-id", [enforcement])}"${state ? ` data-state="${esc(state)}"` : ""}>${esc(id)}${refused ? `<span class="rule-id__refused">×${esc(refused)}</span>` : ""}</span>`;

// --- molecules
ui.story = (id, title) => ui.link(title || id, {title: true, attrs: {"data-story": id}});
// the only way a field is set: its label, the field, what it takes and what was wrong — tied by for, id and describedby
ui.formRow = o => {
  const hintId = o.hint ? `${o.id}-hint` : "", errorId = o.error ? `${o.id}-error` : "";
  const described = [hintId, errorId].filter(Boolean).join(" ");
  const own = Object.assign({}, o.attrs, described ? {"aria-describedby": described} : {}, o.error ? {"aria-invalid": "true"} : {});
  const field = o.options ? ui.select({id: o.id, options: o.options, attrs: own})
    : ui.field({id: o.id, multiline: o.multiline, value: o.value, type: o.type, bar: o.bar, attrs: own});
  return `<div class="${mods("form-row", [o.inline && "inline", o.bar && "bar"])}">${ui.label(o.label, o.id, {quiet: o.quiet})}${field}`
    + (o.hint ? ui.hint(o.hint, {id: hintId}) : "") + (o.error ? ui.error(o.error, {id: errorId}) : "") + `</div>`;
};
// the person's words for an action: the field, an optional why, the button — kept by its draft until written
ui.ask = o => `<div class="ask" data-ask="${esc(o.id)}">`
  + ui.formRow({id: `ask-${slug(o.draft || o.id)}`, label: o.text || o.label, multiline: true, value: o.value, attrs: {"data-draft": o.draft}})
  + ((o.choices || []).length ? ui.formRow({id: `why-${slug(o.draft || o.id)}`, label: "why? (optional)", quiet: true,
      options: [{value: "", label: "—"}, ...o.choices.map(c => ({value: c}))]}) : "")
  + `<div class="ask__go">${ui.btn(o.label, {primary: o.primary, write: o.write, title: o.title, attrs: {"data-press": o.id}})}</div></div>`;
ui.actions = (inner, o = {}) => inner ? `<div class="${mods("actions", [o.end && "end", o.tight && "tight", o.foot && "foot"])}"${o.id ? ` id="${esc(o.id)}"` : ""}${o.own ? " data-own" : ""}>${inner}</div>` : "";
ui.tile = (figure, label, o = {}) => `<div class="${mods("tile", [o.lead && "lead", o.bad && "alert"])}"${o.title ? ` title="${esc(o.title)}"` : ""}>${ui.num(figure)}<span class="tile__label">${esc(label)}</span>${o.said ? `<small class="tile__said">${esc(o.said)}</small>` : ""}</div>`;
ui.kv = pairs => `<dl class="kv">${pairs.filter(Boolean).map(([k, v]) => `<dt class="kv__key">${esc(k)}</dt><dd class="kv__value">${v}</dd>`).join("")}</dl>`;
ui.toast = (text, isError) => `<div class="${mods("toast", [isError && "error"])}" role="status">${esc(text)}</div>`;
ui.legend = items => `<div class="legend">${items.map(([state, label]) => `<span class="legend__item"><i class="legend__key" data-state="${esc(state)}"></i>${esc(label)}</span>`).join("")}</div>`;
ui.strip = (states, title) => `<div class="strip" title="${esc(title)}">${states.map(s => `<i class="strip__seg" data-state="${esc(s)}"></i>`).join("")}</div>`;
ui.said = (keyword, html, o = {}) => `<p class="said"${o.state ? ` data-state="${esc(o.state)}"` : ""}>${keyword || o.icon ? `<span class="said__kw">${o.icon ? ui.icon(o.icon) + " " : ""}${esc(keyword)}</span> ` : ""}${html}${o.goes ? ` <span class="said__goes">${esc(o.goes)}</span>` : ""}</p>`;
ui.figures = items => `<div class="figures">${items.filter(Boolean).map(([label, value, bad]) => `<span class="figures__item">${esc(label)} <b class="${mods("figures__value", [bad && "alert"])}">${value}</b></span>`).join("")}</div>`;
ui.bars = rows => `<div class="bars">${rows.map(([label, n, percent]) => `<span class="bars__label">${esc(label)}</span>${ui.meter(percent)}<span class="bars__n">${esc(n)}</span>`).join("")}</div>`;
ui.toolbar = inner => `<div class="toolbar">${inner}</div>`;
ui.inflow = (label, hint) => `<div class="inflow"><span class="inflow__label">${esc(label)}</span>${ui.hint(hint)}</div>`;
ui.quietLine = html => `<p class="quiet-line">${html}</p>`;
ui.notice = (html, o = {}) => `<div class="${mods("notice", [o.ended && "ended"])}"><div class="notice__text"><span class="notice__arrow">${o.ended ? "!" : "→"}</span>${html}</div>${o.action || ""}</div>`;
ui.storyCard = o => `<div class="story-card" data-state="${esc(o.state)}">${ui.story(o.id, o.title)}${ui.id(o.line, {block: true})}${ui.actions(o.actions, {tight: true})}</div>`;
ui.ticket = o => `<div class="ticket"><div class="ticket__what"><b class="ticket__kind">${esc(o.kind)}</b>${o.target ? `<span>${esc(o.target)}</span>` : ""}${ui.state(o.word, o.state)}${o.words ? `<span>${esc(o.words)}</span>` : ""}</div>`
  + (o.id ? ui.id(o.id, {block: true}) : "") + (o.error ? ui.error(o.error, {block: true}) : "") + (o.note ? ui.note(o.note, {html: true, state: "wait"}) : "")
  + ui.actions(o.actions, {tight: true}) + `</div>`;
ui.option = o => `<div class="${mods("option", [o.advised && "advised"])}"><div class="option__pick">${o.pick}</div>${o.advised ? `<span class="option__advised">recommended</span>` : ""}<span class="option__text">${o.text}</span></div>`;
ui.listItem = o => `<li class="list__item">${o.mark ? ui.mark(o.mark) : ""}<span class="list__what">${o.what}</span>${o.aside ? `<span class="list__aside">${o.aside}</span>` : ""}</li>`;
ui.delivery = o => o.head
  ? `<div class="${mods("delivery", ["head"])}" aria-hidden="true">${["at", "story", "epic", "outcome event", "time", "tokens", "cost"].map((label, i) =>
      `<span class="${mods("delivery__label", [i > 3 && "num"])}${i === 2 || i === 5 ? " hide-narrow" : ""}">${label}</span>`).join("")}</div>`
  : `<div class="delivery"><div class="delivery__at">${esc(o.at)}</div><div class="delivery__what">${ui.story(o.story, o.title)}</div>
  <div class="delivery__epic" title="${esc(o.epic)}">${esc(o.epic)}</div><div class="delivery__event">${o.event ? ui.event(o.event, {title: o.event}) : ""}</div>
  <div class="delivery__fig">${esc(o.seconds || "")}</div><div class="delivery__fig delivery__fig--tokens hide-narrow">${esc(o.tokens || "")}</div><div class="delivery__fig">${esc(o.cost || "")}</div></div>`;
ui.domainNode = (n, title, hint) => `<div class="domain-node"><span class="domain-node__n">${esc(n)}</span>${esc(title)}${hint ? ui.hint(hint) : ""}</div>`;
ui.facts = groups => `<dl class="facts">${groups.map(g => `<dt class="facts__kind">${esc(g.kind)}</dt><dd class="facts__terms">${g.terms.map(t => ui.term(t.name, t)).join("")}</dd>`).join("")}</dl>`;
ui.ruleLine = html => `<div class="rule-line">${html}</div>`;
ui.proposal = o => `<div class="proposal"><b class="proposal__goal">${esc(o.goal)}</b>${o.intent ? `<span>${esc(o.intent)}</span>` : ""}
  <div class="proposal__facts">${o.metric ? ui.event(o.metric) : ""}${o.contact ? `<span>asks ${esc(o.contact)}</span>` : ""}${ui.id(o.id)}</div>
  ${o.epic ? `<div>${ui.state("epic " + o.epic, "ok")}</div>` : ui.actions(o.actions, {tight: true})}</div>`;
ui.aside = (heading, html, h = 3) => `<div class="aside"><h${h} class="aside__heading">${esc(heading)}</h${h}>${html}</div>`;
ui.trailItem = o => `<li class="trail__item"><span class="trail__glyph" aria-hidden="true">✦</span><span class="trail__words"><q>${esc(o.words)}</q>
  <span class="trail__state" data-state="${esc(o.tone)}">${o.tone === "wait" ? ui.spinner() : ""}${esc(o.text)}${o.by ? ` · ${esc(o.by)}` : ""}</span></span>
  <span class="trail__acts">${o.actions}</span></li>`;
ui.tab = o => `<button type="button" class="tab" role="tab" id="tab-${esc(o.id)}" data-tab="${esc(o.id)}" aria-selected="${!!o.on}" tabindex="${o.on || o.first ? 0 : -1}" aria-controls="main" aria-keyshortcuts="${esc(o.key)}"><span class="tab__key" aria-hidden="true">${esc(o.key)}</span>${esc(o.id)}${o.n ? `<span class="tab__n">${esc(o.n)}</span>` : ""}</button>`;
ui.step = (word, text) => `<div class="step"><b class="step__word">${esc(word)}</b>${esc(text)}</div>`;
ui.prose = text => `<div class="prose">${markdown(text)}</div>`;
ui.section = (s, h = 3) => s.kind ? ui.aside(s.heading || s.kind, ui.prose(s.text), h)
  : `${s.heading ? `<h${h}>${esc(s.heading)}</h${h}>` : ""}${ui.prose(s.text)}`;

// --- organisms
ui.card = (title, sub, body, o = {}) => `<section class="${mods("card", [o.wish && "wish", o.tight && "tight"])}"${o.label ? ` aria-label="${esc(o.label)}"` : ""}>`
  + (title || sub ? `<h2 class="card__title">${title}${sub ? ` <span class="card__sub">${sub}</span>` : ""}</h2>` : "") + `${body}</section>`;
// the one fold of the page: a button with aria-expanded over its region, its caret, kept across a redraw by its key
ui.accordion = o => {
  const open = !!o.open, id = "fold-" + slug(o.key);
  // in a fold table the head is the row's cells, on the table's columns; else a title, its meta and what stands below
  const inner = o.cells ? o.cells.map(c => `<span class="${mods("accordion__cell", [c.num && "num"])}${c.hide ? " hide-narrow" : ""}">${c.html}</span>`).join("")
    : `<span class="accordion__title">${o.head}</span>${o.meta ? `<span class="accordion__meta">${o.meta}</span>` : ""}`
      + `${o.below ? `<span class="accordion__below">${o.below}</span>` : ""}`;
  const head = `<button type="button" class="accordion__head" data-fold-toggle="${esc(o.key)}" aria-expanded="${open}" aria-controls="${id}">`
    + `${ui.caret(open)}${inner}</button>`;
  const body = open ? `<div class="accordion__body" id="${id}" role="region">${typeof o.body === "function" ? o.body() : o.body || ""}</div>` : "";
  return `<div class="${mods("accordion", [o.variant])}" data-fold="${esc(o.key)}"${open ? " data-open" : ""}>`
    + (o.level ? `<h${o.level} class="accordion__heading">${head}</h${o.level}>` : head) + `${body}</div>`;
};
// rows that fold, on shared columns: a head row of labels, each row one accordion whose cells take the columns
ui.foldTable = (cols, rows) => `<div class="fold-table" style="--fold-cols: 14px ${cols.map(c => c.num ? "max-content" : c.width || "minmax(0, 1fr)").join(" ")}">`
  + `<div class="fold-table__head" aria-hidden="true"><span></span>${cols.map(c => `<span class="${mods("fold-table__label", [c.num && "num"])}${c.hide ? " hide-narrow" : ""}">${esc(c.label)}</span>`).join("")}</div>`
  + rows.map(r => ui.accordion(Object.assign({variant: "ink"}, r, {cells: r.cells.map((html, i) => ({html, num: cols[i].num, hide: cols[i].hide}))}))).join("") + `</div>`;
ui.tabs = parts => parts.map(p => `<span class="tabs__group" role="presentation">${p.tabs.map((t, i) =>
  (i && p.ordered ? `<span class="tabs__arrow" aria-hidden="true">→</span>` : "") + ui.tab(t)).join("")}</span>`)
  .join(`<span class="tabs__sep" aria-hidden="true"></span>`);
ui.board = columns => `<div class="board">${columns.map(c => `<div class="board__slot">${c}</div>`).join("")}</div>`;
ui.column = o => `<div class="${mods("column", [o.hot && "hot"])}"><h3 class="column__head">${ui.link(o.name, {plain: true, attrs: {"data-tab": o.name}})}<span class="column__count">${esc(o.count)}${o.of != null ? `<small class="column__of"> / ${esc(o.of)}</small>` : ""}</span></h3>`
  + `<div class="column__line"${o.meterLabel ? ` role="img" aria-label="${esc(o.meterLabel)}"` : ""}>${o.meter != null ? ui.meter(o.meter, {thin: true}) : ""}${esc(o.line)}</div>`
  + (o.items || []).map(i => `<div class="column__item">${i}</div>`).join("") + ui.actions(o.actions, {foot: true}) + `</div>`;
ui.trail = items => items.length ? `<ul class="trail" aria-label="the wishes">${items.map(ui.trailItem).join("")}</ul>` : "";
ui.wish = (entry, items) => ui.card("A wish", "your words become a story, a task or a finding settled — a draft until you release it",
  entry + ui.trail(items), {wish: true});
ui.list = items => `<ul class="list">${items.map(ui.listItem).join("")}</ul>`;
ui.lane = o => `<div class="lane" data-state="${esc(o.name)}"${o.cards.length + o.more.length ? "" : " data-bare"}><h4 class="lane__head">${esc(o.label || o.name)} <span>${o.cards.length + o.more.length}</span></h4>`
  + o.cards.map(ui.storyCard).join("")
  + (o.more.length ? ui.accordion({key: o.key, variant: "quiet", head: `${o.more.length} more`, open: o.open, body: () => o.more.map(ui.storyCard).join("")}) : "") + `</div>`;
ui.lanes = lanes => `<div class="lanes">${lanes.map(ui.lane).join("")}</div>`;
ui.epic = o => ui.accordion({key: o.key, variant: "panel", open: o.open,
  head: `<b class="epic__title">${esc(o.title)}</b>${ui.id(o.id)}${o.metric ? ui.event(o.metric) : ""}`,
  meta: `${o.tone || ""}<span>${esc(o.count)}</span>`, below: ui.strip(o.strip, o.stripTitle), body: o.body});
ui.stepper = steps => `<div class="stepper">${steps.map(c => `<div class="stepper__step" data-state="${esc(c.state)}"><i class="stepper__bar"></i>${esc(c.stage)}</div>`).join("")}</div>`;
ui.course = o => `<div class="course"><div class="course__top"><div>${ui.story(o.id, o.title)}${ui.id(o.id, {block: true})}</div>
  <div class="course__right">${ui.state(o.word, o.state)}${o.right}</div></div>${(o.steps || []).length ? ui.stepper(o.steps) : ""}${o.doing ? `<div class="course__doing">${esc(o.doing)}</div>` : ""}</div>`;
ui.queue = inner => `<div class="queue">${inner}</div>`;
ui.record = o => `<section class="${mods("record", [o.accept && "accept"])}"><div class="record__question">${ui.hint(o.about)}<b class="record__text">${o.text}</b></div><div class="record__body">${o.body}</div></section>`;
ui.options = items => `<div class="options">${items.map(ui.option).join("")}</div>`;
ui.tiles = (inner, o = {}) => `<div class="${mods("tiles", [o.many && "many"])}">${inner}</div>`;
ui.days = days => `${ui.delivery({head: true})}<div class="days">${days.map(d => `<div class="days__day"><h4 class="days__date">${esc(d.day)}</h4>${d.rows.map(ui.delivery).join("")}</div>`).join("")}</div>`;
ui.domain = inner => `<div class="domain"><div class="domain__track">${inner}</div></div>`;
ui.kernel = groups => `<div class="kernel"><div class="kernel__top"><b class="kernel__title">Shared kernel</b>${ui.hint("what every context shares, the same in each — no context of its own")}</div>${ui.facts(groups)}</div>`;
ui.proposals = items => `<div class="proposals">${items.map(ui.proposal).join("")}</div>`;
ui.ruleGroup = (label, rows) => rows.length ? `<div class="rule-group">${label ? `<div class="rule-group__label">${esc(label)} <span class="rule-group__n">${rows.length}</span></div>` : ""}${rows.join("")}</div>` : "";
ui.ways = (title, ways) => ways.length ? `<div class="rule-group"><div class="rule-group__label">${esc(title)}</div>${ways.map(w =>
  `${ui.link(`${w.source} → ${w.target}`, {way: true, attrs: {"data-edge": w.key}})} ${ui.hint(w.rules)}`).join("<br>")}</div>` : "";
ui.part = (n, title, body) => body ? `<div class="part"><div class="part__head"><span class="part__n">${esc(n)}</span>${title}</div>${body}</div>` : "";
ui.flow = svg => `<div class="flow">${svg}</div>`;
ui.table = (cols, rows, o = {}) => {
  const cls = c => [c.num && "table__num", c.act && "table__act", c.hide && "hide-narrow", c.mark && "table__mark"].filter(Boolean).join(" ");
  const cell = (c, v) => `<td${cls(c) ? ` class="${cls(c)}"` : ""}>${c.act ? ui.actions(v, {end: true}) : v}</td>`;
  return `<table class="${mods("table", [o.flat && "flat"])}">${cols.some(c => c.label) ? `<tr>${cols.map(c => `<th${cls(c) ? ` class="${cls(c)}"` : ""}>${c.sr ? `<span class="sr">${esc(c.label)}</span>` : esc(c.label || "")}</th>`).join("")}</tr>` : ""}`
    + rows.map(r => `<tr>${cols.map((c, i) => cell(c, r[i] == null ? "" : r[i])).join("")}</tr>`).join("") + `</table>`;
};
ui.terminal = () => `${ui.actions(" ", {id: "follow-acts", own: true})}<pre class="terminal" id="follow-out" data-own></pre>`;
ui.curve = curve => `<div class="curve" id="curve">${curveSvg(curve)}<div class="curve__tip" id="curve-tip" hidden></div></div>`;
ui.curveTip = (c, rows) => `<b class="curve__title">${esc(c.title || c.story)}</b>${rows.map(([k, v]) => `<div class="curve__row"><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join("")}`;

// --- templates
ui.pageHead = (eyebrow, title, lede) => `<div class="page-head"><div class="page-head__eyebrow">${esc(eyebrow)}</div><h1 class="page-head__title">${esc(title)}</h1>${lede ? `<p class="page-head__lede">${esc(lede)}</p>` : ""}</div>`;
ui.drawerFrame = (close, head, body) => `<div class="drawer-frame"><div class="drawer-frame__close">${close}</div>${head}${body}</div>`;
ui.gallery = sections => `<div class="gallery">${sections.map(s => `<section class="gallery__level"><h2 class="gallery__title">${esc(s.level)}</h2>${s.items.map(([name, html]) =>
  `<div class="gallery__item"><div class="gallery__name">${esc(name)}</div><div class="gallery__show">${html}</div></div>`).join("")}</section>`).join("")}</div>`;

"""
