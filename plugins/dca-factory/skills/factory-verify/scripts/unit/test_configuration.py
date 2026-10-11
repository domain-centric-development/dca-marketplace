"""The method's configuration (WP-99): `dca.profile.yaml` under the factory's profile, and the migration that
moves an older conventions file and the description section's places into it."""

import os
import unittest

from support import contract, project, write
from dca_factory import runner


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Layer(unittest.TestCase):

    def test_the_factory_profile_wins_and_the_method_fills_what_it_leaves_open(self):
        with project() as p:
            write(os.path.join(p.root, contract.METHOD_PROFILE), "root: docs/\noverview: docs/what.md\n"
                                                                 "verify_command: make arch\n")
            profile = write(os.path.join(p.root, contract.PROFILE_FILE), "test: make test\ntech: here/tech.md\n")
            read_back = contract.read_profile(profile)
            self.assertEqual(read_back["architecture"], "make arch")
            self.assertEqual(read_back["product"], "docs/what.md")
            self.assertEqual(read_back["tech"], "here/tech.md")
            self.assertEqual(read_back["domain"], "docs/domain.md")

    def test_without_a_method_profile_nothing_changes(self):
        with project() as p:
            profile = write(os.path.join(p.root, contract.PROFILE_FILE), "test: make test\n")
            self.assertEqual(contract.read_profile(profile), {"test": "make test"})


class Migration(unittest.TestCase):

    def test_the_conventions_file_and_the_sections_places_move_into_the_method_profile_once(self):
        with project() as p:
            write(os.path.join(p.root, ".agents", "dca", "conventions.md"),
                  "# DCA conventions\n\ncatalog_path: x\n\n## Resolved configuration\n\nverify_command: make arch\n")
            write(os.path.join(p.root, "AGENTS.md"),
                  "# P\n\n- conventions: `.agents/dca/conventions.md` — layout\n\n<!-- dca-describe: start -->\n"
                  "- product: `docs/what.md` — x\n- tech: `product/tech.md` — y\n<!-- dca-describe: end -->\n")
            said = []
            runner.migrate_configuration(p.root, said.append)
            method = contract.read_flat(os.path.join(p.root, contract.METHOD_PROFILE))
            self.assertEqual(method, {"catalog_path": "x", "verify_command": "make arch", "overview": "docs/what.md"})
            self.assertFalse(os.path.exists(os.path.join(p.root, ".agents", "dca", "conventions.md")))
            self.assertIn("- configuration: `dca.profile.yaml`", read(os.path.join(p.root, "AGENTS.md")))
            again = []
            runner.migrate_configuration(p.root, again.append)
            self.assertEqual(again, [])

    def test_a_section_naming_the_default_places_writes_no_place(self):
        with project() as p:
            write(os.path.join(p.root, "AGENTS.md"),
                  "<!-- dca-describe: start -->\n- product: `product/overview.md` — x\n- tech: `project/tech.md` — y\n"
                  "<!-- dca-describe: end -->\n")
            runner.migrate_configuration(p.root, lambda _: None)
            self.assertFalse(os.path.exists(os.path.join(p.root, contract.METHOD_PROFILE)))


if __name__ == "__main__":
    unittest.main()
