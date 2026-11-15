# Event delivery, operation boundaries, ACL evidence, modelling edge cases

## Publish and clear in a use case

```java
@Transactional
public Result execute(Command cmd) {
    var aggregate = repository.findById(cmd.id()).orElseThrow();
    aggregate.doSomething(cmd.payload());
    repository.save(aggregate);
    eventPublisher.publishAndClearEvents(aggregate);
    return Result.of(aggregate);
}
```
```csharp
public Task<Result> ExecuteAsync(Command cmd, CancellationToken ct = default) =>
    _transaction.InTransactionAsync(async innerCt =>
    {
        var aggregate = await _repository.FindByIdAsync(new Id(cmd.Id), innerCt) ?? throw new ArgumentException(...);
        aggregate.DoSomething(cmd.Payload);
        await _repository.SaveAsync(aggregate, innerCt);
        await _events.PublishAndClearEventsAsync(aggregate, innerCt);
        return Result.From(aggregate);
    }, ct);
```

## Event delivery

- Async consumers acknowledge per consumer/effect. Bounded retry and intentional manual replay keep the snapshot and
  a stable event/consumer/effect key.
- Suppressing acceptance-before-ack duplicates needs provider-supported idempotency.
- Synchronous remote effects cannot roll back with local state.
- Event snapshot policy does not decide template or recipient policy.

## Operation boundaries (`DCA-USE-016`, `DCA-CYC-005`)

- Ordinary use cases invoke no other use case — not directly, not through an input port, not through an application
  helper. Shared collaborators that call no operation are fine.
- `DCA-USE-016` follows dependencies within the module's application layer, reports `Caller -> Target [via Helper]`.
- Explicit coordination: caller-side exception, e.g.
  `dca.rule.DCA-USE-016.ignore=^com\.example\.module\.application\.coordinate\.CoordinatorUseCase -> `.
  It lets the coordinator invoke operations, never an operation invoke the coordinator. `DCA-CYC-005` still detects
  coordination cycles, including two operations in one feature. No coordinator marker exists.
- No reliable exception expressible → WARN with a recorded reason; review the coordinator's transaction boundaries
  and partial-failure semantics by hand.
- Reflection, container lookups and calls through interfaces outside the InputPort hierarchy: manual review.

## Input-port surface (`DCA-USE-017`, `DCA-NET-003`)

- The input port describes the complete effective public instance surface: declared and inherited business methods,
  unrelated-interface methods, public properties/getters/setters all in the input-port contract.
- Exempt: constructors, Object members, compiler-generated members. A property accessor is not exempt for its
  special runtime name.
- Ordinary, inherited and explicit input-port implementations are valid.
- .NET: `DCA-NET-003` separately checks `IUseCase<TIn,TOut>.ExecuteAsync(input, CancellationToken)` returning
  `Task<T>` through the interface map; it does not count declared public methods.

## ACL evidence (`DCA-MAP-008`)

- Per declared ACL interaction, the matching adapter holds a class using that upstream's channel contract and the
  declaring context's own domain or application model.
- Two translators for different upstreams may share an adapter package; evidence for one upstream never satisfies
  another. The rule proves a structural translation site, not translation quality.

## Modelling edge cases

- Domain vocabulary may include `Manager`.
- Repository and Store ports may be local to one use case; reused ports go to `application/shared`.
- Store lookup by key is valid; aggregate save/delete semantics need a Repository.
- Response types may belong to incoming or outgoing adapters.
- Review entity constructor callers for the invariant boundary instead of demanding private constructors.
- Configured operation containers do not change the flat/grouped consistency requirement.
- Validate invariants again at aggregate entry points when default construction, deserialization or reconstitution
  can bypass a value constructor.
- Retrieve external facts in the use case, hand immutable snapshots to domain services; no lookup hidden in aggregate
  callbacks. TAC-002 checks fields only — callback review stays manual.
