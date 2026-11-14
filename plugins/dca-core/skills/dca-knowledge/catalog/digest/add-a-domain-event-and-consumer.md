# Add a domain event and consumer — digest

Node: `/recipe/add-a-domain-event-and-consumer.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Record that something meaningful happened in the domain, and let another part of the *same* context react to it.

## Steps (first sentence each)

1. **Define the event** as a record implementing `DomainEvent`, in the aggregate's `domain/` package.
2. **Register it on the aggregate** during the state change that causes it — never construct-and-forget.
3. **Publish after persistence** — the use case saves the aggregate, then publishes and clears the registered events (`publishAndClearEvents`, inside `@Transactional` or a `TransactionBoundary` block).
4. **Consume in-context** — decide the listener kind first ([Reacting to an event](/decision/reacting-to-an-event.md)).
5. **Keep the domain framework-free** — no Spring annotations on the event record itself.
6. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/domain-event.md` Domain event skeleton (record implementing DomainEvent): Domain-free skeleton for a domain event: an immutable fact about something that happened, internal to one bounded context. — code: `/template/domain-event/java.md`
- `/template/event-consumer.md` Event consumer skeleton (incoming adapter, transactional listener): Domain-free skeleton for an event consumer: an incoming adapter that reacts to an event by driving a use case. — code: `/template/event-consumer/java.md`
