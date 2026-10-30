"""The rules the pipeline decides by, bound by their ids where they are decided — the rules themselves come from the
rules' repository (`RuleRepository`, Markdown files beside the pipeline today), loaded once per process by its
composition root (`load`).

A gate check binds its rules where it registers (`@check(..., rule="GATE-…")`), a pass action where it registers
(`@on_pass(..., rule=…)`), and a runner's decision on the use case that takes it (`@decides("RUN-…")`). The code says
how a rule is checked or decided; the rule says what it holds the story to and where each outcome sends it.

    GATE-<CHECK>        what a gate check holds — one rule per name it reports under (`GATE-HAPPY-PATH` under `plan`)
    RUN-<AREA>-<n>      what the runner decides — the route, the rounds, the schedule, the requests, the tools
    STAGE-<STAGE>-<n>   what a stage is told — in the skill's text, never here
"""

from __future__ import annotations

import typing

from ...domain.model.jump import Jump, RuleId
from ...domain.model.stage import StoryKind
from ...domain.model.workflow_rule import OutcomeState, RulePart, WorkflowRule
from ..shared.rule_repository import RuleRepository

Function = typing.TypeVar("Function", bound=typing.Callable[..., typing.Any])


class Bound(typing.NamedTuple):
    """Where a rule is bound: its id, the kind of code, the stages and kinds that code holds for, its place."""

    rule: str
    part: RulePart
    stages: typing.Tuple[str, ...] = ()
    kinds: typing.FrozenSet[StoryKind] = frozenset(StoryKind)
    place: str = ""


#: Every rule bound in the code this process imported, in the order the modules bind them.
BOUND: typing.List[Bound] = []
#: The rules a runner's decision or the gate's frame binds (`@decides`), in their order.
DECIDED: typing.List[Bound] = []
#: The rules as the repository holds them, retired ones included — filled by `load`.
RULES: typing.Dict[str, WorkflowRule] = {}


def place_of(function: typing.Callable[..., typing.Any]) -> str:
    """Where the code that binds a rule is written: the module's file and the line it starts on."""
    code = getattr(function, "__code__", None)
    line = code.co_firstlineno if code is not None else 0
    return f"dca_factory/{function.__module__.split('dca_factory.', 1)[-1].replace('.', '/')}.py:{line}"


def bind(ids: typing.Iterable[str], part: RulePart, function: typing.Callable[..., typing.Any],
         stages: typing.Tuple[str, ...] = (), kinds: typing.FrozenSet[StoryKind] = frozenset(StoryKind)
         ) -> typing.Tuple[Bound, ...]:
    """Bind the rules <ids> to the code <function>: each id once in the whole package, and — once the rules are
    loaded — one the repository holds as a rule of that part."""
    known = {b.rule for b in BOUND}
    bound = tuple(Bound(RuleId(rule_id).value, part, stages, kinds, place_of(function)) for rule_id in ids)
    twice = [b.rule for b in bound if b.rule in known]
    if twice:
        raise ValueError(f"rule {', '.join(twice)} bound twice")
    BOUND.extend(bound)
    if RULES:
        held(bound)
    return bound


def held(bound: typing.Iterable[Bound]) -> None:
    """Every bound rule is one the repository holds, not retired, of the part its code is."""
    missing = [b.rule for b in bound if b.rule not in RULES or RULES[b.rule].retired is not None]
    if missing:
        raise ValueError(f"rule {', '.join(missing)} is bound in the code but the rules hold no such rule — "
                         "write its file under workflow/rules/")
    other = [f"{b.rule} ({RULES[b.rule].part.value}, bound as {b.part.value})" for b in bound
             if RULES[b.rule].part is not b.part]
    if other:
        raise ValueError(f"rule {', '.join(other)}: its file names another part than the code that binds it")


def load(repository: RuleRepository) -> None:
    """The rules from <repository>, held against every rule bound so far — once per process, by its composition
    root."""
    RULES.clear()
    RULES.update({r.id.value: r for r in repository.all()})
    held(BOUND)


def rule_of(rule_id: str) -> WorkflowRule:
    """The loaded rule by its id."""
    if not RULES:
        raise RuntimeError("the rules are not loaded — the composition root loads them (`load(RuleFiles())`)")
    found = RULES.get(rule_id)
    if found is None:
        raise KeyError(f"rule {rule_id}: the rules hold no such rule")
    return found


def unbound() -> typing.List[str]:
    """The rules the repository holds that no code binds, retired ones aside — each a rule that decides nothing."""
    bound = {b.rule for b in BOUND}
    return sorted(rule_id for rule_id, r in RULES.items() if r.retired is None and rule_id not in bound)


def jump(rule_id: str, state: str = "fail") -> Jump:
    """Where a runner rule sends the story on <state> — the one place a runner's decision reads its way. An id no
    decision binds is a programming error, never a silent default."""
    if rule_id not in {b.rule for b in DECIDED}:
        raise KeyError(f"rule {rule_id} is not bound — @decides it where it is decided")
    return rule_of(rule_id).jump(OutcomeState(state))


def decides(*ids: str) -> typing.Callable[[Function], Function]:
    """Bind the rules a function decides by — a use case's step, the gate's command, the commit hook."""
    def register(function: Function) -> Function:
        DECIDED.extend(bind(ids, RulePart.DECISION, function))
        return function
    return register
