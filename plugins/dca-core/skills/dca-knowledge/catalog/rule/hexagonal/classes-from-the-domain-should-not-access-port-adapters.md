---
type: Rule
id: DCA-HEX-001
title: Classes from the domain should not access port adapters
rule: "Domain should not depend on adapters (ports and adapters pattern)."
constraint: Classes from the domain should not access port adapters.
enforced_by: "HexagonalRules#DCA-HEX-001"
status: enforced
rule_set: hexagonal
implementations: [java, dotnet]
tags: [hexagonal, archunit]
---

```java
DcaRule.of(
    "DCA-HEX-001",
    "Classes from the domain should not access port adapters",
    "Domain should not depend on adapters (ports and adapters pattern)",
    arch ->
        noClasses()
            .that()
            .resideInAnyPackage(arch.allDomainModelPatterns())
            .should()
            .dependOnClassesThat()
            .resideInAnyPackage(arch.allAdapterPatterns())
            .allowEmptyShould(true))
```
