"""The page's stylesheet (WP-180), by level: the base and the frame, then atoms, molecules, organisms, templates.

Every class is a BEM block of a component in `page_ui.py` (or of the page's frame, `FRAME_BLOCKS`), an element of one
(`block__element`) or a variant (`block--variant`); a state the factory names is selected as `[data-state="…"]`, never
as a class. Colours come from the tokens alone (`page_tokens.py`) — no colour is written here as a value. The rules
under `.flow` select the drawing the factory makes of a flow: its classes are that drawing's, not the page's.
"""

#: The blocks of the page's frame — the bar, the main region, the drawer — written in the page itself, not by a
#: component; and the few utilities a component may add beside its block.
FRAME_BLOCKS = ("topbar", "brand", "tabs", "status", "banner", "main", "toasts", "drawer", "wrap", "sr", "hide-narrow")

STYLE = """
/* === base ===================================================================================================== */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font: 17px/1.55 var(--body); min-height: 100vh; }
a { color: var(--brand-text); text-decoration: none; }
button:focus-visible, a:focus-visible, textarea:focus-visible, select:focus-visible, input:focus-visible {
  outline: 3px solid var(--brand); outline-offset: 2px; border-radius: 4px; }
code { font-family: var(--mono); font-size: .78em; background: var(--code); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }
h3 { font: 600 15px var(--display); margin: 18px 0 6px; }
table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 16px; }
th { text-align: left; font: 500 11.5px var(--mono); letter-spacing: 1.2px; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding: 6px 8px; }
td { border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 0 24px; }
.sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }

/* a state the factory names, as the one tone every display of it takes — and the palette by its own names */
[data-state="success"] { --tone: var(--success); } [data-state="warning"] { --tone: var(--warning); }
[data-state="danger"] { --tone: var(--danger); } [data-state="info"] { --tone: var(--info); }
[data-state="ok"], [data-state="done"], [data-state="delivered"], [data-state="adds"] { --tone: var(--ok); }
[data-state="wait"], [data-state="waiting"], [data-state="running"], [data-state="ask"], [data-state="look"], [data-state="question"],
[data-state="changes"], [data-state="now"], [data-state="hot"] { --tone: var(--wait); }
[data-state="bad"], [data-state="stopped"], [data-state="failed"], [data-state="interrupted"], [data-state="gone"] { --tone: var(--stop); }
/* a gate's verdict: its own pair, apart from the brand and from a story's state */
[data-state="pass"] { --tone: var(--pass); }
[data-state="fail"] { --tone: var(--fail); }
[data-state="queued"], [data-state="approved"] { --tone: var(--info); }

/* === the frame: the bar, the main region, the drawer ========================================================== */
.topbar { position: sticky; top: 0; z-index: 20; background: var(--bar); color: var(--bar-ink); border-bottom: 1px solid var(--bar-rule); }
.topbar__nav { display: flex; align-items: center; gap: 18px; padding: 12px 0; flex-wrap: wrap; }
.brand { display: flex; align-items: center; gap: 1ex; font: 700 19px var(--display); letter-spacing: -.3px; color: var(--bar-ink);
  text-decoration: none; border-radius: 6px; padding: 2px 6px; margin: -2px -6px; }
.brand:hover .brand__name { color: var(--brand); }
.brand:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.brand__logo { display: inline-block; width: 2.13ex; height: 2.4ex; transform: translateY(.1ex); }
.brand__logo svg { display: block; width: 100%; height: 100%; overflow: visible; }
:root[data-logo] .brand__logo { width: var(--logo-width); background: var(--logo) left center / contain no-repeat; }
:root[data-logo] .brand__logo svg { display: none; }
.brand__dot { color: var(--brand); }
.brand__project { font: 400 13px var(--mono); color: var(--bar-dim); letter-spacing: .3px; margin-left: 4px; }
.tabs { display: flex; align-items: center; gap: 4px; margin-left: auto; overflow-x: auto; scrollbar-width: none; }
.tabs__group { display: flex; align-items: center; }
.tabs__sep { flex: none; width: 1px; height: 16px; margin: 0 8px; background: var(--bar-faint); }
.tabs__arrow { color: var(--bar-faint); font: 400 12px var(--mono); }
.status { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font: 400 13px var(--mono); color: var(--bar-text); }
.banner { background: var(--bar); color: var(--bar-ink); border-bottom: 3px solid var(--stop); font: 500 14px var(--display); padding: 8px 0; }
.main { padding-top: 40px; padding-bottom: 72px; }
.toasts { position: fixed; right: 16px; bottom: 16px; z-index: 40; display: flex; flex-direction: column; gap: 8px; max-width: min(440px, calc(100% - 32px)); }
.drawer { position: fixed; inset: var(--bar-height, 0px) 0 0 auto; width: min(760px, 100%); z-index: 15; background: var(--paper);
  border-left: 1px solid var(--line); box-shadow: var(--shadow); overflow-y: auto; padding: 24px; }

/* === atoms ==================================================================================================== */
/* a control is pressed, a display is read: a control is a raised rectangle in the display face, a display flat, in the
   mono face, never with an edge — the accent alone tells neither (the brand's controls and displays) */
.btn { font: 600 14px var(--display); padding: 7px 14px; border-radius: 7px; border: 1px solid var(--line); background: var(--panel);
  color: var(--ink); cursor: pointer; white-space: nowrap; box-shadow: var(--lift); }
.btn:active:not(:disabled) { transform: translateY(1px); box-shadow: none; }
.btn:hover { border-color: var(--brand); color: var(--brand-text); }
.btn:disabled { opacity: .5; cursor: default; }
.btn--primary { background: var(--brand-fill); border-color: var(--brand-fill); color: var(--brand-ink);
  box-shadow: 0 1px 0 var(--brand-fill-hover), 0 2px 6px color-mix(in srgb, var(--brand) 30%, transparent); }
.btn--primary::after { content: "→"; font-weight: 400; margin-left: 6px; }
.btn--primary:hover { background: var(--brand-fill-hover); border-color: var(--brand-fill-hover); color: var(--brand-ink); }
.btn--plain::after { content: none; }
.btn--write::before { content: "✦"; color: var(--brand-text); margin-right: 6px; font-weight: 400; }
.btn--primary.btn--write::before { color: var(--brand-ink); }
.btn--danger:hover { border-color: var(--stop); color: var(--stop); }
.btn--small { font-size: 12.5px; padding: 4px 9px; }
.btn--bar { font: 500 13px var(--display); color: var(--bar-ink); background: none; border-color: var(--bar-faint); box-shadow: none; padding: 5px 12px; border-radius: 6px; }
.btn--bar:hover { border-color: var(--brand); color: var(--brand); }
.btn--bar.btn--primary { background: var(--brand-fill); border-color: var(--brand-fill); color: var(--brand-ink); }
.link { background: none; border: 0; padding: 0; text-align: left; font: inherit; color: var(--brand-text); cursor: pointer;
  text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px;
  text-decoration-color: color-mix(in srgb, var(--brand-text) 45%, transparent); }
.link:hover { text-decoration-color: currentColor; }
.link--title { font: 500 16.5px var(--display); text-decoration: none; }
.link--title:hover { text-decoration: underline; }
.link--to { display: inline-block; margin-top: 12px; font: 500 13px var(--mono); text-decoration: none; }
.link--way { font: 500 13px var(--mono); padding: 2px 0; }
.link--plain { font: inherit; color: inherit; text-decoration: none; }
.link--plain:hover { color: var(--brand-text); }
.switch { display: inline-flex; border: 1px solid var(--line); border-radius: 7px; overflow: hidden; background: var(--panel); }
.switch__opt { font: 500 13px var(--display); color: var(--ink); background: none; border: 0; padding: 5px 11px; cursor: pointer; white-space: nowrap; }
.switch__opt + .switch__opt { border-left: 1px solid var(--line); }
.switch__opt:hover { color: var(--brand-text); }
.switch__opt[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
.switch__n { font: 400 11px var(--mono); margin-left: 4px; opacity: .7; }
.switch--bar { background: none; border-color: var(--bar-faint); border-radius: 6px; }
.switch--bar .switch__opt { font: 400 12px var(--mono); color: var(--bar-dim); padding: 4px 8px; }
.switch--bar .switch__opt + .switch__opt { border-left-color: var(--bar-faint); }
.switch--bar .switch__opt[aria-pressed="true"] { background: var(--bar-rule); color: var(--bar-ink); }
.select { font: 400 13px var(--mono); color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 7px 8px; }
.field { font: 400 14px var(--mono); color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; width: 100%; }
.field--area { min-height: 72px; resize: vertical; font: 17px/1.5 var(--body); padding: 10px 12px; }
.field[aria-invalid="true"] { border-color: var(--stop); }
.field--bar { font: 400 13px var(--mono); color: var(--bar-ink); background: var(--bar-rule); border-color: var(--bar-faint); border-radius: 6px; padding: 4px 8px; width: 170px; }
.caret { color: var(--muted); font: 400 12px var(--mono); }
.label { display: block; font: 600 14px var(--display); color: var(--ink); margin-bottom: 4px; }
.label--quiet { font: 400 12.5px var(--mono); color: var(--muted); }
.hint { font: 400 12.5px var(--mono); color: var(--muted); }
.hint--block { display: block; margin: 6px 0; font: 400 14px var(--body); }
.error { display: inline-block; font: 400 14px var(--body); color: var(--stop); }
p.error { display: block; margin: 6px 0; }
.term { font: 500 12px var(--mono); padding: 2px 8px; border-radius: 3px; background: var(--tint); color: var(--brand-text); white-space: nowrap; cursor: help; }
.term--minor { background: transparent; box-shadow: inset 0 0 0 1px var(--brand); }
/* a term of the shared kernel, in a context or in the kernel's own block: never a context's accent */
.term--shared { background: color-mix(in srgb, var(--shared) 14%, transparent); color: var(--shared); }
.term--shared::before { content: "⇄ "; font-size: 10px; }
.event { font: 500 12px var(--mono); padding: 1px 9px 1px 7px; border-radius: 999px; background: var(--tint); color: var(--brand-text); white-space: nowrap; }
.event::before { content: "◆"; font-size: 8.5px; margin-right: 5px; vertical-align: 1px; }
.state { font: 600 10.5px var(--mono); letter-spacing: .07em; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; white-space: nowrap;
  color: var(--tone, var(--muted)); background: color-mix(in srgb, var(--tone, var(--muted)) 14%, transparent); }
.mark { font: 700 15px var(--display); display: inline-block; width: 1.3em; text-align: center; color: var(--tone, var(--muted)); }
.mark[data-state="running"], .mark[data-state="next"] { color: var(--run); }
.icon { width: 15px; height: 15px; vertical-align: -3px; margin-right: 2px; }
.icon circle { stroke: none; fill: var(--muted); }
.icon path { fill: none; stroke: var(--brand-ink); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.icon[data-state="pass"] circle { fill: var(--pass); } .icon[data-state="fail"] circle { fill: var(--fail); }
.icon[data-state="minor"] path { stroke: var(--muted); }
.num { font: 700 24px/1.1 var(--display); font-variant-numeric: tabular-nums; }
.num__unit { font: 500 12px var(--mono); color: var(--muted); margin-left: 3px; }
.id { font: 400 12.5px var(--mono); color: var(--muted); overflow-wrap: anywhere; }
div.id { margin-top: 2px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--bar-off); display: inline-block; margin-right: 6px; }
.dot[data-state="up"] { background: var(--info); box-shadow: 0 0 0 3px color-mix(in srgb, var(--info) 25%, transparent); }
.dot[data-state="stopping"] { background: var(--wait); }
.spinner { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--wait); margin-right: 6px; animation: pulse 1.2s infinite; }
@keyframes pulse { 50% { opacity: .35; } }
.meter { display: inline-block; height: 8px; min-width: 80px; flex: 1; border-radius: 0 4px 4px 0; overflow: hidden; }
.meter__fill { display: block; height: 100%; background: var(--brand); min-width: 2px; border-radius: 0 4px 4px 0; }
.meter--thin { height: 4px; border-radius: 2px; background: var(--soft); }
.meter--thin .meter__fill { background: var(--ok); }
.flag { font: 500 11.5px var(--mono); padding: 1px 6px; border-radius: 4px; white-space: nowrap; background: color-mix(in srgb, var(--tone, var(--muted)) 22%, transparent); }
.pill { font: 600 11px var(--mono); letter-spacing: .08em; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; white-space: nowrap; margin-left: 8px; }
.pill--core { background: color-mix(in srgb, var(--brand) 28%, transparent); box-shadow: inset 0 0 0 1.5px var(--brand); color: var(--brand); }
.pill--supporting { box-shadow: inset 0 0 0 1.5px var(--brand); color: var(--brand); }
.pill--generic { box-shadow: inset 0 0 0 1.5px currentColor; opacity: .7; }
.empty { color: var(--muted); font-style: italic; margin-top: 8px; }
.intro { color: var(--muted); margin: 6px 0 8px; font-size: 16px; max-width: 48em; }
.note { color: var(--tone, var(--muted)); font-size: 15px; margin-top: 4px; }
.rule-id { font: 500 11.5px var(--mono); color: var(--muted); padding-left: 6px; white-space: nowrap; }
.rule-id--gate { border-left: 3px solid var(--bar); } .rule-id--runner { border-left: 3px solid var(--run); } .rule-id--instructed { border-left: 3px solid var(--wait); }
.rule-id[data-state] { background: color-mix(in srgb, var(--tone, var(--muted)) 20%, transparent); }
.rule-id__refused { font-weight: 700; color: var(--stop); margin-left: 3px; }

/* === molecules ================================================================================================ */
.form-row { margin-top: 12px; }
.form-row .hint, .form-row .error { display: block; margin-top: 4px; }
.form-row--inline { display: inline-flex; align-items: baseline; gap: 8px; margin-top: 0; }
.form-row--inline .label { margin: 0; }
.form-row--bar .label { color: var(--bar-text); }
.ask { margin-top: 12px; }
.ask .form-row:first-child { margin-top: 0; }
.ask__go { margin-top: 10px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }
.actions > .ask { flex: 1 1 100%; }
.actions--end { justify-content: flex-end; margin-top: 0; }
.actions--tight { margin-top: 6px; }
.actions--foot { margin-top: auto; padding-top: 14px; flex-wrap: nowrap; }
.actions--foot .link--to { margin: 0 0 0 auto; }
.tile { border-radius: 9px; padding: 10px 12px; background: var(--soft); }
.tile .num { display: block; }
.tile--lead .num { color: var(--brand-text); }
.tile--alert .num { color: var(--stop); }
.tile__label { display: block; margin-top: 4px; font: 500 11px/1.4 var(--mono); color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.tile__said { display: block; font: 400 11.5px var(--mono); color: var(--muted); margin-top: 2px; }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin-top: 12px; font-size: 16px; }
.kv__key { font: 400 12.5px var(--mono); color: var(--muted); padding-top: 3px; }
.toast { background: var(--panel); color: var(--ink); border: 1px solid var(--line); border-left: 4px solid var(--info); border-radius: 8px;
  padding: 10px 14px; box-shadow: var(--shadow); font-size: 15px; white-space: pre-wrap; }
.toast--error { border-left-color: var(--danger); }
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font: 400 12px var(--mono); color: var(--muted); margin-top: 10px; }
.legend__item { display: inline-flex; align-items: center; gap: 6px; }
.legend__key { display: inline-block; width: 18px; height: 6px; border-radius: 1px; }
.strip { display: flex; gap: 2px; }
.strip__seg { flex: 1; height: 5px; background: var(--line); }
.strip__seg[data-state="delivered"], .legend__key[data-state="delivered"] { background: var(--ok); }
.strip__seg[data-state="running"], .legend__key[data-state="running"] { background: var(--wait); }
.strip__seg[data-state="stopped"], .legend__key[data-state="stopped"] { background: var(--stop); }
.strip__seg[data-state="approved"], .legend__key[data-state="approved"] { background: color-mix(in srgb, var(--info) 40%, var(--line)); }
.strip__seg[data-state="draft"], .legend__key[data-state="draft"] { background: transparent; box-shadow: inset 0 0 0 1px var(--muted); }
.strip__seg[data-state="superseded"], .legend__key[data-state="superseded"] { background: var(--line); }
.said { margin: 4px 0; font: 400 15px var(--body); line-height: 1.45; }
.said__kw { font: 600 12.5px var(--mono); color: var(--ink); margin-right: 6px; white-space: nowrap; }
.said__goes { font: 500 12.5px var(--mono); color: var(--brand-text); white-space: nowrap; }
.figures { display: flex; flex-wrap: wrap; gap: 4px 14px; font: 400 12.5px var(--mono); color: var(--muted); margin: 0 0 10px; }
.figures__value { color: var(--ink); font-weight: 600; }
.figures__value--alert { color: var(--stop); }
.bars { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content; gap: 6px 12px; align-items: center; margin-top: 8px; }
.bars__label { font: 500 12.5px var(--mono); color: var(--ink); }
.bars__n { font: 500 12.5px var(--mono); color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
.toolbar { display: flex; gap: 8px 14px; flex-wrap: wrap; align-items: center; margin-top: 12px; }
.inflow { display: flex; gap: 14px; align-items: center; margin-top: 22px; }
.inflow__label { font: 500 11px var(--mono); text-transform: uppercase; letter-spacing: .08em; color: var(--brand-text); white-space: nowrap; }
.quiet-line { margin-top: 14px; font: 400 13px var(--mono); color: var(--muted); }
.quiet-line .link { font: inherit; text-decoration: none; }
.notice { margin-top: 26px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 14px 18px;
  border: 1px solid var(--line); border-left: 4px solid var(--info); border-radius: 10px; background: var(--panel); }
.notice__text { flex: 1 1 280px; font: 500 16px var(--display); }
.notice__arrow { color: var(--info); margin-right: 6px; }
.notice--ended { border-left-color: var(--danger); }
.notice--ended .notice__arrow { color: var(--danger); }
.story-card { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; font-size: 14px; line-height: 1.35;
  box-shadow: inset 3px 0 0 var(--line); }
.story-card .link--title { font-size: 14px; }
.story-card .id { margin-top: 3px; }
.story-card[data-state="delivered"] { box-shadow: inset 3px 0 0 var(--ok); }
.story-card[data-state="running"] { box-shadow: inset 3px 0 0 var(--wait); }
.story-card[data-state="stopped"] { box-shadow: inset 3px 0 0 var(--stop); }
.story-card[data-state="approved"] { box-shadow: inset 3px 0 0 color-mix(in srgb, var(--info) 40%, var(--line)); }
.story-card[data-state="draft"] { box-shadow: none; border-left: 2px dashed var(--muted); }
.ticket { border: 1px dashed var(--line); border-radius: 7px; padding: 6px 10px; font-size: 14px; display: grid; gap: 4px; min-width: 0; }
.ticket__what { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.ticket__kind { font: 600 12px var(--mono); color: var(--brand-text); }
.option { border: 1px solid var(--line); border-radius: 8px; padding: 9px 12px; font-size: 15px; display: grid;
  grid-column: 1 / -1; grid-template-columns: subgrid; gap: 4px 12px; align-items: start; }
.option__pick { grid-row: 1 / span 2; }
.option__pick .btn { min-width: 2.6em; }
.option__advised { grid-column: 2; font: 600 10.5px var(--mono); color: var(--brand-text); text-transform: uppercase; letter-spacing: .07em; }
.option__text { grid-column: 2; }
.option--advised { border-color: var(--brand); box-shadow: inset 0 0 0 1px var(--brand); }
.list__item { display: flex; gap: 10px; align-items: baseline; padding: 8px 0; border-top: 1px solid var(--line); }
.list__item:first-child { border-top: 0; }
.list__what { flex: 1; min-width: 0; }
.list__aside { font: 400 13px var(--mono); color: var(--muted); white-space: nowrap; text-align: right; }
/* a delivery a row of fixed columns: when, what, its epic, its outcome event, how long, what it cost */
.delivery { display: grid; grid-template-columns: 44px minmax(0, 1fr) 150px 210px 76px 64px; gap: 4px 14px; align-items: start;
  padding: 5px 0; border-bottom: 1px solid var(--line); font-size: 15px; }
.delivery__epic, .delivery__event { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.delivery__at, .delivery__epic, .delivery__fig { font: 400 12.5px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.delivery__fig { text-align: right; }
.delivery > :not(.delivery__what) { padding-top: 4px; }
.domain-node { position: relative; margin: 16px 0 8px; font: 600 15px var(--display); }
.domain-node__n { position: absolute; left: -33px; top: -1px; width: 22px; height: 22px; border-radius: 50%; background: var(--brand); color: var(--brand-ink);
  font: 600 12px var(--mono); display: grid; place-items: center; }
.domain-node .hint { font: 400 13px var(--body); margin-left: 6px; }
.facts { display: grid; grid-template-columns: max-content 1fr; gap: 6px 12px; margin: 2px 0 0; }
.facts__kind { font: 600 11px var(--mono); color: var(--muted); text-transform: uppercase; letter-spacing: .06em; padding-top: 3px; }
.facts__terms { margin: 0; display: flex; flex-wrap: wrap; gap: 4px; }
.rule-line { padding: 8px 10px 2px; font: italic 500 14px var(--body); color: var(--muted); }
.rule-line::before { content: "Rule · "; font: normal 600 11px var(--mono); color: var(--brand-text); letter-spacing: .06em; }
.proposal { border: 1px solid var(--line); border-radius: 8px; padding: 9px 11px; margin-bottom: 8px; display: grid; gap: 5px; min-width: 0; }
.proposal__goal { font: 600 15px var(--display); }
.proposal__facts { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 13px; color: var(--muted); }
.proposal .event { white-space: normal; overflow-wrap: anywhere; }
.aside { margin-top: 18px; padding: 4px 14px 6px; border-left: 4px solid var(--wait); border-radius: 6px; background: var(--panel); }
.trail { list-style: none; margin-top: 14px; border-top: 1px solid var(--line); }
.trail__item { display: grid; grid-template-columns: 1.4em minmax(0, 1fr) auto; gap: 4px 10px; align-items: baseline; padding: 10px 0; border-bottom: 1px solid var(--line); }
.trail__item:last-child { border-bottom: 0; }
.trail__glyph { color: var(--brand-text); }
.trail__words { min-width: 0; }
.trail__words q { font-style: italic; }
.trail__state { display: block; font: 400 12.5px var(--mono); color: var(--tone, var(--muted)); margin-top: 2px; }
.trail__state[data-state="wait"] { color: var(--muted); }
.trail__acts { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.tab { font: 400 13px var(--mono); letter-spacing: .4px; color: var(--bar-dim); background: none; border: 0;
  padding: 8px 10px; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.tab:hover { color: var(--brand); }
.tab[aria-selected="true"] { color: var(--bar-ink); border-bottom-color: var(--brand); }
.tab:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
/* the keys show while the bar is worked by keyboard, never for a mouse */
.tab__key { display: none; margin-right: 6px; color: var(--brand); font-size: 11px; }
.tabs:has(:focus-visible) .tab__key { display: inline; }
.tab__n { display: inline-block; min-width: 18px; margin-left: 6px; padding: 0 5px; border-radius: 9px; background: var(--brand-fill);
  color: var(--brand-ink); font-size: 11px; text-align: center; }
.step__word { font: 600 14px var(--display); color: var(--brand-text); margin-right: 6px; }
.prose { font-size: 16px; }
.prose p, .prose ul, .prose ol { margin: 0 0 8px; }
.prose table { width: auto; margin: 4px 0 10px; font-size: 15px; }
.prose td, .prose th { padding: 5px 12px 5px 0; }
.prose pre { font: 12.5px/1.5 var(--mono); background: var(--code); border-radius: 6px; padding: 10px 12px; overflow-x: auto; margin: 4px 0 10px; }
.prose h4 { font: 600 14px var(--display); margin: 10px 0 4px; }
.prose ul, .prose ol { padding-left: 1.3em; }
.prose li { margin: 2px 0; }

/* === organisms ================================================================================================ */
.card { margin-top: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 20px 22px; }
.card__title { font: 700 20px/1.25 var(--display); letter-spacing: -.3px; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.card__sub { font: 400 12.5px var(--mono); color: var(--muted); letter-spacing: .2px; }
.card--wish .ask { margin-top: 14px; }
/* the one fold: a button over its region — a row, a quiet line, a group, an ink row, an epic's panel, a whole card */
.accordion__heading { font: inherit; margin: 0; }
.accordion__head { display: grid; grid-template-columns: 14px minmax(0, 1fr) max-content; gap: 4px 10px; align-items: baseline; width: 100%;
  background: none; border: 0; padding: 7px 2px; text-align: left; color: var(--ink); cursor: pointer; font: 400 15px var(--body); }
.accordion__head:hover .accordion__title { color: var(--brand-text); }
.accordion__head:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; border-radius: 6px; }
.accordion__title { min-width: 0; display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.accordion__meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; font: 400 12.5px var(--mono); color: var(--muted); }
.accordion__below { grid-column: 2 / -1; display: flex; gap: 6px; flex-wrap: wrap; }
.accordion__body { padding: 2px 4px 12px 26px; }
.accordion--row { border-top: 1px solid var(--line); }
.accordion--row:last-child { border-bottom: 1px solid var(--line); }
.accordion--row[data-open] { box-shadow: inset 3px 0 0 var(--brand); background: color-mix(in srgb, var(--brand) 5%, transparent); }
.accordion--quiet > .accordion__head { display: inline-flex; width: auto; padding: 2px 0; font: 500 12px var(--mono); color: var(--brand-text); margin-top: 6px; }
.accordion--quiet > .accordion__head .caret { color: inherit; }
.accordion--quiet > .accordion__body { padding: 4px 0 0; }
.accordion--group { border: 1px solid var(--group-line); border-radius: 6px; margin-top: 6px; background: var(--panel); }
.accordion--group > .accordion__head { padding: 6px 10px; background: var(--group); border-radius: 6px; font: 600 15px var(--display); }
.accordion--group[data-open] > .accordion__head { border-radius: 6px 6px 0 0; }
.accordion--group[data-open] > .accordion__head .caret { color: var(--brand-text); }
.accordion--group > .accordion__body { padding: 0 0 6px; }
.accordion--group .accordion--row { border-top: 0; } .accordion--group .accordion--row + .accordion--row { border-top: 1px solid var(--line); }
.accordion--group .accordion--row > .accordion__head { padding: 5px 10px 5px 20px; }
.accordion--group .actions { padding: 0 10px 4px; }
.accordion--ink { border-bottom: 1px solid var(--line); }
.accordion--ink > .accordion__head { padding: 10px 8px; font-size: 16px; }
.accordion--ink > .accordion__head:hover { background: var(--soft); }
.accordion--ink .accordion__title b { font: 500 16.5px var(--display); }
.accordion--ink[data-open] > .accordion__head { background: var(--ink); color: var(--paper); border-radius: 4px 4px 0 0; box-shadow: inset 0 4px 0 var(--brand); }
.accordion--ink[data-open] > .accordion__head .accordion__title b { font-weight: 700; color: var(--paper); }
.accordion--ink[data-open] > .accordion__head :is(.id, .hint, .caret, .accordion__meta) { color: color-mix(in srgb, var(--paper) 70%, transparent); }
.accordion--ink > .accordion__body { padding: 4px 0 8px; }
.accordion--panel { border-radius: 8px; background: var(--panel); border: 1px solid var(--line); overflow: hidden; margin-top: 8px; }
.accordion--panel > .accordion__head { padding: 9px 12px 0; background: var(--soft); }
.accordion--panel .accordion__below { grid-column: 1 / -1; margin: 4px -12px 0; display: block; }
.accordion--panel > .accordion__body { padding: 14px 12px 12px; }
.accordion--card { margin-top: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 22px; }
.accordion--card > .accordion__heading .accordion__head { font: 700 20px/1.25 var(--display); letter-spacing: -.3px; }
.accordion--card > .accordion__body { padding: 4px 0 6px; }
.board { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 26px; align-items: stretch; }
.board__slot { display: flex; align-items: stretch; }
.board__slot + .board__slot::before { content: "→"; align-self: center; padding: 0 6px; color: var(--muted); font: 400 18px var(--mono); }
.column { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
.column--hot { border-color: var(--wait); box-shadow: inset 0 3px 0 var(--wait); }
.column__head { font: 700 17px var(--display); display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin: 0; }
.column__count { font: 700 26px var(--display); }
.column__of { font: 500 14px var(--mono); color: var(--muted); }
.column__line { display: flex; align-items: center; gap: 8px; font: 400 12px/16px var(--mono); color: var(--muted); min-height: 16px; margin-top: 2px; }
.column__item { margin-top: 12px; font-size: 15px; }
.column__item + .column__item { margin-top: 8px; }
.column__item .link--title { font: inherit; color: var(--ink); }
.column__item .link--title:hover { color: var(--brand-text); }
.column__item .id { display: block; font-size: 12px; }
.list { list-style: none; margin-top: 12px; }
.lanes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
/* a lane carries its state's colour as a rule along its top; an empty one says so quietly */
.lane { background: var(--paper); border-radius: 4px; padding: 8px; min-width: 0; border-top: 3px solid var(--line); }
.lane[data-state="draft"] { border-top-color: var(--muted); }
.lane[data-state="approved"] { border-top-color: color-mix(in srgb, var(--info) 45%, var(--line)); }
.lane[data-state="running"] { border-top-color: var(--wait); }
.lane[data-state="delivered"] { border-top-color: var(--ok); }
.lane[data-state="delivered"]:not([data-bare]) { background: color-mix(in srgb, var(--ok) 7%, var(--paper)); }
.lane[data-bare] .lane__head { opacity: .55; }
.lane[data-state="delivered"] .story-card[data-state="delivered"] { box-shadow: none; border-color: color-mix(in srgb, var(--ok) 35%, var(--line)); }
.lane__head { font: 600 11px var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); display: flex; justify-content: space-between; margin-bottom: 6px; }
.epic__title { font: 600 15.5px var(--display); }
.stepper { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 3px; padding: 0 12px 10px; }
.stepper__step { text-align: center; font: 500 11px var(--mono); color: var(--muted); }
.stepper__bar { display: block; height: 8px; border-radius: 4px; background: var(--line); margin-bottom: 4px; }
.stepper__step[data-state="done"] .stepper__bar { background: var(--ok); }
.stepper__step[data-state="stopped"] { color: var(--stop); font-weight: 600; }
.stepper__step[data-state="stopped"] .stepper__bar { background: var(--stop); }
.stepper__step[data-state="now"] { color: var(--ink); font-weight: 600; }
.stepper__step[data-state="now"] .stepper__bar { background: var(--wait); animation: pulse 1.5s infinite; }
.course { border: 1px solid var(--line); border-radius: 9px; overflow: hidden; margin-top: 12px; }
.course__top { display: flex; justify-content: space-between; gap: 10px; padding: 9px 12px; align-items: baseline; flex-wrap: wrap; }
.course__right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.course__doing { padding: 6px 12px; font: 400 12.5px var(--mono); color: var(--muted); border-top: 1px solid var(--line); }
.queue { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 12px; }
/* decide: the question on a tinted head, its answers as rows, the recommended one framed */
.record { margin-top: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
.record__question { padding: 12px 18px; background: color-mix(in srgb, var(--wait) 12%, var(--panel)); border-bottom: 1px solid var(--line); }
.record--accept .record__question { background: color-mix(in srgb, var(--brand) 10%, var(--panel)); }
.record__text { font: 600 17px/1.3 var(--display); display: block; margin-top: 2px; }
.record__body { padding: 10px 18px 16px; }
.record__body > .id:last-child { margin-top: 10px; }
.options { display: grid; grid-template-columns: minmax(64px, max-content) minmax(0, 1fr); gap: 6px; margin-top: 10px; }
.tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.tiles--many { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.days { border-left: 2px solid var(--line); margin: 16px 0 0 6px; padding-left: 16px; display: grid; gap: 12px; }
.days__day { position: relative; }
.days__day::before { content: ""; position: absolute; left: -22px; top: 5px; width: 10px; height: 10px; border-radius: 50%; background: var(--ok); }
.days__date { font: 600 12px var(--mono); color: var(--muted); margin-bottom: 2px; }
.domain { margin: 4px 0 8px; }
.domain__track { border-left: 2px solid var(--line); margin: 10px 0 0 12px; padding-left: 20px; }
.kernel { border: 1px solid color-mix(in srgb, var(--shared) 35%, var(--line)); border-top: 4px solid var(--shared); border-radius: 4px 4px 9px 9px;
  padding: 10px 14px 12px; margin: 12px 0 4px; background: color-mix(in srgb, var(--shared) 5%, var(--panel)); }
.kernel__top { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-bottom: 8px; }
.kernel__title { font: 700 18px var(--display); color: var(--shared); }
.proposals { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 8px; }
.rule-group { margin-top: 14px; }
.rule-group__label { font: 500 10.5px var(--mono); letter-spacing: 1px; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }
.rule-group__n { color: var(--ink); margin-left: 4px; }
.part { border-left: 2px solid var(--line); padding: 2px 0 6px 14px; margin-top: 14px; }
.part__head { font: 600 15px var(--display); display: flex; gap: 8px; align-items: baseline; }
.part__head .hint { font: 400 13px var(--body); }
.part__n { font: 600 12px var(--mono); color: var(--brand-text); }
.part .rule-group:first-of-type { margin-top: 6px; }
.table { margin-top: 12px; }
.table__num { text-align: right; font-family: var(--mono); font-size: 13px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.table__act .actions { margin-top: 0; }
.table__mark { width: 1.6em; }
.terminal { font: 12.5px/1.5 var(--mono); background: var(--terminal); color: var(--terminal-ink); border-radius: 8px; padding: 12px; max-height: 460px; overflow: auto;
  white-space: pre-wrap; word-break: break-word; margin-top: 12px; }
.terminal:empty { display: none; }
/* delivered over time: two panels on one time axis — cost above, tokens below, never two scales on one axis */
.curve { position: relative; margin-top: 14px; }
.curve svg { display: block; width: 100%; height: auto; }
.curve__grid { stroke: var(--line); stroke-width: 1; }
.curve__axis { font: 400 11px var(--mono); fill: var(--muted); }
.curve__name { font: 600 11px var(--mono); fill: var(--muted); letter-spacing: .06em; text-transform: uppercase; }
.curve__end { font: 600 12px var(--mono); fill: var(--ink); }
.curve__area { fill: color-mix(in srgb, var(--brand) 12%, transparent); }
.curve__line { fill: none; stroke: var(--brand); stroke-width: 2; stroke-linejoin: round; }
.curve__cross { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 3; }
.curve__dot { fill: var(--brand); stroke: var(--panel); stroke-width: 2; }
.curve__tip { position: absolute; pointer-events: none; background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  box-shadow: var(--shadow); padding: 8px 10px; font: 400 12.5px var(--mono); color: var(--ink); max-width: 320px; }
.curve__title { display: block; font: 600 13.5px var(--display); margin-bottom: 4px; }
.curve__row { display: flex; justify-content: space-between; gap: 14px; color: var(--muted); }
.curve__row span:last-child { color: var(--ink); }
/* the flow, drawn by the factory: a way back shown on a hover, a step, a gate or an edge picked by a click — the
   classes below `.flow` are the drawing's own */
.flow { overflow-x: auto; margin-top: 12px; }
.flow svg { display: block; width: 100%; min-width: 880px; height: auto; }
.flow .f text { fill: var(--ink); } .flow .f text.small { fill: var(--muted); stroke: var(--panel); }
.flow .f .on-line { stroke: color-mix(in srgb, var(--muted) 70%, transparent); } .flow .f .tip-on { fill: color-mix(in srgb, var(--muted) 70%, transparent); }
.flow .f .gate circle, .flow .f .tip-again { fill: var(--pass); } .flow .f .way-again path.vis { stroke: var(--pass); }
.flow .f .way-again text.small { fill: var(--pass); } .flow .f .way-back path.vis { stroke: var(--ink); } .flow .f .tip-back { fill: var(--ink); }
.flow .f .gate path, .flow .f .mark path { stroke: var(--brand-ink); }
.flow .f .mark-stop circle { fill: var(--fail); } .flow .f .mark-waits circle { fill: var(--muted); } .flow .f .done { stroke: var(--ink); }
.flow .way, .flow .gate, .flow [data-stage] { cursor: pointer; }
.flow .way-back { opacity: 0; pointer-events: none; transition: opacity .15s; }
.flow .way-back[data-shown], .flow .way-back[data-picked] { opacity: 1; pointer-events: auto; }
/* what is picked stands out, the rest steps back: a band behind the picked way, a ring round the picked gate */
.flow[data-has-pick] .way:not([data-picked]):not(.way-back), .flow[data-has-pick] .gate:not([data-picked]), .flow[data-has-pick] [data-stage]:not([data-picked]) { opacity: .35; }
.flow .way[data-picked] path.vis { stroke-dasharray: none; stroke-width: 2.4; }
.flow .way-again[data-picked] path.hit { stroke: color-mix(in srgb, var(--pass) 22%, transparent); }
.flow .way-back[data-picked] path.hit { stroke: color-mix(in srgb, var(--ink) 14%, transparent); }
.flow .way[data-picked] text.small { font-weight: 700; }
.flow .gate[data-picked] circle { stroke: color-mix(in srgb, var(--pass) 30%, transparent); stroke-width: 10px; }
.flow .mark[data-picked] circle { stroke: color-mix(in srgb, var(--fail) 30%, transparent); stroke-width: 8px; }
.flow [data-stage][data-picked] { fill: var(--brand); paint-order: stroke; stroke: color-mix(in srgb, var(--brand) 22%, transparent); stroke-width: 10px; stroke-linejoin: round; }
.flow [data-stage][data-has-back]:hover { fill: var(--brand); }
.flow[data-has-story] [data-stage]:not([data-reached]) { opacity: .35; }
.flow [data-stage][data-now] { fill: var(--brand); text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 4px; }
.flow .gate[data-failed] circle { stroke: var(--fail); stroke-width: 4px; }
.flow [data-badge] { font: 700 11px var(--mono); fill: var(--fail); }

/* === templates ================================================================================================ */
.page-head__eyebrow { font: 400 12.5px var(--mono); letter-spacing: 2.5px; text-transform: uppercase; color: var(--brand-text); margin-bottom: 10px; }
.page-head__title { font: 700 clamp(28px, 4vw, 38px)/1.1 var(--display); letter-spacing: -1px; }
.page-head__lede { margin-top: 10px; color: var(--muted); max-width: 44em; font-size: 18px; }
.drawer-frame h2 { font: 600 16px var(--display); margin: 20px 0 6px; }
.drawer-frame__close { float: right; }
.drawer-frame > .actions { margin: 16px 0 22px; }
.drawer-frame .ask { margin: 8px 0 24px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
.gallery { margin-top: 18px; }
.gallery__level { margin-top: 30px; }
.gallery__title { font: 700 20px var(--display); text-transform: capitalize; border-bottom: 1px solid var(--line); padding-bottom: 6px; }
.gallery__item { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 16px; padding: 14px 0; border-bottom: 1px solid var(--line); }
.gallery__name { font: 500 12.5px var(--mono); color: var(--brand-text); padding-top: 4px; }
.gallery__show { min-width: 0; }
.gallery__show > .card:first-child, .gallery__show > .record:first-child, .gallery__show > .board:first-child,
.gallery__show > .accordion--card:first-child, .gallery__show > .notice:first-child { margin-top: 0; }

/* === the narrow screen ======================================================================================== */
@media (prefers-reduced-motion: reduce) { .spinner, .stepper__step[data-state="now"] .stepper__bar { animation: none; } .flow .way-back { transition: none; } }
@media (max-width: 860px) {
  .board { grid-template-columns: 1fr; } .board__slot { flex-direction: column; }
  .board__slot + .board__slot::before { content: "↓"; padding: 4px 0; }
}
@media (max-width: 760px) {
  .wrap { padding: 0 16px; }
  .tabs { order: 3; width: 100%; margin-left: 0; }
  .hide-narrow { display: none; }
  td, th { padding: 8px 4px; }
  .field--bar { width: 100px; }
  .lanes, .tiles { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .delivery { grid-template-columns: 44px minmax(0, 1fr) auto; } .delivery__epic { display: none; }
  .delivery__event { grid-column: 2 / -1; grid-row: 2; } .delivery__fig + .delivery__fig { grid-column: 3; grid-row: 2; }
  .gallery__item { grid-template-columns: 1fr; gap: 6px; }
  /* a row with buttons: its cells side by side, the buttons on a line of their own beneath */
  tr:has(> td.table__act) { display: grid; grid-template-columns: auto 1fr fit-content(40%); border-bottom: 1px solid var(--line); }
  tr:has(> td.table__act) > td { border-bottom: 0; } tr:has(> td.table__act) > td.hide-narrow { display: none; }
  td.table__act { grid-column: 1 / -1; padding-top: 0; } td.table__act:empty { display: none; }
  td.table__act .actions { justify-content: flex-start; }
  table:has(td.table__act) tr:has(> th) { display: none; }
}
"""
