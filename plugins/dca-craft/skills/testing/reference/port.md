# Port tests: the use case once, through its input port

A port test runs one use case through its input port in the wired application: real outgoing adapters, the store
as the project runs it in tests (its own database in a container, not an in-memory stand-in), an external system
stubbed at the protocol. It asserts the scenario's business outcome — what is stored, refused, published,
returned. It is the test of the use case, whichever adapter calls it.

## Rules

- **Once per use case and scenario**, never once per incoming adapter that calls it.
- **No mocked output port.** The output port's adapter is part of what the test proves; a mock proves the mock.
  Where an output port has several adapters, each passes one contract test of what the port promises, and the
  port test runs one of them.
- **An external system is stubbed at the protocol** — a real HTTP server on a free port answering what the test
  arranges (WireMock in Java, WireMock.Net in .NET). The stub's answer is the arrangement; the adapter builds its
  request and reads the response exactly as in production. Never a shared or real instance of the other system.
- **A clause about what is stored is asserted here** — through a query port or the repository the use case uses,
  reading back what the use case wrote, never what the test wrote itself.
- **A refusal is asserted as it leaves the use case**: the returned case with its values where the context returns
  refusals, the exact failure type where it throws them. The adapter test of the same criterion stubs exactly that.
- **A helper that runs a use case to arrange a state asserts that it succeeded.** An ignored result swallows a
  refusal, and the test goes on from a state that never came about.
- **An event or a message to an unmanaged system** is the one interaction asserted — through the stub's received
  requests or the published event, not through a call on a mock.

## Shape

```java
@Test
void completesAnOpenTask() {
    TaskId id = givenAnOpenTask(unique("Write report"));          // through the input port, success asserted

    CompleteTaskResult result = completeTask.execute(new CompleteTaskCommand(id));

    assertThat(result).isInstanceOf(CompleteTaskResult.Completed.class);
    assertThat(tasks.findById(id).orElseThrow().isDone()).isTrue();
}
```

```csharp
[Fact]
public async Task CompletesAnOpenTask()
{
    var id = await GivenAnOpenTask(Unique("Write report"));

    var result = await _completeTask.Execute(new CompleteTaskCommand(id));

    Assert.IsType<CompleteTaskResult.Completed>(result);
    Assert.True((await _tasks.FindById(id))!.IsDone);
}
```

The fixture is fresh: the task is this test's own, with a unique title, so the test runs beside every other one.
