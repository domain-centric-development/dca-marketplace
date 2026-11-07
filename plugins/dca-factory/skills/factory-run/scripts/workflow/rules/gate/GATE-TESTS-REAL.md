---
id: GATE-TESTS-REAL
title: A criterion's test runs through the real use case
part: check
reports:
- tests-real
pass: no integrated or end-to-end test replaces its input port, or it is the adapter's beside one that does not
fail: a criterion's test mocks the input port it should drive, or a criterion given both shapes has no test through the real input port
---

# GATE-TESTS-REAL

**When:** the test or adopt gate runs (contract 21 on)

**Why:** a criterion's test runs through the real use case; only what lies outside is replaced

A criterion the plan gives `integration (adapter: …)` alone tests the adapter's translation against a stubbed
input port. One the plan gives both shapes — through the port and the adapter's, anywhere in its `level:` — may stub
the input port in its adapter test, as long as one of its tests above the unit level runs through the real one.
