"""What holds, shown (WP-173): each context with its purpose and subdomain from the designed domain, its domain
model from its glossary, its features with their rules and criteria, and the open stories that would change them."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.sharedkernel.adapter.outgoing.profile.profile_files import set_places
from dca_factory.spec.adapter.outgoing.delivery.open_story_files import OpenStoryFiles
from dca_factory.spec.adapter.outgoing.files.context_spec_files import ContextSpecFiles, terms_of
from dca_factory.spec.application.showspec.show_spec import ShowSpecQuery, ShowSpecUseCase
from dca_factory.spec.domain.model.context_spec import TermKind


def plant(root, files):
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)


PROJECT = {
    "product/domain.md": "# Context Map\n\n## Bounded Contexts\n\n| Context | Responsibility | Subdomain |\n|---|---|---|\n"
                         "| `tasks` | Keeping a person's tasks | Core |\n\n## Relationships\n",
    "product/spec/tasks/glossary.md": "# Tasks\n\n## Aggregates\n\n### TaskList\n\n**Type:** Aggregate Root\n\n"
                                      "The tasks of one person, in order.\nNever empty of its owner.\n\n"
                                      "### Task\n\nOne thing to do.\n\n## Value Objects\n\n### TaskTitle\n\n"
                                      "**Type:** Value Object\n\nWhat a task is called.\n\n## Features\n\n### Listing\n\n"
                                      "**Type:** Feature\n\nShowing the list.\n",
    "product/spec/tasks/listing/scenarios.md": "# tasks — listing\n\n### Rule: A task is created with a title\n\n"
                                               "#### a-task-is-created\n- Given an empty list\n- When a task is added\n"
                                               "- Then the list holds it\nTest: ListTest#created\n\n"
                                               "#### an-empty-title-is-refused\n- Given an empty list\n"
                                               "- When a task without title is added\n- Then nothing is added\n",
    "product/epics/e/s-1/story.md": "---\nid: s-1\nstatus: approved\ncontext: tasks\ntitle: A title names the field\n---\n\n"
                                    "## Acceptance criteria\n\n### Rule: A task is created with a title\n\n"
                                    "#### an-empty-title-is-refused\n- Given an empty list\n- When a task without title "
                                    "is added\n- Then the page says why\n\n#### a-long-title-is-refused\n- Given x\n"
                                    "- When y\n- Then z\n",
    "product/epics/e/s-0/story.md": "---\nid: s-0\nstatus: delivered\ncontext: tasks\n---\n\n## Acceptance criteria\n\n"
                                    "#### a-task-is-created\n- Given q\n",
}


class SpecViewTest(unittest.TestCase):

    def view(self, root):
        set_places({})
        return ShowSpecUseCase(ContextSpecFiles(root), OpenStoryFiles(root)).execute(ShowSpecQuery())

    def test_a_context_shows_its_purpose_its_model_its_features_and_what_open_stories_change(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, PROJECT)
            [tasks] = self.view(root)["contexts"]
            self.assertEqual(("tasks", "Keeping a person's tasks", "Core"),
                             (tasks["context"], tasks["purpose"], tasks["subdomain"]))
            model = {g["kind"]: [t["name"] for t in g["terms"]] for g in tasks["model"]}
            self.assertEqual({"aggregate": ["TaskList", "Task"], "value object": ["TaskTitle"]}, model)
            [feature] = tasks["features"]
            self.assertEqual("listing", feature["feature"])
            [rule] = feature["rules"]
            self.assertEqual("A task is created with a title", rule["rule"])
            created, refused = rule["criteria"]
            self.assertEqual(["ListTest#created"], created["tests"])
            self.assertEqual([], created["changed_by"])                       # a delivered story changes nothing
            self.assertEqual([("s-1", "changes")], [(c["story"], c["verdict"]) for c in refused["changed_by"]])
            self.assertEqual([{"story": "s-1", "title": "A title names the field", "status": "approved",
                               "keys": [{"key": "a-long-title-is-refused"}]}], tasks["coming"])

    def test_a_term_takes_its_kind_from_its_type_line_and_its_first_paragraph_as_meaning(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, PROJECT)
            terms = terms_of(os.path.join(root, "product/spec/tasks/glossary.md"))
            self.assertEqual([("TaskList", TermKind.AGGREGATE, "The tasks of one person, in order. Never empty of its owner."),
                              ("Task", TermKind.AGGREGATE, "One thing to do."),
                              ("TaskTitle", TermKind.VALUE_OBJECT, "What a task is called.")],
                             [(t.name.value, t.kind, t.meaning.value) for t in terms])

    def test_the_cli_shows_the_spec_as_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, PROJECT)
            cli = os.path.join(support.SCRIPTS, "factory-cli.py")
            shown = subprocess.run([sys.executable, cli, "--spec"], cwd=root, capture_output=True, text=True,
                                   encoding="utf-8")
            self.assertEqual(0, shown.returncode, shown.stderr)
            self.assertIn("## tasks — Core", shown.stdout)
            self.assertIn("`an-empty-title-is-refused` — open: s-1 changes", shown.stdout)
            data = json.loads(subprocess.run([sys.executable, cli, "--spec", "--format", "json"], cwd=root,
                                             capture_output=True, text=True, encoding="utf-8").stdout)
            self.assertEqual(["tasks"], [c["context"] for c in data["contexts"]])
            refused = data["contexts"][0]["features"][0]["rules"][0]["criteria"][1]
            self.assertEqual("wish", refused["change"]["request"]["kind"])        # a change is a draft story, never an edit
            self.assertIn("criterion `an-empty-title-is-refused`", refused["change"]["request"]["prefix"])
            self.assertIn("feature `listing`", data["contexts"][0]["features"][0]["add"]["request"]["prefix"])


if __name__ == "__main__":
    unittest.main()
