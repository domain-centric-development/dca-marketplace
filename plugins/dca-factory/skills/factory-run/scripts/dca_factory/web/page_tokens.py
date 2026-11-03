"""The page's tokens (WP-180): the one place a colour, a face or a measure is written as a value.

The public tokens are the contract a project's theme overrides (`.dca-factory/theme/theme.css`, the plugin's
`theme.example.css` lists them): a few, each light/dark pair one declaration with `light-dark()`. Everything else is
derived from them — `oklch(from …)` for the brand's tones, `color-mix()` for every tint, halo and dimmed text — so a
theme that sets `--brand` alone recolours the page coherently, and one that sets `--bar` / `--bar-ink` turns the bar
light without touching anything else. A token not in the public list is internal and may change without notice.
"""

#: The public tokens, in the order `theme.example.css` lists them: name → the role a theme gives it.
PUBLIC = {
    "--brand": "the accent: the mark's core, focus rings, done bars, the wordmark's dot",
    "--brand-text": "the accent as text and links (derived from --brand)",
    "--brand-fill": "the ground of the one primary button (derived from --brand)",
    "--brand-ink": "text on --brand-fill",
    "--ink": "text",
    "--paper": "the page's ground",
    "--panel": "cards and panels",
    "--line": "rules and borders",
    "--muted": "secondary text",
    "--bar": "the top bar's ground — light or dark per scheme, the theme decides",
    "--bar-ink": "the top bar's text",
    "--success": "the palette of meanings: what went well — every use below defaults to one of these four",
    "--warning": "the palette: what waits or needs a look",
    "--danger": "the palette: what was refused or stopped",
    "--info": "the palette: what is under way, a neutral notice",
    "--ok": "a story done or delivered (--success)",
    "--pass": "a gate that passed — its dot in the flow, a rule that passed (--success)",
    "--wait": "a story that waits for a person, or runs (--warning)",
    "--stop": "a story refused or stopped (--danger)",
    "--fail": "a gate that refused — its mark in the flow, a rule that failed (--danger)",
    "--run": "a stage that runs (--info)",
    "--shared": "the shared kernel's terms",
    "--display": "the face of headings and controls",
    "--body": "the face of running text",
    "--mono": "the face of displays: states, ids, figures",
    "--density": "how dense the page sits: every space is a step of the scale times this — .85 compact, 1.15 airy",
    **{f"--space-{n}": f"the space scale, a 4 px rhythm: step {n}, {px} px times --density"
       for n, px in enumerate((4, 8, 12, 16, 24, 32, 48, 72), 1)},
    **{f"--text-{step}": f"the type scale: {px} px"
       for step, px in (("xs", 11), ("sm", 12.5), ("md", 14), ("base", 16), ("lg", 18), ("xl", 20), ("2xl", 24), ("3xl", 38))},
    "--text-read": "the reading size of running text — the body face's, apart from the scale",
    "--radius-label": "a label's corner: a term, a flag (3 px)",
    "--radius-control": "a control's corner: a button, a field (7 px)",
    "--radius-card": "a card's corner (12 px)",
    "--radius-round": "a state, an event, a dot: round",
    "--measure": "the page's width",
    "--logo": "the logo in the bar, an url(); none keeps the mark — per scheme under :root[data-scheme=\"dark\"]",
    "--logo-width": "the logo's width in the bar",
}

#: The default light values the tab's icon is drawn with — the same as the tokens below.
ICON_INK, ICON_BRAND = "#1c2433", "#148f96"

TOKENS = """
:root {
  color-scheme: light dark;
  /* public — a theme overrides these */
  --brand: #148f96;
  --brand-text: light-dark(oklch(from var(--brand) calc(l - .112) calc(c * .81) h), oklch(from var(--brand) calc(l + .137) calc(c * 1.12) h));
  --brand-fill: oklch(from var(--brand) calc(l - .112) calc(c * .81) h);
  --brand-ink: #ffffff;
  --ink: light-dark(#1c2433, #e8eaf0);
  --paper: light-dark(#f7f6f3, #12171f);
  --panel: light-dark(#ffffff, #1a2130);
  --line: light-dark(#dedbd3, #2b3445);
  --muted: light-dark(#5b6472, #9aa3b2);
  --bar: #171d29;
  --bar-ink: #e8eaf0;
  /* the palette of meanings — a state, not the brand; every use below defaults to one of them */
  --success: light-dark(#0d6b70, #3cbcc3);
  --warning: light-dark(#93600f, #e2ab55);
  --danger: light-dark(#c96a5a, #d9826f);
  --info: light-dark(#148f96, #3cbcc3);
  /* the uses — one overridden alone where it should differ */
  --ok: var(--success);
  --pass: var(--success);
  --wait: var(--warning);
  --stop: var(--danger);
  --fail: var(--danger);
  --run: var(--info);
  --shared: light-dark(#4b47b8, #b3b0f2);
  --display: "Space Grotesk", "Avenir Next", "Trebuchet MS", sans-serif;
  --body: "Newsreader", Georgia, "Times New Roman", serif;
  --mono: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  --logo: none;
  --logo-width: 2.13ex;
  /* the rhythm — space a 4 px scale times the density, type eight steps, a corner by what it rounds (WP-181) */
  --density: 1;
  --space-1: calc(4px * var(--density));
  --space-2: calc(8px * var(--density));
  --space-3: calc(12px * var(--density));
  --space-4: calc(16px * var(--density));
  --space-5: calc(24px * var(--density));
  --space-6: calc(32px * var(--density));
  --space-7: calc(48px * var(--density));
  --space-8: calc(72px * var(--density));
  --text-xs: 11px;
  --text-sm: 12.5px;
  --text-md: 14px;
  --text-base: 16px;
  --text-lg: 18px;
  --text-xl: 20px;
  --text-2xl: 24px;
  --text-3xl: 38px;
  --text-read: 17px;
  --radius-label: 3px;
  --radius-control: 7px;
  --radius-card: 12px;
  --radius-round: 999px;
  --measure: 1100px;
  --grid-columns: 12;
  /* internal — derived from the public ones */
  --brand-fill-hover: color-mix(in srgb, var(--brand-fill), black 15%);
  --tint: color-mix(in srgb, var(--brand) 14%, transparent);
  --soft: color-mix(in srgb, var(--brand) 8%, var(--panel));
  --group: color-mix(in srgb, var(--brand) 13%, var(--panel));
  --group-line: color-mix(in srgb, var(--brand) 24%, var(--panel));
  --code: color-mix(in srgb, var(--ink) 5%, var(--paper));
  --bar-rule: color-mix(in srgb, var(--bar-ink) 8%, var(--bar));
  --bar-faint: color-mix(in srgb, var(--bar-ink) 35%, var(--bar));
  --bar-dim: color-mix(in srgb, var(--bar-ink) 62%, var(--bar));
  --bar-text: color-mix(in srgb, var(--bar-ink) 80%, var(--bar));
  --bar-off: color-mix(in srgb, var(--bar-ink) 55%, var(--bar));
  --terminal: color-mix(in srgb, var(--bar), black 35%);
  --terminal-ink: color-mix(in srgb, var(--bar-ink) 85%, var(--bar));
  --shadow: 0 6px 24px light-dark(color-mix(in srgb, var(--ink) 10%, transparent), rgb(0 0 0 / .35));
  --lift: 0 1px 0 var(--line), 0 1px 3px rgb(0 0 0 / .06);
}
:root[data-scheme="light"] { color-scheme: light; }
:root[data-scheme="dark"] { color-scheme: dark; }
"""
