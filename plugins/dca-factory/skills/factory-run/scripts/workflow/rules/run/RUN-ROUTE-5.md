---
id: RUN-ROUTE-5
title: A changed test is recorded red again before building
part: decision
stages:
- build
- tidy
fail: the test changed since its red proof — the run starts at the test stage instead, no round is spent
goes.fail: test
---

# RUN-ROUTE-5

**When:** a run resumes at build or tidy and a test changed since its red proof

**Why:** a test changed on the main line is recorded red again before anything is built on it
