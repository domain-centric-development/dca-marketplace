"""The living spec (WP-98): a story's criteria as entries, the spec file read and written, the delta derived and
checked, the merge by key."""

import io
import contextlib
import os
import unittest

from support import project, write
from dca_factory import cli
from dca_factory.delivery.adapter.outgoing.files import migrations
from dca_factory.spec import api as spec
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles
from dca_factory.sharedkernel.adapter.outgoing.markdown import front_matter as markdown

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
        found = spec.story_entries(markdown.split_front(STORY)[1])
        self.assertEqual([(e["key"], e["rule"], e["form"]) for e in found],
                         [("shows-the-name", "A widget is shown with its name", "scenario"),
                          ("lists-in-order", "A widget is shown with its name", "line")])
        self.assertEqual(found[0]["lines"][0], "#### shows-the-name")
        self.assertEqual(found[1]["lines"], ["- lists-in-order: the widgets are listed by name,",
                                             "  the first one at the top."])

    def test_the_spec_file_reads_back_as_written(self):
        entries = spec.story_entries(markdown.split_front(STORY)[1])
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

    def test_a_delta_that_disagrees_is_named(self):
        story = [spec.entry("a", "S", "line", ["- a: one"])]
        delta = spec.read_delta('## Spec delta\n- adds a\n- removes zzz\n- rule "Q" → "S"\n')
        problems = spec.delta_problems(story, self.held, delta)
        self.assertTrue(any("`adds a`" in p for p in problems), problems)
        self.assertTrue(any("removes zzz" in p for p in problems), problems)
        self.assertTrue(any('rule "Q" — the spec has no such rule' in p for p in problems), problems)
        fine = spec.read_delta('## Spec delta\n- changes a\n- removes b: gone\n- rule "R" -> "S"\n')
        self.assertEqual(spec.delta_problems(story, self.held, fine), [])

    def test_a_renamed_rule_takes_the_criteria_it_holds_along_without_the_story_carrying_them(self):
        # #164: a story that rewords a rule and adds one criterion under it — the held ones follow the new text
        story = [spec.entry("c", "S", "line", ["- c: three"])]
        delta = spec.read_delta('## Spec delta\n- adds c\n- holds a\n- holds b\n- rule "R" → "S"\n')
        self.assertEqual(spec.delta_problems(story, self.held, delta), [])
        merged = spec.merge(self.held, story, delta, {"c": ["x.T#c"]})
        self.assertEqual([(e["key"], e["rule"], e["tests"]) for e in merged],
                         [("a", "S", ["x.T#a"]), ("b", "S", ["x.T#b"]), ("c", "S", ["x.T#c"])])
        self.assertEqual(spec.renamed_rules(story, self.held, delta), {"R": ["a", "b"]})
        without = spec.read_delta('## Spec delta\n- adds c\n- holds a\n')
        self.assertTrue(any("`holds a` — the story has no criterion" in p
                            for p in spec.delta_problems(story, self.held, without)))

    def test_a_rule_the_changed_expectations_reword_needs_its_rename(self):
        # #164: the .NET plan of the same story left the rename out; the story's own words said it
        story = [spec.entry("c", "S", "line", ["- c: three"])]
        changed = ['- The rule "R" reads \u201cS\u201d.']
        bare = spec.read_delta('## Spec delta\n- adds c\n')
        problems = spec.rule_problems(changed, story, self.held, bare)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('names the rule "R"', problems[0])
        self.assertIn("(a, b follow it)", problems[0])
        renamed = spec.read_delta('## Spec delta\n- adds c\n- rule "R" → "S"\n')
        self.assertEqual(spec.rule_problems(changed, story, self.held, renamed), [])
        emptied = spec.read_delta('## Spec delta\n- adds c\n- removes a: x\n- removes b: y\n')
        self.assertEqual(spec.rule_problems(changed, story, self.held, emptied), [])
        still = [spec.entry("c", "R", "line", ["- c: three"])]
        self.assertEqual(spec.rule_problems(changed, still, self.held, bare), [])

    def test_the_merge_replaces_moves_removes_and_renames_and_keeps_a_held_test(self):
        story = [spec.entry("a", "R2", "line", ["- a: one"]), spec.entry("c", None, "line", ["- c: new"])]
        delta = spec.read_delta('## Spec delta\n- removes b\n- rule "R" → "R2"\n')
        merged = spec.merge(self.held, story, delta, {"c": ["x.T#c"]})
        self.assertEqual([(e["key"], e["rule"], e["tests"]) for e in merged],
                         [("a", "R2", ["x.T#a"]), ("c", None, ["x.T#c"])])

    def test_a_rules_criteria_follow_the_order_the_delivering_story_lists_them_held_keys_included(self):
        # #136: one criterion delivered first, the rest by a later story — the spec holds the later story's order,
        # the same as where all came at once
        first = spec.merge([], [spec.entry("b", "R", "line", ["- b: two"])], spec.read_delta(""), {})
        story = [spec.entry("a", "R", "line", ["- a: one"]), spec.entry("b", "R", "line", ["- b: two"]),
                 spec.entry("c", "R", "line", ["- c: three"])]
        later = spec.merge(first, story, spec.read_delta(""), {})
        at_once = spec.merge([], story, spec.read_delta(""), {})
        self.assertEqual([e["key"] for e in later], ["a", "b", "c"])
        self.assertEqual(spec.render_spec([], later, "C"), spec.render_spec([], at_once, "C"))

    def test_the_storys_criteria_stand_together_where_the_first_of_them_stood(self):
        held = [spec.entry(k, "R", "line", [f"- {k}: {k}"]) for k in ("x", "b", "y")] \
            + [spec.entry("s", "S", "line", ["- s: s"])]
        story = [spec.entry("a", "R", "line", ["- a: a"]), spec.entry("b", "R", "line", ["- b: b"])]
        self.assertEqual([e["key"] for e in spec.merge(held, story, spec.read_delta(""), {})],
                         ["x", "a", "b", "y", "s"])
        alone = [spec.entry("y", "R", "line", ["- y: Y"])]          # one changed criterion keeps its place
        self.assertEqual([e["key"] for e in spec.merge(held, alone, spec.read_delta(""), {})], ["x", "b", "y", "s"])
        fresh = [spec.entry("n", "R", "line", ["- n: n"])]           # a new one goes to its rule's end
        self.assertEqual([e["key"] for e in spec.merge(held, fresh, spec.read_delta(""), {})],
                         ["x", "b", "y", "n", "s"])

    def test_a_context_names_its_folder(self):
        self.assertEqual(spec.context_folder("Product Catalog"), "product-catalog")


