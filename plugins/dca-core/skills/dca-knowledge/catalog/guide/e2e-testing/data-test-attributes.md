---
type: Section
title: Data-Test Attributes
chapter: E2E Testing for Domain-Centric Architecture
source: guide
tags: [guide, section]
---

### The Problem

Brittle selectors couple tests to UI implementation details:

```java
// ❌ BAD: Breaks on text/CSS changes
page.locator("button:has-text('Add to Cart')").click();
page.locator(".product-card").first().click();
page.locator("a:has-text('View Details')").click();
```

### The Solution

Use `data-test` attributes to create a stable test contract:

```html
<!-- Template -->
<button data-test="product-add-to-cart-button">Add to Cart</button>
<a href="/products/1" data-test="product-view-details-link">View Details</a>
```

```java
// ✅ GOOD: Stable selectors
page.locator("[data-test='product-add-to-cart-button']").click();
page.locator("[data-test='product-view-details-link']").first().click();
```

### Naming Convention

Pattern: `{context}-{element}-{action}` (kebab-case)

| Element Type | Pattern | Example |
|--------------|---------|---------|
| Buttons | `{context}-{action}-button` | `product-add-to-cart-button` |
| Links | `{context}-{target}-link` | `cart-checkout-link` |
| Inputs | `{context}-{field}-input` | `buyer-email-input` |
| Containers | `{context}-{name}-container` | `product-card-container` |
| Forms | `{context}-{name}-form` | `buyer-info-form` |

### Examples by Feature

**Product Catalog:**
- `product-card-container`
- `product-view-details-link`
- `product-add-to-cart-button`
- `product-detail-container`

**Shopping Cart:**
- `cart-item-container`
- `cart-checkout-link`
- `cart-remove-item-button`

**Checkout:**
- `buyer-email-input`
- `buyer-continue-button`
- `checkout-place-order-button`
- `confirmation-message`

### A marker, not a position

**Rule: a locator names a stable marker of the element itself, never its position among siblings.**

A `data-test` attribute is stable only as long as the locator relies on nothing else. A position does:

```java
// ❌ BAD: the second title within one parent — breaks when each task gets an entry of its own
page.locator("//*[@data-test='task-title'][2]");

// ✅ GOOD: the task this test created, found by its marker and the value the test gave it
page.locator("[data-test='task']").filter(new Locator.FilterOptions().setHasText(title));
```

The first locator finds nothing as soon as a later change wraps each task in an element of its own, although
the page is right. The test then changes without a change in behaviour — the property Kent Beck's *Test
Desiderata* call *structure-insensitive* is lost. Where several elements carry the same marker, the test tells
them apart by the data it created itself ([Test Levels](/guide/testing-levels/a-test-that-holds.md)),
or the markup gives each one a marker of its own (`data-task-id`). Filtering by the test's own unique value
is not a selector by visible text: the value is the test's fixture, not the page's copy.

### Template Integration

```html
<!-- Before -->
<div class="product-card">
  <a href="/products/1">View Details</a>
  <button>Add to Cart</button>
</div>

<!-- After -->
<div class="product-card" data-test="product-card-container">
  <a href="/products/1" data-test="product-view-details-link">View Details</a>
  <button data-test="product-add-to-cart-button">Add to Cart</button>
</div>
```

---
