---
id: GATE-TESTS-ASSERT-THEN
title: A criterion's test says the text its Then quotes
part: check
kinds:
- story
reports:
- tests-assert-then
pass: every text a `Then` or `And` quotes as shown stands in the source of a test mapped to its criterion
fail: a quoted text stands in no test of its criterion, or the criterion's tests have no source file to look in
---

# GATE-TESTS-ASSERT-THEN

**When:** the test gate runs for a story whose `Then`/`And`/`But` lines quote a text

**Why:** a test that asserts the number a use case returns, where the scenario says a sentence is shown, proves the
number and leaves the sentence unproven

**What is looked for.** Every text a scenario's `Then` and each `And` or `But` after it put in quotes — „…“, "…",
“…”, ‚…‘, ‘…’ or «…», outside a code span — is searched, as it is written, in the whole file of every test the tests
table maps to that scenario: the file, not only the method, because a text often stands in a constant. A straight
quote inside the text may stand escaped (`\"`). One test of the criterion that holds the text is enough.

**A name, not a text shown.** A quoted text names an element when
- a control noun stands right before it — *button, link, field, input field, form, tab, menu, menu item, checkbox,
  toggle, dropdown, control*; *Schaltfläche, Knopf, Button, Feld, Eingabefeld, Formular, Link, Reiter, Menü,
  Menüpunkt, Kontrollkästchen, Auswahlfeld* — "near the form „Create“", "still carries a button „Done“";
- or one stands right after it, a hyphen allowed — "the „Save“ button", "an "Event Log" link",
  "die „Speichern“-Schaltfläche";
- or it is the object of a press — *press, click, tap; drücken, klicken, tippen, betätigen*, in their forms, an
  `on`/`auf` and an article allowed between — "presses „Done“", "klickt auf „Weiter“".

Such a text is left out: a test finds the element by its selector and need not spell its label. Every other quoted
text is a text the scenario says is there, and its test says it.

**Not found.** A criterion with a quoted text whose mapped tests have no source file is named, not guessed at;
`GATE-TESTS-EXIST` says which file is missing.
