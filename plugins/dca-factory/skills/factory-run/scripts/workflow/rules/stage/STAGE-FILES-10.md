---
id: STAGE-FILES-10
part: told
section: Decision records — `<story>/decisions/<nn>.md`, in the story's folder
see: factory-run/reference/file-contracts.md
order: 2
---

# STAGE-FILES-10

The question a stage may not answer, kept as a file of its own so the answer has a place to land
and a second session — or the same one tomorrow, or another tool — finds it without any
transcript. It lives in the folder of the story it belongs to, `product/epics/<epic>/<story>/decisions/<nn>.md`
(an acceptance as `accept-<n>.md`), because a human's answer is human-written state and belongs in
the people's place; committed with the story. The record's `id:` is `<story>-<nn>` (`<story>-accept-<n>`),
which is how stages, the gate and the inbox cite it, and the file is found by that name: a record
whose `id:` or `story:` does not match its place is refused. Markdown with front matter, from
`templates/decision.md.tmpl`:
