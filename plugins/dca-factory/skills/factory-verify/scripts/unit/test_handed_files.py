"""A request carries the files beside its words (WP-184): one command into `WriteRequest`, the domain deciding what it
takes, the store keeping it — all or nothing —, and the agent told where to read it."""

import os
import time
import types
import unittest

import support  # noqa: F401 — puts the package on the path
from support import project
from dca_factory.delivery.adapter.outgoing.files.handed_files import HandedFileFolder, files_dir
from dca_factory.delivery.adapter.outgoing.process.runner_ports import RunnerRequestSkill
from dca_factory.delivery.application.requests.write_request import WriteRequestCommand
from dca_factory.delivery.application.shared.request_skill import HandedFileRead
from dca_factory.delivery.application.shared.requests import RequestRefused
from dca_factory.delivery.domain.model.handed_file import FileName, HandedFile, HandedFileId, KEEP_DAYS
from dca_factory.infrastructure import delivery as wiring

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
PDF = b"%PDF-1.7\n%..."


class Here:
    """The project as the current folder, as the server and the runner work in it."""

    def __init__(self, root):
        self.root, self.before = root, os.getcwd()

    def __enter__(self):
        os.chdir(self.root)
        return self

    def __exit__(self, *_):
        os.chdir(self.before)


class TheStoreKeepsWhatTheDomainTook(unittest.TestCase):
    def test_kept_found_and_read_by_its_id_alone(self):
        with project() as p, Here(p.root):
            store = HandedFileFolder()
            ref = store.keep(HandedFile(FileName("../screen shot.png"), PNG))
            self.assertEqual("screen-shot.png", ref.name.value)
            self.assertEqual(ref, store.find(ref.id))
            self.assertTrue(store.readable(ref.id).value.startswith(".dca-factory/requests/files/"))
            self.assertIsNone(store.find(HandedFileId("f" + "0" * 16)))

    def test_a_file_nothing_names_goes_after_a_while_and_a_named_one_stays(self):
        with project() as p, Here(p.root):
            store = HandedFileFolder()
            named, loose = store.keep(HandedFile(FileName("a.pdf"), PDF)), store.keep(HandedFile(FileName("b.pdf"), PDF))
            old = time.time() - (KEEP_DAYS + 1) * 86400
            for ref in (named, loose):
                os.utime(os.path.join(files_dir(), ref.id.value), (old, old))
            store.prune([named.id])
            self.assertIsNotNone(store.find(named.id))
            self.assertIsNone(store.find(loose.id))


class AWishCarriesItsFiles(unittest.TestCase):
    def test_the_files_are_kept_and_the_request_names_them(self):
        with project() as p, Here(p.root):
            written = wiring.write_request(p.root).execute(
                WriteRequestCommand("wish", {}, "the desk sees the queue", "Ann", (("page today.png", PNG), ("notes.md", b"# notes\n"))))
            text = open(written.path, encoding="utf-8").read()
            ids = [line.split(":", 1)[1].split() for line in text.splitlines() if line.startswith("files:")][0]
            self.assertEqual(2, len(ids))
            self.assertEqual("page-today.png", HandedFileFolder().find(HandedFileId(ids[0])).name.value)

    def test_refused_by_the_domain_and_then_nothing_is_kept(self):
        with project() as p, Here(p.root):
            for files in ((("x.svg", b"<svg><script/></svg>"),), tuple((f"{n}.png", PNG) for n in range(6))):
                with self.subTest(n=len(files)), self.assertRaises(RequestRefused):
                    wiring.write_request(p.root).execute(WriteRequestCommand("wish", {}, "a wish", "Ann", files))
            self.assertFalse(os.path.isdir(files_dir()) and os.listdir(files_dir()))

    def test_a_kind_without_words_takes_no_file(self):
        with project() as p, Here(p.root):
            p.story("US-1", status="draft")
            with self.assertRaises(RequestRefused):
                wiring.write_request(p.root).execute(WriteRequestCommand("release", {"story": "US-1"}, "", "Ann", (("a.png", PNG),)))


class TheCliHandsFilesOverToo(unittest.TestCase):
    def test_a_request_from_the_terminal_carries_its_files(self):
        import subprocess
        import sys
        cli = os.path.join(os.path.dirname(support.__file__), "..", "..", "..", "factory-run", "scripts", "factory-cli.py")
        with project() as p:
            picture = os.path.join(p.root, "shot.png")
            with open(picture, "wb") as out:
                out.write(PNG)
            done = subprocess.run([sys.executable, os.path.abspath(cli), "--request", "wish", "the desk sees the queue",
                                   "--file", picture, "--by", "Ann"], cwd=p.root, capture_output=True, text=True)
            self.assertEqual(0, done.returncode, done.stderr + done.stdout)
            with Here(p.root):
                self.assertEqual(1, len(os.listdir(files_dir())))
            refused = subprocess.run([sys.executable, os.path.abspath(cli), "--request", "wish", "w", "--file",
                                      os.path.join(p.root, "missing.png")], cwd=p.root, capture_output=True, text=True)
            self.assertEqual(2, refused.returncode)


class TheAgentIsToldWhatWasHandedOver(unittest.TestCase):
    def test_the_prompt_lists_each_file_by_its_path_and_says_it_is_committed_only_as_part_of_the_story(self):
        with project() as p, Here(p.root):
            ref = HandedFileFolder().keep(HandedFile(FileName("the page today.png"), PNG))
            run = types.SimpleNamespace(skill_dirs=lambda tool: [], scripts=os.path.join(p.root, "scripts"),
                                        pwd=p.root, home=p.root, where_things_are=lambda *a, **k: "")
            store = HandedFileFolder()
            handed = [HandedFileRead(ref, store.readable(ref.id))]
            prompt = RunnerRequestSkill(run).request_prompt(
                {"id": "R1", "kind": "wish", "words": "the desk sees the queue", "files": ref.id.value}, "claude", handed)
            self.assertIn(f"- .dca-factory/requests/files/{ref.id.value}/the-page-today.png (image/png", prompt)
            self.assertIn("never committed", prompt)
            self.assertIn("/files/<its name>", prompt)
            self.assertLess(prompt.index("<<<end of the person's words>>>"), prompt.index("the-page-today.png"))


if __name__ == "__main__":
    unittest.main()
