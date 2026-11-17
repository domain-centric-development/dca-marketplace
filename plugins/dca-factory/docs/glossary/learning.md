# Glossary — Bounded Context: learning

What repeats across the stories, counted and never guessed, and what a person decided about it — so nothing decided is
asked again, unless the place it was put did not hold it. Learning reads delivery's facts through delivery's `api`
(`api/learning.py`) and files a lesson in delivery's decision inbox through the same api; delivery knows no lesson.

Code: `dca_factory/learning/` — `domain/model/` flat (`lesson.py`, `maintainer_issue.py`, `words.py`), `application/`
the use cases (show, write, write an issue), `application/shared/` the output ports, `adapter/outgoing/delivery/` what
it reads and files through delivery's api, `adapter/outgoing/files/` the issue texts, `adapter/incoming/cli/`
`factory.sh lessons`.

### Signal (Signal) · Signal key (SignalKey)

**Definition:** One counted occurrence of a kind of deviation, with the story and the record, row or line it stands in.
Its key is what makes two signals the same: `<context>/<tag>` for a question, a finding's class on a hierarchy —
`<target>/<type>`, within it `<perspective>/<target>/<type>/<qualifier>`, within that `<perspective>/<rule id>` (`within`)
—, the refused check, the reason code, the answered assumption without its cited source, the flagged term. Lower case.

**Type:** Value Object

### Lesson kind (LessonKind) · Threshold (THRESHOLDS)

**Definition:** What repeats — question, finding, refusal, correction, assumption, term — and in how many stories it
must repeat before it is a pattern: three for a question, a finding and a refusal, two for the rest.

**Type:** Enum · Concept

### Candidate (Candidate)

**Definition:** A pattern at its threshold, drawn at the finest level that repeats: its evidence (one per story, a
finding's with its outcome), a contrast — the last story of the same target without it —, its places, the recommended
one first (a finding's by its target), and the lesson it was placed as before where it came back.

**Type:** Value Object

**Operations:**
- draw (`Signals.candidates`) — the candidates the signals make against what was decided;
- bound (`Signals.bounded`) — at most `lessons.open` written at a time, the most stories first.

### Lesson · Place (LessonPlace) · Owner (Owner)

**Definition:** A candidate asked of a person, filed in delivery's inbox as a lesson record. A place is where its
correction goes — the description, the instructions, a project rule, a profile check, a criterion, the glossary, the
maintainers' (factory, rule suite, knowledge) — and its owner the skill that writes it; the factory writes none itself.
`not-now` and `never` write nothing.

**Type:** Concept · Enum

### Decided (Decided) · Back after (lessons.backAfter)

**Definition:** What a person said about a candidate — the memory. `never` stops it for good; `not now` lets it back on
more evidence; a place lets it back only when its signal came back in `lessons.backAfter` stories more (default 3) —
the place did not hold it; an open record is not asked again.

**Type:** Value Object

### Issue text (MaintainerIssue)

**Definition:** A lesson answered with a place of the maintainers', as an anonymised text a person sends: the kind of
signal, how many stories, the factory's own words of its key, the pipeline's version — no project, no story, no file.

**Type:** Value Object
