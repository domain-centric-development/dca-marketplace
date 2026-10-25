"""#151: a merge's resolution keeps the main line's side of every test it met — what the main line added to a test
while the story ran is held, the lines it kept from the base stay the story's to change."""

import os
import subprocess
import tempfile
import unittest

from support import write
from dca_factory.sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from dca_factory import gate
from dca_factory.delivery.adapter.outgoing.git import integration


def git(cwd, *args, check=True):
    done = subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, capture_output=True,
                          text=True, check=check)
    return done.stdout.strip()


TEST = "src/test/java/com/example/ShopTest.java"
BASE = "class ShopTest {\n  @Test void opens() { assertTrue(shop.open()); }\n}\n"
MAIN = "class ShopTest {\n  @Test void opens() { assertTrue(shop.open()); }\n  @Test void sideShop() { assertTrue(side.open()); }\n}\n"
STORY = "class ShopTest {\n  @Test void opens() { assertTrue(shop.open()); }\n  @Test void closes() { assertFalse(shop.open()); }\n}\n"


class MainTests(unittest.TestCase):

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = self.scratch.name
        self.runs = os.path.join(self.root, ".dca-factory", "runs")
        git(self.root, "init", "-q", "-b", "main")
        write(os.path.join(self.root, ".gitignore"), ".dca-factory/\n")
        write(os.path.join(self.root, TEST), BASE)
        write(os.path.join(self.root, "src/main/Other.java"), "class Other {}\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        git(self.root, "checkout", "-q", "-b", "story/STORY-1")
        write(os.path.join(self.root, TEST), STORY)
        git(self.root, "commit", "-qam", "the story's case")
        git(self.root, "checkout", "-q", "main")
        write(os.path.join(self.root, TEST), MAIN)
        write(os.path.join(self.root, "src/main/Other.java"), "class Other { int a; }\n")
        git(self.root, "commit", "-qam", "another story's case")
        git(self.root, "checkout", "-q", "story/STORY-1")
        git(self.root, "merge", "--no-edit", "-q", "main", check=False)      # stops on the test both changed
        integration.record_main_tests(self.root, self.runs, "STORY-1", "main")

    def tearDown(self):
        self.scratch.cleanup()

    def resolve(self, text):
        write(os.path.join(self.root, TEST), text)

    def test_the_record_holds_the_tests_the_main_line_changed_with_both_versions(self):
        with open(os.path.join(evidence_dir(self.runs, "STORY-1"), integration.MAIN_TESTS), encoding="utf-8") as handle:
            rows = [line.split("\t") for line in handle.read().splitlines()]
        self.assertEqual([row[2] for row in rows], [TEST])          # a production file the main line changed is no test
        self.assertNotEqual(rows[0][0], rows[0][1])

    def test_a_resolution_that_takes_the_storys_side_whole_loses_the_main_lines_case(self):
        self.resolve(STORY)
        lost = integration.main_tests_lost(self.root, self.runs, "STORY-1")
        self.assertEqual([rel for rel, _ in lost], [TEST])
        self.assertTrue(any("sideShop" in line for line in lost[0][1]))
        result = gate.Result()
        gate.check_main_tests(result, self.root, self.runs, "STORY-1")
        self.assertIn("main-tests", {check for kind, check, _ in result.entries if kind == "fail"})

    def test_both_cases_kept_hold_and_the_story_may_still_change_what_the_base_had(self):
        self.resolve(STORY.replace("\n}\n", "\n  @Test void sideShop() { assertTrue(side.open()); }\n}\n"))
        self.assertEqual(integration.main_tests_lost(self.root, self.runs, "STORY-1"), [])
        # a line the main line kept from the base is the story's to change — tests-kept judges that, not this check
        self.resolve(MAIN.replace("assertTrue(shop.open())", "assertTrue(shop.isOpen())"))
        self.assertEqual(integration.main_tests_lost(self.root, self.runs, "STORY-1"), [])
        result = gate.Result()
        gate.check_main_tests(result, self.root, self.runs, "STORY-1")
        self.assertIn("main-tests", {check for kind, check, _ in result.entries if kind == "pass"})

    def test_a_test_file_the_resolution_removed_is_lost_whole(self):
        os.remove(os.path.join(self.root, TEST))
        self.assertEqual(integration.main_tests_lost(self.root, self.runs, "STORY-1"), [(TEST, ["(the file is gone)"])])

    def answer(self, stage, answered=True):
        """A record of the story, asked at <stage>, that names the test file; answered by a person or still open."""
        folder = os.path.join(self.root, "product", "epics", "sample", "STORY-1")
        write(os.path.join(folder, "story.md"), "---\nid: STORY-1\nstatus: approved\n---\n# STORY-1\n")
        answer = "\n## Answer\nanswer: a\nby: the-expert\nat: 2026-10-21T18:30:00Z\n" if answered else ""
        write(os.path.join(folder, "decisions", "01.md"),
              f"---\nid: STORY-1-01\nstory: STORY-1\nstage: {stage}\n---\n# Keep the merged helpers?\n\n"
              f"## Question\n`{TEST}` lost a line that no longer compiles.\n\n## Options\n- a: keep the merge\n{answer}")

    def test_a_record_that_names_the_file_by_its_name_alone_waives_it_and_a_longer_name_does_not(self):
        self.resolve(STORY)
        self.answer("integrate")
        record = os.path.join(self.root, "product", "epics", "sample", "STORY-1", "decisions", "01.md")
        with open(record, encoding="utf-8") as handle:
            text = handle.read()
        write(record, text.replace(f"`{TEST}`", "`OtherShopTest.java`"))
        self.assertEqual([rel for rel, _ in integration.main_tests_lost(self.root, self.runs, "STORY-1")], [TEST])
        write(record, text.replace(f"`{TEST}`", "`ShopTest.java`"))
        self.assertEqual(integration.main_tests_lost(self.root, self.runs, "STORY-1"), [])

    def test_a_file_an_answered_integrate_decision_names_is_not_asked_back(self):
        self.resolve(STORY)
        self.answer("integrate", answered=False)
        self.assertEqual([rel for rel, _ in integration.main_tests_lost(self.root, self.runs, "STORY-1")], [TEST])
        self.answer("build")
        self.assertEqual([rel for rel, _ in integration.main_tests_lost(self.root, self.runs, "STORY-1")], [TEST])
        self.answer("integrate")
        self.assertEqual(integration.main_tests_lost(self.root, self.runs, "STORY-1"), [])
        result = gate.Result()
        gate.check_main_tests(result, self.root, self.runs, "STORY-1")
        kinds = {kind for kind, check, _ in result.entries if check == "main-tests"}
        self.assertNotIn("fail", kinds)
        self.assertTrue(any("STORY-1-01" in message for _k, check, message in result.entries if check == "main-tests"))


SHOP = "src/main/java/com/example/Shop.java"
R_BASE = ("class ShopTest {\n  @Test void opens() {\n    assertTrue(shop.open());\n  }\n}\n")
R_MAIN = ("class ShopTest {\n  @Test void opens() {\n    assertTrue(shop.open());\n  }\n"
          "  @Test void sideShop() {\n    assertTrue(side.open());\n  }\n}\n")
R_STORY = ("class ShopTest {\n  @Test void opens() {\n    assertTrue(shop.open(9));\n  }\n}\n")


class ResignedHelpers(unittest.TestCase):
    """#163: a main-line test line that calls what the story re-signed was adapted by the merge, not lost — while a
    case that went whole is still asked back."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = self.scratch.name
        self.runs = os.path.join(self.root, ".dca-factory", "runs")
        git(self.root, "init", "-q", "-b", "main")
        write(os.path.join(self.root, ".gitignore"), ".dca-factory/\n")
        write(os.path.join(self.root, TEST), R_BASE)
        write(os.path.join(self.root, SHOP), "class Shop {\n  public boolean open() { return true; }\n}\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "base")
        git(self.root, "checkout", "-q", "-b", "story/STORY-1")
        write(os.path.join(self.root, TEST), R_STORY)
        write(os.path.join(self.root, SHOP), "class Shop {\n  public boolean open(int hour) { return hour > 8; }\n}\n")
        git(self.root, "commit", "-qam", "the story re-signs open")
        git(self.root, "checkout", "-q", "main")
        write(os.path.join(self.root, TEST), R_MAIN)
        git(self.root, "commit", "-qam", "another story's case")
        git(self.root, "checkout", "-q", "story/STORY-1")
        integration.record_main_tests(self.root, self.runs, "STORY-1", "main")    # as the merge would stop
        git(self.root, "merge", "--no-edit", "-q", "main", check=False)
        write(os.path.join(evidence_dir(self.runs, "STORY-1"), "target"), "main\n")

    def tearDown(self):
        self.scratch.cleanup()

    def resolve(self, text):
        write(os.path.join(self.root, TEST), text)

    def test_a_case_adapted_to_the_new_signature_is_not_lost_and_is_named(self):
        self.resolve(R_STORY.replace("\n}\n", "\n  @Test void sideShop() {\n    assertTrue(side.open(9));\n  }\n}\n"))
        self.assertEqual(integration.main_tests_lost(self.root, self.runs, "STORY-1"), [])
        self.assertEqual(integration.main_tests_adapted(self.root, self.runs, "STORY-1"), [(TEST, ["assertTrue(side.open());"])])
        result = gate.Result()
        gate.check_main_tests(result, self.root, self.runs, "STORY-1")
        self.assertIn("main-tests", {check for kind, check, _ in result.entries if kind == "pass"})

    def test_a_case_that_went_whole_is_still_lost(self):
        self.resolve(R_STORY)
        lost = integration.main_tests_lost(self.root, self.runs, "STORY-1")
        self.assertEqual([rel for rel, _ in lost], [TEST])
        self.assertIn("@Test void sideShop() {", lost[0][1])

    def test_a_line_calling_what_the_story_left_alone_is_lost(self):
        write(os.path.join(self.root, SHOP), "class Shop {\n  public boolean open() { return true; }\n}\n")
        self.resolve(R_STORY.replace("\n}\n", "\n  @Test void sideShop() {\n    assertTrue(side.open(9));\n  }\n}\n"))
        lost = integration.main_tests_lost(self.root, self.runs, "STORY-1")
        self.assertEqual(lost, [(TEST, ["assertTrue(side.open());"])])


if __name__ == "__main__":
    unittest.main()
