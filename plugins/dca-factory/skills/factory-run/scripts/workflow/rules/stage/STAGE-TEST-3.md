---
id: STAGE-TEST-3
part: told
stages:
- test
section: Do
order: 8
---

# STAGE-TEST-3

3. **A unit test for every invariant the plan's `## Invariants` names** — each rule, the guards
   included: a required value refused when absent, a trimmed one refused untrimmed, a range at both
   bounds. The test drives the domain type alone, no framework, and is its own — never a criterion's
   test. `factory-cli.py --files-skeleton <story> test` writes tests.md's `## Invariants` table with one
   row per rule the plan names (element, number, the rule's text); fill in each row's last cell,
   `<Class>#<method>`. The test gate refuses a rule without its own test, a test that is not in the
   project, and a criterion's test in that table. Each rule's test must be shown to guard it: a test of a rule
   the code does not have yet is red before the build, and that is its proof; a test of a rule the code has
   already is green, so write its **break** — `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`, the
   smallest `git apply` change to the production code that turns exactly this test red (`git diff` of the
   change, then revert it). The gate runs every rule's test once, then each break on one scratch copy; a test
   that stays green under its break, or a green one without a break, is refused (`invariant-breaks`). These belong to the domain's own vocabulary and are the part of the suite
   that survives a rewrite of the adapters. A use case gets no unit test of its own from this stage: its
   port test runs it in the wired application, and a second test of the same path with doubles proves
   the doubles.
