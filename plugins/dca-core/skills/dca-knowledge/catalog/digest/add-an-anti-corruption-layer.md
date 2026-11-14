# Add an anti-corruption layer — digest

Node: `/recipe/add-an-anti-corruption-layer.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Protect your domain from a foreign model — another bounded context or an external system.

## Steps (first sentence each)

1. **Consume through the provider's contract** — for a peer context, go through its Open Host Service (`@OpenHostService`), never its internals.
2. **Define an output port** in your `application/shared/` in *your* terms (a `DomainGateway`-style interface); your use cases depend on this, not on the foreign types.
3. **Implement the ACL in an outgoing adapter** in an `acl` package under `adapter/outgoing/` — it calls the foreign contract and maps the foreign model to your domain types (and your requests to theirs).
4. **For event-driven integration**, consume the other context's integration event in `adapter/incoming/messaging/`, translate it through the ACL, then invoke your own use case ([Publish a cross-context event](/recipe/publish-a-cross-context-event.md)).
5. **Declare the relationship** — a new external system gets its declaration on the context: `@ExternalUpstream` on `package-info.java` (C#: `[ExternalUpstream]` on the context's marker class) with the translation, the interaction and the protocol, and a row in the designed context map.
6. **Keep the boundary one-directional** — foreign types stay inside the ACL; nothing foreign appears in your domain or application layer.
7. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).
