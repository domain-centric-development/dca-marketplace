"""Show what holds: each bounded context with what it is for, its domain model, its features with their rules and
criteria — and beside each criterion the open stories that would add or change it (WP-173)."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.context_spec import ContextName, ContextSpec, PendingChange, TermKind
from ...domain.model.criterion import Criterion
from ..shared.context_specs import ContextSpecs
from ..shared.open_stories import OpenStories

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowSpecQuery:
    """`context`: one context by its folder name; None — every one."""

    context: typing.Optional[str] = None


class ShowSpecInputPort(UseCase[ShowSpecQuery, Model], typing.Protocol):
    """The spec, as a read model."""


def criterion_model(item: Criterion, pending: typing.Sequence[PendingChange]) -> Model:
    return dict(key=item.key.value, form=item.form.value, lines=[line.value for line in item.lines],
                tests=[t.value for t in item.tests],
                changed_by=[dict(story=p.story.value, title=p.title.value, status=p.status.value,
                                 verdict=p.verdict.value) for p in pending if p.key == item.key])


def context_model(spec: ContextSpec, pending: typing.Sequence[PendingChange]) -> Model:
    held = {item.key for item in spec.held()}
    coming: typing.Dict[str, typing.List[Model]] = {}
    for change in pending:
        if change.key not in held:
            coming.setdefault(change.story.value, []).append(dict(key=change.key.value))
    return dict(
        context=spec.id.value, purpose=spec.purpose.value, subdomain=spec.subdomain.value,
        model=[dict(kind=kind.value, terms=[dict(name=t.name.value, meaning=t.meaning.value)
                                            for t in spec.terms_of(kind)])
               for kind in TermKind if spec.terms_of(kind)],
        features=[dict(feature=feature.name.value,
                       rules=[dict(rule=block.rule.value if block.rule else "",
                                   criteria=[criterion_model(item, pending) for item in block.criteria])
                              for block in feature.rules()])
                  for feature in spec.features],
        criteria=len(spec.held()),
        coming=[dict(story=story, title=next(p.title.value for p in pending if p.story.value == story),
                     status=next(p.status.value for p in pending if p.story.value == story), keys=keys)
                for story, keys in coming.items()],
    )


class ShowSpecUseCase:
    """The contexts the project keeps, with what open stories would do to them."""

    def __init__(self, specs: ContextSpecs, stories: OpenStories) -> None:
        self._specs = specs
        self._stories = stories

    def execute(self, query: ShowSpecQuery) -> Model:
        wanted = ContextName(query.context) if query.context else None
        stories = tuple(self._stories.not_delivered())
        contexts = [spec for spec in self._specs.contexts() if wanted is None or spec.id == wanted]
        return dict(context=query.context,
                    contexts=[context_model(spec, spec.pending(stories)) for spec in contexts])
