"""A judge row's origin from the story's diff, its place against the round before, and what a verdict means once its
rows are weighed (WP-208)."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.files.diff_lines import added_lines, origin_of
from dca_factory.delivery.adapter.outgoing.files.judge_rows_files import judge_rows_of
from dca_factory.delivery.domain.model.judge_rows import (
    JudgeRow, Origin, RoundPlace, pass_contradicted, weighed)
from dca_factory.delivery.domain.model.story_state import Detail, Judged

DIFF = ("diff --git a/src/Thing.java b/src/Thing.java\n--- a/src/Thing.java\n+++ b/src/Thing.java\n"
        "@@ -1,3 +1,4 @@\n class Thing {\n-  int x;\n+  int a;\n+  int b;\n }\n")
JUDGE = ("## Verdict\nverdict: changes-requested\n\n## Confirmed defects\n| Perspective | File:line | Severity | Defect | Fix |\n"
         "|---|---|---|---|---|\n| ddd | `src/Thing.java:{line}` | major | d | f |\n")


def row(severity, origin, since=RoundPlace.FIRST):
    return JudgeRow(Detail("ddd"), Detail("src/Thing.java:9"), Detail(severity), origin, since)


class OriginTest(unittest.TestCase):

    def test_the_new_sides_added_lines(self):
        self.assertEqual({"src/Thing.java": {2, 3}}, added_lines(DIFF))

    def test_a_line_the_story_added_is_introduced(self):
        self.assertIs(Origin.INTRODUCED, origin_of("`src/Thing.java:3`", added_lines(DIFF)))

    def test_an_untouched_line_or_file_is_pre_existing(self):
        self.assertIs(Origin.PRE_EXISTING, origin_of("src/Thing.java:9", added_lines(DIFF)))
        self.assertIs(Origin.PRE_EXISTING, origin_of("src/Other.java:2", added_lines(DIFF)))

    def test_a_tail_of_the_path_names_the_same_file(self):
        self.assertIs(Origin.INTRODUCED, origin_of("Thing.java:2", added_lines(DIFF)))

    def test_no_line_is_unresolved(self):
        self.assertIs(Origin.UNRESOLVED, origin_of("the whole package", added_lines(DIFF)))


class WeighedTest(unittest.TestCase):

    def test_changes_requested_on_pre_existing_code_alone_is_a_pass(self):
        self.assertIs(Judged.PASS, weighed(Judged.AGAIN, [row("major", Origin.PRE_EXISTING), row("minor", Origin.INTRODUCED)]))

    def test_an_introduced_major_still_sends_the_story_back(self):
        self.assertIs(Judged.AGAIN, weighed(Judged.AGAIN, [row("major", Origin.INTRODUCED), row("blocker", Origin.PRE_EXISTING)]))

    def test_a_new_finding_on_untouched_lines_from_round_two_blocks_nothing(self):
        self.assertIs(Judged.PASS, weighed(Judged.AGAIN, [row("major", Origin.INTRODUCED, RoundPlace.UNTOUCHED)]))
        self.assertIs(Judged.AGAIN, weighed(Judged.AGAIN, [row("major", Origin.INTRODUCED, RoundPlace.REPEATED)]))

    def test_changes_requested_with_minors_alone_stands_as_written(self):
        self.assertIs(Judged.AGAIN, weighed(Judged.AGAIN, [row("minor", Origin.INTRODUCED)]))

    def test_a_pass_over_an_introduced_major_is_contradicted(self):
        self.assertEqual(1, len(pass_contradicted(Judged.PASS, [row("major", Origin.INTRODUCED), row("major", Origin.PRE_EXISTING)])))


class RoundPlaceTest(unittest.TestCase):

    def test_first_round_without_a_previous_verdict(self):
        self.assertIs(RoundPlace.FIRST, judge_rows_of(JUDGE.format(line=3), DIFF)[0].since)

    def test_a_place_the_previous_verdict_named_is_repeated(self):
        found = judge_rows_of(JUDGE.format(line=3), DIFF, JUDGE.format(line=3), DIFF)
        self.assertIs(RoundPlace.REPEATED, found[0].since)

    def test_a_line_changed_since_the_previous_diff(self):
        later = DIFF.replace("+  int b;", "+  int c;")
        self.assertIs(RoundPlace.CHANGED_SINCE, judge_rows_of(JUDGE.format(line=3), later, JUDGE.format(line=2), DIFF)[0].since)

    def test_a_line_the_round_left_as_it_was_is_untouched(self):
        self.assertIs(RoundPlace.UNTOUCHED, judge_rows_of(JUDGE.format(line=3), DIFF, JUDGE.format(line=2), DIFF)[0].since)


if __name__ == "__main__":
    unittest.main()
