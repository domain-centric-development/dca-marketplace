---
id: GATE-INVARIANTS-COVER
title: Every domain type the story changes has its invariants line
part: check
stages:
- build
- tidy
kinds:
- story
reports:
- invariants-cover
pass: every domain type the story's change touched has a line under `## Invariants` — the plan's, or build.md's for a type the build reached
fail: a domain type the story changed has no line under the plan's `## Invariants`
---

# GATE-INVARIANTS-COVER

**When:** the build and tidy gates run, for a plan that came about under contract 36 or later

**Why:** a type the plan never weighed gets a guard nobody named and a rule nobody tested — a value from a request
reaching it through a new factory is the plan's to see

The domain layer is where the profile's `layer.domain` places it — blank-separated globs from the project root; in a
project with the method's configuration (`dca.profile.yaml`) and no such line, every folder named `domain` or
`<Project>.Domain`. A type is
a changed production file there, named by its file; a test source, a file of no type of its own (`package-info`,
`__init__`, `index`) is none. Its line names it, with its rules or `none — <why>`.
