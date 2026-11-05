---
name: frontend
description: The craft of a maintainable web frontend, carried out the way the project's description decides — design principles, cascade layers and one owner per style in the styling method the project chose (native @scope, BEM, scoped styles, utility classes or a component library), state in attributes, tokens in three tiers with themes and light/dark, scales with floors, intrinsic layouts with container queries and named widths, components with a contract, landmarks, WCAG 2.2 AA, a gallery with fixtures, and the checks that keep it. Use when building or changing a page, component, layout, template or stylesheet, when a delivery stage needs the frontend craft, or when a frontend has drifted ("make the spacing consistent", "add a theme", "/frontend"). Stack-neutral: server templates, React, Vue, Svelte or plain HTML.
---

# A frontend that stays maintainable

A frontend drifts one screenshot at a time: a padding fixed here, a colour copied there, a second way of opening
a panel. Each fix looks harmless; after fifty of them nothing lines up and nobody dares change the stylesheet.
Everything below stops that drift at its source: **one component per behaviour, one token per decision, one
place per rule — and a check that says so.**

The rules are stated as principles; where a stack spells one differently, the spelling is given beside it.
Rules marked **house rule** go beyond WCAG 2.2 AA on purpose; a project may drop them, it may not drop AA.

## 0. Read the project first

Before writing a line, find what the project already decided:

- the project instructions (`AGENTS.md`) and the technical description (a `tech.md` or similar): its frontend
  approach, and in it the **`Browsers:`** it serves, the **`Styling:`** method (section 3) and the **`Gallery:`**
  (section 14) it chose
- **whether the stack scopes styles** — CSS Modules, Vue `<style scoped>`, Svelte, Shadow DOM — or whether every
  class is global (server templates, plain HTML)
- existing tokens, a component folder, a gallery or Storybook, a theme file, a lint config (stylelint)
- the browser tests' selectors (`data-test` attributes are a contract)

**The description decides how; this skill offers the ways and their reasons.** Where it names a method, follow
it and say so. Where it names none, take the default of section 3 for the browsers it serves and say which, so
the person can confirm it into the description — in a delivery pipeline, a question to record, not a guess for
the next page to contradict. Never mix methods. A rule here that contradicts the description is a finding to
raise, not a change to slip in.

## 1. Design principles

Each is checkable on a screenshot:

1. **One primary action per view**; everything else is visibly secondary.
2. **Hierarchy through weight, colour and space before size** — not a sixth font size.
3. **Grouping by proximity** — the space inside a group is smaller than the space between groups.
4. **One alignment line per region**; text, icons and controls start on it.
5. **Restraint** — at most two typefaces, the steps of one type scale, the colours of the token set.
6. **Colour carries meaning, never alone** — a state also has a word or a shape.
7. **Every state is visible** — hover, focus, selected, disabled, invalid, busy, empty.

## 2. CSS architecture

- **Cascade layers set the order once**: `@layer reset, base, tokens, layout, components, utilities;`.
  Unlayered CSS beats every layer — a theme file may be unlayered on purpose (it wins), third-party CSS goes
  into a named layer.
- **A short modern reset** (box-sizing, margins, media defaults, inherited fonts on controls), not a 400-line
  normalize.
- **Flat specificity**: one class per selector where possible; no id selectors for style; no `!important` except
  in the `utilities` layer and in user-preference overrides (`forced-colors`, reduced motion).
- **One file (or one style module) per component**, named like it; tokens in one file; layout primitives in one.
- **Utilities are helpers, not a second method**: a few single-purpose classes (`visually-hidden`, a flow
  spacer) in the last layer. A project that is utility-first follows its own rules instead (section 0).

## 3. Ownership and naming

The principle, in every stack:

- **One owner per style.** A component's markup and its styles live together (a partial or macro plus its block;
  a component file plus its style module or `<style scoped>`), and nothing else renders that markup.
- **No reach-in.** A component never styles another component's inside. A rule that names two components may
  only **place** the inner one (margin, grid area, order, alignment) — never its colour, font, padding, border or
  size. Framework escape hatches (`:deep`, `:global`, `::part`) are the reviewed exception.
- **A component writes only its own classes.** Children get content through props, slots or parameters — never
  a class to wear.

**The styling method — the description's `Styling:` line chooses one.** Every method keeps the three rules above;
they differ in who enforces them. BEM was the answer to a CSS that was global and had no layers; the language now
does that itself, so the names are a fallback, not the goal (`reference/styling.md` shows each in code):

