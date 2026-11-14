# Building-block digest

What a plan needs from each recipe: its opening sentence, the first sentence of each step and the templates it fills in, by path. Pick the kinds the change needs and read their digests; open the full recipe only for a decision a digest leaves open. The templates' code is read by whoever writes the code, not by the plan. Derived from `recipe/` on every run.

- [Add a bounded context](add-a-bounded-context.md) — Carve out a new top-level context package with its own domain / application / adapter layers and a hard boundary to every other context.
- [Add a browser runner to an existing project](add-a-browser-runner.md) — A project shows pages and has no way to drive a browser in its tests.
- [Add a bulk operation](add-a-bulk-operation.md) — Perform one operation over many aggregates at once — delete all, archive everything completed before a date, purge expired sessions.
- [Add a domain event and consumer](add-a-domain-event-and-consumer.md) — Record that something meaningful happened in the domain, and let another part of the *same* context react to it.
- [Add a read model](add-a-read-model.md) — Build a view for a query without going through the full aggregate write journey.
- [Add a repository with adapter](add-a-repository-with-adapter.md) — Give an aggregate root a persistence port: an interface in the application layer, an implementation in an outgoing adapter.
- [Add a store](add-a-store.md) — Give a context a persistence port for operational data that has **no aggregate of its own** — login attempts, an audit trail, metric snapshots, an event log.
- [Add a use case](add-a-use-case.md) — Add one application-layer use case (a single intention: place an order, add an item, get a product).
- [Add a value object](add-a-value-object.md) — Add an immutable value object — a concept defined by its attributes, with no identity (`Money`, `EmailAddress`, a quantity).
- [Add an aggregate](add-an-aggregate.md) — Add an aggregate root: the transactional consistency boundary that owns its invariants and emits domain events.
- [Add an anti-corruption layer](add-an-anti-corruption-layer.md) — Protect your domain from a foreign model — another bounded context or an external system.
- [Add an identity port](add-an-identity-port.md) — Give the application a way to learn *who is calling* without letting authentication leak into use cases or the caller leak into the domain.
- [Add an incoming REST adapter](add-an-incoming-rest-adapter.md) — Expose a use case to the outside world through a primary (driving) adapter.
- [Adopt existing behaviour into the backlog](adopt-existing-behaviour.md) — Describe what the system already does as a story, and let it count as delivered only with evidence.
- [Adopt the rules on existing code — scope, warn, ignore or freeze](adopt-the-rules-on-existing-code.md) — An existing code base switches the rule catalog on and the first run is red, often by hundreds of violations.
- [Bootstrap a new application](bootstrap-a-new-application.md) — Stand up a fresh Domain-Centric Architecture app from nothing: the building-block dependencies, the package skeleton, the rule catalog as a test, and the first bounded context.
- [Build DCA without a framework](build-dca-without-a-framework.md) — DCA does not need a container.
- [Expose an Open Host Service](expose-an-open-host-service.md) — Publish the public, stable capabilities of a bounded context so *other* contexts can call in — the provider side of the Open Host Service (OHS) pattern.
- [Hand a use case a second operation](hand-a-use-case-a-second-operation.md) — A use case needs what another use case already does — apply a list line by line through an existing operation, start a sub-run, settle a step.
- [Host a long-running process](host-a-long-running-process.md) — A process that runs for minutes or hours — a worker, a command-line run over many steps, a job — has state that belongs to the process, not to the domain: the claim on a resource, a lock, the working directory, the child processes it started, the signal that it should stop.
- [Isolate the data of integration tests](isolate-the-data-of-integration-tests.md) — Integration tests run the application against a real database.
- [Move a repository from memory to a database](move-a-repository-to-a-database.md) — Put an aggregate into a relational database **without touching the output port or the domain**.
- [Return expected refusals as a sealed result](return-expected-refusals-as-a-sealed-result.md) — A use case can be refused in ways its caller answers: the addressed thing is not there, it is not the caller's, the input is refused, a rule of the model refuses the change, a foreign system behind an output port refused or did not answer.
- [Put an end-to-end test's preconditions in place through the input port](seed-an-end-to-end-test-through-the-input-port.md) — An end-to-end test is about one interaction: the click, the form, the page under test.
- [Test a scenario integrated, the external system stubbed at the protocol](test-a-scenario-integrated.md) — Test one scenario of a story below the page: the use case runs through the wired application — its input port or its HTTP surface, whichever the scenario's `When` names — with real adapters and persistence as the project runs it in tests.
- [Test a use case](test-a-use-case.md) — Test a use case once, through its input port, in the wired application: real outgoing adapters, the store as the project runs it in tests (its own database engine in a container), an external system stubbed at the protocol.
- [Test an aggregate](test-an-aggregate.md) — Test an aggregate root as a pure domain unit test: no mocks, no Spring, no infrastructure.
