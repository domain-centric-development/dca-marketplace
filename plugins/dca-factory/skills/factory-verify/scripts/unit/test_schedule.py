"""The schedule: every story's state, the order and the next one to run, over a few synthetic stories."""

import unittest
from datetime import datetime, timedelta, timezone

from support import project, state


def schedule(p, **kwargs):
    return state.schedule_data(p.root, p.epics, p.runs, **kwargs)


class Order(unittest.TestCase):

    def test_a_story_comes_after_the_story_it_depends_on(self):
        with project() as p:
            p.story("A-1", deps=("B-1",))
            p.story("B-1")
            data = schedule(p)
            self.assertEqual(data["order"], ["B-1", "A-1"])
            self.assertEqual(data["next"], "B-1")
            self.assertEqual(data["stories"]["A-1"]["state"], "blocked")
            self.assertEqual(data["stories"]["A-1"]["detail"], "depends on B-1 (ready)")

    def test_a_delivered_dependency_frees_the_story(self):
        with project() as p:
            p.story("A-1", deps=("B-1",))
            p.story("B-1", status="delivered")
            data = schedule(p)
            self.assertEqual((data["next"], data["stories"]["A-1"]["state"]), ("A-1", "ready"))
            self.assertEqual(data["counts"], {"ready": 1, "delivered": 1})

    def test_an_unknown_dependency_and_a_cycle_block(self):
        with project() as p:
            p.story("A-1", deps=("NOPE",))
            p.story("C-1", deps=("C-2",))
            p.story("C-2", deps=("C-1",))
            data = schedule(p)
            self.assertEqual(data["stories"]["A-1"]["detail"], "depends on unknown NOPE")
            self.assertEqual(data["stories"]["C-1"]["detail"], "on a dependency cycle: C-1, C-2")
            self.assertEqual(data["order"][-2:], ["C-1", "C-2"])
            self.assertIsNone(data["next"])
            self.assertEqual(data["reason"], "nothing can run")

    def test_the_epics_order_comes_before_the_ids(self):
        with project() as p:
            p.epic("alpha", deps=("beta",))
            p.epic("beta")
            p.story("A-1", epic="alpha")
            p.story("Z-1", epic="beta", status="delivered")
            p.story("Z-2", epic="beta", status="delivered")
            self.assertEqual(schedule(p)["order"], ["Z-1", "Z-2", "A-1"])


class EpicDependencies(unittest.TestCase):

    def test_a_story_waits_until_every_story_of_the_epic_it_needs_is_delivered(self):
        with project() as p:
            p.epic("alpha", deps=("beta",))
            p.epic("beta")
            p.story("A-1", epic="alpha")
            p.story("B-1", epic="beta", status="delivered")
            p.story("B-2", epic="beta")
            data = schedule(p)
            self.assertEqual(data["stories"]["A-1"]["detail"], "its epic alpha depends on epic beta (1 of 2 delivered)")
            self.assertEqual(data["next"], "B-2")

    def test_an_epic_without_a_story_holds_what_depends_on_it(self):
        with project() as p:
            p.epic("alpha", deps=("beta",))
            p.epic("beta")
            p.story("A-1", epic="alpha")
            self.assertEqual(schedule(p)["stories"]["A-1"]["detail"],
                             "its epic alpha depends on epic beta, which has no story yet")

    def test_a_superseded_story_does_not_count_for_its_epic(self):
        with project() as p:
            p.epic("alpha", deps=("beta",))
            p.epic("beta")
            p.story("A-1", epic="alpha")
            p.story("B-1", epic="beta", status="delivered")
            p.story("B-2", epic="beta", status="superseded")
            self.assertEqual(schedule(p)["stories"]["A-1"]["state"], "ready")


