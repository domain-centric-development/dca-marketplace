---
id: RUN-ROUTE-5
part: decision
fail: the run starts at the test stage instead — no round
goes.fail: test
---

# RUN-ROUTE-5

**When:** a run resumes at build or tidy and a test changed since its red proof

**Why:** a test changed on the main line is recorded red again before anything is built on it
