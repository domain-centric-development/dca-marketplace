"""The spec's use case, wired to the project's files and to delivery's open host service."""

from __future__ import annotations

from ..sharedkernel.adapter.outgoing.profile.profile_files import read_profile, resolve_profile, set_places
from ..spec.adapter.outgoing.delivery.open_story_files import OpenStoryFiles
from ..spec.adapter.outgoing.files.context_spec_files import ContextSpecFiles
from ..spec.application.showspec.show_spec import ShowSpecUseCase


def show_spec(cwd: str) -> ShowSpecUseCase:
    set_places(read_profile(resolve_profile(None, cwd)))
    return ShowSpecUseCase(ContextSpecFiles(cwd), OpenStoryFiles(cwd))
