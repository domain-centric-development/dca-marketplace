"""A criterion's test says the text its `Then` quotes as shown (GATE-TESTS-ASSERT-THEN): which quoted texts are shown
and which name an element, and what the check says over the tests a story maps."""

import unittest

import support  # noqa: F401 — puts the package on the path
from dca_factory.delivery.adapter.outgoing.files.criteria_files import criteria_of
from dca_factory.delivery.adapter.outgoing.files.stage_evidence_files import stage_story
from dca_factory.delivery.domain.model.stage_story import (
    Clause, CommandKey, Count, MappedTest, Place, ScenarioKey, Selector, TestSource)
from dca_factory.delivery.domain.model.story_state import Detail
from dca_factory.delivery.domain.model.verdict import FindingState
from dca_factory.delivery.domain.service.then_checks import ThenChecks, shown_literals


def shown(text):
    return [literal.value for literal in shown_literals(Clause(Count(1), Detail(text)))]


BODY = """# A story

## Acceptance criteria

### Rule: The count follows the record

#### count-follows-a-change (happy path)
- Given the record holds „Alpha“ and „Beta“, both open
- When the reader presses „Done“ at „Beta“
- Then „2 entries, 1 open“ is shown
- And the hint „Nothing left“ is not shown

#### count-stands-near-the-form
- Given the record holds „Alpha“
- When the reader opens the record
- Then the count stands above the list, near the form „Add“
"""


def story(body=BODY):
    return stage_story("S-1", "story.md", {"status": "approved", "context": "Widgets"}, body,
                       criteria_of("story.md", body))


def test(key, cls, place):
    return MappedTest(ScenarioKey(key), Selector(f"com.example.{cls}#checks"), Place(place) if place else None,
                      CommandKey("test.pages"), None)


class Sources:
    """The test files a case's project holds."""

    def __init__(self, files):
        self.files = files

    def test_source(self, place):
        text = self.files.get(place.value)
        return TestSource(text) if text is not None else None


PORT = "src/test/com/example/CountPortTest.java"
PAGE = "src/test/com/example/CountPageTest.java"
NEAR = "src/test/com/example/NearFormTest.java"


class WhatIsShown(unittest.TestCase):

    def test_a_quoted_text_the_step_says_is_shown_is_shown(self):
        self.assertEqual(shown("Then „2 entries, 1 open“ is shown"), ["2 entries, 1 open"])
        self.assertEqual(shown('Then the page "Our Things" opens'), ["Our Things"])
        self.assertEqual(shown("Then “Saved” appears and ‚ok‘ beside it"), ["Saved", "ok"])

    def test_a_text_a_control_noun_names_is_an_element(self):
        self.assertEqual(shown("Then the count stands near the form „Add“"), [])
        self.assertEqual(shown("And „Alpha“ still carries a button „Done“"), ["Alpha"])
        self.assertEqual(shown("And it offers an \"Event Log\" link"), [])
        self.assertEqual(shown("Then die „Speichern“-Schaltfläche ist deaktiviert"), [])
        self.assertEqual(shown("Then steht beim Feld „Titel“ die Meldung „Bitte einen Titel eingeben.“"),
                         ["Bitte einen Titel eingeben."])

    def test_a_text_that_is_pressed_or_clicked_is_an_element(self):
        self.assertEqual(shown("Then the reader presses „Done“ again and „1 open“ is shown"), ["1 open"])
        self.assertEqual(shown("And the reader klickt auf „Weiter“"), [])
        self.assertEqual(shown("And clicks on the \"Next\""), [])

    def test_a_label_the_step_says_is_shown_is_shown(self):
        self.assertEqual(shown('Then the price "9.99 EUR" is labelled "Retail Price"'), ["9.99 EUR", "Retail Price"])

    def test_a_code_span_holds_no_shown_text(self):
        self.assertEqual(shown('Then the card of `"Bounded Context" Pin` shows "12.99 EUR"'), ["12.99 EUR"])


class Asserted(unittest.TestCase):

    def findings(self, tests, files):
        return ThenChecks.asserted(story(), tuple(tests), Sources(files))

    def test_a_text_in_a_constant_of_the_test_class_passes(self):
        found = self.findings([test("count-follows-a-change", "CountPageTest", PAGE),
                               test("count-stands-near-the-form", "NearFormTest", NEAR)],
                              {PAGE: 'class CountPageTest { static final String COUNT = "2 entries, 1 open";\n'
                                     '  static final String HINT = "Nothing left"; void checks() {} }\n',
                               NEAR: "class NearFormTest { void checks() {} }\n"})
        self.assertEqual([f.state for f in found], [FindingState.PASS])
        self.assertIn("2 text(s)", found[0].said.value)

    def test_one_test_of_the_criterion_that_says_it_is_enough(self):
        found = self.findings([test("count-follows-a-change", "CountPortTest", PORT),
                               test("count-follows-a-change", "CountPageTest", PAGE)],
                              {PORT: "class CountPortTest { void checks() { assertThat(count).isEqualTo(2); } }\n",
                               PAGE: 'class CountPageTest { void checks() { see("2 entries, 1 open", "Nothing left"); } }\n'})
        self.assertEqual([f.state for f in found], [FindingState.PASS])

    def test_a_text_no_test_of_the_criterion_says_fails_naming_criterion_text_and_class(self):
        found = self.findings([test("count-follows-a-change", "CountPortTest", PORT)],
                              {PORT: 'class CountPortTest { void checks() { assertThat(count).isEqualTo(2); '
                                     'see("Nothing left"); } }\n'})
        self.assertEqual([f.state for f in found], [FindingState.FAIL])
        self.assertIn("count-follows-a-change: „2 entries, 1 open“ is in no test of it (CountPortTest)",
                      found[0].said.value)
        self.assertNotIn("Nothing left", found[0].said.value)

    def test_a_label_alone_asks_for_nothing(self):
        found = self.findings([test("count-stands-near-the-form", "NearFormTest", NEAR)],
                              {NEAR: "class NearFormTest { void checks() {} }\n"})
        self.assertEqual(found, ())

    def test_a_test_without_a_source_file_is_named_not_guessed(self):
        found = self.findings([test("count-follows-a-change", "CountPortTest", None)], {})
        self.assertEqual([f.state for f in found], [FindingState.FAIL])
        self.assertIn("count-follows-a-change (com.example.CountPortTest#checks)", found[0].said.value)
        self.assertIn("tests-exist", found[0].said.value)

    def test_a_straight_quote_in_the_text_may_stand_escaped(self):
        body = BODY.replace("- Then „2 entries, 1 open“ is shown", '- Then „Say "hi"“ is shown')
        found = ThenChecks.asserted(story(body), (test("count-follows-a-change", "CountPageTest", PAGE),),
                                    Sources({PAGE: 'class CountPageTest { String a = "Say \\"hi\\""; '
                                                   'String b = "Nothing left"; }\n'}))
        self.assertEqual([f.state for f in found], [FindingState.PASS])

    def test_a_task_or_a_story_without_scenarios_is_not_asked(self):
        line_form = "# A story\n\n## Acceptance criteria\n\n- shows-it (happy path): „Shown“ is shown\n"
        self.assertEqual(ThenChecks.asserted(story(line_form), (test("shows-it", "CountPortTest", PORT),),
                                             Sources({PORT: "class CountPortTest {}\n"})), ())


if __name__ == "__main__":
    unittest.main()
