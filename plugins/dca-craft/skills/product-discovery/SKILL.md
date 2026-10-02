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

# /product-discovery — From a problem to work worth doing

Discovery answers two questions before anyone plans: **which problem is worth solving**, and
**how will anyone know it got better**. Everything else in this skill serves those two. It writes
no plan, no story and no code; what it produces is a report a person decides on.

A wished deliverable ("we need an export") is a fine starting point, but it is a solution. The
first move is always back to the problem it is meant to solve — and to whether there is evidence
that the problem exists, for whom, and how often.

## The five parts

1. **Problem** — one paragraph, in the words of the people who have it, with no solution in it.
   "Users cannot export" is a missing feature; "the team rebuilds the monthly report by hand,
   four hours each month" is a problem. Name what it costs and whom.
2. **Users and evidence** — who has the problem, and what shows it: an interview passage, a ticket,
   a support count, a page that says so. Each claim carries its source. A claim without one is an
   assumption and is listed as such — never written as a finding.
3. **Options** — at least two ways to address the problem, doing nothing included. For each: what
   it changes for the user, what it costs roughly, and its main risk (value, usability, feasibility,
   viability). Do not rank by preference; say what would decide between them.
4. **Outcome** — for every option worth pursuing, the observable fact that shows it worked: a
   business event the system records when the problem is solved for someone (`ReportSent`,
   `OrderPlaced`), not a count of features shipped. A target ("from 4 hours to 10 minutes a
   month") only where the person can measure it; otherwise name the fact and leave the target open.
   An event that fires at the start of a flow measures intent; the outcome is the fact at its end.
5. **Risks and open questions** — what is still unknown, what would change the recommendation, and
   who could answer it.

## Research

- **Sources first, then claims.** Search the web, read the project's own documents, read what the
  person hands over. Every statement in the report cites where it stands: a URL with the date it
  was read, a project file with its line (`docs/support.md:14`), an excerpt file with its line.
- **What you could not verify, you say.** A page that could not be opened, a number that differs
  between two sources — both go into the report as they are.
- **Hand-over documents** — interviews, tickets, exports — reach the session by a path or as pasted
  text, or from a folder of originals the project keeps out of version control. For each one, ask
  once: keep it whole, or keep an excerpt? **The excerpt is the default**: only the passages the
  report cites, with names and identifying details removed (`Interview 1`, `a team lead`). The
  original stays where it was; the report notes only who holds it, never a path on someone's machine.
- **Say once, at the first document,** that whatever is read enters the model's context and its
  session record even when nothing is committed — an anonymised version is the safer input for a
  sensitive interview.
- **Use the most capable model the session offers.** Discovery is few turns and much judgement; a
  wrong problem costs every piece of work built on it. Recommend it once at the start; never insist.

## The report

One report per topic, in this order: `## Problem`, `## Users and evidence`, `## Options`,
`## Outcome`, `## Risks and open questions`, `## Proposed work`, `## Sources`. `## Proposed work`
names each body of work worth doing with why it exists, what changes for the user, the outcome
fact that measures it and who answers questions about it. `## Sources` lists every source once:
`- [S1] <title> — <URL, read YYYY-MM-DD | file path | excerpt file>`; claims cite `[S1]`.

Where a project or a pipeline names the report's place and checks its shape, follow that; this
skill is the craft, not the location.

## Do not

- Do not start from the solution and work backwards to a problem that fits it.
- Do not present an assumption as evidence, or a single interview as a pattern.
- Do not invent a metric or a target the person cannot observe.
- Do not commit an original interview, or a name from it, without the person's explicit yes.
- Do not decide. The report proposes; the person who owns the product chooses.
