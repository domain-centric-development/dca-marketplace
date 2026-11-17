"""Show the lessons: the candidates the stories' signals make, with their evidence — read only."""

from __future__ import annotations

import dataclasses
import typing

from ...building_blocks import UseCase
from ..domain.model.lesson import Candidate, LessonKind, Signals, THRESHOLDS
from ..domain.model.words import Count
from .shared.lesson_signals import LessonSignals

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowLessonsQuery:
    pass


class ShowLessonsInputPort(UseCase[ShowLessonsQuery, Model], typing.Protocol):
    """`candidates` (id, kind, key, stories, evidence, places, recommended, placed, contrast), `signals` counted by
    kind, the `thresholds` by kind, `open_at_once` and how many candidates `wait` beyond it."""


def candidate_model(candidate: Candidate) -> Model:
    return dict(id=candidate.id.value, kind=candidate.kind.value, key=candidate.key.value,
                stories=candidate.stories.value,
                evidence=[dict(story=e.story.value, source=e.source.value) for e in candidate.evidence],
                places=[dict(place=p.value, owner=p.owner.value, says=p.says.value) for p in candidate.places],
                recommended=candidate.recommended.value,
                placed=(dict(place=candidate.placed.place.value, stories=candidate.placed.stories.value)
                        if candidate.placed is not None and candidate.placed.place is not None else None),
                contrast=candidate.contrast.value if candidate.contrast is not None else None)


class ShowLessonsUseCase(ShowLessonsInputPort):
    """Every candidate not yet asked, `never` said or placed — what a write would ask a person next."""

    def __init__(self, signals: LessonSignals) -> None:
        self._signals = signals

    def execute(self, query: ShowLessonsQuery) -> Model:
        signals = Signals(tuple(self._signals.signals()))
        counted = {kind.value: signals.count(kind).value for kind in LessonKind}
        decided = self._signals.decided()
        candidates = signals.candidates(decided, self._signals.back_after())
        waiting = Count(sum(1 for d in decided if d.place is None))
        written = signals.bounded(candidates, waiting, self._signals.open_at_once())
        return dict(candidates=[candidate_model(c) for c in candidates], signals=counted,
                    thresholds={k.value: t.value for k, t in THRESHOLDS.items()},
                    open_at_once=self._signals.open_at_once().value, wait=len(candidates) - len(written))
