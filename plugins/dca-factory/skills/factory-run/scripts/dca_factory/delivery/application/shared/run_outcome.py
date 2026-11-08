"""How a story's run, a gate and a merge of the main line end — the run's own words; an exit code is the runner's
translation of them, never the application's."""

from __future__ import annotations

import enum


class RunOutcome(enum.Enum):
    """How a story's run, or a process that carries its stages, ended."""

    RAN_THROUGH = "ran through"
    FAILED = "failed"
    #: the pipeline is not set up where the run looks for it — nothing ran
    NOT_SET_UP = "not set up"
    #: it stopped for a decision or an acceptance a person gives
    WAITS_FOR_PERSON = "waits for a person"
    #: a limit of the run was reached — a number of stages, a story's budget
    AT_LIMIT = "at a limit"
    #: another worker holds the checkout
    CHECKOUT_TAKEN = "checkout taken"
    #: the pipeline, or a person's file, changed under the run
    CHANGED_UNDER_IT = "changed under it"


class GateOutcome(enum.Enum):
    """What a gate said about a story."""

    PASSED = "passed"
    REFUSED = "refused"
    #: every check passed and the story waits for a person's acceptance
    WAITS_FOR_PERSON = "waits for a person"


class MergeOutcome(enum.Enum):
    """What merging the main line into a story's branch did."""

    MERGED = "merged"
    #: git stopped on conflicts, named in what the merge said
    CONFLICTS = "conflicts"
    FAILED = "failed"
