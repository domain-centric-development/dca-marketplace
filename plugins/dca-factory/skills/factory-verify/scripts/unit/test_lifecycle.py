"""The factory as a process — started, ended, its page, its worker — and the discovery's view, as use cases."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.application.lifecycle.show_worker import ShowWorkerQuery, ShowWorkerUseCase
from dca_factory.delivery.application.lifecycle.start_factory import StartFactoryCommand, StartFactoryUseCase
from dca_factory.delivery.application.lifecycle.start_page import StartPageCommand, StartPageUseCase
from dca_factory.delivery.application.status.show_discovery import ShowDiscoveryQuery, ShowDiscoveryUseCase


class Process:
    def __init__(self, page=None):
        self.page, self.calls = page, []

    def up(self, run_args, serve, port, by):
        self.calls.append(("up", tuple(run_args), serve))
        return 0

    def running_page(self):
        return self.page

    def start_page(self, port):
        self.calls.append(("start_page", port))
        return 0

    def worker(self):
        return {"owner": "runner:me"}

    def worker_line(self, info):
        return f"factory: up — {info['owner']}"


class Discovery:
    def topics(self):
        return dict(store="product/discovery", topics=[dict(
            topic="t", title="T", report="product/discovery/t/report.md",
            proposals=[dict(id="p-1", epic=None, metric="m"), dict(id="p-2", epic="e", metric="m")],
            description_changes=[dict(target="product", change="say more")])])


class Requests:
    def all(self):
        return []


class Stories:
    def names_story(self, word):
        return False


class LifecycleTest(unittest.TestCase):

    def test_the_factory_starts_with_the_runners_flags_and_a_running_page_is_never_started_twice(self):
        process = Process()
        self.assertEqual(0, StartFactoryUseCase(process).execute(StartFactoryCommand(("--tool", "claude"), True)))
        self.assertEqual(None, StartPageUseCase(process).execute(StartPageCommand(9000)).running)
        running = Process(page={"url": "http://127.0.0.1:9000/?t=x"})
        self.assertEqual("http://127.0.0.1:9000/?t=x", StartPageUseCase(running).execute(StartPageCommand()).running["url"])
        self.assertEqual([("up", ("--tool", "claude"), True), ("start_page", 9000)], process.calls)
        self.assertEqual([], running.calls)

    def test_the_worker_comes_with_its_line(self):
        self.assertEqual(({"owner": "runner:me"}, "factory: up — runner:me"),
                         ShowWorkerUseCase(Process()).execute(ShowWorkerQuery()))


class DiscoveryViewTest(unittest.TestCase):

    def test_a_proposal_not_yet_an_epic_offers_to_become_one_and_a_change_offers_to_be_applied(self):
        model = ShowDiscoveryUseCase(Discovery(), Requests(), Stories()).execute(ShowDiscoveryQuery("shop"))
        topic = model["topics"][0]
        self.assertEqual("shop", model["project"])
        self.assertEqual(["make epic"], [a["label"] for a in topic["proposals"][0]["actions"]])
        self.assertEqual([], topic["proposals"][1]["actions"])
        self.assertEqual(["apply"], [a["label"] for a in topic["description_changes"][0]["actions"]])


if __name__ == "__main__":
    unittest.main()
