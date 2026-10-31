---
id: STAGE-DOCUMENT-4
part: told
stages:
- document
section: Do
marked: stage-document/SKILL.md
---

# STAGE-DOCUMENT-4

4. **Write only what you can verify.** Every path, file, class, method and command you put in a
   document must exist — check it, do not remember it. A documented path that does not resolve is
   worse than no documentation: it survives, gets cited, and sends the next reader nowhere.
   Write every path **as it resolves from the project root**, in your file and in the document you
   write — `product/spec/billing/glossary.md`, not a shorthand such as `billing/glossary.md`. A shorthand a reader has to complete
   is not a path: it reads like one, it cannot be opened, and it is indistinguishable from a typo.
   Add the line or the section separately (`file.md:149`, `Book.cs:28-31`) — the location is
   allowed and is not part of the file name.
