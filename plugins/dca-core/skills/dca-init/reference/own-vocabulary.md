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

Where the project marks its building blocks with annotations instead of supertypes, the role takes a marker
(0.11): `withValue(DcaMarker.ofAnnotation("com.acme.ddd.ValueObject"))` / `WithValue(DcaMarker.OfAttribute(
"Acme.Ddd.ValueObjectAttribute"))`, or `anyOf` the type and the annotation during a migration. The annotation counts
on the class and on its supertypes. A building block is never named by its package.

## Commands and queries (0.11)

The rules recognise a use case's input as a command or a query by its name, `…Command` / `…Query`. A project that
names every input `…Command`, the read-only ones included, gets its queries reported as commands (`DCA-HEX-014`
flags its GET handlers). Ask what tells them apart in the code: a supertype or an annotation →
`withCommand(DcaMarker.ofType(..))` / `withQuery(..)`; nothing → the read-only inputs are renamed `…Query`, a task
for the project, not a setting.

## Layers by the project's package or annotation (0.11)

A layer is its package below a module root by default. A project whose packages differ names the package
(`withOutgoingAdapter(DcaMarker.ofPackage("adapter.out"))`); one that already marks its layers with annotations —
its own or jMolecules' — names the annotation: `DcaMarker.anyOf(DcaMarker.ofPackage("adapter.outgoing"),
DcaMarker.ofAnnotation("<its layer annotation>"))`. On a `package-info` it holds for the package tree below; on a
class it places that class. In .NET the attribute sits on the type, on the assembly, or as an assembly attribute
that names the namespace. The library ships no annotations; never add one to the project for this. Run the suite
once with `DCA-LAY-007` (experimental) on: it lists the classes of a module that sit in no layer. A project with no
layers yet runs without the `hexagonal` and `layered` sets (`dca.rules.off.sets`, with the reason) until they stand:
`DCA-HEX-019` reports every output port implementation that sits in no layer.

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
