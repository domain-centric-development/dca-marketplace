"""The cli's views as read models: what the stories spent, what a stage's process does, the open findings."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.cost.show_spent import ShowSpentQuery, ShowSpentUseCase
from dca_factory.delivery.application.shared.stage_outputs import Output
from dca_factory.delivery.application.shared.usage_ledger import Spent
from dca_factory.delivery.application.status.follow_output import FollowOutputQuery, FollowOutputUseCase
from dca_factory.delivery.application.status.list_findings import ListFindingsQuery, ListFindingsUseCase
from dca_factory.delivery.application.status.show_stage_outputs import ShowStageOutputsQuery, ShowStageOutputsUseCase


class Ledger:
    def stories(self):
        return ["S-1", "S-2"]

    def spent(self, story):
        return Spent(5, 1000) if story == "S-1" else None


class Outputs:
    def __init__(self):
        self.texts = {"a.out": "one\ntwo\n", "b.out": "three\nfour\nfive\n"}
        self.latest = Output("S-1", "builder", "a.out")

    def outputs(self, story, process):
        return [Output(story, "builder", "a.out"), Output(story, "verifier", "b.out")]

    def newest(self, story, process, request):
        return self.latest

    def read(self, output, offset):
        text = self.texts[output.path]
        return text[offset:], len(text)

    def lines(self, text):
        return [line for line in text.split("\n") if line], "five" in text


class Facts:
    def finding_records(self):
        return [dict(owner="S-1", where="a.py:3", severity="minor", defect="d", plain="p", perspective="ddd", fix="f")]

    def findings_name(self):
        return "findings.md"


class ViewsTest(unittest.TestCase):

    def test_what_the_stories_spent_and_the_total(self):
        view = ShowSpentUseCase(Ledger()).execute(ShowSpentQuery())
        self.assertEqual({"S-1": Spent(5, 1000), "S-2": None}, dict(view.by_story))
        self.assertEqual(1000, view.tokens)
        self.assertEqual(0, ShowSpentUseCase(Ledger()).execute(ShowSpentQuery(("S-2",))).tokens)

    def test_every_output_of_a_story_or_the_newest_with_its_last_lines(self):
        shown = ShowStageOutputsUseCase(Outputs()).execute(ShowStageOutputsQuery("S-1", every=True))
        self.assertEqual([("builder", True), ("verifier", False)], [(e["stage"], e["running"]) for e in shown])
        newest = ShowStageOutputsUseCase(Outputs()).execute(ShowStageOutputsQuery("S-1", lines=1))
        self.assertEqual([dict(story="S-1", stage="builder", file="a.out", running=True, lines=["two"])], newest)

    def test_following_reads_what_was_added_and_a_new_output_takes_over(self):
        outputs = Outputs()
        follow = FollowOutputUseCase(outputs)
        first = follow.execute(FollowOutputQuery("S-1"))
        self.assertEqual((True, ["one", "two"]), (first.started, first.lines))
        outputs.texts["a.out"] += "half"
        again = follow.execute(FollowOutputQuery("S-1", current=first.current, offset=first.offset))
        self.assertEqual((False, [], "half"), (again.started, again.lines, again.pending))
        outputs.latest = Output("S-1", "verifier", "b.out")
        moved = follow.execute(FollowOutputQuery("S-1", current=again.current, offset=again.offset,
                                                 pending=again.pending))
        self.assertEqual((True, ["three", "four", "five"], ""), (moved.started, moved.lines, moved.pending))

    def test_the_open_findings_with_the_file_they_are_kept_in(self):
        found = ListFindingsUseCase(Facts()).execute(ListFindingsQuery())
        self.assertEqual("findings.md", found["name"])
        self.assertEqual([dict(story="S-1", where="a.py:3", severity="minor", defect="d", plain="p")], found["rows"])


if __name__ == "__main__":
    unittest.main()
