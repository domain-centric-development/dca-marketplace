"""The delivered stories and the spec, read through the spec's open host service."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import place, shown
from .....spec.api import lint_context, read_delta, story_entries
from ....application.shared.delivered_specs import DeliveredCriteria
from ..files.story_layout import journeys_hold, delivered_on, is_delivered, story_files, story_id_of
from .story_spec_files import spec_target, story_spec

Front = typing.Mapping[str, typing.Any]


def spec_place(front: Front) -> str:
    """What a key is unique in: the story's context (every feature of it), or the journeys."""
    return "journeys" if journeys_hold(front) else str(front.get("context", "")).strip().lower()


class DeliveredSpecFiles:
    """The stories under <epics>, their plans under <runs>, the spec under the profile's place."""

    def __init__(self, runs: str, epics: str) -> None:
        self._runs = runs
        self._epics = epics

    def delivered(self) -> typing.List[DeliveredCriteria]:
        found = []
        for story_path in story_files(self._epics):
            try:
                front, body = read_front_matter(story_path)
            except GateError:
                continue
            if not (is_delivered(front) and spec_target(front)):
                continue
            story_id = story_id_of(story_path)
            target, spec, _features, _feature = story_spec(front)
            plan = os.path.join(self._runs, story_id, "plan.md")
            removes = tuple(read_delta(read_text(plan))["removes"]) if os.path.isfile(plan) else ()
            found.append(DeliveredCriteria(
                str(delivered_on(front)), story_id, spec_place(front),
                tuple(item["key"] for item in story_entries(body)), frozenset(item["key"] for item in spec),
                str(shown(target or "")), removes))
        return found

    def shapes(self) -> typing.List[str]:
        spec_root = place("spec")
        lines: typing.List[str] = []
        for name in sorted(os.listdir(spec_root)) if os.path.isdir(spec_root) else []:
            if os.path.isdir(os.path.join(spec_root, name)):
                lines += lint_context(name)
        return lines
