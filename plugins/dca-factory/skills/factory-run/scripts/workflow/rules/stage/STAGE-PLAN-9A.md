---
id: STAGE-PLAN-9A
part: told
stages:
- plan
section: Do
marked: stage-plan/SKILL.md
order: 12
---

# STAGE-PLAN-9A

9a. **Find what the system already shows.** A scenario whose `Then` holds on today's code cannot get a red
   test, and the test gate refuses a green one. Look for it the same way — the test sources, and the
   scenarios of the delivered and adopted stories under the epics. Who carries it decides what you do:
   - **only code carries it, no story, and a test shows it** → ask nothing. Write `## Adopt` in plan.md, one row
     per such scenario: `| <key> | <Class>#<method> |`, the test that shows it holds today. The plan gate adopts
     what you name: every scenario of the story → the story becomes `status: adopted`, and the runner goes on with
     it as an adoption (end the plan there, write no later stage's file); some → they move into an adopted story
     `<story>-holds` beside this one, and you plan the rest as usual. Where the scenarios that hold include the
     story's only happy path and others remain, do not adopt: ask, as below;
   - **a delivered or adopted story's scenario carries it** → write **one** decision record (`stage: plan`) naming
     each such scenario, the test that asserts it (file and line) and the story that delivered it, and stop;
     recommend `superseded` for a whole story, or taking the scenario out of this one;
   - where the story reads as asking for more than what holds — its wording names behaviour the code lacks — ask
     too, with the option to change the story so it asks for what the page does not do yet.
   A scenario the story changes is step 9's, not this one.
