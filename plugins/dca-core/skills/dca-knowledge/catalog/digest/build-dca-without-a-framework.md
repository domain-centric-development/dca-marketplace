# Build DCA without a framework — digest

Node: `/recipe/build-dca-without-a-framework.md` — cite it by that path; read it in full only for a decision this digest leaves open.

DCA does not need a container.

## Steps (first sentence each)

1. **Lay out the package as DCA does.** Per bounded context `domain/`, `application/`, `adapter/incoming/`, `adapter/outgoing/`; one `infrastructure/` for the composition root and the process host; the building blocks and the shared kernel beside the contexts.
2. **Write the building blocks once, by the names the libraries use.** `Value`, `Id`, `Entity`, `AggregateRoot`, `DomainEvent`, `DomainService`, `DomainException`, `UseCase`, `OutputPort`, `Repository`, `Store`, `PortException`, `InputPortException`, `UseCaseException`, `OutputPortException`, `Refusal`.
3. **Keep the domain free of bare primitives where they carry meaning.** A string with a format is a value, a moment is a value, a state with three or more values is an enum.
4. **Write the composition root by hand — Pure DI.** One module in `infrastructure/` constructs the outgoing adapters, passes them to the use cases' constructors, passes the use cases to the incoming adapters, and calls the entry point.
5. **Check the layers yourself.** Without `dca-archunit` / `DomainCentric.ArchRules`, a small script over the imports enforces the same direction (domain imports nothing of the application or adapters; the application nothing of adapters or infrastructure; an incoming adapter no infrastructure) and reports under the libraries' rule ids, so a finding reads the…
6. **Let the type checker carry the rest.** `mypy --strict` (or the language's strict mode) holds the ports' signatures, the frozen values and the typed ids; run it with the layer check in the same build step.
7. **Verify** — the layer check, the type checker and the tests in one command, red on the first finding.
