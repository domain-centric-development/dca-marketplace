"""When a delivered story waits for a person's look, and what its acceptance says at the gate that delivers it —
and when a flaky test becomes a finding of its own."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import DomainService, Value
from ..model.decision_record import ANSWERED_STATES, DecisionState, Given, RecordKind, WAITING
from ..model.stage_story import Presence
from ..model.story import StoryId
from ..model.story_state import Acceptance, AcceptanceVerdict, Detail
from ..model.verdict import CheckName, Findings, Said

ACCEPTANCE = CheckName("acceptance")


class AcceptanceMode(enum.Enum):
    """Which stories wait for a person's look before they count as delivered: none, those with something to look
    at in a browser, all."""

    NONE = "none"
    PAGES = "pages"
    ALL = "all"


class AcceptanceStep(Value):
    """What the acceptance says at the gate that delivers: the findings, whether to ask a person now, and whether
    the delivery goes on."""

    findings: Findings
    ask: Presence
    goes_on: Presence


class FlakyFinding(Value):
    """A test flaky in this story and in others: a row of the project's own findings, for a task that fixes it."""

    test: Detail
    defect: Detail
    fix: Detail
    plain: Detail


class AcceptanceRules(DomainService):
    """The acceptance of a delivery and the flaky tests it leaves."""

    @staticmethod
    def asks(mode: AcceptanceMode, browser: Presence, end_user_test: Presence) -> Presence:
        """Whether this story waits for a person before it is delivered. `pages`: it has a criterion whose test the
        end-user command runs, in a project with a browser — something to look at."""
        if mode is AcceptanceMode.NONE:
            return Presence.ABSENT
        if mode is AcceptanceMode.ALL:
            return Presence.PRESENT
        return Presence.PRESENT if browser is Presence.PRESENT and end_user_test is Presence.PRESENT \
            else Presence.ABSENT

    @staticmethod
    def accepts(given: Given) -> Presence:
        """An answer that accepts the delivery: it begins with `accept`."""
        return Presence.PRESENT if given.value.strip().lower().startswith("accept") else Presence.ABSENT

    @staticmethod
    def corrects(state: DecisionState, given: Given) -> Presence:
        """An acceptance answered with anything but `accept…`: the person asks for a correction."""
        return Presence.PRESENT if state in ANSWERED_STATES and AcceptanceRules.accepts(given) is Presence.ABSENT \
            else Presence.ABSENT

    @staticmethod
    def backs_change(kind: RecordKind, state: DecisionState, given: Given) -> Presence:
        """A person's answer that backs a change of what holds: a question answered, or an acceptance's correction —
        never an acceptance that accepted."""
        if kind is RecordKind.ACCEPTANCE:
            return AcceptanceRules.corrects(state, given)
        return Presence.PRESENT if state in ANSWERED_STATES else Presence.ABSENT

    @staticmethod
    def verdict(latest: typing.Optional[DecisionState], given: Given, same_story: Presence) -> AcceptanceVerdict:
        """Where the story's acceptance stands, from its latest record: none asks for one; one waiting is open; an
        answer holds only for the story it was given for — a story changed since (a correction written in) is asked
        again once it has run —; it accepts or it asks for a correction."""
        if latest is None:
            return AcceptanceVerdict.ASK
        if latest in WAITING:
            return AcceptanceVerdict.OPEN
        if same_story is Presence.ABSENT:
            return AcceptanceVerdict.ASK
        return AcceptanceVerdict.ACCEPTED if AcceptanceRules.accepts(given) is Presence.PRESENT \
            else AcceptanceVerdict.CORRECTION

    @staticmethod
    def at_delivery(acceptance: Acceptance) -> AcceptanceStep:
        """Accepted, the story is delivered; an open look holds it; a correction not yet in the story refuses it; no
        look asked yet, one is asked now and holds it."""
        rid = acceptance.record.value if acceptance.record else "?"
        if acceptance.verdict is AcceptanceVerdict.ACCEPTED:
            return AcceptanceStep((ACCEPTANCE.ok(Said(f"{rid} accepted — the story is delivered")),),
                                  Presence.ABSENT, Presence.PRESENT)
        if acceptance.verdict is AcceptanceVerdict.OPEN:
            return AcceptanceStep((ACCEPTANCE.wait(Said(
                f"{rid} waits for a human's look — answer it through /factory-decisions; the story holds the "
                f"checkout until then")),), Presence.ABSENT, Presence.ABSENT)
        if acceptance.verdict is AcceptanceVerdict.CORRECTION:
            return AcceptanceStep((ACCEPTANCE.fail(Said(
                f"{rid} asked for a correction that is not in the story yet — write it in (criteria, an `answered:` "
                f"line naming {rid}); the story then runs again from plan")),), Presence.ABSENT, Presence.ABSENT)
        return AcceptanceStep((), Presence.PRESENT, Presence.ABSENT)

    @staticmethod
    def asked(record: Detail, where: Detail) -> Findings:
        return (ACCEPTANCE.wait(Said(f"{record.value} asks a human to accept the story before it is delivered — "
                                     f"{where.value}, answered through /factory-decisions")),)

    @staticmethod
    def flaky(story: StoryId, mine: typing.FrozenSet[Detail],
              others: typing.Mapping[Detail, typing.Tuple[StoryId, ...]],
              open_rows: typing.FrozenSet[Detail]) -> typing.Tuple[FlakyFinding, ...]:
        """A test noted flaky in this story and in another one is a finding — open, for a task that fixes the flake
        instead of running it again for ever. One open row per test across the backlog."""
        found = []
        for test in sorted(mine, key=lambda t: t.value):
            if test not in others or test in open_rows:
                continue
            seen = ", ".join([story.value] + [s.value for s in others[test]])
            found.append(FlakyFinding(
                test, Detail(f"red in a whole suite run and green on its own run, in {seen}"),
                Detail("find what it depends on — load, order, a timeout, shared state — and fix the test or the "
                       "code, as a task"),
                Detail(f"The test {test.value} fails now and then in the whole suite, in more than one story — it is "
                       f"fixed, not run again")))
        return tuple(found)
