# ArchUnit Templates — JUnit5 + Java

Only `BaseArchUnitTest.java.tmpl` is shipped statically. The other 10 test classes are
translated from the Groovy templates at install time, using `PORTING_GUIDE.md`.

## Why this asymmetry?

Pre-porting all 11 tests would mean ~3000 lines of mechanical translation duplication.
Translating at install time:
- Saves the skill bundle from carrying outdated Java twins of the canonical Groovy rules
- Lets the skill adapt to project quirks (e.g. AssertJ vs Hamcrest preferences)
- Matches the SKILL.md design principle: skills are instructions + reference, not generators

## Workflow when user picks `junit5-java`

1. The skill writes `BaseArchUnitTest.java.tmpl` from this directory (substituting placeholders).
2. For each ArchUnit module the user selected, the skill reads the corresponding
   `*ArchUnitTest.groovy.tmpl` from `../groovy/` and translates it to Java using the rules in
   `PORTING_GUIDE.md`.
3. After writing, run `./gradlew compileTestArchitectureJava` to validate the port compiled.
4. If compile errors occur, the skill fixes them by re-reading the Groovy original and
   adjusting the translation — common issues: missing semicolons, unboxed primitives,
   non-final local variables captured in lambdas.

## Files in this directory

| File | Purpose |
|---|---|
| `BaseArchUnitTest.java.tmpl` | Canonical Java translation. Always installed when test style is `junit5-java`. |
| `PORTING_GUIDE.md` | Rules the skill follows when translating other Groovy tests. |
| `README.md` | This file. |

## Substitution placeholders

Same as Groovy variant — see `../groovy/README.md`. Note that Java import statements look
like `import {{aggregateRootMarkerFqn}};` — the placeholder must expand to a fully qualified
class name (e.g. `com.acme.shop.sharedkernel.marker.tactical.AggregateRoot`).
