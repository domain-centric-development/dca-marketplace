---
id: RUN-REQUEST-4
title: A request changes and commits only what a person owns
part: decision
pass: the request is settled without a tool where it can be (accept, release, an option), else its skill runs headless — the paths it wrote (backlog, description, docs) are committed if they were clean before
fail: the request no longer holds, the tool failed, or the commit was refused
ask: the skill opened a record — the request waits (exit 3)
---

# RUN-REQUEST-4

**When:** a request is worked

**Why:** a request changes only what a person owns, and commits only that
