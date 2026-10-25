"""A person's requests (WP-91): what a view's action becomes as a request, what a request may name, the order the
factory works them in, and the project's own decision records beside the stories'."""

import json
import os
import subprocess
import sys
import time
import unittest

from support import contract, project, write

from dca_factory import cli, gate, state
from dca_factory.delivery.adapter.outgoing.process import factory_process as service
from dca_factory.delivery.application.status.actions import request_of
from dca_factory.delivery.adapter.incoming.runner.usage import book_request_usage
from dca_factory.delivery.adapter.outgoing.files import request_files
from dca_factory.delivery.adapter.outgoing.files.decision_record_files import project_record_path, request_records
from dca_factory.delivery.adapter.outgoing.files.journal_files import mark_questioned
from dca_factory.delivery.adapter.outgoing.files.story_files import names_story
from dca_factory.delivery.application.requests.check_request import CheckRequestCommand
from dca_factory.delivery.application.requests.pending import mark_pending, pending_id
from dca_factory.delivery.application.requests.retry_request import RetryRequestCommand
from dca_factory.delivery.application.requests.take_back_request import TakeBackRequestCommand
from dca_factory.delivery.application.requests.write_request import WriteRequestCommand
from dca_factory.delivery.application.shared.requests import DuplicateRequest, operations_of, RequestRefused, STATES
from dca_factory.infrastructure import delivery as wiring


def validate(cwd, kind, fields, words):
    checked = wiring.check_request(cwd).execute(CheckRequestCommand(kind, fields, words))
    return checked.fields, checked.words


def write_request(cwd, kind, fields, words, by):
    written = wiring.write_request(cwd).execute(WriteRequestCommand(kind, fields, words, by))
    return written.id, written.path


def settle(cwd, runs, request, at):
    return wiring.settlement(cwd, runs).settle(request, at)


RECORD = """---
id: {id}
{story}stage: {stage}
asked: 2026-10-24T10:00:00Z
{extra}---

# Which one?

## Options
- a: this one
- b: that one

## Recommendation
a
"""


def record(story="", rid="", stage="plan", extra=""):
    return RECORD.format(id=rid, story=f"story: {story}\n" if story else "", stage=stage, extra=extra)


class Actions(unittest.TestCase):
    """The request a view's press writes is the factory's: `request_of` reads the action's slash command."""

    def setUp(self):
        contract.set_places({})

    def test_each_session_command_has_its_request(self):
        cases = {
            "/factory-run US-1": ("run", {"story": "US-1"}, "", ""),
            "/factory-run show the newest first": ("wish", {}, "show the newest first", ""),
            "/factory-run faster": ("wish", {}, "faster", ""),
            "/factory-backlog release US-1 US-2": ("release", {"story": "US-1 US-2"}, "", ""),
            "/factory-backlog stories shop": ("stories", {"epic": "shop"}, "", ""),
            "/factory-backlog journey shop": ("journey", {"epic": "shop"}, "", ""),
            "/factory-backlog epic P-1 --from product/discovery/cart/discovery.md":
                ("epic-from", {"topic": "cart", "proposal": "P-1"}, "", ""),
            "/factory-backlog US-3#2: the copy drifts": ("wish", {}, "US-3#2: the copy drifts", ""),
            "/factory-backlog": ("wish", {}, "", "words"),
            "/factory-decisions US-3 US-3-01: answer b": ("answer", {"record": "US-3-01"}, "b", ""),
            "/factory-decisions US-3": ("answer", {"story": "US-3"}, "", "record"),
            "/factory-decisions US-3 US-3-01: answer": ("answer", {"record": "US-3-01"}, "", "words"),
            "/factory-decisions Q-1: answer": ("answer", {"record": "Q-1"}, "", "words"),
            "/factory-decisions US-3 US-3-02: answer accepted": ("accept", {"story": "US-3"}, "", ""),
            "/dca-describe tech: PostgreSQL 17": ("describe", {}, "tech: PostgreSQL 17", ""),
            "/factory-discover": ("discover", {}, "", "words"),
        }
        with project() as p:
            p.story("US-1")
            for skill, (kind, fields, words, still) in cases.items():
                with self.subTest(skill=skill):
                    self.assertEqual(request_of(skill, names_story),
                                     dict(kind=kind, fields=fields, words=words, open=still))

    def test_a_correction_asks_for_words_and_offers_the_reason_codes(self):
        for skill in ("/factory-decisions US-3 US-3-02: answer correction:", "/factory-decisions US-3: answer correction:",
                      "/factory-decisions US-3: answer correction"):
            with self.subTest(skill=skill):
                self.assertEqual(request_of(skill, names_story),
                                 dict(kind="correct", fields={"story": "US-3"}, words="", open="words",
                                      choices=list(gate.REASON_CODES)))

    def test_what_no_request_does_has_none(self):
        for skill in ("/factory-setup", "/factory-update", "/factory-verify US-1", "", None):
            self.assertIsNone(request_of(skill, names_story))


