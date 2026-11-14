---
id: STAGE-TEST-2A
part: told
why: an adapter test stubbed a refusal the use case never raises, proving a page for a case that cannot happen
stages:
- test
section: Do
order: 3
---

# STAGE-TEST-2A

2a. **An integration test** has the shape the plan wrote after its level, in the source set a
   `test.<name>:` key declares. `integration (port)`: the use case through its input port in the wired
   application, with real outgoing adapters and persistence as the project runs it in tests — the
   scenario's outcome asserted on what the use case returns, stores or publishes. `integration (adapter:
   <Adapter>)`: that incoming adapter's translation — the request it turns into a command, the page,
   status or payload it makes of the result and of each refusal — against a stubbed input port that
   answers with the outcome; stubbing the input port here is right, the use case behind it has its own
   test. **A refusal the stub answers with is the one the port test proves**, in the style the plan's
   `## Context` names for the context. Where the context **returns** its refusals, the stub returns the
   case of the input port's result — the case the port test of the same criterion asserts the real use
   case returns, never a throw in its place — and the result's type holds the seam: a case renamed or
   removed stops both tests compiling, so no pair is needed to hold it. Where the context **throws**
   them, the stub throws the very failure type — the same class, never a parent or a generic one — that
   the port test of the same criterion asserts the real use case throws, and both tests stand in that
   criterion's rows of the table. Together they hold the seam the stub cuts: rename the failure or throw
   another, and the port test turns red. A thrown failure no port test asserts is a stub of nothing —
   write the port test beside it. **A clause about what is stored** — the list stays unchanged, the task remains open, it is done
   afterwards — is never asserted here: the stub answers what you told it, so the assertion holds whatever
   the code does. Assert it through the input port with the real store (`integration (port)`), or end to end;
   the adapter test asserts only the adapter's part (the status, the page, that the use case was not called).
   **The adapter half of a criterion with both shapes shows a state; it does not replay the change.** Arrange
   the stub once with the outcome the port test of the criterion asserts, make the one request that shows
   it, assert the text — and name the test after what is shown for that state (`showsTwoOfThreeTasksOpen`),
   not after the change (`showsOneOpenTaskLessAfterCompletingOne`): the name the plan gave it after
   `test:` in the adapter shape, unchanged, mapped to that criterion (`tests-planned`). Never perform the scenario's action
   against the stubbed port and then answer the port a second time with the state after it: the second
   answer is yours, the assertion holds with the action deleted, and the name claims a behaviour the test
   cannot prove. The same holds for a value the use case computes — trimmed, counted, sorted: it is the
   stub's arrangement here, never this test's claim. The action's own translation — the request turned
   into the command, the redirect — is an adapter test of its own that asserts the command the port was
   called with. A plan line with the bare `integration` of an older plan is the port shape. An external system
   is stubbed **at the protocol**, with the stub the profile names (`http.stub:` — WireMock,
   WireMock.Net): the stub's answer is the test's arrangement, and allowed. Never a mock of the port
   whose adapter the plan changes — that tests everything except the translation — and never a
   shared or real instance, which makes the test pass or fail on another system. Every adapter the
   plan lists as changed is passed by at least one mapped integration test; a case the adapter
   handles that no scenario names (a malformed body, a status the story does not mention) gets an
   integration test outside the table, named under `## Notes`, like the unit tests of step 3.
   **Every branch the story adds in an adapter has a test** — the success, each refusal, each fallback
   (input that does not parse, so the port is never called): one test per branch, not one per adapter.
   An outgoing adapter that keeps state of its own beside what it stores — an index, a lookup by a second
   key — gets an adapter test that saves, changes and saves again, and asserts the lookup after the
   second save.
