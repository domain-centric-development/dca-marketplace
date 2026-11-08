"""What happens to a story or a decision is an event the aggregate registers, and the journal records it once
published: a story's into its journal, kind `event`, named by its type."""

import os
import tempfile
import unittest

import support
from support import gate_story
from dca_factory.delivery.adapter.outgoing.files.journal_events import JournalEventPublisher
from dca_factory.delivery.adapter.outgoing.files.journal_files import journal_events
from dca_factory.delivery.domain.model.decision_record import (
    Answer, Asker, DecisionRecord, DecisionState, Given, QuestionAnswered, RecordContent, RecordId, RecordKind)
from dca_factory.delivery.domain.model.moment import Moment
from dca_factory.delivery.domain.model.person import Person
from dca_factory.delivery.domain.model.story import Assumption, StoryId, StoryReleased
from dca_factory.delivery.domain.model.story_words import Detail

AT = Moment("2026-11-08T10:00:00Z")


class Events(unittest.TestCase):

    def test_a_released_story_registers_its_release_and_the_journal_records_it_once(self):
        story = gate_story("S-1", front={"status": "draft"})
        story.release(Assumption("- answered: released"), AT)
        self.assertEqual(story.domain_events(), (StoryReleased(StoryId("S-1"), AT),))
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
        self.assertEqual(record.domain_events(), (QuestionAnswered(RecordId("S-1-01"), StoryId("S-1"), AT),))


if __name__ == "__main__":
    unittest.main()
