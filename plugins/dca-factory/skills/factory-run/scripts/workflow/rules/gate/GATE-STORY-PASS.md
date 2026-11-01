---
id: GATE-STORY-PASS
title: A delivery rests on one pass through every stage
part: check
reports:
- story-pass
pass: every hand-over is of this pass, the judge said pass and the story is unchanged since the plan
fail: a hand-over is missing or from an earlier pass, there is no `verdict: pass`, or the story changed since the plan — a round runs from where the story's state resumes: the stage of the missing pass, plan for a changed story
goes.fail: again
skip: there is no story digest from the plan gate
---

# GATE-STORY-PASS

**When:** the document gate runs

**Why:** a delivery rests on one pass through every stage of the current story
