"""Every discovery topic with its proposed epics and description changes, as discovery says them — with what a person
can do with each: make a proposal an epic, write a change into the description."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..requests.pending import mark_pending
from ..shared.discovery_list import DiscoveryList
from ..shared.requests import PENDING, RequestStore
from ..shared.story_repository import StoryRepository
from .actions import make_action, offered

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowDiscoveryQuery:
    project: str


class ShowDiscoveryInputPort(UseCase[ShowDiscoveryQuery, Model], typing.Protocol):
    """`project`, `store`, `topics` — each proposal and change with its `actions`."""


class ShowDiscoveryUseCase:
    def __init__(self, discovery: DiscoveryList, requests: RequestStore, stories: StoryRepository) -> None:
        self._discovery = discovery
        self._requests = requests
        self._stories = stories

    def execute(self, query: ShowDiscoveryQuery) -> Model:
        model = self._discovery.topics()
        pending = [r for r in self._requests.all() if r["state"] in PENDING]
        names_story = self._stories.names_story
        for topic in model["topics"]:
            for proposal in topic["proposals"]:
                proposal["actions"] = [] if proposal["epic"] else offered(make_action(
                    names_story, text="the proposal, written as an epic",
                    skill=f"/factory-backlog epic {proposal['id']} --from {topic['report']}", label="make epic",
                    primary=True))
            for change in topic["description_changes"]:
                change["actions"] = offered(make_action(
                    names_story, text="the change, written into the description",
                    skill=f"/dca-describe {change['target']}: {change['change']}", label="apply"))
            mark_pending([a for item in topic["proposals"] + topic["description_changes"] for a in item["actions"]],
                         pending)
        return dict(project=query.project, store=model["store"], topics=model["topics"])
