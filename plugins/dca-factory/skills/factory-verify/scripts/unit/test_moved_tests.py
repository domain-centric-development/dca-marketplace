"""`## Moved tests` names a test as it is now: a row naming the old one is refused, and a criterion the story
carries keeps the test its mapping names when the story is delivered."""

import os
import unittest

from support import contract, project, write
from dca_factory import gate
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
- Then "Cog" is shown in bold

## Changed expectations

- The name is shown in bold.
"""

SPEC = """# Widgets

### Rule: A widget is shown with its name

#### shows-the-name
- Given a widget "Cog"
- When the page opens
- Then "Cog" is shown
Test: com.example.WidgetPageTest#showsTheName
"""

PLAN = "# Plan\n\n## Spec delta\n- changes shows-the-name\n"

TESTS = """# Tests

<!-- gate:tests -->
| criterion | test |
| --- | --- |
| shows-the-name | com.example.WidgetPortTest#showsTheNameInBold |

## Moved tests
| shows-the-name | {moved} |
"""


class MovedTests(unittest.TestCase):

    def setup(self, p, moved):
        profiles.set_places({})
        path = p.story("S-1", text=STORY)
        write(os.path.join(p.root, "product", "spec", "widgets", "scenarios.md"), SPEC)
        write(os.path.join(p.root, "src", "test", "java", "com", "example", "WidgetPortTest.java"),
              "class WidgetPortTest { void showsTheNameInBold() {} }\n")
        p.run_file("S-1", "plan.md", PLAN)
        p.run_file("S-1", "tests.md", TESTS.format(moved=moved))
        front, body = markdown.read_front_matter(path)
        return path, front, body

    def test_a_row_naming_the_test_it_replaced_is_refused(self):
        with project() as p:
            _path, front, body = self.setup(p, "com.example.WidgetPageTest#showsTheName")
            result = gate.Result()
            mapping = gate.read_mapping(p.runs, "S-1")[1]
            gate.check_spec_tests(result, p.root, p.runs, "S-1", front, mapping)
            failed = [message for state, check, message in result.entries if state == "fail" and check == "spec-tests"]
            self.assertTrue(failed and "Moved tests" in failed[0] and "WidgetPageTest" in failed[0], result.entries)

    def test_the_storys_criterion_keeps_its_mapped_test_at_delivery(self):
        with project() as p:
            path, front, _body = self.setup(p, "com.example.WidgetPageTest#showsTheName")
            gate.merge_spec(gate.Result(), path, "S-1", front, p.runs)
            with open(os.path.join(p.root, "product", "spec", "widgets", "scenarios.md"), encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("Test: com.example.WidgetPortTest#showsTheNameInBold", text)
            self.assertNotIn("WidgetPageTest", text)


if __name__ == "__main__":
    unittest.main()
