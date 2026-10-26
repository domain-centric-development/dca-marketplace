"""A story's tests table and the tests it names, as a stage's checks read them."""

from __future__ import annotations

import typing

from ...domain.model.stage_story import MappedTest, TestLocation

Mapping = typing.Dict[str, typing.List[str]]


class StageTests(typing.Protocol):
    """The tests table of a story and its tests in the project."""

    def table(self, story: str) -> typing.Tuple[typing.Optional[str], Mapping, typing.Optional[str]]:
        """(the table's file, criterion key → its tests, why the table cannot be read — None where it can)."""
        ...

    def locate(self, mapping: typing.Mapping[str, typing.Sequence[str]]
               ) -> typing.Tuple[typing.Dict[str, str], typing.Tuple[TestLocation, ...]]:
        """{test: its file} for the tests found, and where each was looked for."""
        ...

    def mapped(self, body: str, mapping: typing.Mapping[str, typing.Sequence[str]],
               located: typing.Mapping[str, str]) -> typing.Tuple[MappedTest, ...]:
        """The table's rows with each test's file, the command that runs it and an end-user test's title check."""
        ...
