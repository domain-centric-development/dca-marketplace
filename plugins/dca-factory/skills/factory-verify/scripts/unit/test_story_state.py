"""Where a story stands, read off its files and its journal — the journal's order, never the clock, decides a pass."""

import contextlib
import io
import os
import unittest

from support import contract, project, state, write

SECOND = "2026-10-10T10:00:00Z"
STAGES = ("plan", "test", "build", "tidy", "judge", "document")


def full_pass(p, story_id, upto="judge", verdict="changes-requested", at=SECOND):
    """Every hand-over up to `upto` written and journaled in the run order, all in one second."""
    for stage in STAGES[:STAGES.index(upto) + 1]:
        p.write_and_journal(story_id, stage, f"# {stage}\nverdict: {verdict}\n" if stage == "judge" else None, at=at)


class Journal(unittest.TestCase):

    def test_every_append_takes_the_next_number_and_keeps_its_line_whole(self):
        with project() as p:
            self.assertEqual(state.journal_append(p.runs, "S-1", "stage-start", "plan", "tool=claude", at=SECOND), 1)
            self.assertEqual(state.journal_append(p.runs, "S-1", "note", "a\tb\nc", "", "why=x y"), 2)
            events = state.journal_events(p.runs, "S-1")
            self.assertEqual([(e["seq"], e["kind"], e["name"]) for e in events],
                             [(1, "stage-start", "plan"), (2, "note", "a b c")])
            self.assertEqual(events[0]["fields"], {"tool": "claude"})
            self.assertEqual(events[1]["fields"], {"why": "x y"})

    def test_the_number_orders_the_events_not_the_clock(self):
        with project() as p:
            path = state.journal_path(p.runs, "S-1")
            state.append_event(path, "wrote", "plan.md", "sha=a", at="2026-10-10T10:00:05Z")
            state.append_event(path, "wrote", "tests.md", "sha=b", at="2026-10-10T10:00:00Z")
            self.assertEqual([e["name"] for e in state.read_events(path)], ["plan.md", "tests.md"])

    def test_a_line_without_a_number_takes_its_position(self):
        with project() as p:
            path = write(state.journal_path(p.runs, "S-1"),
                         f"{SECOND}\tstage-start\tplan\n{SECOND}\tstage-end\tplan\texit=0\nbroken line\n")
            self.assertEqual([(e["seq"], e["kind"]) for e in state.read_events(path)],
                             [(1, "stage-start"), (2, "stage-end")])
            self.assertEqual(state.journal_append(p.runs, "S-1", "note", "x"), 3)

    def test_gate_runs_read_as_pass_held_and_fail_and_a_file_gone_drops_its_write(self):
        with project() as p:
            for gate, code in (("plan", "exit=0"), ("document", "exit=3"), ("build", "exit=1")):
                state.journal_append(p.runs, "S-1", "gate", gate, code)
            state.journal_append(p.runs, "S-1", "wrote", "plan.md", "sha=abc")
            state.journal_append(p.runs, "S-1", "wrote", "plan.md", "sha=gone")
            self.assertEqual(state.pass_marks(p.runs, "S-1"), {"pass:plan": 1, "held:document": 2, "fail:build": 3})


class StatusFirst(unittest.TestCase):

    def test_a_story_with_no_run_is_ready_for_its_plan(self):
        with project() as p:
            p.story("S-1")
            self.assertEqual(p.state_of("S-1"), ("ready", "plan", ""))

    def test_a_draft_is_unreleased(self):
        with project() as p:
            p.story("S-1", status="draft")
            self.assertEqual(p.state_of("S-1")[:2], ("unreleased", None))

    def test_superseded_and_delivered_hold_whatever_the_run_folder_says(self):
        with project() as p:
            p.story("S-1", status="superseded")
            p.story("S-2", status="delivered")
            p.run_file("S-2", ".gate-build.txt", "gate:fail tests-green\n")
            self.assertEqual(p.state_of("S-1")[0], "superseded")
            self.assertEqual(p.state_of("S-2"), ("delivered", None, ""))

    def test_three_rounds_stop_the_story(self):
        with project() as p:
            p.story("S-1")
            p.evidence("S-1", ".rounds", "3\n")
            self.assertEqual(p.state_of("S-1")[:2], ("stopped", None))


