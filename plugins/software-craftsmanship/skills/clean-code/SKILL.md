---
name: clean-code
description: |
  Applies Clean Code, Pragmatic Programmer, and Refactoring principles during
  code edits: meaningful names, small functions, no comment smell, SLAP (Single
  Level of Abstraction), DRY with judgment, Boy-Scout-Rule. Complements
  language-specific style guides; does not replace formatters.
disable-model-invocation: false
---

# /clean-code — Clean-Code principles while writing

This skill is a **set of writing principles**, not a linter. It guides what
Claude *types* — naming choices, function size, comment discipline. Formatters
handle whitespace; this skill handles judgment.

Sources: Bob Martin's *Clean Code*, Hunt/Thomas's *Pragmatic Programmer*,
Fowler's *Refactoring* (smells + named techniques).

## Names

- **Verbs for functions**, nouns for classes, adjectives or short noun phrases
  for booleans (`isEmpty`, `hasPaidInvoice`, not `getEmpty`).
- **Domain words, not technical words.** `placeOrder` beats `processData`.
  `Customer` beats `UserDto` in domain code (DTOs belong in adapters anyway).
- **No encoding prefixes.** Don't use `I` for interfaces, `m_` for fields,
  `str` for strings. Modern IDEs make these noise.
- **No disinformation.** A `Map<UserId, User>` named `userList` lies. So does
  a parameter `accountInfo` that's a single string.
- **Searchable names.** Avoid single-letter names except in tiny scopes
  (lambdas, loop counters).
- **Pick one word per concept.** `fetch`, `retrieve`, `get` for the same
  operation across the codebase = three searches instead of one.

## Functions

- **One function = one task** at one level of abstraction.
- **Short.** ~20 lines is a *smell threshold*, not a hard rule. If a 40-line
  function is genuinely linear and reads top-to-bottom, leave it. If a
  15-line function has three nested ifs, split it.
- **Few parameters.** 0-2 is fine, 3 is borderline, 4+ suggests a Parameter
  Object (Java record / value object).
- **No flag parameters.** `process(item, /*async=*/ true)` should be
  `processAsync(item)` and `processSync(item)`.
- **No hidden side effects.** A function called `validate` should not also
  *save* to a database. Name reflects the full effect.

## SLAP — Single Level of Abstraction Per function

Inside one function, all statements live at the same conceptual level.

Bad (mixed levels):

```java
public Order placeOrder(Cart cart) {
    var lines = new ArrayList<OrderLine>();
    for (var item : cart.items()) {                       // <-- low level
        lines.add(new OrderLine(item.productId(), item.qty()));  // low
    }
    Order order = Order.create(cart.customerId(), lines); // high level
    publishEvent(new OrderPlaced(order.id()));            // high level
    return order;
}
```

Good (separated):

```java
public Order placeOrder(Cart cart) {
    Order order = Order.create(cart.customerId(), toOrderLines(cart));
    publishEvent(new OrderPlaced(order.id()));
    return order;
}

private List<OrderLine> toOrderLines(Cart cart) {
    return cart.items().stream()
        .map(item -> new OrderLine(item.productId(), item.qty()))
        .toList();
}
```

## Comments

**Default: don't write a comment.** Make the code say it.

When a comment **is** warranted:

- **Why, not what.** Document non-obvious constraints, hidden invariants,
  surprising tradeoffs.
- **Workarounds.** "We avoid `Stream.parallel()` here because the JDBC driver
  isn't thread-safe under load — see incident-2024-03." That comment earns
  its keep.
- **Public API / library boundary.** Javadoc on exported types.

**Comment smells (delete on sight):**

- Restating the code: `// increment i` next to `i++`.
- Journal comments: `// 2024-03-15: bug fix`.
- Commented-out code: delete it. Git remembers.
- TODOs with no owner or date that are >6 months old.

## DRY with judgment

Three similar lines are not yet a duplication problem. Two-three-four occurrences
of similar code are sometimes simpler than the abstraction that would unify
them.

Apply **Rule of Three**: extract on the third occurrence — when the *shape*
of the duplication is stable. Premature abstraction is harder to undo than
duplication.

When duplication *is* worth extracting, name the extraction by **intent**, not
shape:

- Good: `validateOrderPlaceable(order)`
- Bad: `helper1(order)`, `commonChecks(order)`

## Code smells (from Fowler's *Refactoring*) — flag these

| Smell | Fix (named refactoring) |
|---|---|
| Long Method | Extract Method, Replace Temp with Query, Decompose Conditional |
| Long Parameter List | Introduce Parameter Object, Preserve Whole Object |
| Feature Envy (method talks more to another class's data than its own) | Move Method |
| Data Clumps (same 3-4 params travel together) | Extract Class / Parameter Object |
| Primitive Obsession (lots of `String`, `int` standing in for domain concepts) | Replace Primitive with Value Object |
| Shotgun Surgery (one change touches many classes) | Move Method/Field to consolidate |
| Comments-as-Crutch | Extract Method (name the explained section) |
| Dead Code | Delete |
| Speculative Generality (unused flexibility) | Inline / Collapse Hierarchy |
| Switch on type | Replace Conditional with Polymorphism |

## Boy-Scout Rule

Leave touched code a little cleaner than you found it. Bounds:

- **Adjacent to the change**, not anywhere in the file. No drive-by refactors
  in a feature commit.
- **Mechanical and obvious.** Rename a poorly-named local, extract a
  three-line block, delete dead code. Not "rewrite the architecture."
- **Reversible.** If the cleanup is risky, do it as a separate commit so
  reviewers can isolate the feature change.

## Formatting & style

This skill does **not** auto-reformat. It works alongside whatever formatter
the project has configured. Read
`<project-root>/.claude/dca/conventions.md` for the project's formatter
command (e.g. `./gradlew spotlessApply`); offer to run it at the end of a
larger edit, but don't reformat invisibly mid-edit.

## What this skill flags during editing

When Claude is about to write code that has a smell:

- **Long Method incoming**: "This function is approaching 40 lines mixing
  validation, mapping, and persistence. Extract the validation block?"
- **Primitive Obsession**: "We're passing `(String customerId, String
  productId, int qty)` — these are domain concepts. Introduce
  `OrderLineDraft` record?"
- **Comment-as-crutch**: "This block has a comment explaining what it does.
  Extract it into a named method instead?"

The skill **proposes**; the user decides.

## Not in scope

- Formatting (use the formatter)
- Performance optimization (separate concern)
- Architectural review (use `dca-discipline` or reviewer agents)
- Test design (use `tdd`)
