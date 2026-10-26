"""The profile's questions, wired to the project's stack profile."""

from __future__ import annotations

import typing

from ..delivery.application.profile.ask_profile import AskProfileUseCase
from ..sharedkernel.adapter.outgoing.profile.profile_files import ProfileFiles


def ask_profile(path: typing.Optional[str]) -> AskProfileUseCase:
    return AskProfileUseCase(ProfileFiles(path))
