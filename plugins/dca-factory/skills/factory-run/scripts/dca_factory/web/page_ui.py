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
// drawn at the width it is shown at, so its words keep their size in a side column as on the width
function curveSvg(curve, width = CURVE.w) {
  const {left, right, top, panel, gap, bottom} = CURVE, w = width, h = top + panel * 2 + gap + bottom;
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
  const ticks = Math.max(2, Math.min(6, Math.floor((w - left - right) / 90))), axisY = top + panel * 2 + gap + 18;
  let named = "";                                      // a day is named once, however many ticks fall on it
  for (let i = 0; i <= ticks; i++) {
    const v = t0 + (t1 - t0) * i / ticks, day = new Date(v).toISOString().slice(5, 10);
    if (day === named) continue;
    named = day;
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
// a press: `size` s, m (the default) or l — its height a token, the same whatever it carries; `icon` a mark before the words: play or stop
ui.btn = (label, o = {}) => `<button type="button" class="${mods("btn", [o.primary && "primary", o.write && "write",
  o.danger && "danger", (o.size === "s" || o.size === "l") && o.size, o.plain && "plain", o.bar && "bar"])}"${o.title ? ` title="${esc(o.title)}"` : ""}${attrs(o.attrs)}>`
  + `${o.icon ? `<span class="btn__icon btn__icon--${esc(o.icon)}" aria-hidden="true"></span>` : ""}${esc(label)}</button>`;
ui.link = (label, o = {}) => `<button type="button" class="${mods("link", [o.title && "title", o.to && "to", o.way && "way",
  o.plain && "plain", o.quiet && "quiet", o.compact && "compact", o.ink && "ink"])}"${attrs(o.attrs)}>${o.html ? label : esc(label)}</button>`;
ui.switch = (items, o = {}) => `<span class="${mods("switch", [o.bar && "bar"])}" role="group"${o.label ? ` aria-label="${esc(o.label)}"` : ""}>${items.map(i =>
  `<button type="button" class="switch__opt" aria-pressed="${!!i.pressed}"${attrs(i.attrs)}>${esc(i.label)}${i.n != null ? `<span class="switch__n">${esc(i.n)}</span>` : ""}</button>`).join("")}</span>`;
ui.select = o => `<select class="select" id="${esc(o.id)}"${attrs(o.attrs)}>${(o.options || []).map(p =>
  `<option value="${esc(p.value)}"${p.selected ? " selected" : ""}>${esc(p.label == null ? p.value : p.label)}</option>`).join("")}</select>`;
ui.field = o => o.type === "file"
  ? `<input class="${mods("field", ["file"])}" id="${esc(o.id)}" type="file"${attrs(o.attrs)}>`
  : o.multiline
  ? `<textarea class="${mods("field", ["area"])}" id="${esc(o.id)}"${o.placeholder ? ` placeholder="${esc(o.placeholder)}"` : ""}${attrs(o.attrs)}>${esc(o.value || "")}</textarea>`
  : `<input class="${mods("field", [o.bar && "bar"])}" id="${esc(o.id)}" type="${esc(o.type || "text")}" value="${esc(o.value || "")}"${o.placeholder ? ` placeholder="${esc(o.placeholder)}"` : ""}${attrs(o.attrs)}>`;
// the one caption: what names a column, a group, a kind — small capitals in the mono face, muted or in the brand's ink
ui.caption = (text, o = {}) => `<span class="${mods("caption", [o.brand && "brand"])}">${esc(text)}</span>`;
ui.caret = open => `<svg class="caret" viewBox="0 0 12 12" aria-hidden="true"${open ? " data-open" : ""}><path d="M4.25 2.5 7.75 6l-3.5 3.5"/></svg>`;
ui.label = (text, forId, o = {}) => `<label class="${mods("label", [o.quiet && "quiet", o.bar && "bar", o.hidden && "hidden"])}" for="${esc(forId)}">${esc(text)}</label>`;
ui.hint = (text, o = {}) => `<${o.block ? "p" : "span"} class="${mods("hint", [o.block && "block", o.prose && "prose"])}"${o.id ? ` id="${esc(o.id)}"` : ""}${o.title ? ` title="${esc(o.title)}"` : ""}>${o.html ? text : esc(text)}</${o.block ? "p" : "span"}>`;
ui.error = (text, o = {}) => `<${o.block ? "p" : "span"} class="${mods("error", [o.block && "block"])}"${o.id ? ` id="${esc(o.id)}"` : ""}>✗ ${esc(text)}</${o.block ? "p" : "span"}>`;
// a word that stands out in a line — a name, a figure: its weight, face and ink the line's to set (`--em-*`)
ui.em = text => `<b class="em">${esc(text)}</b>`;
ui.term = (name, o = {}) => `<span class="${mods("term", [o.minor && "minor", o.shared && "shared"])}"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(name)}</span>`;
ui.event = (text, o = {}) => `<span class="${mods("event", [o.wrap && "wrap"])}"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(text)}</span>`;
ui.state = (word, state, o = {}) => `<span class="state" data-state="${esc(state || word)}"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(word)}</span>`;
ui.mark = m => `<span class="mark" data-state="${esc(m)}" aria-hidden="true">${esc(MARKS[m] || "")}</span>`;
ui.icon = (state, o = {}) => ICONS[state] ? `<svg class="${mods("icon", [o.large && "large"])}" data-state="${esc(state)}" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10"/>${ICONS[state]}</svg>`
  : `<svg class="icon" data-state="minor" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 10h8"/></svg>`;
ui.num = (figure, unit, o = {}) => `<span class="${mods("num", [o.lead && "lead", o.alert && "alert"])}">${esc(figure)}${unit ? `<span class="num__unit">${esc(unit)}</span>` : ""}</span>`;
ui.id = (text, o = {}) => `<${o.block ? "div" : "span"} class="${mods("id", [o.line && "line", o.block && "block"])}">${o.html ? text : esc(text)}</${o.block ? "div" : "span"}>`;
ui.dot = state => `<span class="dot" data-state="${esc(state)}"></span>`;
ui.spinner = () => `<span class="spinner" aria-hidden="true"></span>`;
ui.meter = (percent, o = {}) => `<span class="${mods("meter", [o.thin && "thin"])}"><i class="meter__fill" style="width:${Math.max(0, Math.min(100, +percent || 0))}%"></i></span>`;
ui.flag = (text, state, o = {}) => `<span class="flag" data-state="${esc(state)}"${o.title ? ` title="${esc(o.title)}"` : ""}>${esc(text)}</span>`;
ui.pill = (text, kind, o = {}) => `<span class="${mods("pill", [kind, o.line && "line"])}">${esc(text)}</span>`;
ui.empty = text => `<p class="empty">${esc(text)}</p>`;
ui.intro = (text, o = {}) => `<p class="intro">${o.html ? text : esc(text)}</p>`;
ui.note = (text, o = {}) => `<div class="note"${o.state ? ` data-state="${esc(o.state)}"` : ""}>${o.html ? text : esc(text)}</div>`;
ui.ruleId = (id, enforcement, state, refused) => `<span class="${mods("rule-id", [enforcement])}"${state ? ` data-state="${esc(state)}"` : ""}>${esc(id)}${refused ? `<span class="rule-id__refused">×${esc(refused)}</span>` : ""}</span>`;

// one file beside the words: its name, its size or what became of it, a way to take it back; a picture as a preview
const kb = n => n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
ui.fileChip = (f, key) => `<li class="${mods("file-chip", [f.busy && "busy", f.error && "error"])}"${f.error ? ` title="${esc(f.error)}"` : ""}>${f.preview ? `<img class="file-chip__preview" src="${esc(f.preview)}" alt="">` : `<span class="file-chip__kind" aria-hidden="true">${esc((f.name.split(".").pop() || "").toUpperCase())}</span>`}`
  + `<span class="file-chip__name">${esc(f.name)}</span><span class="file-chip__size">${esc(f.error ? "not taken" : f.busy ? "handing over…" : kb(f.size))}</span>`
  + `<button type="button" class="file-chip__drop" aria-label="take ${esc(f.name)} back" data-unhand="${esc(key)}" data-file="${esc(f.key)}">×</button></li>`;
// a picture a stage took of what it built: the picture, opened large in a tab of its own, and who took it when
ui.shot = o => `<figure class="shot"><a class="shot__open" href="${esc(o.href)}" target="_blank" rel="noopener">`
  + `<img class="shot__picture" src="${esc(o.href)}" alt="${esc(o.alt || o.name)}" loading="lazy"></a>`
  + `<figcaption class="shot__said">${o.stage ? `<b>${esc(o.stage)}</b> · ` : ""}${esc(o.name)}${o.at ? ` · ${esc(o.at)}` : ""}</figcaption></figure>`;
// --- molecules
ui.story = (id, title, o = {}) => ui.link(title || id, {title: true, compact: o.compact, ink: o.ink, attrs: {"data-story": id}});
// the only way a field is set: its label, the field, what it takes and what was wrong — tied by for, id and describedby
ui.formRow = o => {
  const hintId = o.hint ? `${o.id}-hint` : "", errorId = o.error ? `${o.id}-error` : "";
  const described = [hintId, errorId].filter(Boolean).join(" ");
  const own = Object.assign({}, o.attrs, described ? {"aria-describedby": described} : {}, o.error ? {"aria-invalid": "true"} : {});
  const field = o.options ? ui.select({id: o.id, options: o.options, attrs: own})
    : ui.field({id: o.id, multiline: o.multiline, value: o.value, type: o.type, bar: o.bar, placeholder: o.placeholder, attrs: own});
  return `<div class="${mods("form-row", [o.inline && "inline", o.bar && "bar"])}">${ui.label(o.label, o.id, {quiet: o.quiet, hidden: o.labelHidden})}${field}`
    + (o.hint ? ui.hint(o.hint, {id: hintId}) : "") + (o.error ? ui.error(o.error, {id: errorId}) : "") + `</div>`;
};
// the person's words for an action: the field, an optional why, the button — kept by its draft until written
// the words a person gives, with the files beside them (WP-184): a picture, a PDF, a text — chosen or dropped on the field
ui.ask = o => `<div class="ask" data-ask="${esc(o.id)}" data-hand="${esc(o.draft || o.id)}">`
  + ui.formRow({id: `ask-${slug(o.draft || o.id)}`, label: o.label, labelHidden: !!o.text, placeholder: o.text, multiline: true, value: o.value, attrs: {"data-draft": o.draft || o.id}})
  + ui.files(o.files || [], o.draft || o.id)
  + ((o.choices || []).length ? ui.formRow({id: `why-${slug(o.draft || o.id)}`, label: "why? (optional)", quiet: true, attrs: {"data-ask-why": ""},
      options: [{value: "", label: "—"}, ...o.choices.map(c => ({value: c}))]}) : "")
  + `<div class="ask__go">${ui.btn(o.label, {primary: o.primary, write: o.write, title: o.title, attrs: {"data-press": o.id}})}${ui.attach(o.draft || o.id)}${o.also || ""}</div></div>`;
// a quiet press that opens the file picker; the picker itself, a field, stays hidden
const HANDED_KINDS = "image/png,image/jpeg,image/gif,image/webp,application/pdf,.txt,.md,.csv,.json";
ui.attach = key => ui.btn("+ file", {title: "a picture, a PDF or a text — at most 5, 10 MB each", attrs: {"data-attach": key}})
  + ui.field({id: `pick-${slug(key)}`, type: "file", attrs: {multiple: true, accept: HANDED_KINDS, hidden: true, "aria-label": "files beside the words", "data-attach-input": key}});
// the files chosen for one entry, a chip each
ui.files = (files, key) => files.length ? `<ul class="files" aria-label="files beside the words">${files.map(f => ui.fileChip(f, key)).join("")}</ul>` : "";
// a button that opens a panel beneath it, the panel's words the page's — Escape or a click beside it closes it
ui.menu = o => `<div class="${mods("menu", [o.bar && "bar", o.flush && "flush"])}" data-menu-box="${esc(o.id)}">`
  + `<button type="button" class="menu__toggle" aria-expanded="${!!o.open}" aria-controls="menu-${esc(o.id)}" data-menu="${esc(o.id)}"${o.title ? ` title="${esc(o.title)}"` : ""}>`
  + `${o.label}<span class="menu__chev" aria-hidden="true">▾</span></button>`
  + `<div class="menu__panel" id="menu-${esc(o.id)}"${o.open ? "" : " hidden"}>${o.body}</div></div>`;
ui.actions = (inner, o = {}) => inner ? `<div class="${mods("actions", [o.end && "end", o.tight && "tight", o.foot && "foot", o.indent && "indent"])}"${o.id ? ` id="${esc(o.id)}"` : ""}${o.own ? " data-own" : ""}>${inner}</div>` : "";
ui.tile = (figure, label, o = {}) => `<div class="${mods("tile", [o.lead && "lead", o.bad && "alert"])}"${o.title ? ` title="${esc(o.title)}"` : ""}>${ui.num(figure, "", {lead: o.lead, alert: o.bad})}${ui.caption(label)}${o.said ? `<small class="tile__said">${esc(o.said)}</small>` : ""}</div>`;
ui.kv = pairs => `<dl class="kv">${pairs.filter(Boolean).map(([k, v]) => `<dt class="kv__key">${esc(k)}</dt><dd class="kv__value">${v}</dd>`).join("")}</dl>`;
ui.toast = (text, isError) => `<div class="${mods("toast", [isError && "error"])}" role="status">${esc(text)}</div>`;
ui.legend = items => `<ul class="legend">${items.map(([state, label]) => `<li class="legend__item"><i class="legend__key" data-state="${esc(state)}"></i>${esc(label)}</li>`).join("")}</ul>`;
ui.strip = (states, title) => `<span class="strip" role="img" aria-label="${esc(title)}" title="${esc(title)}">${states.map(s => `<i class="strip__seg" data-state="${esc(s)}"></i>`).join("")}</span>`;
ui.said = (keyword, html, o = {}) => `<p class="said"${o.state ? ` data-state="${esc(o.state)}"` : ""}>${keyword || o.icon ? `<span class="said__kw">${o.icon ? ui.icon(o.icon) + " " : ""}${esc(keyword)}</span> ` : ""}${html}${o.goes ? ` <span class="said__goes">${esc(o.goes)}</span>` : ""}</p>`;
ui.figures = items => `<div class="figures">${items.filter(Boolean).map(([label, value, bad]) => `<span class="figures__item">${esc(label)} <b class="${mods("figures__value", [bad && "alert"])}">${value}</b></span>`).join("")}</div>`;
ui.bars = rows => `<div class="bars">${rows.map(([label, n, percent]) => `<span class="bars__label">${esc(label)}</span>${ui.meter(percent)}<span class="bars__n">${esc(n)}</span>`).join("")}</div>`;
ui.toolbar = inner => `<div class="toolbar">${inner}</div>`;
ui.quietLine = html => `<p class="quiet-line">${html}</p>`;
ui.notice = (html, o = {}) => `<div class="${mods("notice", [o.ended && "ended"])}"><div class="notice__text"><span class="notice__arrow">${o.ended ? "!" : "→"}</span>${html}</div>${o.action || ""}</div>`;
ui.storyCard = o => `<li class="story-card" data-state="${esc(o.state)}">${ui.story(o.id, o.title, {compact: true})}${ui.id(o.line, {block: true})}${ui.actions(o.actions, {tight: true})}</li>`;
ui.ticket = o => `<li class="ticket"><div class="ticket__what"><b class="ticket__kind">${esc(o.kind)}</b>${o.target ? `<span>${esc(o.target)}</span>` : ""}${o.words ? `<span>${esc(o.words)}</span>` : ""}${ui.state(o.word, o.state)}</div>`
  + (o.id ? ui.id(o.id, {block: true}) : "") + (o.error ? ui.error(o.error, {block: true}) : "") + (o.note ? ui.note(o.note, {html: true, state: "wait"}) : "")
  + ui.actions(o.actions, {tight: true}) + `</li>`;
ui.option = o => `<li class="${mods("option", [o.advised && "advised"])}"><div class="option__pick">${o.pick}</div>${o.advised ? `${ui.caption("recommended", {brand: true})}` : ""}<span class="option__text">${o.text}</span></li>`;
ui.listItem = o => `<li class="${mods("list__item", [o.press && "press"])}"${o.on ? ' aria-current="true"' : ""}>${o.mark ? ui.mark(o.mark) : ""}<span class="list__what">${o.press ? `<button type="button" class="list__press"${attrs(o.press.attrs)}>${esc(o.press.label)}</button>` : ""}${o.what || ""}</span>${o.aside ? `<span class="list__aside">${o.aside}</span>` : ""}</li>`;
ui.delivery = o => o.head
  ? `<div class="${mods("delivery", ["head"])}" aria-hidden="true">${["at", "story", "epic", "outcome event", "time", "tokens", "cost"].map((label, i) =>
      `<span class="${mods("delivery__label", [i > 3 && "num"])}${i === 2 || i === 5 ? " hide-narrow" : ""}">${ui.caption(label)}</span>`).join("")}</div>`
  : `<div class="delivery"><div class="delivery__at">${esc(o.at)}</div><div class="delivery__what">${ui.story(o.story, o.title)}</div>
  <div class="delivery__epic" title="${esc(o.epic)}">${esc(o.epic)}</div><div class="delivery__event">${o.event ? ui.event(o.event, {title: o.event}) : ""}</div>
  <div class="delivery__fig">${esc(o.seconds || "")}</div><div class="delivery__fig delivery__fig--tokens hide-narrow">${esc(o.tokens || "")}</div><div class="delivery__fig">${esc(o.cost || "")}</div></div>`;
ui.domainNode = (title, hint) => `<h3 class="domain-node"><span class="domain-node__dot" aria-hidden="true"></span>${esc(title)}${hint ? ` ${ui.hint(hint, {prose: true})}` : ""}</h3>`;
ui.facts = groups => `<dl class="facts">${groups.map(g => `<dt class="facts__kind">${ui.caption(g.kind)}</dt><dd class="facts__terms">${g.terms.map(t => ui.term(t.name, t)).join("")}</dd>`).join("")}</dl>`;
ui.proposal = o => `<li class="proposal"><b class="proposal__goal">${esc(o.goal)}</b>${o.intent ? `<span>${esc(o.intent)}</span>` : ""}
  <div class="proposal__facts">${o.metric ? ui.event(o.metric, {wrap: true}) : ""}${o.contact ? `<span>asks ${esc(o.contact)}</span>` : ""}${ui.id(o.id)}</div>
  ${o.epic ? `<div>${ui.state("epic " + o.epic, "ok")}</div>` : ui.actions(o.actions, {tight: true})}</li>`;
ui.aside = (heading, html, h = 3) => `<div class="aside"><h${h} class="aside__heading">${esc(heading)}</h${h}>${html}</div>`;
ui.trailItem = o => `<li class="trail__item"><span class="trail__glyph" aria-hidden="true">✦</span><span class="trail__words"><q class="trail__quote">${esc(o.words)}</q>
  <span class="trail__state" data-state="${esc(o.tone)}">${o.tone === "wait" ? ui.spinner() : ""}${esc(o.text)}${o.by ? ` · ${esc(o.by)}` : ""}</span></span>
  <span class="trail__acts">${o.actions}</span></li>`;
ui.tab = o => `<button type="button" class="tab" role="tab" id="tab-${esc(o.id)}" data-tab="${esc(o.id)}" aria-selected="${!!o.on}" tabindex="${o.on || o.first ? 0 : -1}" aria-controls="main" aria-keyshortcuts="${esc(o.key)}"><span class="tab__key" aria-hidden="true">${esc(o.key)}</span>${esc(o.id)}${o.n ? `<span class="tab__n">${esc(o.n)}</span>` : ""}</button>`;
ui.step = (word, text) => `<div class="step"><b class="step__word">${esc(word)}</b>${esc(text)}</div>`;
// `base`: the file the markdown stands in, which a picture's or a link's path is beside
ui.prose = (text, base = "") => `<div class="prose">${markdown(text, base)}</div>`;
ui.section = (s, h = 3, base = "") => s.kind ? ui.aside(s.heading || s.kind, ui.prose(s.text, base), h)
  : `${s.heading ? `<h${h}>${esc(s.heading)}</h${h}>` : ""}${ui.prose(s.text, base)}`;

// a story's pictures side by side, as many to a row as its column holds
ui.shots = list => `<div class="shots">${list.map(ui.shot).join("")}</div>`;
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
  return `<div class="${mods("accordion", [o.variant, o.cells && "cells"])}" data-fold="${esc(o.key)}"${open ? " data-open" : ""}>`
    + (o.level ? `<h${o.level} class="accordion__heading">${head}</h${o.level}>` : head) + `${body}</div>`;
};
// rows that fold, on shared columns: a head row of labels, each row one accordion whose cells take the columns
ui.foldTable = (cols, rows) => `<div class="fold-table" style="--fold-cols: calc(var(--space-2) + 14px) ${cols.map(c => c.num ? "max-content" : c.width || "minmax(0, 1fr)").join(" ")}">`
  + `<div class="fold-table__head" aria-hidden="true"><span></span>${cols.map(c => `<span class="${mods("fold-table__label", [c.num && "num"])}${c.hide ? " hide-narrow" : ""}">${ui.caption(c.label)}</span>`).join("")}</div>`
  + rows.map(r => ui.accordion(Object.assign({variant: "ink"}, r, {cells: r.cells.map((html, i) => ({html, num: cols[i].num, hide: cols[i].hide}))}))).join("") + `</div>`;
ui.tabs = parts => parts.map(p => `<span class="tabs__group" role="presentation">${p.tabs.map((t, i) =>
  (i && p.ordered ? `<span class="tabs__arrow" aria-hidden="true">→</span>` : "") + ui.tab(t)).join("")}</span>`)
  .join(`<span class="tabs__sep" aria-hidden="true"></span>`);
// the tabs in their bar, where they stand apart from the frame — the pattern library's
ui.tabBar = parts => `<nav class="tabs" aria-label="tabs">${ui.tabs(parts)}</nav>`;
ui.board = columns => `<div class="board">${columns.map(c => `<div class="board__slot">${c}</div>`).join("")}</div>`;
ui.column = o => `<section class="${mods("column", [o.hot && "hot"])}"><h2 class="column__head">${ui.link(o.name, {plain: true, attrs: {"data-tab": o.name}})}<span class="column__count">${esc(o.count)}${o.of != null ? `<small class="column__of"> / ${esc(o.of)}</small>` : ""}</span></h2>`
  + `<div class="column__line"${o.meterLabel ? ` role="img" aria-label="${esc(o.meterLabel)}"` : ""}>${o.meter != null ? ui.meter(o.meter, {thin: true}) : ""}${esc(o.line)}</div>`
  + (o.items || []).map(i => `<div class="column__item">${i}</div>`).join("") + ui.actions(o.actions, {foot: true}) + `</section>`;
ui.trail = items => items.length ? `<ul class="trail" aria-label="the wishes">${items.map(ui.trailItem).join("")}</ul>` : "";
ui.wish = (entry, items) => ui.card("A wish", "your words become a story, a task or a finding settled — a draft until you release it",
  entry + ui.trail(items), {wish: true});
ui.list = items => `<ul class="list">${items.map(ui.listItem).join("")}</ul>`;
ui.lane = o => `<section class="lane" data-state="${esc(o.name)}"${o.cards.length + o.more.length ? "" : " data-bare"}><h4 class="lane__head">${ui.caption(o.label || o.name)}${ui.caption(String(o.cards.length + o.more.length))}</h4>`
  + (o.cards.length ? `<ul class="lane__cards">${o.cards.map(ui.storyCard).join("")}</ul>` : "")
  + (o.more.length ? ui.accordion({key: o.key, variant: "quiet", head: `${o.more.length} more`, open: o.open, body: () => `<ul class="lane__cards">${o.more.map(ui.storyCard).join("")}</ul>`}) : "") + `</section>`;
ui.lanes = lanes => `<div class="lanes">${lanes.map(ui.lane).join("")}</div>`;
ui.epic = o => ui.accordion({key: o.key, variant: "panel", open: o.open, level: 3,
  head: `${ui.em(o.title)}${ui.id(o.id)}${o.metric ? ui.event(o.metric) : ""}`,
  meta: `${o.tone || ""}<span>${esc(o.count)}</span>`, below: ui.strip(o.strip, o.stripTitle), body: o.body});
ui.stepper = steps => `<div class="stepper">${steps.map(c => `<div class="stepper__step" data-state="${esc(c.state)}"><i class="stepper__bar"></i>${esc(c.stage)}</div>`).join("")}</div>`;
ui.course = o => `<div class="course"><div class="course__top"><div><div class="course__title">${ui.story(o.id, o.title)}${ui.state(o.word, o.state)}</div>${o.title ? ui.id(o.id, {block: true}) : ""}</div>
  <div class="course__right">${o.right}</div></div>${(o.steps || []).length ? ui.stepper(o.steps) : ""}${o.doing ? `<div class="course__doing">${esc(o.doing)}</div>` : ""}</div>`;
// what the factory runs, opened from its control: each story in flight with its course, then the lines that follow
ui.runPanel = o => {
  const story = r => `<div class="run-panel__story"><div class="run-panel__head">${ui.story(r.id, r.title || r.id, {compact: true})}${ui.hint(r.word)}</div>`
    + ((r.steps || []).length ? ui.stepper(r.steps) : "") + (r.doing ? ui.hint(r.doing) : "") + `</div>`;
  return `<div class="run-panel">${(o.runs || []).map(story).join("")}`
    + (o.idle ? `<p class="run-panel__line">${esc(o.idle)}</p>` : "")
    + (o.lines || []).map(l => `<p class="run-panel__line">${l}</p>`).join("") + ui.actions(o.acts) + `</div>`;
};
// the factory's run, from every page: its dot and a word on what it does, the one action beside — the panel the rest
ui.runControl = o => `<div class="run-control" data-state="${esc(o.state)}">`
  + ui.menu({id: "run", bar: true, flush: true, open: o.open, title: o.title,
             label: `${ui.dot(o.state)}<span class="run-control__say">${o.say}</span>`, body: o.panel})
  + (o.act || "") + `</div>`;
// a story's stages as a track: each with its figures and its share of the time — done, the one now, or where it stopped
ui.track = stages => `<ol class="track">${stages.map(s => `<li class="track__stage" data-state="${esc(s.state || "")}">`
  + `<b class="track__name">${esc(s.name)}${{done: " ✓", stopped: " ✗", now: " ▶"}[s.state] || ""}</b>`
  + (s.lines || []).map(l => `<span class="track__line">${l}</span>`).join("") + (s.share != null ? ui.meter(s.share, {thin: true}) : "") + `</li>`).join("")}</ol>`;
// a text of sections — a story's words, its scenarios —: its headings in the page's faces and on its rhythm
ui.document = (html, o = {}) => `<div class="${mods("document", [o.compact && "compact"])}">${html}</div>`;
ui.queue = inner => `<ul class="queue">${inner}</ul>`;
ui.record = o => `<section class="${mods("record", [o.accept && "accept"])}"><div class="record__question">${ui.hint(o.about)}<h2 class="record__text">${o.text}</h2></div><div class="record__body">${o.body}</div></section>`;
ui.options = items => `<ul class="options">${items.map(ui.option).join("")}</ul>`;
ui.tiles = (inner, o = {}) => `<div class="${mods("tiles", [o.many && "many"])}">${inner}</div>`;
ui.days = days => `<div class="days"><div class="days__head">${ui.delivery({head: true})}</div><div class="days__track">${days.map(d => `<div class="days__day"><h3 class="days__date">${ui.caption(d.day)}</h3>${d.rows.map(ui.delivery).join("")}</div>`).join("")}</div></div>`;
ui.domain = inner => `<div class="domain"><div class="domain__track">${inner}</div></div>`;
ui.kernel = groups => `<div class="kernel"><div class="kernel__top"><h3 class="kernel__title">Shared kernel</h3>${ui.hint("what every context shares, the same in each — no context of its own")}</div>${ui.facts(groups)}</div>`;
ui.proposals = items => `<ul class="proposals">${items.map(ui.proposal).join("")}</ul>`;
ui.ruleGroup = (label, rows, o = {}) => rows.length ? `<div class="rule-group">${label ? `<div class="rule-group__label">${o.plain ? ui.hint(label, {prose: true}) : `${ui.caption(label)} <span class="rule-group__n">${rows.length}</span>`}</div>` : ""}<ul class="rule-group__rows">${rows.map(r => `<li class="rule-group__row">${r}</li>`).join("")}</ul></div>` : "";
// a rule with the scenarios it holds: the rule a heading, its scenarios a list beneath it, one block per rule
ui.ruleBlock = (rule, rows) => `<section class="rule-block">${rule ? `<h4 class="rule-block__rule">${ui.caption("Rule", {brand: true})} ${rule}</h4>` : ""}`
  + `<ul class="rule-block__rows">${rows.map(r => `<li>${r}</li>`).join("")}</ul></section>`;
ui.ways = (title, ways, o = {}) => ways.length ? `<div class="rule-group">${title ? `<div class="rule-group__label">${o.plain ? ui.hint(title, {prose: true}) : ui.caption(title)}</div>` : ""}<ul class="ways">${ways.map(w =>
  `<li class="ways__row">${ui.link(`${w.source} → ${w.target}`, {way: true, attrs: {"data-edge": w.key}})}<span class="ways__rules">${esc(w.rules)}</span></li>`).join("")}</ul></div>` : "";
ui.part = (title, body, o = {}) => body ? `<section class="${mods("part", [o.aside && "aside"])}"><h${o.level || 3} class="part__head">${title}</h${o.level || 3}>${body}</section>` : "";
// how a check ends: a mark in the state's colour, where the story goes in plain words, what happens then beneath
ui.outcome = (state, head, body) => `<section class="outcome" data-state="${esc(state)}"><h4 class="outcome__head">${ui.icon(state, {large: true})}<span>${head}</span></h4>${body ? `<div class="outcome__body">${body}</div>` : ""}</section>`;
ui.flow = svg => `<div class="flow">${svg}</div>`;
ui.table = (cols, rows, o = {}) => {
  const cls = c => [c.num && "table__num", c.act && "table__act", c.hide && "hide-narrow", c.mark && "table__mark"].filter(Boolean).join(" ");
  const cell = (c, v) => `<td class="table__cell ${cls(c)}">${c.act ? ui.actions(v, {end: true}) : v}</td>`;
  return `<table class="${mods("table", [o.flat && "flat", cols.some(c => c.act) && "acts"])}">${cols.some(c => c.label) ? `<tr class="table__row table__row--head">${cols.map(c => `<th class="table__label ${cls(c)}">${c.sr ? `<span class="sr">${esc(c.label)}</span>` : esc(c.label || "")}</th>`).join("")}</tr>` : ""}`
    + rows.map(r => `<tr class="table__row">${cols.map((c, i) => cell(c, r[i] == null ? "" : r[i])).join("")}</tr>`).join("") + `</table>`;
};
ui.terminal = () => `${ui.actions(" ", {id: "follow-acts", own: true})}<pre class="terminal" id="follow-out" data-own></pre>`;
ui.curve = (curve, o = {}) => `<div class="curve" id="curve">${curveSvg(curve, o.w)}<div class="curve__tip" id="curve-tip" hidden></div></div>`;
ui.curveTip = (c, rows) => `<div class="curve-tip"><b class="curve-tip__title">${esc(c.title || c.story)}</b>`
  + rows.map(([k, v]) => `<div class="curve-tip__row"><span class="curve-tip__key">${esc(k)}</span><span class="curve-tip__value">${esc(v)}</span></div>`).join("") + `</div>`;

// --- templates
ui.pageHead = (eyebrow, title, lede) => `<div class="page-head"><div class="page-head__eyebrow">${esc(eyebrow)}</div><h1 class="page-head__title">${esc(title)}</h1>${lede ? `<p class="page-head__lede">${esc(lede)}</p>` : ""}</div>`;
// a wide window in two columns, never half and half (WP-183) — below the wide width each stacks as one column
// content and the column beside it: what belongs to the content, on 4 of the 12 columns
// side-first: stacked on a narrower window, what is beside the content comes before it — a summary over its detail
ui.split = o => `<div class="${mods("split", [o.sideFirst && "side-first"])}"><div class="split__main">${o.main}</div><div class="split__side">${o.side}</div></div>`;
// a list beside the item opened from it; without one the list takes the width
ui.master = o => `<div class="${mods("master", [o.narrowList && "narrow-list", o.bare && "bare"])}"${o.detail ? " data-open" : ""}><div class="master__list">${o.list}</div>`
  + (o.detail ? `<section class="master__detail" aria-label="${esc(o.label || "opened")}">${o.detail}</section>` : "") + `</div>`;
// a document read as one: its sections beside it, the text at a reading measure
ui.reader = o => `<div class="reader"><nav class="reader__toc" aria-label="${esc(o.label || "sections")}">${o.head || ""}<ol class="reader__sections">`
  + (o.sections || []).map(s => `<li><button type="button" class="reader__goto" data-goto="${esc(s.id)}">${esc(s.heading)}</button></li>`).join("")
  + `</ol></nav><article class="reader__text">${(o.sections || []).map(s => `<section class="reader__part" id="${esc(s.id)}">`
    + `<h2 class="reader__heading">${esc(s.heading)}</h2>${s.aside ? `<div class="reader__aside">${s.aside}</div>` : ""}`
    + `<div class="reader__body">${s.body}</div></section>`).join("")}</article></div>`;
ui.drawerFrame = (close, head, body) => `<div class="drawer-frame"><div class="drawer-frame__close">${close}</div>${head}${body}</div>`;
// the items the library shows as a list, where the page holds them in a component's own list
ui.galleryList = html => `<ul class="gallery__list">${html}</ul>`;
ui.gallery = sections => `<div class="gallery">${sections.map(s => `<section class="gallery__level"><h2 class="gallery__title">${esc(s.level)}</h2>${s.items.map(([name, html]) =>
  `<div class="gallery__item"><h3 class="gallery__name">${esc(name)}</h3><div class="gallery__show">${html}</div></div>`).join("")}</section>`).join("")}</div>`;

"""
