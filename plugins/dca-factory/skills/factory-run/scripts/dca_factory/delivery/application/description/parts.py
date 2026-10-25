"""The project description's parts as they stand — what the status shows and the check holds."""

from __future__ import annotations

import typing

from ...domain.model.description import DescriptionRules, Part, REQUIRED
from ..shared.description_store import DescriptionStore

Model = typing.Dict[str, typing.Any]


def part_as_it_stands(store: DescriptionStore, part: Part) -> Model:
    """One part: where it is, whether it is there, which required headings are missing or empty, and every `## `
    heading it carries."""
    written = store.read(part)
    model: Model = dict(part=part.value, path=store.path(part), present=written is not None, missing=[], empty=[],
                        sections=[], required=[h.value for h in REQUIRED[part]])
    if written is None:
        return model
    model.update(sections=[h.value for h in written.headings],
                 missing=[h.value for h in DescriptionRules.missing(part, written)],
                 empty=[h.value for h in DescriptionRules.empty(part, written)])
    return model


def parts_as_they_stand(store: DescriptionStore) -> typing.List[Model]:
    """The product, the technical decisions and the designed domain, in that order."""
    return [part_as_it_stands(store, part) for part in Part]
