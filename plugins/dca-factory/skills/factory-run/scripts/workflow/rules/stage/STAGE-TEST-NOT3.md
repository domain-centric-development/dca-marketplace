---
id: STAGE-TEST-NOT3
part: told
why: a stage changed what an older test expected and turned a contradiction green unnoticed
stages:
- test
section: Do not
order: 19
---

# STAGE-TEST-NOT3

- Do not change what a test that existed before this story expects — unless the plan lists it
  under `## Changed tests`. Change those to the story's new expectation; everywhere else add a
  case and leave the old lines as they are. The gate compares every test file against the state
  the plan gate recorded and refuses a changed or removed line the plan does not list and back —
  except around the assertions: where a type the test builds gains a field, give the old call the
  new argument and keep every assertion, its expected values and matchers as they were. That is
  no changed expectation and needs no question.
  A contradicting test the plan missed is a question (a decision record with `stage: test`).