class Checkout(unittest.TestCase):

    def test_two_stories_under_one_id_both_stop(self):
        with project() as p:
            p.story("S-1", epic="one")
            p.story("S-1", epic="two")
            data = schedule(p)
            self.assertEqual(sorted(s["state"] for s in data["stories"].values()), ["stopped", "stopped"])
            self.assertTrue(all("is not unique" in s["detail"] for s in data["stories"].values()))

    def test_a_story_with_tests_in_the_checkout_holds_it(self):
        with project() as p:
            p.story("A-1")
            p.story("B-1")
            p.write_and_journal("B-1", "plan")
            p.write_and_journal("B-1", "test")
            data = schedule(p)
            self.assertTrue(data["stories"]["B-1"]["holds"])
            self.assertEqual(data["next"], "B-1")

    def test_a_holder_that_cannot_run_stops_every_other_story(self):
        with project() as p:
            p.story("A-1")
            p.story("B-1")
            p.write_and_journal("B-1", "plan")
            p.write_and_journal("B-1", "test")
            p.evidence("B-1", ".rounds", "3")
            data = schedule(p)
            self.assertIsNone(data["next"])
            self.assertIn("B-1 holds unfinished code in the checkout (stopped)", data["reason"])

    def test_slots_start_several_stories_at_once(self):
        with project() as p:
            for story_id in ("A-1", "A-2", "A-3"):
                p.story(story_id)
            data = schedule(p, slots=2)
            self.assertEqual((data["next"], data["also"]), ("A-1", ["A-2"]))
            data = schedule(p, slots=2, busy=("A-1",))
            self.assertEqual((data["next"], data["also"]), ("A-2", []))
            self.assertEqual(data["stories"]["A-1"]["state"], "running")


class RunnerSteps(unittest.TestCase):
    """WP-112: the runner's own steps — integrate, merge, format — are journaled as running, apart from the stages."""

    def journal(self, p, story_id, *events):
        now = datetime.now(timezone.utc)
        lines = [f"{(now - timedelta(seconds=60 - n)).strftime('%Y-%m-%dT%H:%M:%SZ')}\t{kind}\t{name}\tby=runner"
                 for n, (kind, name) in enumerate(events)]
        p.evidence(story_id, "journal.tsv", "\n".join(lines) + "\n")

    def test_an_open_step_runs_and_a_stage_inside_it_runs_in_its_place(self):
        with project() as p:
            p.story("A-1")
            self.journal(p, "A-1", ("stage-start", "document"), ("stage-end", "document"), ("step-start", "integrate"))
            self.assertEqual([(s, st) for s, st, _t in state.running_stages(p.runs)], [("A-1", "integrate")])
            self.assertEqual(schedule(p)["stories"]["A-1"]["state"], "running")
            self.journal(p, "A-1", ("step-start", "integrate"), ("stage-start", "integrate"))
            self.assertEqual([st for _s, st, _t in state.running_stages(p.runs)], ["integrate"])
            self.journal(p, "A-1", ("step-start", "integrate"), ("step-start", "format"), ("step-end", "format"))
            self.assertEqual([st for _s, st, _t in state.running_stages(p.runs)], ["integrate"])

    def test_an_ended_step_runs_no_more_and_counts_as_no_stage_run(self):
        with project() as p:
            p.story("A-1")
            self.journal(p, "A-1", ("stage-start", "plan"), ("stage-end", "plan"), ("step-start", "integrate"),
                         ("step-end", "integrate"))
            self.assertEqual(state.running_stages(p.runs), [])
            self.assertEqual(sorted(state.journal_usage(p.runs, "A-1")), ["plan"])



class WaitingForTheLimit(unittest.TestCase):
    """#161: a stage that waits for the tool's usage limit to reset stays running until then, though it began long
    before what a stage may take."""

    def test_a_stage_waiting_for_its_reset_runs_and_one_past_it_is_interrupted(self):
        with project() as p:
            p.story("A-1")
            now = datetime.now(timezone.utc)
            at = lambda delta: (now + delta).strftime("%Y-%m-%dT%H:%M:%SZ")
            p.evidence("A-1", "journal.tsv", f"{at(timedelta(hours=-5))}\tstage-start\tbuilder\ttool=claude\n"
                                             f"{at(timedelta(hours=-4))}\tlimit\tbuilder\ttool=claude\t"
                                             f"until={at(timedelta(hours=1))}\n")
            self.assertEqual(schedule(p)["stories"]["A-1"]["state"], "running")
            p.evidence("A-1", "journal.tsv", f"{at(timedelta(hours=-9))}\tstage-start\tbuilder\ttool=claude\n"
                                             f"{at(timedelta(hours=-8))}\tlimit\tbuilder\ttool=claude\t"
                                             f"until={at(timedelta(hours=-7))}\n")
            self.assertNotEqual(schedule(p)["stories"]["A-1"]["state"], "running")


if __name__ == "__main__":
    unittest.main()
