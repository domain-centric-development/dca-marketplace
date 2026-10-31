---
id: STAGE-TEST-ADOPT
part: told
stages:
- test
kinds:
- adopt
section: Adopt mode
marked: stage-test/SKILL.md
order: 16
---

# STAGE-TEST-ADOPT

For a story with `status: adopted`: map every scenario in the `gate:tests` table to the existing test the
plan names, green as it is. For a scenario without one, write a **characterization test** — green on
today's code, asserting the scenario's `Then` with its values — list it under `## Characterization` in
`tests.md` (`- <Class>#<method>`), and write its **break**: `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`,
a unified diff against the working tree that changes the production code minimally so that exactly this
test turns red (`git diff` of the change, then revert it). Change no production code and no existing test;
the gate applies the break to a scratch copy and expects red there. The plan's invariants are held the same
way: every rule gets its row in the `gate:invariants` table — an existing unit test that asserts exactly that
rule, or a characterization unit test you write, listed under `## Characterization` with its break. The adopt
gate runs every rule's test green beside the scenarios' tests.
