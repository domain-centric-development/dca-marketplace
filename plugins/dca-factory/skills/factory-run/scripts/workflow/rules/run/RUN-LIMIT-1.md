---
id: RUN-LIMIT-1
title: A stage that hangs is stopped at its timeout
part: decision
fail: the stage runs too long — its process group is stopped (124) and the stage failed
goes.fail: stop
---

# RUN-LIMIT-1

**When:** a stage runs longer than `FACTORY_STAGE_TIMEOUT` or `stageTimeout:`

**Why:** a stage that hangs costs no night
