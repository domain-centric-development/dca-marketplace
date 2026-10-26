"""Ask the stack profile one question — the shell runner's, a skill's, a person's — and get its answer as lines."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import UseCase
from ..shared.profile_source import ProfileSource
from .profile_rules import carrier_lines, carriers, command_heads, model_for, perspectives_of


class Question(enum.Enum):
    """What the profile is asked."""

    VALUE = "value"                     # the value of one key, or nothing
    MODEL = "model"                     # the model a tool runs a stage on
    COMMAND_HEADS = "command-heads"     # the first word of every declared command
    CARRIERS = "carriers"               # the skills it names, without a plugin prefix
    CARRIER_LINES = "carrier-lines"     # the keys that name a skill, with the skill
    PERSPECTIVES = "perspectives"       # the judge's perspectives with their carriers


@dataclasses.dataclass(frozen=True)
class AskProfileQuery:
    question: Question
    key: str = ""
    tool: str = ""
    stage: str = ""


class AskProfileInputPort(UseCase[AskProfileQuery, typing.Tuple[str, ...]], typing.Protocol):
    """The profile's answer to one question, one line per item."""


class AskProfileUseCase:
    def __init__(self, profiles: ProfileSource) -> None:
        self._profiles = profiles

    def execute(self, query: AskProfileQuery) -> typing.Tuple[str, ...]:
        profile = self._profiles.profile()
        if query.question is Question.VALUE:
            return (str(profile.get(query.key, "")),)
        if query.question is Question.MODEL:
            return (model_for(profile, query.tool, query.stage),)
        if query.question is Question.COMMAND_HEADS:
            return tuple(command_heads(profile))
        if query.question is Question.CARRIERS:
            return tuple(carriers(profile))
        if query.question is Question.CARRIER_LINES:
            return tuple(f"{key} {value}" for key, value in carrier_lines(profile))
        return tuple(f"{name}\t{carrier}" for name, carrier in perspectives_of(profile))
