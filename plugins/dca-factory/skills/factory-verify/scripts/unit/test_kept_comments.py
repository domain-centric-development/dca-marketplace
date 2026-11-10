"""`tests-kept` reads a test without its comments as the compiler does: a `//` or `/*` inside a string is text."""

import os
import subprocess
import unittest

from support import evidence, gate_story, project, write
from dca_factory.delivery.adapter.outgoing.files.kept_files import TESTS_BASELINE, meaningful_lines

JAVA_TEST = "src/test/java/PageTest.java"

BEFORE = """class PageTest {
  private static final String ITEM = "//*[@data-test='task-item']";
  private static final String FORM = "//form[@data-test='create']";

  void listsTheTask() {
    assertXpath(ITEM, "Milch");
  }
}
"""

# Purely additive: a new constant, a new test and a helper with a doc comment — every old line stays, in order.
AFTER = """class PageTest {
  private static final String ITEM = "//*[@data-test='task-item']";
  private static final String BUTTON = "//*[@data-test='complete']";
  private static final String FORM = "//form[@data-test='create']";

  void listsTheTask() {
    assertXpath(ITEM, "Milch");
  }

  void completesTheTask() {
    assertXpath(BUTTON, "erledigt");
  }

  /** The row of the task with this title. */
  private static String row(String title) {
    return ITEM + "[.='" + title + "']";
  }
}
"""


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


class KeptComments(unittest.TestCase):

    def test_a_comment_mark_inside_a_string_is_text(self):
        lines = meaningful_lines('a = "//*[@id=\'x\']"; // gone\nb = "/* kept */"; /* gone */ c();\n', JAVA_TEST)
        self.assertEqual(lines, ['a = "//*[@id=\'x\']";', 'b = "/* kept */";  c();'])

    def test_a_block_comment_keeps_the_lines_after_it_in_place(self):
        lines = meaningful_lines("a();\n/* one\n   two */\nb(); // c();\n", JAVA_TEST)
        self.assertEqual(lines, ["a();", "b();"])

    def test_a_commented_out_assertion_is_still_gone(self):
        self.assertEqual(meaningful_lines("/*\n  assertEquals(1, x);\n*/\nok();\n", JAVA_TEST), ["ok();"])

    def test_an_addition_beside_xpath_strings_and_a_doc_comment_keeps_the_test(self):
        with project() as p:
            git(p.root, "init", "-q")
            git(p.root, "config", "user.email", "jane@example.com")
            git(p.root, "config", "user.name", "Jane")
            write(os.path.join(p.root, JAVA_TEST), BEFORE)
            git(p.root, "add", "-A")
            git(p.root, "commit", "-q", "-m", "base")
            p.evidence("S-1", TESTS_BASELINE, f"{git(p.root, 'rev-parse', f'HEAD:{JAVA_TEST}')}  {JAVA_TEST}\n")
            p.evidence("S-1", "base-tree", git(p.root, "rev-parse", "HEAD^{tree}") + "\n")
            write(os.path.join(p.root, JAVA_TEST), AFTER)
            kept = evidence(p.root, p.runs).kept_tests(gate_story("S-1").id)
            self.assertEqual(kept.changed, ())


if __name__ == "__main__":
    unittest.main()
