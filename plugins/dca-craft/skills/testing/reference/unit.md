# Unit tests: every invariant, its guards included

One aggregate, entity, value object or domain service alone — no framework, container or database.

## What gets a unit test

- **Every rule a domain type enforces has its own test** (completed twice, negative quantity, title too long).
- **Guards are invariants too** — required, trimmed, in range, unique within the aggregate — and need their own test
  even when the page trims and the form requires: the next caller is not the page. A guard nobody named as an
  invariant is not written.
- **A range at both bounds**; a trimmed value refused untrimmed or stored trimmed, as the rule says.
- **No unit test for a use case** — its port test runs it.

Never a criterion's test; it stands in the `Invariants` table, one row per rule.

## How

- Construct with the rule's values visible in the test; a builder gives the rest.
- Assert the outcome — the exact failure type or returned case with its values, the new state — never a private
  field or a call.
- Time and chance as parameters or injected sources (fixed clock, seeded source).
- Never double a value object.

```java
@Test
void refusesATitleLongerThanAllowed() {
    String tooLong = "x".repeat(Title.MAX_LENGTH + 1);

    assertThatThrownBy(() -> new Title(tooLong))
        .isInstanceOf(TitleTooLong.class);
}
```

```csharp
[Fact]
public void RefusesATitleLongerThanAllowed()
{
    var tooLong = new string('x', Title.MaxLength + 1);

    Assert.Throws<TitleTooLong>(() => new Title(tooLong));
}
```

`repeat` builds the input, not the expected value — allowed.

## A rule the code already has

The test is green at once. Break the rule minimally in production code, see red, revert. Green under its break =
does not guard the rule.
