"""The stack profile, as the use cases read it: a value, read once by its adapter."""

from __future__ import annotations

import dataclasses
import typing


@dataclasses.dataclass(frozen=True)
class Profile:
    """The project's stack profile: what the project declares — its commands, places, tools, models — flat
    `key: value`, the method's configuration layered under it. A key it does not name reads as ''."""

    values: typing.Mapping[str, str]

    def get(self, key: str, default: str = "") -> str:
        return str(self.values.get(key, default) or default).strip()

    def names(self, key: str) -> bool:
        """Whether the profile names a value under this key."""
        return bool(self.get(key))

    def family(self, prefix: str) -> typing.Dict[str, str]:
        """The keys of one family — `test.`, `model.` — by the part after the prefix."""
        return {key[len(prefix):]: self.get(key) for key in self.values if key.startswith(prefix)}
