"""The workflow a story runs through: its stages in their order — what each one writes, which process may carry it,
which stories run it, what its gate holds it to — loaded from the workflow's repository, validated as a whole. Every
question about a stage is the workflow's; nothing else names a stage to decide on it."""

from __future__ import annotations

import re
import typing

from ....building_blocks import AggregateRoot, Id
from .jump import AGAIN, STOP, Target
from .stage import HandOver, Stage, StageName, StageText, StoryKind, Trait, Window
from .workflow_rule import Written

WORKFLOW_NAME = re.compile(r"[a-z][a-z0-9-]*")


class WorkflowName(Id):
    """A workflow by its name — `delivery`, the one every story runs today."""

    value: str

    def __post_init__(self) -> None:
        if not WORKFLOW_NAME.fullmatch(self.value):
            raise ValueError(f"{self.value!r} is no workflow name")


#: The workflow every story runs.
DELIVERY = WorkflowName("delivery")


class Workflow(AggregateRoot[WorkflowName]):
    """The stages in their order: each name once, each hand-over written by one stage, each hand-over a gate weighs
    written by a stage of it. Where each stage is written, as a person finds it, where the repository says."""

    def __init__(self, name: WorkflowName, stages: typing.Sequence[Stage],
                 written: typing.Optional[typing.Mapping[StageName, Written]] = None,
                 every_stage: typing.Optional[StageText] = None) -> None:
        super().__init__()
        names = [s.name.value for s in stages]
        if not names:
            raise ValueError(f"workflow {name.value}: has no stage")
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise ValueError(f"workflow {name.value}: names the stage {', '.join(twice)} twice")
        reserved = [n for n in names if n in (AGAIN, STOP)]
        if reserved:
            raise ValueError(f"workflow {name.value}: a stage named {', '.join(reserved)} — a target, not a stage")
        files = [s.hand_over.value for s in stages if s.hand_over is not None]
        shared = sorted({f for f in files if files.count(f) > 1})
        if shared:
            raise ValueError(f"workflow {name.value}: several stages write {', '.join(shared)}")
        unwritten = sorted({h.value for s in stages for h in s.sizes} - set(files))
        if unwritten:
            raise ValueError(f"workflow {name.value}: a gate weighs {', '.join(unwritten)}, which no stage writes")
        self._id = name
        self._stages = tuple(stages)
        self._written = dict(written or {})
        self._every_stage = every_stage

    @property
    def id(self) -> WorkflowName:
        return self._id

    @property
    def stages(self) -> typing.Tuple[Stage, ...]:
        """Every stage, in the workflow's order — the run order's steps first, the steps after it last."""
        return self._stages

    def stage(self, name: StageName) -> typing.Optional[Stage]:
        """The stage by its name, None for a name the workflow has no stage of."""
        return next((s for s in self._stages if s.name == name), None)

    @property
    def every_stage(self) -> typing.Optional[StageText]:
        """What every stage is told before its own — a frame like a stage's, its rules by marker."""
        return self._every_stage

    def written(self, name: StageName) -> typing.Optional[Written]:
        """Where the stage is written — `workflow/stages/plan.md` —, None where the repository says nothing."""
        return self._written.get(name)

    def having(self, trait: Trait) -> typing.Tuple[Stage, ...]:
        return tuple(s for s in self._stages if trait in s.traits)

    def without(self, trait: Trait) -> typing.Tuple[Stage, ...]:
        return tuple(s for s in self._stages if trait not in s.traits)

    def in_window(self, window: Window) -> typing.Tuple[Stage, ...]:
        """The stages the shared <window> may carry, in order."""
        return tuple(s for s in self._stages if s.window is window)

    def order(self, kind: StoryKind) -> typing.Tuple[StageName, ...]:
        """The run order of a story of <kind>."""
        return tuple(s.name for s in self._stages if Trait.IN_ORDER in s.traits and kind in s.kinds)

    def hand_over(self, name: StageName) -> typing.Optional[HandOver]:
        """The file the stage writes, None for a stage that writes none."""
        found = self.stage(name)
        return found.hand_over if found is not None else None

    def targets(self) -> typing.FrozenSet[Target]:
        """Every target a rule's outcome may send a story to: a stage of the workflow, `again`, `stop`."""
        return frozenset(Target(name) for name in [s.name.value for s in self._stages] + [AGAIN, STOP])
