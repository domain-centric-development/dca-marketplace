# Theming and token upkeep

Sections 5–6.

## Theming

- Two axes: `data-theme="<name>"` = colour world; `data-scheme="light|dark"` overrides the system (absent: system).
  Every theme has both schemes.
- Light/dark via `color-scheme` + `light-dark(<light>, <dark>)`, each colour token once per theme;
  `:root[data-scheme="dark"] { color-scheme: dark; }`. Never a second stylesheet, never per-component overrides.
- Derived colours (hover, soft bg, borders, text-on-colour) via `color-mix()` or `oklch(from var(--color-action) …)`;
  re-check contrast of every derived pair.
- A theme = optional file loaded after the page's own (or unlayered), reassigning public tokens only. Ship an
  example theme listing every public token with default; a check keeps it and the token file the same set.
- Optional: theme folder with logo/favicon/fonts (white-label); several themes per page, `data-theme` per subtree.

## Token upkeep

- Rename: old name stays an alias one release, marked deprecated; a check fails when a component still reads it.
- DTCG JSON / Style Dictionary / `@property` only if tokens leave CSS or animate.
