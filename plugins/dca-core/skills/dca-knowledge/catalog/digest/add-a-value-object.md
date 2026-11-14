# Add a value object — digest

Node: `/recipe/add-a-value-object.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Add an immutable value object — a concept defined by its attributes, with no identity (`Money`, `EmailAddress`, a quantity).

## Steps (first sentence each)

1. **Model it as a record** implementing `Value`, in the domain model package `domain/model/`, beside the aggregate that owns it (or the shared kernel if it is genuinely universal — [Shared kernel](/guide/spring-modulith/shared-kernel-in-spring-modulith.md)).
2. **Validate in the compact constructor** — reject invalid state at construction so an instance is always valid; throw on bad input rather than storing it.
3. **Keep it immutable** — records give you final fields and value equality for free; a class must be final, hold only final fields, and implement `equals`/`hashCode` itself.
4. **Name from the ubiquitous language** — no technical suffixes (`Helper`, `Util`, `Utils`, `Impl`, `Implementation`) and no primitive obsession (wrap the primitive, don't pass a bare `String`).
5. **Never embed an aggregate root or entity** inside a value object; hold their `Id` if a reference is needed.
6. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/value-object.md` Value object skeleton (Java record implementing Value): Domain-free skeleton for a value object: an immutable, attribute-equal concept with no identity. — code: `/template/value-object/java.md`
