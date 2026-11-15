---
name: review-clean-code
description: The clean-code review perspective: naming, function size and single level of abstraction, SOLID violations, code smells (long method, feature envy, primitive obsession, data clumps, shotgun surgery, comment smell), DRY with judgement, boy-scout opportunities. Use when reviewing a change for readability and maintainability, or as the carrier of the `clean-code` perspective in a delivery pipeline's review stage.
---

# /review-clean-code

Clean-code reviewer (Martin, Hunt/Thomas, Fowler). Static review; report, never fix, reformat or run tests. Read
the conventions (explicit path, else the configuration file `AGENTS.md` names, `AGENTS.md`, `CLAUDE.md`) for the
formatter command.

## Checks

The `clean-code` skill's rules, judged on the diff, plus:

- **SOLID**: SRP (`OrderManager` validating, persisting, publishing); OCP (type switch edited per new type →
  Replace Conditional with Polymorphism); LSP (subclass throwing `UnsupportedOperationException`). ISP god port and
  DIP → `nit` only unless clean-code-specific (e.g. coupling to `System.out`); otherwise `review-hexagonal`.
- **Names**: intention-revealing, no disinformation (`accountList` typed `Map`), searchable, pronounceable, nouns
  for classes / verbs for methods, no pun (one word, two meanings), no encoding, one word per concept.
- **Functions**: ~20 lines is a smell threshold (linear 40 may stay; 15 with three nested ifs splits); one level of
  abstraction; 0–2 params fine, 3 borderline, 4+ → Introduce Parameter Object; no flag params; no hidden side
  effect (`validate` that saves); no output arguments; command–query separation.
- **Comments**: keep legal headers, why, warnings, public-API docs. Flag restated code, journal lines,
  commented-out code, closing-brace comments, misleading/stale ones. A comment the change made wrong or too narrow
  is the change's finding; so is one citing a source the reader cannot see instead of what holds in the file.
- **Smells**: name the smell and its refactoring — Long Method (Extract Method, Replace Temp with Query, Decompose
  Conditional), Long Parameter List (Introduce Parameter Object, Preserve Whole Object), Feature Envy (Move
  Method), Data Clumps (Extract Class), Primitive Obsession (Replace Primitive with Value Object), type Switch
  (Replace Conditional with Polymorphism), Parallel Inheritance (Move Method/Field), Lazy Class (Inline Class),
  Speculative Generality (Inline / Collapse Hierarchy), Temporary Field (Extract Class), Message Chains (Hide
  Delegate), Middle Man (Remove Middle Man), Inappropriate Intimacy (Move Method/Field, Change Bidirectional to
  Unidirectional), Shotgun Surgery (Move Method/Field together), Comment as Crutch (Extract Method), Dead Code
  (Delete), Duplicate Code (Extract Method after Rule of Three).
- **DRY**: flag duplication only with a stable shape over ≥3 occurrences AND an honest intent name for the
  extraction. Exceptions flagged from the second place: a decision made twice (same question answered in two
  places, two ways); a guard that hides a crash instead of fixing its cause; a value checked by one way of making
  the type while another skips it.
- **Boy scout**: small mechanical improvements adjacent to touched code only (misnamed local, dead branch, trivial
  duplication), as `nit`: "while you're in this file, consider...". No drive-by refactors elsewhere.

## Output format

```
# Clean Code Review

**Scope:** {N} files
**Smells found:** {summary: e.g. "3 Long Method, 1 Primitive Obsession"}

## Findings

### must-fix ({n})

- **path/File.java:LL** (or `.cs`) — <Smell name>: <one-line description>
  *Why:* <one sentence>
  *Fix:* <named refactoring + how>

### should-fix ({n})

(same shape)

### nits ({n})

(same shape)

## Strengths

- (Optional: clean names, well-sized functions, etc.)

## Closing

Run `./gradlew spotlessApply` / `dotnet format` (or project's formatter) before committing.
```

Nothing found in a section → say so plainly. The formatter line is the closing only, with the project's command.

## Severity

- **must-fix**: obscures intent — misleading name, lying comment, function doing three unrelated things.
- **should-fix**: future friction — primitive obsession, long parameter list, comment as crutch.
- **nit**: stylistic; boy-scout opportunities.

## Not this perspective

Formatting (formatter); aggregate design, language → `review-ddd`; port shape, adapter direction, framework leaks
→ `review-hexagonal`.
