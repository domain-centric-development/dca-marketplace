"""A question the integrate step asked: no stage file cites its answer, so every gate before the integrate step waits
for it and the integrate gate stamps it applied — it never holds the story in a loop of rounds."""

import os
import unittest

from support import project, write
from dca_factory import contract, gate
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles

RECORD = """---
id: S-1-01
story: S-1
stage: integrate
---
# Keep the merged helpers?

## Question
Three main-line lines no longer compile verbatim.

## Options
- a: keep the merge
- b: restore them

## Answer
answer: a
by: the-expert
at: 2026-10-21T18:30:00Z
"""


class IntegrateDecision(unittest.TestCase):

    def checks(self, p, story, gating):
        result = gate.Result()
        gate.check_decisions(result, p.runs, "S-1", p.root, gating, story)
        return {(kind, check) for kind, check, _ in result.entries}, result

    def test_the_gates_before_wait_and_the_integrate_gate_stamps_it(self):
        with project() as p:
            profiles.set_places({})
            story = p.story("S-1")
            record = write(os.path.join(os.path.dirname(story), "decisions", "01.md"), RECORD)
            for gating in ("build", "tidy", "document"):
                kinds, result = self.checks(p, story, gating)
                self.assertNotIn(("fail", "decisions"), kinds, (gating, result.entries))
                self.assertIn(("note", "decisions"), kinds)
            kinds, result = self.checks(p, story, "integrate")
            self.assertIn(("pass", "decisions"), kinds, result.entries)
            with open(record, encoding="utf-8") as handle:
                self.assertIn("## Applied", handle.read())
            with open(story, encoding="utf-8") as handle:
                self.assertIn("(S-1-01)", handle.read())


if __name__ == "__main__":
    unittest.main()
