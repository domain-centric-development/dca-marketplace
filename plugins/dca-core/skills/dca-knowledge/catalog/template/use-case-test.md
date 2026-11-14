---
type: Template
title: "Use-case port test skeleton (the input port in the wired application)"
tags: [template, testing, use-case]
review: draft
owner: DCA catalog maintainers
evidence: [/guide/testing-levels.md, /marker/port-in/usecase.md, /marker/port-out/repository.md, /marker/port-out/domaineventpublisher.md, /marker/application/refusal.md]
applies_to: [java]
framework: [spring]
---

Domain-free skeleton for a use case's port test. It takes the input port from the wired application, drives it with a `Command`/`Query`, and asserts the `Result` and what is stored — with the real outgoing adapters and the store as the project runs it in tests. No output port is faked or mocked. Real domain objects are used directly. Replace `{Name}` (use case), `{Aggregate}`, `{context}` / `{basePackage}`. A refusal is asserted in the form the context carries it — the thrown exception's exact type, or the returned case — with its values; the Java node shows both.

The test's data is its own: a value made unique per test, kept in a variable the assertion uses. The store is isolated between tests by the project's one shape — a reset to a known state, or a database per application instance ([Isolate the data of integration tests](/recipe/isolate-the-data-of-integration-tests.md)).

## Languages

The code lives in one child node per language, so the prose below is written once and a
further language is one more file rather than a second copy of this node.

- Java — [`use-case-test/java.md`](/template/use-case-test/java.md)

## Realizes / governed by

- Guide: [Test levels](/guide/testing-levels.md)
- Markers: [UseCase<INPUT, OUTPUT>](/marker/port-in/usecase.md) · [Repository<T, ID>](/marker/port-out/repository.md) · [DomainEventPublisher](/marker/port-out/domaineventpublisher.md) · [Refusal](/marker/application/refusal.md)
- Recipe: [Test a use case](/recipe/test-a-use-case.md) · [Add a use case](/recipe/add-a-use-case.md) · [Test a scenario integrated](/recipe/test-a-scenario-integrated.md)
