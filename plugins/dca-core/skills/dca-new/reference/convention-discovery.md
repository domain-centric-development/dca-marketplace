# Convention discovery

Part of the `dca-new` skill: what every code mode reads before it writes — the project's `DcaLayout`, the
conventions file and the rule selection, or a scan of the code where no architecture test exists.

```bash
# 1. The project's DcaLayout — the architecture test is the single source of the layout conventions
grep -rn "DcaLayout\." --include='*.java' --include='*.cs' . | grep -v '/build/\|/bin/\|/obj/'
```

If found: `Read` the test. The `DcaLayout` builder chain **is** the convention list — every `with…`/`With…`
call is a deviation from the DCA default:
- `forBasePackage("com.acme.shop")` / `ForRootNamespace("Acme.Shop")` → `{{basePackage}}` / `{{rootNamespace}}`
- `withIncomingSubpackage("in")`, `withOutgoingSubpackage("out")` / `WithIncomingSegment`, `WithOutgoingSegment`
  → adapter sub-folders
- `withUseCaseSuffix("ApplicationService")` / `WithUseCaseSuffix(...)` → `{{useCaseImplSuffix}}`
- `withRestControllerSuffix(...)` / `WithRestControllerSuffix(...)` → REST adapter suffix
- `withDomainSubpackage`, `withApplicationSubpackage`, `withAdapterSubpackage` (rare) → layer names

The marker types are the library's (`dev.domaincentric.dca.buildingblocks.…` / `DomainCentric.BuildingBlocks.…`).
The conventions file — the one the `AGENTS.md` line ``- conventions: `<path>` `` names, `.agents/dca/conventions.md`
by default, `.claude/dca/conventions.md` in older projects — may override any of it. Also read
`dca-archunit.properties` (test class path / next to the test assembly) — a rule set switched off there tells
you which patterns the project deliberately does not use (e.g. no `tactical` → do not lay out a rich aggregate
without asking).

If no architecture test exists: scan the project directly:
```bash
# Java — existing aggregate root style, use case style, adapter folders
grep -rln --include='*.java' -E 'extends BaseAggregateRoot|implements AggregateRoot' src/main/java
grep -rln --include='*.java' -E 'implements\s+\w+UseCase|class\s+\w+(UseCase|ApplicationService)' src/main/java
find . -type d \( -name incoming -o -name outgoing -o -name in -o -name out \) -path '*/adapter/*' -not -path '*/build/*'

# C# — same questions
grep -rln --include='*.cs' -E ': AggregateRootBase<|: IAggregateRoot<' src
grep -rln --include='*.cs' -E ': I\w+InputPort|class \w+(UseCase|ApplicationService)\b' src
find . -type d \( -name Incoming -o -name Outgoing -o -name In -o -name Out \) -path '*/Adapter/*' -not -path '*/bin/*' -not -path '*/obj/*'
```

Build a `conventions` summary and (if anything is ambiguous) confirm with the user before generating. Generate
code that matches what's already there. Don't impose DCA defaults if the project follows different (but
consistent) conventions.
