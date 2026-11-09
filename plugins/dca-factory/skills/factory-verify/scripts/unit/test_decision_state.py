"""A decision record's state, read off its sections: applied, open, a draft until the answer carries every line —
and where an acceptance stands from its latest record."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.decision_record import AnswerField, DecisionState, Given, RecordKind, Section
from dca_factory.delivery.domain.model.story_state import AcceptanceVerdict
from dca_factory.delivery.domain.model.acceptance import acceptance_verdict, changed_story_verdict
from dca_factory.delivery.domain.model.decision_record import Asker, DecisionRecord, RecordContent, RecordId
from dca_factory.delivery.domain.model.story_words import Detail

FULL = {AnswerField("answer"), AnswerField("by"), AnswerField("at")}


class State(unittest.TestCase):

    def test_applied_wins_over_everything_else(self):
        self.assertIs(DecisionState.of({Section.APPLIED}, set()), DecisionState.APPLIED)

    def test_without_an_answer_section_the_record_is_open(self):
        self.assertIs(DecisionState.of(set(), FULL), DecisionState.OPEN)

    def test_an_answer_lacking_a_line_is_a_draft(self):
        self.assertIs(DecisionState.of({Section.ANSWER}, FULL - {AnswerField("by")}), DecisionState.DRAFT)
        self.assertIs(DecisionState.of({Section.ANSWER}, FULL), DecisionState.ANSWERED)


class Acceptance(unittest.TestCase):

    def test_none_asks_one_waiting_is_open_and_a_changed_story_is_asked_again(self):
        self.assertIs(acceptance_verdict(None), AcceptanceVerdict.ASK)
        self.assertIs(acceptance_verdict(record(DecisionState.DRAFT, "accepted")), AcceptanceVerdict.OPEN)
        self.assertIs(changed_story_verdict(record(DecisionState.ANSWERED, "accepted")), AcceptanceVerdict.ASK)
        self.assertIs(changed_story_verdict(record(DecisionState.DRAFT, "accepted")), AcceptanceVerdict.OPEN)
        self.assertIs(changed_story_verdict(None), AcceptanceVerdict.ASK)

    def test_an_answer_beginning_accept_accepts_any_other_asks_for_a_correction(self):
        self.assertIs(acceptance_verdict(record(DecisionState.APPLIED, " Accepted ")),
                      AcceptanceVerdict.ACCEPTED)
        self.assertIs(acceptance_verdict(record(DecisionState.ANSWERED, "the button is red")),
                      AcceptanceVerdict.CORRECTION)

    def test_a_correction_and_an_answered_question_back_a_change_an_acceptance_that_accepted_does_not(self):
        answered, waiting = DecisionState.ANSWERED, DecisionState.OPEN
        self.assertTrue(record(answered, "the label is wrong").corrects())
        self.assertFalse(record(answered, "accepted").corrects())
        self.assertFalse(record(waiting, "").corrects())
        self.assertTrue(record(answered, "b", RecordKind.QUESTION).backs_change())
        self.assertFalse(record(waiting, "", RecordKind.QUESTION).backs_change())
        self.assertFalse(record(answered, "accepted").backs_change())


def record(state, given, kind=RecordKind.ACCEPTANCE):
    """A record as the files keep it: its state, its answer as written."""
    return DecisionRecord.restore(RecordId("S-1-01"), kind, Asker.STAGE, state,
                                  content=RecordContent(Detail("q"), None, Detail(given), Detail("jane"), ()))


if __name__ == "__main__":
    unittest.main()
