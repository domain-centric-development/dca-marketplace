"""What the project's journals say about the rules: how often each rule refused, where and in which stories — and how
one story ran along its kind's track: per stage passed, refused between the stages or tried again inside one, the ways
back it took and where its run started anew.

The runner writes a jump back and a restart into the journal where it decides them (`jump`, `restart`); a journal
written before that holds neither, and its route is read from the order of the runner's own gates and the judge's
start: a stage earlier than the one before is a way back where the track has one between the two, else a restart. A
stage's own gate calls inside its process (a shared builder's, a verifier's) are tries inside the stage, never a way.
A refused gate line names its checks (`fail=`) since 2026-10-10; an older one counts as a refusal without them.
"""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .rule import Count, KindName, Moment, OutcomeState, Rule, RuleId, StageName, Words
from .track import Track

#: The stage a process starts at where it is not a stage's own name: the shared verifier is the judge first.
JUDGE = "judge"
DELIVERED = "delivered"
PLAN = "plan"


class JournalLineKind(enum.Enum):
    """A line of a story's journal a reading of its route takes."""

    GATE = "gate"              # a gate ran over a stage — the runner's, or a stage's own inside its process
    JUMP = "jump"              # the runner sent the story back (`jump <to> from=<from> rule=<id>`)
    RESTART = "restart"        # the runner started the story anew at a stage (`restart <at> rule=<id> reason=<why>`)
    START = "start"            # a stage's process started
    FROM = "from"              # a person named the stage to run from (`--from`, the rounds counted anew)
    REOPENED = "reopened"      # a delivered story taken back for a correction at its acceptance


class CheckNaming(enum.Enum):
    """Whether a refused gate line names the checks that refused — a line written before 2026-10-10 names none."""

    NAMED = "named"
    UNNAMED = "unnamed"


class Reach(enum.Enum):
    """Whether a story's run got to a stage."""

    REACHED = "reached"
    NOT_REACHED = "not-reached"


class GateHand(enum.Enum):
    """Whose gate call it was: the runner's, between the stages, or a stage's own, inside its process."""

    RUNNER = "runner"
    STAGE = "stage"


class JournalLine(Value):
    """One line of the journal, as the reading needs it: its kind and moment, the stage it names (where a gate ran,
    where a jump goes, where a run starts), and for a gate how it ended, whose it was and the checks that refused —
    `naming` unnamed where a refused line names none (written before 2026-10-10)."""

    kind: JournalLineKind
    at: Moment
    stage: StageName
    source: StageName = StageName("")
    state: OutcomeState = OutcomeState.PASS
    hand: GateHand = GateHand.RUNNER
    checks: typing.Tuple[Words, ...] = ()
    naming: CheckNaming = CheckNaming.NAMED
    rule: Words = Words("")
    reason: Words = Words("")


class StoryJournal(Value):
    """One story's journal: the story, its kind where its file says one, its lines in order."""

    story: Words
    kind: typing.Optional[KindName]
    events: typing.Tuple[JournalLine, ...]


class StoryTimes(Value):
    story: Words
    times: Count


class StageTimes(Value):
    stage: StageName
    times: Count


class CheckTimes(Value):
    check: Words
    times: Count


class RuleRefusals(Value):
    """How often a rule refused in the project — between the stages and inside one alike —, when last, in which
    stories and at which stages."""

    rule: RuleId
    times: Count
    last: Moment
    stories: typing.Tuple[StoryTimes, ...]
    stages: typing.Tuple[StageTimes, ...]


class ProjectRefusals(Value):
    """Every rule's refusals over the project's journals, and the refusals no rule can be named for: their lines name
    no check."""

    rules: typing.Tuple[RuleRefusals, ...]
    unnamed: Count
    stories: typing.Tuple[Words, ...]


class StageRun(Value):
    """One stage of a story's run: reached, how its last gate there ended, refused between the stages (the runner's
    gate) and by which checks, tried again inside the stage (its own gate calls)."""

    stage: StageName
    reach: Reach
    ended: typing.Optional[OutcomeState]
    refused: Count
    checks: typing.Tuple[CheckTimes, ...]
    unnamed: Count
    tries: Count


class WayTaken(Value):
    source: StageName
    target: StageName
    times: Count


class RestartTaken(Value):
    stage: StageName
    times: Count
    reasons: typing.Tuple[Words, ...]


class RouteReading(enum.Enum):
    """Where a story's ways back were read from: the runner's own lines, or the order of its gates (an older journal)."""

    JOURNAL = "journal"
    GATE_ORDER = "gate-order"


class StoryRun(Value):
    """One story along its kind's track: each stage, the ways back it took, its restarts, the stage it reached last."""

    story: Words
    kind: KindName
    stages: typing.Tuple[StageRun, ...]
    ways: typing.Tuple[WayTaken, ...]
    restarts: typing.Tuple[RestartTaken, ...]
    last: StageName
    reading: RouteReading


