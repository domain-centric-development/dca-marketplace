# Entering an operation

Read before entering an operation (`add`, step 5).

## Look up how the field names it — per bounded context

Where the session can search, before asking. Per context, never for the product as a whole — *cancel* an
authorization (payment) ≠ *cancel* an order (ordering).

1. **A published standard** for the context's subdomain, where one exists (healthcare, payments, logistics). Offer
   it first.
2. **The vocabulary of widely used systems** of that subdomain — their APIs and documentation.
3. **Operations they keep apart that look alike** — two verbs, different effects (holding an amount vs collecting
   it). Most useful finding: each is a question for the person.

- Offer findings per operation as options, each with its source; show disagreements between sources — a decision
  for the context. Nothing found enters unconfirmed.
- **Generic** context: usually adopts the established vocabulary (often conforms to a product it integrates).
  **Core** context: keeps its own language, uses the lookup for the distinctions, not the words.
- No search available → ask as below.

## Ask in Event-Storming grammar, without the workshop

1. **The event first** — what happened, past tense, domain words. The participle fixes the verb.
2. **The command** that caused it — the operation, with its code word.
3. **The aggregate** that accepts it and holds the rules — the term the operation is entered on. Ask: "What exists
   before this step and after it, and whose state changes?"
4. **The read model** a person looks at to decide — a term of its own, **and the verb for looking at it**. No event
   names a read, so ask directly ("What do you call looking at this?") and enter it with its code word
   (`anzeigen (list)` or `anzeigen (show)`, not both) — two writers translating a read alone pick different verbs.
5. **Policies** ("whenever this happens, do that") — an operation an event triggers.
6. **Hot spots** — what nobody can answer yet. Stays an open question; not entered.

Where the domain word could name more than one effect, ask which.
