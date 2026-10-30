"""What the plan may adopt without asking (WP-165): scenarios of the story that hold on today's code alone, each shown
by a test that is there — the whole story, or a part split off, as long as the rest keeps its happy path."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.stage_story import PlanAdoption, Presence, ScenarioKey, StageStory
from ..model.verdict import CheckName, Findings, Said

PLAN_ADOPTS = CheckName("plan-adopts")


class Adoption(enum.Enum):
    """What a passing plan gate does with the plan's `## Adopt`."""

    NONE = "none"
    WHOLE = "whole"
    SPLIT = "split"


class AdoptChecks(DomainService):

    @staticmethod
    def outcome(story: StageStory, adoption: typing.Optional[PlanAdoption]) -> Adoption:
        """The whole story where every criterion holds, a split where some do, nothing where the plan adopts none."""
        if adoption is None or not adoption.rows or story.kind is not StoryKind.STORY:
            return Adoption.NONE
        held = {row.key.value for row in adoption.rows}
        return Adoption.WHOLE if held >= {key.value for key in story.criteria} else Adoption.SPLIT

    @staticmethod
    def found(story: StageStory, evidence: StageEvidence) -> Findings:
        """The plan's `## Adopt` names criteria of this story, each with a test that is there; a split leaves the rest
        its happy path — where it would not, the plan asks instead."""
        adoption = evidence.plan_adoption(story.story)
        outcome = AdoptChecks.outcome(story, adoption)
        if adoption is None or outcome is Adoption.NONE:
            return ()
        criteria = {key.value for key in story.criteria}
        unknown = [row.key.value for row in adoption.rows if row.key.value not in criteria]
        if unknown:
            return (PLAN_ADOPTS.fail(Said(f"`## Adopt` names what is no criterion of the story: {', '.join(unknown)}")),)
        absent = [f"{row.key.value} → {row.test.value}" for row in adoption.rows if row.present is Presence.ABSENT]
        if absent:
            return (PLAN_ADOPTS.fail(Said(f"`## Adopt` names a test that is not there: {'; '.join(absent)} — a row names "
                                          f"the test that shows the scenario holds today")),)
        keys = ", ".join(row.key.value for row in adoption.rows)
        if outcome is Adoption.WHOLE:
            return (PLAN_ADOPTS.ok(Said(f"every scenario holds today ({keys}) — the story becomes `status: adopted`")),)
        held = {row.key.value for row in adoption.rows}
        if story.happy_paths and all(key.value in held for key in story.happy_paths):
            return (PLAN_ADOPTS.fail(Said(
                f"the scenarios that hold ({keys}) include the story's happy path, and the rest would have none — "
                f"that is the person's to settle: a decision record instead of `## Adopt`")),)
        return (PLAN_ADOPTS.ok(Said(f"{keys} hold today — split into an adopted story; this one builds the rest")),)


def adopted_keys(adoption: typing.Optional[PlanAdoption]) -> typing.Tuple[ScenarioKey, ...]:
    return tuple(row.key for row in adoption.rows) if adoption else ()
