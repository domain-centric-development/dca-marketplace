"""The skills an update copies into a project are committed with it: no folder of theirs may carry a name a project's
`.gitignore` drops as build output — a Gradle project ignores `build/`, and a clone without the folder cannot import
the package."""

import os
import tempfile
import unittest

import support

SKILLS = os.path.dirname(os.path.dirname(support.SCRIPTS))

#: Folder names the common `.gitignore` templates drop as build output or a tool's cache (Gradle, Maven, .NET,
#: Node, Python, IDEs).
IGNORED_BY_PROJECTS = frozenset(("build", "bin", "obj", "out", "target", "dist", "node_modules", "coverage", "tmp",
                                 "temp", "logs", "venv", "env"))
#: Caches the verify suite leaves beside its own files; an update never copies them.
LOCAL = frozenset(("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"))


def ignored_folders(root):
    found = []
    for folder, subfolders, _files in os.walk(root):
        subfolders[:] = [name for name in subfolders if name not in LOCAL]
        found += [os.path.relpath(os.path.join(folder, name), root) for name in subfolders
                  if name.lower() in IGNORED_BY_PROJECTS]
    return sorted(found)


class ShippedFoldersTest(unittest.TestCase):

    def test_no_shipped_folder_is_one_a_project_ignores(self):
        self.assertEqual([], ignored_folders(SKILLS))

    def test_a_build_folder_is_found(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "factory-run", "scripts", "adapter", "build"))
            os.makedirs(os.path.join(root, "factory-run", "__pycache__", "build"))
            self.assertEqual([os.path.join("factory-run", "scripts", "adapter", "build")], ignored_folders(root))


if __name__ == "__main__":
    unittest.main()
