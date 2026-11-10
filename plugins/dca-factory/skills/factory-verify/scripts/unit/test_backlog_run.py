"""The backlog run and the runner's request queue over stand-ins for their ports: which story runs next, when the run
ends, what --keep-going sets aside, and what becomes of a request whose process ended without a word."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.backlog.run_backlog import RunBacklogCommand, RunBacklogUseCase
from dca_factory.delivery.application.requests.request_queue import RequestQueue
from dca_factory.delivery.application.shared.backlog_schedule import ScheduleRead
from dca_factory.delivery.application.shared.requests import RequestRefused
from dca_factory.delivery.adapter.outgoing.files.request_files import aggregate_of, life_of
from dca_factory.delivery.domain.model.request import RequestState


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

    # RequestRepository: the aggregate over the same dicts
    def every(self):
        return [aggregate_of(r) for r in self.requests]

    def get(self, request_id):
        return aggregate_of(self.find(request_id.value))

    def save(self, request):
        if request.state is RequestState.DONE:
            self.delete_by_id(request.id)
            return request
        for r in self.requests:
            if r["id"] == request.id.value:
                for key, value in life_of(request).items():
                    if value is None:
                        r.pop(key, None)
                    else:
                        r[key] = value
        return request

    def delete_by_id(self, request_id):
        self.requests = [r for r in self.requests if r["id"] != request_id.value]

    def journal(self, *fields):
        self.journaled.append(fields)


class Events:
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)

    def publish_and_clear_events(self, aggregate):
        for event in aggregate.domain_events():
            self.publish(event)
        aggregate.clear_domain_events()


class Transactions:
    def in_transaction(self, work):
        return work()


def queue_of(store, records, starts, lines, events=None):
    return RequestQueue(store, records, starts, "me", lines, requests=store, events=events or Events(),
                        transactions=Transactions(), now=lambda: "2026-11-09T10:00:00Z")

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
        self.switched_off = False

    # BacklogCheckout
    def prune(self):
        pass

    def renew(self):
        return True

    def stop_asked(self):
        return None

    def stop_place(self):
        return "stop"

    def backlog_off(self):
        self.switched_off = True

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
    store = store or Store()
    queue = queue_of(store, Records(), Starts(), lines)
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

    def test_a_stop_request_ends_the_run_before_the_next_story_and_turns_the_backlog_off(self):
        schedule = Schedule("A-1")
        worker = Worker(schedule)
        store = Store({"id": "r1", "kind": "stop", "state": "queued"})
        use_case, _lines = backlog(schedule, worker, store)
        self.assertEqual(use_case.execute(RunBacklogCommand(1)), 0)
        self.assertEqual(worker.ran, [])
        self.assertTrue(worker.switched_off)


class Child:
    """A process that ends with <code> after it was asked <after> times."""

    def __init__(self, code=0, after=2):
        self.code, self.left = code, after

    def ended(self):
        self.left -= 1
        return self.code if self.left <= 0 else None


class LaneWorker(Worker):
    """The factory's worker: stories and requests as processes; the backlog on or off, the page open or closed."""

    def __init__(self, schedule, store, backlog=False, page=False):
        super().__init__(schedule)
        self.store, self.backlog, self.page, self.started, self.reads = store, backlog, page, [], 0

    def backlog_on(self):
        return self.backlog

    def page_open(self):
        return self.page

    def start(self, story, start):
        self.started.append(("story", story))
        if story in self.schedule.stories:
            self.schedule.stories.remove(story)
        return Child(0, after=4)

    def start_request(self, request):
        self.started.append(("request", request["id"]))
        self.store.requests = [r for r in self.store.requests if r["id"] != request["id"]]  # its process works it; done, its file goes
        return Child(0, after=1)


