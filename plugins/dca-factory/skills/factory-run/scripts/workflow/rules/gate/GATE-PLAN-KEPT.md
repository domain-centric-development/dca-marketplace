---
id: GATE-PLAN-KEPT
title: The plan stays as its gate passed it
part: check
stages:
- test
- build
- tidy
reports:
- plan-kept
pass: plan.md is as the plan gate passed it
fail: plan.md changed after its gate passed it — a stage after the plan wrote it
---

# GATE-PLAN-KEPT

**When:** a gate of the test, build or tidy stage runs, for a plan a stamped plan gate passed (contract 38 on)

**Why:** a stage after the plan that rewrites plan.md makes every later hand-over one of an earlier pass, and the
delivery sends the story a round back; what a later stage adds or takes back belongs in its own file

The plan gate stamps the plan's digest when it passes it; this check compares plan.md with the stamp. What the build
adds or takes back stands in build.md — a domain type's line under `## Invariants` (`invariants-cover`), a planned
file taken back under `## Plan changes`, `- `<path>` — <why>` (`plan-files`) — and the gates read it beside the plan.
A plan that is wrong goes back to the plan stage, whose gate stamps it anew.
