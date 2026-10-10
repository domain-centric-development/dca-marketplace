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
