# Expose an Open Host Service — digest

Node: `/recipe/expose-an-open-host-service.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Publish the public, stable capabilities of a bounded context so *other* contexts can call in — the provider side of the Open Host Service (OHS) pattern.

## Steps (first sentence each)

1. **Confirm a synchronous call is right.** Run [Cross-context communication](/decision/cross-context-communication.md).
2. **Place and annotate it.** An OHS is the *relationship* your context publishes, not a transport.
3. **Depend on input ports, delegate to use cases.** Like a REST resource, an OHS injects your **input port interfaces** and calls `execute(...)` — it must never touch a repository or output port directly, and holds no business logic of its own.
4. **Return DTOs in a published language — never domain objects.** Expose small records (e.g. a `ProductInfo` record) built from the use-case `Result`.
5. **Tell consumers how to consume it.** A consuming context must **not** call your OHS from its use cases.
6. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/open-host-service.md` Open Host Service skeleton (provider-side cross-context API): Domain-free skeleton for an **Open Host Service (OHS)**: the published, provider-side API a bounded context exposes so *other* contexts can consume its capabilities. — code: `/template/open-host-service/java.md`
