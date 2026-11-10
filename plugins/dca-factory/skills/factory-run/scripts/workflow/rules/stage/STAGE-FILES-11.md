---
id: STAGE-FILES-11
part: told
why: unknown
section: Project decision records — `product/decisions/<name>.md`, beside the epics
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-11

A question that belongs to no story yet — the description, a discovery, an epic not written — asked by a skill the
factory runs for a request (`reference/requests.md`). The shape of a story's record without `story:`: `id:` is the
file's name (`<stamp>-<topic>`), `stage: request`, and `request: <request id>` names the request that waits on it.
The state is read off the file as for every record; the inbox (`--list-decisions`), the status's *waiting* and the
page list it beside the stories' records, and an answer is written as for any other. Answered, the request runs
again; when it has, the factory stamps `## Applied`. A record here that names a story is unreadable — a story's
record lives in its story's folder. Committed with the backlog: a commit of these records alone runs no suite.
