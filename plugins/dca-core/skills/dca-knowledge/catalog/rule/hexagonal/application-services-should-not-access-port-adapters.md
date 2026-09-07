---
type: Rule
id: DCA-HEX-002
title: Application Services should not access port adapters
rule: "Application services should only depend on domain and outbound ports, not adapters."
constraint: Application Services should not access port adapters.
enforced_by: "HexagonalRules#DCA-HEX-002"
status: enforced
rule_set: hexagonal
implementations: [java, dotnet]
tags: [hexagonal, archunit]
---

```java
DcaRule.of(
    "DCA-HEX-002",
    "Application Services should not access port adapters",
    "Application services should only depend on domain and outbound ports, not adapters",
    arch ->
        noClasses()
            .that()
            .resideInAnyPackage(arch.allApplicationPatterns())
            .should()
            .dependOnClassesThat()
            .resideInAnyPackage(arch.allAdapterPatterns())
            .allowEmptyShould(true))
```
