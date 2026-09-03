---
type: Rule
id: DCA-ADV-017
title: Specifications must end with 'Specification'
rule: Specification implementations are part of the domain layer.
constraint: Specifications must end with 'Specification'.
enforced_by: "AdvancedPatternRules#DCA-ADV-017"
status: enforced
rule_set: advanced
implementations: [java, dotnet]
tags: [advanced, archunit]
---

```java
DcaRule.of(
    "DCA-ADV-017",
    "Specifications must end with 'Specification'",
    "Specification implementations are part of the domain layer",
    arch ->
        classes()
            .that()
            .haveSimpleNameEndingWith("Specification")
            .and()
            .areNotInterfaces()
            .and()
            .doNotHaveSimpleName("Specification")
            .should()
            .resideInAnyPackage(arch.allDomainPatterns())
            .allowEmptyShould(true))
```

## Applies to markers

- [Specification<T>](/marker/tactical/specification.md)
