# dca-init — a project with its own vocabulary

What a retrofit sets in the layout instead of switching rules off. Java and .NET side by side.

## Marker roles (INIT-MARKERS → Role)

The rules select every building block through a role. Point a role at the project's type and keep the code as it is:

```java
DcaLayout.forBasePackage("com.acme.billing")
    .withMarkers(DcaMarkers.dca()
        .named("acme")
        .withAggregateRoot("com.acme.platform.ddd.AggregateRoot")
        .withOutputPort("com.acme.platform.ports.OutputPort")
        .withRepository("com.acme.platform.ports.Repository"));
```

```csharp
DcaLayout.ForRootNamespace("Acme.Billing")
    .WithMarkers(new DcaMarkers
    {
        AggregateRoot = "Acme.Platform.Ddd.IAggregateRoot",
        OutputPort = "Acme.Platform.Ports.IOutputPort",
        Repository = "Acme.Platform.Ports.IRepository",
    });
```

Limits:

- A role names one type, matched by assignability. Where the project has two shapes (a use case with and one
  without a result), point the role at their common supertype.
- Every port role needs `outputPort` set as well; `DCA-HEX-009` measures each port against it.
- Four method names stay fixed: `save` and `deleteById` / `delete` on the repository, `publishAndClearEvents` on
  the domain-event publisher, `registerEvent` on the aggregate root. A vocabulary with other names is selected
  and then found to save nothing; keep the names or switch the affected ids off with a reason.

## Own context annotations

The project's own `@BoundedContext`, `@SharedKernel` and `@IntegrationEventType` (Java, on `package-info` and on
the event) or attributes (.NET, on the context marker class) are roles too: `withBoundedContext(fqn)`,
`withSharedKernel(fqn)`, `withIntegrationEventType(fqn)` / the `DcaMarkers` properties of the same name. Their
members are read by name — `name` / `Name` and `description` / `Description`; Java reads them from the compiled
class, so `CLASS` retention is enough. A member the rules need and the annotation lacks is reported with package
and member. The relationship annotations (`@Upstream`, `@ExternalUpstream`, `@Partnership`, `@OpenHostService`)
stay the library's. Where no package declares a shared kernel, `<base>.<sharedKernelSubpackage>` (`sharedkernel`
by default) is taken as one.

## A start-up module named like a layer (INIT-EXCLUDE)

`withExcludedPackages("com.acme.billing.app")` / `WithExcludedNamespaces("Acme.Billing.App")` — below the base
package; the module is left out of the import, a dependency on it still counts. The test report names the base
package when it still resolves as a module root.

## Ports that never leave the process (INIT-LOCAL-PORTS)

`withLocalOutputPorts("com.acme.platform.LocalPort")` / `WithLocalOutputPorts("Acme.Platform.ILocalPort")`,
matched by assignability, so one own supertype covers them all. `DCA-USE-013` then reports only the ports that
call out of the process from inside a declarative transaction.

## Input-port suffix (INIT-SUFFIX)

`withInputPortSuffix("UseCase")` / `WithInputPortSuffix("UseCase")` for interfaces named `*UseCase` (.NET:
`I*UseCase`); `DCA-NAM-003` then holds the project to it.
