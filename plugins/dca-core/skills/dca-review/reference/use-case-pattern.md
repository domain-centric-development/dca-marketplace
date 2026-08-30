# Use Case Pattern Reference

Zentrale Referenz für die DCA-Use-Case-Struktur. Lies dies, bevor du eine neue Use Case
schreibst, reviewst oder umstrukturierst. Ergänzt [checklist.md](checklist.md) (für Audit)
und [naming-conventions.md](naming-conventions.md) (für Namens-Tabellen).

---

## 1. Vollständige Folder-Struktur einer Use Case

```
{basePackage}/{boundedcontext}/application/{usecasename}/
├── {Name}InputPort.java       # Interface: extends UseCase<{Input}, {Output}>
├── {Name}{ImplSuffix}.java    # Impl:      @Service [@Transactional], implements *InputPort
├── {Name}Command.java         # Input (writes)  -- Java record
│   ODER
│   {Name}Query.java           # Input (reads)   -- Java record
└── {Name}Result.java          # Output          -- Java record
```

**Beispiel** (`placeOrder` im `orders`-Kontext, Default-Konvention):

```
com.example.shop/orders/application/placeorder/
├── PlaceOrderInputPort.java   # extends UseCase<PlaceOrderCommand, PlaceOrderResult>
├── PlaceOrderUseCase.java     # @Service @Transactional implements PlaceOrderInputPort
├── PlaceOrderCommand.java     # record(CustomerId customerId, List<LineItem> items)
└── PlaceOrderResult.java      # record(OrderId orderId, Instant placedAt)
```

### Folder-Name (lowercase, kein Separator)

Der Folder-Name ist **immer lowercase ohne Separator**: `placeorder`, `getorderbyid`,
`cancelorder`. Nicht `placeOrder`, nicht `place-order`, nicht `PlaceOrder`.

**Warum:** Java-Package-Names sind per Konvention lowercase und dürfen kein `-` enthalten.
Use-Case-Folder *sind* Java-Packages, also gelten Package-Regeln. `place-order` würde
einen Compile-Fehler erzeugen, `placeOrder` ist gültig aber bricht mit der lowercase-Konvention.

**Lesbarkeitsverlust akzeptiert:** `getorderbyid` liest sich schlechter als `get-order-by-id`,
aber Konsistenz mit der Package-Konvention wiegt schwerer. Die Klassen *innen* (PascalCase)
sind ohnehin der primäre Anker für die Lesbarkeit.

---

## 2. Datei-Rollen im Detail

### `{Name}InputPort.java` — das Interface

```java
public interface PlaceOrderInputPort extends UseCase<PlaceOrderCommand, PlaceOrderResult> {
    // keine zusätzlichen Methoden -- execute(Input) kommt aus UseCase
}
```

- **Single-Method-Interface.** `UseCase<I, O>` definiert genau `O execute(I input)`. Keine
  weiteren Methoden hinzufügen — wenn eine zweite Operation nötig ist, ist es eine zweite
  Use Case.
- **Owned by application layer.** Das Interface lebt in `application/{usecasename}/`,
  nicht in `domain/`. Adapter (Controller, Event-Consumer) hängen gegen dieses Interface.
- **Alternative Suffixe.** Manche Projekte nutzen `*UseCase` als Interface-Name (Hombergs-Stil)
  und `*ApplicationService` für die Impl. Beides ist DCA-konform — wähle pro Projekt **ein**
  Schema und halte es durch.

### `{Name}{ImplSuffix}.java` — die Implementierung

```java
@Service
@Transactional
public class PlaceOrderUseCase implements PlaceOrderInputPort {

    private final OrderRepository orderRepository;
    private final CustomerDataPort customerData;
    private final DomainEventPublisher events;

    // Konstruktor-Injection
    public PlaceOrderUseCase(OrderRepository r, CustomerDataPort c, DomainEventPublisher e) { ... }

    @Override
    public PlaceOrderResult execute(PlaceOrderCommand cmd) {
        // 1. Lade Aggregate / Daten via Output-Ports
        // 2. Rufe Domain-Methoden auf (Aggregat-Verhalten, keine Felder direkt schreiben)
        // 3. Persistiere via Repository
        // 4. Publiziere Domain-Events
        // 5. Mappe auf Result
    }
}
```

