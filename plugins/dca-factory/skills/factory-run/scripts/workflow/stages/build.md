---
name: build
order: 3
hand_over: build.md
window: builder
kinds:
- story
- task
traits:
- gated
- post_gated
- tested
- lists
- guarded
- suite
- in_order
commands:
- architecture
- format
sizes:
- build.md
---

# build

Writes the production code that turns the story's red tests green, with the smallest change that works. Its skill: `stage-build`.
