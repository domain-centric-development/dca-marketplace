"""What every feature's commands of the cli share."""

from __future__ import annotations

import os
import typing
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    read_profile, resolve_profile, set_places)
from ....application.shared.story_repository import StoryNotFound


RESULT = typing.TypeVar("RESULT")


def story_command(run: typing.Callable[[], RESULT]) -> RESULT:
    """A story command's use case run; a story not found is the gate's error, as the readers raise it."""
    try:
        return run()
    except StoryNotFound as error:
        raise GateError(str(error)) from None


def placed(profile_arg: typing.Optional[str] = None) -> None:
    """The places as the profile names them, for a command that reads no other option."""
    set_places(read_profile(resolve_profile(profile_arg, os.getcwd())))
