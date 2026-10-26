"""A story's and an epic's sections as the details show them: every `## ` section in the file's order, the criteria
or the stories as a block of their own at their place, why a story is not built first — and the one line that says
what is up with a story, with the view its detail opens with."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory import cli
from dca_factory.delivery.adapter.incoming.cli import terminal
from dca_factory.delivery.adapter.outgoing.files import detail_files as detail
from dca_factory.delivery.application.status import show_epic, show_story


def epic_sections(body, front):
    """An epic's sections as its detail shows them: taken apart by the file adapter, the head's fields left out."""
    sections, at = detail.sections_of(body, detail.EPIC_OWN_BLOCK, detail.FIRST_SECTIONS)
    return show_epic.epic_sections(sections, at, front)


def story_situation(row, story, overview, body):
    from datetime import datetime, timezone
    return show_story.story_situation(row, story, overview, detail.story_sections(body)["sections"],
                                      datetime.now(timezone.utc))


STORY = """# Show the thing

Prose before the first section.

## Story

As a reader I want the thing.

## Acceptance criteria

- shows-it (happy path): the thing shows

## Notes

- a note that runs on
  onto a second line
<!-- a comment nobody reads -->

## Empty

<!-- only a comment -->

## Superseded

- Not built: nobody wants it. A second sentence.
"""


class Sections(unittest.TestCase):

    def test_every_section_in_the_file_order_with_the_criteria_out_and_their_place_kept(self):
        sections, at = detail.sections_of(STORY, detail.STORY_OWN_BLOCK, detail.FIRST_SECTIONS)
        self.assertEqual([s["heading"] for s in sections], ["Superseded", "", "Story", "Notes"])
        self.assertEqual(sections[at - 1]["heading"], "Story")
        self.assertEqual(at, 3)

    def test_superseded_comes_first_and_says_so(self):
        sections = detail.story_sections(STORY)["sections"]
        self.assertEqual((sections[0]["heading"], sections[0]["kind"]), ("Superseded", "superseded"))
        self.assertEqual({s["kind"] for s in sections[1:]}, {""})

    def test_a_wrapped_line_is_kept_and_a_comment_left_out(self):
        notes = next(s for s in detail.sections_of(STORY, detail.STORY_OWN_BLOCK, detail.FIRST_SECTIONS)[0] if s["heading"] == "Notes")
        self.assertEqual(notes["text"], "- a note that runs on\n  onto a second line")

    def test_the_text_view_joins_a_wrapped_list_line_to_its_item(self):
        lines = terminal.paragraph_lines("- a note that runs on\n  onto a second line\n- another", "  ")
        self.assertEqual(lines, ["  - a note that runs on onto a second line", "  - another"])

    def test_an_epic_keeps_its_stories_place(self):
        sections, at = detail.sections_of("# E\n\n## Intent\n\nwhy\n\n## Stories\n\n- S-1\n\n## Journey\n\n- open\n",
                                       detail.EPIC_OWN_BLOCK)
        self.assertEqual(([s["heading"] for s in sections], at), (["Intent", "Journey"], 1))

    def test_no_criteria_section_has_no_place(self):
        self.assertIsNone(detail.story_sections("# T\n\n## Story\n\ntext\n")["criteria_at"])


EPIC = """# Availability before adding

## Intent

Customers order products
that are no longer in stock.

## Goal

A customer sees whether a product is available. More: and why it matters.

## Outcome

The epic is measured by the outcome event `StockChanged`: as long as it is not published in production, the epic
has not delivered, however much code exists.

## Stories

- S-1 — one

## Journey

