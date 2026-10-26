"""A story's spec delta, read from the story, its plan and the spec through the spec's open host service."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....spec.api import derived, read_delta, renamed_rules, story_entries
from ....application.shared.spec_deltas import SpecDeltaFacts
from ..files.story_layout import find_story
from .story_spec_files import story_spec


class SpecDeltaFiles:
    """The stories under <epics>, their plans under <runs>."""

    def __init__(self, runs: str, epics: str) -> None:
        self._runs = runs
        self._epics = epics

    def facts(self, story: str) -> typing.Optional[SpecDeltaFacts]:
        front, body = read_front_matter(find_story(self._epics, story))
        target, held, _features, feature = story_spec(front)
        if not target:
            return None
        plan = os.path.join(self._runs, story, "plan.md")
        delta = read_delta(read_text(plan)) if os.path.isfile(plan) else read_delta("")
        entries = story_entries(body)
        follow = renamed_rules(entries, held, delta)
        return SpecDeltaFacts(
            context=str(front.get("context", "")).strip(), feature=feature,
            story=tuple((item["key"], feature, tuple(item["lines"])) for item in entries),
            held=tuple((item["key"], item["feature"], tuple(item["lines"])) for item in held),
            verbs=derived(entries, held), moves=frozenset(delta["moves"]), removes=dict(delta["removes"]),
            renames=tuple((old, new, tuple(follow.get(old, []))) for old, new in delta["renames"]),
            features=tuple(delta["features"]))
