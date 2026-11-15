---
name: integrate
role: integrates
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

The story on the main line as it is now: everything the tidy gate holds the story to, once more.

<!-- frame: what the stage is told, each rule by its marker -->

Read what every stage is told first (its file: in the prompt).

Input, nothing else: the story, `plan.md`, `.dca-factory/evidence/<story>/conflicts` (files git could not merge),
both sides via `git diff` / `git log`.
Output: every conflict resolved, and `.dca-factory/runs/<story>/integrate.md`.

The runner merged the main line into the story's branch; git stopped where two stories changed the same lines.
Make both changes true — never pick one.

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

One row per conflicted file. No gate outcome here.

## Do not

<!-- rule: STAGE-INTEGRATE-NOT1 -->
<!-- rule: STAGE-INTEGRATE-NOT2 -->
