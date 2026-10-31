"""The rules of the workflow as Markdown files, one per rule — `workflow/rules/gate/<ID>.md` and
`workflow/rules/run/<ID>.md` beside the package, installed with it as `.agents/factory/workflow/`. The front matter
holds what the factory reads (the part, the stages, kinds and report names, each outcome and where it goes), the body
what a person reads (when it applies, why it exists):

    ---
    id: GATE-RED-PROOF
    part: check
    reports:
    - red-proof
    pass: no test changed since it was recorded red, or changed on an answer
    fail: a test changed since its red proof — the test stage records it red again
    goes.fail: test
    ---

    # GATE-RED-PROOF

    **When:** the gates that expect green (build, tidy; test for a journey or adoption), with a red ledger.

    **Why:** a green test proves something only as the version that was seen red.

The repository's adapter for now — another one (a project's folder, a database) can take its place."""

from __future__ import annotations

import os
import typing

from ....domain.model.jump import RuleId, Target
from ....domain.model.stage import StageName, StoryKind
from ....domain.model.verdict import CheckName
from ....domain.model.workflow_rule import (
    Outcome, OutcomeState, RuleOrder, RulePart, RuleText, WorkflowRule, Written)
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter

#: The rules beside the package: `scripts/workflow/rules` in the plugin, `.agents/factory/workflow/rules` installed.
FOLDER = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "..",
                                       "workflow", "rules"))
WHEN, WHY = "**When:** ", "**Why:** "
QUOTES = "\"'"


#: The folder of each kind of rule, by its id's first part.
FOLDERS = {"GATE": "gate", "RUN": "run", "STAGE": "stage"}


def part_folder(rule_id: RuleId) -> str:
    return FOLDERS[rule_id.value.split("-", 1)[0]]


def listed(value: typing.Any) -> typing.List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [value] if value else []


def written_value(value: str) -> str:
    """A value the front matter reads back as it is: one the reader would unquote is quoted once more."""
    return f'"{value}"' if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTES else value


def paragraph(body: str, label: str) -> str:
    """The paragraph that starts with <label>, its lines joined."""
    lines = body.splitlines()
    for at, line in enumerate(lines):
        if line.startswith(label):
            said = [line[len(label):].strip()]
            for more in lines[at + 1:]:
                if not more.strip():
                    break
                said.append(more.strip())
            return " ".join(said)
    return ""