class HandAndMigration(unittest.TestCase):

    def quiet(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            return args[0](*args[1:]), out.getvalue()

    def test_a_hand_delivery_merges_its_new_criteria_without_a_test_line_and_refuses_a_change(self):
        with project() as p:
            profiles.set_places({})
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
            profiles.set_places({})
            p.story("S-1", text=STORY.replace("status: approved", "status: delivered\ndelivered: 2026-10-01T00:00:00Z"))
            p.run_file("S-1", "tests.md", "<!-- gate:tests -->\n| criterion | test |\n|---|---|\n"
                                          "| shows-the-name | a.WidgetTest#showsTheName |\n"
                                          "| lists-in-order | a.WidgetTest#listsInOrder |\n")
            write(os.path.join(p.root, "src", "main", "java", "a", "widgets", "domain", "glossary.md"), "# Widgets\n")
            said = []
            migrations.migrate_glossaries(p.root, said.append)
            migrations.migrate_spec(p.root, p.epics, p.runs, said.append)
            text = read(os.path.join(p.root, "product", "spec", "widgets", "scenarios.md"))
            self.assertIn("Test: a.WidgetTest#showsTheName", text)
            self.assertTrue(os.path.isfile(os.path.join(p.root, "product", "spec", "widgets", "glossary.md")))
            again = []
            migrations.migrate_spec(p.root, p.epics, p.runs, again.append)
            self.assertEqual(again, [])


    def test_the_migration_leaves_a_delivered_story_whose_criteria_stand_in_feature_folders(self):
        """WP-105: a criterion moved into a feature folder is held there — the update does not merge it back."""
        with project() as p:
            profiles.set_places({})
            p.story("S-1", text=STORY.replace("status: approved", "status: delivered\ndelivered: 2026-10-01T00:00:00Z"))
            migrations.migrate_spec(p.root, p.epics, p.runs, lambda _: None)
            root_file = os.path.join(p.root, "product", "spec", "widgets", "scenarios.md")
            preamble, entries = spec.read_spec(root_file)
            write(os.path.join(p.root, "product", "spec", "widgets", "naming", "scenarios.md"),
                  spec.render_spec([], entries, "widgets — naming"))
            os.remove(root_file)
            said = []
            migrations.migrate_spec(p.root, p.epics, p.runs, said.append)
            self.assertEqual(said, [])
            self.assertFalse(os.path.isfile(root_file))

    def test_the_migration_leaves_a_criterion_a_later_story_changed_and_adds_only_what_the_spec_lacks(self):
        """A delivered story whose criterion the spec holds in other words — a later story changed it, in a feature
        folder — is not merged back into its own file; a criterion of it the spec lacks is."""
        with project() as p:
            profiles.set_places({})
            p.story("S-1", text=STORY.replace("status: approved", "status: delivered\ndelivered: 2026-10-01T00:00:00Z"))
            changed = STORY.replace('"Cog" is shown', '"Cog" is shown in bold')
            later = spec.story_entries(changed.split("---", 2)[2])
            feature = os.path.join(p.root, "product", "spec", "widgets", "naming", "scenarios.md")
            write(feature, spec.render_spec([], [item for item in later if item["key"] == "shows-the-name"],
                                            "widgets — naming"))
            said = []
            migrations.migrate_spec(p.root, p.epics, p.runs, said.append)
            root_file = os.path.join(p.root, "product", "spec", "widgets", "scenarios.md")
            text = read(root_file)
            self.assertIn("lists-in-order", text)
            self.assertNotIn("shows-the-name", text)
            self.assertIn("in bold", read(feature))

    def test_the_migration_leaves_out_a_criterion_a_later_story_removed(self):
        with project() as p:
            profiles.set_places({})
            p.story("S-1", text=STORY.replace("status: approved", "status: delivered\ndelivered: 2026-10-01T00:00:00Z"))
            p.story("S-2", text=STORY.replace("S-1", "S-2").replace("status: approved",
                                                                    "status: delivered\ndelivered: 2026-10-02T00:00:00Z"))
            p.run_file("S-2", "plan.md", "# Plan\n\n## Spec delta\n- holds shows-the-name\n"
                                         "- removes lists-in-order: no longer wanted\n")
            root_file = os.path.join(p.root, "product", "spec", "widgets", "scenarios.md")
            write(root_file, spec.render_spec([], [item for item in spec.story_entries(STORY.split("---", 2)[2])
                                                   if item["key"] == "shows-the-name"], "widgets"))
            said = []
            migrations.migrate_spec(p.root, p.epics, p.runs, said.append)
            self.assertEqual(said, [])
            self.assertNotIn("lists-in-order", read(root_file))

    def test_the_spec_check_names_a_delivered_criterion_the_spec_lacks(self):
        with project() as p:
            profiles.set_places({})
            p.story("S-1", text=STORY.replace("status: approved", "status: delivered\ndelivered: 2026-10-01T00:00:00Z"))
            self.assertEqual(self.quiet(cli.spec_check, p.root, p.runs, p.epics)[0], 1)
            migrations.migrate_spec(p.root, p.epics, p.runs, lambda _: None)
            self.assertEqual(self.quiet(cli.spec_check, p.root, p.runs, p.epics)[0], 0)


class Layout(unittest.TestCase):

    def test_the_description_section_of_agents_md_follows_the_move_to_product(self):
        with project() as p:
            os.rename(os.path.join(p.root, "product"), os.path.join(p.root, "project"))
            write(os.path.join(p.root, "project", "product.md"), "# P\n")
            write(os.path.join(p.root, "AGENTS.md"), "<!-- dca-describe: start -->\n- product: `project/product.md` — x\n"
                                                     "- tech: `project/tech.md` — y\n<!-- dca-describe: end -->\n")
            with contextlib.redirect_stdout(io.StringIO()):
                migrations.migrate_layout(p.root)
            text = read(os.path.join(p.root, "AGENTS.md"))
            self.assertIn("`product/overview.md`", text)
            self.assertIn("`product/tech.md`", text)
            self.assertTrue(os.path.isfile(os.path.join(p.root, "product", "overview.md")))


if __name__ == "__main__":
    unittest.main()