class Written(unittest.TestCase):

    def setUp(self):
        contract.set_places({})

    def test_a_kind_names_what_it_must_and_nothing_else(self):
        with project() as p:
            p.story("US-1", status="draft")
            refused = (("wish", {}, ""), ("wish", {"story": "US-1"}, "x"), ("stories", {}, ""),
                       ("stories", {"epic": "nope"}, ""), ("release", {"story": "US-1", "epic": "sample"}, ""),
                       ("run", {"story": "US-1", "from": "nowhere"}, ""), ("stop", {}, "words"),
                       ("run", {"story": "../x"}, ""), ("answer", {"record": "US-1-01"}, "b"), ("nope", {}, ""))
            for kind, fields, words in refused:
                with self.subTest(kind=kind, fields=fields):
                    with self.assertRaises(RequestRefused):
                        validate(p.root, kind, fields, words)

    def test_a_release_naming_an_epic_releases_the_epic(self):
        with project() as p:
            p.story("US-1", status="draft")
            fields, _words = validate(p.root, "release", {"story": "sample"}, "")
            self.assertEqual(fields, {"epic": "sample"})

    def test_an_answer_takes_an_option_named_in_words_and_refuses_one_the_record_lacks(self):
        with project() as p:
            p.story("US-1")
            write(os.path.join(p.epics, "sample", "US-1", "decisions", "01.md"), record("US-1", "US-1-01"))
            fields, words = validate(p.root, "answer", {"record": "US-1-01"}, "B")
            self.assertEqual((fields["option"], fields["story"], words), ("b", "US-1", ""))
            with self.assertRaises(RequestRefused):
                validate(p.root, "answer", {"record": "US-1-01"}, "c")
            fields, words = validate(p.root, "answer", {"record": "US-1-01"}, "neither, a third way")
            self.assertEqual(words, "neither, a third way")
            fields, words = validate(p.root, "answer", {"record": "US-1-01"}, "no")
            self.assertEqual((fields.get("option"), words), (None, "no"))
            write_request(p.root, "answer", {"record": "US-1-01"}, "b", "a")
            with self.assertRaises(RequestRefused):        # one record takes one answer
                write_request(p.root, "answer", {"record": "US-1-01"}, "a", "a")

    def test_requests_are_worked_in_the_order_they_were_written_whatever_their_kind(self):
        with project() as p:
            p.story("US-1", status="draft")
            first, _ = write_request(p.root, "wish", {}, "zz first", "a")
            second, _ = write_request(p.root, "release", {"story": "US-1"}, "", "a")
            third, _ = write_request(p.root, "stop", {}, "", "a")
            self.assertEqual([r["id"] for r in request_files.list_requests()], [first, second, third])

    def test_the_same_request_twice_is_one(self):
        with project() as p:
            p.story("US-1", status="draft")
            first, _ = write_request(p.root, "release", {"story": "US-1"}, "", "a")
            with self.assertRaises(DuplicateRequest) as caught:
                write_request(p.root, "release", {"story": "US-1"}, "", "b")
            self.assertEqual(caught.exception.existing, first)

    def test_a_state_change_keeps_the_words_and_a_broken_file_reads_as_failed(self):
        with project() as p:
            rid, path = write_request(p.root, "wish", {}, "line one\nline two", "a")
            request = request_files.find_request(rid)
            request_files.update_request(request, state="running", worker="runner:h:1")
            again = request_files.find_request(rid)
            self.assertEqual((again["state"], again["worker"], again["words"]),
                             ("running", "runner:h:1", "line one\nline two"))
            write(path, "no front matter")
            self.assertEqual(request_files.find_request(rid)["state"], "failed")

    def test_a_running_request_is_not_dropped_and_only_a_failed_one_retried(self):
        with project() as p:
            rid, _ = write_request(p.root, "wish", {}, "x", "a")
            with self.assertRaises(RequestRefused):
                wiring.retry_request(p.root).execute(RetryRequestCommand(rid))
            request_files.update_request(request_files.find_request(rid), state="running")
            with self.assertRaises(RequestRefused):
                wiring.take_back_request(p.root).execute(TakeBackRequestCommand(rid))

    def test_one_queued_answer_holds_every_answer_to_its_record(self):
        pending = [dict(id="R1", kind="answer", record="US-1-01", story="US-1", words="", option="b")]
        for request in (dict(kind="answer", fields={"record": "US-1-01"}, words="a", open=""),
                        dict(kind="answer", fields={"record": "US-1-01"}, words="", open="words")):
            with self.subTest(request=request):
                self.assertEqual(pending_id(request, pending), "R1")
        self.assertEqual(pending_id(dict(kind="answer", fields={"record": "US-1-02"}, words="a", open=""),
                                             pending), "")

    def test_the_chosen_answer_says_queued_and_the_other_choices_wait_on_it(self):
        pending = [dict(id="R1", kind="answer", record="US-1-01", story="US-1", words="", option="b")]
        offer = lambda words, open_: dict(request=dict(kind="answer", fields={"record": "US-1-01"}, words=words, open=open_))
        actions = mark_pending([offer("a", ""), offer("b", ""), offer("", "words"), dict(label="no request")],
                                        pending)
        self.assertEqual([(a.get("queued"), a.get("waits_on")) for a in actions],
                         [("", "R1"), ("R1", ""), ("", "R1"), (None, None)])
        running = [dict(pending[0], state="waiting")]
        self.assertEqual([a["queued_text"] for a in mark_pending([offer("b", ""), offer("a", "")], running)],
                         ["asks you", ""])
        worded = [dict(pending[0], option="", words="neither")]
        self.assertEqual([a["queued"] for a in mark_pending([offer("a", ""), offer("", "words")], worded)],
                         ["", "R1"])

    def test_what_a_person_can_do_with_a_request_follows_its_state(self):
        self.assertEqual({state: operations_of(state) for state in STATES},
                         {"queued": ["drop"], "running": ["follow"], "waiting": ["drop"], "failed": ["retry", "drop"]})


