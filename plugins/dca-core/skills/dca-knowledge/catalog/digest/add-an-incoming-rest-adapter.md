# Add an incoming REST adapter — digest

Node: `/recipe/add-an-incoming-rest-adapter.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Expose a use case to the outside world through a primary (driving) adapter.

## Steps (first sentence each)

1. **Place it in `adapter/incoming/`** — REST resources under the api package, web controllers under the web package (they are separated on purpose — [Java package structure](/guide/package-structure.md)).
2. **Name by role** — a REST endpoint class ends with `Resource`; an MVC class ends with `Controller` (a `*PageController`).
3. **Depend on the input port only** — inject the `{Name}InputPort`, build the `{Name}Command`/`{Name}Query` from the request, call `execute`.
4. **Map at the edge** — translate the use case `{Name}Result` into a `*Response` DTO (or a view model for web) in the adapter; DTOs and view models live here, never in domain or application.
5. **Stay in your context** — an incoming adapter accesses only its own bounded context (event consumers and Open Host Services are the sanctioned exceptions).
6. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/rest-resource.md` REST resource skeleton (incoming adapter injecting input ports): Domain-free skeleton for a REST resource: a primary (incoming) adapter that exposes use cases over HTTP. — code: `/template/rest-resource/java.md`
- `/template/view-model.md` ViewModel skeleton (page-specific, primitive-only presentation record): Domain-free skeleton for a **ViewModel**: a page-specific record that transforms a domain read model (or a use-case `Result`) into **primitives only** for a server-rendered template. — code: `/template/view-model/java.md`
- `/template/page-controller.md` Page controller skeleton (server-rendered web adapter): Domain-free skeleton for a **page controller**: a primary (incoming) adapter that drives use cases from a server-rendered browser page. — code: `/template/page-controller/java.md`
- `/template/mcp-tool-provider.md` MCP tool provider skeleton (incoming adapter exposing use cases as MCP tools): Domain-free skeleton for an **MCP tool provider**: a primary (incoming) adapter that exposes a bounded context's use cases as [Model Context Protocol](https://modelcontextprotocol.io) tools an AI model can invoke. — code: `/template/mcp-tool-provider/java.md`
