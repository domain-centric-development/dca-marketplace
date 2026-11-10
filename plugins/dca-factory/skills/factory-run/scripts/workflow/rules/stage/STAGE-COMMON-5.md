---
id: STAGE-COMMON-5
part: told
why: stages looked up answers in dependency sources and package caches instead of the catalog nodes they were given
section: A session the runner started
order: 5
---

# STAGE-COMMON-5

- Where the prompt names a knowledge skill's catalog, open its `index.md` first. Where it names nodes to
  read once before you write code, read them before the first line: they hold what you would otherwise
  look up in a dependency's sources or a package cache, which is never the place.
