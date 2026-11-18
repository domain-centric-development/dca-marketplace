"""Signals become candidates — counted, never guessed (WP-185): below a kind's threshold nothing, at it one candidate
with its evidence; `never` stops it, `not now` lets it come back on more evidence."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.learning.domain.model.lesson import (Decided, Evidence, LessonId, LessonKind, LessonPlace, Signal,
                                                      SignalKey, Signals, THRESHOLDS)
from dca_factory.learning.domain.model.words import Count, Detail, StoryId

SIGNALS = "dca_factory.learning.adapter.outgoing.delivery.delivery_signals"


def published(row):
    """A findings row as delivery's api publishes it."""
    n, perspective, _where, _severity, defect, _fix, _status, _plain, _origin, outcome, *kind = row
    target, kind_, qualifier = kind if kind else ("", "", "")
    return dict(n=n, perspective=perspective, defect=defect, outcome=outcome, target=target, type=kind_,
                qualifier=qualifier)

KEYS = {LessonKind.QUESTION: "accounts/test-level", LessonKind.FINDING: "ddd/domain-concept",
        LessonKind.CORRECTION: "missing-case", LessonKind.ASSUMPTION: "prices are gross → yes",
        LessonKind.TERM: "entry", LessonKind.REFUSAL: "tests-kept"}


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
        self.assertEqual({"question": 3, "finding": 3, "correction": 2, "assumption": 2, "term": 2, "refusal": 3},
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
        self.assertEqual((), drawn(signals(LessonKind.QUESTION, 5), (placed,)))
        back = drawn(signals(LessonKind.QUESTION, 6), (placed,))           # placed, and back in three stories more
        self.assertEqual(1, len(back))
        self.assertIs(LessonPlace.DESCRIPTION, back[0].placed.place)
        self.assertEqual((), drawn(signals(LessonKind.QUESTION, 9), (waiting,)))

    def test_a_finding_is_drawn_at_the_finest_level_that_repeats(self):
        def classed(story, fine, coarse):
            evidence = Evidence(StoryId(story), Detail(f"{story}#1"))
            return [Signal(LessonKind.FINDING, SignalKey(coarse), evidence),
                    Signal(LessonKind.FINDING, SignalKey(fine), evidence, SignalKey(coarse))]
        same = sum((classed(f"s-{n}", "clean-code/test/duplication/extraneous", "test/duplication") for n in (1, 2, 3)), [])
        found = drawn(same)
        self.assertEqual(["clean-code/test/duplication/extraneous"], [c.key.value for c in found])
        self.assertIs(LessonPlace.INSTRUCTIONS, found[0].recommended)          # the target test proposes the place
        spread = (classed("s-1", "clean-code/test/duplication/extraneous", "test/duplication")
                  + classed("s-2", "ddd/test/duplication/extraneous", "test/duplication")
                  + classed("s-3", "clean-code/test/duplication/incorrect", "test/duplication"))
        self.assertEqual(["test/duplication"], [c.key.value for c in drawn(spread)])  # no finer key repeats

    def test_a_finding_candidate_names_a_story_of_its_target_without_it(self):
        def one(story, key):
            return Signal(LessonKind.FINDING, SignalKey(key), Evidence(StoryId(story), Detail(f"{story}#1")))
        items = [one(f"s-{n}", "test/duplication") for n in (1, 2, 3)] + [one("s-4", "test/checking"),
                                                                           one("s-5", "code/naming")]
        self.assertEqual("s-4", drawn(items)[0].contrast.value)

    def test_at_most_the_open_lessons_are_written_the_most_stories_first(self):
        many = drawn(signals(LessonKind.QUESTION, 5) + signals(LessonKind.FINDING, 3)
                     + signals(LessonKind.TERM, 4))
        kept = Signals(()).bounded(many, Count(3), Count(5))
        self.assertEqual(["question", "term"], [c.kind.value for c in kept])
        self.assertEqual((), Signals(()).bounded(many, Count(5), Count(5)))

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
    """What the files make a signal of: a finding by its class or the rule it names, never its domain code alone; a
    story id is no rule."""

    def test_a_finding_is_counted_under_its_rule_never_its_code_alone_and_a_flagged_term_on_its_own(self):
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import finding_signals
        story = StoryId("s-1")

        def row(defect):
            return ("2", "hexagonal", "src/A.java:3", "minor", defect, "fix", "open", "", "introduced", "")
        self.assertEqual(["hexagonal/dca-hex-014"],
                         [s.key.value for s in finding_signals(story, published(row("breaks DCA-HEX-014 as US-3 asked")))])
        self.assertEqual([], finding_signals(story, published(row("stale comment, see US-3"))))
        found = finding_signals(story, published(row("domain-term: `Entry` is called `Item` here")))
        self.assertEqual([("term", "entry")], [(s.kind.value, s.key.value) for s in found])   # a code alone: no key
        self.assertEqual("s-1#2", found[0].evidence.source.value)

    def test_a_finding_is_read_from_a_findings_file_in_todays_shape(self):
        import os
        import tempfile
        from dca_factory.delivery.adapter.outgoing.files.findings_files import findings_rows
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import finding_signals
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "findings.md")
            with open(path, "w", encoding="utf-8") as out:
                out.write("| 1 | ddd | src/A.java:3 | minor | introduced | | plain words "
                          "| breaks DCA-HEX-014 | fix it | open |\n")
            rows = findings_rows(path)
        self.assertEqual(13, len(rows[0]))
        self.assertEqual(["ddd/dca-hex-014"], [s.key.value for s in finding_signals(StoryId("s-1"), published(rows[0]))])

    def test_a_findings_class_counts_on_two_levels_and_a_rule_within_it(self):
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import finding_signals
        row = ("2", "clean-code", "src/A.java:3", "minor", "duplicate fixture, breaks DCA-HEX-014", "fix", "open", "",
               "introduced", "fixed", "test", "duplication", "extraneous")
        found = finding_signals(StoryId("s-1"), published(row))
        self.assertEqual([("test/duplication", None),
                          ("clean-code/test/duplication/extraneous", "test/duplication"),
                          ("clean-code/dca-hex-014", "clean-code/test/duplication/extraneous")],
                         [(s.key.value, s.within.value if s.within else None) for s in found])
        self.assertEqual("s-1#2 (fixed)", found[0].evidence.source.value)
        unlisted = finding_signals(StoryId("s-1"), published(row[:10] + ("", "", "")))   # the api publishes no class
        self.assertEqual([("clean-code/dca-hex-014", None)],                 # outside delivery's lists
                         [(s.key.value, s.within.value if s.within else None) for s in unlisted])

    def test_a_check_the_gate_refused_counts_once_per_story(self):
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import refusal_signals
        refused = [dict(stage="test", check="tests-kept"), dict(stage="test", check="clauses"),
                   dict(stage="build", check="tests-kept")]
        self.assertEqual(["tests-kept", "clauses"], [s.key.value for s in refusal_signals(StoryId("s-1"), refused)])

    def test_a_release_and_the_plans_adoption_are_no_answered_assumption(self):
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import assumption_signals
        from dca_factory.delivery.domain.model.story import Assumption
        said = [s.key.value for s in assumption_signals(
            StoryId("s-1"), ["leeren (clear) — every task leaves the list (product/domain.md)."])]
        self.assertEqual(["leeren (clear) — every task leaves the list"], said)   # the source it cites aside
        self.assertTrue(Assumption("- answered: the story is released for building (request R-9, Ann, "
                                   "2026-11-17T14:46:59Z).").marks_process)       # delivery's api leaves these out
        self.assertTrue(Assumption("- answered: every scenario holds on today's code — the plan adopted the story "
                                   "(plan-adopt)").marks_process)
        self.assertFalse(Assumption("- answered: leeren (clear)").marks_process)