class PassOrder(unittest.TestCase):

    def test_the_next_stage_is_the_first_file_not_written(self):
        with project() as p:
            p.story("S-1")
            p.write_and_journal("S-1", "plan", at=SECOND)
            self.assertEqual(p.state_of("S-1"), ("in-progress", "test", "tests.md not written yet"))

    def test_events_in_one_second_are_ordered_by_their_number(self):
        with project() as p:
            p.story("S-1")
            p.write_and_journal("S-1", "plan", at=SECOND)
            p.write_and_journal("S-1", "test", at=SECOND)
            self.assertEqual(p.state_of("S-1")[1], "build")
            p.write_and_journal("S-1", "plan", "# plan, again\n", at=SECOND)       # a re-plan in the same second
            self.assertEqual(p.state_of("S-1"), ("in-progress", "test", "tests.md not written yet"))

    def test_a_judge_asking_for_changes_sends_the_story_to_build(self):
        with project() as p:
            p.story("S-1")
            full_pass(p, "S-1")
            self.assertEqual(p.state_of("S-1"), ("in-progress", "build", "the judge requested changes"))

    def test_a_build_window_rewriting_identical_content_is_marked_same_and_moves_on(self):
        with project() as p:
            path = p.story("S-1")
            full_pass(p, "S-1")
            state.record_owned(p.runs, "S-1", path)
            p.handover("S-1", "build")                                         # the same bytes again
            self.assertEqual(state.owned_end(p.runs, "S-1", "build", ran="0"), 0)
            last = state.journal_events(p.runs, "S-1")[-1]
            self.assertEqual((last["kind"], last["name"], last["fields"].get("same")), ("wrote", "build.md", "1"))
            self.assertEqual(p.state_of("S-1"), ("in-progress", "tidy", "tidy.md not written yet"))

    def test_a_window_that_broke_off_marks_nothing(self):
        with project() as p:
            path = p.story("S-1")
            full_pass(p, "S-1")
            state.record_owned(p.runs, "S-1", path)
            state.owned_end(p.runs, "S-1", "build", ran="1")
            self.assertEqual(p.state_of("S-1")[1], "build")

    def test_a_shared_window_marks_every_stage_it_left_unchanged(self):
        with project() as p:
            path = p.story("S-1")
            full_pass(p, "S-1", upto="tidy")
            state.record_owned(p.runs, "S-1", path)
            state.owned_end(p.runs, "S-1", "builder", ran="0")
            same = [e["name"] for e in state.journal_events(p.runs, "S-1") if e["fields"].get("same") == "1"]
            self.assertEqual(same, ["plan.md", "tests.md", "build.md", "tidy.md"])

    def test_a_later_pass_of_a_post_gated_stage_holds_its_file(self):
        with project() as p:
            p.story("S-1")
            full_pass(p, "S-1", upto="build")
            p.write_and_journal("S-1", "test", "# tests, again\n", at=SECOND)
            self.assertEqual(p.state_of("S-1")[1], "build")
            state.journal_append(p.runs, "S-1", "gate", "build", "exit=0", at=SECOND)
            self.assertEqual(p.state_of("S-1")[1], "tidy")
            self.assertTrue(state.gate_passed_since(p.runs, "S-1", "build", "build"))

    def test_an_outdated_mark_makes_a_file_an_earlier_passs(self):
        with project() as p:
            p.story("S-1")
            full_pass(p, "S-1", upto="document", verdict="pass")
            self.assertEqual(p.state_of("S-1")[1:], ("document", "document.md is written, its gate has not passed yet"))
            state.journal_append(p.runs, "S-1", "outdated", "document.md", "by=integrate")
            self.assertEqual(p.state_of("S-1")[1:], ("document", "document.md not written yet"))