class ProjectRecords(unittest.TestCase):

    def setUp(self):
        contract.set_places({})

    def test_the_inbox_reads_the_projects_records_beside_the_stories(self):
        with project() as p:
            p.story("US-1")
            write(os.path.join(p.epics, "sample", "US-1", "decisions", "01.md"), record("US-1", "US-1-01"))
            folder = os.path.join(p.root, "product", "decisions")
            write(os.path.join(folder, "20261024T100000Z-wish.md"),
                  record(rid="20261024T100000Z-wish", stage="request", extra="request: R-1\n"))
            write(os.path.join(folder, "misplaced.md"), record("US-1", "misplaced"))
            found = {name: (state, error is None) for name, _f, _b, state, error, _p in contract.decision_files(p.root)}
            self.assertEqual(found, {"US-1-01": ("open", True), "20261024T100000Z-wish": ("open", True),
                                     "misplaced": ("unreadable", False)})
            self.assertEqual([rid for _p, rid, _s in request_records(p.root, "R-1")],
                             ["20261024T100000Z-wish"])

    def test_a_project_record_is_where_a_request_without_a_story_asks(self):
        with project():
            path = project_record_path("R-1", "A new Epic?")
            self.assertTrue(path.replace(os.sep, "/").startswith("product/decisions/"), path)
            self.assertTrue(path.endswith("-a-new-epic.md"), path)