class LessonRecordTest(unittest.TestCase):
    """A lesson is a decision record of its own kind: the factory writes `not now` and `never` from a press; a place
    goes through the decisions skill, which has the owning skill write it. Its answer changes no story."""

    def lesson(self):
        from dca_factory.delivery.domain.model.story_words import Detail
        from dca_factory.delivery.domain.model.decision_record import (
            ANSWER_FIELDS, Asker, DecisionRecord, DecisionState, OptionKey, OptionLine, RecordContent, RecordId,
            RecordKind)
        lines = [("a", "description — a statement"), ("f", "not-now — asked again"), ("g", "never — not again")]
        return DecisionRecord.restore(
            RecordId("lesson-question-x"), RecordKind.LESSON, Asker.STAGE, DecisionState.OPEN,
            [OptionKey(k) for k, _ in lines],
            content=RecordContent(Detail("The same kind of question in 3 stories"), None, Detail(""), Detail(""),
                                  ANSWER_FIELDS, tuple(OptionLine(OptionKey(k), Detail(t)) for k, t in lines)))

    def test_not_now_and_never_settle_alone_a_place_needs_its_skill(self):
        from dca_factory.delivery.domain.model.decision_record import OptionKey
        record = self.lesson()
        self.assertTrue(record.settles_alone(OptionKey("g")))
        self.assertTrue(record.settles_alone(OptionKey("f")))
        self.assertFalse(record.settles_alone(OptionKey("a")))

    def test_an_answered_lesson_backs_no_change_of_a_story_and_says_so_in_its_event(self):
        from dca_factory.delivery.domain.model.decision_record import LessonAnswered, OptionKey
        from dca_factory.delivery.domain.model.moment import Moment
        from dca_factory.delivery.domain.model.person import Person
        record = self.lesson()
        record.choose(OptionKey("g"), Person("the-lead"), Moment("2026-11-10T10:00:00Z"))
        self.assertFalse(record.backs_change())
        self.assertEqual([LessonAnswered], [type(e) for e in record.domain_events()])


