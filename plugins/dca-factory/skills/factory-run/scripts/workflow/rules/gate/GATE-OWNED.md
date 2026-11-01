---
id: GATE-OWNED
title: A stage leaves what a person owns unchanged
part: check
reports:
- owned
pass: nothing a person owns changed during the stage
fail: the story or an answer changed under a stage — a person looks and confirms (`--owned-confirm`)
goes.fail: stop
---

# GATE-OWNED

**When:** a gate runs, once a stage window was recorded

**Why:** the story and every answer are the person's — a stage asks, it never answers
