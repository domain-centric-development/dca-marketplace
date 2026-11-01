---
id: GATE-TESTS-REAL
title: A criterion's test runs through the real use case
part: check
reports:
- tests-real
pass: no integrated or end-to-end test replaces its input port
fail: a criterion's test mocks the input port it should drive
---

# GATE-TESTS-REAL

**When:** the test or adopt gate runs (contract 21 on)

**Why:** a criterion's test runs through the real use case; only what lies outside is replaced