class RuleFiles:
    """The rules' repository (`RuleRepository`) over a folder of Markdown files."""

    def __init__(self, folder: str = FOLDER) -> None:
        self._folder = folder

    def path_of(self, rule_id: RuleId) -> str:
        return os.path.join(self._folder, part_folder(rule_id), f"{rule_id.value}.md")

    def all(self) -> typing.Sequence[WorkflowRule]:
        found: typing.List[WorkflowRule] = []
        for part in FOLDERS.values():
            place = os.path.join(self._folder, part)
            if os.path.isdir(place):
                found += [self._read(os.path.join(place, name)) for name in sorted(os.listdir(place))
                          if name.endswith(".md")]
        return sorted(found, key=lambda r: r.id.value)

    def find_by_id(self, aggregate_id: RuleId) -> typing.Optional[WorkflowRule]:
        path = self.path_of(aggregate_id)
        return self._read(path) if os.path.isfile(path) else None

    def save(self, aggregate: WorkflowRule) -> WorkflowRule:
        path = self.path_of(aggregate.id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as out:
            out.write(self.text(aggregate))
        return self._read(path)

    def delete_by_id(self, aggregate_id: RuleId) -> None:
        path = self.path_of(aggregate_id)
        if os.path.isfile(path):
            os.remove(path)

    def _read(self, path: str) -> WorkflowRule:
        front, body = read_front_matter(path)
        name = os.path.splitext(os.path.basename(path))[0]
        rule_id = RuleId(str(front.get("id") or name))
        if rule_id.value != name:
            raise ValueError(f"{path}: its id is {rule_id.value} — the file is named after the id")
        outcomes = []
        for state in OutcomeState:
            said = front.get(state.value)
            if said:
                goes = tuple(Target(t) for t in listed(front.get(f"goes.{state.value}")))
                outcomes.append(Outcome(state, RuleText(str(said)), goes))
        unsaid = [key for key in front if key.startswith("goes.") and not front.get(key[len("goes."):])]
        if unsaid:
            raise ValueError(f"{path}: {', '.join(unsaid)} for an outcome it says nothing about")
        retired = front.get("retired")
        if str(front.get("part") or "") == RulePart.TOLD.value:
            section, see, order = front.get("section"), front.get("see"), str(front.get("order") or "")
            return WorkflowRule(
                rule_id, RulePart.TOLD, RuleText(""), RuleText(""), (), (),
                [StageName(s) for s in listed(front.get("stages"))], [StoryKind(k) for k in listed(front.get("kinds"))],
                RuleText(str(retired)) if retired else None, self._written(path), RuleText(told_of(body, rule_id)),
                RuleText(str(section)) if section else None, Written(str(see)) if see else None,
                RuleOrder(int(order)) if order.isdigit() else None)
        return WorkflowRule(
            rule_id, RulePart(str(front.get("part") or "decision")), RuleText(paragraph(body, WHEN)),
            RuleText(paragraph(body, WHY)), outcomes, [CheckName(n) for n in listed(front.get("reports"))],
            [StageName(s) for s in listed(front.get("stages"))], [StoryKind(k) for k in listed(front.get("kinds"))],
            RuleText(str(retired)) if retired else None, self._written(path))

    def _written(self, path: str) -> Written:
        return Written(os.path.relpath(path, os.path.dirname(os.path.dirname(self._folder))).replace(os.sep, "/"))

    @staticmethod
    def text(rule: WorkflowRule) -> str:
        """The rule's file: the front matter the factory reads, the body a person reads."""
        if rule.part is RulePart.TOLD:
            return told_text(rule)
        lines = ["---", f"id: {rule.id.value}", f"part: {rule.part.value}"]
        for key, values in (("stages", [s.value for s in rule.stages]), ("kinds", [k.value for k in rule.kinds])):
            if values:
                lines += [f"{key}:"] + [f"- {v}" for v in values]
        if rule.id.value.startswith("GATE-"):
            lines += ["reports:"] + [f"- {r.value}" for r in rule.reports]
        for outcome in rule.outcomes:
            lines.append(f"{outcome.state.value}: {written_value(outcome.said.value)}")
            goes = [t.value for t in outcome.goes]
            if len(goes) == 1:
                lines.append(f"goes.{outcome.state.value}: {goes[0]}")
            elif goes:
                lines += [f"goes.{outcome.state.value}:"] + [f"- {t}" for t in goes]
        if rule.retired is not None:
            lines.append(f"retired: {written_value(rule.retired.value)}")
        lines += ["---", "", f"# {rule.id.value}", "", f"{WHEN}{rule.when.value}", "", f"{WHY}{rule.why.value}", ""]
        return "\n".join(lines)


def told_text(rule: WorkflowRule) -> str:
    """A told rule's file: where it holds in the front matter, its words — as the stage reads them — in the body."""
    lines = ["---", f"id: {rule.id.value}", f"part: {rule.part.value}"]
    for key, values in (("stages", [s.value for s in rule.stages]), ("kinds", [k.value for k in rule.kinds])):
        if values:
            lines += [f"{key}:"] + [f"- {v}" for v in values]
    if rule.section is not None:
        lines.append(f"section: {written_value(rule.section.value)}")
    if rule.see is not None:
        lines.append(f"see: {rule.see.value}")
    if rule.order is not None:
        lines.append(f"order: {rule.order.value}")
    if rule.retired is not None:
        lines.append(f"retired: {written_value(rule.retired.value)}")
    told = rule.told.value if rule.told is not None else ""
    return "\n".join(lines + ["---", "", f"# {rule.id.value}", "", told, ""])


def told_of(body: str, rule_id: RuleId) -> str:
    """The words under the `# <id>` heading, as written — indentation, list marks and emphasis kept."""
    lines = body.splitlines()
    at = next((i for i, line in enumerate(lines) if line.strip() == f"# {rule_id.value}"), -1)
    return "\n".join(lines[at + 1:]).strip("\n")
