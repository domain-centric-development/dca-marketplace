"""A story's acceptance criteria and the test stage's criterion-to-test table, as the gate reads them."""

import os
import unittest

from support import contract, project, write
from dca_factory import gate


def criteria(section):
    return gate.criteria_of("story.md", "# Story\n\n## Acceptance criteria\n" + section + "\n## Notes\n- not a criterion\n")


class LineForm(unittest.TestCase):

    def test_one_line_per_criterion_with_the_happy_path_mark_left_out_of_the_key(self):
        self.assertEqual(criteria("- shows-the-thing (happy path): the thing shows\n- shows-nothing: nothing\n"),
                         [("shows-the-thing", "the thing shows"), ("shows-nothing", "nothing")])

    def test_a_dash_line_without_a_key_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "has no key"):
            criteria("- The thing shows\n")

    def test_no_criteria_at_all_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "no acceptance criteria"):
            gate.criteria_of("story.md", "# Story\n\nNothing here.\n")

    def test_a_key_twice_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "appears twice"):
            criteria("- shows-it: a\n- shows-it: b\n")


class ScenarioForm(unittest.TestCase):

    def test_a_scenario_is_its_steps_joined(self):
        self.assertEqual(criteria("### Rule: things show\n#### shows-the-thing (happy path)\n"
                                  "- Given a thing\n- When I look\n- Then it shows\n- And it is bright\n"),
                         [("shows-the-thing", "Given a thing; When I look; Then it shows; And it is bright")])

    def test_an_and_after_when_is_a_second_trigger(self):
        with self.assertRaisesRegex(contract.GateError, "has 2 triggers"):
            criteria("#### shows-it\n- Given a thing\n- When I look\n- And I blink\n- Then it shows\n")

    def test_a_scenario_without_then_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "has no `Then`"):
            criteria("#### shows-it\n- Given a thing\n- When I look\n")

    def test_a_rule_without_a_scenario_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "has no scenario"):
            criteria("### Rule: things show\n### Rule: another\n#### shows-it\n- When I look\n- Then it shows\n")

    def test_a_step_outside_a_scenario_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "stands outside a scenario"):
            criteria("- Given a thing\n")

    def test_a_third_level_heading_must_be_a_rule(self):
        with self.assertRaisesRegex(contract.GateError, "is a `### Rule: <text>`"):
            criteria("### Things\n")

    def test_a_scenario_heading_must_be_a_key(self):
        with self.assertRaisesRegex(contract.GateError, "is not a key"):
            criteria("#### Shows It\n- When I look\n- Then it shows\n")


class HappyPathAndTitles(unittest.TestCase):

    BODY = ("## Acceptance criteria\n#### shows-the-thing (happy path)\nTitle: The thing is shown\n"
            "- When I look\n- Then it shows\n- shows-nothing: nothing\n\n## Notes\n- other (happy path): no\n")

    def test_only_the_criteria_section_marks_a_happy_path(self):
        self.assertEqual(gate.happy_paths(self.BODY), ["shows-the-thing"])

    def test_a_title_line_names_the_scenario_else_the_key_in_words(self):
        self.assertEqual(gate.scenario_titles(self.BODY),
                         {"shows-the-thing": "The thing is shown", "shows-nothing": "Shows nothing"})


class Mapping(unittest.TestCase):

    def write_tests(self, p, table):
        write(os.path.join(p.runs, "S-1", "tests.md"), "# Tests\n\n<!-- gate:tests -->\n" + table)

    def test_rows_map_a_key_to_its_selectors_until_the_next_heading(self):
        with project() as p:
            self.write_tests(p, "| criterion | test |\n|---|---|\n"
                             "| shows-it | com.example.WidgetTest#showsIt |\n"
                             "| shows-it | com.example.WidgetUnitTest#showsIt |\n"
                             "| hides-it | com.example.WidgetTest#hidesIt |\n"
                             "\n## Invariants\n| other | com.example.X#y |\n")
            _path, mapping = gate.read_mapping(p.runs, "S-1")
            self.assertEqual(mapping, {"shows-it": ["com.example.WidgetTest#showsIt", "com.example.WidgetUnitTest#showsIt"],
                                       "hides-it": ["com.example.WidgetTest#hidesIt"]})

    def test_a_selector_that_is_no_class_and_method_is_refused(self):
        with project() as p:
            self.write_tests(p, "| shows-it | WidgetTest.showsIt |\n")
            with self.assertRaisesRegex(contract.GateError, "is not `<Class>#<method>`"):
                gate.read_mapping(p.runs, "S-1")

    def test_a_tests_file_without_the_table_marker_is_refused(self):
        with project() as p:
            write(os.path.join(p.runs, "S-1", "tests.md"), "| shows-it | com.example.WidgetTest#showsIt |\n")
            with self.assertRaisesRegex(contract.GateError, "no `<!-- gate:tests -->` table"):
                gate.read_mapping(p.runs, "S-1")


if __name__ == "__main__":
    unittest.main()
