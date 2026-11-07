# Template placeholders

Part of the `dca-new` skill: the placeholders its templates carry and what fills each.

- `{{basePackage}}`, `{{context}}` — base package + bounded context name (Java, lowercase)
- `{{rootNamespace}}`, `{{Context}}`, `{{contextDisplayName}}` — root namespace + PascalCase context segment + the
  display name in `[BoundedContext("…")]` (C#)
- `{{FeatureSegment}}`, `{{IncomingSegment}}`, `{{OutgoingSegment}}` — PascalCase twins of the Java segments (C#)
- `{{usecasename}}` (lowercase, no separator) — for use case folder
- `{{featureSegment}}` — empty in a flat context, `{feature}.` in a grouped one (so the package reads `application.{{featureSegment}}{{usecasename}}`)
- `{{Name}}` — PascalCase name (e.g. `PlaceOrder`, `Order`, `TransferPolicy`)
- `{{commandOrQuery}}` — `Command` or `Query`
- `{{useCaseImplSuffix}}` — `UseCase` (default) or `ApplicationService` etc.
- `{{aggregateRootMarker}}` — short class name to use (`BaseAggregateRoot` if available, else `AggregateRoot`)
- `{{repositoryMarker}}`, `{{storeMarker}}`, `{{useCaseMarker}}`, `{{idMarker}}` etc. — short names
- `{{storedType}}`, `{{StoredType}}`, `{{queryMethods}}` — for Mode store
- `{{domainServiceMarkerFqn}}`, `{{serviceDescription}}`, `{{operation}}` / `{{Operation}}`, `{{operationParameters}}`,
  `{{ResultType}}`, `{{aggregateList}}`, `{{domainImports}}` / `{{domainUsings}}` — for Mode domainservice
- `{{incomingSubfolder}}`, `{{outgoingSubfolder}}` — `incoming` (default) or `in`
- `{{useLombok}}` — `true` / `false` based on project convention
- `{{returnsRefusals}}` — `true` when the context returns its refusals (the technical description's
  `Refusals (<context>): returned`, else `Refusals: returned`) **and** the use case has at least one expected
  refusal; `false` otherwise — a context that throws, or a use case nobody can refuse, keeps the plain result record
- `{{SuccessCase}}` — the success case, named for what happened (`Placed`, `Cancelled`, `Found`)
- `{{refusalCases}}` — one nested case per expected refusal, named after the refusal, carrying the ids and figures it
  compared and implementing the refusal marker: Java `    record OrderNotFound(OrderId orderId) implements
  {{Name}}Result, Refusal {}`, C# `    public sealed record OrderNotFound(OrderId OrderId) : IRefusal;`
- `{{refusalMarkerFqn}}` — the refusal marker's import: `dev.domaincentric.dca.buildingblocks.application.Refusal`,
  or the project's own marker where convention discovery found one aliased to it
- `{{caseTypeList}}` — C#: the cases in order, success first, as `{{Name}}Result.{{SuccessCase}}, {{Name}}Result.OrderNotFound, …`
