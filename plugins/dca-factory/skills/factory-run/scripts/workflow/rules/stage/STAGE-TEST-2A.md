---
id: STAGE-TEST-2A
part: told
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
   test. **A refusal the stub throws is one a port test proves:** the stub throws the very failure type —
   the same class, never a parent or a generic one — that the port test of the same criterion asserts the
   real use case throws, and both tests stand in that criterion's rows of the table. Together they hold
   the seam the stub cuts: rename the failure or throw another, and the port test turns red. A failure
   no port test asserts is a stub of nothing — write the port test beside it. **A clause about what is stored** — the list stays unchanged, the task remains open, it is done
   afterwards — is never asserted here: the stub answers what you told it, so the assertion holds whatever
   the code does. Assert it through the input port with the real store (`integration (port)`), or end to end;
   the adapter test asserts only the adapter's part (the status, the page, that the use case was not called). A plan line with the bare `integration` of an older plan is the port shape. An external system
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
