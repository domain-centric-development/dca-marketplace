---
name: clean-code
description: |
  Applies Clean Code, Pragmatic Programmer, and Refactoring principles during
  code edits: meaningful names, small functions, no comment smell, SLAP (Single
  Level of Abstraction), DRY with judgment, Boy-Scout-Rule. Complements
  language-specific style guides; does not replace formatters.
disable-model-invocation: false
---

# /clean-code

Writing principles while editing, not a linter. Propose; the user decides.

## Names

- Domain words over technical ones: `placeOrder`, not `processData`; `Customer`, not `UserDto` in domain code.
- No encoding prefixes (`m_`, `str`, `I` unless the language's convention requires it).
- A name says what the thing holds: a `Map<UserId, User>` is not `userList`; a sentence shown on a page is not a
  `count`. One name never stands for two things in one type.
- One word per concept across the code base (`fetch` or `get`, not both).

## Functions

- One task, one level of abstraction (SLAP): orchestration lines and loop/mapping detail never share a body —
  extract the detail into a named function.
- ~20 lines is a smell threshold, not a limit: a linear 40-line function may stay; a 15-line one with three nested
  ifs splits.
- 0–2 parameters fine, 3 borderline, 4+ → parameter object (record / value object).
- No flag parameters: `processAsync(item)` / `processSync(item)`, not `process(item, true)`.
- The name states the full effect: `validate` does not save.

## Comments

- Default: none — make the code say it.
- Write one only for a why: a non-obvious constraint, a workaround with its reason, a public API boundary.
- Delete: restated code, journal lines, commented-out code, ownerless TODOs older than six months.
- A comment the change made wrong or too narrow is rewritten or deleted in the same change. It states what holds
  in this file, never what a source the reader cannot see says.

## Duplication and decisions

- Rule of Three: extract on the third occurrence, once the shape is stable. Name the extraction by intent
  (`validateOrderPlaceable`), never by shape (`commonChecks`).
- One decision in one place: a question the code answers (is it empty, may it be cancelled, which price applies)
  is answered once; every other place asks that answer. A view reads the model's decision, never makes it again.

## Subtract before you add

- Smallest change that solves the problem. A requirement the design did not foresee → reshape first, then add.
- A guard that only hides a crash is no fix: reproduce, fix the cause.
- A value that must never be illegal cannot be created illegal: every way the type is made checks it, not one
  factory beside an open constructor.

## Smells to flag while writing

Long method, long parameter list, feature envy, data clumps, primitive obsession, shotgun surgery, comment as
crutch, dead code, speculative generality, switch on type — name the smell and Fowler's refactoring for it.
Example: "Passing `(String customerId, String productId, int qty)` — introduce an `OrderLineDraft` record?"

## Boy-Scout Rule

Leave touched code a little cleaner — only adjacent to the change, only mechanical and obvious (rename a local,
extract a block, delete dead code). A risky cleanup goes into its own commit.

## Formatting

Never reformat invisibly mid-edit. Take the formatter command from the configuration file `AGENTS.md` names
(``- configuration: `<file>` ``) or from `AGENTS.md`; offer to run it at the end of a larger edit.

## Not in scope

Formatting (formatter), performance, architecture review (`review-ddd`, `review-hexagonal`), test design
(`testing`).
