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

`status: adopted`: the change is a claim — each mapped test proves its scenario. Read each test against its scenario:
arranges the `Given`, performs the `When`, asserts every `Then` and `And` with the scenario's values? Passing without
asserting the outcome, or asserting another → **major**. A break changing something the test does not depend on →
major. Each `gate:invariants` row the same: a test not asserting its rule → **major**. `pass` only when every scenario is
proved; nothing else is reviewed.
