"""Why a person corrected a delivered story."""

from __future__ import annotations

import enum


class ReasonCode(enum.Enum):
    """Why a person corrected a story at its acceptance (WP-148 C): `correction: <code>: <their words>` — the skill
    proposes a code from the words, the person confirms it."""

    STRUCTURAL = "structural"
    BEHAVIOURAL = "behavioural"
    DOMAIN_CONCEPT = "domain-concept"
    DOMAIN_BOUNDARY = "domain-boundary"
    DOMAIN_INVARIANT = "domain-invariant"
    DOMAIN_TERM = "domain-term"
    ASSUMPTION = "assumption"


#: The codes as a person writes them, in their order.
REASON_CODES = tuple(code.value for code in ReasonCode)
