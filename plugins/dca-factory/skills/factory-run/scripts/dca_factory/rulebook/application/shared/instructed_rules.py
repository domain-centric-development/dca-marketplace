"""The rules a stage is told, as the rulebook reads them from the skills."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.rule import Citation, Rule


class InstructedRules(OutputPort, typing.Protocol):
    """The skills' text: each paragraph a `<!-- rule: <id> -->` marks — the words a told rule's file holds, while a
    skill still carries them — and every rule id the text cites."""

    def rules(self) -> typing.Tuple[Rule, ...]:
        """Every marked paragraph as a rule — none where no skill is found; held against the rule files, never a rule
        of its own."""
        ...

    def citations(self) -> typing.Tuple[Citation, ...]:
        """Every rule id the skills name outside a marker."""
        ...

    def where(self) -> str:
        """The skills folder read, as a person reads it — empty where none was found."""
        ...
