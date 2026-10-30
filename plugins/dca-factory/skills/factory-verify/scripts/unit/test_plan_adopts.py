"""The plan adopts what already holds (WP-165): `## Adopt` names scenarios that hold on today's code with the test
that shows each; the plan gate adopts the whole story or splits those scenarios off into an adopted story."""

import os
import unittest

from support import evidence, project, verdict, write
from dca_factory.delivery.adapter.outgoing.files.plan_adoption_files import split_off
from dca_factory.delivery.adapter.outgoing.files.stage_delivery_files import StageDeliveryFiles
from dca_factory.delivery.adapter.outgoing.files.stage_evidence_files import stage_story
from dca_factory.delivery.domain.service.adopt_checks import AdoptChecks, Adoption
from dca_factory.sharedkernel.adapter.outgoing.markdown import front_matter as markdown

STORY = """---
id: S-1
epic: sample
status: approved
context: widgets
title: Widgets are shown
---

# Widgets are shown

## Acceptance criteria

### Rule: A widget is shown with its name

#### shows-the-name (happy path)
- Given a widget "Cog"
- Then "Cog" is shown

#### shows-the-price
- Given a widget "Cog" at 3 EUR
- Then "3 EUR" is shown

### Rule: An empty shelf says so

#### says-the-shelf-is-empty
- Given no widget
- Then "Nothing here yet" is shown

## Notes

- a note
"""

TEST = "class WidgetPageTest {\n  @Test void showsThePrice() {}\n  @Test void saysTheShelfIsEmpty() {}\n" \
       "  @Test void showsTheName() {}\n}\n"


def adopt(*rows):
    return "# Plan\n\n## Adopt\n\n| criterion | test |\n| --- | --- |\n" + "".join(
        f"| {key} | {test} |\n" for key, test in rows)


class PlanAdopts(unittest.TestCase):

    def setUp(self):
        self._project = project()
        self.p = self._project.__enter__()
        self.path = self.p.story("S-1", text=STORY)
        write(os.path.join(self.p.root, "src/test/java/WidgetPageTest.java"), TEST)

    def tearDown(self):
        self._project.__exit__(None, None, None)

    def story(self):
        front, body = markdown.read_front_matter(self.path)
        keys = [("shows-the-name", ""), ("shows-the-price", ""), ("says-the-shelf-is-empty", "")]
        return stage_story("S-1", self.path, front, body, [(k, t) for k, t in keys if f"#### {k}" in body])

    def found(self):
        return verdict(AdoptChecks.found(self.story(), evidence(self.p.root, self.p.runs)))

    def test_a_plan_without_adopt_adopts_nothing(self):
        self.p.run_file("S-1", "plan.md", "# Plan\n")
        self.assertIs(AdoptChecks.outcome(self.story(), evidence(self.p.root, self.p.runs).plan_adoption(
            self.story().story)), Adoption.NONE)

    def test_scenarios_that_hold_without_the_happy_path_are_split_off(self):
        self.p.run_file("S-1", "plan.md", adopt(("shows-the-price", "WidgetPageTest#showsThePrice"),
                                                ("says-the-shelf-is-empty", "WidgetPageTest#saysTheShelfIsEmpty")))
        self.assertFalse(self.found().failed)
        held = [("shows-the-price", "WidgetPageTest#showsThePrice"),
                ("says-the-shelf-is-empty", "WidgetPageTest#saysTheShelfIsEmpty")]
        StageDeliveryFiles(self.p.root, self.p.runs, {}).adopt(verdict(), "S-1", self.path, held, False)
        rest = markdown.read_text(self.path)
        self.assertIn("#### shows-the-name (happy path)", rest)
        self.assertNotIn("shows-the-price", rest.split("## Assumptions")[0])
        self.assertNotIn("An empty shelf", rest)
        self.assertIn("split them into the adopted story `S-1-holds`", rest)
        split = os.path.join(os.path.dirname(os.path.dirname(self.path)), "S-1-holds", "story.md")
        front, body = markdown.read_front_matter(split)
        self.assertEqual(front["status"], "adopted")
        self.assertIn("#### shows-the-price", body)
        self.assertIn("### Rule: An empty shelf says so", body)
        self.assertIn("### Rule: A widget is shown with its name", body)

    def test_the_whole_story_holding_makes_it_adopted(self):
        self.p.run_file("S-1", "plan.md", adopt(("shows-the-name", "WidgetPageTest#showsTheName"),
                                                ("shows-the-price", "WidgetPageTest#showsThePrice"),
                                                ("says-the-shelf-is-empty", "WidgetPageTest#saysTheShelfIsEmpty")))
        self.assertFalse(self.found().failed)
        adoption = evidence(self.p.root, self.p.runs).plan_adoption(self.story().story)
        self.assertIs(AdoptChecks.outcome(self.story(), adoption), Adoption.WHOLE)
        StageDeliveryFiles(self.p.root, self.p.runs, {}).adopt(
            verdict(), "S-1", self.path, [(r.key.value, r.test.value) for r in adoption.rows], True)
        front, body = markdown.read_front_matter(self.path)
        self.assertEqual(front["status"], "adopted")
        self.assertIn("the plan adopted the story", body)
        self.assertIs(AdoptChecks.outcome(self.story(), adoption), Adoption.NONE)

    def test_a_split_that_takes_the_only_happy_path_is_refused(self):
        self.p.run_file("S-1", "plan.md", adopt(("shows-the-name", "WidgetPageTest#showsTheName")))
        self.assertTrue(self.found().failed)

    def test_a_test_that_is_not_there_is_refused(self):
        self.p.run_file("S-1", "plan.md", adopt(("shows-the-price", "WidgetPageTest#showsTheTaxToo")))
        self.assertTrue(self.found().failed)

    def test_a_key_that_is_no_criterion_is_refused(self):
        self.p.run_file("S-1", "plan.md", adopt(("shows-the-colour", "WidgetPageTest#showsThePrice")))
        self.assertTrue(self.found().failed)


class SplitOff(unittest.TestCase):

    def test_a_rule_with_scenarios_on_both_sides_goes_to_both(self):
        rest, moved = split_off(STORY.split("\n"), {"shows-the-price"})
        self.assertIn("### Rule: A widget is shown with its name", rest)
        self.assertIn("### Rule: A widget is shown with its name", moved)
        self.assertIn("#### shows-the-price", moved)
        self.assertNotIn("#### shows-the-price", rest)
        self.assertIn("## Notes", rest)


if __name__ == "__main__":
    unittest.main()
