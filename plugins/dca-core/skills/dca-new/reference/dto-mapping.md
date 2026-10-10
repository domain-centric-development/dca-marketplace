# DTO mapping at the adapter boundary

Part of the `dca-new` skill (mode `usecase`): who maps what at the adapter boundary, inline or with a
converter, examples in and out, and the anti-patterns.

## Responsibility ownership

| Direction | Adapter type | Maps | Lives in |
|---|---|---|---|
| **In →** | `*Resource` (REST), `*Controller` (MVC), `*EventConsumer` | request DTO → `*Command`/`*Query` | `adapter/incoming/...` |
| **In ←** | same as above | `*Result` → response DTO (`*Response`, `*ViewModel`) | `adapter/incoming/...` |
| **Out →** | `*Repository` implementation, `*EventPublisher` implementation | Domain (`Order`, `OrderPlacedEvent`) → JPA entity / `*IntegrationEvent` / persistence record | `adapter/outgoing/...` |
| **Out ←** | same as above | JPA entity / row → Domain (`Order`) | `adapter/outgoing/...` |

## Decision: inline mapping or a dedicated `*Converter` class

```
If (command shape ≈ request DTO shape, ≤ 5 fields, no transformation):
    map inline in the controller
    → no mapper file, no indirection

If (shapes diverge, validation / lookup / default calculation needed):
    a dedicated *Converter in the same adapter folder
    → e.g. adapter/incoming/api/PlaceOrderRequestConverter.java

If (several resources map similar structures):
    a shared converter in adapter/incoming/api/mapper/
    → extract only when the third place needs it (rule of three)
```

## Example: REST inbound (inline)

```java
@RestController
@RequestMapping("/orders")
class OrderResource {

    private final PlaceOrderInputPort placeOrder;

    @PostMapping
    PlaceOrderResponse place(@RequestBody @Valid PlaceOrderRequest req) {
        var cmd = new PlaceOrderCommand(
            new CustomerId(req.customerId()),
            req.items().stream().map(i -> new LineItem(new ProductId(i.productId()), i.quantity())).toList(),
            new Address(req.shipping().street(), req.shipping().city())
        );
        var result = placeOrder.execute(cmd);
        return new PlaceOrderResponse(result.orderId().value(), result.placedAt(), result.totalAmount().amount());
    }
}

record PlaceOrderRequest(String customerId, List<LineItemDto> items, AddressDto shipping) {}
record PlaceOrderResponse(UUID orderId, Instant placedAt, BigDecimal totalAmount) {}
```

## Example: REST inbound with a dedicated converter

```java
@RestController
class OrderResource {
    private final PlaceOrderInputPort placeOrder;
    private final PlaceOrderRequestConverter converter;

    @PostMapping("/orders")
    PlaceOrderResponse place(@RequestBody @Valid PlaceOrderRequest req) {
        var result = placeOrder.execute(converter.toCommand(req));
        return converter.toResponse(result);
    }
}

// adapter/incoming/api/PlaceOrderRequestConverter.java
@Component
class PlaceOrderRequestConverter {
    PlaceOrderCommand toCommand(PlaceOrderRequest req) { ... }
    PlaceOrderResponse toResponse(PlaceOrderResult result) { ... }
}
```

## Example: outbound (repository implementation)

```java
// adapter/outgoing/persistence/JpaOrderRepository.java
@Component
class JpaOrderRepository implements OrderRepository {

    private final JpaOrderEntityRepository jpa;

    @Override
    public Optional<Order> findById(OrderId id) {
        return jpa.findById(id.value()).map(this::toDomain);
    }

    @Override
    public void save(Order order) {
        jpa.save(toEntity(order));
    }

    private Order toDomain(OrderEntity entity) { ... }
    private OrderEntity toEntity(Order order) { ... }
}

@Entity @Table(name = "orders")
class OrderEntity { /* JPA fields, accessors, @Id, @Column ... */ }
```

## Anti-patterns

- **The aggregate as the REST response** — leaks the domain's shape to clients (`Order` as the JSON answer). Always map to a `*Response` record in the adapter.
- **`*Command`/`*Query`/`*Result` as a JPA `@Entity`** — breaks the framework-free domain and application and mixes two lifecycles (use-case input and persistence row).
- **Mapping logic in the use case** — when `PlaceOrderUseCase` constructs a `PlaceOrderRequest` or builds a `*Response`, the boundary has moved. Mappers belong in `adapter/`.
- **One `*Dto` shared by request *and* persistence** — the same record serves two roles; every change on one side forces the other. Prefer two separate records with explicit mapping.
- **A mapper in `application/` or `domain/`** — mapping is an adapter concern.
- **A domain event as the Kafka payload** — domain events stay inside the context. Across contexts it is an `*IntegrationEvent` (schema version in `IntegrationEventType`; a business `version` stays allowed), mapped in the `adapter/outgoing/event/` publisher.

The complete wiring picture is `dca-audit`'s reference `use-case-pattern.md` (section 4, "Adapter wiring: who calls
what?"), the adapter naming table its `naming-conventions.md` (section "Adapter layer").
