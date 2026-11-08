"""The factory's own package held to the full DCA-Python rule suite, released and experimental rules alike: every
rule `dca-rules` implements finds nothing in `dca_factory/`, except the ids listed in NOT_YET_HELD — and each of those
still finds something, so the list shrinks as the package is brought in line and an id once held cannot break again.
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
    "DCA-USE-018": "the cli, the gate and the press settle drive the commands of several features",
}


_FOUND = {}


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
        )
    )
    out = {}
    for rule_id in implemented():
        outcome = run(project, rule_id)
        if outcome.kind == "ran" and not outcome.informational:
            out[rule_id] = outcome.findings
    _FOUND.update(out)
    return _FOUND


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

    def test_every_id_not_yet_held_still_finds_something(self):
        held = sorted(rule_id for rule_id in NOT_YET_HELD if not findings().get(rule_id))
        self.assertEqual([], held, "ids the package now holds: take them out of NOT_YET_HELD")


if __name__ == "__main__":
    unittest.main()
