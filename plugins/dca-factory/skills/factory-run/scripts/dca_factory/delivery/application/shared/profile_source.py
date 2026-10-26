"""The stack profile as it stands now, read from wherever the project keeps it."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class ProfileSource(OutputPort, typing.Protocol):
    def profile(self) -> typing.Mapping[str, str]:
        """The profile's flat `key: value` pairs, the method's configuration layered under them."""
        ...
