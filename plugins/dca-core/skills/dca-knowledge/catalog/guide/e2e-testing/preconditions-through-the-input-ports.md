---
type: Section
title: Preconditions through the input ports
chapter: E2E Testing for Domain-Centric Architecture
source: guide
tags: [guide, section]
---

An end-to-end test is about one interaction: the click, the form, the page under test. Everything before it is
precondition, and how it gets there decides whether the test is fast, stable and honest.

### Fresh fixture, end to end

**Rule: an end-to-end test builds its own preconditions, with data of its own, and reads nothing another test
can change.**

The rule of [Test Levels](/guide/testing-levels/a-test-that-holds.md) holds here with more force: the
suite shares one running application and often one store, so a test that reads what another one wrote fails in
one order and passes in the other. Each test creates its own records — a title with a random part, a user of its
own — and asserts only about them. A seeded record is shared: a test that changes it, or needs one of its values
to be exact, creates its own instead.

### Through the input ports, never through SQL

**Rule: an end-to-end test puts its preconditions in place through the application's input ports, never by
writing to the database.**

The test is one more incoming adapter. It calls the same use cases the page calls, so every invariant of the
domain holds for the data it creates, and a change to the schema does not break it. Rows written with SQL pass
both by: the test builds a state the application could never reach, and it breaks on a renamed column the
application handles fine. Clicking the preconditions through the pages is the other mistake: the test gets slow
and fails on pages it is not about.

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

Where the test starts the application in its own process, it takes the input port from the wired application.
Where the application runs beside the test, the entry that seeds it — an endpoint, a command — lives in the test
source set or in a test profile, never in production code. A seeding endpoint that ships is a way past every
check the page makes.

A session is a precondition too. The test obtains it from an API or a token and hands it to the browser context;
only the test of the login itself fills the login form.

### Skipping the clicks loses no coverage

**Rule: every step an end-to-end test puts in place directly has a test of its own that proves it through the
surface.**

The test above adds its task through the input port because adding a task has an end-to-end test of its own —
the happy path of the story that delivered it. Only an epic's journey test walks the whole way, page by page,
to the epic's outcome ([Test Levels](/guide/testing-levels/smoke-test-happy-path-test-journey-test.md)). A
precondition that no test proves through the surface is a gap: write that test first, or click the step through
here and say why.

---
