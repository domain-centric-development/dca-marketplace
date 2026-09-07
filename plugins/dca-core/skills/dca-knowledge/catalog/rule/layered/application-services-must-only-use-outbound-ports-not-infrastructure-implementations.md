---
type: Rule
id: DCA-LAY-003
title: "Application Services must only use outbound ports (not infrastructure implementations)"
rule: "Application services should only use outbound ports declared as interfaces (port.out), not infrastructure implementation details."
constraint: "Application Services must only use outbound ports (not infrastructure implementations)."
enforced_by: "LayeredRules#DCA-LAY-003"
status: enforced
rule_set: layered
implementations: [java, dotnet]
tags: [layered, archunit]
---

```java
DcaRule.of(
    "DCA-LAY-003",
    "Application Services must only use outbound ports (not infrastructure implementations)",
    "Application services should only use outbound ports declared as interfaces (port.out), not"
        + " infrastructure implementation details",
    arch ->
        noClasses()
            .that()
            .resideInAnyPackage(arch.allApplicationPatterns())
            .should()
            .dependOnClassesThat(arch.infrastructureImplementation())
            .allowEmptyShould(true))
```
