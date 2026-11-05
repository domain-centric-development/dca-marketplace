# The styling methods, in code

The skill's section 3 names five methods; the description's `Styling:` line chooses one. The same card in each —
a root, a title, a slot that may hold another component, a variant and a state.

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

`@scope` is Baseline since 2026: a browser without it drops the whole block, so the component stands unstyled.
Serve it only where the description's `Browsers:` are current ones.

## BEM names, in cascade layers

```css
@layer components {
  .card { padding: var(--card-padding, var(--space-4)); }
  .card__title { font-size: var(--text-lg); }
  .card--quiet { background: var(--color-surface-quiet); }
  .card[data-state="fail"] { --tone: var(--color-danger); }
}
```

The names carry what the browser cannot enforce in older versions: the owner (`card__`) and flat specificity. A
check keeps them honest — every class a known block, element or modifier; no element of one block under another.

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

CSS Modules (`styles.title`) and Svelte work the same way. `:deep()`, `:global()` and `::part()` reach into
another component — each is a reviewed exception.

## Utility classes

```html
<article class="rounded-lg p-4 data-[variant=quiet]:bg-surface-quiet" data-variant="quiet">
  <h3 class="text-lg">…</h3>
</article>
```

The tokens are the theme's variables (`@theme`); a repeated class list becomes a component of the stack, not a
copy. State and variant stay attributes.

## A component library

Use its components and its theming API (its tokens, its variants). Nothing restyles a library component from
outside; a look it does not offer is a request to the library's theme, or a component of the project's own.
