"""The trail under a wish field: every wish, newest first, and what became of a done one — until what it made is
released or the note hidden (WP-179)."""

import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.application.requests.list_requests import ListRequestsQuery, ListRequestsUseCase
from dca_factory.delivery.application.requests.take_back_request import TakeBackRequestCommand, \
    TakeBackRequestUseCase
from dca_factory.delivery.application.shared.requests import RequestRefused


class Transactions:
    def in_transaction(self, work):
        return work()


class Store:
    def __init__(self, queue, notes):
        self.queue, self.notes = queue, notes

    def all(self):
        return list(self.queue)

    def done(self):
        return list(self.notes)

    def find(self, request_id):
        raise RequestRefused(f"no request {request_id}")

    def hide_done(self, request_id):
        before = len(self.notes)
        self.notes = [n for n in self.notes if n["id"] != request_id]
        return len(self.notes) < before

    def shown(self, request):
        return request["id"]

    def where(self):
        return ".dca-factory/requests"


class Made:
    def __init__(self, items):
        self.items = items

    def at(self, paths):
        return [self.items[p] for p in paths if p in self.items]


def wish(rid, state, asked, **more):
    return dict(id=rid, kind="wish", state=state, asked=asked, words=f"words of {rid}", by="Jane", **more)


class WishTrailTest(unittest.TestCase):

    def trail(self, queue, notes, items):
        return ListRequestsUseCase(Store(queue, notes), Made(items)).execute(ListRequestsQuery())["wishes"]

    def test_every_wish_newest_first_each_in_its_state(self):
        trail = self.trail([wish("a", "running", "2026-11-02T10:00:00Z"), wish("b", "failed", "2026-11-02T11:00:00Z",
                                                                               error="the tool ran past its time limit")],
                           [wish("c", "done", "2026-11-02T12:00:00Z", wrote="e/s/story.md")],
                           {"e/s/story.md": dict(kind="task", id="s", title="The name is short", status="draft")})
        self.assertEqual(["c", "b", "a"], [w["id"] for w in trail])
        self.assertEqual("became a draft task: The name is short", trail[0]["text"])
        self.assertEqual("release", trail[0]["actions"][0]["request"]["kind"])
        self.assertEqual(["hide"], [o["name"] for o in trail[0]["operations"]])
        self.assertEqual(("bad", "the tool ran past its time limit"), (trail[1]["tone"], trail[1]["text"]))
        self.assertEqual(("wait", "writing"), (trail[2]["tone"], trail[2]["text"]))

    def test_a_done_wish_whose_drafts_are_released_leaves_the_trail(self):
        trail = self.trail([], [wish("c", "done", "2026-11-02T12:00:00Z", wrote="e/s/story.md")],
                           {"e/s/story.md": dict(kind="story", id="s", title="T", status="approved")})
        self.assertEqual([], trail)

    def test_a_hidden_note_is_gone_and_what_it_made_stays(self):
        store = Store([], [wish("c", "done", "2026-11-02T12:00:00Z")])
        TakeBackRequestUseCase(store, store, Transactions()).execute(TakeBackRequestCommand("c"))
        self.assertEqual([], store.notes)
        with self.assertRaises(RequestRefused):
            TakeBackRequestUseCase(store, store, Transactions()).execute(TakeBackRequestCommand("c"))


if __name__ == "__main__":
    unittest.main()