class Lane(unittest.TestCase):
    """WP-177: what a person asks for runs; the backlog only while it is on."""

    def run_lane(self, worker, store):
        use_case, lines = backlog(worker.schedule, worker, store)
        reads = worker.schedule.read
        worker.schedule.read = lambda *a: (setattr(worker, "reads", worker.reads + 1), reads(*a))[1]
        return use_case.execute(RunBacklogCommand(1, watch=True, stay=True, lane=True)), lines

    def test_a_request_runs_beside_a_story_that_takes_the_only_place_and_the_backlog_off_starts_none(self):
        store = Store({"id": "r1", "kind": "run", "state": "queued", "story": "B-1", "from": "plan", "by": "ann"},
                      {"id": "r2", "kind": "discover", "state": "queued", "by": "ann"})
        worker = LaneWorker(Schedule("A-1"), store)
        code, lines = self.run_lane(worker, store)
        self.assertEqual(0, code)
        self.assertEqual([("request", "r2"), ("story", "B-1")], worker.started)     # A-1: the backlog is off
        self.assertEqual(0, worker.reads)
        self.assertIn("the backlog is off and no page is open — the worker ends", lines.text())

    def test_with_the_backlog_on_its_story_takes_the_place_a_run_request_left(self):
        store = Store({"id": "r1", "kind": "run", "state": "queued", "story": "B-1", "from": "plan", "by": "ann"})
        worker = LaneWorker(Schedule("A-1"), store, backlog=True)
        worker.wait = lambda interval: setattr(worker, "backlog", False)       # `down` while it waits
        code, _lines = self.run_lane(worker, store)
        self.assertEqual(0, code)
        self.assertEqual([("story", "B-1"), ("story", "A-1")], worker.started)


class Queue(unittest.TestCase):

    def test_a_request_stopped_by_a_signal_is_queued_again_and_one_that_died_silently_failed(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "wish", "state": "running", "worker": "me"},
                      {"id": "r2", "kind": "wish", "state": "running", "worker": "me"})
        events = Events()
        queue = queue_of(store, Records(), Starts(), lines, events)
        queue.ended({"id": "r1"}, 143)
        queue.ended({"id": "r2"}, 1)
        self.assertEqual([r["state"] for r in store.requests], ["queued", "failed"])
        self.assertIn("before it said how", store.requests[1]["error"])
        self.assertNotIn("worker", store.requests[0])
        self.assertEqual(["RequestQueued", "RequestFailed"], [type(e).__name__ for e in events.published])

    def test_a_run_request_for_a_story_that_cannot_start_fails_and_says_why(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "run", "state": "queued", "story": "A-1"})
        queue = queue_of(store, Records(), Starts({"A-1": ("delivered", None, "")}), lines)
        self.assertIsNone(queue.take_run())
        self.assertEqual(store.requests[0]["state"], "failed")
        self.assertIn("A-1 is delivered; nothing runs.", lines.text())

    def test_a_waiting_request_runs_again_once_its_records_are_answered(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "wish", "state": "waiting", "record_file": "x"})
        queue = queue_of(store, Records({"r1": [("x", "D-1", "answered")]}), Starts(), lines)
        self.assertEqual(queue.next()["id"], "r1")
        self.assertEqual(store.requests[0]["answered"], "D-1")
        self.assertNotIn("record_file", store.requests[0])

    def test_a_waiting_request_whose_record_is_gone_runs_again_and_asks_again(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "wish", "state": "waiting", "record_file": "x"})
        queue = queue_of(store, Records(), Starts(), lines)
        self.assertEqual(queue.next()["id"], "r1")
        self.assertNotIn("answered", store.requests[0])
        self.assertIn("a record that is gone", lines.text())

    def test_a_run_request_taken_is_settled_and_gone(self):
        lines, events = Lines(), Events()
        store = Store({"id": "r1", "kind": "run", "state": "queued", "story": "A-1", "from": "plan"})
        asked = queue_of(store, Records(), Starts(), lines, events).take_run()
        self.assertEqual(asked.start, "plan")
        self.assertEqual(store.requests, [])
        self.assertEqual(["RequestSettled"], [type(e).__name__ for e in events.published])

    def test_a_request_left_running_by_another_factory_is_queued_again(self):
        lines = Lines()
        store = Store({"id": "r1", "kind": "wish", "state": "running", "worker": "other"},
                      {"id": "r2", "kind": "wish", "state": "running", "worker": "me"})
        queue_of(store, Records(), Starts(), lines).requeue_orphans()
        self.assertEqual([r["state"] for r in store.requests], ["queued", "running"])


if __name__ == "__main__":
    unittest.main()
