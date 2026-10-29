"""The factory's own architecture checks (WP-152) can go red: each rule finds the import it forbids in a planted
package, the value-object check a bare primitive in a domain field or signature, the cycle check a cycle — and the
factory's package itself holds all three."""

import os
import sys
import tempfile
import unittest

import support  # noqa: F401 — puts the package on the path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import architecture  # noqa: E402

PACKAGE = os.path.join(support.SCRIPTS, "dca_factory")


def plant(root, files):
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)


def rules(findings):
    return sorted({f.split()[1] for f in findings})


class LayersTest(unittest.TestCase):

    def test_the_factory_holds_its_layers(self):
        self.assertEqual([], architecture.layer_findings(PACKAGE))

    def test_the_factory_has_no_module_outside_its_layers(self):
        self.assertEqual([], architecture.place_findings(PACKAGE))

    def test_a_module_at_the_top_is_found_and_the_stamp_is_not(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {"__init__.py": "", "building_blocks.py": "", "contract.py": "", "legacy.py": "",
                         "delivery/__init__.py": "", "delivery/domain/__init__.py": "", "delivery/domain/m.py": ""})
            self.assertEqual(["legacy.py:1 outside every layer — a module belongs to a context, the shared kernel, "
                              "the web host or the root"], architecture.place_findings(root))

    def test_each_rule_finds_what_it_forbids(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "__init__.py": "",
                "building_blocks.py": "",
                "legacy.py": "",
                "delivery/__init__.py": "",
                "delivery/domain/model/story.py":
                    "import os\nfrom ...application.shared import port\nfrom ...adapter.outgoing import files\n"
                    "from .... import legacy\nfrom ....spec.domain.model import criterion\n"
                    "from .... import building_blocks\nimport dataclasses\n",
                "delivery/application/shared/port.py":
                    "import subprocess\nfrom ...adapter.incoming import cli\nfrom ....spec.application import merge\n"
                    "from ...domain.model import story\n",
                "delivery/adapter/incoming/cli.py": "from ..outgoing import files\nfrom ...application.shared import port\n",
                "delivery/adapter/outgoing/files.py": "from ...application.shared import port\nimport os\n",
                "spec/domain/model/criterion.py": "",
                "spec/application/merge.py": "",
                "sharedkernel/domain/model/moment.py": "from ....delivery.domain.model import story\n",
                "spec/adapter/outgoing/backlog.py": "from ....delivery.adapter.outgoing import files\n"
                                                    "from ....delivery import api\n",
                "delivery/api/__init__.py": "",
            })
            found = architecture.layer_findings(root)
        self.assertEqual(["DCA-HEX-001", "DCA-HEX-002", "DCA-HEX-006", "DCA-LAY-003", "DCA-ONI-001", "DCA-ONI-002",
                          "DCA-STR-002", "DCA-STR-003", "DCA-STR-004", "DCA-STR-006"], rules(found), found)
        self.assertEqual(1, sum("DCA-STR-006" in f for f in found), found)       # the api is the way in
        self.assertEqual(2, sum("DCA-HEX-001" in f for f in found), found)        # the adapter and the legacy module
        self.assertFalse(any("building_blocks" in f or "dataclasses" in f for f in found), found)


class ValuesTest(unittest.TestCase):

    def test_the_factory_wraps_its_primitives(self):
        self.assertEqual([], architecture.value_findings(PACKAGE))

    def test_a_bare_primitive_in_a_field_or_a_signature_is_found(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "delivery/domain/model/story.py":
                    "import dataclasses, datetime, typing, uuid\n"
                    "class StoryId(Id):\n    value: str\n"
                    "class Pair(Value):\n    value: str\n    other: int\n"
                    "@dataclasses.dataclass(frozen=True)\nclass Loose:\n    value: str\n"
                    "class Story:\n    title: str\n    LIMIT: typing.ClassVar[int] = 3\n"
                    "    def __str__(self) -> str: ...\n"
                    "    def rename(self, title: typing.Optional[str]) -> None: ...\n"
                    "    def is_draft(self) -> bool: ...\n"
                    "def due(at: datetime.datetime) -> StoryId: ...\n"
                    "def owner_of(story: StoryId) -> uuid.UUID: ...\n",
                "delivery/application/release.py": "def release(story: str) -> bool: ...\n",
            })
            found = architecture.value_findings(root)
        said = " ".join(found)
        self.assertEqual(7, len(found), found)
        for part in ("Pair.value is str", "Pair.other is int", "Loose.value is str", "Story.title is str",
                     "rename(title) takes str", "due(at) takes datetime", "owner_of returns UUID"):
            self.assertIn(part, said)
        self.assertNotIn("is_draft", said)      # a predicate returns bool
        self.assertNotIn("StoryId", said)
        self.assertNotIn("release", said)


