"""Check the project description: the product and the technical decisions complete."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.description import Part, REQUIRED
from ..shared.description_store import DescriptionStore
from .parts import part_as_it_stands

#: How each mandatory part is called in what the check says.
WHAT = {Part.PRODUCT: "product description", Part.TECH: "technical description"}


@dataclasses.dataclass(frozen=True)
class CheckDescriptionCommand:
    pass


@dataclasses.dataclass(frozen=True)
class Verdict:
    """One part's verdict: `ok`, `fail` or `note`, and what the gate says."""

    part: str
    state: str
    said: str


@dataclasses.dataclass(frozen=True)
class DescriptionChecked:
    verdicts: typing.Tuple[Verdict, ...]
    complete: bool


class CheckDescriptionInputPort(UseCase[CheckDescriptionCommand, DescriptionChecked], typing.Protocol):
    """Check the project description."""


class CheckDescriptionUseCase:
    """The two mandatory parts: the product and the technical decisions — the designed domain is read by the context
    check and stays optional here. Absent is a note: the gate does not block a project that has none, the backlog
    skill does. A key that names a missing file is a broken reference, and a heading missing or empty is a
    description nobody finished: both fail."""

    def __init__(self, store: DescriptionStore) -> None:
        self._store = store

    def execute(self, command: CheckDescriptionCommand) -> DescriptionChecked:
        verdicts, complete = [], True
        for part in (Part.PRODUCT, Part.TECH):
            verdict = self._verdict(part)
            verdicts.append(verdict)
            complete = complete and verdict.state == "ok"
        return DescriptionChecked(tuple(verdicts), complete)

    def _verdict(self, part: Part) -> Verdict:
        key, what, named = part.value, WHAT[part], self._store.named(part)
        model = part_as_it_stands(self._store, part)
        path, missing, empty = model["path"], model["missing"], model["empty"]
        if not model["present"]:
            if named:
                return Verdict(key, "fail", f"the profile's `{key}: {named}` names no file")
            return Verdict(key, "note", f"no {what} at {path} — `/factory-setup` writes it before the first story")
        if missing or empty:
            detail = "; ".join(filter(None, [
                f"missing `## {'`, `## '.join(missing)}`" if missing else "",
                f"empty `## {'`, `## '.join(empty)}`" if empty else "",
            ]))
            return Verdict(key, "fail", f"{path}: {detail} — every heading gets one honest line, never a placeholder")
        return Verdict(key, "ok", f"{path} fills all {len(REQUIRED[part])} headings of the {what}")