class Journals(Value):
    """The project's journals, read against the rules."""

    journals: typing.Tuple[StoryJournal, ...]

    def refusals(self, rules: typing.Tuple[Rule, ...]) -> ProjectRefusals:
        """Each refused check named for the rules that report under it at that stage (a rule without stages: at any) —
        every refused gate line, a stage's own tries inside it among them."""
        by_name: typing.Dict[Words, typing.List[Rule]] = {}
        for rule in rules:
            for name in rule.reports:
                by_name.setdefault(name, []).append(rule)
        times: typing.Dict[RuleId, int] = {}
        last: typing.Dict[RuleId, str] = {}
        stories: typing.Dict[RuleId, typing.Dict[str, int]] = {}
        stages: typing.Dict[RuleId, typing.Dict[str, int]] = {}
        unnamed = 0
        for journal in self.journals:
            for event in journal.events:
                if event.kind is not JournalLineKind.GATE or event.state is not OutcomeState.FAIL:
                    continue
                if event.naming is CheckNaming.UNNAMED:
                    unnamed += 1
                    continue
                hit = {rule.id for check in event.checks for rule in by_name.get(check, ())
                       if not rule.stages or rule.holds_at(event.stage)}
                for rule_id in hit:
                    times[rule_id] = times.get(rule_id, 0) + 1
                    last[rule_id] = max(last.get(rule_id, ""), event.at.value)
                    at = stories.setdefault(rule_id, {})
                    at[journal.story.value] = at.get(journal.story.value, 0) + 1
                    where = stages.setdefault(rule_id, {})
                    where[event.stage.value] = where.get(event.stage.value, 0) + 1
        found = tuple(RuleRefusals(rule_id, Count(n), Moment(last[rule_id]),
                                   tuple(StoryTimes(Words(s), Count(c)) for s, c in
                                         sorted(stories[rule_id].items(), key=lambda x: -x[1])),
                                   tuple(StageTimes(StageName(s), Count(c)) for s, c in stages[rule_id].items()))
                      for rule_id, n in sorted(times.items(), key=lambda x: -x[1]))
        return ProjectRefusals(found, Count(unnamed), tuple(j.story for j in self.journals))

    def story(self, name: Words) -> typing.Optional[StoryJournal]:
        return next((j for j in self.journals if j.story == name), None)


def position(event: JournalLine, route: typing.Sequence[StageName]) -> typing.Optional[StageName]:
    """Where the event puts the story on its route: the runner's gate at a stage, a stage's process starting (the
    shared verifier at the judge) — none for a stage's own gate call inside its process."""
    if event.kind is JournalLineKind.GATE and event.hand is GateHand.RUNNER:
        return event.stage if event.stage in route else None
    if event.kind is JournalLineKind.START:
        at = StageName(JUDGE) if event.stage.value == "verifier" else event.stage
        return at if at in route else None
    return None


def story_run(journal: StoryJournal, track: Track) -> StoryRun:
    """The story along <track>: its stages, the ways back it took — the runner's `jump` lines, or for an older
    journal the order of its gates —, its restarts, and the stage it reached last."""
    route = [tile.stage for tile in track.tiles]
    known = {(w.source, w.target) for w in track.ways}
    explicit = any(e.kind in (JournalLineKind.JUMP, JournalLineKind.RESTART) for e in journal.events)
    ways: typing.Dict[typing.Tuple[StageName, StageName], int] = {}
    restarts: typing.Dict[StageName, typing.List[str]] = {}
    gates: typing.Dict[StageName, typing.List[JournalLine]] = {}
    reached: typing.Set[StageName] = set()
    here: typing.Optional[StageName] = None
    explained = ""                         # a jump or restart the runner wrote: the next earlier stage is it

    def took(source: StageName, target: StageName) -> None:
        ways[(source, target)] = ways.get((source, target), 0) + 1

    def restarted(stage: StageName, why: Words) -> None:
        restarts.setdefault(stage, []).append(why.value)

    for event in journal.events:
        if event.kind is JournalLineKind.JUMP:
            if event.source != event.stage and (event.source, event.stage) in known:
                took(event.source, event.stage)
            explained = "jump"
            continue
        if event.kind is JournalLineKind.RESTART:
            restarted(event.stage, event.reason)
            explained = "restart"
            continue
        if event.kind is JournalLineKind.REOPENED:
            if (StageName(DELIVERED), StageName(PLAN)) in known:
                took(StageName(DELIVERED), StageName(PLAN))
            explained = "reopened"
            continue
        if event.kind is JournalLineKind.FROM:
            explained = "from"
            continue
        if event.kind is JournalLineKind.GATE:
            gates.setdefault(event.stage, []).append(event)
            reached.add(event.stage)
        at = position(event, route)
        if at is None:
            continue
        reached.add(at)
        if here is not None and route.index(at) < route.index(here):
            if explained == "from":
                restarted(at, Words("a person named the stage (--from)"))
            elif explained:
                pass
            elif not explicit and (here, at) in known:
                took(here, at)
            else:
                restarted(at, Words(""))
        explained = ""
        here = at
    stages = []
    for stage in route:
        ran = gates.get(stage, [])
        between = [e for e in ran if e.hand is GateHand.RUNNER and e.state is OutcomeState.FAIL]
        checks: typing.Dict[str, int] = {}
        for event in between:
            for check in event.checks:
                checks[check.value] = checks.get(check.value, 0) + 1
        stages.append(StageRun(stage, Reach.REACHED if stage in reached else Reach.NOT_REACHED, ran[-1].state if ran else None, Count(len(between)),
                               tuple(CheckTimes(Words(c), Count(n)) for c, n in checks.items()),
                               Count(sum(1 for e in between if e.naming is CheckNaming.UNNAMED)),
                               Count(sum(1 for e in ran if e.hand is GateHand.STAGE and e.state is OutcomeState.FAIL))))
    last = here or next((s for s in reversed(route) if s in reached), route[0] if route else StageName(""))
    return StoryRun(journal.story, track.kind, tuple(stages),
                    tuple(WayTaken(s, t, Count(c)) for (s, t), c in ways.items()),
                    tuple(RestartTaken(s, Count(len(why)), tuple(dict.fromkeys(Words(w) for w in why if w)))
                          for s, why in restarts.items()),
                    last, RouteReading.JOURNAL if explicit else RouteReading.GATE_ORDER)
