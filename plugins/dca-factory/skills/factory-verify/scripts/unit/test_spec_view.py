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
from dca_factory.spec.adapter.outgoing.delivery.proof_files import DeliveryFiles, TestSourceFiles
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
        return ShowSpecUseCase(ContextSpecFiles(root), OpenStoryFiles(root), TestSourceFiles(root),
                               DeliveryFiles(root)).execute(ShowSpecQuery())

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

    def test_the_shared_kernel_stands_beside_the_contexts_and_a_context_shows_the_shared_terms_it_uses(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, dict(PROJECT, **{
                "product/spec/tasks/glossary.md": PROJECT["product/spec/tasks/glossary.md"].replace(
                    "**Type:** Aggregate Root\n\n", "**Type:** Aggregate Root\n\n**Identity:** `TaskListId`\n\n")
                .replace("### Task\n\nOne thing to do.", "### Task\n\n**Identity:** `TaskId` (Shared Kernel)\n\nOne thing to do.")
                .replace("### TaskTitle\n\n", "### TaskTitle\n\nWritten as `Text`.\n\n"),
                "product/spec/shared-kernel/glossary.md": "# Shared Kernel\n\n## Value Objects\n\n### TaskId\n\n"
                                                         "**Type:** Value Object (ID)\n\nA task's identity.\n\n"
                                                         "### Text\n\n**Type:** Value Object\n\nWords as written.\n\n"
                                                         "### Owner\n\n**Type:** Value Object\n\nWho owns a thing.\n"}))
            view = self.view(root)
            self.assertEqual(["tasks"], [c["context"] for c in view["contexts"]])     # the kernel is no context
            kernel = {t["name"]: t["used_by"] for g in view["shared_kernel"]["model"] for t in g["terms"]}
            self.assertEqual({"TaskId": ["tasks"], "Text": ["tasks"], "Owner": []}, kernel)
            [tasks] = view["contexts"]
            ids = {t["name"]: t["shared"] for g in tasks["model"] if g["kind"] == "identity" for t in g["terms"]}
            self.assertEqual({"TaskId": True, "TaskListId": False}, ids)      # a shared id, and one of its own

    def test_without_a_shared_kernel_glossary_there_is_no_kernel(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, PROJECT)
            self.assertIsNone(self.view(root)["shared_kernel"])

    def test_health_names_what_proves_each_criterion_a_test_gone_and_who_delivered_it(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, dict(PROJECT, **{
                "product/spec/tasks/other/scenarios.md": "# other\n\n#### a-gone-test\n- Given a\n- When b\n- Then c\n"
                                                         "Test: com.example.GoneTest#vanished\n",
                "src/test/java/com/example/ListTest.java": "package com.example;\nclass ListTest { void created() {} }\n"}))
            files = dict(PROJECT)
            files["product/spec/tasks/listing/scenarios.md"] = files["product/spec/tasks/listing/scenarios.md"].replace(
                "Test: ListTest#created", "Test: com.example.ListTest#created")
            plant(root, {"product/spec/tasks/listing/scenarios.md": files["product/spec/tasks/listing/scenarios.md"]})
            set_places({})
            view = ShowSpecUseCase(ContextSpecFiles(root), OpenStoryFiles(root), TestSourceFiles(root),
                                   DeliveryFiles(root)).execute(ShowSpecQuery(health=True))
            [tasks] = view["contexts"]
            items = {x["key"]: x["health"] for f in tasks["features"] for r in f["rules"] for x in r["criteria"]}
            self.assertEqual("tested", items["a-task-is-created"]["proof"])
            self.assertEqual("s-0", items["a-task-is-created"]["delivered_by"]["story"])
            self.assertEqual("untested", items["an-empty-title-is-refused"]["proof"])
            self.assertEqual(("orphaned", ["com.example.GoneTest#vanished"]),
                             (items["a-gone-test"]["proof"], items["a-gone-test"]["missing"]))
            self.assertIsNone(items["a-gone-test"]["delivered_by"])
            self.assertEqual({"tested": 1, "orphaned": 1, "untested": 1, "undelivered": 2}, tasks["health"])

    def test_a_term_takes_its_kind_from_its_type_line_and_its_first_paragraph_as_meaning(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, PROJECT)
            terms = terms_of(os.path.join(root, "product/spec/tasks/glossary.md"))
            self.assertEqual([("TaskList", TermKind.AGGREGATE, "The tasks of one person, in order. Never empty of its owner."),
                              ("Task", TermKind.AGGREGATE, "One thing to do."),
                              ("TaskTitle", TermKind.VALUE_OBJECT, "What a task is called.")],
                             [(t.name.value, t.kind, t.meaning.value) for t in terms])

    def test_an_identity_is_a_kind_of_its_own_and_a_name_in_code_names_no_kind(self):
        from dca_factory.spec.domain.model.context_spec import Statement
        kind = lambda words: TermKind.named(Statement(words))
        self.assertEqual([TermKind.IDENTITY] * 3, [kind("Value Object (Id)"), kind("Value Object (ID, Shared Kernel)"),
                                                    kind("Value Object (Identity)")])
        self.assertEqual(TermKind.VALUE_OBJECT, kind("Value Object"))
        self.assertEqual(TermKind.CONCEPT, kind("Concept (read through the Shared Kernel's `IdentityProvider.Identity`)"))

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
