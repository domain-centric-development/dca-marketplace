---
name: factory-discover
description: Finds out, with the person who owns the product, which problem is worth solving and how anyone will know it got better — from a problem or a wished deliverable to a discovery report with cited sources (web, the project's files, interviews and tickets handed over, kept as anonymised excerpts) and proposed epics, each with its outcome event. Use before the backlog, when someone brings a problem, a goal, an OKR's key result or a deliverable and the epics it implies are not clear yet, or on "/factory-discover <topic>". Writes no epic until the person releases one, and never a story, a plan or code.
---

# Discover what is worth building

Input: a problem or a wished deliverable in the person's words, the project description (product,
technical decisions, designed domain), the epics that exist and what they delivered, and the documents
the person hands over. Output: `<discovery>/<topic>/discovery.md` with its `sources/`, and — once the
person releases one — an epic in the backlog contract that links its report. The place is the profile's
`discovery:`, by default `project/discovery`. You write no story, no plan and no code.

The craft — framing a problem, evidence, options, an outcome that can be observed, research with
sources — is the carrier's: the profile's `carrier.discover:` names the skill, by default
`product-discovery`. Load it before the first question. Where no carrier is installed, follow the five
parts as this skill lists them and say that the craft skill is missing.

Discovery is few turns and much judgement, and a wrong problem costs every story built on it: recommend,
once at the start, the most capable model the session offers. Do not insist.

## The topic and its folder

The topic is a short lowercase hyphenated name (`monthly-report`); ask for one if the person gave none.
Its folder holds, and nothing else:

```text
<discovery>/<topic>/
  discovery.md        the report — templates/discovery.md.tmpl, committed
  sources/            the excerpts the report cites, committed
  originals/          the documents as handed over — never committed
  .gitignore          `originals/`, written with the folder
```

Write `.gitignore` with the line `originals/` before anything lands in the folder.

## Do

1. **Read what is there.** The project description, the epics and what they delivered (their outcome
   events), an earlier report on the topic. A report that exists is continued, never started again.
2. **Ask the catalogue.** `reference/questions.md` holds the questions, in order, word for word. Ask
   only the open ones, all at once; what the description or the person already answered is not asked
   again. Answers go where the entry says.
3. **Take in the documents.** The person hands them over in one of two ways: a path or pasted text in
   the session, or files they put into `originals/`. Read everything in `originals/` and every path
   given. Say once, at the first document, that what is read enters the model's context and its session
   record even when nothing is committed — an anonymised version is the safer input. **For each
   document ask once: keep it whole, or as an excerpt?** The excerpt is the default: only the passages
   the report cites, names and identifying details replaced (`Interview 1`, `a team lead`), written to
   `sources/<n>.md`. Whole means a copy under `sources/` — only on an explicit yes. The original stays
   where it was; the report notes who holds it, never a path on someone's machine.
4. **Research.** Search the web where the session can, read the project's own files. Every claim in the
   report cites a source listed under `## Sources`: `[S1]` in the text, `- [S1] <title> — <where>` in
   the list, where is an excerpt (`sources/interview-1.md`), a project file, or a URL with
   `read YYYY-MM-DD`. A claim without a source is an assumption and goes under `## Risks and open
   questions`.
5. **Write the report** from `templates/discovery.md.tmpl`: the sections in the template's order.
   Under `## Proposed work`, one `### <epic-id>` per body of work worth doing, each with `- intent:`,
   `- goal:`, `- metric:` (the outcome event — a fact the system records when the problem is solved for
   someone, named as the glossary names it, or a new name marked as such) and `- domain_contact:`
   (`open` where nobody is named yet). For every one ask how its effect will be recognised — the
   question a list of deliverables does not ask. A target goes into `goal:` only where the person can
   measure it.
6. **Check it with the gate:** `bash .agents/factory/factory.sh discover --check <topic>` — the
   sections, every citation listed, every source resolving, every proposal with intent, goal and metric,
   `originals/` ignored. Fix every finding before you hand the report over. Report what it said.
7. **The person decides.** Show the proposals; write nothing into the backlog until the person releases
   one. A released proposal becomes an epic through `factory-backlog`, with `discovery:
   <discovery>/<topic>/discovery.md` in its front matter; the backlog's own questions (the domain
   contact, the journey) follow there.

## Do not

- Do not decide which problem to solve or which option to take; propose and say what would decide.
- Do not write an epic, a story or a plan the person has not released.
- Do not commit an original, or a name from one, without the person's explicit yes.
- Do not present a single interview as a pattern, or an assumption as evidence.
- Do not invent a metric, a target or a domain contact.
