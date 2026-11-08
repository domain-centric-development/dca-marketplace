"""The package's bytecode, kept by its source's content: a second copy of the package at another path compiles nothing
again, a changed module compiles anew, and a traceback names the copy that runs."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import SCRIPTS

IMPORT = ("import sys; sys.pycache_prefix = sys.argv[1] or None; sys.path.insert(0, sys.argv[2]);"
          "import dca_factory.contract, dca_factory.building_blocks")


class BytecodeByContent(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.cache = os.path.join(self.root, "cache")

    def copy(self, name):
        target = os.path.join(self.root, name)
        shutil.copytree(os.path.join(SCRIPTS, "dca_factory"), os.path.join(target, "dca_factory"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        return target

    def run_in(self, copy, cache=None, code=IMPORT):
        return subprocess.run([sys.executable, "-c", code, self.cache if cache is None else cache, copy],
                              capture_output=True, text=True)

    def kept(self):
        store = os.path.join(self.cache, "by-content")
        return sorted(name for _, _, files in os.walk(store) for name in files)

    def test_a_second_copy_finds_what_the_first_compiled(self):
        self.assertEqual(self.run_in(self.copy("one")).returncode, 0)
        first = self.kept()
        self.assertGreaterEqual(len(first), 2)
        self.assertEqual(self.run_in(self.copy("two")).returncode, 0)
        self.assertEqual(self.kept(), first)

    def test_a_changed_module_compiles_anew(self):
        self.run_in(self.copy("one"))
        first = self.kept()
        changed = self.copy("two")
        with open(os.path.join(changed, "dca_factory", "contract.py"), "a", encoding="utf-8") as handle:
            handle.write("\nCHANGED = True\n")
        self.assertEqual(self.run_in(changed).returncode, 0)
        self.assertEqual(len(self.kept()), len(first) + 1)

    def test_a_traceback_names_the_copy_that_runs(self):
        self.run_in(self.copy("one"))
        two = self.copy("two")
        ran = self.run_in(two, code=IMPORT + ";"
                          "print(dca_factory.contract.__spec__.loader.__class__.__name__);"
                          "print(dca_factory.building_blocks._frozen.__code__.co_filename)")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        loader, path = ran.stdout.split()
        self.assertEqual(loader, "ByContent")
        self.assertTrue(os.path.realpath(path).startswith(os.path.realpath(two)), path)

    def test_without_a_cache_folder_python_keeps_its_own_way(self):
        ran = self.run_in(self.copy("one"), cache="",
                          code=IMPORT + "; print(dca_factory.contract.__spec__.loader.__class__.__name__)")
        self.assertEqual(ran.stdout.strip(), "SourceFileLoader", ran.stderr)
        self.assertEqual(self.kept(), [])


if __name__ == "__main__":
    unittest.main()
