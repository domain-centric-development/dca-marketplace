# Hand a use case a second operation — digest

Node: `/recipe/hand-a-use-case-a-second-operation.md` — cite it by that path; read it in full only for a decision this digest leaves open.

A use case needs what another use case already does — apply a list line by line through an existing operation, start a sub-run, settle a step.

## Steps (first sentence each)

1. **Decide how the two steps run together.** - Both must succeed or fail together, in one process and one transaction → steps 2–5.
2. **Declare the port in the first use case's words.** An interface extending `OutputPort` beside the first use case (or in `application/shared/` when several use it), named for what the first use case needs, not for the use case behind it: `PriceSetter.setPrice(product, amount)`, not `ChangePriceCaller`.
3. **Let the first use case decide.** It depends on the port only; the order of the steps, what a failure of one step means for the rest, and what it counts all stay in its `execute`.
4. **Implement the port in the composition root.** In `{context}/infrastructure/` — a `@Bean` in the context's `@Configuration` (Spring), a registration in `Add{Context}Context()` (.NET), a line in the hand-written root (no container).
5. **Check the transaction.** In-process, the second use case's boundary joins the first's (`@Transactional` `REQUIRED`; an ambient transaction in .NET).
6. **Verify** — the architecture suite.
