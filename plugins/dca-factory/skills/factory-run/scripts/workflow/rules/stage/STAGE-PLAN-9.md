---
id: STAGE-PLAN-9
part: told
why: a story changed agreed behaviour without saying so, and older tests were quietly rewritten
stages:
- plan
section: Do
order: 11
---

# STAGE-PLAN-9

9. **Find the existing tests the story contradicts** — any test in the project, read in the test sources, not the
   backlog. List each under `## Changed tests` with its backing line from the story's `## Changed expectations`.
   - No such section but contradicting tests → the story changes agreed behaviour unsaid: **one** decision record
     (`stage: plan`) listing each, with today's expectation and what the story would need; stop. Answered → plan again,
     cite the id in each row.
   - Only listed and backed tests may change in later stages; an uncontradicted test is not listed.
   - A test that only follows a changed shape (a type gains a field, a type or method is renamed; assertions and
     expected values stay) is not contradicted: neither listed nor asked about.