- **`@Service`** auf der Impl, niemals auf dem Interface, niemals in `domain/`.
- **`@Transactional`** nur für **Commands** (Writes). Queries sind read-only — `@Transactional(readOnly = true)`
  ist optional, aber sinnvoll wenn das Projekt es konsistent nutzt.
- **Kein Remote-Port in der Transaktion.** Ruft der Use Case einen Output-Port, der den Prozess verlassen kann
  (API eines anderen Kontexts, Payment-Provider, Mail-Gateway), dann kein Klassen-`@Transactional`: Remote-Read
  zuerst, danach `transactionBoundary.inTransaction(() -> { load; mutate; save; publish; })` (`TransactionBoundary` aus den Building
  Blocks — Ausführungsabstraktion der Application-Schicht, kein Port). Sonst hält die Transaktion die DB-Connection für den Remote-Roundtrip (`DCA-USE-013`).
- **Konstruktor-Injection.** Kein `@Autowired` auf Feldern. Records oder
  `@RequiredArgsConstructor` (Lombok) sind erlaubt.
- **Nur via Output-Ports.** Niemals direkter Zugriff auf `EntityManager`, `JdbcTemplate`,
  `KafkaTemplate` etc. — alles geht über Ports.

### `{Name}Command.java` / `{Name}Query.java` — der Input

```java
public record PlaceOrderCommand(
    CustomerId customerId,
    List<LineItem> items,
    Address shippingAddress
) {
    public PlaceOrderCommand {
        Objects.requireNonNull(customerId, "customerId required");
        if (items == null || items.isEmpty()) throw new IllegalArgumentException("items must not be empty");
        items = List.copyOf(items); // defensive copy für Immutability
    }
}
```

- **`record`**, nicht `class`. Records garantieren Immutability + `equals`/`hashCode`.
- **Validierung im compact constructor.** Null-Checks, Pflichtfeld-Prüfung,
  defensive Copies bei Collections.
- **Domain-Typen statt Primitives.** `CustomerId` statt `String`, `Money` statt `BigDecimal`.
- **Command vs Query** ist eine harte Regel, nicht stylistisch:
  - **Command:** ändert Zustand. Wird in einer Transaktion ausgeführt. Endet meist mit
    Domain-Event-Publikation.
  - **Query:** liest nur. Keine Mutationen, keine Events.
  - Wenn eine Use Case sowohl liest *als auch* schreibt → es ist ein Command.
  - Diese Trennung erlaubt später CQRS-Aufspaltung (z.B. Read-Models auf Replicas) ohne
    Refactoring der Aufrufer.

### `{Name}Result.java` — der Output

```java
public record PlaceOrderResult(
    OrderId orderId,
    Instant placedAt,
    Money totalAmount
) {}
```

- **`record`**.
- **Lebt im selben Package** wie die Use Case — nicht in einem geteilten `dto/`-Ordner.
- **Exponiert keine Aggregate.** Niemals `Order order` als Result-Feld — stattdessen
  IDs, Value Objects, Primitives.
- **Anti-Pattern:** Result hat **dieselben Felder wie das Aggregat** → fragwürdig.
  Entweder die Use Case macht keine sinnvolle Transformation (dann brauchst du sie
  vielleicht nicht), oder der Adapter sollte direkt das Aggregat-Snapshot abrufen.
- Bei Void-Use-Cases (z.B. `cancelOrder` ohne Rückgabe): trotzdem ein `Result`-Record
  zurückgeben, ggf. mit nur einem Bestätigungs-Feld (`record CancelOrderResult(Instant cancelledAt) {}`).
  Vermeidet API-Brüche, wenn später Felder dazukommen.

---

## 3. Decision-Guide: Lokaler vs Shared Output Port

Output-Ports leben entweder **im Use-Case-Folder** (lokal) oder in
**`application/shared/`** (geteilt). Diese Entscheidung wird oft falsch getroffen.

### Default: Shared (`application/shared/`)

**Aggregat-Repositories und Cross-Use-Case-Ports gehören in `application/shared/`:**

