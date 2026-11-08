"""What happens to a story or a decision is an event the aggregate registers, and the journal records it once
published: a story's into its journal, kind `event`, named by its type."""

import os
import tempfile
import unittest

import support
from support import gate_story
from dca_factory.delivery.adapter.outgoing.files.journal_events import JournalEventPublisher, cells
from dca_factory.delivery.domain.model.delivery_event import DeliveryEvent
from dca_factory.delivery.domain.model.story_words import ScenarioKey
from dca_factory.delivery.adapter.outgoing.files.journal_files import journal_events
from dca_factory.delivery.domain.model.decision_record import (
    Answer, AnswerApplied, Asker, CorrectionAsked, DecisionRecord, DecisionState, DeliveryAccepted, Given, NotAnswered,
    NotOpen, OptionKey, OptionNotOffered, QuestionAnswered, RecordContent, RecordId, RecordKind)
from dca_factory.delivery.domain.model.moment import Moment
from dca_factory.delivery.domain.model.person import Person
from dca_factory.delivery.domain.model.stage import StageName
from dca_factory.delivery.domain.model.story import (
    PLAN_ADOPT, AlreadyDelivered, Releasing, DeliveredBy, GatePass, StoryAdoptedForProof, Assumption, CitedCorrection, NothingToDeliver, NotReleased, PublicationTakenBack,
    StoryAdoptedOnPlan, StoryDeliveredByGate, StoryId, StoryReleased, StoryReopened, StoryStatus)
from dca_factory.delivery.domain.model.story_words import Detail

AT = Moment("2026-11-08T10:00:00Z")


class Events(unittest.TestCase):

    def test_a_released_story_registers_its_release_and_the_journal_records_it_once(self):
        story = gate_story("S-1", front={"status": "draft"})
        story.release(Person("jane"), Detail("R1"), AT)
        self.assertEqual(story.domain_events(), (StoryReleased(StoryId("S-1"), Person("jane"), AT),))
        with tempfile.TemporaryDirectory() as root:
            runs = os.path.join(root, "runs")      # the evidence, the journal among it, lies beside the run folder
            JournalEventPublisher(runs).publish_and_clear_events(story)
            self.assertEqual(story.domain_events(), ())
            written = [(e["name"], e["at"]) for e in journal_events(runs, "S-1") if e["kind"] == "event"]
            self.assertEqual(written, [("StoryReleased", AT.value)])

    def test_an_answered_question_registers_the_answer(self):
        record = DecisionRecord.restore(RecordId("S-1-01"), RecordKind.QUESTION, Asker.REQUEST, DecisionState.OPEN,
                                        story=StoryId("S-1"),
                                        content=RecordContent(Detail("q"), None, Detail(""), Detail(""), ()))
        record.answer(Answer(Given("a"), Person("jane"), AT))
        self.assertEqual(record.domain_events(), (QuestionAnswered(RecordId("S-1-01"), StoryId("S-1"), Person("jane"), Given("a"), AT),))


def record(kind=RecordKind.QUESTION, state=DecisionState.OPEN, options=(), written=""):
    return DecisionRecord.restore(RecordId("S-1-01"), kind, Asker.REQUEST, state, [OptionKey(o) for o in options],
                                  story=StoryId("S-1"),
                                  content=RecordContent(Detail("q"), None, Detail(written), Detail("jane"), ()))


