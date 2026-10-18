"""A story's and an epic's sections as the details show them: every `## ` section in the file's order, the criteria
or the stories as a block of their own at their place, why a story is not built first — and the one line that says
what is up with a story, with the view its detail opens with."""

import unittest

from support import contract  # noqa: F401 — puts the package on the path
from dca_factory import cli


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
        sections, at = cli.sections_of(STORY, cli.STORY_OWN_BLOCK)
        self.assertEqual([s["heading"] for s in sections], ["Superseded", "", "Story", "Notes"])
        self.assertEqual(sections[at - 1]["heading"], "Story")
        self.assertEqual(at, 3)

    def test_superseded_comes_first_and_says_so(self):
        sections = cli.story_sections(STORY)["sections"]
        self.assertEqual((sections[0]["heading"], sections[0]["kind"]), ("Superseded", "superseded"))
        self.assertEqual({s["kind"] for s in sections[1:]}, {""})

    def test_a_wrapped_line_is_kept_and_a_comment_left_out(self):
        notes = next(s for s in cli.sections_of(STORY, cli.STORY_OWN_BLOCK)[0] if s["heading"] == "Notes")
        self.assertEqual(notes["text"], "- a note that runs on\n  onto a second line")

    def test_the_text_view_joins_a_wrapped_list_line_to_its_item(self):
        lines = cli.paragraph_lines("- a note that runs on\n  onto a second line\n- another", "  ")
        self.assertEqual(lines, ["  - a note that runs on onto a second line", "  - another"])

    def test_an_epic_keeps_its_stories_place(self):
        sections, at = cli.sections_of("# E\n\n## Intent\n\nwhy\n\n## Stories\n\n- S-1\n\n## Journey\n\n- open\n",
                                       cli.EPIC_OWN_BLOCK)
        self.assertEqual(([s["heading"] for s in sections], at), (["Intent", "Journey"], 1))

    def test_no_criteria_section_has_no_place(self):
        self.assertIsNone(cli.story_sections("# T\n\n## Story\n\ntext\n")["criteria_at"])


class Situation(unittest.TestCase):

    OVERVIEW = dict(running=[], waiting=[], queue=dict(ready=["S-2", "S-1"]))

    def row(self, **more):
        return dict(dict(story="S-1", done=False, delivered=None, mark="none", state="ready", passes=0), **more)

    def test_superseded_names_the_first_sentence_of_its_reason_and_opens_the_story(self):
        self.assertEqual(cli.story_situation(self.row(state="superseded"), dict(state="superseded"), self.OVERVIEW, STORY),
                         dict(situation="superseded — Not built: nobody wants it", view="story"))

    def test_a_ready_story_says_its_place_in_line(self):
        self.assertEqual(cli.story_situation(self.row(), dict(state="ready"), self.OVERVIEW, ""),
                         dict(situation="ready — not started · 2. in line", view="story"))

    def test_a_running_story_names_stage_and_round_and_opens_the_pipeline(self):
        overview = dict(self.OVERVIEW, running=[dict(story="S-1", stage="build", round=2, interrupted=False, since=None)])
        self.assertEqual(cli.story_situation(self.row(), dict(state="running"), overview, ""),
                         dict(situation="running build · round 2", view="pipeline"))

    def test_a_waiting_story_opens_the_pipeline(self):
        got = cli.story_situation(self.row(mark="look", state="waiting for your acceptance"), dict(state="waiting"),
                                  self.OVERVIEW, "")
        self.assertEqual(got, dict(situation="waiting for your acceptance", view="pipeline"))

    def test_a_blocked_story_says_on_what(self):
        got = cli.story_situation(self.row(state="blocked"), dict(state="blocked", detail="depends on S-0"),
                                  self.OVERVIEW, "")
        self.assertEqual(got["situation"], "blocked — depends on S-0")


if __name__ == "__main__":
    unittest.main()