class Outputs(unittest.TestCase):

    def setUp(self):
        contract.set_places({})

    def test_an_output_is_pruned_once_its_request_is_gone_and_old(self):
        with project():
            rid, _ = write_request(os.getcwd(), "wish", {}, "x", "a")
            live, gone = request_files.out_path(rid), request_files.out_path("20200101T000000000Z-wish")
            for path in (live, gone):
                write(path, "out")
                os.utime(path, (time.time() - 30 * 86400,) * 2)
            request_files.prune_outputs(days=7)
            self.assertEqual((os.path.isfile(live), os.path.isfile(gone)), (True, False))


class RecordText(unittest.TestCase):

    def test_a_record_shows_its_question_and_leaves_options_recommendation_and_answer_to_the_actions(self):
        body = record(story="s").split("---\n", 2)[2].replace("## Options", "## Question\nWhich `one`?\n\n## Options")
        body += "\n## Answer\nanswer: a\n"
        self.assertEqual([(s["heading"], s["text"]) for s in cli.record_sections(body)], [("Question", "Which `one`?")])


ACCEPTANCE = """---
id: {rid}
story: {story}
stage: document
kind: acceptance
asked: 2026-10-24T10:00:00Z
---

# Accept {story}?

## Question
Look at it.
"""


class Settled(unittest.TestCase):
    """What the factory settles without a tool, and what it leaves to a skill."""

    def setUp(self):
        contract.set_places({})

    def request(self, kind, **fields):
        return dict(id="R-9", kind=kind, by="Ann", words="", **fields)

    def test_an_acceptance_is_written_as_accepted(self):
        with project() as p:
            p.story("US-1")
            path = write(os.path.join(p.epics, "sample", "US-1", "decisions", "accept-1.md"),
                         ACCEPTANCE.format(rid="US-1-accept-1", story="US-1"))
            self.assertEqual(settle(p.root, p.runs, self.request("accept", story="US-1"), "2026-10-25T08:00:00Z"),
                             ["US-1-accept-1"])
            self.assertEqual(contract.decision_state(contract.read_text(path))[1],
                             {"answer": "accepted", "by": "Ann", "at": "2026-10-25T08:00:00Z"})

    def test_an_option_is_written_for_a_requests_question_and_a_stages_question_goes_to_the_skill(self):
        with project() as p:
            p.story("US-1")
            asked = write(os.path.join(p.epics, "sample", "US-1", "decisions", "01.md"),
                          record("US-1", "US-1-01", stage="backlog", extra="request: R-1\n"))
            staged = write(os.path.join(p.epics, "sample", "US-1", "decisions", "02.md"), record("US-1", "US-1-02"))
            at = "2026-10-25T08:00:00Z"
            self.assertEqual(settle(p.root, p.runs, self.request("answer", record="US-1-01", option="b"), at),
                             ["US-1-01"])
            self.assertEqual(contract.decision_state(contract.read_text(asked))[1]["answer"], "b")
            self.assertIsNone(settle(p.root, p.runs, self.request("answer", record="US-1-02", option="a"), at))
            self.assertIsNone(settle(p.root, p.runs, dict(self.request("answer", record="US-1-01", option="a"),
                                                                   words="neither"), at))
            self.assertEqual(contract.decision_state(contract.read_text(staged))[0], "open")

    def test_a_draft_its_question_pass_ran_on_is_released_and_one_changed_since_is_the_skills(self):
        with project() as p:
            path = p.story("US-1", status="draft")
            changed = p.story("US-2", status="draft")
            mark_questioned(p.root, p.runs, [os.path.relpath(path, p.root), os.path.relpath(changed, p.root)], "R-1")
            with open(changed, "a", encoding="utf-8") as handle:
                handle.write("\nOne more criterion.\n")
            at = "2026-10-25T08:00:00Z"
            self.assertIsNone(settle(p.root, p.runs, self.request("release", story="US-2"), at))
            self.assertEqual(settle(p.root, p.runs, self.request("release", story="US-1"), at), ["US-1"])
            front, body = contract.read_front_matter(path)
            self.assertEqual(front["status"], "approved")
            self.assertIn("- answered: the story is released for building (request R-9, Ann, 2026-10-25T08:00:00Z).", body)

    def test_a_draft_an_open_record_holds_is_the_skills_to_release(self):
        with project() as p:
            path = p.story("US-1", status="draft")
            mark_questioned(p.root, p.runs, [os.path.relpath(path, p.root)], "R-1")
            write(os.path.join(p.epics, "sample", "US-1", "decisions", "01.md"), record("US-1", "US-1-01", stage="backlog"))
            self.assertIsNone(settle(p.root, p.runs, self.request("release", story="US-1"), "2026-10-25T08:00:00Z"))
            self.assertEqual(contract.read_front_matter(path)[0]["status"], "draft")


