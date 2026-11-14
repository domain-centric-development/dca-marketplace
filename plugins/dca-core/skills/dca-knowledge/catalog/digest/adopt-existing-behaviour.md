# Adopt existing behaviour into the backlog — digest

Node: `/recipe/adopt-existing-behaviour.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Describe what the system already does as a story, and let it count as delivered only with evidence.

## Steps (first sentence each)

1. **Write the story as for new behaviour** — keyed scenarios under business rules, the project's own words — and mark it adopted (`status: adopted`).
2. **Plan: find the behaviour and its test.** For each scenario, name where the behaviour lives and which existing test covers it — or that none does.
3. **Map every scenario to a test.** The existing test where there is one.
4. **Break every test you wrote, once.** A minimal change to the production code that turns exactly this test red, kept as a patch beside the story and applied to a scratch copy — never to the working tree.
5. **Review the claim.** A fresh reviewer reads every mapped test against its scenario: does it arrange the `Given`, perform the `When`, assert every `Then`? A test that passes without asserting the outcome is a defect ([pitfall](/pitfall/a-green-test-that-asserts-nothing.md)).
6. **Deliver as adopted.** Every test green, every break red, the review passed: the story counts as delivered, a new story may depend on it, and its tests are guarded like any delivered story's.
