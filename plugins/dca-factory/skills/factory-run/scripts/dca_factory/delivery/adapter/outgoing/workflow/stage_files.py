"""The workflow's stages as Markdown files, one per stage — `workflow/stages/<name>.md` beside the package, installed
with it as `.agents/factory/workflow/`. The front matter holds what the factory reads, the body what a person reads:

    ---
    name: build
    order: 3
    hand_over: build.md
    window: builder
    kinds:
    - story
    - task
    traits:
    - gated
    - in_order
    - lists
    commands:
    - architecture
    sizes:
    - build.md
    ---

    # build

    Writes the production code that turns the story's red tests green, with the smallest change that works.

`order` places the stage in the workflow; the run order's steps come first, the steps after it (adopt, integrate) last.
The repository's adapter for now — another one (a project's folder, a database) can take its place."""

from __future__ import annotations

import os
import typing

from ....domain.model.stage import HandOver, ProfileCommand, Role, Stage, StageName, StageText, StoryKind, Trait, Window
from ....domain.model.workflow import DELIVERY, Workflow, WorkflowName
from ....domain.model.workflow_rule import Written
from ....application.shared.workflow_repository import WorkflowRepository
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .rule_files import listed

#: The line in a stage's body after which its frame starts — what it is told, its rules by marker.
FRAME = "<!-- frame: what the stage is told, each rule by its marker -->"
#: What every stage is told, beside the stages' folder.
EVERY_STAGE = "every-stage.md"

#: The stages beside the package: `scripts/workflow/stages` in the plugin, `.agents/factory/workflow/stages` installed.
FOLDER = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "..",
                                       "workflow", "stages"))


class StageFiles(WorkflowRepository):
    """The workflow's repository (`WorkflowRepository`) over a folder of Markdown files, one per stage — the folder
    holds the one workflow every story runs, `delivery`."""

    def __init__(self, folder: str = FOLDER) -> None:
        self._folder = folder

    def find_by_id(self, aggregate_id: WorkflowName) -> typing.Optional[Workflow]:
        if aggregate_id != DELIVERY or not os.path.isdir(self._folder):
            return None
        read = [self._read(os.path.join(self._folder, name)) for name in sorted(os.listdir(self._folder))
                if name.endswith(".md")]
        if not read:
            return None
        places = [place for place, _ in read]
        twice = sorted({p for p in places if places.count(p) > 1})
        if twice:
            raise ValueError(f"{self._folder}: several stages at order {', '.join(map(str, twice))}")
        stages = [stage for _, stage in sorted(read, key=lambda r: r[0])]
        every = os.path.join(os.path.dirname(self._folder), EVERY_STAGE)
        frame = read_text(every).split(FRAME, 1)[-1].strip("\n") if os.path.isfile(every) else ""
        return Workflow.restore(aggregate_id, stages, {s.name: self._written(s.name) for s in stages},
                        StageText(frame) if frame else None)

    def save(self, aggregate: Workflow) -> Workflow:
        if aggregate.id != DELIVERY:
            raise ValueError(f"workflow {aggregate.id.value}: this folder holds the delivery workflow alone")
        os.makedirs(self._folder, exist_ok=True)
        names = {s.name.value for s in aggregate.stages}
        for name in os.listdir(self._folder):
            if name.endswith(".md") and name[:-3] not in names:
                os.remove(os.path.join(self._folder, name))
        for place, stage in enumerate(aggregate.stages, 1):
            with open(self._path_of(stage.name), "w", encoding="utf-8", newline="\n") as out:
                out.write(self.text(stage, place))
        every = os.path.join(os.path.dirname(self._folder), EVERY_STAGE)
        if aggregate.every_stage is not None:
            with open(every, "w", encoding="utf-8", newline="\n") as out:
                out.write(f"# What every stage is told\n\n{FRAME}\n\n{aggregate.every_stage.value}\n")
        elif os.path.isfile(every):
            os.remove(every)
        found = self.find_by_id(aggregate.id)
        assert found is not None
        return found

    def delete_by_id(self, aggregate_id: WorkflowName) -> None:
        if aggregate_id == DELIVERY and os.path.isdir(self._folder):
            for name in os.listdir(self._folder):
                if name.endswith(".md"):
                    os.remove(os.path.join(self._folder, name))

    def _path_of(self, name: StageName) -> str:
        return os.path.join(self._folder, f"{name.value}.md")

    def _written(self, name: StageName) -> Written:
        """The stage's file as a person finds it — below the folder that holds the workflow."""
        return Written(os.path.relpath(self._path_of(name), os.path.dirname(os.path.dirname(self._folder)))
                       .replace(os.sep, "/"))

    def _read(self, path: str) -> typing.Tuple[int, Stage]:
        front, body = read_front_matter(path)
        file_name = os.path.splitext(os.path.basename(path))[0]
        name = str(front.get("name") or file_name)
        if name != file_name:
            raise ValueError(f"{path}: its name is {name} — the file is named after the stage")
        order = str(front.get("order") or "")
        if not order.isdigit():
            raise ValueError(f"{path}: order {order!r} — the stage's place, a number")
        hand_over, window = front.get("hand_over"), front.get("window")
        return int(order), Stage(
            StageName(name), HandOver(str(hand_over)) if hand_over else None, Window(str(window)) if window else None,
            frozenset(StoryKind(k) for k in listed(front.get("kinds"))),
            frozenset(Trait(t) for t in listed(front.get("traits"))),
            tuple(ProfileCommand(c) for c in listed(front.get("commands"))),
            tuple(HandOver(h) for h in listed(front.get("sizes"))), about_of(body.split(FRAME, 1)[0], name),
            frame_of(body), Role(str(front["role"])) if front.get("role") else None)

    @staticmethod
    def text(stage: Stage, place: int) -> str:
        """The stage's file: the front matter the factory reads, the body a person reads."""
        lines = ["---", f"name: {stage.name.value}"] + ([f"role: {stage.role.value}"] if stage.role else []) + [
            f"order: {place}"]
        if stage.hand_over is not None:
            lines.append(f"hand_over: {stage.hand_over.value}")
        if stage.window is not None:
            lines.append(f"window: {stage.window.value}")
        for key, values in (("kinds", [k.value for k in StoryKind if k in stage.kinds]),
                            ("traits", [t.value for t in Trait if t in stage.traits]),
                            ("commands", [c.value for c in stage.commands]),
                            ("sizes", [h.value for h in stage.sizes])):
            if values:
                lines += [f"{key}:"] + [f"- {v}" for v in values]
        lines += ["---", "", f"# {stage.name.value}", ""]
        if stage.about is not None:
            lines += [stage.about.value, ""]
        if stage.frame is not None:
            lines += [FRAME, "", stage.frame.value, ""]
        return "\n".join(lines)


def about_of(body: str, name: str) -> typing.Optional[StageText]:
    """The body's prose under its `# <name>` heading, its lines joined — None where it says nothing."""
    lines = [line.strip() for line in body.splitlines()]
    said = " ".join(line for line in lines if line and line != f"# {name}")
    return StageText(said) if said else None


def frame_of(body: str) -> typing.Optional[StageText]:
    """The body after its frame line, as written — None where it has none."""
    if FRAME not in body:
        return None
    frame = body.split(FRAME, 1)[1].strip("\n")
    return StageText(frame) if frame else None
