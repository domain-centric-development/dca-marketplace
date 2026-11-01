---
id: RUN-STANDING-1
title: A story's state is read from its own files
part: decision
pass: the story is ready, in progress or resumable
fail: the story is stopped: owned files changed, a twin, three rounds, a plan refused, a story conflict
skip: the story is delivered, superseded, unreleased, or claimed by another factory
wait: the story waits for a record, or is published, until merged on the remote
---

# RUN-STANDING-1

**When:** a run is about to start

**Why:** a story's state is read from its own files
