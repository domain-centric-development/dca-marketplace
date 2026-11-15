# Adapter tests: what an incoming adapter makes of a request and a result

One incoming adapter against a stubbed input port, in the framework's slice where it has one (Spring web slice,
ASP.NET Core test host). Asserts only what the adapter produces: the command it makes of a request; the page,
status, redirect or payload it makes of the result and of each refusal. Stubbing the input port is right here: the
adapter is the unit under test, and the use case behind the port has a port test of its own — so an adapter test
never proves a sequence or what is stored.

## Only where the adapter produces what the `Then` says

A quoted text, a status, a redirect, a mark. A value the use case computes (trimmed title, count, sorted list) and
the page shows gets the port test alone: an adapter test of it has nothing left to prove, whatever its name —
`showsATitleWithoutSurroundingSpaces` claims a trim its stub did.

## It shows a state; it does not replay the change

- Arrange the stub once with the outcome the port test of the same criterion asserts, make the one request,
  assert the element.
- Name it after the state shown (`showsTwoOfThreeTasksOpen`), never the change
  (`showsOneOpenTaskLessAfterCompletingOne`, `showsZeroTasksAfterClearing`, `…AfterAFreshStart`): a name that
  tells a sequence claims a behaviour the test cannot prove.
- Never perform the action against the stub and answer a second time with the after-state: the second answer is
  yours, and the assertion holds with the action deleted. Split such a test: the action's translation (below) and
  the state shown, each its own test.
- The arranged state stands in the method name, nowhere else.

## The action's translation is a test of its own

Post the form, assert the command the port was called with (fields, values as passed on); or post unparseable
input and assert the port was not called. Both directions are the adapter's outcome. That test asserts nothing
about the page afterwards. Never assert a value the stub was arranged to return: that is the stub, not the adapter.

## Rules

- **No stored-state clause here** — assert it in the port test; here only the status, the page, port not called.
- **The refusal the stub answers with is the one the port test proves**: same returned case, or the very failure
  type thrown — never a parent or generic one.
- **One test per branch**: success, each refusal, each fallback (unparseable input, port never called).
- **Assert the element, not the page** — by stable marker, role or field, never the page's whole text ("disabled"
  somewhere on the page is true whenever anything is disabled).
- **Locate by a stable marker, never by position among siblings.**

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
