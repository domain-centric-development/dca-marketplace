---
id: STAGE-BUILD-4A
part: told
why: comments in touched files kept describing the one case or the mechanism the change had replaced
stages:
- build
section: Do
order: 6
---

# STAGE-BUILD-4A

4a. **A comment the change made wrong is rewritten in this story.** A comment or doc comment in a file
   you touch that your change made wrong or too narrow — it names the one case where there are two now,
   a mechanism the code no longer uses — says what holds after the change. A comment says what holds
   in this file, not what a source the reader cannot see says (the plan, the story, another document).