class HonestCountTest(unittest.TestCase):
    """WP-224: one decision copied into several stories is one answer; a question about the pipeline is the factory's;
    a finding's place follows its class; a lesson no longer drawn is withdrawn."""

    def test_one_source_in_several_stories_is_one_answer_two_sources_a_candidate(self):
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import assumption_signals
        copied = [s for n in range(1, 5) for s in assumption_signals(
            StoryId(f"s-{n}"), ["every refusal names its field (the person, WP-7 decision 4)"])]
        self.assertEqual((), drawn(copied))
        twice = copied + assumption_signals(StoryId("s-9"), ["every refusal names its field (s-9-01)"])
        found = drawn(twice)
        self.assertEqual(1, len(found))
        self.assertEqual("every refusal names its field", found[0].said.value)
        self.assertEqual("answered in s-9-01", found[-1].evidence[-1].source.value)

    def test_the_questions_tag_names_the_description_file(self):
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import assumption_signals
        found = assumption_signals(StoryId("s-1"), ["prices are gross (s-1-01)"], {"s-1-01": "failure"})
        self.assertEqual("tech.md", found[0].file.value)
        self.assertIsNone(assumption_signals(StoryId("s-1"), ["prices are gross"])[0].file)

    def test_a_wrapped_assumption_is_one_line_and_a_pipeline_answer_is_left_out(self):
        from dca_factory.delivery.api.learning import assumption_items, cites
        self.assertEqual(["- answered: every refusal names its field (WP-7 decision 4)", "- answered: b (x)"],
                         assumption_items(["", "- answered: every refusal names", "  its field (WP-7 decision 4)",
                                           "- answered: b (x)"]))
        self.assertTrue(cites("run the stage again as it is (s-1-02).", {"s-1-02"}))
        self.assertFalse(cites("run the stage again as it is (s-1-021)", {"s-1-02"}))
        self.assertFalse(cites("prices are gross (WP-7 decision 4)", {"s-1-02"}))

    def test_a_question_about_the_pipeline_goes_to_the_factory_alone(self):
        found = drawn(signals(LessonKind.QUESTION, 3, key="accounts/pipeline"))
        self.assertEqual((LessonPlace.FACTORY, LessonPlace.NOT_NOW, LessonPlace.NEVER), found[0].places)

    def test_an_assumption_offers_the_description_and_the_factory(self):
        found = drawn(signals(LessonKind.ASSUMPTION, 2))
        self.assertEqual((LessonPlace.DESCRIPTION, LessonPlace.FACTORY, LessonPlace.NOT_NOW, LessonPlace.NEVER),
                         found[0].places)

    def test_a_findings_place_follows_its_class(self):
        from dca_factory.learning.domain.model.lesson import places_of
        def first(key):
            return places_of(LessonKind.FINDING, SignalKey(key))
        self.assertEqual(LessonPlace.GLOSSARY, first("ddd/code/domain-term/incorrect")[0])
        self.assertEqual(LessonPlace.CRITERION, first("story/traceability")[0])
        self.assertEqual(LessonPlace.INSTRUCTIONS, first("clean-code/code/comment/incorrect")[0])
        self.assertEqual((LessonPlace.PROJECT_RULE, LessonPlace.RULE_LIBRARY, LessonPlace.FACTORY),
                         first("clean-code/code/dead-code/extraneous")[:3])
        self.assertNotIn(LessonPlace.RULE_LIBRARY, first("clean-code/code/comment/incorrect"))

    def test_a_waiting_lesson_no_longer_drawn_is_stale_an_answered_one_never(self):
        key = SignalKey(KEYS[LessonKind.ASSUMPTION])
        waiting = Decided(LessonKind.ASSUMPTION, key, None, Count(2), Detail("lesson-a"))
        answered = Decided(LessonKind.ASSUMPTION, SignalKey("other"), LessonPlace.NEVER, Count(2), Detail("lesson-b"))
        none = Signals(())
        self.assertEqual((waiting,), none.stale([waiting, answered]))
        self.assertEqual((), Signals(tuple(signals(LessonKind.ASSUMPTION, 2))).stale([waiting]))

    def test_the_record_shows_the_draft_and_names_the_file(self):
        from dca_factory.learning.adapter.outgoing.delivery.delivery_lessons import lesson_text
        from dca_factory.learning.adapter.outgoing.delivery.delivery_signals import assumption_signals
        from dca_factory.learning.domain.model.words import Moment, RecordId
        found = drawn([s for n, src in ((1, "s-1-01"), (2, "s-2-01")) for s in assumption_signals(
            StoryId(f"s-{n}"), [f"Prices are gross ({src})"], {src: "failure"})])
        text = lesson_text(RecordId(found[0].id.value), found[0], Moment("2026-11-18T10:00:00Z"), {})
        self.assertIn("## Draft\n> Prices are gross", text)
        self.assertIn("- a: description — keep the draft below once in `product/tech.md`", text)
        self.assertIn("- b: factory —", text)
