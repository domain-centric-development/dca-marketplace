"""A decision record's state, read off its sections: applied, open, a draft until the answer carries every line —
and where an acceptance stands from its latest record."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.decision_record import AnswerField, DecisionState, Given, RecordKind, Section
from dca_factory.delivery.domain.model.stage_story import Presence
from dca_factory.delivery.domain.model.story_state import AcceptanceVerdict
from dca_factory.delivery.domain.model.acceptance import RecordAnswer

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
        same, changed = Presence.PRESENT, Presence.ABSENT
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, None, Given("")).verdict(same), AcceptanceVerdict.ASK)
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, DecisionState.DRAFT, Given("accepted")).verdict(same), AcceptanceVerdict.OPEN)
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, DecisionState.ANSWERED, Given("accepted")).verdict(changed),
                      AcceptanceVerdict.ASK)

    def test_an_answer_beginning_accept_accepts_any_other_asks_for_a_correction(self):
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, DecisionState.APPLIED, Given(" Accepted ")).verdict(Presence.PRESENT),
                      AcceptanceVerdict.ACCEPTED)
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, DecisionState.ANSWERED, Given("the button is red")).verdict(Presence.PRESENT),
                      AcceptanceVerdict.CORRECTION)

    def test_a_correction_and_an_answered_question_back_a_change_an_acceptance_that_accepted_does_not(self):
        answered, waiting = DecisionState.ANSWERED, DecisionState.OPEN
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, answered, Given("the label is wrong")).corrects(), Presence.PRESENT)
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, answered, Given("accepted")).corrects(), Presence.ABSENT)
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, waiting, Given("")).corrects(), Presence.ABSENT)
        self.assertIs(RecordAnswer(RecordKind.QUESTION, answered, Given("b")).backs_change(), Presence.PRESENT)
        self.assertIs(RecordAnswer(RecordKind.QUESTION, waiting, Given("")).backs_change(), Presence.ABSENT)
        self.assertIs(RecordAnswer(RecordKind.ACCEPTANCE, answered, Given("accepted")).backs_change(),
                      Presence.ABSENT)


if __name__ == "__main__":
    unittest.main()
