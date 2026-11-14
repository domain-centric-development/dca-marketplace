# Unit tests: every invariant, its guards included

A unit test drives one aggregate, entity, value object or domain service alone — no framework, no container, no
database. It is the part of the suite that survives a rewrite of every adapter.

## What gets a unit test

- **Every rule a domain type enforces is an invariant, and every invariant has its own test**: a task completed
  twice, an order line with a negative quantity, a title longer than allowed.
- **The guards are invariants too**: a value that is required, trimmed, within a range, unique within its aggregate.
  A criterion rarely names them, because the page trims and the form requires — which is why they need their own
  test: the next caller is not the page. A guard nobody named as an invariant is not written.
- **A range is tested at both bounds**; a trimmed value is refused untrimmed or stored trimmed, whichever the rule says.
- **A use case gets no unit test.** Its port test runs it in the wired application; a second test of the same path
  with doubles proves the doubles.

A unit test is never a criterion's test. It stands in the `Invariants` table, one row per rule.

## How

- Construct the type with the values the rule is about, visible in the test; a builder gives the rest.
- Assert the outcome — the refusal and its type, the new state — never a private field or a call.
- A refusal is asserted as the exact failure type or the exact returned case, with its values.
- Time and chance come in as parameters or injected sources: a fixed clock, a seeded source.
- Never double a value object; build the real one.

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

The `repeat` builds the input, not the expected value; the rule against logic in a test is about what is asserted.

## A rule the code already has

A test of a rule the code does not have yet is red before the rule is built — that is its proof. A test of a rule
that exists already is green at once. Break it: change the production code minimally so the rule is gone, see the
test turn red, revert. A test that stays green under its break does not guard the rule.
