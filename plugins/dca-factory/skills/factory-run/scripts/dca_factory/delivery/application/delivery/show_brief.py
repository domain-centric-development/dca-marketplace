"""What a stage is told for one story — its brief, from the workflow, the rules and the stack profile."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.jump import RuleId
from ...domain.model.stack_profile import SkillName
from ...domain.model.stage import StageName, Trait
from ...domain.model.story import StoryId
from ...domain.service.stage_brief import Brief, Carrier, CarrierRole, StageBrief
from ..shared.profile_source import ProfileSource
from ..shared.story_repository import StoryRepository
from .check_stage import judging
from .pipeline_rules import RULES
from .pipeline_workflow import workflow


@dataclasses.dataclass(frozen=True)
class ShowBriefQuery:
    story: StoryId
    stage: StageName


class ShowBriefInputPort(UseCase[ShowBriefQuery, Brief], typing.Protocol):
    """The stage's brief for the story; StoryNotFound where no single story has the id, ValueError where the workflow
    has no such stage or the story's kind does not run it."""


class ShowBriefUseCase:
    def __init__(self, stories: StoryRepository, profile: ProfileSource) -> None:
        self._stories = stories
        self._profile = profile

    def execute(self, query: ShowBriefQuery) -> Brief:
        kind = self._stories.get(query.story).kind
        return StageBrief(workflow()).of(query.stage, kind, list(RULES.values()),
                                          [RuleId(r) for r in judging(query.stage.value, kind)],
                                          self._carriers(query.stage))

    def _carriers(self, stage: StageName) -> typing.List[Carrier]:
        """The skills the profile names for the stage: its craft, the guard where it writes production code, the
        method's knowledge."""
        profile = self._profile.profile()
        row = workflow().stage(stage)
        wanted = [(CarrierRole.CRAFT, f"carrier.{stage.value}")]
        if row is not None and Trait.GUARDED in row.traits:
            wanted.append((CarrierRole.GUARD, "carrier.guard"))
        wanted.append((CarrierRole.KNOWLEDGE, "knowledge"))
        found = []
        for role, key in wanted:
            words = (profile.get(key) or "").split()
            if words:
                found.append(Carrier(role, SkillName(words[0])))
        return found
