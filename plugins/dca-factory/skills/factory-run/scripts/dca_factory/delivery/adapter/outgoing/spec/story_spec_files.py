"""What a story's criteria do to the spec: read and written through the spec's open host service."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..files.hand_over_patterns import MAPPING_ROW, SELECTOR
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....spec.api import (
    context_files, derived, feature_name, journeys_path, merge, read_context, read_delta, read_spec, render_spec,
    scenarios_path, story_entries)
from ....application.shared.front import is_acceptance
from ....application.shared.story_spec import SpecChange
from ....domain.model.story import StoryId
from ..files.decision_record_files import records_of
from ..files.kept_files import human_line
from ..files.story_layout import journeys_hold, find_story
from ....domain.model.decision_record import DecisionState, Given, RecordKind
from ....domain.model.stage_story import Presence
from ....domain.service.acceptance_rules import AcceptanceRules

Front = typing.Mapping[str, typing.Any]
Entries = typing.List[typing.Dict[str, typing.Any]]


class StorySpecFiles:
    """The spec files beside the stories under <epics>."""

    def __init__(self, epics: str) -> None:
        self._epics = epics

    def _reading(self, story: StoryId) -> typing.Dict[str, typing.Any]:
        front, body = read_front_matter(find_story(self._epics, story.value))
        target, spec, _features, feature = story_spec(front)
        return dict(front=front, target=target or "", spec=spec, feature=feature,
                    story=story_entries(body) if target else [])

    def changing(self, story: StoryId) -> SpecChange:
        # A story that changes or removes what holds needs a plan to derive its delta: that is `--prove`'s adopt
        # path, not a delivery by hand.
        read = self._reading(story)
        elsewhere = {item["key"] for item in read["spec"] if item["feature"] != read["feature"]}
        keys = [key for key, verb in derived(read["story"], read["spec"]).items() if verb == "changes"] \
            + sorted(item["key"] for item in read["story"] if item["key"] in elsewhere)
        return SpecChange(tuple(keys), read["target"])

    def take_unproven(self, story: StoryId) -> SpecChange:
        read = self._reading(story)
        target, spec, front = read["target"], read["spec"], read["front"]
        added = [item for item in read["story"] if item["key"] not in {s["key"] for s in spec}]
        if added:
            own = [item for item in spec if item["feature"] == read["feature"]] if not journeys_hold(front) \
                else spec
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(render_spec(read_spec(target)[0], merge(own, read["story"], read_delta(""), {}),
                                         str(front.get("context", "")).strip() or "Spec"))
        return SpecChange(tuple(item["key"] for item in added), target)


def spec_target(front: Front) -> typing.Optional[str]:
    """The spec file a story changes: its feature's `scenarios.md` under its context — the context's own for a story
    without `feature:` —, or `journeys.md` for a journey item; None for a story that names no context."""
    if journeys_hold(front):
        return journeys_path()
    return scenarios_path(front["context"], front.get("feature")) if str(front.get("context", "")).strip() else None


def story_spec(front: Front) -> typing.Tuple[typing.Optional[str], Entries, typing.Set[str], str]:
    """(the file the story's criteria go to, what the spec holds where the story's keys are looked up — every
    criterion of the context with its feature —, the context's features, the story's feature). A journey's is
    `journeys.md` alone."""
    target = spec_target(front)
    if not target:
        return None, [], set(), ""
    if journeys_hold(front):
        return target, [dict(item, feature="") for item in read_spec(target)[1]], set(), ""
    context = front["context"]
    return (target, read_context(context), {name for name, _p in context_files(context) if name},
            feature_name(front.get("feature")))


def spec_backing(cwd: str, story_id: str, body: str, story_path: typing.Optional[str] = None) -> str:
    """What backs a change of what holds: the story's `## Changed expectations` in a person's words, or a decision a
    human answered for this story. "" where nothing does."""
    if any(l.strip().startswith(("-", "*")) and human_line(l.strip()[1:].strip())
           for l in section_of(body, "changed expectations") or []):
        return "the story's `## Changed expectations`"
    try:
        answered = [str(f["id"]).strip() for _p, f, _b, state, a in records_of(story_id, story_path)
                    if AcceptanceRules.backs_change(RecordKind.ACCEPTANCE if is_acceptance(f) else RecordKind.QUESTION,
                                                    DecisionState(state), Given(str(a.get("answer", ""))))
                    is Presence.PRESENT]
    except GateError:
        answered = []
    return f"decision {', '.join(answered)}" if answered else ""


def moved_tests(runs: str, story_id: str) -> typing.Dict[str, typing.List[str]]:
    """{key: [selector]} from tests.md's `## Moved tests` table — a test of the spec this story renamed or moved."""
    path = os.path.join(runs, story_id, "tests.md")
    moved: typing.Dict[str, typing.List[str]] = {}
    for line in (section_of(read_text(path), "moved tests") or []) if os.path.isfile(path) else []:
        row = MAPPING_ROW.match(line.strip())
        if row and row.group(1) not in ("criterion", "key", "---") and SELECTOR.match(row.group(2).strip()):
            moved.setdefault(row.group(1), []).append(row.group(2).strip())
    return moved
