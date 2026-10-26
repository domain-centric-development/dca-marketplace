"""A session's marks and the checkout's worker as use cases: what each asks its port, in which order, and its exit."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.checkout.give_checkout_back import GiveCheckoutBackCommand, GiveCheckoutBackUseCase
from dca_factory.delivery.application.checkout.mark_listening import MarkListeningCommand, MarkListeningUseCase
from dca_factory.delivery.application.checkout.take_checkout import TakeCheckoutCommand, TakeCheckoutUseCase
from dca_factory.delivery.application.session.end_session_stage import EndSessionStageCommand, EndSessionStageUseCase
from dca_factory.delivery.application.session.start_session_stage import (
    StartSessionStageCommand, StartSessionStageUseCase)


class Marks:
    def __init__(self, stage_exit=0, owned_exit=0):
        self.calls, self.stage_exit, self.owned_exit = [], stage_exit, owned_exit

    def stage(self, story, stage, edge, log):
        self.calls.append(("stage", edge))
        return self.stage_exit

    def record_owned(self, story):
        self.calls.append(("record",))

    def compare_owned(self, story, stage, ran):
        self.calls.append(("compare", ran))
        return self.owned_exit


class Checkout:
    def __init__(self):
        self.calls = []

    def freeze_windows(self):
        self.calls.append("freeze")

    def claim(self, owner):
        self.calls.append(f"claim {owner}")
        return 3

    def release(self, owner):
        self.calls.append(f"release {owner}")
        return 0

    def listening(self):
        self.calls.append("listening")
        return 0


class SessionStageTest(unittest.TestCase):

    def test_a_started_stage_records_the_persons_parts_only_when_its_mark_was_written(self):
        marks = Marks()
        self.assertEqual(0, StartSessionStageUseCase(marks).execute(StartSessionStageCommand("S-1", "plan")))
        self.assertEqual([("stage", "start"), ("record",)], marks.calls)
        refused = Marks(stage_exit=2)
        self.assertEqual(2, StartSessionStageUseCase(refused).execute(StartSessionStageCommand("S-1", "plan")))
        self.assertEqual([("stage", "start")], refused.calls)

    def test_an_ended_stage_compares_the_persons_parts_and_a_change_there_wins_the_exit(self):
        changed = Marks(owned_exit=7)
        self.assertEqual(7, EndSessionStageUseCase(changed).execute(EndSessionStageCommand("S-1", "plan")))
        self.assertEqual([("stage", "end"), ("compare", 0)], changed.calls)
        self.assertEqual(2, EndSessionStageUseCase(Marks(stage_exit=2)).execute(EndSessionStageCommand("S-1", "plan")))


class CheckoutTest(unittest.TestCase):

    def test_every_worker_command_freezes_the_open_windows_first(self):
        checkout = Checkout()
        self.assertEqual(3, TakeCheckoutUseCase(checkout).execute(TakeCheckoutCommand("me")))
        self.assertEqual(0, GiveCheckoutBackUseCase(checkout).execute(GiveCheckoutBackCommand()))
        self.assertEqual(0, MarkListeningUseCase(checkout).execute(MarkListeningCommand()))
        self.assertEqual(["freeze", "claim me", "freeze", "release None", "freeze", "listening"], checkout.calls)


if __name__ == "__main__":
    unittest.main()
