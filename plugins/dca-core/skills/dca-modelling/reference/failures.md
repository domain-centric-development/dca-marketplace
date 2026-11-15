# Failures — building the types

The invariants are `dca-discipline`'s (invariant 6); this is how the types are built.

- Building blocks, all abstract, no code, no status: `DomainException` (domain); under `PortException` —
  `UseCaseException` (under `InputPortException`; concrete ones never extend `InputPortException` directly) for a use
  case's refusal, `OutputPortException` for an output port's declared failure, thrown by its adapter, caught by
  concrete type in the use case.
- Own infrastructure failing (lost connection, timeout) → platform exception, no `OutputPortException`. A foreign
  system behind an output port (`@ExternalUpstream` on the context map) refusing / timing out / unreachable → port
  declares `{System}UnavailableException extends OutputPortException`, adapter catches the client failure and throws
  it, use case answers it as a refusal. Which systems are foreign: read the context map, never judge per failure.
- "Which one, if any" (active session, open draft) answers none with an empty value in a plain result; "not found"
  refuses only when the caller names a thing by id.
- Refusal style per context (read first; neither tech line nor use cases → ask). *Thrown:* the use case throws its
  `UseCaseException` subtypes, lets the model's pass. *Returned:* input port returns a sealed `{Operation}Result` —
  one success case named for what happened, one nested record per refusal named after it implementing `Refusal`
  (.NET `IRefusal`; closed union, OneOf until C# `union` ships), no `Exception` suffix; the model still throws, the
  use case catches each concrete domain/output-port exception once and returns its case. One outcome → plain result
  record. Several successes, no refusal (`Sent` | `AlreadySent`) → may seal, no case marked `Refusal` (a marked
  success would roll back). Styles equal; a context never mixes them.
- Whoever searches owns "not found": aggregate by id via repository → use case's refusal (`UseCaseException`
  subtype or `Refusal` case); part by local id inside the aggregate → `DomainException`, caught and answered by the
  use case.
- Decide, then write: load, ask the model and every refusing port, refuse or go on, save last. The boundary's
  rollback of a returned `Refusal` is the net, not the design.
- Name the rule, not the answer: `InsufficientStockException`, never `StockError`/`OrderHttpException`; no
  `Error`/`Fault`/`Failure` suffix, no `Http`/`Status`/`Response` in the name.
- Carry the compared facts as fields with accessors (`requested()`, `available()`). Message is for the log; the
  incoming adapter words the refusal from type and values so a page can translate it.
- Placement: domain failure beside the model raising it (no `domain/exception/`); use-case failure with its use case,
  or `application/shared` when several raise it; output-port failure beside its port; refusal case nested in its
  result, never its own file.
- Argument guard (null/range on a value only code passes) stays `IllegalArgumentException` / `ArgumentException`.
  Cut = origin and name: value built from input → its rule's failure; a domain expert's word → domain failure with
  that word.
- Never annotate a failure type or name a transport concept in it — the incoming adapter maps it, so one use case
  serves REST and a page with different answers.
