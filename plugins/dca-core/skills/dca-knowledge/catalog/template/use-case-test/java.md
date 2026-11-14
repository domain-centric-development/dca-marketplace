---
type: Template
title: "Use-case port test skeleton (the input port in the wired application) — Java"
parent: /template/use-case-test.md
tags: [template, testing, use-case]
review: draft
owner: DCA catalog maintainers
evidence: [/guide/testing-levels.md, /marker/port-in/usecase.md, /marker/port-out/repository.md, /marker/port-out/domaineventpublisher.md, /marker/application/refusal.md]
applies_to: [java]
framework: [spring]
---

The Java code of [Use-case port test skeleton](/template/use-case-test.md). The prose, the evidence and what
governs it stay in that node; this file carries the skeleton only.

## `{Name}UseCaseTest.java` — the use case through its input port

```java
package {basePackage}.{context}.application.{usecasename};

import static org.junit.jupiter.api.Assertions.*;

import {basePackage}.{context}.application.shared.{Aggregate}Repository;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

// The application as it runs in tests: real adapters, the project's database in a container,
// an external system stubbed at the protocol. The project's base class or extension isolates the store.
@SpringBootTest
@DisplayName("{Name}")
class {Name}UseCaseTest {

  @Autowired private {Name}InputPort useCase;
  @Autowired private {Aggregate}Repository repository;   // read back what the use case stored
  @Autowired private Create{Aggregate}InputPort create{Aggregate};

  @Test
  @DisplayName("{one behaviour, stated in ubiquitous language}")
  void {behaviour}() {
    // Arrange — the Given, through the input port, with values of this test's own
    String title = "{a value} " + UUID.randomUUID();
    {Aggregate}Id id = givenA{Aggregate}(title);

    // Act — once
    {Name}Result result = useCase.execute(new {Name}Command(id /* , ... */));

    // Assert — the outcome: the result and what is stored, never a call
    assertInstanceOf({Name}Result.{Done}.class, result);
    assertEquals(title, repository.findById(id).orElseThrow().title());
  }

  private {Aggregate}Id givenA{Aggregate}(String title) {
    // A helper that arranges state through a use case asserts that it succeeded.
    return assertInstanceOf(
            Create{Aggregate}Result.Created.class,
            create{Aggregate}.execute(new Create{Aggregate}Command(title)))
        .id();
  }
}
```

## Testing a refusal — two variants

The test asserts the refusal with its values, in the form the context carries it.

```java
  @Test
  @DisplayName("refuses {a missing aggregate}")
  void refusesMissing() {
    {Aggregate}Id unknown = {Aggregate}Id.generate();   // an id nobody stored
    {Name}Command command = new {Name}Command(unknown);

    // Thrown: the exact type, never a parent
    {Aggregate}NotFound refusal = assertThrows({Aggregate}NotFound.class, () -> useCase.execute(command));
    assertEquals(unknown, refusal.id());

    // Returned: the exact case and its values
    // {Name}Result.{Aggregate}NotFound refusal =
    //     assertInstanceOf({Name}Result.{Aggregate}NotFound.class, useCase.execute(command));
    // assertEquals(unknown, refusal.id());

    // Either way nothing was stored
    assertTrue(repository.findById(unknown).isEmpty());
  }
```

Keep the variant of the context and drop the other. An incoming adapter that shows this refusal has its own test
against a stubbed input port; its stub answers with exactly the refusal asserted here — the same returned case, or
the very failure type thrown.

## Where the store comes from

The application's tests run against the engine production runs, started once per test run in a container; the
outgoing adapters are the production ones. An in-memory adapter that remains in the test sources is no stand-in for
them here: it does not roll back, lock or map types as the database does
([an in-memory store hands out live aggregates](/pitfall/an-in-memory-store-hands-out-live-aggregates.md)). An
external system the use case calls is a real HTTP server on a free port, its address handed to the application
through configuration ([Test a scenario integrated](/recipe/test-a-scenario-integrated.md)).
