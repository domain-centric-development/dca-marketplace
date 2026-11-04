---
id: STAGE-COMMON-37
part: told
section: A picture of what you built
order: 37
---

# STAGE-COMMON-37

A picture of the product reaches the story's place through the end-user tests: where the stack profile names
`screenshots:`, the folder those tests save their pictures in, the runner copies what a test run took into the
story's run folder (`shots/`) after every test command the gate runs, and the story's place shows it under its
pipeline. So a picture worth seeing is one a test takes — on a failure, as the project's base test already may, and
on a page a person would want to see, by the project's own screenshot helper, its name saying what it shows. Never
one of a page with a person's data in it. A picture a question rests on goes beside the record instead
(`<nn>/<name>.png`, named in its text). A mockup is made only where a person asked for one: one static page beside the
record, `<nn>/<name>.html` — HTML and inline CSS, no script, nothing loaded from elsewhere —, named in the text as a
picture is, `![a: what it shows](<nn>/<name>.html)`.
