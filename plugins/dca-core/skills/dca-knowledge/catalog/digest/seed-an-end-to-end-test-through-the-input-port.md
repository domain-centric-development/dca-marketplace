# Put an end-to-end test's preconditions in place through the input port — digest

Node: `/recipe/seed-an-end-to-end-test-through-the-input-port.md` — cite it by that path; read it in full only for a decision this digest leaves open.

An end-to-end test is about one interaction: the click, the form, the page under test.

## Steps (first sentence each)

1. **Name the one interaction** the test is about; everything before it is precondition.
2. **Give the precondition data of its own** — a title with a random part, a user of its own — and keep each value in a variable the assertion uses ([Pitfall](/pitfall/a-shared-fixture-makes-tests-interact.md)).
3. **Call the use case for each precondition.** Where the test starts the application in its own process, take the input port from the wired application and call it; assert that it succeeded, so a refusal does not leave the test running on a state that never came about.
4. **Where the application runs beside the test,** put the seeding entry — an endpoint or a command — in the test source set or a test profile, never in production code.
5. **Get the session from an API or a token** and hand it to the browser context.
6. **Check that each step put in place directly has a test through the surface** — the happy path of the story that delivered it.
7. **Perform the one interaction and assert the element it changes**, found by a stable marker and the data the test created.
