---
id: STAGE-TEST-ADOPT
part: told
why: a test written for an adoption could pass whatever the code did unless a break showed it turn red
stages:
- test
kinds:
- adopt
section: Adopt mode
order: 16
---

# STAGE-TEST-ADOPT

`status: adopted`: map each scenario in `gate:tests` to the existing test the plan names, green as is. No test →
write a **characterization test** (green on today's code, asserting the `Then` with its values), list it under
`## Characterization` in tests.md (`- <Class>#<method>`) with its **break** `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`
— a unified diff, the minimal production change turning exactly this test red (`git diff`, then revert). No production
or existing-test change; the gate applies the break on a scratch copy and expects red. Each invariant rule gets its
`gate:invariants` row: an existing unit test asserting exactly that rule, or a characterization unit test with its break.
The adopt gate runs every rule's test green beside the scenarios'.
