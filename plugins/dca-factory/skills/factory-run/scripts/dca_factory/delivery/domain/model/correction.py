"""Why a person corrected a delivered story."""

from __future__ import annotations


from ....building_blocks import Value

#: Why a person corrected a story at its acceptance (WP-148 C): `correction: <code>: <their words>` — the skill
#: proposes a code from the words, the person confirms it.
REASON_CODES = ("structural", "behavioural", "domain-concept", "domain-boundary", "domain-invariant", "domain-term",
                "assumption")


class ReasonCode(Value):
    """One of the reason codes a correction names, lower case."""

    value: str

    def __post_init__(self) -> None:
        if self.value not in REASON_CODES:
            raise ValueError(f"a correction's code is one of {', '.join(REASON_CODES)} — not {self.value!r}")
