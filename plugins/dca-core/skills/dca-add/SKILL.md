---
name: dca-add
description: |
  Adds one capability to an existing Domain-Centric Architecture (DCA) project, at any time and as often as
  needed: `rules <set>` (one more rule set of the DCA catalog), `freeze` (accept today's violations as a
  baseline so only new ones fail), `formatter` (Spotless for Gradle or Maven, or `dotnet format`, with one
  formatting run over the whole code base) and `browser` (a browser runner and a smoke test, through
  `e2e-testing`), `integration-tests` (an integration source set or test project with its own command and
  one smoke test), `http-stub` (WireMock or WireMock.Net, for integration tests against an external
  system stubbed at the protocol), `coverage` (JaCoCo or coverlet, one report over every suite, no
  threshold) and `event-delivery` (an outbox for transactional listeners — Spring Modulith's event publication
  registry, an outbox table with a worker, or Wolverine — and one test shown to fail). Use when the user asks to "add the tactical rules", "freeze the existing
  violations", "set up a formatter", "add Playwright", "add browser tests", "add WireMock", "stub the
  payment provider in tests", "add an integration test level", "add test coverage", "add JaCoCo", "add an outbox", "make event reactions durable", or "/dca-add <capability>". Java (Gradle, Maven)
  and .NET. Changes only what the capability needs, never overwrites a file, and records the capability as one
  line of the technical description.
---

# dca-add

One capability per run, into a project that builds (usually set up by `dca-init`; `dca-new` calls this). The
list holds only capabilities with knowledge beyond the tool's docs or that a delivery pipeline needs; anything
else is ordinary work — do it, don't add it here.

| Capability | Does | Knowledge in |
|---|---|---|
| `rules <set>` | one more rule set in `dca-archunit.properties` | `dca-init`'s reference `module-selection-guide.md` |
| `freeze` | today's violations become the baseline; only new ones fail | `reference/freeze.md` |
| `formatter` | formatter in the build, one run over the whole code base, check and fix commands | `reference/formatter.md` |
| `browser` | browser runner, one smoke test on the start page | `e2e-testing`'s setup mode |
| `integration-tests` | integration source set or test project, its command, one smoke test shown to fail | `reference/integration-tests.md` |
| `http-stub` | HTTP stub on a free port for integration tests, one smoke test shown to fail | `reference/http-stub.md` |
| `coverage` | line + branch coverage over all suites together and per suite, one report, no threshold | `reference/coverage.md` |
| `event-delivery` | outbox under the transactional listeners, the rule's roles, one test shown to fail | `reference/event-delivery.md` |

Read a capability's reference when running it. Versions (plugins, packages): look up, latest stable, never from
memory.

## Before any capability

1. **The project.** Build system (`build.gradle(.kts)`, `pom.xml`, `*.sln` / `*.slnx` / `*.csproj`), the
   architecture test (`extends DcaArchitectureTest` / `: DcaArchitectureTest`) and its
   `dca-archunit.properties`, `dca.profile.yaml` at the root (named by the `AGENTS.md` line
   ``- configuration: `dca.profile.yaml` ``) — flat `key: value` lines where this skill records; missing →
   create with the first line. No build file → stop, point to `dca-new`.
2. **Already there?** Report what is there, stop.
3. **Never overwrite a file.** Edit in place (only the lines needed); impossible → user picks *overwrite /
   skip / abort* (default skip).

## `rules <set>`

1. Read `dca.rules.sets`. No key → whole catalog already runs; say so. Valid names (unknown fails the run):
   `cycles`, `layered`, `onion`, `hexagonal`, `naming`, `tactical`, `strategic`, `contextmap`, `advanced`,
   `usecase`, `errors`; .NET `dotnet` (always on).
