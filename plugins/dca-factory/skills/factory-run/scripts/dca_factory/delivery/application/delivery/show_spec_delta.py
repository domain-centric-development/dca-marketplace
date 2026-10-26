"""Show what holds before and after a story: per key of its delta, the verb, the feature before and after, the
criterion's lines before and after — what a person accepting the story looks at."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.spec_deltas import SpecDeltas

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowSpecDeltaQuery:
    story: str


class ShowSpecDeltaInputPort(UseCase[ShowSpecDeltaQuery, Model], typing.Protocol):
    """The story's spec delta as a view."""


class ShowSpecDeltaUseCase:
    """The rows read from the story, its plan and the spec, never parsed by a skill: a key the plan moves and the spec
    holds as it is `moves`, a key the plan removes `removes` with its reason; `features` names what the story
    brings."""

    def __init__(self, deltas: SpecDeltas) -> None:
        self._deltas = deltas

    def execute(self, query: ShowSpecDeltaQuery) -> Model:
        facts = self._deltas.facts(query.story)
        if facts is None:
            return dict(story=query.story, context="", feature="", features=[], renames=[], rows=[])
        before = {key: (feature, lines) for key, feature, lines in facts.held}
        after: typing.Dict[str, typing.Tuple[str, ...]] = {}
        for key, _feature, lines in facts.story:
            after.setdefault(key, lines)
        rows = []
        for key, verb in facts.verbs.items():
            old = before.get(key)
            rows.append(dict(key=key, verb="moves" if key in facts.moves and verb == "holds" else verb,
                             before_feature=old[0] if old else None, after_feature=facts.feature,
                             before=list(old[1]) if old else [], after=list(after[key]), reason=""))
        for key, reason in sorted(facts.removes.items()):
            old = before.get(key)
            rows.append(dict(key=key, verb="removes", before_feature=old[0] if old else None, after_feature=None,
                             before=list(old[1]) if old else [], after=[], reason=reason))
        renames = [dict(old=old, new=new, follow=list(follow)) for old, new, follow in facts.renames]
        return dict(story=query.story, context=facts.context, feature=facts.feature,
                    features=sorted(facts.features), renames=renames, rows=rows)
