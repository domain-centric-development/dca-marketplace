"""The rules the pipeline decides by, registered where they are decided — the one source of the rulebook for
everything deterministic.

A gate check carries its rules where it registers (`@check(..., rule=...)`), a pass action where it registers
(`@on_pass(..., rule=...)`), and a runner's decision on the use case that takes it (`@decides(...)`). Delivery
publishes them through its open host service (`delivery/api/rules.py`); the rulebook context reads them there, beside
the rules the stage skills carry in their text.

    GATE-<CHECK>        what a gate check holds — one rule per name it reports under (`GATE-HAPPY-PATH` under `plan`)
    RUN-<AREA>-<n>      what the runner decides — the route, the rounds, the schedule, the requests, the tools
    STAGE-<STAGE>-<n>   what a stage is told — in the skill's text, never here

An id is stable: a rule that goes keeps its id in `RETIRED`, with the reason, as the rule libraries keep theirs.
"""

from __future__ import annotations

import re
import typing

RULE_ID = re.compile(r"^(GATE|RUN|STAGE)(-[A-Z0-9]+)+$")
#: Where an outcome sends the story beside a stage's name: the stage that was refused once more, or nowhere — the run
#: ends and a person looks.
AGAIN, STOP = "again", "stop"
#: How a rule can come out, in the order a reader takes them: `ask` writes a decision record and stops.
OUTCOME_STATES = ("pass", "fail", "skip", "note", "wait", "ask")

Function = typing.TypeVar("Function", bound=typing.Callable[..., typing.Any])


class PipelineRule(typing.NamedTuple):
    """One rule: its id, when it applies, what it does in each outcome, why it exists — and, filled in where it
    registers, the stages and kinds it holds for, the names a gate reports it under and where it is written."""

    id: str
    when: str
    why: str
    outcomes: typing.Tuple[typing.Tuple[str, str], ...]
    reports: typing.Tuple[str, ...] = ()
    stages: typing.Tuple[str, ...] = ()
    kinds: typing.Tuple[str, ...] = ()
    source: str = ""
    #: per outcome state, where the story goes then: stages, `again`, `stop`
    goes: typing.Tuple[typing.Tuple[str, typing.Tuple[str, ...]], ...] = ()


def rule(id: str, when: str, why: str, *, ok: typing.Optional[str] = None, fail: typing.Optional[str] = None,
         skip: typing.Optional[str] = None, note: typing.Optional[str] = None, wait: typing.Optional[str] = None,
         ask: typing.Optional[str] = None, reports: typing.Optional[typing.Tuple[str, ...]] = None,
         stages: typing.Tuple[str, ...] = (), kinds: typing.Tuple[str, ...] = (),
         goes: typing.Optional[typing.Mapping[str, typing.Union[str, typing.Tuple[str, ...]]]] = None) -> PipelineRule:
    """A rule as it is written beside its code: `ok` is the pass outcome. A gate rule reports under the name its id
    gives (`GATE-TESTS-KEPT` → `tests-kept`) unless `reports` names others; `stages` and `kinds` narrow a gate rule
    below its check's and place a runner rule in the flow; `goes` says, per outcome (`ok` for pass), where the story
    goes then — a stage, `again` or `stop`."""
    if not RULE_ID.fullmatch(id) or id.startswith("STAGE-"):
        raise ValueError(f"rule {id}: an id is GATE-<CHECK> or RUN-<AREA>-<n> — STAGE- ids live in the skills")
    texts = dict(zip(OUTCOME_STATES, (ok, fail, skip, note, wait, ask)))
    outcomes = tuple((state, said) for state, said in texts.items() if said)
    if not outcomes:
        raise ValueError(f"rule {id}: says no outcome")
    if reports is None:
        reports = (id[len("GATE-"):].lower(),) if id.startswith("GATE-") else ()
    went = tuple(("pass" if state == "ok" else state, (to,) if isinstance(to, str) else tuple(to))
                 for state, to in (goes or {}).items())
    unsaid = [state for state, _to in went if state not in texts or not texts[state]]
    if unsaid:
        raise ValueError(f"rule {id}: goes somewhere on {', '.join(unsaid)} it says nothing about")
    return PipelineRule(id, when, why, outcomes, reports, stages, kinds, "", went)


def placed(rules: typing.Tuple[PipelineRule, ...], function: typing.Callable[..., typing.Any]) -> typing.Tuple[PipelineRule, ...]:
    """The rules, each with the place its code is written: the module's file and the line it starts on."""
    code = getattr(function, "__code__", None)
    line = code.co_firstlineno if code is not None else 0
    source = f"dca_factory/{function.__module__.split('dca_factory.', 1)[-1].replace('.', '/')}.py:{line}"
    return tuple(r._replace(source=source) for r in rules)


#: Every runner rule and every gate rule outside the stage checks, in the order their modules register them.
DECIDED: typing.List[PipelineRule] = []

#: A rule that went: its id, kept, and why — an id is never given to another rule.
RETIRED: typing.Dict[str, str] = {}


def decides(*rules: PipelineRule) -> typing.Callable[[Function], Function]:
    """Register the rules a function decides by — a use case's step, the gate's command, the commit hook."""
    def register(function: Function) -> Function:
        known = {r.id for r in DECIDED}
        twice = [r.id for r in rules if r.id in known]
        if twice:
            raise ValueError(f"rule {', '.join(twice)} registered twice")
        DECIDED.extend(placed(rules, function))
        return function
    return register
