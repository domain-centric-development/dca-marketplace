---
id: STAGE-BUILD-NOT2
part: told
stages:
- build
section: Do not
order: 12
---

# STAGE-BUILD-NOT2

- **A test whose expectation cannot hold** — two assertions that exclude each other, a substring
  that also matches what must be there — is a question about what the story expects, not a
  deviation: write `## needs-human` naming a decision record with `stage: build` that names the
  test, the line and why it cannot hold, and stop (what every stage is told). Once a human has answered — and repaired
  the test where the answer says so — the build runs again and cites the id in `build.md`.
