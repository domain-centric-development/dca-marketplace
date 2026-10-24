"""A person's requests (WP-91): what a view's action becomes as a request, what a request may name, the order the
factory works them in, and the project's own decision records beside the stories'."""

import os
import time
import unittest

from support import contract, project, write

from dca_factory import requests


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
            "/dca-describe tech: PostgreSQL 17": ("describe", {}, "tech: PostgreSQL 17", ""),
            "/factory-discover": ("discover", {}, "", "words"),
        }
        with project() as p:
            p.story("US-1")
            for skill, (kind, fields, words, still) in cases.items():
                with self.subTest(skill=skill):
                    self.assertEqual(requests.request_of(skill),
                                     dict(kind=kind, fields=fields, words=words, open=still))

    def test_what_no_request_does_has_none(self):
        for skill in ("/factory-setup", "/factory-update", "/factory-verify US-1", "", None):
            self.assertIsNone(requests.request_of(skill))


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
                    with self.assertRaises(requests.RequestError):
                        requests.validate(p.root, kind, fields, words)

    def test_a_release_naming_an_epic_releases_the_epic(self):
        with project() as p:
            p.story("US-1", status="draft")
            fields, _words = requests.validate(p.root, "release", {"story": "sample"}, "")
            self.assertEqual(fields, {"epic": "sample"})

    def test_an_answer_takes_an_option_named_in_words_and_refuses_one_the_record_lacks(self):
        with project() as p:
            p.story("US-1")
            write(os.path.join(p.epics, "sample", "US-1", "decisions", "01.md"), record("US-1", "US-1-01"))
            fields, words = requests.validate(p.root, "answer", {"record": "US-1-01"}, "B")
            self.assertEqual((fields["option"], fields["story"], words), ("b", "US-1", ""))
            with self.assertRaises(requests.RequestError):
                requests.validate(p.root, "answer", {"record": "US-1-01"}, "c")
            fields, words = requests.validate(p.root, "answer", {"record": "US-1-01"}, "neither, a third way")
            self.assertEqual(words, "neither, a third way")

    def test_requests_are_worked_in_the_order_they_were_written_whatever_their_kind(self):
        with project() as p:
            p.story("US-1", status="draft")
            first, _ = requests.write_request(p.root, "wish", {}, "zz first", "a")
            second, _ = requests.write_request(p.root, "release", {"story": "US-1"}, "", "a")
            third, _ = requests.write_request(p.root, "stop", {}, "", "a")
            self.assertEqual([r["id"] for r in requests.list_requests()], [first, second, third])

    def test_the_same_request_twice_is_one(self):
        with project() as p:
            p.story("US-1", status="draft")
            first, _ = requests.write_request(p.root, "release", {"story": "US-1"}, "", "a")
            with self.assertRaises(requests.Duplicate) as caught:
                requests.write_request(p.root, "release", {"story": "US-1"}, "", "b")
            self.assertEqual(caught.exception.existing, first)

    def test_a_state_change_keeps_the_words_and_a_broken_file_reads_as_failed(self):
        with project() as p:
            rid, path = requests.write_request(p.root, "wish", {}, "line one\nline two", "a")
            request = requests.find_request(rid)
            requests.update_request(request, state="running", worker="runner:h:1")
            again = requests.find_request(rid)
            self.assertEqual((again["state"], again["worker"], again["words"]),
                             ("running", "runner:h:1", "line one\nline two"))
            write(path, "no front matter")
            self.assertEqual(requests.find_request(rid)["state"], "failed")

    def test_a_running_request_is_not_dropped_and_only_a_failed_one_retried(self):
        with project() as p:
            rid, _ = requests.write_request(p.root, "wish", {}, "x", "a")
            with self.assertRaises(requests.RequestError):
                requests.retry_request(rid)
            requests.update_request(requests.find_request(rid), state="running")
            with self.assertRaises(requests.RequestError):
                requests.drop_request(rid)


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
            self.assertEqual([rid for _p, rid, _s in requests.request_records(p.root, "R-1")],
                             ["20261024T100000Z-wish"])

    def test_a_project_record_is_where_a_request_without_a_story_asks(self):
        with project():
            path = requests.project_record_path("R-1", "A new Epic?")
            self.assertTrue(path.replace(os.sep, "/").startswith("product/decisions/"), path)
            self.assertTrue(path.endswith("-a-new-epic.md"), path)


class Outputs(unittest.TestCase):

    def setUp(self):
        contract.set_places({})

    def test_an_output_is_pruned_once_its_request_is_gone_and_old(self):
        with project():
            rid, _ = requests.write_request(os.getcwd(), "wish", {}, "x", "a")
            live, gone = requests.out_path(rid), requests.out_path("20200101T000000000Z-wish")
            for path in (live, gone):
                write(path, "out")
                os.utime(path, (time.time() - 30 * 86400,) * 2)
            requests.prune_outputs(days=7)
            self.assertEqual((os.path.isfile(live), os.path.isfile(gone)), (True, False))


if __name__ == "__main__":
    unittest.main()
