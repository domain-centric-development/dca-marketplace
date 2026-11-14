# Adapter tests: what an incoming adapter makes of a request and a result

An adapter test runs one incoming adapter against a stubbed input port. It asserts what only the adapter produces:
the command it makes of a request, and the page, status, redirect or payload it makes of the result and of each
refusal. Where the framework offers a slice for the adapter alone (a web slice in Spring, a test host in ASP.NET
Core), it runs in that. Stubbing the input port is right here: the adapter is the unit under test, and the use case
behind the port has a port test of its own.

## Only where the adapter produces what the `Then` says

A criterion gets an adapter test only where its `Then` names something the adapter itself produces: a quoted text,
a status, a redirect, a mark on the page. A value the use case computes — a trimmed title, a count, a sorted list —
and the page merely shows is proven by the port test; an adapter test of it has nothing left to prove, whatever its
name (`showsATitleWithoutSurroundingSpaces` claims a trim its stub did). Such a criterion gets the port test alone.

## It shows a state; it does not replay the change

Arrange the stub once with the outcome the port test of the same criterion asserts, make the one request that shows
it, assert the element — and name the test after the state shown (`showsTwoOfThreeTasksOpen`), never after the change
(`showsOneOpenTaskLessAfterCompletingOne`). Never perform the scenario's action against the stubbed port and then
answer a second time with the state after it: the second answer is yours, the assertion holds with the action
deleted, and the name claims a behaviour the test cannot prove.

The name is the record: the state the stub was arranged with stands in the method name, and nowhere else.

## The action's translation is a test of its own

The adapter's translation goes both ways, and both are its outcome: the command it makes of a request, and — for
input that does not parse — that it does not call the use case at all. Post the form, assert the command the port
was called with — its fields, the value as the adapter passed it on; or post the bad input and assert that the port
was not called. That test asserts nothing about what the page shows afterwards. What is never asserted is a value the
stub was arranged to return: that is the stub, not the adapter.

## Rules

- **A clause about what is stored is never asserted here.** The stub answers what you told it. Assert it in the port
  test; here assert only the adapter's part — the status, the page, that the port was not called.
- **A refusal the stub answers with is the one the port test proves**: the same returned case where the context
  returns refusals, the very failure type — never a parent, never a generic one — where it throws them.
- **Every branch the adapter has gets a test**: the success, each refusal, each fallback (input that does not parse,
  so the port is never called). One test per branch, not one per adapter.
- **Assert the element, not the page.** By its stable marker, its role, its field — never the page's whole text:
  "disabled" somewhere on the page is true whenever anything is disabled.
- **Locate by a stable marker, never by position among siblings** — the rule of end-to-end tests holds for every
  test that reads a rendered page.

```java
@Test
void showsTwoOfThreeTasksOpen() throws Exception {
    when(listTasks.execute(any())).thenReturn(new ListTasksResult(List.of(
        open("Write report"), open("Book room"), done("Send invoice"))));

    mvc.perform(get("/tasks"))
       .andExpect(xpath("//*[@data-test='open-count']").string("2 of 3 open"));
}
```

```csharp
[Fact]
public async Task ShowsTwoOfThreeTasksOpen()
{
    _listTasks.Execute(Arg.Any<ListTasksQuery>()).Returns(new ListTasksResult([
        Open("Write report"), Open("Book room"), Done("Send invoice")]));

    var page = await _client.GetPageAsync("/tasks");

    Assert.Equal("2 of 3 open", page.QuerySelector("[data-test='open-count']")!.TextContent);
}
```
