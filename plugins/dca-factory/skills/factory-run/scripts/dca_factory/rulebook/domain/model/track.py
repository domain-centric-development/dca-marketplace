"""The track of a kind: its stages in order, the delivered end, and the ways back between them — read off the flow the
rules make (`Rulebook.graph`), so a page draws what the rules say and nothing it was told by hand.

A way back is one line per pair of stages, never one per rule: the rules behind it are its own. It costs a round when
a stage sends the story back — the runner counts one for every jump (RUN-ROUNDS-1, RUN-BACK-1, RUN-VERDICT-1,
RUN-INTEGRATE-1, RUN-ADOPT-1) —, and none when a person takes a delivered story back at its acceptance: a pass
action's way back starts at the delivered end, and the story runs as a new pass. Two things are never a line: a stage
sent into itself again (its tile's rounds), and a restart — a rule that starts the run anew at a stage (`restarts:`),
which is a note on that stage's tile.
"""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .rule import Count, KindName, Rule, RuleId, StageName, Words


class WayCost(enum.Enum):
    """What a way back costs the story: one of its rounds, or none."""

    ROUND = "round"
    FREE = "free"


class TileTurn(enum.Enum):
    """What a refused stage does next: runs once more (its rounds), decides by a verdict instead of a gate, or
    neither."""

    ROUNDS = "rounds"
    DECIDES = "decides"
    ONCE = "once"


class TrackWay(Value):
    """One line under the track: from a stage — or the delivered end — back to an earlier stage, what it costs, the
    rules that send a story along it, and its reason in their words."""

    source: StageName
    target: StageName
    cost: WayCost
    rules: typing.Tuple[RuleId, ...]
    reason: Words


class TrackTile(Value):
    """One stage of the track: its turn — a refused gate sends the story into it once more, or it decides by a
    verdict instead of a gate —, and the rules that start the run anew there, with on what."""

    stage: StageName
    turn: TileTurn
    restarts: typing.Tuple[RuleId, ...]
    restart_when: typing.Tuple[Words, ...]


class Track(Value):
    """A kind's stages in order, the delivered end and the ways back; `round_limit` how many rounds a story runs
    before a person looks."""

    kind: KindName
    tiles: typing.Tuple[TrackTile, ...]
    ways: typing.Tuple[TrackWay, ...]
    round_limit: Count

    def accepted(self) -> bool:
        """The delivered end waits for a person's acceptance: a way back starts there, and only that one is free."""
        return any(way.cost is WayCost.FREE for way in self.ways)


def reason_of(said: Words) -> Words:
    """An outcome's reason: what it says before its first dash — `a test cannot pass — …` reads `a test cannot pass`."""
    return Words(said.value.split(" — ")[0].strip())


def restarting(rule: Rule, stage: StageName) -> bool:
    """The rule starts the run anew at <stage> — a re-entry there, not a jump."""
    return rule.restart is not None and rule.restart.stage == stage