| Method | Spelling | Enforced by | Choose it when |
|---|---|---|---|
| native scoping | the root named for what it *is* (`.card`), short local names inside (`.title`); `@scope (.card) to (.card-slot)` stops at nested components; variants as `data-variant`, state as attributes | the browser | the pages serve current browsers only — the default there |
| BEM names | `block`, `block__element`, `block--modifier`, inside cascade layers | discipline and checks | older browsers must be served — the default there (`@scope` is Baseline since 2026; a browser without it drops the whole block) |
| the framework's scoped styles | one style module or `<style scoped>` per component, plain names | the build | React with CSS Modules, Vue, Svelte |
| utility classes | Tailwind classes on the element | the build | the project chose it |
| a component library | its components and theming API, nothing restyled | the library | the project named one |

In every method: the component's root is named for what it *is*, never for where it sits or how it looks; a
variant is an attribute or a modifier of its own component; no unscoped descendant selector inside a component
(`.card .body p` is wrong) except for children it owns (`.icon > svg`).

**Content zones.** Written text from outside (markdown, a CMS, a long help text) is the one place where tag
selectors style headings, paragraphs and lists: inside one `.prose` block, never globally.

Classes are for style, `data-test` for tests, `data-*` for state and behaviour hooks. A test never selects by a
style class; a script never reads a style class to decide behaviour.

## 4. State

- **State is an attribute the CSS selects**: the ARIA state where one exists (`aria-expanded`, `aria-current`,
  `aria-selected`, `aria-invalid`, `aria-busy`), otherwise `data-state="…"`. No `is-open`/`active`/`error`
  classes, and a script never toggles a class to show state (in React or Vue, `data-state={state}` is as easy as
  a computed `className` and keeps one vocabulary).
- **One mapping from state to tone**, set on the component root:
  `.pill[data-state="fail"] { --tone: var(--color-danger); }` — the component paints with `--tone`. Set it on the
  root, not on `:root`: custom properties inherit, and a tone set too high leaks into nested components.
- **State words come from the product**, the same word in markup, script, copy and tests.
- **UI state is keyed by identity, not by position**: an opened panel, a selection, a field's draft survive a
  re-render because they are keyed by the item's id and the place it is shown in (the same item in two places
  opens independently). State worth sharing or reloading lives in the URL.

## 5. Tokens

Every design decision is a CSS custom property. Nothing else in the stylesheet carries a literal colour, font
stack or length (hairline borders and values a check allows excepted).

**Three tiers:**

| Tier | What it is | Example | Who reads it |
|---|---|---|---|
| primitive | the raw palette and scales | `--blue-600`, `--space-4` | the semantic tier only |
| semantic | the decision: what a value is *for* | `--color-action`, `--color-danger`, `--color-surface`, `--text-body` | components, layout, theme |
| component | a documented hook of one component | `--button-bg`, `--card-padding` | that component |

- **The product's own states alias the semantic tier** (`--color-pass: var(--color-success)`), so a red brand
  never turns "done" red and a theme can repaint one state alone.
- **Component hooks with a fallback**: `background: var(--button-bg, var(--color-action));` — a theme or a parent
  can set the hook; without it the semantic token applies.
- **Public tokens** = the semantic tier plus the documented component hooks. That is all a theme may override.
- **Naming**: `--<category>-<role>[-<variant>]` for semantic tokens, `--<block>-<property>` for hooks; one name
  per decision, no synonyms.
- **Renaming** keeps the old name as an alias of the new one for one release, marked deprecated, and a check fails
  when a component still reads it.
- **DTCG JSON, Style Dictionary or `@property`** only where tokens must leave CSS (native apps, design tools) or
  must animate; optional.

## 6. Theming

- **Theme and scheme are two axes.** A *theme* is a colour world (a brand, a white-label customer); a *scheme* is
  light or dark. Every theme has both schemes, so each has its own attribute: `data-theme="<name>"` picks the
  colour world, `data-scheme="light|dark"` overrides the system's choice (absent: the system decides).
- **Light and dark** through `color-scheme` and `light-dark(<light>, <dark>)`, each colour token written once per
  theme: `:root[data-scheme="dark"] { color-scheme: dark; }`. Dark mode is never a second stylesheet and never
  per-component overrides.