class Refusals(unittest.TestCase):

    def refuse_plan(self, p, path, digest=True):
        p.run_file("S-1", ".gate-plan.txt", "gate:fail story\n")
        fields = ["exit=1"] + ([f"backlog={state.backlog_digest(path)}"] if digest else [])
        state.journal_append(p.runs, "S-1", "gate", "plan", *fields)

    def test_a_plan_refusal_holds_until_the_story_or_its_epic_changes(self):
        with project() as p:
            path = p.story("S-1")
            self.refuse_plan(p, path)
            self.assertEqual(p.state_of("S-1")[:2], ("stopped", None))
            p.story("S-1", text=contract.read_text(path) + "- shows-more: more\n")
            self.assertEqual(p.state_of("S-1"),
                             ("in-progress", "plan", "the story changed after the plan gate refused it — planned again"))

    def test_an_edited_epic_also_lets_the_plan_gate_ask_again(self):
        with project() as p:
            path = p.story("S-1")
            self.refuse_plan(p, path)
            write(os.path.join(p.epics, "sample", contract.EPIC_FILE),
                  contract.read_text(os.path.join(p.epics, "sample", contract.EPIC_FILE)) + "More.\n")
            self.assertEqual(p.state_of("S-1")[:2], ("in-progress", "plan"))

    def test_a_plan_refusal_without_a_digest_stays_stopped(self):
        with project() as p:
            path = p.story("S-1")
            self.refuse_plan(p, path, digest=False)
            p.story("S-1", text=contract.read_text(path) + "- shows-more: more\n")
            self.assertEqual(p.state_of("S-1")[:2], ("stopped", None))

    def test_a_stage_gate_refusal_runs_the_stage_again(self):
        with project() as p:
            p.story("S-1")
            full_pass(p, "S-1", upto="build")
            p.run_file("S-1", ".gate-build.txt", "gate:fail tests-green\n")
            self.assertEqual(p.state_of("S-1"), ("in-progress", "build", "the build gate refused — the stage runs again"))

    def test_needs_human_without_a_record_stops_the_story(self):
        with project() as p:
            p.story("S-1")
            p.write_and_journal("S-1", "plan", "# plan\n## needs-human\nwhy: two readings\n")
            self.assertEqual(p.state_of("S-1"),
                             ("stopped", None, "plan.md ends in `## needs-human` without an open record"))


class Decisions(unittest.TestCase):

    RECORD = "---\nid: S-1-01\nstory: S-1\nstage: plan\n---\n## Question\nwhich one?\n"

    def test_an_open_record_makes_the_story_wait(self):
        with project() as p:
            store = contract.decisions_store(p.story("S-1"))
            write(os.path.join(store, "01.md"), self.RECORD)
            self.assertEqual(p.state_of("S-1"), ("waiting", None, "decision S-1-01"))

    def test_an_answer_resumes_at_the_stage_that_applies_it_until_its_file_cites_the_id(self):
        with project() as p:
            store = contract.decisions_store(p.story("S-1"))
            write(os.path.join(store, "01.md"), self.RECORD + "\n## Answer\nanswer: the first\nby: a person\nat: now\n")
            p.write_and_journal("S-1", "plan")
            self.assertEqual(p.state_of("S-1"), ("resumable", "plan", "decision S-1-01 answered — its stage applies it"))
            p.write_and_journal("S-1", "plan", "# plan\napplies S-1-01\n")
            self.assertEqual(p.state_of("S-1")[:2], ("in-progress", "test"))

    def test_the_story_changed_under_a_stage_stops_it(self):
        with project() as p:
            path = p.story("S-1")
            state.record_owned(p.runs, "S-1", path)
            p.story("S-1", text=contract.read_text(path) + "edited\n")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(state.owned_end(p.runs, "S-1", "plan"), 7)
            self.assertEqual(p.state_of("S-1")[:2], ("stopped", None))
            self.assertIn("--owned-confirm S-1", p.state_of("S-1")[2])


if __name__ == "__main__":
    unittest.main()
