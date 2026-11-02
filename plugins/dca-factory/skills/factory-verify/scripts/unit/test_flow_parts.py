"""The parts the flow falls into: the foundation once, the inflow to the backlog, the cycle every story turns, the
rulebook beside them (WP-178)."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.application.status.show_help import PARTS


class FlowPartsTest(unittest.TestCase):

    def test_the_cycle_is_backlog_run_decide_delivered_in_order(self):
        cycle = next(p for p in PARTS if p["part"] == "cycle")
        self.assertEqual(["backlog", "run", "decide", "delivered"], cycle["tabs"])
        self.assertTrue(cycle["ordered"])

    def test_discover_flows_in_and_is_no_step_of_the_cycle(self):
        self.assertEqual({"foundation": ["describe", "set up"], "inflow": ["discover"],
                          "cycle": ["backlog", "run", "decide", "delivered"], "rules": []},
                         {p["part"]: p["steps"] for p in PARTS})

    def test_every_tab_sits_in_one_part_in_the_views_order(self):
        self.assertEqual(["describe", "discover", "backlog", "run", "decide", "delivered", "rules"],
                         [tab for p in PARTS for tab in p["tabs"]])


if __name__ == "__main__":
    unittest.main()
