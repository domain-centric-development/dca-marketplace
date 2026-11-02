"""The description feature's use case, wired to the project's files — apart from the rest of delivery's wiring, so
the gate takes it without the readers that read the gate."""

from __future__ import annotations

import typing

from ..delivery.adapter.outgoing.files.description_files import DescriptionFiles
from ..delivery.application.description.check_description import CheckDescriptionUseCase
from ..delivery.application.description.show_part import ShowPartUseCase
from ..sharedkernel.application.profile import Profile


def check_description(cwd: str, profile: typing.Mapping[str, str]) -> CheckDescriptionUseCase:
    return CheckDescriptionUseCase(DescriptionFiles(cwd, Profile(profile)))


def show_part(cwd: str) -> ShowPartUseCase:
    return ShowPartUseCase(DescriptionFiles.of_project(cwd))
