# Add a bounded context — digest

Node: `/recipe/add-a-bounded-context.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Carve out a new top-level context package with its own domain / application / adapter layers and a hard boundary to every other context.

## Steps (first sentence each)

1. **Create the package** `{boundedcontext}/` — at the top level or below a grouping package; contexts are discovered by the annotation at any depth — and declare it in `package-info.java` with `@BoundedContext(name = "...", description = "...")` ([package-info template](/template/bounded-context-package-info.md)).
2. **Lay out the layers** inside it: `domain/`, `application/` (with `shared/` for output ports), `adapter/incoming/`, `adapter/outgoing/`, and an optional per-context `infrastructure/`.
3. **Keep the domain framework-free** — no cross-context imports.
4. **Seed the first slice** — one aggregate ([Add an aggregate](/recipe/add-an-aggregate.md)), one use case ([Add a use case](/recipe/add-a-use-case.md)), one incoming adapter ([Add an incoming REST adapter](/recipe/add-an-incoming-rest-adapter.md)).
5. **Record the decision** — add the context to the context map with its subdomain type and relationships; capture the pattern-style choice in an ADR.
6. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project); the isolation rules below run per context.

## Templates

- `/template/bounded-context-package-info.md` Bounded context declaration (package-info.java): Domain-free skeleton for the one file that turns a package into a **bounded context**: `package-info.java` at the context root, annotated with `@BoundedContext`. — code: `/template/bounded-context-package-info/java.md`
