---
name: dca-add
description: |
  Adds one capability to an existing Domain-Centric Architecture (DCA) project, at any time and as often as
  needed: `rules <set>` (one more rule set of the DCA catalog), `freeze` (accept today's violations as a
  baseline so only new ones fail), `formatter` (Spotless for Gradle or Maven, or `dotnet format`, with one
  formatting run over the whole code base) and `browser` (a browser runner and a smoke test, through
  `e2e-testing`). Use when the user asks to "add the tactical rules", "freeze the existing violations", "set
  up a formatter", "add Playwright", "add browser tests", or "/dca-add <capability>". Java (Gradle, Maven)
  and .NET. Changes only what the capability needs and never overwrites a file.
---

# dca-add

One capability into a project that already builds — usually one `dca-init` has set up, and the one `dca-new`
calls it for. Each capability below is a procedure with its own knowledge; nothing else is done in the same
run.

**What belongs on this list:** a capability carries knowledge beyond the tool's own documentation, or a
delivery pipeline needs it. Everything else is ordinary work without a skill — do it, but do not add it here.
Today the list is four entries:

| Capability | Does | The knowledge lives in |
|---|---|---|
| `rules <set>` | one more rule set in `dca-archunit.properties` | `dca-init`'s reference `module-selection-guide.md` |
| `freeze` | today's violations become the baseline; only new ones fail | this skill |
| `formatter` | a formatter in the build, one run over the whole code base, the check and fix commands | this skill |
| `browser` | a browser runner and one smoke test on the start page | `e2e-testing`'s setup mode |

## Before any capability

1. **The project.** Build system (`build.gradle(.kts)`, `pom.xml`, `*.sln` / `*.slnx` / `*.csproj`), the
   architecture test (`extends DcaArchitectureTest` / `: DcaArchitectureTest`) and its
   `dca-archunit.properties`, and the conventions file the `AGENTS.md` line ``- conventions: `<path>` `` names
   (`.agents/dca/conventions.md` by default). A directory without a build file: stop and point to `dca-new`.
2. **Already there?** A capability that is present is not added twice: report what is there and stop.
3. **Never overwrite a file.** A target that exists is edited in place — the lines the capability needs,
   nothing else — or, where that is not possible, the user decides *overwrite / skip / abort* (default skip).

## `rules <set>`

One more set of the DCA rule catalog into an existing architecture test.

1. Read `dca.rules.sets` in `dca-archunit.properties`. Without the key the whole catalog already runs — there is
   nothing to add; say so. An unknown set name fails the run, so take the name from the catalog: `cycles`,
   `layered`, `onion`, `hexagonal`, `naming`, `tactical`, `strategic`, `contextmap`, `advanced`, `usecase`,
   `errors`, and on .NET `dotnet` (always on).
2. Check the set's prerequisite with the rule-set selection guide — `dca-init`'s reference
   `module-selection-guide.md` ("Common reasons to leave a set out", "Order of strictness"). It is the one place
   for that knowledge; this skill does not repeat it. Typical: `tactical` needs classes that implement the
   markers, `strategic` and `contextmap` need more than one declared context, `naming` needs the project's
   suffixes configured in `DcaLayout` first.
3. Append the set to the line and run the architecture test (`./gradlew test-architecture`,
   `mvn test -Dtest='ArchitectureTest'`, `dotnet test tests/<Solution>.ArchitectureTests` in Debug).
4. Violations are findings about the existing code, not a failed step. Offer the three staged forms and let the
   user pick per rule: fix now, `dca.rules.warn` (or `dca.rules.warn.sets = <set>` for the whole set, reported
   but not failing), or `freeze` below. A rule the team rejects is `dca.rules.off` with a
   `dca.rule.<id>.reason` — it stays in the report with the reason.

Spring Modulith's verification is not a rule set: it is a second test class and a dependency, `dca-init`'s
decision E.

## `freeze`

Accept the violations an existing code base has today, so that the rules fail only on what is broken from now
on. For projects that adopt DCA late; a new project has nothing to freeze.

1. Run the architecture test and list the failing rules with their violation count.
2. Per rule, with the user: freeze, ignore by pattern, lower to `warn`, or fix now. Record why in
   `dca.rule.<id>.reason` either way.
