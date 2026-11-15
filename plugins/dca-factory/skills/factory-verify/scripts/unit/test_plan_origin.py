"""A plan keeps the rules it came about under: the contract a check of the plan's form holds it to (`PlanOrigin`)."""

import os
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.files.plan_stamp import plan_digest, plan_origin, plan_stamp_fields
from dca_factory.delivery.domain.model.plan_facts import PlanOrigin, PlanStamp, UNSTAMPED_PLAN_CONTRACT
from dca_factory.delivery.domain.model.profile_facts import ContractNumber


class HeldToTest(unittest.TestCase):

    def test_a_stamped_plan_is_held_to_its_contract_never_a_later_one(self):
        self.assertEqual(33, PlanOrigin(PlanStamp.STAMPED, ContractNumber(33)).held_to(ContractNumber(35)).value)

    def test_the_profile_still_caps_a_stamped_plan(self):
        self.assertEqual(27, PlanOrigin(PlanStamp.STAMPED, ContractNumber(35)).held_to(ContractNumber(27)).value)

    def test_a_plan_from_before_the_stamps_is_held_to_the_contract_before_the_plan_checks(self):
        self.assertEqual(UNSTAMPED_PLAN_CONTRACT.value,
                         PlanOrigin(PlanStamp.BEFORE_STAMPS).held_to(ContractNumber(35)).value)

    def test_a_new_plan_is_held_to_the_profile(self):
        self.assertEqual(35, PlanOrigin(PlanStamp.NEW).held_to(ContractNumber(35)).value)


class PlanOriginTest(unittest.TestCase):

    def origin(self, plan, journal):
        with tempfile.TemporaryDirectory() as root:
            runs = os.path.join(root, ".dca-factory", "runs")
            os.makedirs(os.path.join(runs, "S-1"))
            with open(os.path.join(runs, "S-1", "plan.md"), "w", encoding="utf-8") as handle:
                handle.write(plan)
            evidence = os.path.join(root, ".dca-factory", "evidence", "S-1")
            os.makedirs(evidence)
            with open(os.path.join(evidence, "journal.tsv"), "w", encoding="utf-8") as handle:
                handle.write(journal(plan_digest(runs, "S-1")))
            return plan_origin(runs, "S-1")

    def test_the_stamp_of_the_passing_gate_that_saw_this_plan(self):
        found = self.origin("# Plan\n", lambda d: f"t\tgate\tplan\texit=0\tplan={d}\tcontract=34\tseq=1\n")
        self.assertEqual((PlanStamp.STAMPED, 34), (found.stamp, found.contract.value))

    def test_a_refused_gate_stamps_nothing(self):
        found = self.origin("# Plan\n", lambda d: f"t\tgate\tplan\texit=1\tplan={d}\tcontract=34\tseq=1\n")
        self.assertIs(PlanStamp.NEW, found.stamp)

    def test_passing_gates_without_a_stamp_are_from_before_the_stamps(self):
        found = self.origin("# Plan\n", lambda d: "t\tgate\tplan\texit=0\tby=runner\tseq=1\n")
        self.assertIs(PlanStamp.BEFORE_STAMPS, found.stamp)

    def test_a_plan_changed_since_its_stamp_is_new(self):
        found = self.origin("# Plan\n", lambda d: "t\tgate\tplan\texit=0\tplan=000000000000\tcontract=33\tseq=1\n")
        self.assertIs(PlanStamp.NEW, found.stamp)

    def test_the_stamp_names_the_digest_and_the_contract(self):
        with tempfile.TemporaryDirectory() as runs:
            os.makedirs(os.path.join(runs, "S-1"))
            with open(os.path.join(runs, "S-1", "plan.md"), "w", encoding="utf-8") as handle:
                handle.write("# Plan\n")
            self.assertEqual([f"plan={plan_digest(runs, 'S-1')}", "contract=35"], plan_stamp_fields(runs, "S-1", 35))


if __name__ == "__main__":
    unittest.main()
