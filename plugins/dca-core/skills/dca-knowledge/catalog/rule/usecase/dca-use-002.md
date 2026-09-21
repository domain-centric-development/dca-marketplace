---
type: Rule
id: DCA-USE-002
title: "Types named *Command reside in the application layer"
rule: "Use case commands should be in application layer (CQRS pattern)."
constraint: "Types named *Command reside in the application layer."
selects: Classes under the base package whose simple name ends with Command.
checks: "Each resides in an application package of some module root (<module>.application..). A Command in a domain, adapter or infrastructure package is reported."
enforced_by: "UseCaseRules#DCA-USE-002"
status: enforced
rule_set: usecase
implementations: [java, dotnet]
tags: [usecase, archunit]
---

# Types named *Command reside in the application layer

## Selection

Classes under the base package whose simple name ends with Command.

## Check

Each resides in an application package of some module root (<module>.application..). A Command in a domain, adapter or infrastructure package is reported.

## .NET reading

**Selection.** Types under the root namespace whose name ends with Command.

**Check.** Each resides in an application namespace of some module root (<module>.Application). A Command in a domain, adapter or infrastructure namespace is reported.

## Implementation

```java
DcaRule.of(
        "DCA-USE-002",
        "Types named *Command reside in the application layer",
        "Use case commands should be in application layer (CQRS pattern)",
        arch ->
            classes()
                .that()
                .haveSimpleNameEndingWith("Command")
                .and()
                .resideInAnyPackage(layout.basePackage() + "..")
                .should()
                .resideInAnyPackage(arch.allApplicationPatterns())
                .allowEmptyShould(true))
    .selecting("Classes under the base package whose simple name ends with Command.")
    .checking(
        "Each resides in an application package of some module root (<module>.application..). A Command in a domain, adapter or infrastructure package is reported.")
```

## Architecture queries

[DcaArchitecture](/reference/architecture.md) methods the rule relies on: `allApplicationPatterns()` - how they resolve packages is described there and in [DcaLayout](/reference/layout.md).
### C# expression

```csharp
DcaRule.Of(
        "DCA-USE-002",
        "Types named *Command reside in the application layer",
        "Use case commands should be in application layer (CQRS pattern)",
        arch =>
            Types()
                .That()
                .HaveNameEndingWith("Command")
                .And()
                .ResideInNamespaceMatching(DcaLayout.Below(layout.RootNamespace))
                .Should()
                .ResideInNamespaceMatching(DcaLayout.AnyOf(arch.AllApplicationPatterns())))
    .Selecting(
        "Types under the root namespace whose name ends with Command.")
    .Checking(
        "Each resides in an application namespace of some module root"
            + " (<module>.Application). A Command in a domain, adapter or infrastructure"
            + " namespace is reported.")
```

## Configured by

- [DcaArchitecture](/reference/architecture.md)
- [DcaLayout](/reference/layout.md)
