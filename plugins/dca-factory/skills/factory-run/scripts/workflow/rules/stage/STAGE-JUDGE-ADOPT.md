---
id: STAGE-JUDGE-ADOPT
part: told
why: an adopted story could pass on tests that run its scenario without asserting its outcome
stages:
- judge
kinds:
- adopt
section: Adopt mode
order: 13
---

# STAGE-JUDGE-ADOPT

For a story with `status: adopted`, the change is not code but a claim: each mapped test proves its
scenario. Read every test against its scenario — does it arrange the `Given`, perform the `When` and
assert every `Then` and `And` with the scenario's values? A test that passes without asserting the outcome,
or asserts another one, is **major**. A break that changes something the test does not depend on is major
too. Each row of the `gate:invariants` table is read the same way: a test that does not assert its rule is
**major**. The verdict is `pass` only when every scenario is proved; nothing else is reviewed — nothing was built.