- **Derived colours are computed**: hover, soft backgrounds, borders and text-on-colour come from the semantic
  tokens through `color-mix()` or relative colour (`oklch(from var(--color-action) …)`). Re-check the contrast of
  every derived pair (section 11).
- **A theme is a file, not a fork**: an optional stylesheet loaded after the page's own (or unlayered), that
  reassigns public tokens and nothing else. Ship an example theme listing every public token with its default; a
  check keeps the example and the token file naming the same set.
- **Optional**: a theme folder with logo, favicon and fonts for white-label products; several themes side by side
  on one page, each `data-theme` set on its own subtree.

## 7. Spacing and type

- **One spacing scale** (`--space-1 … --space-8`); every margin, padding and gap uses a step. Optional: a
  `--density` factor multiplying the scale, fluid steps with `clamp()`.
- **Components own their padding; parents own the space between them.** A component sets no outer margin; the
  parent spaces its children with `gap` or a stack primitive. (A project whose components carry a bottom margin —
  GOV.UK does — keeps it.)
- **A type scale** (`--text-xs … --text-3xl`, one ratio around 1.2–1.25) in `rem`, never `px`, so text resizes.
  Floors, a **house rule**: body text 16 px, small reading text (a hint, a card's line, a figure) 14 px, 12 px
  only for fine print (a column head, a label in capitals, a count). Text in a scaled drawing is measured at the
  size it is drawn at.
- **Line height** 1.4–1.6 for reading text, tighter for headings; no fixed heights on boxes holding text (text
  spacing must be able to grow).
- **A reading width** of its own: long text is capped at about 65–75 characters inside the content zone, separate
  from the layout's widths.
- **Control sizes as a scale** (`--control-s|m|l`): every button, select, input and chip takes one, so two
  controls of one size never differ because one has a border; the smallest still meets the 24×24 px target.
- **Icons are drawn, not typed**: SVG (or CSS) marks with `aria-hidden="true"`, the name on the control — never a
  font glyph like × or ▾, which sits on its own metrics and is never centred.
- **Marks align to text, not to boxes**: an icon or a dot beside text aligns with its cap height or baseline.
  `text-box: trim-both cap alphabetic` where the browser policy allows it, a cap-relative margin otherwise.
- **Named insets**: where content must line up with something (a panel's text with its title after a caret), the
  offset is a token computed from its parts, never a number tuned by eye.
- Optional: radius by role (`--radius-control`, `--radius-card`).

## 8. Layout

- **Intrinsic layout primitives first**: stack (vertical rhythm), cluster (wrapping row), sidebar (side column
  that drops below when narrow), switcher, center (max width), grid (`repeat(auto-fit, minmax(<min>, 1fr))`). They
  adapt without breakpoints and carry no visual style.
- **Flex for flow along one axis, grid for placement in two.** `subgrid` where rows of nested parts must line up.
- **Container queries for components** (`container-type: inline-size` on the region that holds them): a component
  adapts to its container, so it works in a drawer and in a wide page. Media queries for the page frame only.
- **A few named widths**, each a token with a name for the decision (narrow, wide, reader), and a check that the
  stylesheet uses no other. A script that needs a width (custom properties do not work in media queries) holds a
  copy, and a check keeps it equal.
- **A drawing** (an SVG diagram, a chart) shrinks with its container down to the width at which its smallest text
  reaches the type floor, then scrolls inside its own box — never the page.
- **A column grid** (12 columns) only where the design has one.

## 9. Components

- **Three working levels**: **primitives** (one element: button, input, label, pill, icon — atoms), **components**
  (several primitives acting as one or a section with its own job: form row, card, table, accordion, dialog —
  molecules and organisms), **views** (a page: a template filled with data). Every piece is on one level.
- **A component uses only lower levels**; circular use is a design error.
- **Same behaviour, same component.** Two things that open and close are both the accordion. A second
  implementation of an existing behaviour is the drift this skill prevents — extend the component instead.
- **A contract**, written where the component lives: its variants (modifiers or a `variant` prop), its sizes
  (the control scale), its states, its slots or content areas, and which hooks a theme may set. **Composition over
  configuration**: a slot beats the tenth boolean prop.
- **No one-off overrides**: a view that needs a new look adds a variant to the component, it does not style the
  instance.
- **A field is always a form row**: label, control, hint and error joined by one component that wires `for`/`id`,
  `aria-describedby` and the error state. No view places a bare input.

## 10. Templates and pages

- **A template is the frame**: landmarks (`header`, `nav`, `main`, `aside`, `footer`), a skip link to `main`, one
  `h1`, `lang` on the root (and `dir` where needed). It composes regions with layout primitives and carries no
  visual style of its own.
- **A view composes, it never styles**: it calls components and layout primitives and passes data and options. It
  sets no colour, type, border or component spacing, and no `style` attribute (a utility-first project allows its
  layout utilities here).
- **Headings in order**, no skipped level; help and contact sit in the same place on every page.

## 11. Accessibility — WCAG 2.2 AA

The floor is WCAG 2.2 AA; `reference/accessibility.md` lists it by number. In short: contrast 4.5:1 for text
and 3:1 for what identifies a control or its state, in both schemes; meaning never by colour alone; text resizes,
reflows at 320 px and takes wider spacing; focus visible and never hidden under a sticky bar; targets 24×24 px;
help in the same place, errors named with their fix, no asking twice, no blocked paste.

- **Native first**: `<details>`/`<summary>` or a `button` with `aria-expanded`/`aria-controls`; `button` for
  actions, `a` for navigation; a `div` with a click handler is a bug.
- **User preferences**: `prefers-reduced-motion` turns motion off; `forced-colors` keeps borders and focus
  visible (`CanvasText`, `Highlight`); logical properties (`margin-inline-start`) so right-to-left works.

House rules above AA, where the project keeps them: quiet text at 7:1 on a dark bar; a light outlined control on
an off-white background with an edge that holds 3:1 against it; 2.4.13 focus appearance.

## 12. Words on the page

Plain language in the user's words; one term per meaning across labels, states, help and tests; structure through
layout, not numbering; a number says what it counts. `reference/words.md` has each with its example.

## 13. Robust by construction

Text goes in as text — the stack's escaping is never bypassed with data; a strict CSP where the project controls
headers, data never in a `style` attribute; no third party at run time; progressive enhancement on server stacks;
the performance basics. `reference/robust.md` names each, with the bypasses per stack.

## 14. The pattern library

Every component in every state, rendered by the real code, where the description's `Gallery:` line says: Storybook
(it renders server templates too) or a development-only gallery page. Named none: Storybook with a Node build,
the gallery page otherwise. Fixtures with every state and an
empty set; a check fails when a component is missing.

## 15. The checks

A rule nobody checks erodes. Prefer **stylelint** where the stack has a Node toolchain; elsewhere plain tests that
read the stylesheet and the render code as text (browser tests assert behaviour, these assert the source's shape):

`reference/checks.md` lists one check per rule — tokens, flat specificity, naming, no reach-in, state, views
compose, fields, the type floor, the named widths, the public token set, the gallery, and a sanity check.

In the browser suite: an automated accessibility check (axe), a 320 px reflow check and a keyboard pass through
the main flow.

## 16. Working on a page

1. **Find the component.** Use it; add a variant or a slot if needed. Only a behaviour that exists nowhere gets a
   new component — at the lowest level that holds it, with its contract and its gallery entry.
2. **Find the token.** A new value is a new token named for the decision, never a literal.
3. **Compose the view** from layout primitives and components only.
4. **Check** both schemes, the narrow and the wide width, the empty and the all-states fixture, the keyboard; look
   at the alignment lines, the heading order and the words.
5. **Run the checks**, then the project's own.

When someone points at one spot ("this padding is off"), fix it **in the component or the token**, so every place
that uses it is fixed at once — then look for the twins that show the same flaw. A fix inside one view is the
start of the next drift.

## 17. Checklist

- [ ] project conventions read; where they speak, they were followed
- [ ] the screenshot passes the seven principles
- [ ] layers, flat specificity, one owner per style, no reach-in, state in attributes
- [ ] no literal outside the tokens; components read semantic tokens and their own hooks
- [ ] light and dark from one token set; the example theme names every public token
- [ ] spacing, type and control size from the scales; floors held; no outer margin on components
- [ ] intrinsic layouts, container queries, only the named widths
- [ ] every new piece on one level, with its contract, in the gallery; views and templates write no visual style
- [ ] WCAG 2.2 AA by number; house rules labelled
- [ ] plain words, one term per meaning
- [ ] escaping never bypassed with data; state survives a re-render
- [ ] the checks pass
