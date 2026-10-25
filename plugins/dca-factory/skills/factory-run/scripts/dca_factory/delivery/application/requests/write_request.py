"""Write one request the factory works before its next story."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.request_check import RequestCheck
from ..shared.requests import RequestStore


@dataclasses.dataclass(frozen=True)
class WriteRequestCommand:
    kind: str
    fields: typing.Mapping[str, typing.Any]
    words: str
    by: str


@dataclasses.dataclass(frozen=True)
class RequestWritten:
    """The request's id and where it is kept."""

    id: str
    path: str


class WriteRequestInputPort(UseCase[WriteRequestCommand, RequestWritten], typing.Protocol):
    """Write one request."""


class WriteRequestUseCase:
    """The request checked against the files and against the requests that wait — DuplicateRequest where the same
    waits already, RequestRefused with the reason otherwise — then written, queued."""

    def __init__(self, check: RequestCheck, store: RequestStore) -> None:
        self._check = check
        self._store = store

    def execute(self, command: WriteRequestCommand) -> RequestWritten:
        fields, words = self._check.checked(command.kind, command.fields, command.words)
        self._check.against(command.kind, fields, words, self._store.all())
        request_id, path = self._store.add(command.kind, fields, words, command.by)
        return RequestWritten(request_id, path)
