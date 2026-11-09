"""When a delivered story waits for a person's look, and what its acceptance says at the gate that delivers it —
and when a flaky test becomes a finding of its own."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from ..model.decision_record import DecisionRecord
from ..model.story_words import Presence
from ..model.story import StoryId
from ..model.story_state import Acceptance, AcceptanceVerdict, Detail
from ..model.verdict import CheckName, Findings, Said

ACCEPTANCE = CheckName("acceptance")


class Viewing(Value):
    """What a person could look at in the story: whether the project runs a browser, and whether one of its criteria
    is shown by a test the end-user command runs."""

    browser: Presence
    end_user_test: Presence

    def shows_a_page(self) -> bool:
        """Something to look at in a browser."""
        return self.browser is Presence.PRESENT and self.end_user_test is Presence.PRESENT


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
    ask: Presence
    goes_on: Presence

    @classmethod
    def at_delivery(cls, acceptance: Acceptance) -> AcceptanceStep:
        """Accepted, the story is delivered; an open look holds it; a correction not yet in the story refuses it; no
        look asked yet, one is asked now and holds it."""
        rid = acceptance.record.value if acceptance.record else "?"
        if acceptance.verdict is AcceptanceVerdict.ACCEPTED:
            return cls((ACCEPTANCE.ok(Said(f"{rid} accepted — the story is delivered")),),
                                  Presence.ABSENT, Presence.PRESENT)
        if acceptance.verdict is AcceptanceVerdict.OPEN:
            return cls((ACCEPTANCE.wait(Said(
                f"{rid} waits for a human's look — answer it through /factory-decisions; the story holds the "
                f"checkout until then")),), Presence.ABSENT, Presence.ABSENT)
        if acceptance.verdict is AcceptanceVerdict.CORRECTION:
            return cls((ACCEPTANCE.fail(Said(
                f"{rid} asked for a correction that is not in the story yet — write it in (criteria, an `answered:` "
                f"line naming {rid}); the story then runs again from plan")),), Presence.ABSENT, Presence.ABSENT)
        return cls((), Presence.PRESENT, Presence.ABSENT)


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


def acceptance_verdict(record: typing.Optional[DecisionRecord], same_story: Presence) -> AcceptanceVerdict:
    """Where the story's acceptance stands, from its latest record: none asks for one; one waiting is open; an answer
    holds only for the story it was given for — a story changed since (a correction written in) is asked again once it
    has run —; it accepts or it asks for a correction. The record decides what its answer says."""
    if record is None:
        return AcceptanceVerdict.ASK
    if record.waits():
        return AcceptanceVerdict.OPEN
    if same_story is Presence.ABSENT:
        return AcceptanceVerdict.ASK
    return AcceptanceVerdict.ACCEPTED if record.accepts() else AcceptanceVerdict.CORRECTION
