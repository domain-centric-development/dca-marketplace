# factory-discover — the questions

One entry per question, in the order they are asked. The skill looks each answer up first and asks
**only the open ones — all at once, in this order, word for word**. An answer goes into the report
section the entry names, in the person's words, with `[Sn]` where it rests on a source.

Each entry has the same fields:

- **look up** — where the answer may already be; found there, the question is not asked;
- **question** — the text, word for word;
- **answer goes to** — the report's section.

### DISC-PROBLEM
- look up: the person's words with the call; an earlier report's `## Problem`
- question: What problem should go away, and for whom? Describe it without the solution — what happens today, how often, and what it costs.
- answer goes to: `## Problem`

### DISC-START
- look up: the person's words with the call
- question: Did this start as a wished deliverable or a goal (a feature, a key result)? Then name it — it is one option, not the problem.
- answer goes to: `## Options`

### DISC-USERS
- look up: `project/product.md → ## What and for whom`
- question: Who has the problem — which actors, how many, in which situation?
- answer goes to: `## Users and evidence`

### DISC-EVIDENCE
- look up: `originals/`, the paths handed over
- question: What shows that the problem exists — interviews, tickets, support numbers, observations? Hand them over: a path, pasted text, or files in the topic's `originals/` folder.
- answer goes to: `## Users and evidence`

### DISC-TODAY
- look up: the project's code and documents; the epics already delivered
- question: How do the people affected deal with it today, and what does the product already do about it?
- answer goes to: `## Users and evidence`

### DISC-OUTCOME
- look up: the glossary's events; the epics' `metric:`
- question: When the problem is solved for someone, which fact would the system record? If you can measure it, from what to what should it change?
- answer goes to: `## Outcome`

### DISC-LIMITS
- look up: `project/tech.md`, `project/product.md → ## Not part of the product`
- question: What is out of bounds — time, budget, technology, rules a solution must not break?
- answer goes to: `## Risks and open questions`

### DISC-CONTACT
- look up: the epics' `domain_contact:`
- question: Who answers questions about this domain while the work is built?
- answer goes to: `## Proposed work` (`- domain_contact:` of every proposal)
