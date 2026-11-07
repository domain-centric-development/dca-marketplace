"""The project description as files: `product/overview.md`, `product/tech.md`, `product/domain.md` by default, or
where the profile places them."""

from __future__ import annotations

import os
import re
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import location, profile_of
from .....sharedkernel.application.profile import Profile
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ....domain.model.description import Body, Heading, Part, Section, Written
from ....application.shared.description_store import DescriptionStore


class DescriptionFiles(DescriptionStore):
    """The description store as files, under the project <cwd>, placed by <profile>."""

    def __init__(self, cwd: str, profile: Profile) -> None:
        self._cwd = cwd
        self._profile = profile.values

    @classmethod
    def of_project(cls, cwd: str) -> DescriptionFiles:
        """The description as the project's own profile places it."""
        return cls(cwd, profile_of(cwd))

    def path(self, part: Part) -> str:
        return str(location(self._profile, part.value)).replace(os.sep, "/")

    def named(self, part: Part) -> str:
        return str(self._profile.get(part.value, "")).strip()

    def read(self, part: Part) -> typing.Optional[Written]:
        found = self.sections(part)
        if found is None:
            return None
        return Written(tuple(s.heading for s in found),
                       frozenset(Heading(s.heading.value.lower()) for s in found if s.body.value))

    def sections(self, part: Part) -> typing.Optional[typing.Tuple[Section, ...]]:
        full = os.path.join(self._cwd, location(self._profile, part.value))
        if not os.path.isfile(full):
            return None
        # guidance in HTML comments does not count as content, so an untouched template is empty
        text = re.sub(r"<!--.*?-->", "", read_text(full), flags=re.S)
        found: typing.List[typing.Tuple[Heading, typing.List[str]]] = []
        for line in text.splitlines():
            if line.startswith("## "):
                found.append((Heading(line[3:].strip()), []))
            elif found:
                found[-1][1].append(line)
        return tuple(Section(heading, Body("\n".join(lines).strip())) for heading, lines in found)
