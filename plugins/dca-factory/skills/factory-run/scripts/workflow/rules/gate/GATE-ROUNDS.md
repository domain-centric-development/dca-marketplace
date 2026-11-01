---
id: GATE-ROUNDS
title: A story gets at most three rounds
part: check
reports:
- rounds
pass: the story is in round n of at most 3
fail: three rounds ended without convergence — the story stops and escalates
goes.fail: stop
---

# GATE-ROUNDS

**When:** a gate runs, once a story went round

**Why:** a story that does not converge goes to a person, not on
