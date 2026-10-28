# Event delivery: an outbox for transactional listeners

A reaction to an event — a domain event of the context or a contract from another — drives a use case after the
publishing transaction committed, in a transaction of its own, from a publication captured in that transaction. The
DCA libraries ship no runtime for it: the building blocks name the `DomainEventPublisher` port, the rules check the
listener's kind, and the outbox is the project's. This page sets one up.

Every form has the same parts, and the setup is done when each one is there:

| Part | What it means |
|---|---|
| capture | the publication is written in the transaction that saves the aggregate; a rollback removes it |
| status | per publication and per listener: published, processing, completed, failed |
| claim | a worker claims due publications atomically; a claim older than a threshold is stale and claimed again |
| wakeup and poll | the commit wakes the worker; a periodic poll finds what a lost wakeup left |
| bounded retry | backoff up to a limit; a terminal failure stays for inspection and a deliberate replay |
| at least once | the same publication can arrive twice; the use case is idempotent per event id and listener |

Two listener kinds sit on top of it. A **synchronous** listener runs inside the publishing transaction and calls
output ports only — the translator that captures an integration event, a metric. A **transactional** listener
drives an input port and is delivered from the outbox. Versions are looked up at setup time, never recalled.

## Java — Spring Modulith (the default where Spring is the framework)

The event publication registry is the outbox. Dependencies (Gradle; Maven alike):

```groovy
implementation platform('org.springframework.modulith:spring-modulith-bom:<version>')
implementation 'org.springframework.modulith:spring-modulith-starter-jdbc'   // or -starter-jpa
```

Configuration — the staleness monitor is off by default, and without it a publication left in processing by a
crash is never seen again:

```yaml
spring:
  modulith:
    events:
      jdbc:
        schema-initialization:
          enabled: true            # development; production creates EVENT_PUBLICATION by migration
      completion-mode: update
      republish-outstanding-events-on-restart: false   # recovery below, bounded
      staleness:
        published: PT1M
        processing: PT1M
        resubmission: PT1M
```

A transactional listener is `@ApplicationModuleListener` (`@Async` + `@Transactional(REQUIRES_NEW)` +
`@TransactionalEventListener`); a synchronous one is `@EventListener`. Recovery resubmits failed publications with
bounded attempts and backoff:

```java
@Component
class EventPublicationRecovery {
  private final IncompleteEventPublications publications;

  @Scheduled(fixedDelayString = "${events.retry.poll-delay:1000}")
  void resubmitDue() {
    var now = Instant.now();
    publications.resubmitIncompletePublications(
        ResubmissionOptions.defaults().withFilter(p ->
            p.getStatus() == EventPublication.Status.FAILED
                && p.getCompletionAttempts() < MAX_ATTEMPTS
                && dueAt(p).isBefore(now)));      // last resubmission + base delay · 2^(attempts-1)
  }
}
```

The registry records the event's class name and the listener's method: moving an event class or renaming a listener
method breaks pending publications. Deploy such a change on a drained registry.

## Java — without Spring Modulith: an outbox table and a worker

```sql
CREATE TABLE event_outbox (
  id            UUID PRIMARY KEY,         -- the event id
  event_type    VARCHAR(200) NOT NULL,    -- a logical name, not the class name
  listener      VARCHAR(200) NOT NULL,    -- one row per event and transactional listener
  payload       TEXT NOT NULL,
  status        VARCHAR(20) NOT NULL,     -- PUBLISHED, PROCESSING, COMPLETED, FAILED
  attempts      INT NOT NULL DEFAULT 0,
  due_at        TIMESTAMP NOT NULL,
  claimed_at    TIMESTAMP,
  last_error    TEXT
);
```

- The project's `DomainEventPublisher` implementation calls the synchronous listeners and inserts one row per
  transactional listener that listens to the event — inside the use case's transaction, so a rollback removes it —
  and registers an after-commit callback that wakes the worker.
- The worker (`@Scheduled` poll plus the wakeup) claims rows with `UPDATE … SET status='PROCESSING', claimed_at=now
  WHERE status IN ('PUBLISHED') OR (status='PROCESSING' AND claimed_at < :stale) … RETURNING` (or `SELECT … FOR UPDATE
  SKIP LOCKED`), calls the listener in a new transaction, and marks the row completed, due again with backoff, or
  failed after the limit.

## .NET — Wolverine

Wolverine's durable local queues with its EF Core (or Marten) outbox carry the parts above; a handler wrapped by its
transactional middleware is the transactional listener. Configuration: `opts.Policies.UseDurableLocalQueues()` and
`opts.Policies.AutoApplyTransactions()`; publish domain events through the outbox inside the use case's transaction
(`IMessageBus` behind the project's `IDomainEventPublisher`). Buffered queues lose messages on a stop — they are the
after-commit callback without a store, fit for a metric, not a reaction.

## .NET — an own outbox

Two listener interfaces and one publisher:

```csharp
public interface IEventListener { bool Listens(object @event); Task OnAsync(object @event, CancellationToken ct = default); }
public interface ITransactionalEventListener : IEventListener { }

public sealed class DomainEventPublisher : IDomainEventPublisher
{
    // Dispatches to the synchronous listeners now (they skip ITransactionalEventListener),
    // and when a transactional listener listens: _outbox.Register(@event) inside the transaction,
    // made eligible on commit, discarded on rollback, the dispatcher woken after commit.
}
```

The outbox table as for Java; a `BackgroundService` reads due publications and delivers each to the transactional
listeners in a DI scope of its own, with per-listener status, retry and a stale claim. An in-memory outbox has the
status machine but loses everything on a stop — a stand-in for a sample, not for production.

## The rule

`DCA-HEX-017` (experimental, from `dca-archunit` / `DomainCentric.ArchRules` 0.10.0) checks that a listener that
drives an input port is of the transactional kind. Switch it on with `dca.rules.experimental = true` or by id.

- Java: the Spring preset names `@TransactionalEventListener` in the `transactionalEventListener` role;
  `@ApplicationModuleListener` carries it. A listener that drives an input port also needs the transactional role on
  the method or its class. Another framework: `withTransactionalEventListener(...)`.
- .NET: name the project's listener types, empty in every preset:

```csharp
DcaLayout.ForRootNamespace("MyApp").WithFrameworkTypes(FrameworkTypes.AspNetCore() with
{
    EventListenerTypes = new[] { "MyApp.SharedKernel.Infrastructure.Events.IEventListener" },
    TransactionalEventListenerTypes = new[] { "MyApp.SharedKernel.Infrastructure.Events.ITransactionalEventListener" },
});
```

## The test, shown to fail

One integration test in the integration source set: a use case raises a domain event and commits; a transactional
listener records the event; assert that it is not called before the commit, is called once after it, and never after a
rollback. With a durable store, also: stop the worker before the commit, start it after, and the reaction still arrives.
Make the listener synchronous — `@EventListener`, or a plain `IEventListener` — and see the test red; restore it.
