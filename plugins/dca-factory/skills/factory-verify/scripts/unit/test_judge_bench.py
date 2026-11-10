"""The judge measured: a seeded-defect bench's score — a planted defect found where a confirmed finding ranked major or
blocker names its file or its words, a control story's major findings counted as false alarms."""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest

from support import write

SCRIPT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "judge_bench.py"))
spec = importlib.util.spec_from_file_location("judge_bench", SCRIPT)
judge_bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge_bench)

JUDGE = """# Judge

## Verdict
verdict: changes-requested

## Confirmed defects
| Perspective | File:line | Severity | Defect | Fix | In plain words |
|---|---|---|---|---|---|
| ddd | `src/main/java/a/domain/Thing.java:14` | major | the invariant is not guarded | guard it | a rule is missing |
| clean-code | `src/main/java/a/Other.java:3` | minor | a long method | split | long |
"""

CONTROL = JUDGE.replace("| ddd |", "| hexagonal |").replace("src/main/java/a/domain/Thing.java:14",
                                                             "src/main/java/a/adapter/Web.java:9")

SET = [
    {"story": "S-1", "kind": "defect", "about": "an invariant left out", "patch": "x",
     "files": ["src/main/java/a/domain/Thing.java"], "words": []},
    {"story": "S-2", "kind": "defect", "about": "a value compared by identity", "patch": "x",
     "files": ["src/main/java/a/domain/Value.java"], "words": ["identity"]},
    {"story": "S-3", "kind": "control"},
]


class JudgeBenchTest(unittest.TestCase):

    def test_recall_and_false_alarms_over_the_set(self):
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, ".dca-factory", "runs", "S-1", "judge.md"), JUDGE)
            write(os.path.join(root, ".dca-factory", "runs", "S-2", "judge.md"), JUDGE)
            write(os.path.join(root, ".dca-factory", "runs", "S-3", "judge.md"), CONTROL)
            result = judge_bench.score(SET, root)
        self.assertEqual((result["found"], result["defects"], result["recall"], result["false_alarms"]), (1, 2, 0.5, 1))
        self.assertEqual([s.get("found") for s in result["stories"][:2]], [True, False])

    def test_a_minor_finding_finds_nothing_and_a_missing_judge_is_named(self):
        with tempfile.TemporaryDirectory() as root:
            write(os.path.join(root, ".dca-factory", "runs", "S-1", "judge.md"), JUDGE.replace("| major |", "| minor |"))
            result = judge_bench.score(SET[:1] + SET[2:], root)
        self.assertEqual((result["found"], result["not_judged"]), (0, ["S-3"]))

    def test_a_set_without_a_defects_patch_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "defects.json")
            write(path, json.dumps([{"story": "S-1", "kind": "defect"}]))
            with self.assertRaises(ValueError):
                judge_bench.items_of(path)

    def test_plant_applies_the_patch_in_the_project(self):
        with tempfile.TemporaryDirectory() as root:
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            write(os.path.join(root, "a.txt"), "one\n")
            patch = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-one\n+two\n"
            cwd = os.getcwd()
            try:
                os.chdir(root)
                code = judge_bench.plant([{"story": "S-1", "kind": "defect", "patch": patch, "files": ["a.txt"]}], "S-1")
            finally:
                os.chdir(cwd)
            self.assertEqual((code, open(os.path.join(root, "a.txt"), encoding="utf-8").read()), (0, "two\n"))


if __name__ == "__main__":
    unittest.main()
