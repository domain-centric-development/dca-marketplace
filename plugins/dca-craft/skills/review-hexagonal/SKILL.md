---
name: review-hexagonal
description: The hexagonal review perspective, from outside any one method: do dependencies point inward, are ports declared inside and implemented in adapters, port granularity, framework leaks into inner layers, command/query/result shape of input ports, translation at the edge, each failure answered once per context, refusals thrown or returned uniformly per context. Use when reviewing a change from the ports-and-adapters point of view, or as the carrier of the `hexagonal` perspective in a delivery pipeline's review stage.
---

# /review-hexagonal

Hexagonal reviewer (Cockburn, Palermo, Hombergs). Static review; report, never fix or run.

## Read first

1. Conventions: an explicit path given, else the configuration file `AGENTS.md` names (``- configuration: `<file>` ``),
   `AGENTS.md`, `CLAUDE.md` — suffixes (`*UseCase` / `*ApplicationService`, `*Resource` / `*Controller`), adapter
   folders (`incoming` / `in`), port markers, each context's refusal style.
2. None → read the layout and dominant names from the code.

Judge against the project's convention, not yours; flag inconsistency within the project.

## Checks

**Dependency direction**
- `domain/`, `application/` import no `adapter/`, `infrastructure/`, framework type (`org.springframework.*`,
  `jakarta.persistence.*`, JDBC, HTTP, Kafka; `Microsoft.AspNetCore.*`, `Microsoft.EntityFrameworkCore.*`,
  `System.Data.*`, `HttpClient`) or port implementation. Use case injecting `JdbcTemplate` / `RestTemplate` →
  extract a port.

