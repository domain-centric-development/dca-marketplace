---
id: STAGE-PLAN-9A
part: told
why: a scenario that already held on today's code got a test that could never be red, and the test gate refused it
stages:
- plan
section: Do
order: 12
---

# STAGE-PLAN-9A

9a. **Find what the system already shows.** A `Then` that holds on today's code cannot get a red test, and the test
   gate refuses a green one. Search the test sources and the delivered and adopted stories' scenarios:
   - **only code carries it, a test shows it, no story** → ask nothing; `## Adopt` in plan.md, one row per scenario
     `| <key> | <Class>#<method> |`. The plan gate adopts: all scenarios → the story becomes `status: adopted` and runs as
     an adoption (end the plan there, no later stage's file); some → they move into an adopted `<story>-holds`, plan the
     rest. If the holding ones include the only happy path and others remain: do not adopt, ask as below;
   - **a delivered or adopted story's scenario carries it** → **one** decision record (`stage: plan`) naming each
     scenario, its test (file, line) and its story; stop. Recommend `superseded` for a whole story, or removing the
     scenario from this one;
   - the story's wording asks for more than what holds → ask too, with the option to change the story to what the page
     does not do yet.
   A scenario the story changes is step 9's.
