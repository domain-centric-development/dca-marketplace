"""`tests-kept` lets a test follow a type or a method the story renamed — read from the tree, never from a claim."""

import os
import subprocess
import unittest

from support import evidence, gate_story, project, write
from dca_factory.delivery.domain.model.stage_story import Presence
from dca_factory.delivery.domain.service.kept_checks import KeptChecks
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles

JAVA_TEST = "src/test/java/OrderTest.java"
CS_TEST = "tests/OrderTest.cs"


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


class Renamed(unittest.TestCase):

    def baseline(self, p, files, test):
        """The project before the story: `files` committed, the tests baseline and the base tree recorded."""
        git(p.root, "init", "-q")
        git(p.root, "config", "user.email", "jane@example.com")
        git(p.root, "config", "user.name", "Jane")
        for rel, text in files.items():
            write(os.path.join(p.root, rel), text)
        git(p.root, "add", "-A")
        git(p.root, "commit", "-q", "-m", "base")
        p.evidence("S-1", profiles_baseline(), f"{git(p.root, 'rev-parse', f'HEAD:{test}')}  {test}\n")
        p.evidence("S-1", "base-tree", git(p.root, "rev-parse", "HEAD^{tree}") + "\n")

    def story(self, p, files, removed=()):
        for rel in removed:
            os.remove(os.path.join(p.root, rel))
        for rel, text in files.items():
            write(os.path.join(p.root, rel), text)
        return evidence(p.root, p.runs).kept_tests(gate_story("S-1").story)

    def test_a_renamed_type_is_followed_and_noted(self):
        with project() as p:
            self.baseline(p, {"src/main/java/OldFailure.java": "class OldFailure extends RuntimeException {}\n",
                              JAVA_TEST: "class OrderTest {\n  void t() {\n"
                                         "    assertThrows(OldFailure.class, () -> order.confirm());\n  }\n}\n"},
                          JAVA_TEST)
            kept = self.story(p, {"src/main/java/NewFailure.java": "class NewFailure extends RuntimeException {}\n",
                                  JAVA_TEST: "class OrderTest {\n  void t() {\n"
                                             "    assertThrows(NewFailure.class, () -> order.confirm());\n  }\n}\n"},
                              removed=("src/main/java/OldFailure.java",))
            self.assertEqual(kept.changed, ())
            self.assertEqual([(r.was.value, r.now.value) for r in kept.renamed[0].renames], [("OldFailure", "NewFailure")])
            notes = " ".join(f.said.value for f in KeptChecks.tests_kept(gate_story("S-1"), evidence(p.root, p.runs)))
            self.assertIn("follows a rename the story made — OldFailure → NewFailure (in no glossary)", notes)

    def test_the_note_says_when_a_glossary_names_the_new_name(self):
        with project() as p:
            self.baseline(p, {"src/main/java/OldFailure.java": "class OldFailure {}\n",
                              JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThrows(OldFailure.class, x);\n  }\n}\n"},
                          JAVA_TEST)
            write(os.path.join(p.root, "product/spec/orders/glossary.md"), "### Changed order (NewFailure)\n")
            kept = self.story(p, {"src/main/java/NewFailure.java": "class NewFailure {}\n",
                                  JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThrows(NewFailure.class, x);\n  }\n}\n"},
                              removed=("src/main/java/OldFailure.java",))
            self.assertIs(kept.renamed[0].renames[0].in_glossary, Presence.PRESENT)

    def test_a_rename_with_a_changed_literal_still_changes_the_test(self):
        with project() as p:
            self.baseline(p, {"src/main/java/OldFailure.java": "class OldFailure {}\n",
                              JAVA_TEST: "class OrderTest {\n  void t() {\n"
                                         "    assertEquals(\"late\", thrown(OldFailure.class));\n  }\n}\n"},
                          JAVA_TEST)
            kept = self.story(p, {"src/main/java/NewFailure.java": "class NewFailure {}\n",
                                  JAVA_TEST: "class OrderTest {\n  void t() {\n"
                                             "    assertEquals(\"early\", thrown(NewFailure.class));\n  }\n}\n"},
                              removed=("src/main/java/OldFailure.java",))
            self.assertEqual([c.place.value for c in kept.changed], [JAVA_TEST])

    def test_an_alias_is_no_rename(self):
        with project() as p:
            self.baseline(p, {"src/main/java/OldFailure.java": "class OldFailure {}\n",
                              JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThrows(OldFailure.class, x);\n  }\n}\n"},
                          JAVA_TEST)
            kept = self.story(p, {"src/main/java/NewFailure.java": "class NewFailure extends OldFailure {}\n",
                                  JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThrows(NewFailure.class, x);\n  }\n}\n"})
            self.assertEqual([c.place.value for c in kept.changed], [JAVA_TEST])

    def test_two_types_merged_into_one_are_two_renames(self):
        with project() as p:
            self.baseline(p, {"src/main/java/LateFailure.java": "class LateFailure {}\n",
                              "src/main/java/GoneFailure.java": "class GoneFailure {}\n",
                              JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThrows(LateFailure.class, x);\n"
                                         "    assertThrows(GoneFailure.class, y);\n  }\n}\n"},
                          JAVA_TEST)
            kept = self.story(p, {"src/main/java/OrderFailure.java": "class OrderFailure {}\n",
                                  JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThrows(OrderFailure.class, x);\n"
                                             "    assertThrows(OrderFailure.class, y);\n  }\n}\n"},
                              removed=("src/main/java/LateFailure.java", "src/main/java/GoneFailure.java"))
            self.assertEqual(kept.changed, ())
            self.assertEqual(len(kept.renamed[0].renames), 2)

    def test_the_csharp_twin_follows_a_renamed_type(self):
        with project() as p:
            self.baseline(p, {"src/Orders/OldFailure.cs": "public sealed class OldFailure : Exception {}\n",
                              CS_TEST: "public class OrderTest {\n  [Fact] public void T() {\n"
                                       "    Assert.Throws<OldFailure>(() => order.Confirm());\n  }\n}\n"},
                          CS_TEST)
            kept = self.story(p, {"src/Orders/NewFailure.cs": "public sealed class NewFailure : Exception {}\n",
                                  CS_TEST: "public class OrderTest {\n  [Fact] public void T() {\n"
                                           "    Assert.Throws<NewFailure>(() => order.Confirm());\n  }\n}\n"},
                              removed=("src/Orders/OldFailure.cs",))
            self.assertEqual(kept.changed, ())
            self.assertTrue(kept.renamed)

    def test_a_renamed_page_object_method_is_followed(self):
        with project() as p:
            page = "tests/Pages/AccountPage.cs"
            self.baseline(p, {page: "public class AccountPage {\n  public bool ShowsFindings() => true;\n}\n",
                              CS_TEST: "public class OrderTest {\n  [Fact] public void T() {\n"
                                       "    Assert.True(page.ShowsFindings());\n  }\n}\n"},
                          CS_TEST)
            kept = self.story(p, {page: "public class AccountPage {\n  public bool ShowsOpenFindings() => true;\n}\n",
                                  CS_TEST: "public class OrderTest {\n  [Fact] public void T() {\n"
                                           "    Assert.True(page.ShowsOpenFindings());\n  }\n}\n"})
            self.assertEqual(kept.changed, ())
            self.assertEqual(kept.renamed[0].renames[0].now.value, "ShowsOpenFindings")

    def test_a_method_rename_needs_the_base_tree(self):
        with project() as p:
            page = "tests/Pages/AccountPage.cs"
            self.baseline(p, {page: "public class AccountPage {\n  public bool ShowsFindings() => true;\n}\n",
                              CS_TEST: "public class OrderTest {\n  [Fact] public void T() {\n"
                                       "    Assert.True(page.ShowsFindings());\n  }\n}\n"},
                          CS_TEST)
            os.remove(os.path.join(profiles.evidence_dir(p.runs, "S-1"), "base-tree"))
            kept = self.story(p, {page: "public class AccountPage {\n  public bool ShowsOpenFindings() => true;\n}\n",
                                  CS_TEST: "public class OrderTest {\n  [Fact] public void T() {\n"
                                           "    Assert.True(page.ShowsOpenFindings());\n  }\n}\n"})
            self.assertEqual([c.place.value for c in kept.changed], [CS_TEST])

    def test_a_swapped_library_matcher_is_no_rename(self):
        with project() as p:
            self.baseline(p, {JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThat(order.open()).isTrue();\n  }\n}\n"},
                          JAVA_TEST)
            write(os.path.join(p.root, "src/main/java/Checks.java"), "class Checks {\n  boolean isFalse() {}\n}\n")
            kept = self.story(p, {JAVA_TEST: "class OrderTest {\n  void t() {\n    assertThat(order.open()).isFalse();\n  }\n}\n"})
            self.assertEqual([c.place.value for c in kept.changed], [JAVA_TEST])


def profiles_baseline():
    from dca_factory.delivery.adapter.outgoing.files.kept_files import TESTS_BASELINE
    return TESTS_BASELINE


if __name__ == "__main__":
    unittest.main()
