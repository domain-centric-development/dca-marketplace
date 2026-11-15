---
id: STAGE-COMMON-22
part: told
why: every requested change went to the build, which may not touch tests, so a too weak test stopped the story for a human
section: A repeat round
order: 22
---

# STAGE-COMMON-22

- *The judge asked for changes*: each stage fixes exactly its own confirmed defects in `judge.md` — a test asserting
  too little is the test stage's (with its break), the code is the build's — nothing else.