**Ports** — an output port is a capability the application needs and does not own (persistence, another context,
an external system, messaging, the caller's identity), declared in its language; responsibility and direction make
a port, not distance. Use cases call output ports; an incoming adapter may use the identity port.
- No application-side caller and not the identity port (cookie/token handling, logout, headers) → plain adapter type.
- Inbound question as an output port (a filter asks its own context "does this account exist?") → query use case or
  published API.
- Transaction / unit of work as a port → finding (execution semantics, not a capability).
- Domain-owned lookup interface without a recorded reason, where the use case could fetch and hand in an immutable
  snapshot → finding. The exception is narrow, read-only, in domain language; one that writes or is held as an
  aggregate field → finding. A pure strategy passed as a parameter is not a lookup.
- God port (≈15 methods) → split. Anemic port (`save(Object)`, `*DataAccessor`, `*PersistenceHandler`) → domain
  name. Leaky signature (`ResultSet`, `KafkaMessage`) → domain terms. Port declared by an adapter → application owns it.

**Adapter direction**
- Primary (controllers, CLI, jobs, consumers, tool providers) in `adapter/incoming/` call in; secondary
  (persistence, clients, publishers) in `adapter/outgoing/` are called.
- Controller calling a persistence repository directly; outgoing adapter changing application state directly;
  aggregate holding a repository/port field (pass as method parameter) → findings.

**Input-port shape** (use the project's names, e.g. `*InputPort`/`*UseCase`, `I*Handler`/`*Handler`)
- Interface the incoming adapter depends on; implementation separate in the application layer.
- Input: immutable command or query record. Output: result of values, never an aggregate/entity.
- One use case, one method: `executeA/B/C` → three use cases. Mutable `*Command`, aggregate as `*Result`,
  primitives instead of a command → findings.

**Framework leaks**
- `@Entity`/`@Table`/`@Column`, `@JsonProperty`/`@JsonIgnore` in domain; `@RestController`/`@RequestMapping` outside
  `adapter/incoming`; `@Repository`/`@Component`/`@Service` in `domain/`; `@Autowired` field injection anywhere.
- `@Transactional` on incoming adapters or in `domain/` (only use cases, or an outgoing persistence adapter).
  `@Service`/`@Transactional` on a use-case impl is fine; the input-port interface stays framework-free.
- A transactional use case calling a remote-capable port (another context, payment, mail) holds the connection:
  fetch remote first, draw the transaction programmatically around load/mutate/save/publish.
- C#: `[ApiController]`/`Controller` or EF Core in `Domain/`/`Application/`; `DbContext`, `System.Transactions` in
  `Application/` (reach the transaction through its own port); `async` on an aggregate; a remote port awaited
  inside the transaction.
- Incoming adapter injecting a domain service → the use case owns it and puts the outcome in the result.

**Mapping at the edge**
- Request DTO → command in the incoming adapter; domain → persistence/external DTO in the outgoing adapter. Inner
  layers import no `*Dto`, `*Request`, `*Response`, JPA `*Entity` (use case returning `OrderResponseDto` → finding).
- Open Host Service: contract is URL + payload; versioning visible (`v1/`, header, content type); responds with a
  published-language DTO, never internal types.

**Failure translation** — an expected refusal (not found, not the caller's, refused input, a model rule, a foreign
system that refused or did not answer) is either **thrown** as a named failure or **returned** as a case of a
closed result; the project chooses per context.
- One style per context; mixing → finding. Contexts may differ; the configuration says which.
- Own database/broker failing → platform exception, nobody answers it. Foreign system (listed as external in the
  context map — read it, do not judge per failure) refusing, timing out, unreachable → declared in the port's
  contract, translated by the outgoing adapter, answered by the use case as a refusal. Foreign timeout escaping as
  platform exception, or own DB failure dressed as refusal → finding.
- Empty answer is not a refusal; "not found" only when the caller names a specific thing.
- Thrown: one handler per context in its `adapter/incoming/` (`@RestControllerAdvice` scoped by `basePackages`, or
  `IExceptionHandler` scoped to its routes). A global handler naming a context's failure → finding.
- Returned: each call site switches naming every case, **no `default`** (C# library union: one function per case,
  in the type's order); each case answered once in one adapter class per context; the handler stays for malformed
  input and the unexpected. A dropped result (test helper included) swallows a refusal; a caller with nobody to
  answer (event consumer) throws on purpose for retry. Each refusal case carries the project's refusal marker so
  the transaction rolls back.
- Answer is a problem document (`ProblemDetail` / `ProblemDetails`), not a home-grown error DTO.
- Words are the adapter's: showing `getMessage()` / `.Message` → finding; word from the failure's type and values.
- Status follows the failure, not the base type (a line missing from an order is a model rule and still `404`).
- No `catch (Exception)`/`catch (RuntimeException)` around a use-case call, no `try`/`catch` the context handler
  already covers, no catch of the port-failure base types as such.
- No `@ResponseStatus` or framework metadata on an inner-layer failure.
- An incoming adapter translating nothing names its reason (e.g. an event consumer relying on delivery retry).

## Output format

```
# Hexagonal Review

**Scope:** {N} files; layers touched: [domain | application | adapter/incoming | adapter/outgoing]
**Conventions:** {file read | read from the code}

## Findings

### must-fix ({n})

- **path/File.java:LL** (or `.cs`) — <Rule short name>
  *Why:* <one sentence, cite Cockburn/Hombergs principle>
  *Fix:* <concrete one-line suggestion>

### should-fix ({n})

(same shape)

### nits ({n})

(same shape)

## Strengths

- (Optional: clean port shape, clean adapter direction, etc.)
```

Nothing found in a section → say so plainly.

## Severity

- **must-fix**: inner imports outer; framework leak into domain; god or leaky port breaking the inversion.
- **should-fix**: anemic port name, primary adapter bypassing the application, mutable command/result.
- **nit**: minor style or naming.

## Not this perspective

Aggregate invariants, language quality → `review-ddd`; function size, comments → `review-clean-code`. Noticed
anyway → `out-of-scope nit:`.
