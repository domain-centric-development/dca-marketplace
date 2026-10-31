---
name: tidy
order: 4
hand_over: tidy.md
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
- tidy.md
---

# tidy

The refactor step the build stage skips, taken with every test green and without changing behaviour — so its whole claim is that everything still holds: its gate runs the build's commands again after the refactor. Its skill: `stage-tidy`.
