"""Write one request the factory works before its next story."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import DomainEventPublisher, TransactionBoundary, UseCase
from ...domain.model.moment import Moment
from ...domain.model.request import Request, RequestId
from ...domain.model.handed_file import FileBytes, FileName, FileRefused, HandedFile, HandedFiles
from ..shared.handed_file_store import HandedFileStore
from ..shared.request_check import RequestCheck
from ..shared.requests import RequestRefused, RequestStore


@dataclasses.dataclass(frozen=True)
class WriteRequestCommand:
    kind: str
    fields: typing.Mapping[str, typing.Any]
    words: str
    by: str
    #: the files a person hands over beside the words, each its name as given and its bytes (WP-184)
    files: typing.Tuple[typing.Tuple[str, bytes], ...] = ()


@dataclasses.dataclass(frozen=True)
class RequestWritten:
    """The request's id and where it is kept."""

    id: str
    path: str


class WriteRequestInputPort(UseCase[WriteRequestCommand, RequestWritten], typing.Protocol):
    """Write one request."""


class WriteRequestUseCase(WriteRequestInputPort):
    """The request checked against the files and against the requests that wait — DuplicateRequest where the same
    waits already, RequestRefused with the reason otherwise —, the files beside its words taken as the domain takes
    them and kept, then written, queued: all or nothing — a request not written keeps no file."""

    def __init__(self, check: RequestCheck, store: RequestStore, files: HandedFileStore, events: DomainEventPublisher,
                 transactions: TransactionBoundary, now: typing.Callable[[], str]) -> None:
        self._transactions = transactions
        self._check = check
        self._store = store
        self._files = files
        self._events = events
        self._now = now

    def execute(self, command: WriteRequestCommand) -> RequestWritten:
        handed = self._handed(command)
        fields, words = self._check.checked(command.kind, {k: v for k, v in command.fields.items() if k != "files"},
                                            command.words, handed.any)
        self._check.against(command.kind, fields, words, self._store.all())
        kept = [self._files.keep(file) for file in handed.files]
        try:
            if kept:
                fields = dict(fields, files=" ".join(ref.id.value for ref in kept))
            request_id, path = self._store.add(command.kind, fields, words, command.by)
        except BaseException:
            for ref in kept:
                self._files.drop(ref.id)
            raise
        # the file is the request as written, queued; the aggregate says so (`RequestQueued`)
        written = Request.written(RequestId(request_id), Moment(self._now()))
        self._transactions.in_transaction(lambda: self._events.publish_and_clear_events(written))
        return RequestWritten(request_id, path)

    @staticmethod
    def _handed(command: WriteRequestCommand) -> HandedFiles:
        """The files as the domain takes them."""
        try:
            return HandedFiles(tuple(HandedFile(FileName(name), FileBytes(data)) for name, data in command.files))
        except FileRefused as refused:
            raise RequestRefused(str(refused)) from None
