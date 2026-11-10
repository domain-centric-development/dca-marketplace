"""Signals become candidates — counted, never guessed (WP-185): below a kind's threshold nothing, at it one candidate
with its evidence; `never` stops it, `not now` lets it come back on more evidence."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.domain.model.lesson import (Decided, Evidence, LessonId, LessonKind, LessonPlace, Signal,
                                                      SignalKey, Signals, THRESHOLDS)
from dca_factory.delivery.domain.model.story import StoryId
from dca_factory.delivery.domain.model.story_words import Count, Detail

KEYS = {LessonKind.QUESTION: "accounts/test-level", LessonKind.FINDING: "ddd/domain-concept",
        LessonKind.CORRECTION: "missing-case", LessonKind.ASSUMPTION: "prices are gross → yes",
        LessonKind.TERM: "entry"}


def drawn(items, decided=()):
    return Signals(tuple(items)).candidates(decided)


def signals(kind, stories, key=None):
    return [Signal(kind, SignalKey(key or KEYS[kind]), Evidence(StoryId(f"s-{n}"), Detail(f"s-{n}-01")))
            for n in range(1, stories + 1)]


class LessonCandidatesTest(unittest.TestCase):

    def test_each_kind_below_its_threshold_writes_nothing(self):
        for kind, threshold in THRESHOLDS.items():
            with self.subTest(kind=kind):
                self.assertEqual((), drawn(signals(kind, threshold.value - 1), ()))

    def test_each_kind_at_its_threshold_is_one_candidate_with_its_evidence(self):
        for kind, threshold in THRESHOLDS.items():
            with self.subTest(kind=kind):
                found = drawn(signals(kind, threshold.value), ())
                self.assertEqual(1, len(found))
                self.assertEqual([f"s-{n}" for n in range(1, threshold.value + 1)],
                                 [e.story.value for e in found[0].evidence])
                self.assertEqual((LessonPlace.NOT_NOW, LessonPlace.NEVER), found[0].places[-2:])

    def test_the_thresholds_are_counts_a_question_and_a_finding_three_the_rest_two(self):
        self.assertEqual({"question": 3, "finding": 3, "correction": 2, "assumption": 2, "term": 2},
                         {k.value: c.value for k, c in THRESHOLDS.items()})

    def test_a_story_that_shows_a_signal_twice_counts_once(self):
        twice = signals(LessonKind.QUESTION, 2) + signals(LessonKind.QUESTION, 2)
        self.assertEqual((), drawn(twice, ()))

    def test_a_question_in_another_context_or_of_another_kind_is_another_pattern(self):
        mixed = (signals(LessonKind.QUESTION, 2) + signals(LessonKind.QUESTION, 1, "billing/test-level"))
        self.assertEqual((), drawn(mixed, ()))

    def test_never_stops_the_same_candidate_and_not_now_lets_it_back_on_more_evidence(self):
        key = SignalKey(KEYS[LessonKind.QUESTION])
        never = Decided(LessonKind.QUESTION, key, LessonPlace.NEVER, Count(3))
        later = Decided(LessonKind.QUESTION, key, LessonPlace.NOT_NOW, Count(3))
        placed = Decided(LessonKind.QUESTION, key, LessonPlace.DESCRIPTION, Count(3))
        waiting = Decided(LessonKind.QUESTION, key, None, Count(3))
        self.assertEqual((), drawn(signals(LessonKind.QUESTION, 9), (never,)))
        self.assertEqual((), drawn(signals(LessonKind.QUESTION, 3), (later,)))
        self.assertEqual(1, len(drawn(signals(LessonKind.QUESTION, 4), (later,))))
        self.assertEqual((), drawn(signals(LessonKind.QUESTION, 9), (placed,)))
        self.assertEqual((), drawn(signals(LessonKind.QUESTION, 9), (waiting,)))

    def test_a_candidate_has_one_id_from_its_kind_and_key(self):
        self.assertEqual("lesson-question-accounts-test-level",
                         LessonId.of(LessonKind.QUESTION, SignalKey(" Accounts/Test-Level ")).value)

    def test_an_option_line_names_its_place_and_its_owner(self):
        self.assertIs(LessonPlace.NEVER, LessonPlace.named(Detail("`never` — the same candidate does not come back")))
        self.assertIs(LessonPlace.DESCRIPTION, LessonPlace.named(Detail("description — a statement")))
        self.assertIsNone(LessonPlace.named(Detail("something else")))
        self.assertTrue(LessonPlace.RULE_LIBRARY.goes_up)
        self.assertEqual("describe", LessonPlace.DESCRIPTION.owner.value)


class LessonSignalReadingTest(unittest.TestCase):
    """What the files make a signal of: a finding by the rule it names, else its domain code; a story id is no rule."""

    def test_a_finding_is_counted_under_its_rule_else_its_code_and_a_flagged_term_on_its_own(self):
        from dca_factory.delivery.adapter.outgoing.files.lesson_signal_files import finding_signals
        story = StoryId("s-1")

        def row(defect):
            return ("2", "hexagonal", "src/A.java:3", "minor", defect, "fix", "open", "")
        self.assertEqual(["hexagonal/dca-hex-014"],
                         [s.key.value for s in finding_signals(story, row("breaks DCA-HEX-014 as US-3 asked"))])
        self.assertEqual([], finding_signals(story, row("stale comment, see US-3")))
        found = finding_signals(story, row("domain-term: `Entry` is called `Item` here"))
        self.assertEqual([("finding", "hexagonal/domain-term"), ("term", "entry")],
                         [(s.kind.value, s.key.value) for s in found])
        self.assertEqual("s-1#2", found[0].evidence.source.value)
