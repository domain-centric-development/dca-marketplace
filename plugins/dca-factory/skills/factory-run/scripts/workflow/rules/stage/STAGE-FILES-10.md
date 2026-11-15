---
id: STAGE-FILES-10
part: told
why: a question lived only in a transcript, so its answer had no place to land and another session could not find it
section: Decision records — `<story>/decisions/<nn>.md`, in the story's folder
see: factory-run/reference/file-contracts.md
order: 2
---

# STAGE-FILES-10

A question a stage may not answer is a file of its own, so the answer has a place and another session or tool finds it
without a transcript: `product/epics/<epic>/<story>/decisions/<nn>.md` (an acceptance `accept-<n>.md`), committed with the
story. `id:` is `<story>-<nn>` (`<story>-accept-<n>`) — how stages, gate and inbox cite it; a record whose `id:` or
`story:` does not match its place is refused. Markdown with front matter, from `templates/decision.md.tmpl`:
