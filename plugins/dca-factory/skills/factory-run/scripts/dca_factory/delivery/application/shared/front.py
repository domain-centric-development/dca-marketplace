"""What a front-matter value means — read the same way by every read model and every file adapter."""

from __future__ import annotations

import re
import typing

from ...domain.model.decision_record import Given, RecordKind
from ...domain.model.stage_story import Presence
from ...domain.service.acceptance_rules import AcceptanceRules

#: The key an item carries its creation under.
CREATED_KEY = "created"


def is_acceptance(front: typing.Mapping[str, typing.Any]) -> bool:
    """A record that asks for a person's look at a delivered story (`kind: acceptance`)."""
    return str(front.get("kind", "")).strip().lower() == RecordKind.ACCEPTANCE.value


def created_of(front: typing.Mapping[str, typing.Any]) -> str:
    """An item's `created:` as written, '' where it has none or where it is no ISO date or UTC time."""
    value = str(front.get(CREATED_KEY) or "").strip().strip("'\"")
    return value if re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$", value) else ""


def accepted(answer: typing.Mapping[str, typing.Any]) -> bool:
    """An answer that accepts the delivery: it begins with `accept`."""
    return AcceptanceRules.accepts(Given(str(answer.get("answer", "")))) is Presence.PRESENT


def front_text(value: typing.Any) -> str:
    """One front-matter value as text — a list (`key:` with `- item` lines) joined, never its Python form."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value or "")