class MarkersTest(unittest.TestCase):

    def test_the_factory_leaves_the_dataclass_to_the_base(self):
        self.assertEqual([], architecture.marker_findings(PACKAGE))

    def test_a_decorator_on_a_value_an_id_or_an_event_is_found(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "delivery/domain/model/story.py":
                    "import dataclasses, typing\nfrom ....building_blocks import DomainEvent, Entity, Id, Value\n"
                    "import building_blocks as bb\n"
                    "@dataclasses.dataclass(frozen=True)\nclass StoryId(Id):\n    value: str\n"
                    "@dataclasses.dataclass\nclass Title(bb.Value):\n    value: str\n"
                    "@dataclasses.dataclass(frozen=True)\nclass Released(DomainEvent):\n    story: StoryId\n"
                    "class Kept(Value):\n    value: str\n"
                    "@dataclasses.dataclass(frozen=True)\nclass Command:\n    story: StoryId\n"
                    "@dataclasses.dataclass\nclass Story(Entity[Id]):\n    title: Title\n",
            })
            found = architecture.marker_findings(root)
        self.assertEqual(["StoryId is a Id", "Title is a Value", "Released is a DomainEvent"],
                         [f.split(" ", 1)[1].split(" —")[0] for f in found], found)


class PortsTest(unittest.TestCase):

    def test_every_port_of_the_factory_is_marked_and_implemented_outside_the_core(self):
        self.assertEqual([], architecture.port_findings(PACKAGE))

    def test_an_unmarked_a_misplaced_and_an_unimplemented_port_are_found(self):
        blocks = ("import typing\nclass OutputPort(typing.Protocol): ...\n"
                  "class Store(OutputPort, typing.Protocol): ...\n"
                  "class Repository(OutputPort, typing.Protocol):\n"
                  "    def find_by_id(self, aggregate_id): ...\n    def save(self, aggregate): ...\n"
                  "class DomainGateway(typing.Protocol): ...\n")
        with tempfile.TemporaryDirectory() as root:
            plant(root, {
                "building_blocks.py": blocks,
                "delivery/application/shared/ports.py":
                    "import typing\nfrom ....building_blocks import OutputPort, Store\n"
                    "class Clock(typing.Protocol):\n    def now(self): ...\n"
                    "class Journal(Store, typing.Protocol):\n    def append(self, line): ...\n"
                    "class Mailer(OutputPort, typing.Protocol):\n    def send(self, to, text): ...\n"
                    "class Archive(OutputPort, typing.Protocol):\n    def keep(self, item): ...\n",
                "delivery/application/run/run_story.py":
                    "class MemoryJournal:\n    def append(self, line): ...\n",
                "delivery/adapter/incoming/cli/mail.py":
                    "class CliMailer:\n    def send(self, to, text): ...\n",
                "delivery/adapter/outgoing/files/journal.py":
                    "class JournalFiles:\n    def append(self, line): ...\n"
                    "class SystemClock:\n    def now(self): ...\n",
                "delivery/domain/gateway/lines.py":
                    "import typing\nfrom ....building_blocks import DomainGateway, OutputPort\n"
                    "class MainLine(DomainGateway, typing.Protocol):\n    def head(self): ...\n"
                    "class Ledger(OutputPort, typing.Protocol):\n    def book(self, entry): ...\n",
                "infrastructure/root.py":
                    "class RootLedger:\n    def __init__(self, book: BookInputPort): ...\n"
                    "    def book(self, entry): ...\n"
                    "class FileArchive:\n    def keep(self, item): ...\n",
            })
            found = architecture.port_findings(root)
        said = "\n".join(found)
        self.assertIn("DCA-HEX-009 Clock is a protocol of the application but no port", said)
        self.assertIn("DCA-HEX-010 the output port Ledger is declared in the domain", said)
        self.assertIn("DCA-HEX-019 FileArchive implements the output port Archive outside the outgoing adapters", said)
        self.assertIn("DCA-TAC-020 MemoryJournal implements the store Journal outside the outgoing adapters", said)
        self.assertIn("DCA-HEX-019 CliMailer implements the output port Mailer outside the outgoing adapters", said)
        self.assertNotIn("MainLine", said)
        self.assertNotIn("JournalFiles", said)
        self.assertNotIn("RootLedger", said)
        self.assertEqual(5, len(found), found)


class CyclesTest(unittest.TestCase):

    def test_the_factory_has_no_cycle(self):
        self.assertEqual([], architecture.cycle_findings(PACKAGE))

    def test_a_cycle_is_found_once(self):
        with tempfile.TemporaryDirectory() as root:
            plant(root, {"a.py": "from . import b\n", "b.py": "from .c import x\n", "c.py": "from .a import y\n",
                         "d.py": "def f():\n    from . import a\n"})
            found = architecture.cycle_findings(root)
        self.assertEqual(["a → b → c → a"], found)


if __name__ == "__main__":
    unittest.main()