class RequestUsage(unittest.TestCase):

    def setUp(self):
        contract.set_places({})

    def test_a_window_a_request_opened_is_booked_with_its_priced_share_and_a_session_window_is_not(self):
        with project():
            runs, here = contract.place("runs"), os.getcwd()
            os.environ["FACTORY_REQUEST"] = "R1"
            try:
                for story in ("S-1", "S-2"):
                    state.mark_window(here, runs, story, "backlog", "start")
                    state.mark_window(here, runs, story, "backlog", "end")
            finally:
                del os.environ["FACTORY_REQUEST"]
            state.mark_window(here, runs, "S-3", "decisions", "start")
            cost = wiring.book_request_cost(here, runs)
            booked = book_request_usage(cost, "R1", "claude", "model=m\tinput=10\tcache_read=100\t"
                                                                    "cache_write=20\toutput=40\tcost=1.0\tseconds=9")
            self.assertEqual(booked, [("S-1", "backlog"), ("S-2", "backlog")])
            usage = [e["fields"] for e in state.journal_events(runs, "S-1") if e["kind"] == "usage"]
            self.assertEqual([(u["request"], u["input"], u["output"], u["cost"]) for u in usage],
                             [("R1", "5", "20", "0.5000")])
            self.assertEqual(book_request_usage(cost, "R2", "claude", "unknown"), [])


class Ended(unittest.TestCase):

    def setUp(self):
        contract.set_places({})

    def test_a_factory_gone_without_a_down_says_why_and_a_stop_request_is_no_such_end(self):
        with project():
            gone = subprocess.Popen([sys.executable, "-c", "pass"])
            gone.wait()
            write(service.own_file(service.LOG_FILE), "== 2026-10-24T10:00:00Z up by a: earlier\nfactory: an older start\n"
                  "== 2026-10-24T11:00:00Z up by a: factory.sh run --watch --stay\nclaim: runner holds the checkout\n"
                  "factory: the installed pipeline changed\nfactory:   since the install. Nothing was started.\n")
            write(service.own_file(service.FACTORY_FILE), json.dumps(dict(pid=gone.pid, started="2026-10-24T11:00:00Z",
                                                                           log=".dca-factory/factory.log")))
            self.assertEqual(service.ended(os.getcwd())["why"],
                             "the installed pipeline changed since the install. Nothing was started.")
            write(service.stop_file(), "stop")
            self.assertIsNone(service.ended(os.getcwd()))
            os.remove(service.stop_file())
            write(service.own_file(service.FACTORY_FILE), json.dumps(dict(pid=os.getpid(), started="x")))
            self.assertIsNone(service.ended(os.getcwd()), "a factory that runs has not ended")


if __name__ == "__main__":
    unittest.main()
