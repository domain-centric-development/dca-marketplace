---
name: integrate
order: 8
hand_over: integrate.md
kinds:
- story
- journey
- adopt
- task
traits:
- gated
- tested
- suite
commands:
- architecture
- format
---

# integrate

The story on the main line as it is now: everything the tidy gate holds the story to, once more. Its skill, where two stories met: `stage-integrate`.

<!-- frame: what the stage is told, each rule by its marker -->

First read `factory-run/reference/stage-common.md` — the rules every stage holds to: a session the
runner started, one session that carries several stages, a repeat round, the shell, the gate. The
runner's prompt names its path and repeats none of it.

Input: the story, `.dca-factory/runs/<story>/plan.md`, `.dca-factory/evidence/<story>/conflicts` — the files git
could not merge — and the two sides as git shows them (`git diff`, `git log`). Nothing else.
Output: the conflicted files with every conflict resolved, plus `.dca-factory/runs/<story>/integrate.md`.

Every story runs in a worktree of its own and reaches the main line only when it is integrated: the runner
merges the main line into the story's branch and squashes the story to one commit. Most merges need no hand.
Where two stories changed the same lines — the same glossary section, the same aggregate, the same page — git
stops and names the files. This step makes both changes true; it is not a choice between them.

## Do

<!-- rule: STAGE-INTEGRATE-1 -->
<!-- rule: STAGE-INTEGRATE-2 -->
<!-- rule: STAGE-INTEGRATE-3 -->
<!-- rule: STAGE-INTEGRATE-4 -->
<!-- rule: STAGE-INTEGRATE-5 -->
<!-- rule: STAGE-INTEGRATE-6 -->
<!-- rule: STAGE-INTEGRATE-7 -->

## The integrate file

```markdown
# Integrate — <story id>

| File | The story changed | The main line changed | How both hold |
|---|---|---|---|
```

One row per conflicted file. The gate's outcome is not recorded here: its report is the evidence.

## Do not

<!-- rule: STAGE-INTEGRATE-NOT1 -->
<!-- rule: STAGE-INTEGRATE-NOT2 -->
