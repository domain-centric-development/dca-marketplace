---
id: STAGE-TEST-3
part: told
why: a domain type's rules had no test of their own, so a guard could go missing unnoticed
stages:
- test
section: Do
order: 8
---

# STAGE-TEST-3

3. **A unit test for every rule under the plan's `## Invariants`**, guards included (a required value refused absent,
   a trimmed one refused untrimmed, a range at both bounds). The domain type alone, no framework; its own test, never a
   criterion's. `factory-cli.py --files-skeleton <story> test` writes tests.md's `## Invariants` rows; fill the last cell
   `<Class>#<method>`. Refused: a rule without its own test, a test not in the project, a criterion's test in the table.
   - A rule the code lacks yet → its test is red before the build: that is its proof.
   - A rule the code has → the test is green: write its **break**, `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`
     — the smallest `git apply` production change turning exactly this test red (`git diff`, then revert). Green under its
     break, or green without one → refused (`invariant-breaks`).
   - No unit test for a use case: its port test runs it wired; a second test of the same path with doubles proves the
     doubles.
