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
    passed = [event for event in journal_events(runs, story_id)
              if event["kind"] == "gate" and event["name"] == "plan" and event["fields"].get("exit") == "0"]
    for event in passed:
        if digest and event["fields"].get("plan") == digest and event["fields"].get("contract", "").isdigit():
            return PlanOrigin(PlanStamp.STAMPED, ContractNumber(int(event["fields"]["contract"])))
    if digest and passed and not any("plan" in event["fields"] for event in passed):
        return PlanOrigin(PlanStamp.BEFORE_STAMPS)
    return PlanOrigin(PlanStamp.NEW)
