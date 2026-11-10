"""The page's stylesheet (WP-180), by level: the base and the frame, then primitives, components (parts, then sections), templates.

Every class is a BEM block of a component in `page_ui.py` (or of the page's frame, `FRAME_BLOCKS`), an element of one
(`block__element`) or a variant (`block--variant`); a state the factory names is selected as `[data-state="…"]`, never
as a class. Colours come from the tokens alone (`page_tokens.py`) — no colour is written here as a value.
"""

#: The one width at which the page narrows — the frame for the window, a component for its container (WP-181).
NARROW = "760px"
#: The one wider width (WP-183): the main region's content from which a view takes two columns.
WIDE = "1500px"
#: The width from which a part's sections stand beside its text: their longest name, a gap and a reading measure —
#: the reader's own, from what it holds, not the page's two columns.
READER = "920px"

#: The blocks of the page's frame — the bar, the main region, the drawer — written in the page itself, not by a
#: component; and the few utilities a component may add beside its block.
FRAME_BLOCKS = ("topbar", "brand", "tabs", "banner", "main", "toasts", "drawer", "wrap", "sr", "hide-narrow")

#: The cascade's order, said once before any rule (WP-182): a later layer wins over an earlier one whatever their
#: selectors weigh; a theme file, linked after the page's style and unlayered, wins over all of them.
LAYERS = "@layer reset, base, tokens, layout, components, utilities;"