class Transitions(unittest.TestCase):

    def test_the_gate_delivers_a_released_or_unmarked_story_and_registers_it(self):
        for front in ({"status": "approved"}, {"status": "adopted"}, {}):
            story = gate_story("S-1", front=front)
            story.deliver_by_gate(AT)
            self.assertEqual(story.domain_events(), (StoryDeliveredByGate(StoryId("S-1"), AT),), front)

    def test_the_gate_refuses_a_draft_a_superseded_and_a_delivered_story(self):
        with self.assertRaises(NotReleased):
            gate_story("S-1", front={"status": "draft"}).deliver_by_gate(AT)
        with self.assertRaises(NothingToDeliver):
            gate_story("S-1", front={"status": "superseded"}).deliver_by_gate(AT)
        with self.assertRaises(AlreadyDelivered):
            gate_story("S-1", front={"status": "delivered", "delivered": AT.value}).deliver_by_gate(AT)

    def test_a_released_story_the_plan_found_holding_is_adopted_with_the_plans_line(self):
        story = gate_story("S-1", front={"status": "approved"})
        line = Assumption.answered(Detail("every scenario holds"), PLAN_ADOPT)
        story.adopt_on_plan(line, AT)
        self.assertIs(story.status, StoryStatus.ADOPTED)
        self.assertIn(line, story.assumptions)
        self.assertEqual(story.domain_events(), (StoryAdoptedOnPlan(StoryId("S-1"), AT),))
        with self.assertRaises(NotReleased):
            gate_story("S-1", front={"status": "draft"}).adopt_on_plan(line, AT)

    def test_a_published_delivery_taken_back_is_what_it_was_published_over(self):
        story = gate_story("S-1", front={"status": "delivered", "delivered": AT.value, "delivered_by": "gate"})
        story.take_back_publication(StoryStatus.ADOPTED, AT)
        self.assertIs(story.status, StoryStatus.ADOPTED)
        self.assertIsNone(story.delivery)
        self.assertEqual(story.domain_events(), (PublicationTakenBack(StoryId("S-1"), AT),))

    def test_a_reopened_story_names_the_correction_it_cites(self):
        story = gate_story("S-1", front={"status": "delivered", "delivered": AT.value, "delivered_by": "gate"})
        story.reopen(CitedCorrection(Detail("S-1-02")), AT)
        self.assertEqual(story.domain_events(), (StoryReopened(StoryId("S-1"), Detail("S-1-02"), AT),))

    def test_an_acceptance_answered_accept_in_any_form_is_accepted_and_anything_else_a_correction(self):
        for given, event in (("accepted", DeliveryAccepted), ("Accepted.", DeliveryAccepted),
                             ("the label is wrong", CorrectionAsked)):
            answered = record(RecordKind.ACCEPTANCE)
            answered.answer(Answer(Given(given), Person("jane"), AT))
            self.assertEqual([type(e) for e in answered.domain_events()], [event], given)
            self.assertEqual(answered.accepts(), event is DeliveryAccepted)

    def test_an_option_is_chosen_on_an_open_record_that_offers_it(self):
        chosen = record(options=("a", "b"))
        chosen.choose(OptionKey("b"), Person("jane"), AT)
        self.assertIs(chosen.state, DecisionState.ANSWERED)
        with self.assertRaises(OptionNotOffered):
            record(options=("a",)).choose(OptionKey("c"), Person("jane"), AT)
        with self.assertRaises(NotOpen):
            record(state=DecisionState.ANSWERED, options=("a",), written="a").choose(OptionKey("a"), Person("jane"), AT)

    def test_a_claimed_delivery_handed_to_the_adopt_path_keeps_the_claim_in_its_event(self):
        story = gate_story("S-1", front={"status": "delivered", "delivered": AT.value, "delivered_by": "hand:jane"})
        story.adopt_for_proof(GatePass.MISSING, AT)
        self.assertEqual(story.domain_events(),
                         (StoryAdoptedForProof(StoryId("S-1"), DeliveredBy.hand(Person("jane")), AT),))

    def test_every_event_keeps_the_delivery_contract_and_the_journal_writes_its_fields_by_their_words(self):
        story = gate_story("S-1", front={"status": "approved"})
        story.split_off((ScenarioKey("a"), ScenarioKey("b")), Detail("a (T#a), b (T#b)"), AT)
        event = story.domain_events()[0]
        self.assertIsInstance(event, DeliveryEvent)
        self.assertEqual(cells(event), ["into=S-1-holds", "scenarios=a,b"])
        self.assertEqual(cells(StoryAdoptedForProof(StoryId("S-1"), DeliveredBy.hand(Person("jane")), AT)),
                         ["claimed_by=hand:jane"])

    def test_where_a_release_is_required_a_draft_or_a_story_without_status_is_never_delivered(self):
        for front in ({"status": "draft"}, {}):
            with self.assertRaises(NotReleased, msg=front):
                gate_story("S-1", front=front, releasing=Releasing.REQUIRED).deliver_by_gate(AT)
            with self.assertRaises(NotReleased, msg=front):
                gate_story("S-1", front=front, releasing=Releasing.REQUIRED).deliver_by_hand(Person("jane"), AT)
        unmarked = gate_story("S-1", front={}, releasing=Releasing.REQUIRED)
        unmarked.release(Person("jane"), Detail("R1"), AT)
        self.assertIs(unmarked.status, StoryStatus.APPROVED)
        unmarked.deliver_by_gate(AT)
        self.assertIs(unmarked.status, StoryStatus.DELIVERED)

    def test_without_the_profile_line_a_story_without_status_and_a_hand_delivered_draft_go_through_as_before(self):
        gate_story("S-1", front={}).deliver_by_gate(AT)
        gate_story("S-1", front={"status": "draft"}).deliver_by_hand(Person("jane"), AT)

    def test_an_answered_record_is_applied_once(self):
        applied = record(state=DecisionState.ANSWERED, written="a")
        applied.apply(StageName("build"), AT)
        self.assertIs(applied.state, DecisionState.APPLIED)
        self.assertEqual(applied.domain_events(),
                         (AnswerApplied(RecordId("S-1-01"), StoryId("S-1"), StageName("build"), AT),))
        with self.assertRaises(NotAnswered):
            applied.apply(StageName("build"), AT)
        with self.assertRaises(NotAnswered):
            record().apply(StageName("build"), AT)


if __name__ == "__main__":
    unittest.main()
