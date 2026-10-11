"""The living spec (WP-98): a story's criteria as entries, the spec file read and written, the delta derived and
checked, the merge by key."""

import io
import contextlib
import os
import unittest

from support import contract, project, write
from dca_factory import cli, runner, spec

STORY = """---
id: S-1
context: Widgets
status: approved
---
# S-1

## Acceptance criteria

### Rule: A widget is shown with its name

#### shows-the-name (happy path)
- Given a widget "Cog"
- When the page opens
- Then "Cog" is shown

- lists-in-order: the widgets are listed by name,
  the first one at the top.

## Assumptions
- open: none
"""


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Entries(unittest.TestCase):

    def test_both_forms_are_read_with_their_rule_and_without_the_happy_path_mark(self):
        found = spec.story_entries(contract.split_front(STORY)[1])
        self.assertEqual([(e["key"], e["rule"], e["form"]) for e in found],
                         [("shows-the-name", "A widget is shown with its name", "scenario"),
                          ("lists-in-order", "A widget is shown with its name", "line")])
        self.assertEqual(found[0]["lines"][0], "#### shows-the-name")
        self.assertEqual(found[1]["lines"], ["- lists-in-order: the widgets are listed by name,",
                                             "  the first one at the top."])

    def test_the_spec_file_reads_back_as_written(self):
        entries = spec.story_entries(contract.split_front(STORY)[1])
        entries[0]["tests"] = ["a.WidgetTest#showsTheName"]
        text = spec.render_spec([], entries, "Widgets")
        preamble, back = spec.parse_spec(text)
        self.assertEqual(spec.render_spec(preamble, back, "ignored"), text)
        self.assertEqual(back[0]["tests"], ["a.WidgetTest#showsTheName"])
        self.assertIn("### Rule: A widget is shown with its name\n\n#### shows-the-name\n", text)

    def test_criteria_without_a_rule_stand_before_the_first_rule(self):
        lone = spec.entry("plain", None, "line", ["- plain: it holds"])
        ruled = spec.entry("ruled", "R", "line", ["- ruled: it holds"])
        text = spec.render_spec([], [ruled, lone], "C")
        self.assertLess(text.index("- plain:"), text.index("### Rule: R"))


class Delta(unittest.TestCase):

    def setUp(self):
        self.held = [spec.entry("a", "R", "line", ["- a: one"], ["x.T#a"]),
                     spec.entry("b", "R", "line", ["- b: two"], ["x.T#b"])]

    def test_new_held_and_changed_keys_are_derived(self):
        story = [spec.entry("a", "R", "line", ["- a: one"]), spec.entry("b", "R", "line", ["- b: TWO"]),
                 spec.entry("c", "R", "line", ["- c: three"])]
        self.assertEqual(spec.derived(story, self.held), {"a": "holds", "b": "changes", "c": "adds"})
        self.assertEqual(spec.touches(story, self.held, spec.read_delta("")), ["b"])

    def test_a_delta_that_disagrees_or_leaves_a_scenario_behind_is_named(self):
        story = [spec.entry("a", "S", "line", ["- a: one"])]
        delta = spec.read_delta('## Spec delta\n- adds a\n- removes zzz\n- rule "R" → "S"\n')
        problems = spec.delta_problems(story, self.held, delta)
        self.assertTrue(any("`adds a`" in p for p in problems), problems)
        self.assertTrue(any("removes zzz" in p for p in problems), problems)
        self.assertTrue(any("leaves b under the old text" in p for p in problems), problems)
        fine = spec.read_delta('## Spec delta\n- changes a\n- removes b: gone\n- rule "R" -> "S"\n')
        self.assertEqual(spec.delta_problems(story, self.held, fine), [])

    def test_the_merge_replaces_moves_removes_and_renames_and_keeps_a_held_test(self):
        story = [spec.entry("a", "R2", "line", ["- a: one"]), spec.entry("c", None, "line", ["- c: new"])]
        delta = spec.read_delta('## Spec delta\n- removes b\n- rule "R" → "R2"\n')
        merged = spec.merge(self.held, story, delta, {"c": ["x.T#c"]})
        self.assertEqual([(e["key"], e["rule"], e["tests"]) for e in merged],
                         [("a", "R2", ["x.T#a"]), ("c", None, ["x.T#c"])])

    def test_a_context_names_its_folder(self):
        self.assertEqual(spec.context_folder("Product Catalog"), "product-catalog")


class HandAndMigration(unittest.TestCase):

    def quiet(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            return args[0](*args[1:]), out.getvalue()

    def test_a_hand_delivery_merges_its_new_criteria_without_a_test_line_and_refuses_a_change(self):
        with project() as p:
            contract.set_places({})
            p.story("S-1", text=STORY)
            code, said = self.quiet(cli.deliver_by_hand, p.root, p.runs, p.epics, "S-1", "ana")
            self.assertEqual(code, 0, said)
            target = os.path.join(p.root, "product", "spec", "widgets", "scenarios.md")
            text = read(target)
            self.assertIn("#### shows-the-name", text)
            self.assertNotIn("Test:", text)
            p.story("S-2", text=STORY.replace("S-1", "S-2").replace('"Cog" is shown', '"Cog" is shown in bold'))
            self.assertEqual(self.quiet(cli.deliver_by_hand, p.root, p.runs, p.epics, "S-2", "ana")[0], 1)

    def test_the_migration_merges_delivered_stories_in_order_and_moves_a_glossary_out_of_the_code(self):
        with project() as p:
            contract.set_places({})
            p.story("S-1", text=STORY.replace("status: approved", "status: delivered\ndelivered: 2026-10-01T00:00:00Z"))
            p.run_file("S-1", "tests.md", "<!-- gate:tests -->\n| criterion | test |\n|---|---|\n"
                                          "| shows-the-name | a.WidgetTest#showsTheName |\n"
                                          "| lists-in-order | a.WidgetTest#listsInOrder |\n")
            write(os.path.join(p.root, "src", "main", "java", "a", "widgets", "domain", "glossary.md"), "# Widgets\n")
            said = []
            runner.migrate_glossaries(p.root, said.append)
            runner.migrate_spec(p.root, p.epics, p.runs, said.append)
            text = read(os.path.join(p.root, "product", "spec", "widgets", "scenarios.md"))
            self.assertIn("Test: a.WidgetTest#showsTheName", text)
            self.assertTrue(os.path.isfile(os.path.join(p.root, "product", "spec", "widgets", "glossary.md")))
            again = []
            runner.migrate_spec(p.root, p.epics, p.runs, again.append)
            self.assertEqual(again, [])


    def test_the_spec_check_names_a_delivered_criterion_the_spec_lacks(self):
        with project() as p:
            contract.set_places({})
            p.story("S-1", text=STORY.replace("status: approved", "status: delivered\ndelivered: 2026-10-01T00:00:00Z"))
            self.assertEqual(self.quiet(cli.spec_check, p.root, p.runs, p.epics)[0], 1)
            runner.migrate_spec(p.root, p.epics, p.runs, lambda _: None)
            self.assertEqual(self.quiet(cli.spec_check, p.root, p.runs, p.epics)[0], 0)


if __name__ == "__main__":
    unittest.main()