STYLE = """
@layer reset {
* { margin: 0; padding: 0; box-sizing: border-box; }
}
@layer base {
/* === base ===================================================================================================== */
body { background: var(--paper); color: var(--ink); font: var(--text-read)/1.55 var(--body); min-height: 100vh; }
a { color: var(--brand-text); text-decoration: none; }
button:focus-visible, a:focus-visible, textarea:focus-visible, select:focus-visible, input:focus-visible {
  outline: 3px solid var(--brand); outline-offset: 2px; border-radius: var(--radius-label); }
code { font-family: var(--mono); font-size: .78em; background: var(--code); padding: 1px var(--space-1); border-radius: var(--radius-label); overflow-wrap: anywhere; }
.wrap { max-width: var(--measure); margin: 0 auto; padding: 0 clamp(var(--space-5), 3vw, var(--space-7)); }
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
}
@layer layout {
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
/* the wordmark: the part before the dot in the bar's ink, the dot and what follows in the accent, never wrapped apart */
.brand__name { white-space: nowrap; }
.brand__accent { color: var(--brand); }
.brand__project { font: 400 var(--text-sm) var(--mono); color: var(--bar-dim); letter-spacing: .3px; margin-inline-start: var(--space-1); }
.tabs { display: flex; align-items: center; gap: var(--space-1); overflow-x: auto; scrollbar-width: none; }
.tabs > :first-child > .tab:first-child, .tabs > .tab:first-child { margin-inline-start: calc(-1 * var(--space-3)); }
.tabs__group { display: flex; align-items: center; }
.tabs__sep { flex: none; width: 1px; height: 16px; margin: 0 var(--space-2); background: var(--bar-faint); }
.tabs__arrow { color: var(--bar-faint); font: 400 var(--text-sm) var(--mono); }
.topbar__tools { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
/* the banner heads the bar, so it stays in sight as the bar does; its ground a tint of what it says, apart from the bar's */
.banner { color: var(--bar-ink); font: 500 var(--text-md) var(--display); padding: var(--space-2) 0; border-bottom: 1px solid; }
.banner[data-state="stop"] { background: color-mix(in srgb, var(--stop) 28%, var(--bar)); border-bottom-color: var(--stop); }
.banner[data-state="info"] { background: color-mix(in srgb, var(--info) 22%, var(--bar)); border-bottom-color: var(--info); }
.main, .drawer, .gallery__show { container-type: inline-size; }
.main { padding-top: var(--space-7); padding-bottom: var(--space-8); }
.toasts { position: fixed; right: 16px; bottom: 16px; z-index: 40; display: flex; flex-direction: column; gap: var(--space-2); max-width: min(440px, calc(100% - 32px)); }
.drawer { position: fixed; inset: var(--bar-height, 0px) 0 0 auto; width: min(760px, 100%); z-index: 15; background: var(--paper);
  border-inline-start: 1px solid var(--line); box-shadow: var(--shadow); overflow-y: auto; padding: var(--space-5); }
}
@layer components {
/* === primitives =============================================================================================== */
/* a control is pressed, a display is read: a control is a raised rectangle in the display face, a display flat, in the
   mono face, never with an edge — the accent alone tells neither (the brand's controls and displays) */
/* a press in three sizes (`--control-s|m|l`), its height fixed so a glyph or an icon never makes it taller */
.btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2); block-size: var(--control-m);
  font: 600 var(--text-md)/1 var(--display); padding: 0 var(--space-4); border-radius: var(--radius-control); border: 1px solid var(--control-edge);
  background: var(--panel); color: var(--ink); cursor: pointer; white-space: nowrap; box-shadow: var(--lift); vertical-align: middle; }
.btn--s { block-size: var(--control-s); font-size: var(--text-sm); padding: 0 var(--space-3); gap: var(--space-1); }
.btn--l { block-size: var(--control-l); font-size: var(--text-base); padding: 0 var(--space-5); }
/* a press's marks are drawn, not typed: a glyph's ink sits where its font puts it, a drawing in the middle of its box */
.btn::before, .btn::after, .btn__icon { flex: none; inline-size: .85em; block-size: .85em; background-color: currentColor;
  mask: var(--btn-mark) center / contain no-repeat; }
.btn::before, .btn::after { content: none; }
.btn__icon--play { --btn-mark: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='black'%3E%3Cpath d='M4.5 2.75v10.5L13 8Z'/%3E%3C/svg%3E"); }
.btn__icon--stop { --btn-mark: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='black'%3E%3Crect x='3.5' y='3.5' width='9' height='9' rx='1.5'/%3E%3C/svg%3E"); }
.btn:active:not(:disabled) { transform: translateY(1px); box-shadow: none; }
.btn:hover { border-color: var(--brand); color: var(--brand-text); }
.btn:disabled { opacity: .5; cursor: default; }
.btn--primary { background: var(--brand-fill); border-color: var(--brand-fill); color: var(--brand-ink); box-shadow: var(--lift-brand); }
.btn--primary::after { content: ""; --btn-mark: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M2.5 8h11M9.5 4l4 4-4 4'/%3E%3C/svg%3E"); }
.btn--primary:hover { background: var(--brand-fill-hover); border-color: var(--brand-fill-hover); color: var(--brand-ink); }
.btn--plain::after { content: none; }
.btn--write::before { content: ""; --btn-mark: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='black'%3E%3Cpath d='M8 1.5 9.5 6.5 14.5 8 9.5 9.5 8 14.5 6.5 9.5 1.5 8 6.5 6.5Z'/%3E%3C/svg%3E"); background-color: var(--brand-text); }
.btn--primary.btn--write::before { background-color: var(--brand-ink); }
.btn--danger:hover { border-color: var(--stop); color: var(--stop); }
.btn--bar { font-weight: 500; color: var(--bar-ink); background: none; border-color: var(--bar-faint); box-shadow: none; }
.btn--bar:hover { border-color: var(--brand); color: var(--brand); }
.btn--bar.btn--primary { background: var(--brand-fill); border-color: var(--brand-fill); color: var(--brand-ink); }
.link { background: none; border: 0; padding: 0; text-align: start; font: inherit; color: var(--brand-text); cursor: pointer;
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
.switch__opt + .switch__opt { border-inline-start: 1px solid var(--line); }
.switch__opt:hover:not(:disabled) { color: var(--brand-text); }
.switch__opt:disabled:not([aria-pressed="true"]) { opacity: .45; cursor: default; }
.switch__opt:disabled { cursor: default; }
.switch__opt[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
.switch__n { font: 400 var(--text-xs) var(--mono); margin-inline-start: var(--space-1); opacity: .7; }
.switch--bar { background: none; border-color: var(--bar-faint); border-radius: var(--radius-control); }
.switch--bar .switch__opt { font: 400 var(--text-sm) var(--mono); color: var(--bar-dim); padding: var(--space-1) var(--space-2); }
.switch--bar .switch__opt + .switch__opt { border-inline-start-color: var(--bar-faint); }
.switch--bar .switch__opt[aria-pressed="true"] { background: var(--bar-rule); color: var(--bar-ink); }
/* a select draws its own chevron, a step clear of its edge, and keeps the text clear of it */
.select { appearance: none; block-size: var(--control-m); font: 400 var(--text-sm) var(--mono); color: var(--ink); background-color: var(--paper);
  border: 1px solid var(--line); border-radius: var(--radius-control); padding: 0 calc(var(--space-3) + var(--space-4)) 0 var(--space-3);
  background-image: linear-gradient(45deg, transparent 50%, var(--muted) 50%), linear-gradient(135deg, var(--muted) 50%, transparent 50%);
  background-size: 5px 5px; background-repeat: no-repeat;
  background-position: right calc(var(--space-3) + 5px) center, right var(--space-3) center; }
.field { block-size: var(--control-m); font: 400 var(--text-md) var(--mono); color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius-control); padding: 0 var(--space-3); width: 100%; }
.field--area { block-size: auto; min-height: 72px; resize: vertical; font: var(--text-read)/1.5 var(--body); padding: var(--space-3) var(--space-3); }
.field[aria-invalid="true"] { border-color: var(--stop); }
.field--bar { block-size: var(--control-s); font: 400 var(--text-sm) var(--mono); color: var(--bar-ink); background: var(--bar-rule); border-color: var(--bar-faint); border-radius: var(--radius-control); padding: 0 var(--space-2); width: 170px; }
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
/* a word that stands out: the line it stands in sets its face, weight and ink (`--em-face`, `--em-weight`, `--em-ink`) */
.em { font-family: var(--em-face, inherit); font-weight: var(--em-weight, 700); color: var(--em-ink, inherit); }
.error { display: inline-block; font: 400 var(--text-md) var(--body); color: var(--stop); }
.error--block { display: block; margin: var(--space-2) 0; }
.term { font: 500 var(--text-sm) var(--mono); padding: 2px var(--space-2); border-radius: var(--radius-label); background: var(--tint); color: var(--brand-text); cursor: help;
  /* one line where it fits; a term wider than its line — failures under one name — wraps inside, never past its card */
  max-width: 100%; overflow-wrap: anywhere; }
.term--minor { background: transparent; box-shadow: inset 0 0 0 1px var(--brand); }
/* a term of the shared kernel, in a context or in the kernel's own block: never a context's accent */
.term--shared { background: color-mix(in srgb, var(--shared) 14%, transparent); color: var(--shared); }
.term--shared::before { content: "⇄ "; font-size: var(--text-xs); }
/* the chip reads on its words' baseline beside other text; its mark stands in the middle of it */
.event { display: inline-flex; align-items: baseline; gap: var(--space-1); font: 500 var(--text-sm) var(--mono); padding: 1px var(--space-2); border-radius: var(--radius-round); background: var(--tint); color: var(--brand-text); white-space: nowrap; }
.event::before { content: "◆"; font-size: .7em; line-height: 1; align-self: center; }
.state { font: 600 var(--text-xs) var(--mono); letter-spacing: .07em; text-transform: uppercase; padding: 2px var(--space-2); border-radius: var(--radius-round); white-space: nowrap;
  color: var(--tone, var(--muted)); background: color-mix(in srgb, var(--tone, var(--muted)) 14%, transparent); }
.mark { font: 700 var(--text-base) var(--display); display: inline-block; width: 1.3em; text-align: center; color: var(--tone, var(--muted)); }
.mark[data-state="running"], .mark[data-state="next"] { color: var(--run); }
.icon { width: 15px; height: 15px; vertical-align: -3px; margin-inline-end: 2px; }
.icon circle { stroke: none; fill: var(--muted); }
.icon path { fill: none; stroke: var(--brand-ink); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.icon[data-state="pass"] circle { fill: var(--pass); } .icon[data-state="fail"] circle { fill: var(--fail); }
.icon[data-state="minor"] path { stroke: var(--muted); }
.num { font: 700 var(--text-2xl)/1.1 var(--display); font-variant-numeric: tabular-nums; }
.num__unit { font: 500 var(--text-sm) var(--mono); color: var(--muted); margin-inline-start: var(--space-1); }
.id { font: 400 var(--text-sm) var(--mono); color: var(--muted); overflow-wrap: anywhere; }
.id--block { display: block; margin-top: 2px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--bar-off); display: inline-block; margin-inline-end: var(--space-2); }
.dot[data-state="up"] { background: var(--info); box-shadow: 0 0 0 3px color-mix(in srgb, var(--info) 25%, transparent); }
.dot[data-state="stopping"] { background: var(--wait); }
.spinner { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--wait); margin-inline-end: var(--space-2); animation: pulse 1.2s infinite; }
@keyframes pulse { 50% { opacity: .35; } }
.meter { display: inline-block; height: 8px; min-width: 80px; flex: 1; border-radius: 0 var(--radius-label) var(--radius-label) 0; overflow: hidden; }
.meter__fill { display: block; height: 100%; background: var(--brand); min-width: 2px; border-radius: 0 var(--radius-label) var(--radius-label) 0; }
.meter--thin { height: 4px; border-radius: 2px; background: var(--soft); }
.meter--thin .meter__fill { background: var(--ok); }
.flag { font: 500 var(--text-xs) var(--mono); padding: 1px var(--space-2); border-radius: var(--radius-label); white-space: nowrap; background: color-mix(in srgb, var(--tone, var(--muted)) 22%, transparent); }
.pill { font: 600 var(--text-xs) var(--mono); letter-spacing: .08em; text-transform: uppercase; padding: 2px var(--space-2); border-radius: var(--radius-round); white-space: nowrap; margin-inline-start: var(--space-2); }
.pill--core { background: color-mix(in srgb, var(--brand) 28%, transparent); box-shadow: inset 0 0 0 1.5px var(--brand); color: var(--brand); }
.pill--supporting { box-shadow: inset 0 0 0 1.5px var(--brand); color: var(--brand); }
.pill--generic { box-shadow: inset 0 0 0 1.5px currentColor; opacity: .7; }
.empty { color: var(--muted); font-style: italic; margin-top: var(--space-2); }
.intro { color: var(--muted); margin: var(--space-2) 0 var(--space-2); font-size: var(--text-base); max-width: 48em; }
.note { color: var(--tone, var(--muted)); font-size: var(--text-base); margin-top: var(--space-1); }
.rule-id { font: 500 var(--text-xs) var(--mono); color: var(--muted); padding-inline-start: var(--space-2); white-space: nowrap; }
.rule-id--gate { border-inline-start: 3px solid var(--bar); } .rule-id--runner { border-inline-start: 3px solid var(--run); } .rule-id--instructed { border-inline-start: 3px solid var(--wait); }
.rule-id[data-state] { background: color-mix(in srgb, var(--tone, var(--muted)) 20%, transparent); }
.rule-id__refused { font-weight: 700; color: var(--stop); margin-inline-start: var(--space-1); }

/* === components: parts ======================================================================================== */
.form-row { margin-top: var(--space-3); }
.form-row .hint, .form-row .error { display: block; margin-top: var(--space-1); }
.form-row--inline { display: inline-flex; align-items: baseline; gap: var(--space-2); margin-top: 0; }
.form-row--inline .label { margin: 0; }
.form-row--inline { max-width: 100%; min-width: 0; }
.form-row--inline .select { min-width: 0; max-width: 26em; }
.label--bar { color: var(--bar-text); }
.ask { margin-top: var(--space-3); }
/* the files beside the words (WP-184): a chip each, a picture as a small preview */
.files { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--space-2); }
/* its words trimmed to their capitals and their baseline, so the same space above and below puts them in the middle,
   whatever a face's metrics leave beneath its letters */
.file-chip { display: inline-flex; align-items: baseline; gap: var(--space-2); padding: var(--space-2) 2px var(--space-2) var(--space-1); border: 1px solid var(--line);
  border-radius: var(--radius-control); background: var(--panel); font-size: var(--text-sm); max-width: 100%; }
.file-chip__kind, .file-chip__name, .file-chip__size, .file-chip__drop { text-box: trim-both cap alphabetic; }
.file-chip__preview { width: 28px; height: 28px; object-fit: cover; border-radius: calc(var(--radius-control) / 2); align-self: center; }
.file-chip__kind { font: 600 var(--text-xs) var(--mono); color: var(--muted); padding: 0 var(--space-1); }
.file-chip__name { overflow-x: clip; overflow-y: visible; text-overflow: ellipsis; white-space: nowrap; max-width: 22ch; }
.file-chip__size { font: 400 var(--text-xs) var(--mono); color: var(--muted); white-space: nowrap; }
.file-chip--busy { opacity: .7; } .file-chip--error { border-color: var(--fail); } .file-chip--error .file-chip__size { color: var(--fail); }
/* the drop stands on the words' baseline and keeps a press's reach, not its height: the chip is as tall as its words */
.file-chip__drop { border: 0; background: none; color: var(--muted); cursor: pointer; font-size: var(--text-md); padding: var(--space-1); margin-block: calc(-1 * var(--space-1)); }
.file-chip__drop:hover { color: var(--ink); }
/* a file dragged over the words: the whole place it lands in is marked */
.ask[data-over] { outline: 2px dashed var(--brand); outline-offset: 4px; border-radius: var(--radius-control); }
.ask .form-row:first-child { margin-top: 0; }
.ask__go { margin-top: var(--space-3); display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); }
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
.tile__said { display: block; font: 400 var(--text-sm) var(--mono); color: var(--muted); margin-top: 2px; }
/* a key and its value read on one baseline, whatever face each takes */
.kv { display: grid; grid-template-columns: max-content 1fr; align-items: baseline; gap: var(--space-1) var(--space-4); margin-top: var(--space-3); font-size: var(--text-base); }
.kv__key { font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.toast { background: var(--panel); color: var(--ink); border: 1px solid var(--line); border-inline-start: 4px solid var(--info); border-radius: var(--radius-control);
  padding: var(--space-3) var(--space-4); box-shadow: var(--shadow); font-size: var(--text-base); white-space: pre-wrap; }
.toast--error { border-inline-start-color: var(--danger); }
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
.said__kw { font: 600 var(--text-sm) var(--mono); color: var(--ink); margin-inline-end: var(--space-2); white-space: nowrap; }
.said__goes { font: 500 var(--text-sm) var(--mono); color: var(--brand-text); white-space: nowrap; }
.figures { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); font: 400 var(--text-sm) var(--mono); color: var(--muted); margin: 0 0 var(--space-3); }
.figures__value { color: var(--ink); font-weight: 600; }
.figures__value--alert { color: var(--stop); }
.bars { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content; gap: var(--space-2) var(--space-3); align-items: center; margin-top: var(--space-2); }
.bars__label { font: 500 var(--text-sm) var(--mono); color: var(--ink); }
.bars__n { font: 500 var(--text-sm) var(--mono); color: var(--muted); text-align: end; font-variant-numeric: tabular-nums; }
.toolbar { display: flex; gap: var(--space-2) var(--space-4); flex-wrap: wrap; align-items: center; margin-top: var(--space-3); }
.quiet-line { margin-top: var(--space-4); font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.link--quiet { font: inherit; text-decoration: none; }
.notice { margin-top: var(--space-5); display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; padding: var(--space-4) var(--space-4);
  border: 1px solid var(--line); border-inline-start: 4px solid var(--info); border-radius: var(--radius-card); background: var(--panel); }
.notice__text { flex: 1 1 280px; font: 500 var(--text-base) var(--display); }
.notice__arrow { color: var(--info); margin-inline-end: var(--space-2); }
.notice--ended { border-inline-start-color: var(--danger); }
.notice--ended .notice__arrow { color: var(--danger); }
.story-card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-2); margin-bottom: var(--space-2); font-size: var(--text-md); line-height: 1.35;
  box-shadow: inset 3px 0 0 var(--line); }
.link--compact { font-size: var(--text-md); }
.story-card .id { margin-top: var(--space-1); }
.story-card[data-state="delivered"] { box-shadow: inset 3px 0 0 var(--ok); }
.story-card[data-state="running"] { box-shadow: inset 3px 0 0 var(--wait); }
.story-card[data-state="stopped"] { box-shadow: inset 3px 0 0 var(--stop); }
.story-card[data-state="approved"] { box-shadow: inset 3px 0 0 color-mix(in srgb, var(--info) 40%, var(--line)); }
.story-card[data-state="draft"] { box-shadow: none; border-inline-start: 2px dashed var(--muted); }
.ticket { border-top: 1px solid var(--line); padding: var(--space-3) 0; font-size: var(--text-md); display: grid; gap: var(--space-1); min-width: 0; }
.ticket:first-child { border-top: 0; padding-top: 0; }
.ticket__what { display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; }
.ticket__what > .state { margin-inline-start: auto; }
.ticket__kind { font: 600 var(--text-sm) var(--mono); color: var(--brand-text); }
/* an option: its press, then what it means beside it — alone on two columns of its own, in a list on the list's */
.option { border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-3); font-size: var(--text-base); display: grid;
  grid-template-columns: minmax(64px, max-content) minmax(0, 1fr); gap: var(--space-1) var(--space-3); align-items: start; }
.options > .option { grid-column: 1 / -1; grid-template-columns: subgrid; }
.option__pick { grid-row: 1 / span 2; }
.option__pick .btn { min-width: 2.6em; }
.option .caption { grid-column: 2; }
.option__text { grid-column: 2; }
.option--advised { border-color: var(--brand); box-shadow: inset 0 0 0 1px var(--brand); }
.list__item { display: flex; gap: var(--space-3); align-items: baseline; padding: var(--space-2) 0; border-top: 1px solid var(--line); }
.list__item:first-child { border-top: 0; }
/* an item that opens as a whole: its title is the button, and the button's reach is the item */
.list__item--press { position: relative; padding-inline: var(--space-2); margin-inline: calc(-1 * var(--space-2)); border-radius: var(--radius-control); }
.list__item--press:hover { background: var(--soft); }
.list__item--press:has(.list__press:focus-visible) { outline: 2px solid var(--brand); outline-offset: -2px; }
.list__press { font: 500 var(--text-base) var(--display); color: var(--ink); background: none; border: 0; padding: 0; cursor: pointer; text-align: start; display: block; }
.list__press::after { content: ""; position: absolute; inset: 0; }
.list__press:focus-visible { outline: none; }
/* what a row offers besides opening stands above the row's reach */
.list__item--press .list__aside { position: relative; z-index: 1; align-self: center; }
.list__item--press:hover .list__press { color: var(--brand-text); }
/* the item open beside its list */
.list__item--press[aria-current="true"] { background: var(--soft); box-shadow: inset 3px 0 0 var(--brand); }
.list__item--press[aria-current="true"] .list__press { color: var(--brand-text); }
.list__what { flex: 1; min-width: 0; }
/* the row's end holds a press or a figure: never more than half the row, so the title keeps its width */
.list__aside { font: 400 var(--text-sm) var(--mono); color: var(--muted); white-space: nowrap; text-align: end; max-width: 50%; overflow: hidden; text-overflow: ellipsis; }
/* a delivery a row of fixed columns: when, what, its epic, its outcome event, how long, what it cost */
.delivery { display: grid; grid-template-columns: 44px minmax(0, 1fr) 150px 210px 76px 76px 64px; gap: var(--space-1) var(--space-4); align-items: baseline;
  padding: var(--space-1) 0; border-bottom: 1px solid var(--line); font-size: var(--text-base); }
/* a title that wraps keeps the row on its first line: as a block its baseline is its first line's, not its last */
.delivery__what > .link { display: block; }
.delivery__epic, .delivery__event { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.delivery__at, .delivery__epic, .delivery__fig { font: 400 var(--text-sm) var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.delivery__fig { text-align: end; }
/* the rows' head: their labels over the same columns, above the line of days */
.delivery--head { margin-top: var(--space-4); border-bottom-color: var(--line); padding-bottom: var(--space-1); }
.delivery__label { white-space: nowrap; }
.delivery__label--num { text-align: end; }
.domain-node { position: relative; margin: var(--space-4) 0 var(--space-2); font: 600 var(--text-base) var(--display); }
/* the dot's middle on the track's line: as far out as the track's space, half the line, half the dot */
.domain-node__dot { position: absolute; left: calc(-1 * var(--space-5) - 1px - 5px); top: .45em; width: 10px; height: 10px; border-radius: var(--radius-round); background: var(--brand); box-shadow: 0 0 0 3px var(--panel); }
.hint--prose { font: 400 var(--text-sm) var(--body); }
/* a kind and its terms on one baseline; a term as tall as its words, never the row */
.facts { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: var(--space-2) var(--space-3); margin: 2px 0 0; align-items: baseline; }
.facts__terms { margin: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-1); }
.proposal { border: 1px solid var(--line); border-radius: var(--radius-control); padding: var(--space-2) var(--space-3); margin-bottom: var(--space-2); display: grid; gap: var(--space-1); min-width: 0; }
.proposal__goal { font: 600 var(--text-base) var(--display); }
.proposal__facts { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; font-size: var(--text-sm); color: var(--muted); }
.event--wrap { white-space: normal; overflow-wrap: anywhere; }
.aside { margin-top: var(--space-4); padding: var(--space-1) var(--space-4) var(--space-2); border-inline-start: 4px solid var(--wait); border-radius: var(--radius-control); background: var(--panel); }
.trail { list-style: none; margin-top: var(--space-4); border-top: 1px solid var(--line); }
.trail__item { display: grid; grid-template-columns: 1.4em minmax(0, 1fr) auto; gap: var(--space-1) var(--space-3); align-items: baseline; padding: var(--space-3) 0; border-bottom: 1px solid var(--line); }
.trail__item:last-child { border-bottom: 0; }
.trail__glyph { color: var(--brand-text); }
.trail__words { min-width: 0; }
.trail__quote { font-style: italic; }
.trail__state { display: block; font: 400 var(--text-sm) var(--mono); color: var(--tone, var(--muted)); margin-top: 2px; }
.trail__state[data-state="wait"] { color: var(--muted); }
.trail__acts { display: flex; gap: var(--space-2); flex-wrap: wrap; justify-content: flex-end; }
.tab { font: 400 var(--text-sm) var(--mono); letter-spacing: .4px; color: var(--bar-dim); background: none; border: 0;
  padding: var(--space-2) var(--space-3); cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.tab:hover { color: var(--brand); }
.tab[aria-selected="true"] { color: var(--bar-ink); border-bottom-color: var(--brand); }
.tab:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
/* the keys show while the bar is worked by keyboard, never for a mouse */
.tab__key { display: var(--tab-key, none); margin-inline-end: var(--space-2); color: var(--brand); font-size: var(--text-xs); }
.tabs:has(:focus-visible) { --tab-key: inline; }   /* the keys show while the keyboard is in the tabs */
.tab__n { display: inline-block; min-width: 18px; margin-inline-start: var(--space-2); padding: 0 var(--space-1); border-radius: var(--radius-control); background: var(--brand-fill);
  color: var(--brand-ink); font-size: var(--text-xs); text-align: center; }
.step__word { font: 600 var(--text-md) var(--display); color: var(--brand-text); margin-inline-end: var(--space-2); }
.prose { font-size: var(--text-base); }
.prose p, .prose ul, .prose ol { margin: 0 0 var(--space-2); }
/* a story's pictures (WP-184): a grid, each with who took it */
.shots { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-3); margin-top: var(--space-3); }
.shot { margin: 0; min-width: 0; }
.shot__open { display: block; border: 1px solid var(--line); border-radius: var(--radius-control); overflow: hidden; background: var(--panel); }
.shot__open:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.shot__picture { display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; object-position: top; }
.shot__said { margin-top: var(--space-1); font: 400 var(--text-sm) var(--mono); color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* a picture in a record, a report or a story (WP-184): as wide as its column at most, opened large in a tab of its own */
.prose img { display: block; max-width: 100%; height: auto; margin: var(--space-2) 0 var(--space-3); border: 1px solid var(--line);
  border-radius: var(--radius-control); background: var(--panel); }
.prose a:has(> img) { display: inline-block; max-width: 100%; }
/* a mockup an option shows (WP-184): its own page in a frame the width of the column */
.prose iframe { display: block; width: 100%; aspect-ratio: 16 / 10; max-height: 26rem; margin: var(--space-2) 0 var(--space-3); border: 1px solid var(--line);
  border-radius: var(--radius-control); background: var(--panel); }
.prose iframe + small, .prose a:has(> img) + small { display: block; margin: calc(-1 * var(--space-2)) 0 var(--space-3); font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.prose table { width: auto; margin: var(--space-1) 0 var(--space-3); font-size: var(--text-base); }
.prose th { text-align: start; font: 500 var(--text-xs) var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); }
.prose td { border-bottom: 1px solid var(--line); vertical-align: top; }
.prose tr:last-child td { border-bottom: 0; }
.prose td, .prose th { padding: var(--space-1) var(--space-3) var(--space-1) 0; }
.prose pre { font: var(--text-sm)/1.5 var(--mono); background: var(--code); border-radius: var(--radius-control); padding: var(--space-3) var(--space-3); overflow-x: auto; margin: var(--space-1) 0 var(--space-3); }
.prose h4 { font: 600 var(--text-md) var(--display); margin: var(--space-3) 0 var(--space-1); }
.prose ul, .prose ol { padding-inline-start: 1.3em; }
.prose li { margin: 2px 0; }

/* === components: sections ===================================================================================== */
.card { scroll-margin-top: calc(var(--bar-height, 0px) + var(--space-4)); margin-top: var(--space-5); background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-5) var(--space-5); }
.card__title { font: 700 var(--text-xl)/1.25 var(--display); letter-spacing: -.3px; display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap; }
.card__sub { font: 400 var(--text-sm) var(--mono); color: var(--muted); letter-spacing: .2px; }
.card--wish .ask { margin-top: var(--space-4); }
/* the one fold: a button over its region — a row, a quiet line, a group, an ink row, an epic's panel, a whole card */
.accordion__heading { font: inherit; margin: 0; }
/* the caret's column and the gap after it: the body starts where the title does, clear of an open row's edge */
.accordion { --fold-inset: var(--space-2); --fold-indent: calc(var(--fold-inset) + 14px + var(--space-3)); }
.accordion__head { display: grid; grid-template-columns: minmax(14px, max-content) minmax(0, 1fr) max-content; gap: var(--space-1) var(--space-3); align-items: baseline; width: 100%;
  background: none; border: 0; padding: var(--space-2) var(--space-1) var(--space-2) var(--fold-inset); text-align: start; color: var(--ink); cursor: pointer; font: 400 var(--text-base) var(--body); }
/* the caret stands on the title's baseline, its middle raised to the middle of the capitals — whatever face, size
   or line height the title takes */
.accordion__head > .caret { align-self: baseline; margin-bottom: calc(.5cap - var(--caret) / 2); }
.accordion__head:hover .accordion__title { color: var(--brand-text); }
.accordion__head:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; border-radius: var(--radius-control); }
.accordion__title { min-width: 0; display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; }
.accordion__meta { display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; justify-content: flex-end; font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.accordion__below { grid-column: 2 / -1; display: flex; gap: var(--space-2); flex-wrap: wrap; }
.accordion__body { padding: 2px var(--space-1) var(--space-3) var(--fold-indent); }
/* a row in a list — of rules, of scenarios: no lines, its caret at the list's edge, an open row's edge clear before it */
.accordion--row { --fold-inset: var(--space-2); margin-inline-start: calc(-1 * var(--space-2)); }
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
.accordion--ink > .accordion__head { --em-face: var(--display); --em-weight: 500; }
.accordion--ink[data-open] > .accordion__head { background: var(--ink); color: var(--paper); border-radius: var(--radius-label) var(--radius-label) 0 0; box-shadow: inset 0 4px 0 var(--brand);
  --muted: color-mix(in srgb, var(--paper) 70%, transparent); --caret-open: color-mix(in srgb, var(--paper) 70%, transparent); }
.accordion--ink[data-open] > .accordion__head { --em-weight: 700; --em-ink: var(--paper); }
.accordion--ink > .accordion__body { padding: var(--space-1) 0 var(--space-2); }
/* a fold table: the rows share the table's columns through subgrid, the head row's labels above them (WP-181) */
.fold-table { display: grid; grid-template-columns: var(--fold-cols); column-gap: var(--space-4); margin-top: var(--space-3); }
.fold-table__head, .fold-table > .accordion { grid-column: 1 / -1; display: grid; grid-template-columns: subgrid; }
/* a fold whose head is cells: the head and the body take the columns of the table it stands in */
.accordion--cells > .accordion__head { grid-column: 1 / -1; display: grid; grid-template-columns: subgrid; column-gap: var(--space-4); align-items: baseline; }
.accordion--cells > .accordion__body { grid-column: 1 / -1; }
.fold-table__head { column-gap: var(--space-4); padding: var(--space-1) var(--space-2); border-bottom: 1px solid var(--line); }
.fold-table__label--num, .accordion__cell--num { text-align: end; }
.accordion__cell { min-width: 0; font: 400 var(--text-base)/1.45 var(--body); --em-face: var(--display); --em-weight: 500; }
.accordion__cell--num { font: 400 var(--text-sm) var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
.id--line { display: block; }
/* a context's subdomain on a line of its own, under its name, at the name's edge — every row alike */
.pill--line { display: block; width: fit-content; margin: var(--space-1) 0 0; }
.accordion--ink[data-open] > .accordion__head .accordion__cell { color: var(--paper); }
.accordion--ink[data-open] > .accordion__head .accordion__cell--num { color: color-mix(in srgb, var(--paper) 70%, transparent); }
.accordion--panel { border-radius: var(--radius-control); background: var(--panel); border: 1px solid var(--line); overflow: hidden; margin-top: var(--space-2); }
.accordion--panel > .accordion__head, .accordion--panel > .accordion__heading > .accordion__head { padding: var(--space-2) var(--space-3); background: var(--soft); }
.accordion--panel .accordion__below { grid-column: 1 / -1; margin: var(--space-1) calc(-1 * var(--space-3)) calc(-1 * var(--space-2)); display: block; }
.accordion--panel > .accordion__body { padding: var(--space-4) var(--space-3) var(--space-3); }
/* a card that folds: its caret on the card's content edge, where a card's title starts */
.accordion--card { --fold-inset: 0px; margin-top: var(--space-5); background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-4) var(--space-5); }
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
.accordion--panel > .accordion__head, .accordion--panel > .accordion__heading > .accordion__head { --em-face: var(--display); --em-weight: 600; }
.stepper { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: var(--space-1); padding: 0 var(--space-3) var(--space-3); }
.stepper__step { text-align: center; font: 500 var(--text-xs) var(--mono); color: var(--muted); }
.stepper__bar { display: block; height: 8px; border-radius: var(--radius-label); background: var(--line); margin-bottom: var(--space-1); }
.stepper__step[data-state="done"] .stepper__bar { background: var(--ok); }
.stepper__step[data-state="stopped"] { color: var(--stop); font-weight: 600; }
.stepper__step[data-state="stopped"] .stepper__bar { background: var(--stop); }
.stepper__step[data-state="now"] { color: var(--ink); font-weight: 600; }
/* a text of sections: a section's heading reads as a card's title, a scenario's as a row's, each on the rhythm */
.document > h2 { font: 700 var(--text-xl)/1.25 var(--display); letter-spacing: -.3px; margin: var(--space-6) 0 var(--space-2); }
.document > h2:first-child { margin-top: 0; }
.document > h3 { font: 600 var(--text-md)/1.3 var(--display); margin: var(--space-5) 0 var(--space-1); }
.document > h2 + h3 { margin-top: var(--space-3); }
.document > .aside { margin-top: var(--space-5); }
/* the compact text: a drawer's, a question's — its headings at the size of the words around them */
.document--compact > h2 { font: 600 var(--text-base) var(--display); margin: var(--space-5) 0 var(--space-2); }
.document--compact > h3 { font: 600 var(--text-base) var(--display); margin: var(--space-4) 0 var(--space-2); }
.aside__heading { font: 600 var(--text-base) var(--display); margin: var(--space-2) 0 var(--space-1); }
/* a story's track: one tile a stage, its top edge the stage's state */
.track { list-style: none; margin: var(--space-4) 0 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr)); gap: var(--space-2); }
.track__stage { display: grid; gap: var(--space-1); align-content: start; padding: var(--space-3); background: var(--panel); border: 1px solid var(--line);
  border-top: 3px solid var(--tone, var(--line)); border-radius: var(--radius-control); font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.track__stage[data-state="done"] { --tone: var(--ok); }
.track__stage[data-state="now"] { --tone: var(--run); background: var(--soft); }
.track__stage[data-state="stopped"] { --tone: var(--stop); }
.track__stage[data-state=""] { border-top-style: dashed; }
.track__name { font: 600 var(--text-base) var(--display); color: var(--ink); }
.track__line { --em-ink: var(--ink); --em-weight: 500; }
/* the run's control: one capsule on the bar — the dot and its word open the panel, the action stands beside them */
.run-control { display: flex; flex-wrap: wrap; max-width: 100%; align-items: center; gap: var(--space-1); padding: var(--space-1); border: 1px solid var(--bar-rule); border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--bar-ink) 5%, var(--bar)); }
.run-control[data-state="up"] { border-color: color-mix(in srgb, var(--run) 45%, var(--bar)); }
.run-control[data-state="stopping"] { border-color: color-mix(in srgb, var(--wait) 55%, var(--bar)); }
.run-control__say { font: 400 var(--text-sm) var(--mono); }
.run-control__say { --em-ink: var(--bar-ink); --em-weight: 500; }
.run-panel { display: grid; gap: var(--space-3); }
.run-panel__story { display: grid; gap: var(--space-1); padding-bottom: var(--space-3); border-bottom: 1px solid var(--line); }
.run-panel__head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
.run-panel__line { margin: 0; font: 400 var(--text-sm) var(--mono); color: var(--muted); }
.run-panel__line { --em-ink: var(--ink); --em-weight: 500; }
.stepper__step[data-state="now"] .stepper__bar { background: var(--wait); animation: pulse 1.5s infinite; }
.course { border: 1px solid var(--line); border-radius: var(--radius-control); overflow: hidden; margin-top: var(--space-3); }
.course__top { display: flex; justify-content: space-between; gap: var(--space-3); padding: var(--space-2) var(--space-3); align-items: baseline; flex-wrap: wrap; }
.course__title { display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; }
.course__right { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.course__doing { padding: var(--space-2) var(--space-3); font: 400 var(--text-sm) var(--mono); color: var(--muted); border-top: 1px solid var(--line); }
/* the requests as a list: one a row, the newest last, its state at the row's end */
.queue { list-style: none; display: grid; margin-top: var(--space-3); padding: 0; }
/* decide: the question on a tinted head, its answers as rows, the recommended one framed */
.record { margin-top: var(--space-5); background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); overflow: hidden; }
.record__question { padding: var(--space-3) var(--space-4); background: color-mix(in srgb, var(--wait) 12%, var(--panel)); border-bottom: 1px solid var(--line); }
.record--accept .record__question { background: color-mix(in srgb, var(--brand) 10%, var(--panel)); }
.record__text { font: 600 var(--text-read)/1.3 var(--display); display: block; margin-top: 2px; }
.record__body { padding: var(--space-3) var(--space-4) var(--space-4); }
.record__body > .id:last-child { margin-top: var(--space-3); }
.options { list-style: none; display: grid; grid-template-columns: minmax(64px, max-content) minmax(0, 1fr); gap: var(--space-2); margin-top: var(--space-3); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: var(--space-4) var(--space-6); margin-top: var(--space-3); }
.stats__group { min-width: 0; }
.stats__head { margin: 0 0 var(--space-1); padding-bottom: var(--space-1); border-bottom: 1px solid var(--line); }
.stats__row { display: grid; grid-template-columns: 5.5em minmax(0, 1fr); align-items: baseline; gap: var(--space-2); padding: var(--space-1) 0; }
.stats__label { font: 400 var(--text-sm)/1.4 var(--mono); color: var(--ink); }
.stats__note { display: block; color: var(--muted); }
.tiles { display: grid; grid-template-columns: repeat(var(--grid-columns), minmax(0, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
.tiles > .tile { grid-column: span 3; }
.tiles--many { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.tiles--many > .tile { grid-column: auto; }
/* the columns' heads stand over the rows: as far in as the timeline's line and its space push them */
.days__head { margin-inline-start: calc(var(--space-2) + 2px + var(--space-4)); }
.days__track { border-inline-start: 2px solid var(--line); margin: var(--space-4) 0 0 var(--space-2); padding-inline-start: var(--space-4); display: grid; gap: var(--space-5); }
/* a day is a divider across the rows, not a cell: its date as a caption, a hairline after it, the timeline's dot on it */
.days__date { position: relative; font: inherit; display: flex; align-items: center; gap: var(--space-3); margin: 0 0 var(--space-2); }
.days__date::after { content: ""; flex: 1; border-top: 1px solid var(--line); }
.days__date::before { content: ""; position: absolute; left: calc(-1 * var(--space-4) - 6px); top: 50%; transform: translateY(-50%);
  width: 10px; height: 10px; border-radius: 50%; background: var(--ok); }
.domain { margin: var(--space-1) 0 var(--space-2); }
.domain__track { border-inline-start: 2px solid var(--line); margin: var(--space-3) 0 0 var(--space-3); padding-inline-start: var(--space-5); }
.kernel { border: 1px solid color-mix(in srgb, var(--shared) 35%, var(--line)); border-top: 4px solid var(--shared); border-radius: var(--radius-label) var(--radius-label) var(--radius-control) var(--radius-control);
  padding: var(--space-3) var(--space-4) var(--space-3); margin: var(--space-3) 0 var(--space-1); background: color-mix(in srgb, var(--shared) 5%, var(--panel)); }
.kernel__top { display: flex; gap: var(--space-3); align-items: baseline; flex-wrap: wrap; margin-bottom: var(--space-2); }
.kernel__title { margin: 0; font: 700 var(--text-lg) var(--display); color: var(--shared); }
.proposals { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-2); }
.rule-group { margin-top: var(--space-4); }
.rule-group__rows { list-style: none; }
.rule-group__label { margin-bottom: var(--space-1); }
.rule-group__n { font: 500 var(--text-xs) var(--mono); color: var(--ink); margin-inline-start: var(--space-1); }
/* a stage's parts as the domain's rule blocks: a line between two, no rail at the side */
.part { padding: var(--space-4) 0 var(--space-2); }
.part + .part { border-top: 1px solid var(--line); }
.part--aside > .part__head { font-size: var(--text-md); color: var(--muted); }
.part__head { font: 600 var(--text-base) var(--display); display: flex; gap: var(--space-2); align-items: baseline; flex-wrap: wrap; margin: 0; }
.part .rule-group:first-of-type { margin-top: var(--space-2); }
/* how a check ends: the pass and the fail, each its mark and where the story goes, what happens then beneath */
.outcome { margin-top: var(--space-4); }
.outcome__head { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; margin: 0; font: 600 var(--text-base) var(--display); }
.outcome__head { --em-ink: var(--brand-text); }
.icon--large { width: var(--mark-large); height: var(--mark-large); margin: 0; }
/* what follows an outcome stands under its words, after its mark: the outcome reads as the heading it is */
.outcome__body { padding-inline-start: calc(var(--mark-large) + var(--space-2)); }
.outcome .rule-group { margin-top: var(--space-2); }
.table { width: 100%; border-collapse: collapse; margin-top: var(--space-3); font-size: var(--text-base); }
.table__label { text-align: start; font: 500 var(--text-xs) var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding: var(--space-2) var(--space-2); }
.table__cell { border-bottom: 1px solid var(--line); padding: var(--space-3) var(--space-2); vertical-align: top; }
.table__row:last-child > .table__cell { border-bottom: 0; }
.table__num { text-align: end; font-family: var(--mono); font-size: var(--text-sm); white-space: nowrap; font-variant-numeric: tabular-nums; }
.table__act > .actions { margin-top: 0; }
.table__mark { width: 1.6em; }
.terminal { font: var(--text-sm)/1.5 var(--mono); background: var(--terminal); color: var(--terminal-ink); border-radius: var(--radius-control); padding: var(--space-3); max-height: 460px; overflow: auto;
  white-space: pre-wrap; word-break: break-word; margin-top: var(--space-3); }
.terminal:empty { display: none; }
/* delivered over time: two panels on one time axis — cost above, tokens below, never two scales on one axis */
.curve { position: relative; margin-top: var(--space-4); max-width: var(--flow-measure); margin-inline: auto; }
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
.curve-tip__title { display: block; font: 600 var(--text-md) var(--display); margin-bottom: var(--space-1); }
.curve-tip__row { display: flex; justify-content: space-between; gap: var(--space-4); color: var(--muted); }
.curve-tip__value { color: var(--ink); }
/* the rules (WP-194): a rule a press in a list, a kind's track with its ways back, a stage in three columns, the checks
   against the stages, the board of a run, a rule in the drawer, the groups that unfold */
.rule-rows { list-style: none; margin-top: var(--space-2); }
.rule-row { border-top: 1px solid var(--line); }
.rule-row:first-child { border-top: 0; }
.rule-row__open { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2); align-items: baseline; width: 100%;
  text-align: start; background: none; border: 0; padding: var(--space-2) 0; font: 400 var(--text-md)/1.35 var(--body); color: var(--ink); cursor: pointer; }
.rule-row__open:hover .rule-row__title { color: var(--brand-text); }
.rule-row[data-state="fail"] .rule-row__title { color: var(--tone); font-weight: 600; }
.rule-row__aside { white-space: nowrap; }
.labelled { display: inline-flex; align-items: center; gap: var(--space-2); white-space: nowrap; max-width: 100%; min-width: 0; }
.labelled__text { font: 400 var(--text-sm) var(--mono); color: var(--muted); }
/* the track: tiles that are presses, their words from the top; the ways back beneath in a low band of levels — one
   meaning per colour (a round in the waiting tone, none in the muted one), the emphasis the stroke */
.rule-track { margin-top: var(--space-4); background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card);
  padding: var(--space-4) var(--space-4) var(--space-2); }
.rule-track__scroll { overflow-x: auto; overflow-y: hidden; }
.rule-track__wrap { position: relative; min-width: calc(var(--tiles) * 8.5rem); padding-bottom: var(--band, var(--space-2)); }
.rule-track__tiles { display: grid; gap: var(--space-3); position: relative; z-index: 1; }
.rule-track__tile { display: flex; flex-direction: column; justify-content: flex-start; align-items: stretch; text-align: start; min-height: 6rem;
  padding: var(--space-3); background: var(--panel); color: var(--ink); border: 1px solid var(--line); border-radius: var(--radius-control);
  cursor: pointer; font: inherit; }
.rule-track__tile:hover { border-color: color-mix(in srgb, var(--brand) 50%, var(--line)); }
.rule-track__tile[aria-pressed="true"] { border-color: var(--brand); background: color-mix(in srgb, var(--brand) 8%, var(--panel)); }
.rule-track__tile[data-here] { box-shadow: 0 0 0 3px color-mix(in srgb, var(--run) 35%, transparent); }
.rule-track__end { display: flex; flex-direction: column; justify-content: flex-start; align-items: center; text-align: center;
  padding: var(--space-3); border: 1px dashed var(--line); border-radius: var(--radius-control); color: var(--muted); }
.rule-track__name { display: block; font: 700 var(--text-lg)/1.15 var(--display); }
.rule-track__end > .rule-track__name { font: 400 var(--text-sm) var(--mono); }
.rule-track__meta, .rule-track__note { display: block; font: 400 var(--text-xs)/1.6 var(--mono); color: var(--muted); }
.rule-track__state { display: block; font: 600 var(--text-xs)/1.6 var(--mono); color: var(--tone, var(--muted)); }
.rule-track__ways { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
.rule-track__way { fill: none; stroke-width: 1.6; }
.rule-track__way--round { stroke: var(--wait); } .rule-track__way--free { stroke: var(--muted); }
.rule-track__way--quiet { stroke-width: 1.1; opacity: .55; stroke-dasharray: 5 4; }
.rule-track__way--solid { stroke-width: 2.2; }
.rule-track__head--round { fill: var(--wait); } .rule-track__head--free { fill: var(--muted); }
.rule-track__hit { fill: none; stroke: transparent; stroke-width: 12; pointer-events: stroke; cursor: help; }
.rule-track__label { font: 600 var(--text-xs) var(--mono); paint-order: stroke; stroke: var(--panel); stroke-width: 4px; }
.rule-track__label--round { fill: var(--wait); } .rule-track__label--free { fill: var(--muted); }
.rule-track__legend { display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); font: 400 var(--text-xs) var(--mono); color: var(--muted); padding-top: var(--space-1); }
.rule-track__key[data-state] { color: var(--tone); }
.stage-read { display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 5fr) minmax(0, 3fr); gap: var(--space-4); align-items: start; margin-top: var(--space-4); }
.stage-read__told, .stage-read__checked, .stage-read__next { min-width: 0; }
.stage-read__told > .card, .stage-read__checked > .card, .stage-read__next > .card:first-child { margin-top: 0; }
.stage-read__next > .card + .card { margin-top: var(--space-3); }
/* the checks against the stages: wider than its place, it scrolls in its own box, never the page */
.rule-matrix { overflow-x: auto; margin-top: var(--space-3); }
.rule-matrix__table { width: 100%; min-width: 36rem; border-collapse: collapse; }
.rule-matrix__corner, .rule-matrix__stage { padding: var(--space-2); border-bottom: 1px solid var(--line); text-align: center; }
.rule-matrix__corner { text-align: start; }
.rule-matrix__pick { font: 700 var(--text-md) var(--display); color: var(--ink); background: none; border: 0; cursor: pointer;
  padding: var(--space-1) var(--space-2); border-radius: var(--radius-label); }
.rule-matrix__pick:hover, .rule-matrix__stage[aria-current="true"] .rule-matrix__pick { color: var(--brand-text); }
.rule-matrix__stage[aria-current="true"], .rule-matrix__cell[data-picked] { background: color-mix(in srgb, var(--brand) 7%, var(--panel)); }
.rule-matrix__label { padding: var(--space-2); border-top: 1px solid var(--line); background: color-mix(in srgb, var(--ink) 4%, var(--panel)); }
.rule-matrix__check { padding: var(--space-2); border-top: 1px solid var(--line); text-align: start; font: 400 var(--text-md)/1.35 var(--body); }
.rule-matrix__rule { font: inherit; color: var(--ink); background: none; border: 0; padding: 0; text-align: start; cursor: pointer; }
.rule-matrix__rule:hover { color: var(--brand-text); }
.rule-matrix__name, .rule-matrix__text, .rule-matrix__plain { font: 400 var(--text-xs) var(--mono); color: var(--muted); white-space: nowrap; }
.rule-matrix__cell { padding: var(--space-2); border-top: 1px solid var(--line); text-align: center; width: 8%; }
.rule-matrix__dot { display: inline-block; width: 11px; height: 11px; border-radius: var(--radius-round); background: var(--tone); vertical-align: middle; }
.rule-matrix__count { display: inline-block; font: 700 var(--text-xs)/1 var(--mono); color: var(--paper); background: var(--tone);
  border-radius: var(--radius-round); padding: var(--space-1) var(--space-2); }
/* the board of a run: a column per stage, side by side; narrower than its columns, it scrolls in its own box */
.rule-board { overflow-x: auto; margin-top: var(--space-4); }
.rule-board__track { display: grid; grid-template-columns: repeat(var(--cols), minmax(11rem, 1fr)); gap: var(--space-3); align-items: start; }
.rule-board__col { min-width: 0; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-3) var(--space-4); }
.rule-board__col[data-picked] { border-color: var(--brand); }
.rule-board__col[data-here] { box-shadow: 0 0 0 3px color-mix(in srgb, var(--run) 35%, transparent); }
.rule-board__head { display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-2); margin: 0 0 var(--space-2);
  padding-bottom: var(--space-2); border-bottom: 2px solid var(--ink); }
.rule-board__pick { font: 700 var(--text-xl)/1.1 var(--display); color: var(--ink); background: none; border: 0; padding: 0; cursor: pointer; }
.rule-board__pick:hover { color: var(--brand-text); }
.rule-board__verdict { margin: 0 0 var(--space-2); border-radius: var(--radius-control); padding: var(--space-2) var(--space-3);
  font: 600 var(--text-sm)/1.35 var(--mono); color: var(--tone, var(--muted)); background: color-mix(in srgb, var(--tone, var(--ink)) 10%, var(--panel)); }
.rule-board__why { display: block; font-weight: 500; }
.rule-board__part { margin-top: var(--space-3); }
.rule-sheet__head { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); }
.rule-sheet__title { font: 700 var(--text-2xl)/1.2 var(--display); margin: var(--space-2) 0; text-wrap: balance; }
.rule-sheet__outcomes { margin-top: var(--space-4); }
.rule-sheet__part { margin-top: var(--space-5); }
.rule-folds { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(18rem, 100%), 1fr)); gap: 0 var(--space-4); }
.rule-folds__item { min-width: 0; }
.rule-folds__item:has(> [data-open]) { grid-column: 1 / -1; }

/* === templates ================================================================================================ */
/* a place beneath a view (a part of the description): its way back stands above the head, apart from it */
.actions + .page-head { margin-top: var(--space-5); }
.page-head__eyebrow { font: 400 var(--text-sm) var(--mono); letter-spacing: 2.5px; text-transform: uppercase; color: var(--brand-text); margin-bottom: var(--space-3); }
.page-head__title { font: 700 clamp(var(--text-2xl), 4vw, var(--text-3xl))/1.1 var(--display); letter-spacing: -1px; }
.page-head__lede { margin-top: var(--space-3); color: var(--muted); max-width: 44em; font-size: var(--text-lg); }
/* the templates of a wide window (WP-183): stacked as one column, side by side from the wide width */
.split, .master, .reader { display: grid; gap: var(--space-5); align-items: start; }
/* each column is a place of its own: what stands in it takes the form its column's width gives it */
.split__main, .split__side, .master__list, .master__detail, .reader__text { min-width: 0; container-type: inline-size; }
.split__main > :first-child, .split__side > :first-child, .master__list > :first-child, .master__detail > :first-child { margin-top: 0; }
.split, .reader { margin-top: var(--space-5); }
.split--side-first > .split__side { order: -1; }
.master__detail { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-5); }
.master--bare > .master__detail { background: none; border: 0; padding: 0; }
.reader__toc { border-bottom: 1px solid var(--line); padding-bottom: var(--space-3); }
/* the text is read on a panel, as a card's is — the sections beside it stay on the paper */
/* the text is as wide as its reading measure, no wider — and stacked, the sections above it end where it does */
.reader { --reader-width: calc(var(--read-measure) + 2 * var(--space-5) + 2px); max-width: var(--reader-width); }
.reader__text { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-card); padding: var(--space-5);
  max-width: var(--reader-width); }
.reader__part:first-child > .reader__heading { margin-top: 0; }
.reader__sections { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-4); }
.reader__goto { font: 400 var(--text-sm) var(--mono); color: var(--muted); background: none; border: 0; padding: var(--space-1) 0; cursor: pointer; text-align: start; }
.reader__goto:hover { color: var(--brand-text); }
.reader__goto:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.reader__part { scroll-margin-top: calc(var(--bar-height, 0px) + var(--space-4)); display: grid; grid-template-columns: minmax(0, 1fr) max-content;
  column-gap: var(--space-5); align-items: baseline; max-width: var(--read-measure); padding-top: var(--space-2); }
.reader__heading { font: 600 var(--text-xl) var(--display); margin: var(--space-5) 0 var(--space-2); }
.reader__aside { font-size: var(--text-sm); }
.reader__body { grid-column: 1 / -1; }
/* the sections beside the text as soon as both fit — the sections as wide as their longest name, kept in sight */
@container (width >= 920px) {
  .reader { grid-template-columns: fit-content(16rem) minmax(0, var(--reader-width)); gap: var(--space-6); max-width: none; }
  .reader__toc { position: sticky; top: calc(var(--bar-height, 0px) + var(--space-4)); border-bottom: 0; padding-bottom: 0;
    max-height: calc(100vh - var(--bar-height, 0px) - 2 * var(--space-4)); overflow-y: auto; }
  .reader__sections { flex-direction: column; flex-wrap: nowrap; }
}
@container (width >= 1500px) {
  .split, .master[data-open] { grid-template-columns: repeat(var(--grid-columns), minmax(0, 1fr)); gap: var(--space-6); }
  .split__main { grid-column: span 8; } .split__side { grid-column: span 4; }
  .split--side-first > .split__side { order: 0; }
  .master__list { grid-column: span 5; } .master__detail { grid-column: span 7; }
  .master--narrow-list > .master__list { grid-column: span 4; } .master--narrow-list > .master__detail { grid-column: span 8; }
  .master__detail { position: sticky; top: calc(var(--bar-height, 0px) + var(--space-4));
    max-height: calc(100vh - var(--bar-height, 0px) - 2 * var(--space-4)); overflow-y: auto; }
}
.drawer-frame__close { float: right; }
.drawer-frame > .actions { margin: var(--space-4) 0 var(--space-5); }
.drawer-frame .ask { margin: var(--space-2) 0 var(--space-5); }
.gallery { margin-top: var(--space-4); }
.gallery__level { margin-top: var(--space-6); }
.gallery__title { font: 700 var(--text-xl) var(--display); text-transform: capitalize; border-bottom: 1px solid var(--line); padding-bottom: var(--space-2); }
.gallery__item { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: var(--space-4); padding: var(--space-4) 0; border-bottom: 1px solid var(--line); }
.gallery__name { margin: 0; font: 500 var(--text-sm) var(--mono); color: var(--brand-text); padding-top: var(--space-1); }
.gallery__show { min-width: 0; }
/* a list the library holds items in, where the page holds them in a component's own: no bullet, no indent */
.gallery__list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.gallery__show > .card:first-child, .gallery__show > .record:first-child, .gallery__show > .board:first-child,
.gallery__show > .accordion--card:first-child, .gallery__show > .notice:first-child { margin-top: 0; }

/* === the narrow screen ======================================================================================== */
@media (prefers-reduced-motion: reduce) { .caret { transition: none; } .spinner, .stepper__step[data-state="now"] .stepper__bar { animation: none; } }
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
  .table__label, .table__cell { padding: var(--space-2) var(--space-1); }
  .delivery { grid-template-columns: 44px minmax(0, 1fr) auto; } .delivery__epic { display: none; } .delivery--head { display: none; }
  .delivery__event { grid-column: 2 / -1; grid-row: 2; } .delivery__fig + .delivery__fig { grid-column: 3; grid-row: 2; }
  .gallery__item { grid-template-columns: 1fr; gap: var(--space-2); }
  .stage-read { grid-template-columns: minmax(0, 1fr); }
  /* a row with buttons: its cells side by side, the buttons on a line of their own beneath */
  .table--acts .table__row { display: grid; grid-template-columns: auto 1fr fit-content(40%); border-bottom: 1px solid var(--line); }
  .table--acts .table__cell { border-bottom: 0; }
  .table__act { grid-column: 1 / -1; padding-top: 0; } .table__act:empty { display: none; }
  .table__act > .actions { justify-content: flex-start; }
  .table--acts .table__row--head { display: none; }
}
}
@layer utilities {
/* === forced colours =========================================================================================== */
/* a high-contrast mode drops every fill and shadow (WP-182): what a fill said — the chosen option, the open tab, a
   state's dot, a meter — becomes a system colour or an edge; the focus takes the system's highlight */
@media (forced-colors: active) {
  .switch__opt[aria-pressed="true"] { background: Highlight; color: HighlightText; forced-color-adjust: none; }
  .tab[aria-selected="true"] { border-bottom-color: Highlight; }
  .pill { border: 1px solid CanvasText; }
  .dot, .meter__fill { forced-color-adjust: none; }
  :focus-visible { outline-color: Highlight !important; }
  /* the rules: the picked stage takes the highlight, the stage a story stands at an edge for its glow; the ways back,
     a check's dot and its count keep their tones — what a way costs is its colour */
  .rule-track__tile[aria-pressed="true"], .rule-board__col[data-picked] { border-color: Highlight; }
  .rule-matrix__stage[aria-current="true"], .rule-matrix__cell[data-picked] { outline: 2px solid Highlight; outline-offset: -2px; }
  .rule-track__tile[data-here], .rule-board__col[data-here] { outline: 3px solid CanvasText; outline-offset: 1px; }
  .rule-track__ways, .rule-matrix__dot, .rule-matrix__count { forced-color-adjust: none; }
}
}
"""
