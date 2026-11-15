---
id: STAGE-COMMON-37
part: told
why: unknown
section: A picture of what you built
order: 37
---

# STAGE-COMMON-37

Pictures reach the story's place through end-user tests: with `screenshots:` the runner copies each test run's pictures
into the run folder (`shots/`). A picture worth seeing is one a test takes — on failure, or of a page a person wants
to see, by the project's screenshot helper, named for what it shows. Never a page with a person's data. A picture a
question rests on goes beside the record (`<nn>/<name>.png`, named in its text). A mockup only where a person asked:
one static page `<nn>/<name>.html` beside the record — HTML and inline CSS, no script, nothing loaded — named as
`![a: what it shows](<nn>/<name>.html)`.
