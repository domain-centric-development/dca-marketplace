"""What a story's criteria do to the spec: read and written through the spec's open host service."""

from __future__ import annotations

import os
import typing

from .....gate import story_spec
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter
from .....spec.api import derived, merge, read_delta, read_spec, render_spec, story_entries
from ....application.shared.story_spec import SpecChange
from ....domain.model.story import StoryId
from ..files.story_layout import find_story, story_kind


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
            own = [item for item in spec if item["feature"] == read["feature"]] if story_kind(front) != "journey" \
                else spec
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(render_spec(read_spec(target)[0], merge(own, read["story"], read_delta(""), {}),
                                         str(front.get("context", "")).strip() or "Spec"))
        return SpecChange(tuple(item["key"] for item in added), target)
