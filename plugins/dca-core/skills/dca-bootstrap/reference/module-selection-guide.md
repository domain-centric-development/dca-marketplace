# Rule Set Selection Guide

Use this guide to recommend rule sets during the bootstrap workflow. A recommendation is a
`dca.rules.sets` line in `dca-archunit.properties` — the same key in Java (`dca-archunit`) and .NET
(`DomainCentric.ArchRules`). Omit the key to run the whole catalog. A single rule the team rejects
becomes `dca.rules.off` with a `dca.rule.<id>.reason`; one the team is working towards becomes
`dca.rules.warn`. Both stay in the report with their reason — prefer that over leaving a set out.

Sets: `cycles`, `layered`, `onion`, `hexagonal`, `naming`, `tactical`, `strategic`, `contextmap`,
`advanced`, `usecase`; on .NET additionally `dotnet` (always on — async ports, synchronous domain,
framework-free application layer).

## By project profile

| Profile | `dca.rules.sets` |
|---|---|
| **Greenfield DCA project** (designing for full DCA from day 1) | *(omit — whole catalog)* |
| **Brownfield retrofit** (introducing DCA into legacy code) | `cycles,hexagonal,naming,usecase` — add `tactical` once classes implement the markers; freeze (`dca.rules.freeze`, Java) or warn on the rest meanwhile |
| **CRUD app, layered but not DDD** | `cycles,layered,onion,hexagonal,naming` |
| **Spring Modulith project** | whole catalog + `SpringModulithVerificationTest` |
| **Microservice (single bounded context)** | `cycles,layered,onion,hexagonal,naming,usecase,tactical,advanced` — `strategic` and `contextmap` are no-ops with one context |
| **Modulith with several contexts** | whole catalog; `contextmap` keeps the `@Upstream` / `@Partnership` declarations honest |
| **Layer enforcement only, no DDD vocabulary** | `cycles,layered,onion,hexagonal,naming` |

## By subdomain type

Pattern choice per subdomain — record it in a pattern-selection ADR:

| Subdomain type | `dca.rules.sets` |
|---|---|
| **Core** (competitive differentiator — full tactical DDD) | *(omit — whole catalog)* |
| **Supporting** (transaction script / active record is fine) | `cycles,layered,onion,hexagonal,naming,usecase` — structural baseline, no `tactical` / `advanced` |
| **Generic** (adopted off the shelf, thin integration) | `cycles,hexagonal,naming` — boundary protection only |

One selection applies to the whole test class. A project with contexts of different types either
runs the strictest selection and records the exceptions per rule (`dca.rule.<id>.ignore` with a
package pattern), or runs one architecture test per group of contexts with its own properties file.

## By concern

| "I want to …" | Sets |
|---|---|
| keep my domain framework-free | `onion`, `layered` |
| make sure adapters and domain don't bleed | `hexagonal`, `layered` |
| naming consistency across the team | `naming` |
| use cases follow Command/Query/Result, results carry values not aggregates | `usecase` |
| enforce aggregate boundaries | `tactical` |
| bounded contexts don't leak into each other | `strategic`, `hexagonal` |
| declared context relationships match the code | `contextmap` |
| events follow conventions (records, timestamps, versioning) | `advanced` |

## Order of strictness

If you can only run one set to start: **`cycles`**. It is the cheapest and catches the worst
structural problems. Raise the bar in this order:

1. `cycles`
2. `hexagonal`
3. `layered`
4. `naming`
5. `usecase`
6. `onion`
7. `tactical`
8. `strategic`, `contextmap`
9. `advanced`

## Common reasons to leave a set out

- **`tactical`**: the classes do not implement the markers yet. Migrate or alias them first, or run
  the set at `warn` while migrating.
- **`strategic`, `contextmap`**: a single bounded context — the rules check nothing.
- **`naming`**: the team's suffixes differ. Configure them first (`withUseCaseSuffix`,
  `withControllerSuffix`, `withRestControllerSuffix`); leave the set out only for conventions the layout cannot express.
- **`SpringModulithVerificationTest`**: `spring-modulith-starter-test` is not on the class path — it
  does not compile.

## After install

Run once for the baseline: `./gradlew test-architecture`, `mvn test -Dtest='ArchitectureTest'` or
`dotnet test` (Debug). Expect failures in retrofit projects — those are findings, not bugs. Use
`/dca-review` to triage and `/dca-scaffold` for new code that complies from the start.
