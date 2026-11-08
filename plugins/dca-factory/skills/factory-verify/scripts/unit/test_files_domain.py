"""The domain's rules for files (WP-184): what a person may hand over, which pictures a story shows, and which project
file the page may show — pure, no folder touched."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.domain.model.handed_file import (ByteSize, FileBytes, FileName, FileRefused, HandedFile,
                                                           HandedFileId, HandedFiles, MAX_BYTES, kind_of)
from dca_factory.delivery.domain.model.moment import Moment
from dca_factory.delivery.domain.model.project_path import ProjectPath
from dca_factory.delivery.domain.model.shot import (REUSED_WITHIN, SHOWN, FoundShot, Instant, RunOrigin, Shot,
                                                    ShotTaker, TakenFile, kept, shot_name, shown, taken_by_the_run,
                                                    taken_since)
from dca_factory.delivery.domain.model.shown_file import FileNotShown, Refusal, ShownAs, ShownFile, ShownPath
from dca_factory.delivery.domain.model.stage_story import CommandKey
from dca_factory.delivery.domain.model.words import MAX_LENGTH, Words, WordsRefused

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
PLACES = (ProjectPath("product"), ProjectPath(".dca-factory"))


class AHandedFile(unittest.TestCase):
    def test_is_known_by_its_content_and_kept_under_a_reduced_name(self):
        f = HandedFile(FileName("../../Bild vom 3. März.PNG"), FileBytes(PNG))
        self.assertEqual(("image/png", "Bild-vom-3.-M-rz.png", 40), (f.kind.value, f.name.value, f.size.value))
        self.assertEqual("text/markdown", HandedFile(FileName("notes.md"), FileBytes("über den Ablauf\n".encode())).kind.value)

    def test_refused_empty_too_big_or_of_no_kind_of_ours(self):
        for name, data in (("a.png", b""), ("a.png", PNG + b"\0" * MAX_BYTES), ("x.svg", b"<svg><script/></svg>"),
                           ("page.txt", b"<html><script>1</script>"), ("tool.exe", b"MZ\x90"), ("t.txt", b"a\x1b[2J")):
            with self.subTest(name=name), self.assertRaises(FileRefused):
                HandedFile(FileName(name), FileBytes(data))

    def test_a_request_takes_five_at_most(self):
        five = tuple(HandedFile(FileName(f"{n}.png"), FileBytes(PNG)) for n in range(5))
        self.assertTrue(HandedFiles(five).any)
        with self.assertRaises(FileRefused):
            HandedFiles(five + five[:1])

    def test_a_fresh_id_is_drawn_from_eight_bytes_in_the_factorys_form(self):
        self.assertEqual("f00ff00ff00ff00ff", HandedFileId.fresh(bytes.fromhex("00ff00ff00ff00ff")).value)
        with self.assertRaises(FileRefused):
            HandedFileId.fresh(b"short")

    def test_an_id_is_the_factorys_own(self):
        HandedFileId("f" + "0" * 16)
        for wrong in ("../f0000000000000000", "f123", "x" * 17):
            with self.subTest(wrong=wrong), self.assertRaises(FileRefused):
                HandedFileId(wrong)

    def test_the_kind_by_content_the_name_only_between_texts(self):
        self.assertEqual("image/png", kind_of(PNG, FileName("x.txt")).value)
        self.assertIsNone(kind_of(b"PK\x03\x04", FileName("sheet.xlsx")))


class APersonsWords(unittest.TestCase):
    def test_carry_what_a_person_types(self):
        self.assertEqual("a wish\n\twith a tab\r\n", Words("a wish\n\twith a tab\r\n").value)

    def test_refused_too_long_or_with_a_control_character_or_a_direction_mark(self):
        for given in ("x" * (MAX_LENGTH + 1), "a\0b", "a\x1bb", "abc\u202edef", "abc\u2066def"):
            with self.subTest(given=given[:12]), self.assertRaises(WordsRefused):
                Words(given)


class AStorysPicture(unittest.TestCase):
    def test_its_name_says_what_took_it(self):
        self.assertEqual("e2e-checkout-review.png", shot_name(CommandKey("e2eTest"), ProjectPath("checkout/review.png")).value)
        self.assertEqual(["e2e", "journey"], [ShotTaker.of(CommandKey(k)).value for k in ("e2eTest", "test.journey")])

    def test_only_a_picture_the_run_took(self):
        since = Instant(1000.0)
        self.assertTrue(taken_by_the_run(FileName("a.png"), PNG, ByteSize(40), Instant(998.0), since))
        self.assertFalse(taken_by_the_run(FileName("a.png"), PNG, ByteSize(40), Instant(900.0), since))
        self.assertFalse(taken_by_the_run(FileName("t.zip"), b"PK", ByteSize(2), Instant(1001.0), since))
        self.assertFalse(taken_by_the_run(FileName("a.png"), PNG, ByteSize(MAX_BYTES + 1), Instant(1001.0), since))

    def test_a_reused_run_counts_from_the_window_before_the_step(self):
        self.assertEqual(Instant(5000.0), taken_since(Instant(5000.0), RunOrigin.RAN))
        self.assertEqual(Instant(5000.0 - REUSED_WITHIN), taken_since(Instant(5000.0), RunOrigin.REUSED))

    def test_the_newest_pictures_the_run_took_are_kept_whatever_their_names(self):
        def file(name, at):
            return TakenFile(ProjectPath(name), FileName(name), FileBytes(PNG if name.endswith(".png") else b"PK"), ByteSize(40),
                             Instant(at))
        files = [file(f"a-{n:02}.png", 1000.0 - n) for n in range(SHOWN + 5)] + [file("old.png", 10.0),
                                                                                  file("trace.zip", 2000.0)]
        names = [f.name.value for f in kept(files, Instant(900.0))]
        self.assertEqual([f"a-{n:02}.png" for n in range(SHOWN)], names)

    def test_newest_first_pictures_only_at_most_shown(self):
        def found(name, at):
            return FoundShot(Shot.of(ProjectPath(f"r/S/shots/{name}"), FileName(name), Moment("2026-11-04T12:00:00Z")),
                             Instant(at), FileBytes(PNG if name.endswith(".png") else b"text"))
        listed = [found("e2e-old.png", 1.0), found("e2e-new.png", 2.0), found("notes.txt", 3.0)]
        self.assertEqual(["e2e-new.png", "e2e-old.png"], [s.name.value for s in shown(listed)])
        self.assertEqual("e2e", shown(listed)[0].taker.value)
        self.assertEqual(SHOWN, len(shown([found(f"e2e-{n}.png", n) for n in range(SHOWN + 5)])))


class AFileThePageShows(unittest.TestCase):
    def test_only_beneath_its_places_and_never_by_a_path_of_the_wrong_form(self):
        ShownPath(ProjectPath("product/epics/e/s/decisions/01/a.png"), PLACES)
        for given, refusal in (("build.gradle", Refusal.NOTHING), ("product/../build.gradle", Refusal.FORM),
                               ("/etc/hosts", Refusal.FORM), ("C:/x/product/a.png", Refusal.FORM), ("", Refusal.FORM)):
            with self.subTest(given=given), self.assertRaises(FileNotShown) as refused:
                ShownPath(ProjectPath(given), PLACES)
            self.assertEqual(refusal, refused.exception.refusal)

    def test_a_mockup_is_a_page_beside_a_record_or_in_a_mockups_folder(self):
        for given in ("product/epics/e/s/decisions/01/a.html", "product/discovery/t/mockups/a.html"):
            shown_file = ShownFile.of(ShownPath(ProjectPath(given), PLACES), FileBytes(b"<b>cards</b>"))
            self.assertEqual((ShownAs.PAGE, "text/html"), (shown_file.shown_as, shown_file.kind.value))
        with self.assertRaises(FileNotShown) as refused:
            ShownFile.of(ShownPath(ProjectPath("product/page.html"), PLACES), FileBytes(b"<html><script>1</script>"))
        self.assertEqual(Refusal.KIND, refused.exception.refusal)

    def test_anything_else_only_as_a_picture_a_pdf_or_a_text(self):
        picture = ShownFile.of(ShownPath(ProjectPath("product/a.png"), PLACES), FileBytes(PNG))
        self.assertEqual((ShownAs.FILE, "image/png"), (picture.shown_as, picture.kind.value))


if __name__ == "__main__":
    unittest.main()
