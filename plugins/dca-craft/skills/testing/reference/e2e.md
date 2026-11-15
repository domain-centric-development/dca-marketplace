# End-to-end tests: the happy path, and its preconditions through the input ports

One per story — its happy path; a `Then` only a browser observes is the exception, reason written down. Browser
specifics (Page Objects, selectors, waits, fake clock, runner setup): the `e2e-testing` skill. This file holds for
any e2e test.

## The application is the test's own

The suite starts the application itself on a free port, with an external system as a stub started first and the
database the application's tests already use. Never drive whatever answers on an address.

## Fresh fixture

- Each test creates its own records (random-part title, own user) and asserts only about them.
- A test that changes a seeded record, or needs one of its values exact, creates its own.
- Run the **whole** suite once before handing over; passes alone, fails in the suite = not done.

## Preconditions through the input ports, never through SQL

The test is one more incoming adapter calling the same use cases the page calls. No SQL rows (unreachable state),
no clicking preconditions through pages (slow, fails on pages it is not about).

- Application in the test's process: take the input port from the wired application and call it.
- Application running beside the test: the seeding entry (endpoint, command) lives in the test source set or a test
  profile, **never in production code**.
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

- Every step put in place directly has its own test through the surface — the happy path of the story that
  delivered it.
- Only an epic's journey test walks the whole way, page by page, to the epic's outcome; green when written, guards
  the flow, not a story's criterion.
- A precondition no test proves through the surface is a gap: write that test first, or click the step through and
  say why.

## Names and red

Display name = the scenario's title. Fail first on an expectation, not an action: expect the form visible before
filling it, so a missing form names what is missing instead of timing out.
