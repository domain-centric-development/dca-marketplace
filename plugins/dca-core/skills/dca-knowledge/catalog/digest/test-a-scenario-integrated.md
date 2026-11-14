# Test a scenario integrated, the external system stubbed at the protocol — digest

Node: `/recipe/test-a-scenario-integrated.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Test one scenario of a story below the page: the use case runs through the wired application — its input port or its HTTP surface, whichever the scenario's `When` names — with real adapters and persistence as the project runs it in tests.

## Steps (first sentence each)

1. **Take the scenario's level from the plan.** The story's happy path is tested end to end; every other scenario is tested here, unless its `Then` only a browser can observe ([Which level for a scenario](/decision/test-level-for-a-scenario.md)).
2. **Start the application as the tests run it** — the project's integration source set or test project, with the persistence it uses in tests.
3. **Point the adapter at a stub.** Start an HTTP stub on a free port and set the adapter's base URL from configuration to the stub's URL.
4. **Arrange** — the `Given`: state through the application's own ports, and the external system's answer as the stub's arrangement (a status, a body, a delay for a timeout).
5. **Act once** — the `When`, through the input port or the HTTP surface.
6. **Assert the `Then`** — the result or response, the state the application now shows, and where the scenario names it the request the adapter sent to the stub.
7. **Cover the adapter's cases** — a case the adapter handles that no scenario names (a malformed body, a status the story does not mention) gets an integration test of its own, outside the story's criteria.