2. Check the prerequisite in `module-selection-guide.md` ("Common reasons to leave a set out", "Order of
   strictness") — the one place for it. Typical: `tactical` needs classes implementing the markers;
   `strategic`/`contextmap` more than one declared context; `naming` the suffixes configured in `DcaLayout`.
3. Append the set; run `./gradlew test-architecture` / `mvn test -Dtest='ArchitectureTest'` /
   `dotnet test tests/<Solution>.ArchitectureTests` (Debug).
4. Violations are findings, not a failed step. User picks per rule: fix now, `dca.rules.warn` (or
   `dca.rules.warn.sets = <set>`), or `freeze`. Rejected rule → `dca.rules.off` + `dca.rule.<id>.reason` (stays
   in the report).

Spring Modulith verification is no rule set: `dca-init` decision E.

## `freeze`

Read `reference/freeze.md`: list failing rules, decide per rule with the user (freeze, ignore by pattern, `warn`,
fix), write `dca.rules.freeze` / `dca.rules.freeze.store` or `dca.rule.<id>.ignore[.n]`, re-run green. **Commit
the store.**

## `formatter`

Read `reference/formatter.md`: Spotless (Gradle, Maven) or `dotnet format`, **no ratchet**, one formatting run
over the whole code base as a commit of its own, `format:` / `formatFix:` in `dca.profile.yaml`.

## `browser`

Run `e2e-testing` in setup mode (its `reference/setup.md`: Playwright, app started in the test on a free port,
browser installed by the build, fake clock, permission stand-ins, static start page). Not installed → say so,
stop; never improvise. An existing suite gets no second one; if it needs an app started beforehand, setup mode
changes its base test to start the app on a free port.

Check afterwards:

- whole suite green with nothing started beforehand; smoke test green;
- smoke test fails with the start page's `<title>` emptied — try once, restore;
- `dca.profile.yaml`: `browser:` (runner), `selector:` (stable-selector attribute), `appStart: started by the
  suite on a free port`;
- the `dca-init` `AGENTS.md` section names `e2e-testing` for browser tests; if not, re-run `dca-init` (or add
  ``- browser tests: `e2e-testing` ``).

## `integration-tests`

Port tests (use case through its input port, wired app, real outgoing adapters, external systems stubbed at the
protocol) and adapter tests (incoming adapter against a stubbed input port). A pipeline puts every scenario but
the happy path here; without it the first story's plan stops.

1. **Already there?** `src/test-integration` or `*.IntegrationTests` → report, stop. A context test in the unit
   source set is not one; it stays.
2. **Own source set/project, own command**: `./gradlew test-integration`, `./mvnw test` over the added test
   source, `dotnet test tests/<Name>.IntegrationTests`.
3. **One smoke test** starting the wired app: green, break it as the reference says, red, restore, green.
4. **Record** in `dca.profile.yaml`: `integration:`, `integrationTest:`, `reset:`.

## `http-stub`

Stub external systems **at the protocol** (real HTTP server, free port) — never mock the port whose adapter is
under test, never a shared or real instance. WireMock (Java), WireMock.Net (.NET).

1. Dependency in the integration source set/project; none → `integration-tests` first.
2. Version looked up (Maven Central, NuGet), latest stable, no beta.
3. **One smoke test**: stub on a free port, one arranged answer, one call, assert. Green; change the arranged
   answer, red; restore, green.
4. Adapter base URL from configuration (`@DynamicPropertySource` / `WebApplicationFactory` configuration). No
   adapter written here.
5. **Record**: `http.stub: wiremock` / `wiremock-net` in `dca.profile.yaml`.

## `coverage`

JaCoCo (Gradle, Maven), coverlet + ReportGenerator (.NET).

1. **Already there?** JaCoCo plugin, or `coverlet` collector with a report step → report, stop.
2. **Every suite** (unit, integration, end-user — the browser suite runs in the test's process), together and per
   suite.
3. **No threshold**, never a failing check. An uncovered branch in an aggregate, entity or value object goes back
   as an invariant with a unit test. The report task joins neither `check` nor any test command a pipeline
   profile names (`test:`, `test.<name>:`, `e2eTest:`).
4. **Shown to work**: domain types in the report with covered lines; comment out one guard's unit test, branch
   missed; restore.
5. **Record**: `coverage:` (command), `coverageReport:` (path) in `dca.profile.yaml`.

## `event-delivery`

A reaction to an event (own domain event or another context's contract) drives a use case after commit, in its
own transaction, from a publication captured in the publishing transaction. The libraries ship no runtime.

1. **Already there?** Modulith events starter with publication registry, outbox table + worker, Wolverine durable
   local queues → report it and which parts it lacks (staleness monitor, bounded retry), stop.
2. **Form, the person's choice:** Spring Modulith where Spring is the framework (default); else outbox table +
   worker; .NET Wolverine or own outbox. In-memory outbox = sample stand-in; say so when there is no database.
3. **Two listener kinds.** Synchronous: in the publishing transaction, output ports only. Transactional: drives an
   input port, delivered from the outbox. Move listeners that drive an input port to transactional; translators
   stay synchronous. Ask before moving one a test expects inside the transaction.
4. **Rule roles** (`DCA-HEX-017`, experimental): Spring nothing; other Java framework
   `withTransactionalEventListener(...)`; .NET `EventListenerTypes` and `TransactionalEventListenerTypes`. Switch
   on by id or with the experimental rules.
5. **One integration test**, shown to fail: not called before commit, once after, never after rollback; make the
   listener synchronous → red; restore.
6. **Record**: `event.delivery: modulith` / `outbox` / `wolverine` in `dca.profile.yaml`.

## After each capability

**Technical description:** one line under `## Stack` — capability in the person's words, tool and version (e.g.
`Browser tests: Playwright 1.56`) — in the file `dca.profile.yaml` names as `tech:` (default `<root>/tech.md`,
`root:` default `product/`). Existing line → update, don't repeat. Description contradicts the capability ("no
end-user tests", another formatter) → ask which is right, change it through `/dca-describe`. No description →
write none; say `/dca-describe` writes it.

Report:

```
✓ Added {capability}
  - Changed: {files} (the technical description's `## Stack` line among them)
  - Run: {command}
  - Commit: {what, and — for formatter — the one formatting commit on its own}
```

With a delivery pipeline (`.agents/factory/`): hint that `factory.sh setup --check` proposes the profile lines
(`format:` / `formatFix:`, `browser:` / `e2eTest:`, `test.integration:`, `http.stub:`). This skill never writes
that profile and does not depend on the pipeline.

## Don't

- add a capability not on the list.
- use a formatter ratchet, or mix the formatting run with any other change.
- delete a failing rule to get green — `warn`, `freeze`, `ignore`, `off` keep it visible.
- freeze without committing the store.
- take a plugin or package version from memory.
