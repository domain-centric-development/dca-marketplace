"""What the help reads of the project, from its files: the profile, the description, a build file, its places."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    location, PROFILE_FILE, read_profile, resolve_profile)
from .story_layout import DECISIONS_DIR

#: The build files a stack is known by; a .NET solution or project is known by its extension.
BUILD_FILES = ("build.gradle", "build.gradle.kts", "pom.xml", "package.json", "pyproject.toml", "go.mod", "Cargo.toml")


class ProjectFiles:
    """The project <cwd>, with its epics and run folder as the profile places them."""

    def __init__(self, cwd: str, epics: str, runs: str) -> None:
        self._cwd, self._epics, self._runs = cwd, epics, runs
        self._profile_file = resolve_profile(None, cwd)
        self._profile = read_profile(self._profile_file)

    def profile_file(self) -> typing.Optional[str]:
        return self._profile_file.replace(os.sep, "/") if self._profile_file else None

    def profile_name(self) -> str:
        return PROFILE_FILE

    def place(self, key: str) -> str:
        if key == "epics":
            return self._epics.replace(os.sep, "/")
        if key == "runs":
            return self._runs
        if key == "decisions":
            return DECISIONS_DIR
        return location(self._profile, key)

    def described(self) -> bool:
        return all(os.path.isfile(os.path.join(self._cwd, location(self._profile, k))) for k in ("product", "tech"))

    def has_build(self) -> bool:
        return any(os.path.isfile(os.path.join(self._cwd, name)) for name in BUILD_FILES) \
            or any(name.endswith((".sln", ".slnx", ".csproj")) for name in os.listdir(self._cwd))
