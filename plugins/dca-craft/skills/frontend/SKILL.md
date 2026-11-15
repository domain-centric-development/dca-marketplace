---
name: frontend
description: The craft of a maintainable web frontend, carried out the way the project's description decides — design principles, cascade layers and one owner per style in the styling method the project chose (native @scope, BEM, scoped styles, utility classes or a component library), state in attributes, tokens in three tiers with themes and light/dark, scales with floors, intrinsic layouts with container queries and named widths, components with a contract, landmarks, WCAG 2.2 AA, a gallery with fixtures, and the checks that keep it. Use when building or changing a page, component, layout, template or stylesheet, when a delivery stage needs the frontend craft, or when a frontend has drifted ("make the spacing consistent", "add a theme", "/frontend"). Stack-neutral: server templates, React, Vue, Svelte or plain HTML.
---

# /frontend

One component per behaviour, one token per decision, one place per rule — and a check that says so.
**House rule** = beyond WCAG 2.2 AA on purpose; a project may drop it, never AA.

## 0. Read the project first

- `AGENTS.md`, the technical description (`tech.md` or similar): frontend approach with its **`Browsers:`**,
  **`Styling:`** (section 3), **`Gallery:`** (section 14) lines.
- Does the stack scope styles (CSS Modules, `<style scoped>`, Svelte, Shadow DOM) or is every class global?
- Existing tokens, components, gallery/Storybook, theme file, stylelint config; `data-test` selectors are a contract.

The description decides. Method named → follow, say so. None → section 3's default for its browsers, say which
for the person to confirm into the description (in a pipeline: a recorded question, not a guess). Never mix
methods. A rule here contradicting the description → a finding, never a slipped-in change.

## 1. Design principles (check on a screenshot)

1. One primary action per view; the rest visibly secondary.
2. Hierarchy through weight, colour, space before size — no sixth font size.
3. Space inside a group < space between groups.
4. One alignment line per region.
5. ≤ 2 typefaces, steps of one type scale, colours of the token set.
6. Colour never alone — a state also has a word or a shape.
7. Every state visible: hover, focus, selected, disabled, invalid, busy, empty.

## 2. CSS architecture

- `@layer reset, base, tokens, layout, components, utilities;` once. A theme file may be unlayered (wins);
  third-party CSS into a named layer.
- Short modern reset, not a normalize.
- One class per selector where possible; no ids; `!important` only in `utilities` and `forced-colors`/reduced-motion
  overrides.
- One file/style module per component, named like it; tokens in one file; layout primitives in one.
- Utilities: a few helpers (`visually-hidden`, flow spacer) in the last layer, not a second method.

## 3. Ownership and naming

- **One owner per style**: markup and styles together (partial + block, component + style module); nothing else
  renders that markup.
- **No reach-in**: a rule naming two components only **places** the inner one (margin, grid area, order,
  alignment) — never colour, font, padding, border, size. `:deep`, `:global`, `::part` = reviewed exception.
- A component writes only its own classes; children get content via props, slots, parameters — never a class.

`Styling:` chooses one: native scoping (`@scope`, default for current browsers only), BEM names (default when
older browsers are served), the framework's scoped styles, utility classes, a component library. Spelling, choice
table and code: `reference/styling.md` — read before styling a component.

All methods: root named for what it *is*, never position or look; variant = attribute or own modifier; no
unscoped descendant selector (`.card .body p` wrong) except owned children (`.icon > svg`).

- Content zone: outside text (markdown, CMS, long help) styled by tag selectors only inside one `.prose` block.
- Classes for style, `data-test` for tests, `data-*` for state/behaviour. Tests never select by style class;
  scripts never read a style class for behaviour.

## 4. State

- State = attribute: ARIA state where one exists (`aria-expanded|current|selected|invalid|busy`), else
  `data-state="…"`. No `is-open`/`active`/`error` classes, no script-toggled state class (React/Vue too).
- One state→tone mapping on the component root, never `:root` (leaks into nested components):
  `.pill[data-state="fail"] { --tone: var(--color-danger); }`; the component paints with `--tone`.
- State words from the product, identical in markup, script, copy, tests.
- UI state keyed by item id + place shown, never position. Shareable/reloadable state lives in the URL.

## 5. Tokens

Every design decision is a custom property; no other literal colour, font stack or length (hairlines and
check-allowed values excepted).

| Tier | Example | Read by |
|---|---|---|
| primitive | `--blue-600`, `--space-4` | semantic tier only |
| semantic | `--color-action`, `--color-danger`, `--color-surface`, `--text-body` | components, layout, theme |
| component hook | `--button-bg`, `--card-padding` | that component |

- Product states alias semantic tokens (`--color-pass: var(--color-success)`).
- Hooks with fallback: `background: var(--button-bg, var(--color-action));`.
- Public tokens = semantic tier + documented hooks; only these a theme may override.
- Names: `--<category>-<role>[-<variant>]`, hooks `--<block>-<property>`; no synonyms.

## 6. Theming

