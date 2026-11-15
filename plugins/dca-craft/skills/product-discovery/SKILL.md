---
name: product-discovery
description: |
  The craft of finding out which problem is worth solving and how anyone will know it got better:
  framing a problem apart from its solution, users and the evidence about them, options with their
  risks, an outcome that can be observed, and research where every statement cites its source —
  web pages, the project's files, interview notes and tickets a person hands over, kept as
  anonymised excerpts unless the person says otherwise. Use when someone brings a problem or a
  wished deliverable and the work it implies is not yet clear, before anything is planned, or as
  the carrier of the discovery craft for a delivery pipeline's discovery step.
disable-model-invocation: false
---

# /product-discovery

Answers two questions before anyone plans: which problem is worth solving, and how anyone will know it got better.
Writes no plan, story or code — a report a person decides on. A wished deliverable ("we need an export") is a
solution: go back to the problem and its evidence (who, how often).

## The five parts

1. **Problem** — one paragraph in the words of those who have it, no solution, naming what it costs and whom.
   Not "users cannot export" but "the team rebuilds the monthly report by hand, four hours each month".
2. **Users and evidence** — who has it, what shows it (interview passage, ticket, support count, page). Each claim
   cites its source; one without is listed as an assumption, never a finding.
3. **Options** — ≥ 2, doing nothing included. Each: what changes for the user, rough cost, main risk (value,
   usability, feasibility, viability). Do not rank by preference; say what would decide.
4. **Outcome** — per option worth pursuing, the business event the system records when the problem is solved for
   someone (`ReportSent`), not features shipped. The fact at the end of the flow, not an event at its start
   (intent). A target ("4 hours → 10 minutes a month") only where the person can measure it; else leave it open.
5. **Risks and open questions** — what is unknown, what would change the recommendation, who could answer.

## Research

- Sources first, then claims. Every statement cites: URL with read date, project file with line
  (`docs/support.md:14`), or excerpt file with line.
- Report what could not be verified: a page that would not open, numbers differing between sources.
- Hand-over documents (interviews, tickets, exports) come by path, pasted text, or a folder of originals kept out of
  version control. Ask once per document: whole or excerpt? **Default excerpt**: only cited passages, names and
  identifying details removed (`Interview 1`, `a team lead`). The original stays put; the report names who holds
  it, never a local path.
- At the first document, say once: what is read enters the model's context and session record even uncommitted —
  an anonymised version is safer for a sensitive interview.
- Recommend once, at the start, the most capable model the session offers; never insist.

## The report

One per topic, these headings in order: `## Problem`, `## Users and evidence`, `## Options`, `## Outcome`,
`## Risks and open questions`, `## Proposed work`, `## Sources`.

- `## Proposed work`: each body of work with why it exists, what changes for the user, the outcome fact that
  measures it, who answers questions about it.
- `## Sources`: each source once, `- [S1] <title> — <URL, read YYYY-MM-DD | file path | excerpt file>`; claims cite
  `[S1]`.

Where a project or pipeline names the report's place and checks its shape, follow it.

## Do not

- Work backwards from a solution to a problem that fits it.
- Present an assumption as evidence, or one interview as a pattern.
- Invent a metric or target the person cannot observe.
- Commit an original interview, or a name from it, without the person's explicit yes.
- Decide. The report proposes; the product owner chooses.
