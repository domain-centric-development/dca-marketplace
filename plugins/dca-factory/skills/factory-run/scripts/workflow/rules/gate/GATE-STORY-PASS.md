---
id: GATE-STORY-PASS
part: check
reports:
- story-pass
pass: every hand-over is of this pass, the judge said pass, the story unchanged since the plan
fail: a hand-over missing or from an earlier pass, no `verdict: pass`, or the story changed since the plan — a round from where the story's state resumes: the stage of the missing pass, plan for a changed story
goes.fail: again
skip: no story digest from the plan gate
---

# GATE-STORY-PASS

**When:** the document gate

**Why:** a delivery rests on one pass through every stage of the current story
