"""Which hand-overs belong to a story's current pass, from the journal's order alone."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.journal_marks import JournalMarks, MarkKind, MarkName, Seq
from dca_factory.delivery.domain.model.stage import StageName
from dca_factory.delivery.domain.service.current_pass import CurrentPass

ORDER = [StageName(s) for s in ("plan", "test", "build", "tidy")]


def marks(**seqs):
    found = {}
    for key, seq in seqs.items():
        kind, name = key.split("_", 1)
        found[(MarkKind(kind), MarkName(name.replace("_", ".")))] = Seq(seq)
    return JournalMarks(found)


class Pass(unittest.TestCase):

    def test_a_stage_run_again_makes_every_later_file_an_earlier_passs(self):
        journal = marks(wrote_plan_md=1, wrote_tests_md=2, wrote_build_md=3, wrote_tidy_md=4)
        everything = set(ORDER)
        self.assertEqual(CurrentPass.holding(journal, ORDER, everything), tuple(ORDER))
        again = marks(wrote_plan_md=1, wrote_tests_md=5, wrote_build_md=3, wrote_tidy_md=4)
        self.assertEqual(CurrentPass.holding(again, ORDER, everything), tuple(ORDER[:2]))

    def test_a_later_pass_of_its_own_gate_holds_an_older_file(self):
        journal = marks(wrote_plan_md=1, wrote_tests_md=5, wrote_build_md=3, pass_build=6)
        self.assertEqual(CurrentPass.holding(journal, ORDER, set(ORDER[:3])), tuple(ORDER[:3]))

    def test_a_file_marked_an_earlier_passs_does_not_hold(self):
        journal = marks(wrote_plan_md=1, wrote_tests_md=2, outdated_tests_md=3)
        self.assertIsNone(CurrentPass.written_at(journal, StageName("test")))
        self.assertEqual(CurrentPass.holding(journal, ORDER, set(ORDER[:2])), (StageName("plan"),))


if __name__ == "__main__":
    unittest.main()
