"""The files' contract: front matter, the profile, the story's fields, decision records, the stage table."""

import os
import tempfile
import unittest

from support import contract, project, write


class FrontMatter(unittest.TestCase):

    def read(self, text):
        with tempfile.TemporaryDirectory() as root:
            return contract.read_front_matter(write(os.path.join(root, "f.md"), text))

    def test_flat_keys_and_dash_lists_are_read_with_the_body(self):
        front, body = self.read("---\nid: S-1\ncontext: Widgets\ndepends_on:\n  - A\n  - B\n---\n# Title\n")
        self.assertEqual(front, {"id": "S-1", "context": "Widgets", "depends_on": ["A", "B"]})
        self.assertEqual(body, "\n# Title\n")

    def test_a_quoted_empty_value_is_empty(self):
        front, _ = self.read('---\ngoal: ""\nmetric: \'\'\nname: "kept"\n---\n')
        self.assertEqual(front, {"goal": [], "metric": [], "name": "kept"})

    def test_comments_and_blank_lines_are_skipped(self):
        front, _ = self.read("---\n# a comment\n\nid: S-1\n---\n")
        self.assertEqual(front, {"id": "S-1"})

    def test_a_value_keeps_its_colons(self):
        front, _ = self.read("---\nurl: http://host:8080/x\n---\n")
        self.assertEqual(front["url"], "http://host:8080/x")

    def test_a_file_without_front_matter_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "no front matter"):
            self.read("# Title\n")

    def test_front_matter_not_closed_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "not closed"):
            self.read("---\nid: S-1\n")

    def test_a_line_without_a_colon_is_refused(self):
        with self.assertRaisesRegex(contract.GateError, "cannot read front-matter line"):
            self.read("---\nid S-1\n---\n")


class Profile(unittest.TestCase):

    def test_a_missing_profile_is_empty(self):
        self.assertEqual(contract.read_profile(None), {})
        self.assertEqual(contract.read_profile("/no/such/profile.yaml"), {})

    def test_keys_are_flat_quotes_go_comments_are_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            path = write(os.path.join(root, "p.yaml"),
                         "# profile\ncontract: 17\ntest: \"gradle test --tests '{class}' -q\"\nformat: 'spotless'\n"
                         "model.claude.build: opus\nnot a key\n")
            self.assertEqual(contract.read_profile(path), {
                "contract": "17", "test": "gradle test --tests '{class}' -q", "format": "spotless",
                "model.claude.build": "opus"})

    @unittest.expectedFailure
    def test_a_double_quoted_value_keeps_a_single_quote_at_its_end(self):
        # read_profile strips `"` and then `'` from both ends, so a command ending in a quoted argument loses
        # its closing quote — kept as a known defect until the reader takes one pair of quotes only
        with tempfile.TemporaryDirectory() as root:
            path = write(os.path.join(root, "p.yaml"), "test: \"gradle test --tests '{class}'\"\n")
            self.assertEqual(contract.read_profile(path)["test"], "gradle test --tests '{class}'")

    def test_location_falls_back_to_the_default_place(self):
        self.assertEqual(contract.location({}, "epics"), "project/epics")
        self.assertEqual(contract.location({"epics": "docs\\epics"}, "epics"), "docs/epics")


