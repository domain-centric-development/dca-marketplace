---
type: Section
title: "Escalation: the three answers a run may not give itself"
chapter: "Delivering a story: backlog, stages, gates"
source: guide
tags: [guide, section]
---

The judge returns exactly one of three verdicts, and the third is the reason this list exists:

- **pass** — the criteria are met and no confirmed defect blocks them.
- **changes-requested** — confirmed defects go back to the build stage with their evidence. Count
  the rounds and stop at three: a loop that will not converge needs a human, not a fourth attempt.
  A planned change left undone is such a defect — ranked a minor, it is recorded and delivered, and
  the plan quietly stops being what was built. One case is not: an addition the build left out on
  purpose, with its reason recorded, where the code bears the reason out — every criterion met, no
  planned rule lost, no convention asking for it. Then the plan was wrong and the code is right; the
  judge names the deviation as a minor and does not stop the story over it.
- **story-conflict** — the story or the plan is wrong. This never goes back to the build stage. A
  correction that changes an agreed criterion must not happen silently; the story is the contract,
  and a human decides it.

**A verdict is weighed by its rows, and a finding's origin is computed.** For every confirmed defect
the pipeline reads from the story's diff whether its line is one the story added or changed —
*introduced* — or code that was there before — *pre-existing*. A review that keeps finding old code
never converges: each round finds a few more old defects, and the story pays a round for every one.
So a pre-existing defect is recorded beside the story and costs no round, a blocker included; a
`changes-requested` whose blocking rows are all pre-existing goes on as a pass, and a `pass` over a
blocking defect the story introduced is no pass. From the second round on the judge reviews what the
round changed: a new blocking finding on a line the round did not touch, at a place no earlier verdict
named, is recorded as a minor. A defect names its class, and every instance of the class goes into
one round — fixing one instance a round is the loop again. A pre-existing blocker is offered to a
person as a task of its own.

**What became of a finding is computed too.** Every verdict is kept, and every blocking finding gets
an outcome at the next one: *repeated* (raised again), *fixed* (gone, its line changed), *dropped*
(gone, its line as it was) or *overruled* (a person's answer closed it). The story's findings keep
them with the outcome beside the person's own status, and three numbers say how the judge does on
real stories: the share of stories that pass on the first verdict, the judge rounds a story needs, and
the share of blocking findings dropped or overruled — its false alarms.

Two more questions belong to a human by construction, and a run that meets one of them stops and
says so instead of answering it:

- **A new bounded context, or a new relationship between contexts.** That is a decision about
  language boundaries and ownership, recorded as a decision and reflected on the designed map — never
  smuggled in by a story. A context that is designed and not built yet is no such question: the
  story plans it as new.
- **A surface the story's actor does not have.** If the criteria can only be observed through a page
  or an endpoint the context does not offer, adding one is a product decision, and where the surface
  needs a guard it is an authorisation decision as well. A guard nobody decided is a guard no test
  holds.

**The question is a file, and so is the answer.** A run that stops writes the question as a record
of its own — the story it blocks, the stage that asked, the options it sees, its recommendation —
never into a chat and never as an answer. Whoever decides writes the answer into that record with
their name and the time; a recommendation, a default, a timeout or an unsigned draft is not one.
The stage that asked runs again with the answer in front of it — or, where the answer names an earlier
one (an answer that changes a test goes back to the test stage), that one — and a check that reads the record
— not the stage's word — refuses the story while the question is open and marks the record applied
once the stage has taken it up. Three things follow: the question survives the session, a second
person can answer it without the first one's transcript, and nobody can mistake a suggestion for a
decision.
