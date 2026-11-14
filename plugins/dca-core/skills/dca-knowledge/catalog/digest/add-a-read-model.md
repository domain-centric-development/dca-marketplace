# Add a read model — digest

Node: `/recipe/add-a-read-model.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Build a view for a query without going through the full aggregate write journey.

## Steps (first sentence each)

1. **Decide the read strategy first.** Run [read-model-vs-domain-query](/decision/read-model-vs-domain-query.md).
2. **Write the query use case.** An `application/{usecasename}/` folder with a `{Name}Query`, a `{Name}Result`, and a use case that loads via the aggregate's repository and maps to the result.
3. **Does the read need data from another context?** If the view must show aggregate state *together with* data owned elsewhere (current price from Pricing, stock from Inventory), or must apply a business rule that spans contexts, build an **enriched domain model** from the [enriched-domain-model template](/template/enriched-domain-model.md): a `record Enriche…
4. **Map to a ViewModel at the adapter edge.** For a server-rendered page, transform the `Result` (or the enriched model) into a `{Page}PageViewModel` of **primitives only** in `{context}/adapter/incoming/web/`, using the [ViewModel template](/template/view-model.md).
5. **Wire the controller thin.** The controller calls the input port, receives the `Result`, converts it to the ViewModel, and hands primitives to the template — no formatting or cross-context logic beyond primitive mapping.
6. **Verify** — run the project's architecture suite: `./gradlew test-architecture` on Gradle, the Maven architecture-test target, or `dotnet test -c Debug` against the architecture-test project on .NET (Debug, because the .NET rule engine cannot read Release async state machines).

## Templates

- `/template/enriched-domain-model.md` Enriched domain model skeleton (read model combining aggregate + cross-context data): Domain-free skeleton for an **enriched domain model**: an immutable read model that combines one aggregate's state with fresh data fetched from *other* bounded contexts, and owns the business rules that need data from more than one context. — code: `/template/enriched-domain-model/java.md`
- `/template/view-model.md` ViewModel skeleton (page-specific, primitive-only presentation record): Domain-free skeleton for a **ViewModel**: a page-specific record that transforms a domain read model (or a use-case `Result`) into **primitives only** for a server-rendered template. — code: `/template/view-model/java.md`
- `/template/rest-resource.md` REST resource skeleton (incoming adapter injecting input ports): Domain-free skeleton for a REST resource: a primary (incoming) adapter that exposes use cases over HTTP. — code: `/template/rest-resource/java.md`
