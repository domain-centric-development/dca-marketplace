"""The signals a story's journal carries beside its marks: what a plan left open, what a judge found."""

from __future__ import annotations

import hashlib
import re
import typing
from datetime import datetime, timezone
from .findings_files import confirmed_defects
from .decision_record_files import NOTHING
from .journal_files import Event, journal_append, journal_events
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of


SignalItem = typing.Tuple[str, str, typing.Dict[str, typing.Any]]
SignalLine = typing.Tuple[str, typing.Dict[str, typing.Any]]


# --- what a gate decided, written once (WP-150 B) --------------------------------------------------------------
# A gate that decides a signal writes it as a group: one `signal <what> run=<id> …` line, then one line per item
# with the same `run=` — `rule <selector>` at the test gate, `finding <perspective>` at the judge gate. A later gate
# run writes a new group; the last group is the record.
def journal_signal(runs: str, story_id: str, what: str,
                   items: typing.Iterable[SignalItem] = (),
                   **fields: typing.Any) -> None:
    """One group: `signal <what>` with `fields`, then `(kind, name, {field: value})` per item, under one run id."""
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    journal_append(runs, story_id, "signal", what, f"run={run}", *(f"{k}={v}" for k, v in fields.items()))
    for kind, name, values in items:
        journal_append(runs, story_id, kind, name or "-", f"run={run}", *(f"{k}={v}" for k, v in values.items()))


def latest_signal(events: typing.List[Event], what: str, kind: typing.Optional[str] = None
                  ) -> typing.Optional[typing.Tuple[typing.Dict[str, typing.Any], typing.List[SignalLine]]]:
    """The last group of a signal: (its `signal` line's fields, [(name, fields)] of its `kind` lines), or None."""
    head = next((e for e in reversed(events) if e["kind"] == "signal" and e["name"] == what), None)
    if head is None:
        return None
    run = head["fields"].get("run")
    items = [("" if e["name"] == "-" else e["name"], e["fields"]) for e in events
             if kind and e["kind"] == kind and e["fields"].get("run") == run]
    return head["fields"], items


#: The code a judge's confirmed defect about the domain model starts its Defect cell with (WP-148 C).
DOMAIN_CODE = re.compile(r"^\s*`?(domain-(?:concept|boundary|invariant|term))`?\s*:", re.I)


def plan_left_open(plan_text: str) -> typing.List[str]:
    """The lines a plan's `## Open assumptions` leaves open — a `none` line is none."""
    return [l for l in (section_of(plan_text, "open assumptions") or []) if l.strip().startswith(("-", "*"))
            and l.strip()[1:].strip().lower().rstrip(".") not in NOTHING]


def record_judge_signal(runs: str, story_id: str, judge_text: str) -> None:
    """The judge's confirmed defects as the journal's `signal judge` group (WP-150 B) — once per judge.md: a group
    for the same text is not written again."""
    sha = hashlib.sha256(judge_text.encode("utf-8")).hexdigest()[:16]
    last = latest_signal(journal_events(runs, story_id), "judge")
    if last and last[0].get("sha") == sha:
        return
    rows = confirmed_defects(judge_text)
    items: typing.List[SignalItem] = []
    for perspective, where, severity, defect, _fix, _plain in rows:
        code = DOMAIN_CODE.match(defect or "")
        items.append(("finding", perspective.lower(), dict(severity=severity.lower(), file=where,
                                                             code=code.group(1).lower() if code else "")))
    journal_signal(runs, story_id, "judge", items, sha=sha, findings=len(rows))
