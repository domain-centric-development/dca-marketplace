# Scenario first (BDD): from Given/When/Then to the test

The scenario is the requirement; the test its evidence; the rows of `SKILL.md`, section 4, the bridge.

## A scenario that can be tested

```text
Scenario: Completing an open task
  Given a list with the open task "Write report"
  When the owner completes "Write report"
  Then "Write report" is done
  And the list shows no open task
```

- **One `When`**; a second action is a second scenario.
- **`Given` names the state** with its values, never the clicks.
- **`Then` and each `And` is one clause**: true or false, with the scenario's values. A quoted text says it is
  shown; a kept value says it is stored.
- Glossary words, the same word for the same thing in every scenario.

## From scenario to test

1. **Level**: the lowest that observes the `Then` from outside (`SKILL.md`, section 1).
2. **`Given` is the arrangement**, built through the input ports with the scenario's values — even where the
   outcome seems not to depend on them (a refusal alike for empty and full list still starts from the named list).
3. **`When` is the one call** — input port, request, click.
4. **One assertion per clause**, on the element or value it names, in the scenario's order. The red run proves only
   the first clause: per clause, name the smallest code change that breaks it alone and check that the assertion on
   that clause's line turns red under it.
5. **Name after the behaviour** (`completesAnOpenTask`); an e2e test's display name is the scenario title, verbatim.
   The scenario's key never appears in a name, display name or comment — the link lives in the `Tests` table alone.
6. **Record the rows**: the test in `Tests`, every clause with its asserting line and level in `Clauses`.

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

A Gherkin runner (Cucumber, Reqnroll) or plain tests following the steps — use what the project has. Adding a
runner is the person's stack decision, not part of a story.
