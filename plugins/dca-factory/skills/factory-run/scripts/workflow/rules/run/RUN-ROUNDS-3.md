---
id: RUN-ROUNDS-3
title: A round that repeats the last refusal restarts fresh
part: decision
stages:
- test
- build
- tidy
- document
- adopt
- integrate
fail: the gate refuses as it refused the round before — the same stage, the same failed checks, the same failing tests; the next round runs in a fresh process from the story, the plan, the gate's report and the round record, the earlier attempt's hand-over set aside
goes.fail: again
---

# RUN-ROUNDS-3

**When:** a gate refuses exactly as it refused the round before, and no fresh restart came between the two

**Why:** a retry without a changed input repeats the refusal; an attempt that starts from the failed attempt's own account debugs worse with every round
