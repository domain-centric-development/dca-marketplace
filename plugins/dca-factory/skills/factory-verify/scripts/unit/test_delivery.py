"""The delivered state in the story (WP-96): one end state, the claim of a hand, `--prove`, the answer as an
`answered:` line, and the migration that brings an older project's stories to it."""

import contextlib
import io
import os
import unittest

from support import contract, project, state, write
from dca_factory import cli, runner
from dca_factory.delivery.adapter.outgoing.files import decision_record_files as records
from dca_factory.sharedkernel.adapter.outgoing.profile import profile_files as profiles

DELIVERED = """---
id: {id}
status: delivered
delivered: 2026-10-01T10:00:00Z
{by}---
# {id}

## Acceptance criteria
- shows-the-thing (happy path): the thing shows
"""


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def quiet(function, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = function(*args)
    return code, out.getvalue()


class HandDelivery(unittest.TestCase):

    def test_a_hand_delivery_writes_three_lines_and_reads_claimed(self):
        with project() as p:
            path = p.story("S-1")
            code, said = quiet(cli.deliver_by_hand, p.root, p.runs, p.epics, "S-1", "Ana Lee")
            self.assertEqual(code, 0, said)
            front, _ = contract.read_front_matter(path)
            self.assertEqual((front["status"], front["delivered_by"]), ("delivered", "hand:Ana Lee"))
            self.assertTrue(front["delivered"])
            self.assertEqual(p.state_of("S-1"), ("delivered", None, "claimed by hand:Ana Lee"))

    def test_a_delivered_story_is_not_delivered_by_hand_again_and_a_hand_names_itself(self):
        with project() as p:
            p.story("S-1", text=DELIVERED.format(id="S-1", by="delivered_by: gate\n"))
            self.assertEqual(quiet(cli.deliver_by_hand, p.root, p.runs, p.epics, "S-1", "ana")[0], 1)
            p.story("S-2")
            self.assertEqual(quiet(cli.deliver_by_hand, p.root, p.runs, p.epics, "S-2", " ")[0], 1)

    def test_a_gate_delivery_reads_delivered_without_a_claim(self):
        with project() as p:
            p.story("S-1", text=DELIVERED.format(id="S-1", by="delivered_by: gate\n"))
            self.assertEqual(p.state_of("S-1"), ("delivered", None, ""))


class Prove(unittest.TestCase):

    def test_prove_takes_a_claim_back_to_adopted_and_keeps_it_in_the_evidence(self):
        with project() as p:
            path = p.story("S-1", text=DELIVERED.format(id="S-1", by="delivered_by: hand:ana\n"))
            code, said = quiet(cli.prove, p.root, p.runs, p.epics, "S-1")
            self.assertEqual(code, 0, said)
            front, _ = contract.read_front_matter(path)
            self.assertEqual(front["status"], "adopted")
            self.assertNotIn("delivered", front)
            self.assertNotIn("delivered_by", front)
            claim = read(os.path.join(profiles.evidence_dir(p.runs, "S-1"), cli.CLAIM_FILE))
            self.assertIn("delivered_by=hand:ana", claim)
            self.assertEqual(contract.story_kind(front), "adopt")

    def test_prove_refuses_an_open_story_and_a_gate_delivery_with_its_pass_on_record(self):
        with project() as p:
            p.story("S-1")
            self.assertEqual(quiet(cli.prove, p.root, p.runs, p.epics, "S-1")[0], 1)
            p.story("S-2", text=DELIVERED.format(id="S-2", by="delivered_by: gate\n"))
            p.evidence("S-2", "gate-document.101010.txt", "gate:pass delivered — x\ngate:pass story S-2 stage document\n")
            self.assertEqual(quiet(cli.prove, p.root, p.runs, p.epics, "S-2")[0], 1)


class Evidence(unittest.TestCase):

    def test_the_newest_delivering_report_decides_and_a_waiting_one_is_no_pass(self):
        with project() as p:
            p.story("S-1")
            self.assertEqual(state.gate_passed_on_record(p.root, p.runs, "S-1"), "")
            first = p.evidence("S-1", "gate-adopt.100000.txt", "gate:pass story S-1 stage adopt\n")
            os.utime(first, (1, 1))
            self.assertTrue(state.gate_passed_on_record(p.root, p.runs, "S-1"))
            p.evidence("S-1", "gate-document.110000.txt", "gate:wait acceptance — x\ngate:wait story S-1 stage document\n")
            self.assertEqual(state.gate_passed_on_record(p.root, p.runs, "S-1"), "")


class Migration(unittest.TestCase):

    def test_adopted_with_a_date_is_delivered_and_the_claim_follows_the_evidence(self):
        with project() as p:
            adopted = p.story("A-1", text="---\nid: A-1\nstatus: adopted\ndelivered: 2026-10-01T10:00:00Z\n---\n# A\n")
            proven = p.story("G-1", text=DELIVERED.format(id="G-1", by=""))
            p.evidence("G-1", "gate-document.100000.txt", "gate:pass story G-1 stage document\n")
            kept = p.story("H-1", text=DELIVERED.format(id="H-1", by="delivered_by: hand:ana\n"))
            said = []
            runner.migrate_delivery(p.root, p.epics, p.runs, said.append)
            self.assertEqual(contract.read_front_matter(adopted)[0]["status"], "delivered")
            self.assertEqual(contract.read_front_matter(adopted)[0]["delivered_by"], "hand:unknown")
            self.assertEqual(contract.read_front_matter(proven)[0]["delivered_by"], "gate")
            self.assertEqual(contract.read_front_matter(kept)[0]["delivered_by"], "hand:ana")
            again = []
            runner.migrate_delivery(p.root, p.epics, p.runs, again.append)
            self.assertEqual(again, [])

    def test_a_planned_digest_of_the_old_function_is_taken_anew(self):
        with project() as p:
            path = p.story("S-1", text="---\nid: S-1\nstatus: approved\ntitle: a --- b\n---\n# S\n")
            p.evidence("S-1", ".story-digest", contract.legacy_story_digest(path) + "\n")
            runner.migrate_delivery(p.root, p.epics, p.runs, lambda _: None)
            mark = read(os.path.join(profiles.evidence_dir(p.runs, "S-1"), ".story-digest"))
            self.assertEqual(mark.strip(), contract.story_digest(path))


RECORD = """---
id: S-1-01
story: S-1
stage: plan
---

# Which way?

## Options
- a: **The first way**, with its cost.
- b: The second way.
"""


class Answered(unittest.TestCase):

    def test_an_option_label_reads_as_the_options_text_and_a_free_answer_as_itself(self):
        self.assertEqual(records.answer_sentence(RECORD, {"answer": "a"}), "The first way, with its cost.")
        self.assertEqual(records.answer_sentence(RECORD, {"answer": "Option B"}), "The second way.")
        self.assertEqual(records.answer_sentence(RECORD, {"answer": "Neither:\n  keep it  as is"}),
                         "Neither: keep it as is")

    def test_every_option_form_a_stage_writes_reads_as_its_label_and_text(self):
        record = ("# Q\n\n## Options\n"
                  "- **a — the check also knows the stories in flight.** It also accepts\n  titles in flight.\n"
                  "- **b – this story writes its scenarios.** Nothing else.\n"
                  "- c - neither\n- **d.** fourth\n- **e**: fifth\n- f) sixth\n(g) seventh\n- h. eighth\n"
                  "- a correction: not an option\n\n## Recommendation\n**Option b.** Because.\n")
        options = records.decision_options(record)
        self.assertEqual([o["key"] for o in options], list("abcdefgh"))
        self.assertEqual(options[0]["line"], "the check also knows the stories in flight. It also accepts")
        self.assertEqual(options[0]["text"], "the check also knows the stories in flight. It also accepts titles in flight.")
        self.assertEqual(options[2]["line"], "neither")
        self.assertEqual(options[7]["text"], "eighth - a correction: not an option")
        self.assertEqual(records.recommended_option(record), "b")
        self.assertEqual(records.recommended_option("## Options\n- a: x\n\n## Recommendation\nnone of them\n"), None)
        self.assertEqual(records.answer_sentence(record, {"answer": "b"}), "this story writes its scenarios. Nothing else.")

    def test_the_line_goes_under_the_assumptions_once_and_the_planned_digest_follows(self):
        with project() as p:
            path = p.story("S-1", text="---\nid: S-1\nstatus: approved\n---\n# S\n\n## Assumptions\n\n"
                                       "- open: which way?\n\n## Out of scope\n- nothing\n")
            p.evidence("S-1", ".story-digest", contract.story_digest(path) + "\n")
            self.assertTrue(state.write_answered(path, p.runs, "S-1-01", "The first way."))
            self.assertFalse(state.write_answered(path, p.runs, "S-1-01", "The first way."))
            text = read(path)
            self.assertIn("- open: which way?\n- answered: The first way. (S-1-01)\n\n## Out of scope", text)
            mark = read(os.path.join(profiles.evidence_dir(p.runs, "S-1"), ".story-digest"))
            self.assertEqual(mark.strip(), contract.story_digest(path))

    def test_a_story_without_assumptions_gains_the_section(self):
        with project() as p:
            path = p.story("S-1")
            state.write_answered(path, p.runs, "S-1-01", "Yes.")
            self.assertTrue(read(path).endswith("## Assumptions\n\n- answered: Yes. (S-1-01)\n"))


class StoryFields(unittest.TestCase):

    def test_the_fields_are_written_by_lines_and_keep_the_line_endings(self):
        with project() as p:
            path = p.story("S-1")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write("---\r\nid: S-1\r\ntitle: a --- b\r\nstatus: approved\r\n---\r\n# S\r\n")
            state.write_story_fields(path, status="delivered", delivered="2026-10-11T00:00:00Z", delivered_by="gate")
            with open(path, encoding="utf-8", newline="") as handle:
                text = handle.read()
            self.assertEqual(text, "---\r\nid: S-1\r\ntitle: a --- b\r\nstatus: delivered\r\n"
                                   "delivered: 2026-10-11T00:00:00Z\r\ndelivered_by: gate\r\n---\r\n# S\r\n")


if __name__ == "__main__":
    unittest.main()
