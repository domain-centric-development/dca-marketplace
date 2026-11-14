# Scenario first (BDD): from Given/When/Then to the test

Behaviour-driven development writes the expected behaviour first as a scenario in the domain's words, then turns
each scenario into a test. The scenario is the requirement; the test is its evidence. The rows of `SKILL.md`,
section 4, are the bridge: one row per scenario, one per clause.

## A scenario that can be tested

```text
Scenario: Completing an open task
  Given a list with the open task "Write report"
  When the owner completes "Write report"
  Then "Write report" is done
  And the list shows no open task
```

- **One `When`**: one action. A second action is a second scenario.
- **`Given` names the state** with its values, never the clicks that lead there.
- **`Then` and each `And` after it is one clause** — one statement that can be true or false, with the scenario's
  own values. A clause that quotes a text says it is shown; a clause about what is kept says it is stored.
- Words from the project's glossary, the same word for the same thing in every scenario.

## From scenario to test

1. **Pick the level** — the lowest that observes the `Then` from outside (`SKILL.md`, section 1). One scenario per
   story, its happy path, is end to end; a clause about what is stored goes through the input port with the real
   store; a text only the page shows goes to that adapter's test as well.
2. **`Given` is the arrangement**, built through the input ports with the scenario's values — even where the outcome
   seems not to depend on them. A refusal that answers alike for an empty and a full list still starts from the list
   the scenario names.
3. **`When` is the one call** — the input port, the request, the click.
4. **`Then` and each `And` are one assertion each**, on the element or the value the clause names, in the order the
   scenario gives. A test stops at its first failing assertion, so the red run proves only the first clause: for
   each clause, name the smallest change to the code that breaks it and leaves the others standing, and check that
   the assertion on that clause's line turns red under it.
5. **Name the test after the behaviour** (`completesAnOpenTask`); an end-to-end test's display name is the scenario's
   title, verbatim. The scenario's key never appears in a name, a display name or a comment — the link lives in the
   `Tests` table alone, which survives renumbering.
6. **Record the rows**: the test in `Tests`, every clause with the line that asserts it and its level in `Clauses`.

```java
@Test
@DisplayName("Completing an open task")
void completesAnOpenTask() {
    String title = unique("Write report");
    TaskId id = givenAnOpenTask(owner, title);                         // Given

    completeTask.execute(new CompleteTaskCommand(owner, id));          // When

    assertThat(tasks.findById(id).orElseThrow().isDone()).isTrue();    // Then
    assertThat(listTasks.execute(new ListTasksQuery(owner)).open())    // And
        .isEmpty();
}
```

```text
| criterion            | test                                          |
| completes-open-task  | com.company.tasks.CompleteTaskTest#completesAnOpenTask |

| criterion           | n | clause                        | assertion                  | level |
| completes-open-task | 1 | "Write report" is done        | CompleteTaskTest.java:9    | port  |
| completes-open-task | 2 | the list shows no open task   | CompleteTaskTest.java:10   | port  |
```

## Tools

A Gherkin runner (Cucumber, Reqnroll) is one way to keep scenarios executable; plain tests that follow the steps are
another. Use what the project has. Adding a runner is a stack decision for the person, not part of a story.
