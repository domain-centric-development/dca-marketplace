# The styling methods, in code

One card per method (section 3): root, title, slot for another component, variant, state.

| Method | Spelling | Enforced by | Choose when |
|---|---|---|---|
| native scoping | `.card` root, local `.title`; `@scope (.card) to (.card-slot)`; `data-variant` | browser | current browsers only — default there |
| BEM names | `block__element`, `block--modifier`, in layers | checks | older browsers — default there (no `@scope` = block dropped) |
| framework scoped | style module / `<style scoped>`, plain names | build | React + CSS Modules, Vue, Svelte |
| utility classes | Tailwind | build | project chose it |
| component library | its components + theming API, nothing restyled | library | project named one |

## Native scoping (`@scope`, cascade layers, attributes)

```css
@layer components {
  @scope (.card) to (.card-slot) {          /* stops at the slot: a nested component is never styled from here */
    :scope { padding: var(--card-padding, var(--space-4)); border-radius: var(--radius-card); }
    .title { font-size: var(--text-lg); }
    :scope[data-variant="quiet"] { background: var(--color-surface-quiet); }
    :scope[data-state="fail"] { --tone: var(--color-danger); }
  }
}
```

```html
<article class="card" data-variant="quiet" data-state="fail">
  <h3 class="title">…</h3>
  <div class="card-slot"><!-- another component, untouched by .card's rules --></div>
</article>
```

`@scope` is Baseline since 2026; a browser without it drops the whole block. Only where `Browsers:` are current.

## BEM names, in cascade layers

```css
@layer components {
  .card { padding: var(--card-padding, var(--space-4)); }
  .card__title { font-size: var(--text-lg); }
  .card--quiet { background: var(--color-surface-quiet); }
  .card[data-state="fail"] { --tone: var(--color-danger); }
}
```

Names carry owner (`card__`) and flat specificity. Check: every class a known block, element or modifier; no
element of one block under another.

## The framework's scoped styles

```vue
<template>
  <article class="card" :data-variant="variant" :data-state="state">
    <h3 class="title"><slot name="title" /></h3>
    <slot />
  </article>
</template>
<style scoped>
.card { padding: var(--card-padding, var(--space-4)); }
.title { font-size: var(--text-lg); }
.card[data-variant="quiet"] { background: var(--color-surface-quiet); }
</style>
```

CSS Modules (`styles.title`) and Svelte alike. `:deep()`, `:global()`, `::part()` = reviewed exception.

## Utility classes

```html
<article class="rounded-lg p-4 data-[variant=quiet]:bg-surface-quiet" data-variant="quiet">
  <h3 class="text-lg">…</h3>
</article>
```

Tokens = the theme's variables (`@theme`); a repeated class list becomes a component, not a copy. State and
variant stay attributes.

## A component library

Its components and theming API (tokens, variants) only. Nothing restyles a library component from outside; a look
it lacks → its theme, or a component of the project's own.
