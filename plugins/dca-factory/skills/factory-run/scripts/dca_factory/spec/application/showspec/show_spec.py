"""Show what holds: each bounded context with what it is for, its domain model, its features with their rules and
criteria — and beside each criterion the open stories that would add or change it (WP-173); above them the shared
kernel, each of its terms with the contexts that use it (WP-175)."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.context_spec import (
    ContextName, ContextSpec, Health, ModelTerm, Origin, PendingChange, Proof, SharedKernel, TermKind)
from ...domain.model.criterion import Criterion
from ..shared.context_specs import ContextSpecs
from ..shared.open_stories import OpenStories
from ..shared.proofs import Deliveries, TestSources

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowSpecQuery:
    """`context`: one context by its folder name; None — every one."""

    context: typing.Optional[str] = None
    #: also each criterion's health — what proves it, which test is gone, who delivered it (reads the code: slower)
    health: bool = False


class ShowSpecInputPort(UseCase[ShowSpecQuery, Model], typing.Protocol):
    """The spec, as a read model."""


def criterion_model(item: Criterion, pending: typing.Sequence[PendingChange]) -> Model:
    return dict(key=item.key.value, form=item.form.value, lines=[line.value for line in item.lines],
                tests=[t.value for t in item.tests],
                changed_by=[dict(story=p.story.value, title=p.title.value, status=p.status.value,
                                 verdict=p.verdict.value) for p in pending if p.key == item.key])


def model_groups(terms: typing.Sequence[ModelTerm],
                 used_by: typing.Callable[[ModelTerm], typing.List[str]] = lambda _: []) -> typing.List[Model]:
    """The terms by kind, in the order a reader meets the kinds; a term says whether it is shared and who uses it."""
    groups = []
    for kind in TermKind:
        mine = [t for t in terms if t.term.kind is kind]
        if mine:
            groups.append(dict(kind=kind.value, terms=[dict(name=t.term.name.value, meaning=t.term.meaning.value,
                                                            shared=t.origin is Origin.SHARED, used_by=used_by(t)) for t in mine]))
    return groups


def kernel_model(kernel: typing.Optional[SharedKernel], contexts: typing.Sequence[ContextSpec]) -> typing.Optional[Model]:
    if kernel is None:
        return None
    return dict(model=model_groups([ModelTerm(term, Origin.SHARED) for term in kernel.terms],
                                   lambda t: [c.value for c in kernel.users(t.term, contexts)]))


def context_model(spec: ContextSpec, pending: typing.Sequence[PendingChange],
                  kernel: typing.Optional[SharedKernel] = None) -> Model:
    held = {item.key for item in spec.held()}
    coming: typing.Dict[str, typing.List[Model]] = {}
    for change in pending:
        if change.key not in held:
            coming.setdefault(change.story.value, []).append(dict(key=change.key.value))
    return dict(
        context=spec.id.value, purpose=spec.purpose.value, subdomain=spec.subdomain.value,
        model=model_groups(spec.model(kernel)),
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


def health_model(found: Health) -> Model:
    by = found.delivered_by
    return dict(proof=found.proof.value, missing=[t.value for t in found.missing],
                delivered_by=dict(story=by.story.value, title=by.title.value, at=by.at.value, how=by.how.value)
                if by else None)


def with_health(model: Model, spec: ContextSpec, health: typing.Sequence[Health]) -> Model:
    """The context's model with each criterion's health and the context's count of each proof and of criteria no
    story delivered."""
    by_key = {h.key.value: h for h in health}
    for feature in model["features"]:
        for rule in feature["rules"]:
            for item in rule["criteria"]:
                item["health"] = health_model(by_key[item["key"]])
    model["health"] = dict({proof.value: sum(1 for h in health if h.proof is proof) for proof in Proof},
                           undelivered=sum(1 for h in health if h.delivered_by is None))
    return model


class ShowSpecUseCase:
    """The contexts the project keeps, with what open stories would do to them — and, asked, how each criterion
    stands."""

    def __init__(self, specs: ContextSpecs, stories: OpenStories, tests: TestSources, deliveries: Deliveries) -> None:
        self._specs = specs
        self._stories = stories
        self._tests = tests
        self._deliveries = deliveries

    def execute(self, query: ShowSpecQuery) -> Model:
        wanted = ContextName(query.context) if query.context else None
        stories = tuple(self._stories.not_delivered())
        every = tuple(self._specs.contexts())
        kernel = self._specs.shared_kernel()
        contexts = [spec for spec in every if wanted is None or spec.id == wanted]
        models = [context_model(spec, spec.pending(stories), kernel) for spec in contexts]
        if query.health:
            named = sorted({t for spec in contexts for item in spec.held() for t in item.tests}, key=lambda t: t.value)
            located, delivered = self._tests.located(named), tuple(self._deliveries.delivered())
            models = [with_health(model, spec, spec.health(located, delivered)) for model, spec in zip(models, contexts)]
        return dict(context=query.context, health=query.health, shared_kernel=kernel_model(kernel, every),
                    contexts=models)