- `OrderRepository` — wird von `placeOrder`, `cancelOrder`, `getOrderById`, ... genutzt
- `CustomerDataPort` — Cross-Context-Read, genutzt von mehreren Use Cases
- `OrderEventPublisher` — Event-Output, oft von mehreren Use Cases genutzt
- `IdentityProvider`, `Clock`, `RandomGenerator` — generische Infrastruktur-Ports

```
application/
├── shared/
│   ├── OrderRepository.java       # extends Repository<Order, OrderId>
│   ├── CustomerDataPort.java      # extends OutputPort
│   └── OrderEventPublisher.java   # extends OutputPort
├── placeorder/
│   └── ...
└── cancelorder/
    └── ...
```

### Ausnahme: Lokaler Port im Use-Case-Folder

**Nur in eng begrenzten Fällen:**

| Fall | Beispiel | Warum lokal |
|---|---|---|
| Use-case-spezifischer Fremdsystem-Call | `placeorder/PaymentGatewayPort.java` | Nur `placeOrder` braucht Payment-Auth-Calls; kein anderer Use Case |
| Spezialisierte Read-Projection | `getorderdashboard/OrderDashboardProjectionPort.java` | Spezifische Query-Optimierung, nicht wiederverwendbar |
| Use-case-lokaler Validator/External Check | `registeruser/EmailDeliverabilityPort.java` | Nur Registrierung prüft Mailbox-Erreichbarkeit |

```
application/
├── shared/
│   └── UserRepository.java
└── registeruser/
    ├── RegisterUserInputPort.java
    ├── RegisterUserUseCase.java
    ├── RegisterUserCommand.java
    ├── RegisterUserResult.java
    └── EmailDeliverabilityPort.java   # lokal -- nur hier genutzt
```

### Entscheidungsregel

> **Wenn ein zweiter Aufrufer plausibel ist → shared. Sonst lokal.**

Falsche Entscheidung in beide Richtungen hat Kosten:

- **Fälschlich shared:** `application/shared/` schwillt an mit unbenutzten Ports → schwerer
  zu navigieren, unklare Ownership.
- **Fälschlich lokal:** Zweiter Use Case duplicates den Port (oder importiert quer aus
  einem fremden Use-Case-Folder, was ArchUnit-Regeln verletzt). Refactoring nötig sobald
  geteilt wird.

**Tie-Breaker:** Im Zweifel `shared/` wählen. Eine Verschiebung von shared → lokal ist
billiger (nur die eine Use Case ist betroffen) als der umgekehrte Weg (mehrere Aufrufer
müssen umgehängt werden).

### Anti-Pattern: Per-Use-Case-Repository

Wenn jede Use Case ein eigenes `*Repository` mit nur den Methoden hat, die *sie* braucht
(`PlaceOrderOrderRepository` mit nur `save`, `GetOrderByIdOrderRepository` mit nur `findById`),
ist das ein Smell. **Aggregat-Repositories sind pro Aggregat**, nicht pro Use Case. Konsolidiere
zu einem `OrderRepository` in `application/shared/`.

---

## 4. Adapter-Wiring: Wer ruft was?

```
┌─────────────────────┐                  ┌──────────────────────┐
│ Incoming Adapter    │                  │ Outgoing Adapter     │
│ (Controller,        │                  │ (Repository-Impl,    │
│  EventConsumer)     │                  │  EventPublisher-Impl)│
└──────────┬──────────┘                  └──────────▲───────────┘
           │ ruft Interface                         │ implementiert Interface
           ▼                                        │
┌─────────────────────┐                  ┌──────────┴───────────┐
│ *InputPort          │ ─── benutzt ──▶  │ OutputPort           │
│ (in application/    │                  │ (in application/     │
│  usecasename/)      │                  │  shared/ oder lokal) │
└──────────┬──────────┘                  └──────────────────────┘
           │ implementiert
           ▼
┌─────────────────────┐
│ *UseCase (Impl)     │
│ ruft OutputPorts    │
└─────────────────────┘
```

**Konkret:**

- Controller injiziert **das Interface** (`PlaceOrderInputPort`), nicht die Impl.
- Repository-Impl implementiert **das Interface** aus `application/shared/`, niemals
  ein anderes.
- Use-Case-Impl hängt **nur gegen Interfaces** (Input + Output Ports), niemals gegen
  konkrete Adapter-Klassen.

