# Port tests: the use case once, through its input port

One use case through its input port in the wired application: real outgoing adapters, the store as the project
runs it in tests (its own database in a container, not an in-memory stand-in), an external system stubbed at the
protocol. Asserts what is stored, refused, published, returned.

## Rules

- **Once per use case and scenario**, never once per calling adapter.
- **No mocked output port.** Several adapters behind one port: each passes one contract test; the port test runs
  one of them.
- **External system stubbed at the protocol**: a real HTTP server on a free port (WireMock in Java, WireMock.Net in
  .NET) answering what the test arranges. Never a shared or real instance.
- **Stored-state clauses are asserted here**, through a query port or the use case's repository, reading what the
  use case wrote — never what the test wrote.
- **A refusal as it leaves the use case**: the returned case with its values, or the exact failure type thrown. The
  adapter test of the same criterion stubs exactly that.
- **A helper running a use case to arrange a state asserts it succeeded.**
- **An event or a message to an unmanaged system** is the one interaction asserted — via the stub's received
  requests or the published event, not a mock call.

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
