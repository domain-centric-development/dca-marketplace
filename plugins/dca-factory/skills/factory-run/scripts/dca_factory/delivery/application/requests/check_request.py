"""Check a request without writing it — before it is worked, or settled at once."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.request_check import Fields, RequestCheck
from ..shared.requests import RequestStore


@dataclasses.dataclass(frozen=True)
class CheckRequestCommand:
    """`against_waiting`: also against the requests not done — a press settled at once is refused like one written."""

    kind: str
    fields: typing.Mapping[str, typing.Any]
    words: str
    against_waiting: bool = False


@dataclasses.dataclass(frozen=True)
class CheckedRequest:
    """The request's fields and words as it would be written."""

    fields: Fields
    words: str


class CheckRequestInputPort(UseCase[CheckRequestCommand, CheckedRequest], typing.Protocol):
    """Check a request."""


class CheckRequestUseCase:
    """What held when a request was written may not hold when it is worked — an answer given by hand, a story
    released meanwhile: it is checked again, the same way."""

    def __init__(self, check: RequestCheck, store: RequestStore) -> None:
        self._check = check
        self._store = store

    def execute(self, command: CheckRequestCommand) -> CheckedRequest:
        fields, words = self._check.checked(command.kind, command.fields, command.words)
        if command.against_waiting:
            self._check.against(command.kind, fields, words, self._store.all())
        return CheckedRequest(fields, words)