Siehe auch [DTO Mapping Strategy](../../../dca-scaffold/SKILL.md#dto-mapping-at-the-adapter-boundary)
für Details, wie Request/Response am Adapter-Rand gemappt werden.

---

## 5. ArchUnit-Validierung

Die folgenden Regeln validieren das Use-Case-Pattern statisch (installierbar via `/dca-bootstrap`):

| Regel | Was sie prüft |
|---|---|
| `useCasesShouldEndWithUseCaseOrInputPort` | Klassen in `application/{x}/` heißen `*InputPort` oder `*UseCase` (bzw. Projekt-Suffix) |
| `useCaseImplsShouldImplementInputPort` | `*UseCase`-Klassen implementieren ein `*InputPort` |
| `inputPortsShouldExtendUseCaseMarker` | Alle `*InputPort`-Interfaces extenden `UseCase<I, O>` |
| `commandsAndQueriesShouldBeRecords` | `*Command` und `*Query` sind `record` oder `final` |
| `resultsShouldBeRecords` | `*Result` ist `record` |
| `noSpringAnnotationsOnCommandsQueriesResults` | Kein `@Component`/`@Service`/... auf Input/Output-Records |
| `useCasesShouldNotDependOnAdapters` | `application/` darf nicht aus `adapter/` importieren |
| `useCasesShouldNotDependOnInfrastructureFrameworks` | Keine `javax.persistence`-/`org.springframework.jdbc`-Imports in `application/` |
| `outputPortsShouldBeInterfaces` | Klassen in `application/shared/` sind Interfaces, keine Klassen |
| `outputPortsShouldExtendOutputPortMarker` | Output-Port-Interfaces extenden `Repository`, `Store`, `OutputPort`, ... |

Siehe `dca-bootstrap/reference/archunit-rule-catalog.md` für die vollständige Liste und
Implementierung der Tests.

---

## 6. Häufige Fehler und ihre Korrektur

| Fehler | Symptom | Korrektur |
|---|---|---|
| Use Case als `@Component` statt `@Service` | Klassifikation unklar | `@Service` benutzen — Spring-Konvention für Use Cases |
| Command mutiert Daten | Setter, nicht-finale Felder, normale Klasse | In `record` umwandeln, defensive Copies in compact constructor |
| Result enthält Aggregat | `record PlaceOrderResult(Order order)` | Auf IDs/Primitives reduzieren: `record PlaceOrderResult(OrderId orderId, Money total)` |
| Use Case hat 2 öffentliche Methoden | `placeOrder()` + `placeOrderUrgent()` | Aufsplitten in zwei Use Cases oder per Command-Feld parametrisieren |
| Folder ist `place-order` oder `placeOrder` | Compile-Fehler oder Konvention-Drift | Auf `placeorder` umbenennen |
| Output-Port im Domain-Layer | `domain/port/OrderRepository.java` | Nach `application/shared/` verschieben (Ports gehören zur Application-Layer) |
| `*UseCase` ohne `*InputPort`-Interface | Adapter hängt direkt gegen Impl | `*InputPort`-Interface einführen, Adapter umhängen |
| Mehr als 5 Output-Ports injiziert | "God Use Case" | Use Case aufsplitten (verschiedene Bounded-Use-Case-Schnitte) oder Domain Service einführen |
| Per-Use-Case-Repository | `PlaceOrderOrderRepository` mit nur `save` | Konsolidieren zu `OrderRepository` in `application/shared/` |

---

## 7. Verwandte Referenzen

- [checklist.md](checklist.md) — Per-Layer-Audit-Checks (Application — Use Cases, Application — Output Ports)
- [naming-conventions.md](naming-conventions.md) — Vollständige Namens-Tabellen
- [archunit-rule-catalog.md](../../dca-bootstrap/reference/archunit-rule-catalog.md) — Statische Regeln, die das Pattern erzwingen
- [DTO Mapping Strategy](../../dca-scaffold/SKILL.md#dto-mapping-at-the-adapter-boundary) — Wie Adapter zu Commands/Results mappen
- [Module Selection Guide](../../dca-bootstrap/reference/module-selection-guide.md) — Welche ArchUnit-Module Use-Case-Pattern erzwingen
