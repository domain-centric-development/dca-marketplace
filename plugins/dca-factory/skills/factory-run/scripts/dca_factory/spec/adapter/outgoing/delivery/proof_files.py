"""What stands behind the spec, asked through delivery's open host service: the tests the code holds and the
delivered stories."""

from __future__ import annotations

import typing

from .....delivery.api import delivered_stories, located_tests
from ....api.published import story_entries
from ....domain.model.context_spec import ContextName, Delivery, Statement, StoryRef
from ....domain.model.criterion import CriterionKey, Selector
from ..files.spec_files import context_folder


class TestSourceFiles:
    """The sources of the project <cwd>."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def located(self, selectors: typing.Sequence[Selector]) -> typing.AbstractSet[Selector]:
        return {Selector(s) for s in located_tests(self._cwd, [s.value for s in selectors])}


class DeliveryFiles:
    """The delivered stories of the project <cwd>."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def delivered(self) -> typing.Sequence[Delivery]:
        return [Delivery(StoryRef(found["id"]), Statement(found["title"]), ContextName(context_folder(found["context"])),
                         Statement(found["delivered"]), Statement(found["by"]),
                         tuple(CriterionKey(item["key"]) for item in story_entries(found["body"])))
                for found in delivered_stories(self._cwd)]
