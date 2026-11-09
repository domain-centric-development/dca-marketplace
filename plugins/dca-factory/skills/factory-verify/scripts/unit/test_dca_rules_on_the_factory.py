"""The factory's own package held to the full DCA-Python rule suite, released and experimental rules alike: every
rule `dca-rules` implements finds nothing in `dca_factory/`, except the ids listed in NOT_YET_HELD — and each of those
still finds something, so the list shrinks as the package is brought in line and an id once held cannot break again.
A rule that selects nothing holds over nothing: it passes only where ALLOW_EMPTY says why the package has none of
what it governs (WP-191), and an id listed there that selects something now has to leave the list.
Runs where a `dca-python` checkout sits beside the marketplace (or `DCA_PYTHON` names one); skipped elsewhere."""

import os
import pathlib
import sys
import unittest

import support

HERE = os.path.dirname(os.path.abspath(__file__))
DCA_PYTHON = os.environ.get("DCA_PYTHON") or os.path.normpath(os.path.join(HERE, *[".."] * 7, "dca-python"))
RULES_SOURCE = os.path.join(DCA_PYTHON, "dca-rules", "src")

#: The ids the package does not hold yet (WP-188), with what stands behind them.
NOT_YET_HELD = {
    # WP-193 (2026-11-09): the rules the factory's DDD review asked for, held to the package they came from.
    "DCA-USE-021": "RunBacklogUseCase keeps the skipped stories in self between calls",
    "DCA-USE-022": "19 use cases answer with an exit code or a bare string — the outcomes of WP-192 step 9a for "
                   "the rest",
}

#: The rules that select nothing in the package, each with why — a statement about the factory, not a waiver (WP-191).
ALLOW_EMPTY = (
    ("DCA-ADV-005", "no integration events: the contexts cross through their api, never by an event"),
    ("DCA-ADV-006", "no integration events: the contexts cross through their api, never by an event"),
    ("DCA-STR-007", "no integration events: the contexts cross through their api, never by an event"),
    ("DCA-STR-008", "no integration events: the contexts cross through their api, never by an event"),
    ("DCA-STR-013", "no api.events package: the contexts publish no events to each other"),
    ("DCA-ADV-013", "no factory: every aggregate is built by its own class"),
    ("DCA-ADV-014", "no factory: every aggregate is built by its own class"),
    ("DCA-ADV-015", "no factory: every aggregate is built by its own class"),
    ("DCA-ADV-016", "no factory: every aggregate is built by its own class"),
    ("DCA-ADV-017", "no specification: a rule of the model is a method of the object it is about"),
    ("DCA-ADV-018", "no specification: a rule of the model is a method of the object it is about"),
    ("DCA-HEX-014", "no router framework: the page runs on http.server, which registers no handler by decorator"),
    ("DCA-HEX-018", "no router framework: the page runs on http.server, which registers no handler by decorator"),
    ("DCA-MAP-012", "no partnership: every relationship between the contexts is customer and supplier"),
    ("DCA-NAM-007", "no class named *Dto: an adapter translates into its own plain records"),
    ("DCA-NAM-008", "no class named *Converter: an adapter translates in functions"),
    ("DCA-NAM-011", "no class named *ViewModel: the page renders from the use cases' answers"),
    ("DCA-PY-001", "no dataclass decorator in a domain: values, ids and events are frozen by their base"),
    ("DCA-TAC-005", "no entity below an aggregate root: each aggregate is its root alone"),
    ("DCA-TAC-007", "no entity below an aggregate root: each aggregate is its root alone"),
    ("DCA-TAC-026", "no owned aggregate: the factory serves one project, no aggregate has an owner"),
    ("DCA-USE-006", "no class named *Result: a use case answers with its own value or a closed union of cases"),
    ("DCA-USE-007", "no class named *Result: a use case answers with its own value or a closed union of cases"),
    ("DCA-USE-015", "no class named *Result: a use case answers with its own value or a closed union of cases"),
    ("DCA-USE-008", "no class named *Response: an incoming adapter answers in its own protocol's terms"),
)


_FOUND = {}
_EMPTY = {}


def findings():
    """{rule id: findings} of every implemented, non-informational rule over the factory's package, read once."""
    if _FOUND:
        return _FOUND
    if RULES_SOURCE not in sys.path:
        sys.path.insert(0, RULES_SOURCE)
    from dca_rules import implemented, run
    from dca_rules.layout import DcaLayout
    from dca_rules.model import Project

    project = Project(
        DcaLayout(
            project_root=pathlib.Path(support.SCRIPTS),
            source_root=".",
            base_package="dca_factory",
            building_blocks=("dca_factory.building_blocks",),
            timestamp_types=("Moment",),   # the factory's own time value; a domain event carries one
            experimental="all",
            allow_empty=ALLOW_EMPTY,
        )
    )
    out = {}
    for rule_id in implemented():
        outcome = run(project, rule_id)
        if outcome.kind == "ran" and not outcome.informational:
            out[rule_id] = outcome.findings
        if outcome.kind == "empty":
            _EMPTY[rule_id] = outcome.allowed
        elif outcome.allowed is not None and outcome.selected:
            _EMPTY[rule_id] = f"selects {outcome.selected} now"
    _FOUND.update(out)
    return _FOUND


def empties():
    """{rule id: the package's reason, None where it gives none} for every rule that selects nothing, and the ids
    ALLOW_EMPTY names that select something now."""
    findings()
    return _EMPTY


@unittest.skipUnless(os.path.isdir(os.path.join(RULES_SOURCE, "dca_rules")), "no dca-python checkout beside the marketplace")
@unittest.skipUnless(sys.version_info >= (3, 12), "dca-rules needs Python 3.12")
class DcaRulesOnTheFactoryTest(unittest.TestCase):
    def test_every_rule_held_finds_nothing(self):
        broken = {
            rule_id: [f"{f.location} {f.message}" for f in items[:5]]
            for rule_id, items in findings().items()
            if items and rule_id not in NOT_YET_HELD
        }
        self.assertEqual({}, broken, "rules the factory's package breaks")

    def test_every_rule_selects_something_or_the_package_says_why(self):
        unexplained = sorted(rule_id for rule_id, why in empties().items() if why is None)
        self.assertEqual([], unexplained, "rules that select nothing in the package: say why in ALLOW_EMPTY")

    def test_every_id_allowed_empty_still_selects_nothing(self):
        selecting = sorted(rule_id for rule_id, why in empties().items() if why and why.startswith("selects "))
        self.assertEqual([], selecting, "ids that select something now: take them out of ALLOW_EMPTY")

    def test_every_id_not_yet_held_still_finds_something(self):
        held = sorted(rule_id for rule_id in NOT_YET_HELD if not findings().get(rule_id))
        self.assertEqual([], held, "ids the package now holds: take them out of NOT_YET_HELD")


if __name__ == "__main__":
    unittest.main()
