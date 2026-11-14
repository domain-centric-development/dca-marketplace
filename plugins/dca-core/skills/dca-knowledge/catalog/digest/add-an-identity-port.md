# Add an identity port — digest

Node: `/recipe/add-an-identity-port.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Give the application a way to learn *who is calling* without letting authentication leak into use cases or the caller leak into the domain.

## Steps (first sentence each)

1. **Declare the port in `application/shared/`** — of the shared kernel when several contexts need it, of one context otherwise ([Elements — Shared Kernel](/guide/elements.md)).
2. **Implement it as an outgoing adapter of the authenticating context** — `adapter/outgoing/security/` reads the security context the framework populated and maps it to the port's `Identity`.
3. **Let the authentication filter enrich, never gate** — it attaches an identity or nothing and the request always proceeds; an anonymous visitor *is* an identity.
4. **Put the caller into the command** — a use case that acts on someone's resource takes the caller as a field (`GetCartByIdQuery(cartId, customerId)`, `StartCheckoutCommand(cartId, customerId)`).
5. **Ask the repository a scoped question** — `findByIdForCustomer(cartId, customerId)` instead of `findById` plus an `if`.
6. **Leave claims-only gates at the edge** — "does this token carry the staff role?" reads nothing but the caller, so the REST resource or page controller may check it and refuse ([Add an incoming REST adapter](/recipe/add-an-incoming-rest-adapter.md)).
7. **Keep the domain caller-free** — no `User` parameter on an aggregate method, no role check in a value object.
8. **Mark caller-less use cases** — an event consumer that reacts to the system's own event acts on nobody's behalf; it checks no caller, and saying so in a comment keeps the next reader from adding a guard that can never be satisfied.
9. **Render refusals in the adapter** — the use case answers "nothing here for you"; whether that becomes `403` or `404` is the resource's protocol decision (a `403` on a stranger's id confirms the id exists).
10. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project); the use case's port test passes a foreign `customerId` through the input port and expects an empty result — the identity port is the incoming adapter's concern, so the test needs no identity infrastructure ([Test a…

## Templates

- `/template/use-case.md` Use case skeleton (InputPort + UseCase + Command/Query + Result): Domain-free skeleton for one application-layer use case. — code: `/template/use-case/java.md`
