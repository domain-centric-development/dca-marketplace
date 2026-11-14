# Return expected refusals as a sealed result — digest

Node: `/recipe/return-expected-refusals-as-a-sealed-result.md` — cite it by that path; read it in full only for a decision this digest leaves open.

A use case can be refused in ways its caller answers: the addressed thing is not there, it is not the caller's, the input is refused, a rule of the model refuses the change, a foreign system behind an output port refused or did not answer.

## Steps (first sentence each)

1. **Check the context's choice.** Every use case of a context returns its expected refusals as cases, or every one throws them.
2. **List the refusals.** For the operation, name every outcome a caller answers: those the use case finds itself (a port returned nothing, the caller does not own it, a precondition on a second aggregate) the concrete `DomainException`s the model can raise during the call, and the concrete `OutputPortException`s the ports it calls declare — a foreign system's…
3. **Write the sealed result** in the use-case package.
4. **Let the input port return it.** `{Operation}InputPort extends UseCase<{Operation}Command, {Operation}Result>` — the signature now says how the operation can end.
5. **Return the cases from the use case — decide, then write.** A refusal the use case finds is returned directly.
6. **Switch in every incoming adapter, without a `default`.** Each call site switches over the result and names every case; a `default` would let a new case compile into whatever it does.
7. **Keep the exception handler for the rest.** One handler per context stays for malformed input and the unexpected; a domain exception no use case names is unexpected and answered generically.
8. **Answer where nobody can.** A caller with no one to show a refusal to — an event consumer, an open host service whose own contract has no such case — turns the case back into an exception (`IllegalStateException` with the case's values) so the delivery's retry or the calling context sees it — a foreign system that did not answer is then tried again with th…
9. **Test the seam.** The port test asserts the returned case and its values.
10. **Verify** — compile (a missed case is a compile error in Java, a missing function in `Match`, a warning with a C# `union`), then the project's architecture suite.

## Templates

- `/template/domain-exception.md` Domain exception skeleton: Domain-free skeleton for the failures the inner layers raise, each with the base class its layer owns. — code: `/template/domain-exception/java.md`
