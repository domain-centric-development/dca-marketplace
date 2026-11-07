"""What a criterion's test must say: every text its `Then` and each `And` after it quote as shown stands in the source
of a test mapped to that criterion. A test that asserts a number the use case returns, where the scenario says a
sentence is shown, proves the number and leaves the sentence unproven."""

from __future__ import annotations

import re
import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.stage_story import Clause, MappedTest, Place, ShownLiteral, StageStory, TestSource
from ..model.verdict import CheckName, Findings, Said

TESTS_ASSERT_THEN = CheckName("tests-assert-then")

#: A quoted text, in each pair of quotes a story is written with: German „…“ (closed by “ or ”), English “…”, the
#: straight "…", the single ‚…‘ and ‘…’, and «…». A straight single quote is an apostrophe too often to be one.
QUOTED = re.compile(r'„([^“”"\n]+)[“”]|“([^”\n]+)”|"([^"\n]+)"|‚([^‘’\n]+)[‘’]|‘([^’\n]+)’|«([^»\n]+)»')
#: A code span holds a name, a path or a value written as code, never a text that is shown; its quotes are its own.
CODE_SPAN = re.compile(r"`[^`\n]*`")

#: The nouns that make a quoted text the name of an element a step points at, not a text it says is shown.
CONTROL_NOUNS = (r"buttons?|links?|fields?|input fields?|forms?|tabs?|menus?|menu items?|check ?box(?:es)?|"
                 r"toggles?|drop-?downs?|controls?|"
                 r"Schaltfläche(?:n)?|Knopf|Knöpfe|Buttons?|Feld(?:er)?|Eingabefeld(?:er)?|Formular(?:e)?|Links?|"
                 r"Reiter|Menü(?:s)?|Menüpunkt(?:e)?|Kontrollkästchen|Auswahlfeld(?:er)?")
#: The verbs whose object is an element: it is pressed, clicked or tapped, not read.
CONTROL_VERBS = (r"press(?:es|ed)?|click(?:s|ed)?|tap(?:s|ped)?|"
                 r"drückt|drücken|gedrückt|klickt|klicken|geklickt|tippt|tippen|getippt|betätigt|betätigen")
ARTICLES = r"(?:the|a|an|its|der|die|das|den|dem|des|ein|eine|einen|einem|einer|seine?[nmr]?|ihre?[nmr]?)"
#: A control noun right before the text — "the button „Save“", "the form „Create“", "das Feld „Titel“".
NOUN_BEFORE = re.compile(rf"(?:^|\W)(?:{CONTROL_NOUNS})\s*:?\s*$", re.IGNORECASE)
#: A control noun right after it — "the „Save“ button", "„Speichern“-Schaltfläche", "an "Event Log" link".
NOUN_AFTER = re.compile(rf"^\s*-?\s*(?:{CONTROL_NOUNS})\b", re.IGNORECASE)
#: The text as the object of a press — "presses „Save“", "clicks on the "Next"", "klickt auf „Weiter“".
VERB_BEFORE = re.compile(rf"(?:^|\W)(?:{CONTROL_VERBS})\s+(?:(?:on|auf)\s+)?(?:{ARTICLES}\s+)?$", re.IGNORECASE)


def shown_literals(clause: Clause) -> typing.Tuple[ShownLiteral, ...]:
    """The texts one expectation quotes as shown, in order: every quoted text outside a code span, but the one a
    control noun stands right before or after, or a press, click or tap takes as its object — that one names the
    element (a test finds it by its selector), it says nothing the page shows. "The count stands near the form
    „Create“" quotes nothing shown; "„2 open“ is shown" and "the hint „Nothing yet.“ is shown" do."""
    text = CODE_SPAN.sub(lambda span: " " * len(span.group(0)), clause.text.value)
    found: typing.List[ShownLiteral] = []
    for match in QUOTED.finditer(text):
        literal = next(group for group in match.groups() if group is not None).strip()
        before, after = text[:match.start()], text[match.end():]
        if not literal or NOUN_BEFORE.search(before) or NOUN_AFTER.match(after) or VERB_BEFORE.search(before):
            continue
        if literal not in (shown.value for shown in found):
            found.append(ShownLiteral(literal))
    return tuple(found)


class ThenChecks(DomainService):
    """The check over what a criterion's tests say."""

    @staticmethod
    def asserted(story: StageStory, tests: typing.Tuple[MappedTest, ...], evidence: StageEvidence) -> Findings:
        """Every text a scenario's `Then` and each `And`/`But` after it quote as shown stands in the whole source of a
        test the tests table maps to that scenario — the file, not only the method, since a text often sits in a
        constant. A scenario whose tests have no source file is named, never guessed at: `tests-exist` says why; one
        without a row is `tests-mapped`'s."""
        if story.kind is not StoryKind.STORY or not story.clauses or not tests:
            return ()
        missing, unfound, held = [], [], 0
        sources: typing.Dict[Place, typing.Optional[TestSource]] = {}
        for scenario in story.clauses:
            literals = [literal for clause in scenario.clauses for literal in shown_literals(clause)]
            if not literals:
                continue
            own = [test for test in tests if test.key == scenario.key]
            located = [test for test in own if test.place is not None]
            if not own:
                continue                      # a criterion without a row is `tests-mapped`'s to refuse
            if not located:
                unfound.append(f"{scenario.key.value} ({', '.join(t.selector.value for t in own)})")
                continue
            for test in located:
                assert test.place is not None
                if test.place not in sources:
                    sources[test.place] = evidence.test_source(test.place)
            # each test's class as a person names it: the selector's simple class name
            classes = ", ".join(dict.fromkeys(test.selector.value.partition("#")[0].rsplit(".", 1)[-1]
                                              for test in located))
            for literal in dict.fromkeys(literals):
                if any(source is not None and source.says(literal)
                       for source in (sources[t.place] for t in located if t.place is not None)):
                    held += 1
                else:
                    missing.append(f"{scenario.key.value}: „{literal.value}“ is in no test of it ({classes})")
        found = []
        if unfound:
            found.append(TESTS_ASSERT_THEN.fail(Said(
                "the `Then` of these criteria quotes a text, and no source file holds their test, so nothing shows "
                "the text is asserted: " + "; ".join(unfound) + " — `tests-exist` names what is missing")))
        if missing:
            found.append(TESTS_ASSERT_THEN.fail(Said(
                "a criterion's `Then` quotes a text as shown and its test never says it — assert the text where it "
                "is shown (the incoming adapter's translation, or end to end), beside what the use case returns: "
                + "; ".join(missing[:8]) + (" …" if len(missing) > 8 else ""))))
        if not found and held:
            found.append(TESTS_ASSERT_THEN.ok(Said(
                f"every text a `Then` quotes as shown stands in a test of its criterion ({held} text(s))")))
        return tuple(found)
