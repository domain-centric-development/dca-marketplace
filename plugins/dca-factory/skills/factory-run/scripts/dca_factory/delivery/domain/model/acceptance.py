"""When a delivered story waits for a person's look, and what its acceptance says at the gate that delivers it —
and when a flaky test becomes a finding of its own."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from ..model.decision_record import DecisionRecord
from ..model.story import StoryId
from ..model.story_state import Acceptance, AcceptanceVerdict, Detail
from ..model.verdict import CheckName, Findings, Said

ACCEPTANCE = CheckName("acceptance")


class Viewing(Value):
    """What a person could look at in the story: whether the project runs a browser, and whether one of its criteria
    is shown by a test the end-user command runs."""

    _has_browser: bool
    _has_end_user_test: bool

    @property
    def has_browser(self) -> bool:
        """Whether the project runs a browser."""
        return self._has_browser

    @property
    def has_end_user_test(self) -> bool:
        """Whether a criterion is shown by a test the end-user command runs."""
        return self._has_end_user_test

    def shows_a_page(self) -> bool:
        """Something to look at in a browser."""
        return self.has_browser and self.has_end_user_test


class AcceptanceMode(enum.Enum):
    """Which stories wait for a person's look before they count as delivered: none, those with something to look
    at in a browser, all."""

    NONE = "none"
    PAGES = "pages"
    ALL = "all"

    def asks(self, viewing: Viewing) -> bool:
        """Whether this story waits for a person before it is delivered. `pages`: it shows a page — something to look
        at."""
        if self is AcceptanceMode.NONE:
            return False
        return self is AcceptanceMode.ALL or viewing.shows_a_page()


class AcceptanceStep(Value):
    """What the acceptance says at the gate that delivers: the findings, whether to ask a person now, and whether
    the delivery goes on."""

    findings: Findings
    _asks: bool
    _goes_on: bool

    @property
    def asks(self) -> bool:
        """Whether to ask a person now."""
        return self._asks

    @property
    def goes_on(self) -> bool:
        """Whether the delivery goes on."""
        return self._goes_on

    @classmethod
    def at_delivery(cls, acceptance: Acceptance) -> AcceptanceStep:
        """Accepted, the story is delivered; an open look holds it; a correction not yet in the story refuses it; no
        look asked yet, one is asked now and holds it."""
        rid = acceptance.record.value if acceptance.record else "?"
        if acceptance.verdict is AcceptanceVerdict.ACCEPTED:
            return cls((ACCEPTANCE.ok(Said(f"{rid} accepted — the story is delivered")),),
                                  False, True)
        if acceptance.verdict is AcceptanceVerdict.OPEN:
            return cls((ACCEPTANCE.wait(Said(
                f"{rid} waits for a human's look — answer it through /factory-decisions; the story holds the "
                f"checkout until then")),), False, False)
        if acceptance.verdict is AcceptanceVerdict.CORRECTION:
            return cls((ACCEPTANCE.fail(Said(
                f"{rid} asked for a correction that is not in the story yet — write it in (criteria, an `answered:` "
                f"line naming {rid}); the story then runs again from plan")),), False, False)
        return cls((), True, False)


class FlakyFinding(Value):
    """A test flaky in this story and in others: a row of the project's own findings, for a task that fixes it."""

    test: Detail
    defect: Detail
    fix: Detail
    plain: Detail

    @classmethod
    def of(cls, story: StoryId, mine: typing.FrozenSet[Detail],
           others: typing.Mapping[Detail, typing.Tuple[StoryId, ...]],
           open_rows: typing.FrozenSet[Detail]) -> typing.Tuple[FlakyFinding, ...]:
        """A test noted flaky in this story and in another one is a finding — open, for a task that fixes the flake
        instead of running it again for ever. One open row per test across the backlog."""
        found = []
        for test in sorted(mine, key=lambda t: t.value):
            if test not in others or test in open_rows:
                continue
            seen = ", ".join([story.value] + [s.value for s in others[test]])
            found.append(cls(
                test, Detail(f"red in a whole suite run and green on its own run, in {seen}"),
                Detail("find what it depends on — load, order, a timeout, shared state — and fix the test or the "
                       "code, as a task"),
                Detail(f"The test {test.value} fails now and then in the whole suite, in more than one story — it is "
                       f"fixed, not run again")))
        return tuple(found)


def acceptance_verdict(record: typing.Optional[DecisionRecord]) -> AcceptanceVerdict:
    """Where the acceptance of the story the latest record was given for stands: none asks for one; one waiting is
    open; an answer accepts or asks for a correction. The record decides what its answer says."""
    if record is None:
        return AcceptanceVerdict.ASK
    if record.waits():
        return AcceptanceVerdict.OPEN
    return AcceptanceVerdict.ACCEPTED if record.accepts() else AcceptanceVerdict.CORRECTION


def changed_story_verdict(record: typing.Optional[DecisionRecord]) -> AcceptanceVerdict:
    """Where the acceptance of a story changed since its latest record stands: an answer holds only for the story it
    was given for, so a changed story (a correction written in) is asked again once it has run; one waiting is open."""
    if record is not None and record.waits():
        return AcceptanceVerdict.OPEN
    return AcceptanceVerdict.ASK
