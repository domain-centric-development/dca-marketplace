# End-to-end tests: the happy path, and its preconditions through the input ports

An end-to-end test drives the running application through its surface. One scenario per story — its happy path —
gets one; a scenario whose `Then` only a browser observes is the exception, with the reason written down. How a
browser test is written — Page Objects, stable selectors, explicit waits, the fake clock, setting up a runner — is
the `e2e-testing` skill. This file is what holds for any end-to-end test, browser or not.

## The application is the test's own

The suite starts the application itself, on a free port, with what it needs — an external system as a stub started
first, the database the application's tests already use. A suite that drives whatever answers on an address tests
whatever happens to answer there.

## Fresh fixture

Each test creates its own records — a title with a random part, a user of its own — and asserts only about them.
The suite shares one application and often one store, so a test that reads what another wrote fails in one order and
passes in the other. A seeded record is shared: a test that changes it, or needs one of its values exact, creates its
own instead. Run the **whole** suite once before handing over; a test that passes alone and fails in the suite is not
done.

## Preconditions through the input ports, never through SQL

The test is one more incoming adapter: it calls the same use cases the page calls, so the domain's invariants hold
for the data it creates and a schema change does not break it. Rows written with SQL build a state the application
could never reach. Clicking the preconditions through the pages makes the test slow and makes it fail on pages it is
not about.

- Application started in the test's process: take the input port from the wired application and call it.
- Application running beside the test: the seeding entry — an endpoint, a command — lives in the test source set or
  a test profile, **never in production code**.
- A session comes from an API or a token handed to the client; only the login test fills the login form.

```java
@Test
@DisplayName("Completes an open task")
void completesAnOpenTask() {
    String title = unique("Write report");
    addTask.execute(new AddTaskCommand(owner, title));    // precondition, through the input port

    TaskListPage list = TaskListPage.navigateTo(page);
    list.complete(title);                                 // the one interaction under test

    assertThat(list.task(title)).hasAttribute("data-state", "done");
}
```

## Skipping the clicks loses no coverage

Every step put in place directly has a test of its own that proves it through the surface — the happy path of the
story that delivered it. Only an epic's journey test walks the whole way, page by page, to the epic's outcome; it is
green when it is written and guards the flow, it is not a story's criterion. A precondition no test proves through
the surface is a gap: write that test first, or click the step through and say why.

## Names and red

The display name is the scenario's title. The test fails first on an expectation, not on an action: expect the form
to be visible before filling it, so a form that does not exist yet names what is missing instead of timing out.
