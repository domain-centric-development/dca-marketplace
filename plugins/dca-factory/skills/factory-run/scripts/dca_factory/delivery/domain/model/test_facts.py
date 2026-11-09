"""The story's tests as the gate reads them: the tests table, the tests' source, how a test changed, the spec delta."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .story_state import Detail
from .story_words import Count, Place, ScenarioKey, Selector
from .suite_run import CommandKey
from .verdict import CheckName, Finding, Said


class TitleCheck(Value):
    """An end-user test's scenario title, and whether the test is reported under it."""

    title: Detail
    _reported: bool

    @property
    def reported(self) -> bool:
        """Whether the test is reported under its scenario's title."""
        return self._reported


class MappedTest(Value):
    """One row of the tests table: the criterion, its test, the file it was found in, the command that runs that
    file, and — for an end-user test of a titled scenario — its title check."""

    key: ScenarioKey
    selector: Selector
    place: typing.Optional[Place]
    command: typing.Optional[CommandKey]
    title: typing.Optional[TitleCheck]


class TestTable(Value):
    """The test stage's table: where it stands and the criteria its rows name, row by row."""

    place: Place
    keys: typing.Tuple[ScenarioKey, ...]
    tests: Count


class TestLocation(Value):
    """Where a mapped test was looked for: the file it was found in by its shape, or the file named after its class
    that lacks the method, or neither."""

    key: ScenarioKey
    selector: Selector
    found: typing.Optional[Place]
    candidate: typing.Optional[Place]
    shape: Detail

    def finding(self) -> Finding:
        """A selector must point at a test that is actually there. Without this check a missing test looks exactly
        like a red one, and the run would certify nothing."""
        selector, key = self.selector.value, self.key.value
        cls, _sep, method = selector.partition("#")
        if self.found is not None:
            return (CheckName("tests-exist").ok(Said(f"{selector} found in {self.found.value} ({key}, by "
                                             f"{self.shape.value})")))
        elif self.candidate is not None:
            return (CheckName("tests-exist").fail(Said(
                f"{selector}: {self.candidate.value} has no {method} — criterion {key!r} has no test, only a row "
                f"in the table")))
        else:
            return (CheckName("tests-exist").fail(Said(
                f"{selector}: no source file for {cls.rsplit('.', 1)[-1]} — criterion {key!r} has no test, and a "
                f"missing test is indistinguishable from a red one at the runner")))


class ShownLiteral(Value):
    """A text an expectation quotes as what is shown — „…“, "…", “…”, ‚…‘, ‘…’ or «…» — not one that names an element
    the step points at (a button, a field, a form, a link, or what is pressed or clicked)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("a shown literal says something")


class TestSource(Value):
    """The whole text of a test's file — a literal often stands in a constant, not in the test's method."""

    value: str

    def says(self, literal: ShownLiteral) -> bool:
        """Whether the file carries the literal as written, or with its straight quotes escaped as a string
        literal of the language writes them."""
        text = literal.value
        return text in self.value or ('"' in text and text.replace('"', '\\"') in self.value)


class ClauseRow(Value):
    """A row of the tests' `gate:clauses` table: the clause, the line that asserts it, the level it runs at."""

    key: ScenarioKey
    number: Count
    location: Detail
    level: Detail


class AssertionAt(enum.Enum):
    """What a line of a test file does: there is no such file, the statement asserts nothing, or it asserts."""

    NO_FILE = "no file"
    NOTHING = "nothing"
    ASSERTS = "asserts"


class AssertionFact(Value):
    """A test file's line as an assertion: what the line does, and whether the file is one of the given tests."""

    state: AssertionAt
    _among: bool

    @property
    def among(self) -> bool:
        """Whether the file is one of the given tests."""
        return self._among


class TestChange(enum.Enum):
    """How a test that existed before the story differs now."""

    CHANGED = "changed"
    REMOVED = "removed"
    SWITCHED_OFF = "switched off"


class TestEdit(enum.Enum):
    """What a story did to a test that existed before it: kept it (lines added only), arranged it anew with every
    assertion kept, switched it off, or changed what it expects."""

    KEPT = "kept"
    ARRANGED = "arranged"
    SWITCHED_OFF = "switched off"
    CHANGED = "changed"


class TestDiff(Value):
    """What a test's diff against the version before the story showed."""

    _switched_off: bool
    _lines_kept: bool
    _assertions_kept: bool

    @property
    def switched_off(self) -> bool:
        """Whether an added line switches the test off."""
        return self._switched_off

    @property
    def lines_kept(self) -> bool:
        """Whether every line is still there, in its order."""
        return self._lines_kept

    @property
    def assertions_kept(self) -> bool:
        """Whether every assertion is still there."""
        return self._assertions_kept

    def edit(self) -> TestEdit:
        """An added line that switches the test off outweighs all; every line still there in its order is kept;
        every assertion still there is an arrangement; anything else changes what the test expects."""
        if self.switched_off:
            return TestEdit.SWITCHED_OFF
        if self.lines_kept:
            return TestEdit.KEPT
        return TestEdit.ARRANGED if self.assertions_kept else TestEdit.CHANGED


class ChangedTest(Value):
    place: Place
    how: TestChange


class SymbolName(Value):
    """A type or a method as the source names it — `OrderChangedSinceReviewException`, `openFindings`."""

    value: str


class Rename(Value):
    """A name the story gave a type or a method: its old declaration gone from the sources, its new one present."""

    was: SymbolName
    now: SymbolName
    #: whether a context's glossary names the new name — the ubiquitous language's, or only the code's
    _in_glossary: bool

    @property
    def in_glossary(self) -> bool:
        """Whether a context's glossary names the new name."""
        return self._in_glossary


class RenamedTest(Value):
    """A test that holds every assertion it had once the names the story renamed are read under their new names."""

    place: Place
    renames: typing.Tuple[Rename, ...]


class KeptTests(Value):
    """The tests that existed before the story, against their baseline: the ones that no longer expect what they
    did, the ones whose baseline git lost, the ones changed only around their assertions, the ones that follow a
    rename."""

    changed: typing.Tuple[ChangedTest, ...]
    lost: typing.Tuple[Place, ...]
    arranged: typing.Tuple[Place, ...]
    renamed: typing.Tuple[RenamedTest, ...] = ()


class PlannedTestChange(Value):
    """A row of the plan's `## Changed tests`: the test, and what the row cites."""

    place: Place
    cites: Detail


class RedProof(Value):
    """The red ledger against the tests as they are: how many tests it names, how many without a file digest, the
    tests whose file changed since, and — at tidy — whether tidy reworked a test the red tree can prove again."""

    entries: Count
    unbound: Count
    moved: typing.Tuple[Detail, ...]
    _reproof: bool

    @property
    def reproof(self) -> bool:
        """Whether tidy reworked a test the red tree can prove again."""
        return self._reproof


class SpecDelta(Value):
    """The plan's `## Spec delta` against the story and the spec as it stands, as the spec's rules read it: what is
    wrong with it, the criteria that hold and that the story changes or removes, how many it adds and leaves."""

    plan: Place
    target: Place
    problems: typing.Tuple[Detail, ...]
    touched: typing.Tuple[ScenarioKey, ...]
    adds: Count
    holds: Count


class SpecTests(Value):
    """The tests the spec the story changes names: the moved tests that are not there, how many the spec names
    outside the story's own, and the ones of those that are gone."""

    target: Place
    absent_moved: typing.Tuple[Detail, ...]
    wanted: Count
    missing: typing.Tuple[Detail, ...]