- Two axes: `data-theme="<name>"` (colour world) and `data-scheme="light|dark"` (absent: system decides); every
  theme has both schemes, via `light-dark()` — never a second stylesheet or per-component overrides.
- A theme = one file reassigning public tokens only; an example theme lists every public token.
- Detail (derived colours, theme file, white-label, token renames, DTCG): `reference/theming.md` — read when adding
  or changing a theme, the scheme, or a token's name.

## 7. Spacing and type

- One spacing scale `--space-1 … --space-8` for every margin, padding, gap. Optional `--density` factor, `clamp()`.
- Components own padding, no outer margin; parents space children (`gap`, stack). A project whose components
  carry a bottom margin (GOV.UK) keeps it.
- Type scale `--text-xs … --text-3xl`, ratio ~1.2–1.25, `rem`. Floors (**house rule**): body 16 px, small reading
  text (hint, card line, figure) 14 px, fine print (column head, caps label, count) 12 px; drawings at drawn size.
- Line height 1.4–1.6 reading, tighter headings; no fixed heights on text boxes.
- Reading width ~65–75 ch inside the content zone, separate from layout widths.
- Control sizes `--control-s|m|l` for every button, select, input, chip; smallest ≥ 24×24 px.
- Icons: SVG/CSS with `aria-hidden="true"`, name on the control — never a font glyph (×, ▾).
- Marks align to cap height/baseline: `text-box: trim-both cap alphabetic` where `Browsers:` allow, else a
  cap-relative margin.
- Named insets: alignment offsets are tokens computed from their parts, never eyeballed numbers.
- Optional: radius by role (`--radius-control`, `--radius-card`).

## 8. Layout

- Intrinsic primitives, no visual style: stack, cluster, sidebar, switcher, center, grid `repeat(auto-fit, minmax())`.
- Flex for one axis, grid for two; `subgrid` to align nested rows.
- Components: container queries (`container-type: inline-size` on the region); media queries: page frame only.
- A few named width tokens (narrow, wide, reader), no others; a script's copy is checked equal.
- A drawing shrinks until its smallest text hits the type floor, then scrolls in its own box — never the page.
- 12-column grid only where the design has one.

## 9. Components

- Levels: **primitives** (button, input, label, pill, icon), **components** (form row, card, table, accordion,
  dialog), **views** (template + data). Each piece on one level, using only lower ones.
- Same behaviour, same component — extend it, never a second implementation.
- Contract where the component lives: variants, sizes (control scale), states, slots, theme hooks. Slot over the
  tenth boolean prop.
- New look → new variant, never an instance override.
- A field is always a form row: label, control, hint, error; wires `for`/`id`, `aria-describedby`, error state. No
  bare input in a view.

## 10. Templates and pages

- Template: landmarks (`header`, `nav`, `main`, `aside`, `footer`), skip link to `main`, one `h1`, `lang` (and
  `dir`); composes regions with layout primitives, no visual style.
- A view composes, never styles: no colour, type, border, component spacing, no `style` attribute (utility-first:
  layout utilities allowed).
- Headings in order, no skipped level; help and contact in the same place on every page.

## 11. Accessibility — WCAG 2.2 AA

Text 4.5:1, control/state 3:1, both schemes; reflow at 320 px; targets 24×24 px. By number:
`reference/accessibility.md` (read when checking a page or a derived colour pair).

- Native first: `<details>`/`<summary>` or `button` + `aria-expanded`/`aria-controls`; `button` acts, `a`
  navigates; a clickable `div` is a bug.
- `prefers-reduced-motion` turns motion off; `forced-colors` keeps borders and focus (`CanvasText`, `Highlight`);
  logical properties for RTL.
- House rules: quiet text 7:1 on a dark bar; a light outlined control on off-white has a 3:1 edge against it;
  2.4.13 focus appearance.

## 12. Words on the page

Plain user words; one term per meaning; structure by layout, not numbering; a number says what it counts
(`reference/words.md`).

## 13. Robust by construction

Escaping never bypassed with data; strict CSP, data never in `style`; no run-time third party; progressive
enhancement on server stacks; performance basics. Per-stack bypasses: `reference/robust.md`.

## 14. The pattern library

Every component in every state, real code, where `Gallery:` says: Storybook (renders server templates too) or a
dev-only gallery page. None named: Storybook with a Node build, else the gallery page. Fixtures with every state and an empty set; a check fails when a component is missing.

## 15. The checks

stylelint where there is a Node toolchain; else plain tests reading stylesheet and render code as text. One check
per rule: `reference/checks.md` (read when adding or running checks). Browser suite: axe, a 320 px reflow check, a
keyboard pass through the main flow.

## 16. Working on a page

1. Find the component; add a variant or slot. A behaviour that exists nowhere → new component at the lowest level
   that holds it, with contract and gallery entry.
2. Find the token; a new value = new token named for the decision.
3. Compose the view from layout primitives and components only.
4. Check both schemes, narrow + wide, empty + all-states fixture, keyboard, alignment, heading order, words.
5. Run these checks, then the project's own.

A pointed-at flaw ("this padding is off") is fixed in the component or token, then its twins found — never inside
one view.