class StoryFields(unittest.TestCase):

    def test_depends_on_reads_three_shapes(self):
        self.assertEqual(contract.depends_on({"depends_on": "[A, 'B', \"C\"]"}), ["A", "B", "C"])
        self.assertEqual(contract.depends_on({"depends_on": ["A", "B"]}), ["A", "B"])
        self.assertEqual(contract.depends_on({"depends_on": "[]"}), [])
        self.assertEqual(contract.depends_on({"depends_on": []}), [])
        self.assertEqual(contract.depends_on({}), [])

    def test_story_kind_from_kind_and_status(self):
        self.assertEqual(contract.story_kind({"kind": "Journey"}), "journey")
        self.assertEqual(contract.story_kind({"status": "adopted"}), "adopt")
        self.assertEqual(contract.story_kind({"status": "approved"}), "story")
        self.assertEqual(contract.story_kind({}), "story")

    def test_delivered_by_status_or_by_a_date(self):
        self.assertTrue(contract.is_delivered({"status": "Delivered"}))
        self.assertTrue(contract.is_delivered({"status": "adopted", "delivered": "2026-10-10"}))
        self.assertFalse(contract.is_delivered({"status": "adopted", "delivered": []}))
        self.assertFalse(contract.is_delivered({"status": "approved"}))

    def test_a_story_id_is_its_id_else_its_folder(self):
        with project() as p:
            named = p.story("S-1")
            unnamed = p.story("folder-name", text="---\nstatus: approved\n---\n")
            self.assertEqual(contract.story_id_of(named), "S-1")
            self.assertEqual(contract.story_id_of(unnamed), "folder-name")

    def test_the_story_digest_ignores_status_and_delivered(self):
        with project() as p:
            path = p.story("S-1")
            before = contract.story_digest(path)
            p.story("S-1", status="delivered")
            self.assertEqual(contract.story_digest(path), before)
            p.story("S-1", text=contract.read_text(path) + "more\n")
            self.assertNotEqual(contract.story_digest(path), before)

    def test_find_story_refuses_a_second_story_with_the_same_id(self):
        with project() as p:
            p.story("S-1", epic="one")
            p.story("S-1", epic="two")
            with self.assertRaisesRegex(contract.GateError, "is not unique"):
                contract.find_story(p.epics, "S-1")
            self.assertEqual(list(contract.duplicate_ids(p.epics)), ["s-1"])

    def test_find_story_names_the_flat_layout(self):
        with project() as p:
            p.epic("sample")
            write(os.path.join(p.epics, "sample", "S-9.md"), "---\nid: S-9\n---\n")
            with self.assertRaisesRegex(contract.GateError, "older flat layout"):
                contract.find_story(p.epics, "S-9")


class Selectors(unittest.TestCase):

    def test_a_selector_is_a_qualified_class_and_a_method(self):
        self.assertEqual(contract.SELECTOR.match("com.example.WidgetTest#showsIt").groups(),
                         ("com.example.WidgetTest", "showsIt"))
        self.assertIsNone(contract.SELECTOR.match("com.example.WidgetTest.showsIt"))
        self.assertIsNone(contract.SELECTOR.match("WidgetTest#shows it"))

    def test_a_mapping_row_is_key_and_first_cell(self):
        row = contract.MAPPING_ROW.match("| shows-the-thing | com.example.WidgetTest#showsIt | end-to-end |")
        self.assertEqual(row.groups(), ("shows-the-thing", "com.example.WidgetTest#showsIt"))
        self.assertIsNone(contract.MAPPING_ROW.match("| Shows-The-Thing | x#y |"))


class Decisions(unittest.TestCase):

    def test_a_record_without_an_answer_is_open(self):
        self.assertEqual(contract.decision_state("## Question\nwhich?\n")[0], "open")

    def test_an_answer_missing_a_field_is_a_draft(self):
        self.assertEqual(contract.decision_state("## Answer\nanswer: a\nby: someone\n")[0], "draft")

    def test_an_answer_with_answer_by_and_at_is_answered(self):
        status, answer = contract.decision_state("## Answer\n- answer: a\n- by: someone\n- at: 2026-10-10\n")
        self.assertEqual(status, "answered")
        self.assertEqual(answer, {"answer": "a", "by": "someone", "at": "2026-10-10"})

    def test_an_applied_section_wins(self):
        self.assertEqual(contract.decision_state("## Answer\nanswer: a\n\n## Applied\nstage: plan\n")[0], "applied")

    def test_needs_human_names_the_ids_and_nothing_for_an_empty_section(self):
        self.assertIsNone(contract.needs_human_ids("# plan\n"))
        self.assertIsNone(contract.needs_human_ids("## needs-human\n(none)\n"))
        self.assertIsNone(contract.needs_human_ids("## needs-human\n- None.\n"))
        self.assertEqual(contract.needs_human_ids("## needs-human\ndecision: `S-1-01`. The browser …\n"), ["S-1-01"])
        self.assertEqual(contract.needs_human_ids("## needs-human\nwhy: nobody can say\n"), [])

    def test_a_record_lies_beside_its_own_story_under_its_own_name(self):
        with project() as p:
            path = p.story("S-1")
            store = contract.decisions_store(path)
            write(os.path.join(store, "01.md"), "---\nid: S-1-01\nstory: S-1\nstage: plan\n---\n## Question\n")
            records = contract.read_decisions(store, "S-1")
            self.assertEqual([(r[1]["id"], r[3]) for r in records], [("S-1-01", "open")])
            write(os.path.join(store, "02.md"), "---\nid: S-1-03\nstory: S-1\n---\n")
            with self.assertRaisesRegex(contract.GateError, "is named '02'"):
                contract.read_decisions(store, "S-1")

    def test_a_record_naming_another_story_is_refused(self):
        with project() as p:
            store = contract.decisions_store(p.story("S-1"))
            write(os.path.join(store, "01.md"), "---\nid: S-1-01\nstory: S-2\n---\n")
            with self.assertRaisesRegex(contract.GateError, "names story 'S-2'"):
                contract.read_decisions(store, "S-1")

    def test_an_answer_resumes_at_the_earlier_of_the_asking_and_the_named_stage(self):
        self.assertEqual(contract.applying_stage({"stage": "plan"}, {"applies": "test"}), "test")
        self.assertEqual(contract.applying_stage({"stage": "plan"}, {"applies": "nowhere"}), "plan")
        self.assertEqual(contract.resume_stage({"stage": "plan"}, {"applies": "test"}), "plan")
        self.assertEqual(contract.resume_stage({"stage": "build"}, {"applies": "test"}), "test")
        self.assertEqual(contract.resume_stage({"stage": "build"}, {}), "build")


