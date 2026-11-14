"""The adapter test the plan names in a criterion's adapter shape, and how the test gate finds it among the
criterion's mapped tests (`tests-planned`)."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.files.design_files import adapter_shapes, adapter_tests
from dca_factory.delivery.domain.model.plan_facts import PlannedTest
from dca_factory.delivery.domain.model.story_words import ScenarioKey, Selector


def named(lines):
    with tempfile.TemporaryDirectory() as runs:
        os.makedirs(os.path.join(runs, "S-1"))
        with open(os.path.join(runs, "S-1", "plan.md"), "w", encoding="utf-8") as handle:
            handle.write("# Plan\n\n## Acceptance criteria\n" + "\n".join(lines) + "\n")
        return adapter_tests(runs, "S-1"), adapter_shapes(runs, "S-1")


class AdapterTestsTest(unittest.TestCase):

    def test_the_test_inside_the_adapter_shape_is_read_with_its_key(self):
        tests, (alone, both) = named([
            "- shows-the-name  →  level: integration (adapter: ThingPage, test: ThingPageTest#showsTheName) — first",
            "- counts-after-a-change  →  level: integration (port) and integration (adapter: ThingPage, test: "
            "`com.example.ThingPageTest#showsTwoThings`)",
            "- happy  →  level: e2e"])
        self.assertEqual([("shows-the-name", "ThingPageTest#showsTheName"),
                          ("counts-after-a-change", "com.example.ThingPageTest#showsTwoThings")], tests)
        self.assertEqual({"shows-the-name"}, alone)
        self.assertEqual({"counts-after-a-change"}, both)

    def test_an_adapter_shape_without_a_test_is_read_as_one_without(self):
        tests, _ = named(["- shows-the-name  →  level: integration (adapter: ThingPage)"])
        self.assertEqual([("shows-the-name", "")], tests)

    def test_a_criterion_without_the_adapter_shape_names_no_test(self):
        tests, _ = named(["- stores-it  →  level: integration (port) — test: ThingTest#storesIt"])
        self.assertEqual([], tests)


class PlannedTestTest(unittest.TestCase):

    def planned(self, test):
        return PlannedTest(ScenarioKey("shows-the-name"), Selector(test))

    def test_found_by_simple_class_name_and_method(self):
        self.assertTrue(self.planned("ThingPageTest#showsTheName").found_in(
            [Selector("com.example.web.ThingPageTest#showsTheName")]))

    def test_found_when_the_plan_names_the_qualified_class(self):
        self.assertTrue(self.planned("com.example.web.ThingPageTest#showsTheName").found_in(
            [Selector("com.example.web.ThingPageTest#showsTheName")]))

    def test_another_method_is_not_it(self):
        self.assertFalse(self.planned("ThingPageTest#showsTheName").found_in(
            [Selector("com.example.web.ThingPageTest#trimsTheName")]))

    def test_another_class_with_the_method_is_not_it(self):
        self.assertFalse(self.planned("ThingPageTest#showsTheName").found_in(
            [Selector("com.example.OtherThingPageTest#showsTheName")]))

    def test_a_shape_without_a_test_is_found_nowhere(self):
        self.assertFalse(PlannedTest(ScenarioKey("k"), None).found_in([Selector("A#b")]))


if __name__ == "__main__":
    unittest.main()