- open: the flow
"""

EPIC_FRONT = dict(intent="Customers order products that are no longer in stock", metric="StockChanged",
                  goal="A customer sees whether a product is available")


class HeadSaysIt(unittest.TestCase):

    def test_a_section_that_only_repeats_a_head_field_is_left_out_and_the_stories_place_follows(self):
        got = epic_sections(EPIC, EPIC_FRONT)
        self.assertEqual([s["heading"] for s in got["sections"]], ["Goal", "Journey"])
        self.assertEqual(got["stories_at"], 1)

    def test_a_section_with_more_to_say_stays(self):
        self.assertIn("Goal", [s["heading"] for s in epic_sections(EPIC, EPIC_FRONT)["sections"]])

    def test_the_outcome_section_stays_beside_another_event(self):
        got = epic_sections(EPIC, dict(EPIC_FRONT, metric="StockReserved"))
        self.assertIn("Outcome", [s["heading"] for s in got["sections"]])

    def test_without_the_field_the_section_stays(self):
        got = epic_sections(EPIC, {})
        self.assertEqual([s["heading"] for s in got["sections"]], ["Intent", "Goal", "Outcome", "Journey"])

    def test_the_template_says_the_outcome_sentence_the_factory_leaves_out(self):
        import os
        template = os.path.join(os.path.dirname(cli.__file__), "..", "..", "templates", "backlog", "epic.md.tmpl")
        with open(template, encoding="utf-8") as handle:
            text = handle.read()
        sentence = show_epic.OUTCOME_BOILERPLATE.format(metric="{{OUTCOME_EVENT_THAT_MEASURES_IT}}")
        self.assertIn(show_story.said_alike(sentence), show_story.said_alike(text))

    def test_the_epic_line_leaves_the_progress_to_the_head(self):
        epic = dict(rows=[dict(story="S-1", state="delivered", passes=1, done=True)], delivered=1, total=1)
        overview = dict(running=[], waiting=[])
        self.assertEqual(show_epic.epic_situation(epic, overview), dict(situation=""))  # one page: no view to choose
        overview = dict(running=[dict(story="S-1", stage="build", interrupted=False)], waiting=[])
        self.assertEqual(show_epic.epic_situation(epic, overview)["situation"], "S-1 running build")


class Situation(unittest.TestCase):

    OVERVIEW = dict(running=[], waiting=[], queue=dict(ready=["S-2", "S-1"]))

    def row(self, **more):
        return dict(dict(story="S-1", done=False, delivered=None, mark="none", state="ready", passes=0), **more)

    def test_superseded_names_the_first_sentence_of_its_reason_and_opens_the_story(self):
        self.assertEqual(story_situation(self.row(state="superseded"), dict(state="superseded"), self.OVERVIEW, STORY),
                         dict(situation="superseded — Not built: nobody wants it", view="story"))

    def test_a_ready_story_says_its_place_in_line(self):
        self.assertEqual(story_situation(self.row(), dict(state="ready"), self.OVERVIEW, ""),
                         dict(situation="ready — not started · 2. in line", view="story"))

    def test_a_running_story_names_stage_and_round_and_opens_the_pipeline(self):
        overview = dict(self.OVERVIEW, running=[dict(story="S-1", stage="build", round=2, interrupted=False, since=None)])
        self.assertEqual(story_situation(self.row(), dict(state="running"), overview, ""),
                         dict(situation="running build · round 2", view="pipeline"))

    def test_a_waiting_story_opens_the_pipeline_without_repeating_its_state(self):
        got = story_situation(self.row(mark="look", state="waiting for your acceptance"), dict(state="waiting"),
                                  self.OVERVIEW, "")
        self.assertEqual(got, dict(situation="", view="pipeline"))  # the head shows that state already

    def test_a_line_that_says_more_than_the_state_stays(self):
        got = story_situation(self.row(mark="stopped", state="stopped"), dict(state="stopped", detail="gate red."),
                                  self.OVERVIEW, "")
        self.assertEqual(got["situation"], "stopped — gate red")

    def test_a_blocked_story_says_on_what(self):
        got = story_situation(self.row(state="blocked"), dict(state="blocked", detail="depends on S-0"),
                                  self.OVERVIEW, "")
        self.assertEqual(got["situation"], "blocked — depends on S-0")


if __name__ == "__main__":
    unittest.main()