class StageTable(unittest.TestCase):

    def test_the_run_order_of_each_kind(self):
        self.assertEqual(contract.stage_order("story"), ("plan", "test", "build", "tidy", "judge", "document"))
        self.assertEqual(contract.stage_order("journey"), ("plan", "test", "judge", "document"))
        self.assertEqual(contract.stage_order("adopt"), ("plan", "test", "judge"))
        self.assertEqual(contract.STAGE_ORDER, contract.stage_order())

    def test_adopt_and_integrate_are_rows_outside_the_run_order(self):
        self.assertEqual([s.name for s in contract.STAGES if not s.in_order], ["adopt", "integrate"])
        self.assertNotIn("integrate", contract.STAGE_FILES)
        self.assertEqual(contract.STAGE["integrate"].file, "integrate.md")

    def test_each_stage_writes_its_own_file(self):
        self.assertEqual(contract.STAGE_FILES, {"plan": "plan.md", "test": "tests.md", "build": "build.md",
                                                "tidy": "tidy.md", "judge": "judge.md", "document": "document.md"})

    def test_the_shared_windows_carry_their_stages(self):
        self.assertEqual(contract.SHARED_WINDOWS, {"builder": ("plan", "test", "build", "tidy"),
                                                  "verifier": ("judge", "document")})

    def test_the_gated_stages_and_their_commands(self):
        self.assertNotIn("judge", contract.STAGE_CHECKS)
        self.assertEqual(contract.STAGE_CHECKS["build"], ("architecture", "format"))
        self.assertEqual(contract.STAGE_CHECKS["document"], ("architecture",))
        self.assertEqual(contract.POST_GATED, ("test", "build", "tidy", "document"))


class Epics(unittest.TestCase):

    def test_epics_in_dependency_order_with_a_cycle_last(self):
        order, cycle = contract.epic_order({"a": ["b"], "b": [], "c": ["d"], "d": ["c"], "e": ["unknown"]})
        self.assertEqual(order, ["b", "a", "e", "c", "d"])
        self.assertEqual(cycle, {"c", "d"})

    def test_an_epic_dependency_that_cannot_hold_is_named(self):
        with project() as p:
            p.epic("a", deps=("b",))
            p.epic("b", deps=("a",))
            p.epic("c", deps=("c",))
            p.epic("d", deps=("nowhere",))
            p.epic("e")
            self.assertIn("dependency cycle", contract.epic_dependency_problem(p.epics, "a"))
            self.assertIn("depends on itself", contract.epic_dependency_problem(p.epics, "c"))
            self.assertIn("'nowhere', which is no epic", contract.epic_dependency_problem(p.epics, "d"))
            self.assertIsNone(contract.epic_dependency_problem(p.epics, "e"))


if __name__ == "__main__":
    unittest.main()
