"""The backlog run and the runner's request queue over stand-ins for their ports: which story runs next, when the run
ends, what --keep-going sets aside, and what becomes of a request whose process ended without a word."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.backlog.run_backlog import RunBacklogCommand, RunBacklogUseCase
from dca_factory.delivery.application.requests.request_queue import RequestQueue
from dca_factory.delivery.application.shared.backlog_schedule import ScheduleRead
from dca_factory.delivery.application.shared.requests import RequestRefused


class Lines:
    def __init__(self):
        self.said = []

    def out(self, line):
        self.said.append(("out", line))

    def err(self, line):
        self.said.append(("err", line))

    def text(self):
        return "\n".join(line for _s, line in self.said)


class Store:
    def __init__(self, *requests):
        self.requests = [dict(r) for r in requests]
        self.journaled = []

    def all(self):
        return [dict(r) for r in self.requests]

    def find(self, request_id):
        for r in self.requests:
            if r["id"] == request_id:
                return dict(r)
        raise RequestRefused(f"no request {request_id}")

    def update(self, request, restore=False, **fields):
        for r in self.requests:
            if r["id"] == request["id"]:
                for key, value in fields.items():
                    if value is None:
                        r.pop(key, None)
                    else:
                        r[key] = value

    def remove(self, request):
        self.requests = [r for r in self.requests if r["id"] != request["id"]]

    def journal(self, *fields):
        self.journaled.append(fields)


class Records:
    def __init__(self, asked=None):
        self._asked = asked or {}

    def asked(self, request):
        return self._asked.get(request, [])


class Starts:
    def __init__(self, starts=None):
        self._starts = starts or {}

    def start(self, story):
        return self._starts.get(story)


class Schedule:
    """The stories in the order given; a story run with exit 0 or 3 leaves it, any other exit keeps it named."""

    def __init__(self, *stories, waits=False):
        self.stories = list(stories)
        self.waits = waits

    def read(self, slots, busy, skip):
        named = [(s, "plan") for s in self.stories if s not in busy and s not in skip][:max(slots, 1)]
        text = "\n".join(f"next: {s} {start}" for s, start in named) or "next: none — nothing ready"
        return ScheduleRead(True, text, tuple(named), self.waits)


class Worker:
    """Each story ends with the exit given (0 by default); a checkout that stays its own."""

    def __init__(self, schedule, exits=None, cap=False):
        self.schedule = schedule
        self.exits = exits or {}
        self.ran = []
        self.cap = cap

    # BacklogCheckout
    def prune(self):
        pass

    def renew(self):
        return True

    def stop_asked(self):
        return None

    def stop_place(self):
        return "stop"

    def claims(self):
        return ""

    def signalled(self):
        return None

    def wait(self, interval):
        raise AssertionError("the run waited")

    def pause(self):
        pass

    # BacklogWorker
    def run(self, story, start):
        self.ran.append((story, start))
        code = self.exits.get(story, 0)
        if code in (0, 3) and story in self.schedule.stories:
            self.schedule.stories.remove(story)
        return code

    def fresh(self, story, start):
        self.ran.append(("fresh", story, start))

    def work(self, busy):
        pass

    def capped(self):
        return self.cap


def backlog(schedule, worker, store=None):
    lines = Lines()
    queue = RequestQueue(store or Store(), Records(), Starts(), "me", lines)
    use_case = RunBacklogUseCase(schedule, worker, worker, queue, lines)
    return use_case, lines


class OneAtATime(unittest.TestCase):

    def test_the_stories_run_in_the_schedules_order_and_the_run_ends_when_nothing_more_can(self):
        schedule = Schedule("A-1", "B-1")
        worker = Worker(schedule)
        use_case, lines = backlog(schedule, worker)
        self.assertEqual(use_case.execute(RunBacklogCommand(1)), 0)
        self.assertEqual(worker.ran, [("A-1", "plan"), ("B-1", "plan")])
        self.assertIn("nothing more can run", lines.text())

    def test_a_story_that_stops_ends_the_run_with_its_exit(self):
        schedule = Schedule("A-1", "B-1")
        worker = Worker(schedule, exits={"A-1": 1})
        use_case, lines = backlog(schedule, worker)
        self.assertEqual(use_case.execute(RunBacklogCommand(1)), 1)
        self.assertEqual(worker.ran, [("A-1", "plan")])
        self.assertIn("story A-1 stopped (exit 1) — the backlog run ends here", lines.text())

    def test_keep_going_skips_a_stopped_story_and_answers_with_its_exit_at_the_end(self):
        schedule = Schedule("A-1", "B-1")
        worker = Worker(schedule, exits={"A-1": 1})
        use_case, lines = backlog(schedule, worker)
        self.assertEqual(use_case.execute(RunBacklogCommand(1, keep_going=True)), 1)
        self.assertEqual(worker.ran, [("A-1", "plan"), ("B-1", "plan")])
        self.assertIn("stopped in this run and skipped: A-1 (exit 1)", lines.text())

    def test_keep_going_does_not_skip_what_concerns_the_whole_run(self):
        for code, cap in ((2, False), (5, False), (4, True)):
            schedule = Schedule("A-1", "B-1")
            worker = Worker(schedule, exits={"A-1": code}, cap=cap)
            use_case, _lines = backlog(schedule, worker)
            self.assertEqual(use_case.execute(RunBacklogCommand(1, keep_going=True)), code)
            self.assertEqual(worker.ran, [("A-1", "plan")])

    def test_a_story_named_again_where_it_ran_stops_the_run_as_no_progress(self):
        schedule = Schedule("A-1")
        worker = Worker(schedule)
        worker.run = lambda story, start: worker.ran.append((story, start)) or 0     # A-1 stays named
        use_case, lines = backlog(schedule, worker)
        self.assertEqual(use_case.execute(RunBacklogCommand(1)), 1)
        self.assertIn("A-1 ran from plan and the schedule names it there again", lines.text())

    def test_a_run_request_goes_before_the_schedule_from_the_stage_it_names(self):
        schedule = Schedule("A-1")
        worker = Worker(schedule)
        store = Store({"id": "r1", "kind": "run", "state": "queued", "story": "B-1", "from": "build", "by": "ann"})
        use_case, _lines = backlog(schedule, worker, store)
        self.assertEqual(use_case.execute(RunBacklogCommand(1)), 0)
        self.assertEqual(worker.ran, [("fresh", "B-1", "build"), ("B-1", "build"), ("A-1", "plan")])
        self.assertEqual(store.requests, [])
        self.assertEqual(store.journaled[-1], ("request-end", "run", "r1", "exit=0"))

    def test_a_stop_request_ends_the_run_before_the_next_story(self):
        schedule = Schedule("A-1")
        worker = Worker(schedule)
        store = Store({"id": "r1", "kind": "stop", "state": "queued"})
        use_case, _lines = backlog(schedule, worker, store)
        self.assertEqual(use_case.execute(RunBacklogCommand(1)), 0)
        self.assertEqual(worker.ran, [])


class Queue(unittest.TestCase):

    def test_a_request_stopped_by_a_signal_is_queued_again_and_one_that_died_silently_failed(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "wish", "state": "running", "worker": "me"},
                      {"id": "r2", "kind": "wish", "state": "running", "worker": "me"})
        queue = RequestQueue(store, Records(), Starts(), "me", lines)
        queue.ended({"id": "r1"}, 143)
        queue.ended({"id": "r2"}, 1)
        self.assertEqual([r["state"] for r in store.requests], ["queued", "failed"])
        self.assertIn("before it said how", store.requests[1]["error"])

    def test_a_run_request_for_a_story_that_cannot_start_fails_and_says_why(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "run", "state": "queued", "story": "A-1"})
        queue = RequestQueue(store, Records(), Starts({"A-1": ("delivered", None, "")}), "me", lines)
        self.assertIsNone(queue.take_run())
        self.assertEqual(store.requests[0]["state"], "failed")
        self.assertIn("A-1 is delivered; nothing runs.", lines.text())

    def test_a_waiting_request_runs_again_once_its_records_are_answered(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "wish", "state": "waiting", "record_file": "x"})
        queue = RequestQueue(store, Records({"r1": [("x", "D-1", "answered")]}), Starts(), "me", lines)
        self.assertEqual(queue.next()["id"], "r1")
        self.assertEqual(store.requests[0]["answered"], "D-1")

    def test_a_request_left_running_by_another_factory_is_queued_again(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "wish", "state": "running", "worker": "other"},
                      {"id": "r2", "kind": "wish", "state": "running", "worker": "me"})
        RequestQueue(store, Records(), Starts(), "me", lines).requeue_orphans()
        self.assertEqual([r["state"] for r in store.requests], ["queued", "running"])


if __name__ == "__main__":
    unittest.main()
