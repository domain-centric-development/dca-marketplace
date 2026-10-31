---
id: STAGE-PLAN-9
part: told
stages:
- plan
section: Do
marked: stage-plan/SKILL.md
order: 11
---

# STAGE-PLAN-9

9. **Find the existing tests the story contradicts** — every test in the project, whoever wrote it:
   the ones that assert the behaviour the criteria change. Read the test sources, not the backlog;
   a test need not belong to any story. List each under `## Changed tests` with what backs the
   change: the line of the story's `## Changed expectations` it follows. Where the story has no
   such section and you still find contradicting tests, the story changes agreed behaviour without
   saying so — write **one** decision record (`stage: plan`) listing every one of them, with the
   expectation each holds today and what the story would need instead, and stop. Once answered,
   plan again and cite the id in each row. A test the story does not contradict is not listed; the
   gate lets the later stages change only what is listed and backed. A test that only has to follow a
   changed shape — a type it builds gains a field, or a type or a method it names is renamed, its assertions and
   expected values stay — is not contradicted: it is neither listed nor asked about.
