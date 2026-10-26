"""Check the backlog: the plan gate's backlog checks over every story that is not done, writing nothing."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.gateway.stage_evidence import StageEvidence
from ...domain.model.story import StoryId
from ...domain.model.verdict import CheckName, Finding, Findings, FindingState, Said
from ...domain.service.backlog_checks import BacklogChecks
from ...domain.service.profile_checks import ProfileChecks
from ...domain.service.story_checks import StoryChecks
from ..shared.backlog_entries import BacklogEntries

STORY = CheckName("story")


@dataclasses.dataclass(frozen=True)
class CheckBacklogCommand:
    """Every story that is not done, or the one `only` names by its id or its folder."""

    only: typing.Optional[StoryId]


@dataclasses.dataclass(frozen=True)
class StoryVerdict:
    """What the checks found for one story, under its label."""

    label: StoryId
    findings: Findings

    @property
    def refused(self) -> bool:
        return any(f.state is FindingState.FAIL for f in self.findings)


@dataclasses.dataclass(frozen=True)
class BacklogChecked:
    """Each story checked, the ones refused for an id another story carries first."""

    verdicts: typing.Tuple[StoryVerdict, ...]
    checked: int

    @property
    def refused(self) -> typing.Tuple[StoryId, ...]:
        return tuple(v.label for v in self.verdicts if v.refused)


class CheckBacklogInputPort(UseCase[CheckBacklogCommand, BacklogChecked], typing.Protocol):
    """Check the backlog."""


class CheckBacklogUseCase:
    """The same checks the plan gate holds a story to on these points — front matter, the epic's completeness, the
    criteria, the status, the context on the map — so a story that passes here passes there. A draft is named, not
    refused. Nothing is written: the plan gate's marks belong to the run that plans the story."""

    def __init__(self, entries: BacklogEntries, evidence: StageEvidence) -> None:
        self._entries = entries
        self._evidence = evidence

    def execute(self, command: CheckBacklogCommand) -> BacklogChecked:
        twice = self._entries.twice()
        verdicts = [StoryVerdict(story_id, (STORY.fail(Said(
            f"id {story_id.value!r} is not unique: {' and '.join(p.value for p in places)}; an id names one story in "
            f"the whole project, give one of them another")),)) for story_id, places in sorted(
                twice.items(), key=lambda item: item[0].value)]
        checked = 0
        contract = ProfileChecks.contract_number(self._evidence)
        for entry in self._entries.entries():
            if command.only is not None and command.only not in (entry.label, entry.folder):
                continue
            if StoryId(entry.label.value.lower()) in twice:
                continue                                # refused above, once for both
            if entry.status is not None and (entry.status.value == "superseded" or entry.delivered):
                continue
            found: typing.List[Finding] = list(BacklogChecks.release(entry.place, entry.status)) \
                if entry.status is not None else []
            if entry.story is None:
                found.append(STORY.fail(Said(entry.unreadable.value if entry.unreadable else "")))
            else:
                story = entry.story
                found.extend(StoryChecks.context(story))
                if story.context.value:
                    found.extend(BacklogChecks.context_map(story, self._evidence))
                found.extend(BacklogChecks.epic(story, self._evidence))
                found.extend(BacklogChecks.outcome(story, contract, self._evidence))
                found.extend(StoryChecks.happy_path(story, contract, self._evidence))
            checked += 1
            verdicts.append(StoryVerdict(entry.label, tuple(found)))
        return BacklogChecked(tuple(verdicts), checked)
