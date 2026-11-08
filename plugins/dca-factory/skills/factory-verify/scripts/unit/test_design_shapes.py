"""The test design's readings a benchmark run found too strict (WP-186, 0.144.1): a plan line that gives a criterion
both shapes, a form field that holds what the person entered, and `- none — <why>` with a colon in the why."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path
from support import gate_story
from dca_factory.delivery.adapter.outgoing.files.design_files import adapter_shapes, plan_invariants
from dca_factory.delivery.domain.model.stage_story import Clause, Count
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.service.design_checks import states_stored as stored


def states_stored(text, *actions):
    return stored(Clause(Count(1), Detail(text)), tuple(Detail(a) for a in actions))


ECHO_STORY = """# A story

## Acceptance criteria

#### refuses-a-name-of-201-characters
- Given the record is empty
- When the person adds a thing whose name is 201 characters „a“
- And presses „Add“
- Then the name field still holds the 201 characters „a“
- And the record is still empty
"""


def shapes(lines):
    with tempfile.TemporaryDirectory() as runs:
        os.makedirs(os.path.join(runs, "S-1"))
        with open(os.path.join(runs, "S-1", "plan.md"), "w", encoding="utf-8") as handle:
            handle.write("# Plan\n\n## Acceptance criteria\n" + "\n".join(lines) + "\n")
        return adapter_shapes(runs, "S-1")


class AdapterShapes(unittest.TestCase):

    def test_the_adapter_shape_alone_is_exempt(self):
        alone, both = shapes(["- shows-the-name  →  level: integration (adapter: ThingPage) — the name stands first"])
        self.assertEqual(({"shows-the-name"}, set()), (alone, both))

    def test_the_port_shape_before_the_adapter_shape_is_both(self):
        alone, both = shapes(["- count-follows-a-change  →  level: integration (port) and integration (adapter: "
                              "ThingPage) — port: after `ChangeThingInputPort`, the count (2, 1)"])
        self.assertEqual((set(), {"count-follows-a-change"}), (alone, both))

    def test_an_end_to_end_shape_beside_the_adapter_shape_is_both(self):
        _alone, both = shapes(["- shows-the-count  →  level: e2e and integration (adapter: ThingPage)"])
        self.assertEqual({"shows-the-count"}, both)

    def test_a_shape_named_only_after_the_dash_is_explanation_not_a_level(self):
        alone, both = shapes(["- shows-the-name  →  level: integration (adapter: ThingPage) — unlike the port's "
                              "integration test of the count"])
        self.assertEqual(({"shows-the-name"}, set()), (alone, both))

    def test_a_line_without_the_adapter_shape_is_neither(self):
        self.assertEqual((set(), set()), shapes(["- shows-the-count  →  level: integration (port)",
                                                 "- shows-the-list  →  level: e2e"]))


class StatesStored(unittest.TestCase):

    def test_a_form_field_holding_what_was_entered_is_the_adapters_translation(self):
        self.assertFalse(states_stored("And the field „Name“ still holds the 201 characters entered"))
        self.assertFalse(states_stored("Und das Eingabefeld „Name“ enthält weiterhin die eingegebenen 201 Zeichen"))
        self.assertFalse(states_stored("And the text box still shows the text typed"))

    def test_another_records_state_stays_a_state_clause(self):
        self.assertTrue(states_stored("And „Alpha“ still carries the button „Done“"))
        self.assertTrue(states_stored("And the thing stays unchanged"))

    def test_a_field_showing_what_is_stored_stays_a_state_clause(self):
        self.assertTrue(states_stored("And the field „Name“ still shows the stored name"))

    def test_a_field_holding_the_texts_and_counts_the_when_names_is_the_adapters_translation(self):
        story = gate_story("S-1", "story.md", {"status": "approved"}, ECHO_STORY)
        scenario = story.content.clauses[0]
        self.assertEqual(("When the person adds a thing whose name is 201 characters „a“", "And presses „Add“"),
                         tuple(a.value for a in scenario.actions))
        echo, record = scenario.clauses
        self.assertFalse(stored(echo, scenario.actions))
        self.assertTrue(stored(record, scenario.actions))

    def test_a_field_naming_what_the_when_does_not_stays_a_state_clause(self):
        when = "When the person adds a thing whose name is 201 characters „a“"
        self.assertTrue(states_stored("Then the name field still holds the 200 characters „a“", when))
        self.assertTrue(states_stored("Then the name field still holds the 201 characters „b“", when))
        self.assertTrue(states_stored("And „Alpha“ still carries the button „201“", when))


class PlanInvariants(unittest.TestCase):

    def test_none_with_a_colon_in_its_why_names_no_element(self):
        plan = ("# Plan\n\n## Invariants\n- none — no domain type changes: the operation loads no record "
                "(`a-recipe.md` § Why)\n")
        self.assertEqual({}, plan_invariants(plan))

    def test_an_element_with_none_keeps_its_empty_list(self):
        plan = "# Plan\n\n## Invariants\n- Thing: a name is required\n- ThingState: none — two constants\n"
        self.assertEqual({"Thing": ["a name is required"], "ThingState": []}, plan_invariants(plan))


if __name__ == "__main__":
    unittest.main()
