---
id: STAGE-BUILD-4
part: told
why: refusals mixed throwing and returning in one context, or were caught by a base type that also swallowed port failures
stages:
- build
section: Do
order: 5
---

# STAGE-BUILD-4

4. Use the project's building blocks and conventions (markers, base types, layout, error handling); its architecture
   suite is binding.
   - Expected refusals take the `## Context` style — returned as a case of the use case's closed result (each case with
     the project's refusal marker) or thrown as the project's failure type — never both in one context.
   - **Decide, then write**: every refusal before the first write.
   - A failure an output port declares: its contract's type, thrown by the adapter, caught by its concrete type in the
     use case, never a base type; no incoming adapter catches a base type that would also catch it.
   - Which base types and marker: the project's carriers say.
