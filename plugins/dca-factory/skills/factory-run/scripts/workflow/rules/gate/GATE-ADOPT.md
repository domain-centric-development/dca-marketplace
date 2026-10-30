---
id: GATE-ADOPT
part: check
reports:
- adopt
- tests-green
pass: the story is `status: adopted` and its tests are green
fail: the story is not adopted, or a test is red
---

# GATE-ADOPT

**When:** the adopt gate

**Why:** an adopted story proves what holds with green tests, never builds
