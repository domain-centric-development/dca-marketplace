"""Where a story stands in the backlog: its context on the map, its epic complete, its outcome event the epic's."""

from __future__ import annotations

import re

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.schedule import ContextName
from ..model.stage import StoryKind
from ..model.stage_story import ContractNumber, Place, StageStory
from ..model.story_state import StatusWord
from ..model.verdict import CheckName, Findings, Said

APPROVED = CheckName("approved")
CONTEXT_MAP = CheckName("context-map")
EPIC = CheckName("epic")
OUTCOME = CheckName("outcome")

#: The fields an epic states: why it exists, what changes for the user, which outcome event measures it, and who
#: answers domain questions.
EPIC_FIELDS = ("intent", "goal", "metric", "domain_contact")

#: The contract that holds a story's outcome event to its epic's metric.
OUTCOME_CONTRACT = ContractNumber(14)


def normal_name(name: ContextName) -> ContextName:
    """A context's name as the map is read: no markup, lower case, without a trailing `(bounded) context`."""
    text = name.value.strip().strip("`*_\"' ").lower()
    return ContextName(re.sub(r"\s+(bounded\s+)?context$", "", text).strip())


class BacklogChecks(DomainService):
    """The checks over the backlog around a story."""

    @staticmethod
    def release(place: Place, status: StatusWord) -> Findings:
        """A draft is a story still being written: named, not refused. A status nobody knows is refused."""
        if status.value == "draft":
            return (APPROVED.note(Said(f"{place.value}: a draft — released with `status: approved` once it is "
                                       f"written")),)
        if status.value and status.value not in ("approved", "adopted"):
            return (APPROVED.fail(Said(f"{place.value}: status {status.value!r} is none of draft, approved, adopted, "
                                       f"superseded")),)
        return ()

    @staticmethod
    def context_map(story: StageStory, evidence: StageEvidence) -> Findings:
        """A story names the context it changes; that context must be on the map. A project without a map is not
        blocked — it has nothing to contradict yet."""
        found = evidence.context_map()
        if found.domain_missing is not None:
            return (CONTEXT_MAP.fail(Said(f"the profile's `domain: {found.domain_missing.value}` names no file")),)
        if found.map is None:
            return (CONTEXT_MAP.skip(Said("the project keeps no context map")),)
        context, where = story.context.value, found.map.value
        if normal_name(story.context) in found.names:
            return (CONTEXT_MAP.ok(Said(f"context {context!r} is on {where}")),)
        return (CONTEXT_MAP.fail(Said(
            f"{where}: context {context!r} does not appear — a story either changes a context that exists on the map, "
            f"or it is a scoping question, not a story")),)

    @staticmethod
    def epic(story: StageStory, evidence: StageEvidence) -> Findings:
        epic = evidence.epic(story)
        if epic.unreadable is not None:
            return (EPIC.fail(Said(epic.unreadable.value)),)
        where, name = epic.place.value, epic.name.value
        found = []
        if epic.missing:
            found.append(EPIC.fail(Said(
                f"{where}: epic {name!r} is incomplete — missing {', '.join(f.value for f in epic.missing)}. An epic "
                f"states why it exists (intent), what changes for the user (goal), which outcome event measures it "
                f"(metric) and who answers domain questions (domain_contact).")))
        elif epic.discovery_missing is not None:
            found.append(EPIC.fail(Said(
                f"{where}: `discovery: {epic.discovery_missing.value}` names a report that is not there — the epic links "
                f"the discovery it came from, or no `discovery:` line")))
        else:
            found.append(EPIC.ok(Said(f"epic {name!r} complete ({', '.join(EPIC_FIELDS)})")))
        if epic.dependency_problem is not None:
            found.append(EPIC.fail(Said(f"{where}: {epic.dependency_problem.value}")))
        return tuple(found)

    @staticmethod
    def outcome(story: StageStory, contract: ContractNumber, evidence: StageEvidence) -> Findings:
        """The event a story declares under `publishes:` is the epic's outcome event — a word of its `metric:`. Two
        names for one outcome are found here, before a line of code is written."""
        if story.kind is not StoryKind.STORY or contract.value < OUTCOME_CONTRACT.value or not story.publishes:
            return ()
        epic = evidence.epic(story)
        if epic.unreadable is not None:
            return ()                                   # `epic` refuses the story already
        metric, name = epic.metric.value, epic.name.value
        events = [e.value for e in story.publishes]
        foreign = [e for e in events if not re.search(rf"(?<!\w){re.escape(e)}(?!\w)", metric)]
        if foreign:
            return (OUTCOME.fail(Said(
                f"the story publishes {', '.join(foreign)}, which epic {name!r}'s `metric:` does not name "
                f"({metric.strip() or 'empty'}) — the story names the epic's outcome event as the epic does, or the "
                f"epic's metric is corrected first")),)
        return (OUTCOME.ok(Said(f"the story publishes {', '.join(events)}, the outcome event epic {name!r} is "
                                f"measured by")),)
