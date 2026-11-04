"""The page's stylesheet (WP-180), by level: the base and the frame, then atoms, molecules, organisms, templates.

Every class is a BEM block of a component in `page_ui.py` (or of the page's frame, `FRAME_BLOCKS`), an element of one
(`block__element`) or a variant (`block--variant`); a state the factory names is selected as `[data-state="…"]`, never
as a class. Colours come from the tokens alone (`page_tokens.py`) — no colour is written here as a value. The rules
under `.flow` select the drawing the factory makes of a flow: its classes are that drawing's, not the page's.
"""

#: The one width at which the page narrows — the frame for the window, a component for its container (WP-181).
NARROW = "760px"

#: The blocks of the page's frame — the bar, the main region, the drawer — written in the page itself, not by a
#: component; and the few utilities a component may add beside its block.
FRAME_BLOCKS = ("topbar", "brand", "tabs", "banner", "main", "toasts", "drawer", "wrap", "sr", "hide-narrow")

STYLE = """
/* === base ===================================================================================================== */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--paper); color: var(--ink); font: var(--text-read)/1.55 var(--body); min-height: 100vh; }
a { color: var(--brand-text); text-decoration: none; }
button:focus-visible, a:focus-visible, textarea:focus-visible, select:focus-visible, input:focus-visible {
  outline: 3px solid var(--brand); outline-offset: 2px; border-radius: var(--radius-label); }
code { font-family: var(--mono); font-size: .78em; background: var(--code); padding: 1px var(--space-1); border-radius: var(--radius-label); overflow-wrap: anywhere; }
h3 { font: 600 var(--text-base) var(--display); margin: var(--space-4) 0 var(--space-2); }
table { width: 100%; border-collapse: collapse; margin-top: var(--space-3); font-size: var(--text-base); }
th { text-align: left; font: 500 var(--text-xs) var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding: var(--space-2) var(--space-2); }
td { border-bottom: 1px solid var(--line); padding: var(--space-3) var(--space-2); vertical-align: top; }
tr:last-child td { border-bottom: 0; }
.wrap { max-width: var(--measure); margin: 0 auto; padding: 0 var(--space-5); }
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
/* the bar holds the application above — the brand, what runs, who acts, the scheme — and the views below, their
   tabs standing on the bar's lower edge and starting where the content starts */
.topbar__app { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2) var(--space-4); padding-block: var(--space-3); flex-wrap: wrap; }
.topbar__nav { border-top: 1px solid var(--bar-rule); }
.brand { display: flex; align-items: baseline; gap: 1ex; font: 700 var(--text-xl) var(--display); letter-spacing: -.3px; color: var(--bar-ink);
  text-decoration: none; border-radius: var(--radius-control); padding: 2px var(--space-2); margin: -2px calc(-1 * var(--space-2)); }
.brand:hover .brand__name { color: var(--brand); }
.brand:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.brand__logo { display: inline-block; width: 2.13ex; height: 2.4ex; align-self: center; }
.brand__logo svg { display: block; width: 100%; height: 100%; overflow: visible; }
:root[data-logo] .brand__logo { width: var(--logo-width); background: var(--logo) left center / contain no-repeat; }
:root[data-logo] .brand__logo svg { display: none; }
.brand__dot { color: var(--brand); }
.brand__project { font: 400 var(--text-sm) var(--mono); color: var(--bar-dim); letter-spacing: .3px; margin-left: var(--space-1); }
.tabs { display: flex; align-items: center; gap: var(--space-1); overflow-x: auto; scrollbar-width: none; }
.tabs > :first-child > .tab:first-child, .tabs > .tab:first-child { margin-left: calc(-1 * var(--space-3)); }
.tabs__group { display: flex; align-items: center; }
.tabs__sep { flex: none; width: 1px; height: 16px; margin: 0 var(--space-2); background: var(--bar-faint); }
.tabs__arrow { color: var(--bar-faint); font: 400 var(--text-sm) var(--mono); }
.topbar__tools { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.banner { background: var(--bar); color: var(--bar-ink); border-bottom: 3px solid var(--stop); font: 500 var(--text-md) var(--display); padding: var(--space-2) 0; }
.main, .drawer, .gallery__show { container-type: inline-size; }
.main { padding-top: var(--space-7); padding-bottom: var(--space-8); }
.toasts { position: fixed; right: 16px; bottom: 16px; z-index: 40; display: flex; flex-direction: column; gap: var(--space-2); max-width: min(440px, calc(100% - 32px)); }
.drawer { position: fixed; inset: var(--bar-height, 0px) 0 0 auto; width: min(760px, 100%); z-index: 15; background: var(--paper);
  border-left: 1px solid var(--line); box-shadow: var(--shadow); overflow-y: auto; padding: var(--space-5); }

/* === atoms ==================================================================================================== */
/* a control is pressed, a display is read: a control is a raised rectangle in the display face, a display flat, in the
   mono face, never with an edge — the accent alone tells neither (the brand's controls and displays) */
.btn { font: 600 var(--text-md) var(--display); padding: var(--space-2) var(--space-4); border-radius: var(--radius-control); border: 1px solid var(--line); background: var(--panel);
  color: var(--ink); cursor: pointer; white-space: nowrap; box-shadow: var(--lift); }
.btn:active:not(:disabled) { transform: translateY(1px); box-shadow: none; }
.btn:hover { border-color: var(--brand); color: var(--brand-text); }
.btn:disabled { opacity: .5; cursor: default; }
.btn--primary { background: var(--brand-fill); border-color: var(--brand-fill); color: var(--brand-ink);
  box-shadow: 0 1px 0 var(--brand-fill-hover), 0 2px 6px color-mix(in srgb, var(--brand) 30%, transparent); }
.btn--primary::after { content: "→"; font-weight: 400; margin-left: var(--space-2); }
.btn--primary:hover { background: var(--brand-fill-hover); border-color: var(--brand-fill-hover); color: var(--brand-ink); }
.btn--plain::after { content: none; }
.btn--write::before { content: "✦"; color: var(--brand-text); margin-right: var(--space-2); font-weight: 400; }
.btn--primary.btn--write::before { color: var(--brand-ink); }
.btn--danger:hover { border-color: var(--stop); color: var(--stop); }
.btn--small { font-size: var(--text-sm); padding: var(--space-1) var(--space-2); }
.btn--bar { font: 500 var(--text-sm) var(--display); color: var(--bar-ink); background: none; border-color: var(--bar-faint); box-shadow: none; padding: var(--space-1) var(--space-3); border-radius: var(--radius-control); }
.btn--bar:hover { border-color: var(--brand); color: var(--brand); }
.btn--bar.btn--primary { background: var(--brand-fill); border-color: var(--brand-fill); color: var(--brand-ink); }
.link { background: none; border: 0; padding: 0; text-align: left; font: inherit; color: var(--brand-text); cursor: pointer;
  text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px;
  text-decoration-color: color-mix(in srgb, var(--brand-text) 45%, transparent); }
.link:hover { text-decoration-color: currentColor; }
.link--title { font: 500 var(--text-base) var(--display); text-decoration: none; }
.link--title:hover { text-decoration: underline; }
.link--to { display: inline-block; margin-top: var(--space-3); font: 500 var(--text-sm) var(--mono); text-decoration: none; }
.link--way { font: 500 var(--text-sm) var(--mono); padding: 2px 0; white-space: nowrap; }
.link--plain { font: inherit; color: inherit; text-decoration: none; }
.link--plain:hover { color: var(--brand-text); }
.switch { display: inline-flex; border: 1px solid var(--line); border-radius: var(--radius-control); overflow: hidden; background: var(--panel); }
.switch__opt { font: 500 var(--text-sm) var(--display); color: var(--ink); background: none; border: 0; padding: var(--space-1) var(--space-3); cursor: pointer; white-space: nowrap; }
.switch__opt + .switch__opt { border-left: 1px solid var(--line); }
.switch__opt:hover { color: var(--brand-text); }
.switch__opt[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
.switch__n { font: 400 var(--text-xs) var(--mono); margin-left: var(--space-1); opacity: .7; }
.switch--bar { background: none; border-color: var(--bar-faint); border-radius: var(--radius-control); }
.switch--bar .switch__opt { font: 400 var(--text-sm) var(--mono); color: var(--bar-dim); padding: var(--space-1) var(--space-2); }
.switch--bar .switch__opt + .switch__opt { border-left-color: var(--bar-faint); }
.switch--bar .switch__opt[aria-pressed="true"] { background: var(--bar-rule); color: var(--bar-ink); }
.select { font: 400 var(--text-sm) var(--mono); color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-2); }
.field { font: 400 var(--text-md) var(--mono); color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-3); width: 100%; }
.field--area { min-height: 72px; resize: vertical; font: var(--text-read)/1.5 var(--body); padding: var(--space-3) var(--space-3); }
.field[aria-invalid="true"] { border-color: var(--stop); }
.field--bar { font: 400 var(--text-sm) var(--mono); color: var(--bar-ink); background: var(--bar-rule); border-color: var(--bar-faint); border-radius: var(--radius-control); padding: var(--space-1) var(--space-2); width: 170px; }
/* the fold's caret: a drawn chevron, as large as its row's text wants, turned down when open */
/* the one caption — a column's, a group's, a kind's name: small capitals in the mono face */
.caption { font: 500 var(--text-xs)/1.4 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.caption--brand { color: var(--brand-text); }
.caret { width: var(--caret); height: var(--caret); fill: none; stroke: var(--muted); stroke-width: 1.8; stroke-linecap: round;
  stroke-linejoin: round; align-self: start; margin-top: calc((1lh - var(--caret)) / 2); transition: transform .15s; }
.caret[data-open] { transform: rotate(90deg); stroke: var(--caret-open, currentColor); }
.label { display: block; font: 600 var(--text-md) var(--display); color: var(--ink); margin-bottom: var(--space-1); }
.label--quiet { font: 400 var(--text-sm) var(--mono); color: var(--muted); }
/* a menu: its button, and beneath it a panel of the page's ground that stays above the content */
.menu { position: relative; }
.menu__toggle { display: inline-flex; align-items: center; gap: var(--space-2); font: 400 var(--text-sm) var(--mono); color: var(--ink);
  background: none; border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-1) var(--space-3); cursor: pointer; white-space: nowrap; }
.menu__toggle:hover { border-color: var(--brand); }
.menu__toggle:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.menu__chev { font-size: var(--text-xs); color: var(--muted); transition: transform .15s; }
.menu__toggle[aria-expanded="true"] .menu__chev { transform: rotate(180deg); }
.menu--bar > .menu__toggle { color: var(--bar-text); border-color: var(--bar-rule); }
.menu--bar > .menu__toggle:hover, .menu--bar > .menu__toggle[aria-expanded="true"] { color: var(--bar-ink); border-color: var(--bar-faint); }
.menu--bar .menu__chev { color: var(--bar-dim); }
.menu--flush > .menu__toggle { border-color: transparent; }
.menu__panel { position: absolute; top: calc(100% + var(--space-2)); right: 0; z-index: 30; width: min(26rem, calc(100vw - 2 * var(--space-4)));
  display: grid; gap: var(--space-3); padding: var(--space-4); background: var(--panel); color: var(--ink); border: 1px solid var(--line);
  border-radius: var(--radius-card); box-shadow: var(--shadow); }
.menu__panel[hidden] { display: none; }
/* a label the field's example already explains: read out, not shown */
.label--hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; margin: 0; }
.hint { font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.hint--block { display: block; margin: var(--space-2) 0; font: 400 var(--text-md) var(--body); }
.error { display: inline-block; font: 400 var(--text-md) var(--body); color: var(--stop); }
p.error { display: block; margin: var(--space-2) 0; }
.term { font: 500 var(--text-sm) var(--mono); padding: 2px var(--space-2); border-radius: var(--radius-label); background: var(--tint); color: var(--brand-text); white-space: nowrap; cursor: help; }
.term--minor { background: transparent; box-shadow: inset 0 0 0 1px var(--brand); }
/* a term of the shared kernel, in a context or in the kernel's own block: never a context's accent */
.term--shared { background: color-mix(in srgb, var(--shared) 14%, transparent); color: var(--shared); }
.term--shared::before { content: "⇄ "; font-size: var(--text-xs); }
.event { font: 500 var(--text-sm) var(--mono); padding: 1px var(--space-2) 1px var(--space-2); border-radius: var(--radius-round); background: var(--tint); color: var(--brand-text); white-space: nowrap; }
.event::before { content: "◆"; font-size: .7em; margin-right: var(--space-1); vertical-align: 1px; }
.state { font: 600 var(--text-xs) var(--mono); letter-spacing: .07em; text-transform: uppercase; padding: 2px var(--space-2); border-radius: var(--radius-round); white-space: nowrap;
  color: var(--tone, var(--muted)); background: color-mix(in srgb, var(--tone, var(--muted)) 14%, transparent); }
.mark { font: 700 var(--text-base) var(--display); display: inline-block; width: 1.3em; text-align: center; color: var(--tone, var(--muted)); }
.mark[data-state="running"], .mark[data-state="next"] { color: var(--run); }
.icon { width: 15px; height: 15px; vertical-align: -3px; margin-right: 2px; }
.icon circle { stroke: none; fill: var(--muted); }
.icon path { fill: none; stroke: var(--brand-ink); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.icon[data-state="pass"] circle { fill: var(--pass); } .icon[data-state="fail"] circle { fill: var(--fail); }
.icon[data-state="minor"] path { stroke: var(--muted); }
.num { font: 700 var(--text-2xl)/1.1 var(--display); font-variant-numeric: tabular-nums; }
.num__unit { font: 500 var(--text-sm) var(--mono); color: var(--muted); margin-left: var(--space-1); }
.id { font: 400 var(--text-sm) var(--mono); color: var(--muted); overflow-wrap: anywhere; }
div.id { margin-top: 2px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--bar-off); display: inline-block; margin-right: var(--space-2); }
.dot[data-state="up"] { background: var(--info); box-shadow: 0 0 0 3px color-mix(in srgb, var(--info) 25%, transparent); }
.dot[data-state="stopping"] { background: var(--wait); }
.spinner { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--wait); margin-right: var(--space-2); animation: pulse 1.2s infinite; }
@keyframes pulse { 50% { opacity: .35; } }
.meter { display: inline-block; height: 8px; min-width: 80px; flex: 1; border-radius: 0 var(--radius-label) var(--radius-label) 0; overflow: hidden; }
.meter__fill { display: block; height: 100%; background: var(--brand); min-width: 2px; border-radius: 0 var(--radius-label) var(--radius-label) 0; }
.meter--thin { height: 4px; border-radius: 2px; background: var(--soft); }
.meter--thin .meter__fill { background: var(--ok); }
.flag { font: 500 var(--text-xs) var(--mono); padding: 1px var(--space-2); border-radius: var(--radius-label); white-space: nowrap; background: color-mix(in srgb, var(--tone, var(--muted)) 22%, transparent); }
.pill { font: 600 var(--text-xs) var(--mono); letter-spacing: .08em; text-transform: uppercase; padding: 2px var(--space-2); border-radius: var(--radius-round); white-space: nowrap; margin-left: var(--space-2); }
.pill--core { background: color-mix(in srgb, var(--brand) 28%, transparent); box-shadow: inset 0 0 0 1.5px var(--brand); color: var(--brand); }
.pill--supporting { box-shadow: inset 0 0 0 1.5px var(--brand); color: var(--brand); }
.pill--generic { box-shadow: inset 0 0 0 1.5px currentColor; opacity: .7; }
.empty { color: var(--muted); font-style: italic; margin-top: var(--space-2); }
.intro { color: var(--muted); margin: var(--space-2) 0 var(--space-2); font-size: var(--text-base); max-width: 48em; }
.note { color: var(--tone, var(--muted)); font-size: var(--text-base); margin-top: var(--space-1); }
.rule-id { font: 500 var(--text-xs) var(--mono); color: var(--muted); padding-left: var(--space-2); white-space: nowrap; }
.rule-id--gate { border-left: 3px solid var(--bar); } .rule-id--runner { border-left: 3px solid var(--run); } .rule-id--instructed { border-left: 3px solid var(--wait); }
.rule-id[data-state] { background: color-mix(in srgb, var(--tone, var(--muted)) 20%, transparent); }
.rule-id__refused { font-weight: 700; color: var(--stop); margin-left: var(--space-1); }

/* === molecules ================================================================================================ */
.form-row { margin-top: var(--space-3); }
.form-row .hint, .form-row .error { display: block; margin-top: var(--space-1); }
.form-row--inline { display: inline-flex; align-items: baseline; gap: var(--space-2); margin-top: 0; }
.form-row--inline .label { margin: 0; }
.label--bar { color: var(--bar-text); }
.ask { margin-top: var(--space-3); }
.ask .form-row:first-child { margin-top: 0; }
.ask__go { margin-top: var(--space-3); }
.actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-3); align-items: center; }
.actions > .ask { flex: 1 1 100%; }
.actions--end { justify-content: flex-end; margin-top: 0; }
.actions--tight { margin-top: var(--space-2); }
.actions--foot { margin-top: auto; padding-top: var(--space-4); flex-wrap: nowrap; }
.actions--foot .link--to { margin: 0 0 0 auto; }
.tile { border-radius: var(--radius-control); padding: var(--space-3) var(--space-3); background: var(--soft); }
.tile .num { display: block; }
.num--lead { color: var(--brand-text); }
.num--alert { color: var(--stop); }
.tile .caption { display: block; margin-top: var(--space-1); }
.tile__said { display: block; font: 400 var(--text-xs) var(--mono); color: var(--muted); margin-top: 2px; }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: var(--space-1) var(--space-4); margin-top: var(--space-3); font-size: var(--text-base); }
.kv__key { font: 400 var(--text-sm) var(--mono); color: var(--muted); padding-top: var(--space-1); }
.toast { background: var(--panel); color: var(--ink); border: 1px solid var(--line); border-left: 4px solid var(--info); border-radius: var(--radius-control);
  padding: var(--space-3) var(--space-4); box-shadow: var(--shadow); font-size: var(--text-base); white-space: pre-wrap; }
.toast--error { border-left-color: var(--danger); }
.legend { list-style: none; display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); font: 400 var(--text-sm) var(--mono); color: var(--muted); margin-top: var(--space-3); }
.legend__item { display: inline-flex; align-items: center; gap: var(--space-2); }
.legend__key { display: inline-block; width: 18px; height: 6px; border-radius: 1px; }
.strip { display: flex; gap: 2px; }
.strip__seg { flex: 1; height: 5px; background: var(--line); }
.strip__seg[data-state="delivered"], .legend__key[data-state="delivered"] { background: var(--ok); }
.strip__seg[data-state="running"], .legend__key[data-state="running"] { background: var(--wait); }
.strip__seg[data-state="stopped"], .legend__key[data-state="stopped"] { background: var(--stop); }
.strip__seg[data-state="approved"], .legend__key[data-state="approved"] { background: color-mix(in srgb, var(--info) 40%, var(--line)); }
.strip__seg[data-state="draft"], .legend__key[data-state="draft"] { background: transparent; box-shadow: inset 0 0 0 1px var(--muted); }
.strip__seg[data-state="superseded"], .legend__key[data-state="superseded"] { background: var(--line); }
.said { margin: var(--space-1) 0; font: 400 var(--text-base) var(--body); line-height: 1.45; }
.said__kw { font: 600 var(--text-sm) var(--mono); color: var(--ink); margin-right: var(--space-2); white-space: nowrap; }
.said__goes { font: 500 var(--text-sm) var(--mono); color: var(--brand-text); white-space: nowrap; }
.figures { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); font: 400 var(--text-sm) var(--mono); color: var(--muted); margin: 0 0 var(--space-3); }
.figures__value { color: var(--ink); font-weight: 600; }
.figures__value--alert { color: var(--stop); }
.bars { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content; gap: var(--space-2) var(--space-3); align-items: center; margin-top: var(--space-2); }
.bars__label { font: 500 var(--text-sm) var(--mono); color: var(--ink); }
.bars__n { font: 500 var(--text-sm) var(--mono); color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
.toolbar { display: flex; gap: var(--space-2) var(--space-4); flex-wrap: wrap; align-items: center; margin-top: var(--space-3); }
.inflow { display: flex; gap: var(--space-4); align-items: baseline; margin-top: var(--space-5); }
.quiet-line { margin-top: var(--space-4); font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.link--quiet { font: inherit; text-decoration: none; }
.notice { margin-top: var(--space-5); display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; padding: var(--space-4) var(--space-4);
  border: 1px solid var(--line); border-left: 4px solid var(--info); border-radius: var(--radius-card); background: var(--panel); }
.notice__text { flex: 1 1 280px; font: 500 var(--text-base) var(--display); }
.notice__arrow { color: var(--info); margin-right: var(--space-2); }
.notice--ended { border-left-color: var(--danger); }
.notice--ended .notice__arrow { color: var(--danger); }
.story-card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-2); margin-bottom: var(--space-2); font-size: var(--text-md); line-height: 1.35;
  box-shadow: inset 3px 0 0 var(--line); }
.link--compact { font-size: var(--text-md); }
.story-card .id { margin-top: var(--space-1); }
.story-card[data-state="delivered"] { box-shadow: inset 3px 0 0 var(--ok); }
.story-card[data-state="running"] { box-shadow: inset 3px 0 0 var(--wait); }
.story-card[data-state="stopped"] { box-shadow: inset 3px 0 0 var(--stop); }
.story-card[data-state="approved"] { box-shadow: inset 3px 0 0 color-mix(in srgb, var(--info) 40%, var(--line)); }
.story-card[data-state="draft"] { box-shadow: none; border-left: 2px dashed var(--muted); }
.ticket { border: 1px dashed var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-3); font-size: var(--text-md); display: grid; gap: var(--space-1); min-width: 0; }
.ticket__what { display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; }
.ticket__kind { font: 600 var(--text-sm) var(--mono); color: var(--brand-text); }
.option { border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-3); font-size: var(--text-base); display: grid;
  grid-column: 1 / -1; grid-template-columns: subgrid; gap: var(--space-1) var(--space-3); align-items: start; }
.option__pick { grid-row: 1 / span 2; }
.option__pick .btn { min-width: 2.6em; }
.option .caption { grid-column: 2; }
.option__text { grid-column: 2; }
.option--advised { border-color: var(--brand); box-shadow: inset 0 0 0 1px var(--brand); }
.list__item { display: flex; gap: var(--space-3); align-items: baseline; padding: var(--space-2) 0; border-top: 1px solid var(--line); }
.list__item:first-child { border-top: 0; }
.list__what { flex: 1; min-width: 0; }
.list__aside { font: 400 var(--text-sm) var(--mono); color: var(--muted); white-space: nowrap; text-align: right; }
/* a delivery a row of fixed columns: when, what, its epic, its outcome event, how long, what it cost */
.delivery { display: grid; grid-template-columns: 44px minmax(0, 1fr) 150px 210px 76px 76px 64px; gap: var(--space-1) var(--space-4); align-items: start;
  padding: var(--space-1) 0; border-bottom: 1px solid var(--line); font-size: var(--text-base); }
.delivery__epic, .delivery__event { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.delivery__at, .delivery__epic, .delivery__fig { font: 400 var(--text-sm) var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.delivery__fig { text-align: right; }
/* the rows' head: their labels over the same columns, above the line of days */
.delivery--head { margin: var(--space-4) 0 0 calc(var(--space-2) + var(--space-4)); border-bottom-color: var(--line); padding-bottom: var(--space-1); }
.delivery__label { white-space: nowrap; }
.delivery__label--num { text-align: right; }
.delivery > :not(.delivery__what) { padding-top: var(--space-1); }
.domain-node { position: relative; margin: var(--space-4) 0 var(--space-2); font: 600 var(--text-base) var(--display); }
.domain-node__dot { position: absolute; left: -27px; top: .45em; width: 10px; height: 10px; border-radius: var(--radius-round); background: var(--brand); box-shadow: 0 0 0 3px var(--panel); }
.hint--prose { font: 400 var(--text-sm) var(--body); }
/* a kind and its terms on one baseline; a term as tall as its words, never the row */
.facts { display: grid; grid-template-columns: max-content 1fr; gap: var(--space-2) var(--space-3); margin: 2px 0 0; align-items: baseline; }
.facts__terms { margin: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-1); }
.proposal { border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-3); margin-bottom: var(--space-2); display: grid; gap: var(--space-1); min-width: 0; }
.proposal__goal { font: 600 var(--text-base) var(--display); }
.proposal__facts { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; font-size: var(--text-sm); color: var(--muted); }
.event--wrap { white-space: normal; overflow-wrap: anywhere; }
.aside { margin-top: var(--space-4); padding: var(--space-1) var(--space-4) var(--space-2); border-left: 4px solid var(--wait); border-radius: var(--radius-control); background: var(--panel); }
.trail { list-style: none; margin-top: var(--space-4); border-top: 1px solid var(--line); }
.trail__item { display: grid; grid-template-columns: 1.4em minmax(0, 1fr) auto; gap: var(--space-1) var(--space-3); align-items: baseline; padding: var(--space-3) 0; border-bottom: 1px solid var(--line); }
.trail__item:last-child { border-bottom: 0; }
.trail__glyph { color: var(--brand-text); }
.trail__words { min-width: 0; }
.trail__words q { font-style: italic; }
.trail__state { display: block; font: 400 var(--text-sm) var(--mono); color: var(--tone, var(--muted)); margin-top: 2px; }
.trail__state[data-state="wait"] { color: var(--muted); }
.trail__acts { display: flex; gap: var(--space-2); flex-wrap: wrap; justify-content: flex-end; }
.tab { font: 400 var(--text-sm) var(--mono); letter-spacing: .4px; color: var(--bar-dim); background: none; border: 0;
  padding: var(--space-2) var(--space-3); cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.tab:hover { color: var(--brand); }
.tab[aria-selected="true"] { color: var(--bar-ink); border-bottom-color: var(--brand); }
.tab:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
/* the keys show while the bar is worked by keyboard, never for a mouse */
.tab__key { display: none; margin-right: var(--space-2); color: var(--brand); font-size: var(--text-xs); }
.tabs:has(:focus-visible) .tab__key { display: inline; }
.tab__n { display: inline-block; min-width: 18px; margin-left: var(--space-2); padding: 0 var(--space-1); border-radius: var(--radius-control); background: var(--brand-fill);
  color: var(--brand-ink); font-size: var(--text-xs); text-align: center; }
.step__word { font: 600 var(--text-md) var(--display); color: var(--brand-text); margin-right: var(--space-2); }
.prose { font-size: var(--text-base); }
.prose p, .prose ul, .prose ol { margin: 0 0 var(--space-2); }
.prose table { width: auto; margin: var(--space-1) 0 var(--space-3); font-size: var(--text-base); }
.prose td, .prose th { padding: var(--space-1) var(--space-3) var(--space-1) 0; }
.prose pre { font: var(--text-sm)/1.5 var(--mono); background: var(--code); border-radius: var(--radius-control); padding: var(--space-3) var(--space-3); overflow-x: auto; margin: var(--space-1) 0 var(--space-3); }
.prose h4 { font: 600 var(--text-md) var(--display); margin: var(--space-3) 0 var(--space-1); }
.prose ul, .prose ol { padding-left: 1.3em; }
.prose li { margin: 2px 0; }

/* === organisms ================================================================================================ */
.card { margin-top: var(--space-5); background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-5) var(--space-5); }
.card__title { font: 700 var(--text-xl)/1.25 var(--display); letter-spacing: -.3px; display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap; }
.card__sub { font: 400 var(--text-sm) var(--mono); color: var(--muted); letter-spacing: .2px; }
.card--wish .ask { margin-top: var(--space-4); }
/* the one fold: a button over its region — a row, a quiet line, a group, an ink row, an epic's panel, a whole card */
.accordion__heading { font: inherit; margin: 0; }
/* the caret's column and the gap after it: the body starts where the title does, clear of an open row's edge */
.accordion { --fold-inset: var(--space-2); --fold-indent: calc(var(--fold-inset) + 14px + var(--space-3)); }
.accordion__head { display: grid; grid-template-columns: minmax(14px, max-content) minmax(0, 1fr) max-content; gap: var(--space-1) var(--space-3); align-items: baseline; width: 100%;
  background: none; border: 0; padding: var(--space-2) var(--space-1) var(--space-2) var(--fold-inset); text-align: left; color: var(--ink); cursor: pointer; font: 400 var(--text-base) var(--body); }
.accordion__head:hover .accordion__title { color: var(--brand-text); }
.accordion__head:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; border-radius: var(--radius-control); }
.accordion__title { min-width: 0; display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; }
.accordion__meta { display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; justify-content: flex-end; font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.accordion__below { grid-column: 2 / -1; display: flex; gap: var(--space-2); flex-wrap: wrap; }
.accordion__body { padding: 2px var(--space-1) var(--space-3) var(--fold-indent); }
/* a row in a list — of rules, of scenarios: no lines, its caret at the list's edge, an open row's edge clear before it */
.accordion--row { --fold-inset: var(--space-2); margin-left: calc(-1 * var(--space-2)); }
.accordion--row > .accordion__head { padding-top: var(--space-1); padding-bottom: var(--space-1); }
.accordion--row[data-open] { box-shadow: inset 3px 0 0 var(--brand); background: color-mix(in srgb, var(--brand) 5%, transparent); }
.accordion--quiet > .accordion__head { display: inline-flex; width: auto; padding: 2px 0; font: 500 var(--text-sm) var(--mono); color: var(--brand-text); margin-top: var(--space-2); }
.accordion--quiet > .accordion__head { --muted: currentColor; }
.accordion--quiet > .accordion__body { padding: var(--space-1) 0 0; }
/* a feature group: its rules, its scenarios' titles, its field and its button on one line — the group title's */
.accordion--group { border: 1px solid var(--group-line); border-radius: var(--radius-control); margin-top: var(--space-2); background: var(--panel); }
.accordion--group > .accordion__head { padding: var(--space-2) var(--space-3); background: var(--group); border-radius: var(--radius-control); font: 600 var(--text-base) var(--display); }
.accordion--group[data-open] > .accordion__head { border-radius: var(--radius-control) var(--radius-control) 0 0; }
.accordion--group[data-open] > .accordion__head { --caret-open: var(--brand-text); }
.accordion--group > .accordion__body { padding: 0 0 var(--space-2); }
/* a rule and its scenarios: one block, the rule a heading on the group's line, its scenarios beneath it — their carets
   under the rule's words, no line between them; a line between two rules */
.rule-block { padding: var(--space-3) var(--space-3) var(--space-2) var(--fold-title); }
.rule-block + .rule-block { border-top: 1px solid var(--line); }
.rule-block__rule { margin: 0 0 var(--space-2); font: italic 500 var(--text-md)/1.45 var(--body); color: var(--muted); }
.rule-block__rows { list-style: none; }
.actions--indent { padding: 0 var(--space-3) var(--space-1) var(--fold-title); }
.accordion--ink { border-bottom: 1px solid var(--line); }
.accordion--ink > .accordion__head { padding: var(--space-3) var(--space-2); font-size: var(--text-base); }
.accordion--ink > .accordion__head:hover { background: var(--soft); }
.accordion--ink .accordion__title b { font: 500 var(--text-base) var(--display); }
.accordion--ink[data-open] > .accordion__head { background: var(--ink); color: var(--paper); border-radius: var(--radius-label) var(--radius-label) 0 0; box-shadow: inset 0 4px 0 var(--brand);
  --muted: color-mix(in srgb, var(--paper) 70%, transparent); --caret-open: color-mix(in srgb, var(--paper) 70%, transparent); }
.accordion--ink[data-open] > .accordion__head .accordion__title b { font-weight: 700; color: var(--paper); }
.accordion--ink > .accordion__body { padding: var(--space-1) 0 var(--space-2); }
/* a fold table: the rows share the table's columns through subgrid, the head row's labels above them (WP-181) */
.fold-table { display: grid; grid-template-columns: var(--fold-cols); column-gap: var(--space-4); margin-top: var(--space-3); }
.fold-table__head, .fold-table > .accordion, .fold-table > .accordion > .accordion__head { grid-column: 1 / -1; display: grid; grid-template-columns: subgrid; }
.fold-table > .accordion > .accordion__body { grid-column: 1 / -1; }
.fold-table__head { column-gap: var(--space-4); padding: var(--space-1) var(--space-2); border-bottom: 1px solid var(--line); }
.fold-table > .accordion > .accordion__head { column-gap: var(--space-4); align-items: baseline; }
.fold-table__label--num, .accordion__cell--num { text-align: right; }
.accordion__cell { min-width: 0; font: 400 var(--text-base)/1.45 var(--body); }
.accordion__cell--num { font: 400 var(--text-sm) var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
.accordion__cell b { font: 500 var(--text-base) var(--display); }
.id--line { display: block; }
/* a context's subdomain on a line of its own, under its name, at the name's edge — every row alike */
.pill--line { display: block; width: fit-content; margin: var(--space-1) 0 0; }
.accordion--ink[data-open] > .accordion__head .accordion__cell { color: var(--paper); }
.accordion--ink[data-open] > .accordion__head .accordion__cell--num { color: color-mix(in srgb, var(--paper) 70%, transparent); }
.accordion--panel { border-radius: var(--radius-control); background: var(--panel); border: 1px solid var(--line); overflow: hidden; margin-top: var(--space-2); }
.accordion--panel > .accordion__head, .accordion--panel > .accordion__heading > .accordion__head { padding: var(--space-2) var(--space-3) 0; background: var(--soft); }
.accordion--panel .accordion__below { grid-column: 1 / -1; margin: var(--space-1) calc(-1 * var(--space-3)) 0; display: block; }
.accordion--panel > .accordion__body { padding: var(--space-4) var(--space-3) var(--space-3); }
.accordion--card { margin-top: var(--space-5); background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-4) var(--space-5); }
.accordion--card > .accordion__heading .accordion__head { font: 700 var(--text-xl)/1.25 var(--display); letter-spacing: -.3px; }
.accordion--card > .accordion__body { padding: var(--space-1) 0 var(--space-2); }
.board { display: grid; grid-template-columns: repeat(var(--grid-columns), minmax(0, 1fr)); margin-top: var(--space-5); align-items: stretch; }
.board__slot { display: flex; align-items: stretch; grid-column: span 3; }
.board__slot + .board__slot::before { content: "→"; align-self: center; padding: 0 var(--space-2); color: var(--muted); font: 400 var(--text-lg) var(--mono); }
.column { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-4); }
.column--hot { border-color: var(--wait); box-shadow: inset 0 3px 0 var(--wait); }
.column__head { font: 700 var(--text-read) var(--display); display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-2); margin: 0; }
.column__count { font: 700 var(--text-2xl) var(--display); }
.column__of { font: 500 var(--text-md) var(--mono); color: var(--muted); }
.column__line { display: flex; align-items: center; gap: var(--space-2); font: 400 var(--text-sm)/1.3 var(--mono); color: var(--muted); min-height: 16px; margin-top: 2px; }
.column__item { margin-top: var(--space-3); font-size: var(--text-base); }
.column__item + .column__item { margin-top: var(--space-2); }
.link--ink { font: inherit; color: var(--ink); text-decoration: none; }
.link--ink:hover { color: var(--brand-text); }
.list { list-style: none; margin-top: var(--space-3); }
.lanes { display: grid; grid-template-columns: repeat(var(--grid-columns), minmax(0, 1fr)); gap: var(--space-2); }
.lanes > .lane { grid-column: span 3; }
/* a lane carries its state's colour as a rule along its top; an empty one says so quietly */
.lane { background: var(--paper); border-radius: var(--radius-label); padding: var(--space-2); min-width: 0; border-top: 3px solid var(--line); }
.lane[data-state="draft"] { border-top-color: var(--muted); }
.lane[data-state="approved"] { border-top-color: color-mix(in srgb, var(--info) 45%, var(--line)); }
.lane[data-state="running"] { border-top-color: var(--wait); }
.lane[data-state="delivered"] { border-top-color: var(--ok); }
.lane[data-state="delivered"]:not([data-bare]) { background: color-mix(in srgb, var(--ok) 7%, var(--paper)); }
.lane[data-bare] .lane__head { opacity: .55; }
.lane__cards { list-style: none; }
.lane__head { display: flex; justify-content: space-between; margin: 0 0 var(--space-2); }
.epic__title { font: 600 var(--text-base) var(--display); }
.stepper { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: var(--space-1); padding: 0 var(--space-3) var(--space-3); }
.stepper__step { text-align: center; font: 500 var(--text-xs) var(--mono); color: var(--muted); }
.stepper__bar { display: block; height: 8px; border-radius: var(--radius-label); background: var(--line); margin-bottom: var(--space-1); }
.stepper__step[data-state="done"] .stepper__bar { background: var(--ok); }
.stepper__step[data-state="stopped"] { color: var(--stop); font-weight: 600; }
.stepper__step[data-state="stopped"] .stepper__bar { background: var(--stop); }
.stepper__step[data-state="now"] { color: var(--ink); font-weight: 600; }
/* the run's control: one capsule on the bar — the dot and its word open the panel, the action stands beside them */
.run-control { display: flex; align-items: center; gap: var(--space-1); padding: var(--space-1); border: 1px solid var(--bar-rule); border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--bar-ink) 5%, var(--bar)); }
.run-control[data-state="up"] { border-color: color-mix(in srgb, var(--run) 45%, var(--bar)); }
.run-control[data-state="stopping"] { border-color: color-mix(in srgb, var(--wait) 55%, var(--bar)); }
.run-control__say { font: 400 var(--text-sm) var(--mono); }
.run-control__say b { color: var(--bar-ink); font-weight: 500; }
.run-panel { display: grid; gap: var(--space-3); }
.run-panel__story { display: grid; gap: var(--space-1); padding-bottom: var(--space-3); border-bottom: 1px solid var(--line); }
.run-panel__head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
.run-panel__line { margin: 0; font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.run-panel__line b { color: var(--ink); font-weight: 500; }
.stepper__step[data-state="now"] .stepper__bar { background: var(--wait); animation: pulse 1.5s infinite; }
.course { border: 1px solid var(--line); border-radius: var(--radius-control); overflow: hidden; margin-top: var(--space-3); }
.course__top { display: flex; justify-content: space-between; gap: var(--space-3); padding: var(--space-2) var(--space-3); align-items: baseline; flex-wrap: wrap; }
.course__right { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.course__doing { padding: var(--space-2) var(--space-3); font: 400 var(--text-sm) var(--mono); color: var(--muted); border-top: 1px solid var(--line); }
.queue { list-style: none; display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center; margin-top: var(--space-3); }
/* decide: the question on a tinted head, its answers as rows, the recommended one framed */
.record { margin-top: var(--space-5); background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); overflow: hidden; }
.record__question { padding: var(--space-3) var(--space-4); background: color-mix(in srgb, var(--wait) 12%, var(--panel)); border-bottom: 1px solid var(--line); }
.record--accept .record__question { background: color-mix(in srgb, var(--brand) 10%, var(--panel)); }
.record__text { font: 600 var(--text-read)/1.3 var(--display); display: block; margin-top: 2px; }
.record__body { padding: var(--space-3) var(--space-4) var(--space-4); }
.record__body > .id:last-child { margin-top: var(--space-3); }
.options { list-style: none; display: grid; grid-template-columns: minmax(64px, max-content) minmax(0, 1fr); gap: var(--space-2); margin-top: var(--space-3); }
.tiles { display: grid; grid-template-columns: repeat(var(--grid-columns), minmax(0, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
.tiles > .tile { grid-column: span 3; }
.tiles--many { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.tiles--many > .tile { grid-column: auto; }
.days { border-left: 2px solid var(--line); margin: var(--space-2) 0 0 var(--space-2); padding-left: var(--space-4); display: grid; gap: var(--space-3); }
.days__day { position: relative; }
.days__day::before { content: ""; position: absolute; left: -22px; top: 5px; width: 10px; height: 10px; border-radius: 50%; background: var(--ok); }
.days__date { margin: 0; font: 600 var(--text-sm) var(--mono); color: var(--muted); margin-bottom: 2px; }
.domain { margin: var(--space-1) 0 var(--space-2); }
.domain__track { border-left: 2px solid var(--line); margin: var(--space-3) 0 0 var(--space-3); padding-left: var(--space-5); }
.kernel { border: 1px solid color-mix(in srgb, var(--shared) 35%, var(--line)); border-top: 4px solid var(--shared); border-radius: var(--radius-label) var(--radius-label) var(--radius-control) var(--radius-control);
  padding: var(--space-3) var(--space-4) var(--space-3); margin: var(--space-3) 0 var(--space-1); background: color-mix(in srgb, var(--shared) 5%, var(--panel)); }
.kernel__top { display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap; margin-bottom: var(--space-2); }
.kernel__title { margin: 0; font: 700 var(--text-lg) var(--display); color: var(--shared); }
.proposals { list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-2); }
.rule-group { margin-top: var(--space-4); }
.rule-group__rows { list-style: none; }
.rule-group__label { margin-bottom: var(--space-1); }
.rule-group__n { font: 500 var(--text-xs) var(--mono); color: var(--ink); margin-left: var(--space-1); }
/* a stage's parts as the domain's rule blocks: a line between two, no rail at the side */
.part { padding: var(--space-4) 0 var(--space-2); }
.part + .part { border-top: 1px solid var(--line); }
.part--aside > .part__head { font-size: var(--text-md); color: var(--muted); }
.part__head { font: 600 var(--text-base) var(--display); display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; margin: 0; }
.part .rule-group:first-of-type { margin-top: var(--space-2); }
/* a rule's caret under its group's label, its title a step in — as a scenario under its rule */
.ways { list-style: none; }
.ways__row { display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap; padding: var(--space-1) 0; }
.ways__rules { font: 400 var(--text-base) var(--body); color: var(--muted); }
/* how a check ends: the pass and the fail, each its mark and where the story goes, what happens then beneath */
.outcome { margin-top: var(--space-4); }
.outcome__head { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; margin: 0; font: 600 var(--text-base) var(--display); }
.outcome__head b { color: var(--brand-text); }
.icon--large { width: var(--mark-large); height: var(--mark-large); margin: 0; }
/* what follows an outcome stands under its words, after its mark: the outcome reads as the heading it is */
.outcome__body { padding-left: calc(var(--mark-large) + var(--space-2)); }
.outcome .rule-group { margin-top: var(--space-2); }
.table { margin-top: var(--space-3); }
.table__num { text-align: right; font-family: var(--mono); font-size: var(--text-sm); white-space: nowrap; font-variant-numeric: tabular-nums; }
.table__act .actions { margin-top: 0; }
.table__mark { width: 1.6em; }
.terminal { font: var(--text-sm)/1.5 var(--mono); background: var(--terminal); color: var(--terminal-ink); border-radius: var(--radius-control); padding: var(--space-3); max-height: 460px; overflow: auto;
  white-space: pre-wrap; word-break: break-word; margin-top: var(--space-3); }
.terminal:empty { display: none; }
/* delivered over time: two panels on one time axis — cost above, tokens below, never two scales on one axis */
.curve { position: relative; margin-top: var(--space-4); }
.curve svg { display: block; width: 100%; height: auto; }
.curve__grid { stroke: var(--line); stroke-width: 1; }
.curve__axis { font: 400 var(--text-xs) var(--mono); fill: var(--muted); }
.curve__name { font: 600 var(--text-xs) var(--mono); fill: var(--muted); letter-spacing: .06em; text-transform: uppercase; }
.curve__end { font: 600 var(--text-sm) var(--mono); fill: var(--ink); }
.curve__area { fill: color-mix(in srgb, var(--brand) 12%, transparent); }
.curve__line { fill: none; stroke: var(--brand); stroke-width: 2; stroke-linejoin: round; }
.curve__cross { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 3; }
.curve__dot { fill: var(--brand); stroke: var(--panel); stroke-width: 2; }
.curve__tip { position: absolute; pointer-events: none; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-control);
  box-shadow: var(--shadow); padding: var(--space-2) var(--space-3); font: 400 var(--text-sm) var(--mono); color: var(--ink); max-width: 320px; }
.curve__title { display: block; font: 600 var(--text-md) var(--display); margin-bottom: var(--space-1); }
.curve__row { display: flex; justify-content: space-between; gap: var(--space-4); color: var(--muted); }
.curve__row span:last-child { color: var(--ink); }
/* the flow, drawn by the factory: a way back shown on a hover, a step, a gate or an edge picked by a click — the
   classes below `.flow` are the drawing's own */
.flow { overflow-x: auto; margin-top: var(--space-3); }
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
.page-head__eyebrow { font: 400 var(--text-sm) var(--mono); letter-spacing: 2.5px; text-transform: uppercase; color: var(--brand-text); margin-bottom: var(--space-3); }
.page-head__title { font: 700 clamp(var(--text-2xl), 4vw, var(--text-3xl))/1.1 var(--display); letter-spacing: -1px; }
.page-head__lede { margin-top: var(--space-3); color: var(--muted); max-width: 44em; font-size: var(--text-lg); }
.drawer-frame h2 { font: 600 var(--text-base) var(--display); margin: var(--space-5) 0 var(--space-2); }
.drawer-frame__close { float: right; }
.drawer-frame > .actions { margin: var(--space-4) 0 var(--space-5); }
.drawer-frame .ask { margin: var(--space-2) 0 var(--space-5); }
.gallery { margin-top: var(--space-4); }
.gallery__level { margin-top: var(--space-6); }
.gallery__title { font: 700 var(--text-xl) var(--display); text-transform: capitalize; border-bottom: 1px solid var(--line); padding-bottom: var(--space-2); }
.gallery__item { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: var(--space-4); padding: var(--space-4) 0; border-bottom: 1px solid var(--line); }
.gallery__name { margin: 0; font: 500 var(--text-sm) var(--mono); color: var(--brand-text); padding-top: var(--space-1); }
.gallery__show { min-width: 0; }
.gallery__show > .card:first-child, .gallery__show > .record:first-child, .gallery__show > .board:first-child,
.gallery__show > .accordion--card:first-child, .gallery__show > .notice:first-child { margin-top: 0; }

/* === the narrow screen ======================================================================================== */
@media (prefers-reduced-motion: reduce) { .caret { transition: none; } .spinner, .stepper__step[data-state="now"] .stepper__bar { animation: none; } .flow .way-back { transition: none; } }
/* the frame answers the window; a component answers the place it stands in — the main region, the drawer, a column
   of the pattern library — so one placed in the drawer takes the narrow layout on a wide screen too (WP-181) */
@media (max-width: 760px) {
  .wrap { padding: 0 var(--space-4); }
  .field--bar { width: 100px; }
}
@container (width < 760px) {
  .board__slot { grid-column: span 12; flex-direction: column; }
  .board__slot + .board__slot::before { content: "↓"; padding: var(--space-1) 0; }
  .lanes > .lane, .tiles > .tile { grid-column: span 6; }
  .hide-narrow { display: none; }
  .fold-table__head { display: none; }
  td, th { padding: var(--space-2) var(--space-1); }
  .delivery { grid-template-columns: 44px minmax(0, 1fr) auto; } .delivery__epic { display: none; } .delivery--head { display: none; }
  .delivery__event { grid-column: 2 / -1; grid-row: 2; } .delivery__fig + .delivery__fig { grid-column: 3; grid-row: 2; }
  .gallery__item { grid-template-columns: 1fr; gap: var(--space-2); }
  /* a row with buttons: its cells side by side, the buttons on a line of their own beneath */
  tr:has(> td.table__act) { display: grid; grid-template-columns: auto 1fr fit-content(40%); border-bottom: 1px solid var(--line); }
  tr:has(> td.table__act) > td { border-bottom: 0; } tr:has(> td.table__act) > td.hide-narrow { display: none; }
  td.table__act { grid-column: 1 / -1; padding-top: 0; } td.table__act:empty { display: none; }
  td.table__act .actions { justify-content: flex-start; }
  table:has(td.table__act) tr:has(> th) { display: none; }
}
"""