3. Write the choice into `dca-archunit.properties`:

   **Java — a baseline** (ArchUnit's freezing store):

   ```properties
   dca.rules.freeze        = DCA-ONI-002,DCA-HEX-003
   dca.rules.freeze.store  = arch/frozen
   ```

   The first run records the current violations in the store directory and passes; every later run fails only
   on a violation the store does not hold, and a fixed violation leaves the store. **Commit the store** with the
   change — without it the next checkout records a new baseline and hides everything. The same in code:
   `DcaRuleSelection.all().frozen(...).withFreezeStore(Path.of(...))` in `additionalSelection()`; the file form
   is preferred because the report shows it. Only rules that are a single ArchUnit rule can be frozen: the
   context-map set and the rules that iterate over bounded contexts fail with a message naming them — lower
   those to `warn` or ignore by pattern instead.

   **.NET — no baseline.** `DomainCentric.ArchRules` rejects `dca.rules.freeze` with a message saying so. The
   equivalent is an ignore pattern over what is already broken, one regular expression per key:

   ```properties
   dca.rule.DCA-ONI-002.ignore   = .*\.Legacy\..*
   dca.rule.DCA-ONI-002.ignore.1 = .*ReportExporter.*
   ```

   The value is **one** expression, commas included; a second one goes into `.ignore.1`, `.ignore.2`, …. The
   rule then reports only what the pattern does not cover. `ignore` works for every rule and means the same in
   both libraries — where a project keeps one configuration for both stacks, prefer it over `freeze` on the
   Java side too.
4. Run the architecture test again: green, with the frozen, ignored and lowered rules named in the report.

## `formatter`

A formatter in the build, **one formatting run over the whole code base when it is set up**, and the two
commands a person and a delivery pipeline use from then on. No ratchet to changed files: after the one run,
the formatter only touches what is unformatted — which is exactly what the last change wrote. That is what lets
a delivery stage, which may touch only its own files, run the fix command without changing anyone else's.

1. **Pick the formatter with the user.** An existing configuration (`.editorconfig`, an IDE formatter profile,
   a checkstyle file) decides the style where there is one; a style the caller hands over, agreed with the
   person (`dca-new` asks it before the skeleton exists), is that answer — do not ask again.
   - **Gradle — Spotless** (`com.diffplug.spotless`, the version from the Gradle Plugin Portal, looked up — never
     from memory): `spotless { java { <style>(); removeUnusedImports(); trimTrailingWhitespace(); endWithNewline() } }`
     with the style the user picks (`googleJavaFormat()`, `palantirJavaFormat()`, `eclipse()`). `spotlessCheck`
     joins `check` by itself. Do **not** set `ratchetFrom`.
   - **Maven — Spotless** (`com.diffplug.spotless:spotless-maven-plugin`, version looked up) with the same
     `<java>` steps; `check` bound to the `verify` phase where the user wants the build to fail on it.
   - **.NET — `dotnet format`**, part of the SDK; its rules come from `.editorconfig` (`dotnet new editorconfig`
     where there is none — then review its severities with the user, they decide what `--verify-no-changes`
     reports).
2. **Format everything once**, before any other change: `./gradlew spotlessApply`, `./mvnw spotless:apply`,
   `dotnet format`. Build and run every suite afterwards — a formatter must not change behaviour. The result is
   one commit of its own that holds nothing but formatting (the person commits it), so a later review or
   `git blame` can skip it. Where the repository has a `.git-blame-ignore-revs`, add the commit there.
3. **The two commands:**

   | Build | Check (`format:`) | Fix (`formatFix:`) |
   |---|---|---|
   | Gradle | `./gradlew spotlessCheck` | `./gradlew spotlessApply` |
   | Maven | `./mvnw spotless:check` | `./mvnw spotless:apply` |
   | .NET | `dotnet format --verify-no-changes` | `dotnet format` |

   Record both in the conventions file, as `format:` and `formatFix:` lines, where the general skills look for
   the formatter. A delivery pipeline's profile carries the same two keys: the gate and the commit hook run the
   check, the stages that write code run the fix before they finish.

## `browser`

A browser runner and one smoke test, set up before the first feature needs them. The knowledge is not here:
run `e2e-testing` in its setup mode — it holds the setup for Gradle, Maven and .NET in its
`reference/setup.md` (Playwright, the application started inside the test on a free port, the browser installed
by the build, a fake clock and permission stand-ins, a static start page instead of a controller). Where
`e2e-testing` is not installed, say so and stop; do not improvise a setup.

What this skill checks afterwards, because a runner that cannot fail is worse than none:

- the smoke test is green;
- it fails when the start page's `<title>` is emptied — try it once, then restore the title;
- the `AGENTS.md` section of `dca-init` names `e2e-testing` for browser tests; where it does not, run
  `dca-init` again to refresh the section (or add the line in its form: ``- browser tests: `e2e-testing` ``).

## After each capability

Report what was added, the commands to run it, and what the user commits:

```
✓ Added {capability}
  - Changed: {files}
  - Run: {command}
  - Commit: {what, and — for formatter — the one formatting commit on its own}
```

Where the project has a delivery pipeline (`.agents/factory/`), hint that `factory.sh setup --check` proposes
the profile lines the new capability needs (`format:` / `formatFix:`, `browser:` / `e2eTest:`). This skill does not write the
profile and does not depend on the pipeline.

## Anti-patterns

- **Don't** add a capability that is not on the list. Setting up a tool the documentation already explains is
  ordinary work.
- **Don't** set up a formatter with a ratchet, and don't mix the one formatting run with any other change.
- **Don't** delete a failing rule to get green. `warn`, `freeze`, `ignore` and `off` keep the decision visible.
- **Don't** freeze without committing the store.
- **Don't** take a plugin or package version from memory.
