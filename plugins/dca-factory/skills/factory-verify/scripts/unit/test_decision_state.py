"""A decision record's state, read off its sections: applied, open, a draft until the answer carries every line —
and where an acceptance stands from its latest record."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.decision_record import AnswerField, DecisionState, Given, Section
from dca_factory.delivery.domain.model.stage_story import Presence
from dca_factory.delivery.domain.model.story_state import AcceptanceVerdict
from dca_factory.delivery.domain.service.acceptance_rules import AcceptanceRules

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
        self.assertIs(AcceptanceRules.verdict(None, Given(""), same), AcceptanceVerdict.ASK)
        self.assertIs(AcceptanceRules.verdict(DecisionState.DRAFT, Given("accepted"), same), AcceptanceVerdict.OPEN)
        self.assertIs(AcceptanceRules.verdict(DecisionState.ANSWERED, Given("accepted"), changed),
                      AcceptanceVerdict.ASK)

    def test_an_answer_beginning_accept_accepts_any_other_asks_for_a_correction(self):
        self.assertIs(AcceptanceRules.verdict(DecisionState.APPLIED, Given(" Accepted "), Presence.PRESENT),
                      AcceptanceVerdict.ACCEPTED)
        self.assertIs(AcceptanceRules.verdict(DecisionState.ANSWERED, Given("the button is red"), Presence.PRESENT),
                      AcceptanceVerdict.CORRECTION)


if __name__ == "__main__":
    unittest.main()
