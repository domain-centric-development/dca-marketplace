"""The plan's stamp in the journal: a passing plan gate records the plan's digest and the contract it held the plan
to (`plan=`, `contract=`), so a later gate knows which rules the plan came about under (`PlanOrigin`)."""

from __future__ import annotations

import hashlib
import os
import typing

from .journal_files import journal_events
from ....domain.model.plan_facts import PlanOrigin, PlanStamp
from ....domain.model.profile_facts import ContractNumber


def plan_digest(runs: str, story_id: str) -> str:
    """The digest of the story's plan as it stands — empty where it has none."""
    path = os.path.join(runs, story_id, "plan.md")
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()[:12]


def plan_stamp_fields(runs: str, story_id: str, contract: int) -> typing.List[str]:
    """A passing plan gate's stamp: the plan's digest and the contract it was held to."""
    digest = plan_digest(runs, story_id)
    return [f"plan={digest}", f"contract={contract}"] if digest else []


def plan_origin(runs: str, story_id: str) -> PlanOrigin:
    """The stamp of the first passing plan gate that saw the plan as it stands; a plan only gates without a stamp have
    passed is from before the stamps; a plan no passing gate has seen is new."""
    digest = plan_digest(runs, story_id)
    events = journal_events(runs, story_id)
    passed = [event for event in events
              if event["kind"] == "gate" and event["name"] == "plan" and event["fields"].get("exit") == "0"]
    for event in passed:
        if digest and event["fields"].get("plan") == digest and event["fields"].get("contract", "").isdigit():
            return PlanOrigin(PlanStamp.STAMPED, ContractNumber(int(event["fields"]["contract"])))
    if digest and passed and not any("plan" in event["fields"] for event in passed):
        return PlanOrigin(PlanStamp.BEFORE_STAMPS)
    if digest and any(event["fields"].get("plan") for event in passed) and rewritten_after_a_later_gate(events):
        return PlanOrigin(PlanStamp.CHANGED)
    return PlanOrigin(PlanStamp.NEW)


#: The gates of the stages after the plan — a plan written after one of them was rewritten by a later stage.
LATER_GATES = ("test", "build", "tidy", "document")


def rewritten_after_a_later_gate(events: typing.Sequence[typing.Any]) -> bool:
    """Whether the last write of plan.md came after a gate of a later stage, with no plan gate between — a later stage
    rewrote the plan. A plan stage that plans again after an answer writes it after the plan gate, which runs before it."""
    last_write = max((i for i, e in enumerate(events) if e["kind"] == "wrote" and e["name"] == "plan.md"), default=None)
    if last_write is None:
        return False
    for event in reversed(events[:last_write]):
        if event["kind"] == "gate" and event["name"] == "plan":
            return False
        if event["kind"] == "gate" and event["name"] in LATER_GATES:
            return True
    return False
