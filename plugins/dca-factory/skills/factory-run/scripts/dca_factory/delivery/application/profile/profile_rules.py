"""The stack profile's rules (`StackProfile`) for a reader that holds the profile as its file's flat pairs: the
adapters and the runner. Each function reads the pairs into the domain's profile and hands back plain words."""

from __future__ import annotations

import typing

from ...domain.model.stack_profile import (
    BUILT_IN_PERSPECTIVES, ProfileKey, ProfileValue, StackProfile, ToolName, Unit)
from ...domain.model.stage import StageName

__all__ = ["BUILT_IN_PERSPECTIVES", "carrier_lines", "carriers", "command_heads", "first_word", "model_for",
           "perspectives_of", "stack_profile", "tool_for", "effort_for"]

Profile = typing.Mapping[str, typing.Any]


def stack_profile(profile: Profile) -> StackProfile:
    """The pairs as the domain's profile."""
    return StackProfile(tuple((ProfileKey(str(key)), ProfileValue(str(value if value is not None else "")))
                              for key, value in profile.items()))


def first_word(value: typing.Any) -> str:
    return ProfileValue(str(value or "")).head().value


def command_heads(profile: Profile) -> typing.List[str]:
    return [head.value for head in stack_profile(profile).command_heads()]


def model_for(profile: Profile, tool: str, stage: str) -> str:
    return stack_profile(profile).model_for(ToolName(tool), StageName(stage)).value


def tool_for(profile: Profile, unit: str) -> str:
    return stack_profile(profile).tool_for(Unit(unit)).value


def effort_for(profile: Profile, tool: str, unit: typing.Optional[str]) -> str:
    return stack_profile(profile).effort_for(ToolName(tool), Unit(unit or "")).value


def perspectives_of(profile: Profile) -> typing.List[typing.Tuple[str, str]]:
    return [(p.name.value, p.carrier.value) for p in stack_profile(profile).perspectives()]


def carrier_lines(profile: Profile) -> typing.List[typing.Tuple[str, str]]:
    return [(key.value, value.value) for key, value in stack_profile(profile).carrier_entries()]


def carriers(profile: Profile) -> typing.List[str]:
    return [skill.value for skill in stack_profile(profile).carriers()]
