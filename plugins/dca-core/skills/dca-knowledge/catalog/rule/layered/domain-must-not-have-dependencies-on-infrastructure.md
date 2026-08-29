---
type: Rule
id: DCA-LAY-002
title: Domain must not have dependencies on Infrastructure
rule: "Domain should not depend on infrastructure concerns (Dependency Inversion Principle)."
constraint: Domain must not have dependencies on Infrastructure.
enforced_by: "LayeredRules#DCA-LAY-002"
status: enforced
rule_set: layered
implementations: [java, dotnet]
tags: [layered, archunit]
---

```java
DcaRule.of(
    "DCA-LAY-002",
    "Domain must not have dependencies on Infrastructure",
    "Domain should not depend on infrastructure concerns (Dependency Inversion Principle)",
    arch ->
        noClasses()
            .that()
            .resideInAnyPackage(layout.domainPattern())
            .should()
            .dependOnClassesThat()
            .resideInAPackage(layout.infrastructurePattern()))
```
