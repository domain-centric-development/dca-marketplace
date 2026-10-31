---
id: STAGE-COMMON-16
part: told
section: One session, several stages
marked: factory-run/reference/stage-common.md
order: 16
---

# STAGE-COMMON-16

- Where the stages are judge and document: apply the stage-judge skill first and write `judge.md` with
  its verdict. Then — only when it says `verdict: pass` — run the document skeleton the prompt names and
  apply the stage-document skill: fill the skeleton's tables, cite paths from its `## Paths` section in
  exactly that form, run the document gate the prompt names and fix exactly what it names, at most
  three attempts. With any other verdict stop after `judge.md`; write no `document.md`. Change no code.
